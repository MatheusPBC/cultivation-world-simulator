"""Voluntary, local household loans for a currently unpaid public payroll.

The institution must ask from a current unpaid-funds receipt. A household sees
only its own dated local notice and account. Economy transfers existing money;
the no-interest principal is repaid only by a later, separately selected
borrower affordance.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import FamilyLoan, FamilyLoanRequest
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import family_loan_notice_id
from src.classes.governance.models import FamilyLoanNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue

from .economy import _causes, _delta
from .events import record_event
from .household_provisioning import household_stock_id


REQUEST_ACTION = "request_family_loan"
LEND_ACTION = "lend_to_polity"
REPAY_ACTION = "repay_family_loan"
REQUEST_WINDOW_DAYS = 60
LOAN_TERM_DAYS = 180


@dataclass(frozen=True)
class FamilyLoanRequestOption(SocietyValue):
    id: str
    actor_ref: EntityRef
    settlement_id: str
    account_id: str
    purpose: str
    employment_contract_id: str | None
    production_facility_id: str | None
    source_event_id: str
    principal: int

    def decision(self):
        return {
            "action": REQUEST_ACTION,
            "actor_ref": self.actor_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


@dataclass(frozen=True)
class FamilyLoanOfferOption(SocietyValue):
    id: str
    actor_ref: EntityRef
    notice_id: str
    request_id: str
    principal: int

    def decision(self):
        return {
            "action": LEND_ACTION,
            "actor_ref": self.actor_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


@dataclass(frozen=True)
class FamilyLoanRepaymentOption(SocietyValue):
    id: str
    actor_ref: EntityRef
    loan_id: str
    principal: int

    def decision(self):
        return {
            "action": REPAY_ACTION,
            "actor_ref": self.actor_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


def _event(world, event_id):
    return world.event_index().get(event_id) if event_id else None


def _current_unpaid_contract(world, contract):
    event = _event(world, contract.last_event_id)
    account = world.economy.accounts.get(contract.account_id)
    gross = contract.staffing_target * contract.wage_per_worker
    if (
        contract.last_outcome != "unpaid_funds"
        or contract.staffing_target <= 0
        or contract.last_reviewed_day != world.clock.absolute_day
        or event is None
        or event.event_type != "permanent_employment_unpaid"
        or event.day != world.clock.absolute_day
        or account is None
        or account.owner_ref != contract.employer_ref
        or account.balance >= gross
    ):
        return None
    return event, account, gross - account.balance


def _current_food_production_shortfall(world, facility):
    """A current production receipt may finance only its next food batch wages."""
    economy = world.economy
    source = _event(world, facility.last_event_id)
    stock = economy.stocks.get(facility.stock_id)
    recipe = economy.recipes.get(facility.recipe_id)
    account = economy.accounts.get(facility.payroll_account_id)
    payload = (
        source.causal_payload.get("production")
        if source is not None and isinstance(source.causal_payload, dict)
        else None
    )
    limits = payload.get("limits") if isinstance(payload, dict) else None
    if (
        source is None or source.event_type != "production_limited"
        or source.day != world.clock.absolute_day
        or stock is None or recipe is None or account is None
        or "food" not in recipe.outputs
        or account.owner_ref != stock.owner_ref
        or payload.get("facility_id") != facility.id
        or payload.get("observed_day") != world.clock.absolute_day
        or payload.get("batches") != 0
        or payload.get("limitations") != ["payroll_funds"]
        or not isinstance(limits, dict)
        or limits.get("payroll_funds") != 0
        or any(type(value) is not int or value < 1
               for key, value in limits.items() if key != "payroll_funds")
    ):
        return None
    return source, account, recipe.workers * facility.wage_per_worker


def family_loan_request_options(world, actor):
    """Borrow only against a current unpaid obligation or one food batch."""
    if (
        not isinstance(actor, EntityRef)
        or actor.kind != "polity"
        or actor.id not in world.society.polities
        or any(
            not can_actor_act_for(world, actor, actor, scope)
            for scope in ("trade", "supply")
        )
    ):
        return ()
    if any(
        item.borrower_ref == actor
        and item.status in {"open", "partially_funded"}
        and world.clock.absolute_day <= item.expires_day
        for item in world.economy.family_loan_requests.values()
    ):
        return ()
    options = []
    for contract in sorted(
        world.economy.employment_contracts.values(), key=lambda item: item.id
    ):
        if contract.employer_ref != actor:
            continue
        unpaid = _current_unpaid_contract(world, contract)
        if unpaid is None:
            continue
        source, account, principal = unpaid
        if not any(
            group.settlement_id == contract.settlement_id
            and world.society.available_count(group.id) > 0
            for group in world.society.population.values()
        ):
            continue
        if any(
            request.source_event_id == source.id
            for request in world.economy.family_loan_requests.values()
        ):
            continue
        option_id = (
            f"family-loan-request:{actor.id}:{contract.id}:{source.id}:"
            f"{account.balance}:{world.clock.absolute_day}"
        )
        options.append(
            FamilyLoanRequestOption(
                id=option_id,
                actor_ref=actor,
                settlement_id=contract.settlement_id,
                account_id=contract.account_id,
                purpose="employment_payroll",
                employment_contract_id=contract.id,
                production_facility_id=None,
                source_event_id=source.id,
                principal=principal,
            )
        )
    for facility in sorted(world.economy.facilities.values(), key=lambda item: item.id):
        stock = world.economy.stocks[facility.stock_id]
        if stock.owner_ref != actor:
            continue
        current = _current_food_production_shortfall(world, facility)
        if current is None:
            continue
        source, account, principal = current
        settlement_id = stock.location_id
        if not any(
            group.settlement_id == settlement_id
            and world.society.available_count(group.id) > 0
            for group in world.society.population.values()
        ):
            continue
        if any(item.source_event_id == source.id
               for item in world.economy.family_loan_requests.values()):
            continue
        option_id = (
            f"family-loan-request:{actor.id}:food-production:{facility.id}:{source.id}:"
            f"{account.balance}:{world.clock.absolute_day}"
        )
        options.append(FamilyLoanRequestOption(
            id=option_id,
            actor_ref=actor,
            settlement_id=settlement_id,
            account_id=facility.payroll_account_id,
            purpose="food_production_payroll",
            employment_contract_id=None,
            production_facility_id=facility.id,
            source_event_id=source.id,
            principal=principal,
        ))
    return tuple(options)


def _current_household_report(world, actor, group):
    report = world.knowledge.settlement_report(actor, group.settlement_id)
    if (
        report is None
        or report.observed_day != world.clock.absolute_day
        or report.channel != "local_settlement_report"
        or report.recipient_ref != actor
        or report.publisher_ref != actor
    ):
        return None
    try:
        world.knowledge._validate_settlement_report(world, world.event_index(), report)
    except ValueError:
        return None
    return report


def _lendable_balance(world, group, account):
    """Preserve one day's locally priced food need before exposing loan sizes."""
    market = world.economy.markets.get(group.settlement_id)
    if market is None or "food" not in market.prices:
        return 0
    pantry = world.economy.stocks.get(household_stock_id(group.id))
    stored_food = pantry.goods.get("food", 0) if pantry is not None else 0
    food_gap = max(0, group.count - stored_food)
    immediate_food_reserve = food_gap * market.prices["food"]
    return max(0, account.balance - immediate_food_reserve)


def family_loan_options(world, actor):
    """Recompose local loans from a household's own notice and account only."""
    if not isinstance(actor, EntityRef) or actor.kind != "population_group":
        return ()
    group = world.society.population.get(actor.id)
    if (
        group is None
        or group.count <= 0
        or world.society.available_count(group.id) != group.count
    ):
        return ()
    report = _current_household_report(world, actor, group)
    if report is None:
        return ()
    account = world.economy.accounts.get(f"household:{group.id}")
    if account is None or account.owner_ref != actor:
        return ()
    lendable = _lendable_balance(world, group, account)
    options = []
    for notice in world.knowledge.family_loan_notices_for_actor(actor):
        request = world.economy.family_loan_requests.get(notice.request_id)
        if (
            notice.status != "requested"
            or request is None
            or request.status not in {"open", "partially_funded"}
            or world.clock.absolute_day > notice.expires_day
            or world.clock.absolute_day > request.expires_day
            or group.settlement_id != notice.settlement_id
            or request.borrower_ref != notice.borrower_ref
        ):
            continue
        already_funded = sum(
            loan.principal
            for loan in world.economy.family_loans.values()
            if loan.request_id == request.id
        )
        remaining = request.principal - already_funded
        if remaining <= 0 or any(
            loan.request_id == request.id and loan.lender_ref == actor
            for loan in world.economy.family_loans.values()
        ):
            continue
        maximum = min(remaining, lendable)
        amounts = tuple(sorted({maximum, maximum // 2}, reverse=True))
        for amount in amounts:
            if amount <= 0:
                continue
            option_id = (
                f"family-loan:{request.id}:{group.id}:{amount}:"
                f"{request.last_event_id}:{report.event_id}:"
                f"{account.last_event_id or 'opening'}"
            )
            options.append(
                FamilyLoanOfferOption(
                    id=option_id,
                    actor_ref=actor,
                    notice_id=notice.id,
                    request_id=request.id,
                    principal=amount,
                )
            )
    return tuple(options)


def family_loan_repayment_options(world, actor):
    if (
        not isinstance(actor, EntityRef)
        or actor.kind != "polity"
        or any(
            not can_actor_act_for(world, actor, actor, scope)
            for scope in ("trade", "supply")
        )
    ):
        return ()
    options = []
    for loan in sorted(world.economy.family_loans.values(), key=lambda item: item.id):
        account = world.economy.accounts.get(loan.borrower_account_id)
        if (
            loan.borrower_ref != actor
            or loan.status != "active"
            or world.clock.absolute_day < loan.due_day
            or account is None
            or account.balance < loan.principal
        ):
            continue
        options.append(
            FamilyLoanRepaymentOption(
                id=f"family-loan-repay:{loan.id}:{account.balance}:{loan.last_event_id}",
                actor_ref=actor,
                loan_id=loan.id,
                principal=loan.principal,
            )
        )
    return tuple(options)


def record_family_loan_decision(world, actor, option_id, *, action, decision_source):
    builders = {
        REQUEST_ACTION: family_loan_request_options,
        LEND_ACTION: family_loan_options,
        REPAY_ACTION: family_loan_repayment_options,
    }
    if action not in builders:
        raise ValueError("unknown family loan action")
    option = next(
        (item for item in builders[action](world, actor) if item.id == option_id), None
    )
    if option is None:
        raise ValueError("family loan affordance is stale or unknown")
    if (
        not isinstance(decision_source, dict)
        or not isinstance(decision_source.get("kind"), str)
        or not decision_source["kind"]
    ):
        raise ValueError("family loan decision requires an explicit source")
    return record_event(
        world,
        f"{action}_decided",
        "Uma decisão de crédito familiar foi registrada.",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(),
        causal_payload={"decision_source": decision_source},
        cause_ids=_option_causes(world, option),
    )


def _option_causes(world, option):
    if isinstance(option, FamilyLoanRequestOption):
        account = world.economy.accounts[option.account_id]
        owner_event_id = (
            world.economy.employment_contracts[option.employment_contract_id].last_event_id
            if option.employment_contract_id is not None
            else world.economy.facilities[option.production_facility_id].last_event_id
        )
        return _causes(option.source_event_id, owner_event_id, account.last_event_id)
    if isinstance(option, FamilyLoanOfferOption):
        request = world.economy.family_loan_requests[option.request_id]
        notice = world.knowledge.family_loan_notices[option.notice_id]
        group = world.society.population[option.actor_ref.id]
        account = world.economy.accounts[f"household:{group.id}"]
        report = world.knowledge.settlement_report(
            option.actor_ref, group.settlement_id
        )
        pantry = world.economy.stocks.get(household_stock_id(group.id))
        return _causes(
            request.last_event_id,
            notice.event_id,
            group.last_event_id,
            account.last_event_id,
            report.event_id if report else None,
            pantry.last_event_ids.get("food") if pantry else None,
        )
    loan = world.economy.family_loans[option.loan_id]
    return _causes(
        loan.last_event_id,
        world.economy.accounts[loan.borrower_account_id].last_event_id,
        world.economy.accounts[loan.lender_account_id].last_event_id,
    )


def _selected_decision(world, event_id, actor, action, option):
    decision = world.event_index().get(event_id)
    if (
        decision is None
        or decision.fact_kind != FactKind.DECISION
        or decision.causal_origin is not CausalOrigin.ACTOR_DECISION
        or decision.day != world.clock.absolute_day
        or decision.decision != option.decision()
        or actor != option.actor_ref
    ):
        raise ValueError(
            "family loan requires the current actor's exact affordance decision"
        )
    return decision


def request_family_loan(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next(
        (
            item
            for item in family_loan_request_options(candidate, actor)
            if item.id == option_id
        ),
        None,
    )
    if option is None:
        raise ValueError("family loan request option is stale or unknown")
    decision = _selected_decision(
        candidate, decision_event_id, actor, REQUEST_ACTION, option
    )
    require_authority(candidate, actor, "trade")
    require_authority(candidate, actor, "supply")
    contract = None
    if option.purpose == "employment_payroll":
        contract = candidate.economy.employment_contracts[option.employment_contract_id]
        current = _current_unpaid_contract(candidate, contract)
    else:
        facility = candidate.economy.facilities[option.production_facility_id]
        current = _current_food_production_shortfall(candidate, facility)
    if current is None:
        raise ValueError("family loan request no longer matches its material source")
    source, account, principal = current
    if source.id != option.source_event_id or principal != option.principal:
        raise ValueError("family loan request no longer matches its material source")
    request_id = f"family-loan-request:{decision.id}"
    expires_day = candidate.clock.absolute_day + REQUEST_WINDOW_DAYS
    request_event = record_event(
        candidate,
        "family_loan_requested",
        "A instituição pediu um empréstimo local sem juros.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "decision_event_id": decision.id,
            "actor_ref": actor.to_dict(),
            "selected_affordance_id": option.id,
        },
        deltas=(
            _delta("family_loan_request", request_id, "status", None, "open"),
            _delta("family_loan_request", request_id, "principal", None, principal),
            _delta(
                "family_loan_request", request_id, "source_event_id", None, source.id
            ),
            _delta("family_loan_request", request_id, "purpose", None, option.purpose),
            *(() if option.production_facility_id is None else (
                _delta("family_loan_request", request_id, "production_facility_id",
                       None, option.production_facility_id),
            )),
            _delta("family_loan_request", request_id, "expires_day", None, expires_day),
        ),
        cause_ids=_causes(decision.id, *_option_causes(candidate, option)),
    )
    request = FamilyLoanRequest(
        id=request_id,
        borrower_ref=actor,
        settlement_id=option.settlement_id,
        account_id=option.account_id,
        purpose=option.purpose,
        employment_contract_id=contract.id if contract is not None else None,
        production_facility_id=option.production_facility_id,
        source_event_id=source.id,
        principal=principal,
        created_day=candidate.clock.absolute_day,
        expires_day=expires_day,
        decision_event_id=decision.id,
        selected_affordance_id=option.id,
        request_event_id=request_event.id,
        last_event_id=request_event.id,
    )
    candidate.economy.family_loan_requests[request.id] = request
    recipients = tuple(
        sorted(
            (
                group
                for group in candidate.society.population.values()
                if group.settlement_id == request.settlement_id
                and candidate.society.available_count(group.id) > 0
            ),
            key=lambda group: group.id,
        )
    )
    if not recipients:
        raise ValueError(
            "a family loan request requires a locally present population group"
        )
    notices = [
        FamilyLoanNotice(
            id=family_loan_notice_id(
                request.id, EntityRef("population_group", group.id)
            ),
            recipient_ref=EntityRef("population_group", group.id),
            request_id=request.id,
            borrower_ref=actor,
            settlement_id=request.settlement_id,
            purpose=request.purpose,
            requested_principal=request.principal,
            expires_day=request.expires_day,
            requested_day=candidate.clock.absolute_day,
            learned_day=candidate.clock.absolute_day,
            event_id="pending",
        )
        for group in recipients
    ]
    delivered = record_event(
        candidate,
        "family_loan_request_delivered",
        "Um pedido local de crédito foi afixado no assentamento.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(
            _delta(
                "family_loan_notice",
                notice.id,
                "observation",
                None,
                notice.observation(),
            )
            for notice in notices
        ),
        cause_ids=(request_event.id,),
    )
    for notice in notices:
        candidate.knowledge.family_loan_notices[notice.id] = notice.model_copy(
            update={"event_id": delivered.id}
        )
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return request


def lend_to_polity(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next(
        (
            item
            for item in family_loan_options(candidate, actor)
            if item.id == option_id
        ),
        None,
    )
    if option is None:
        raise ValueError("family loan offer is stale or unknown")
    decision = _selected_decision(
        candidate, decision_event_id, actor, LEND_ACTION, option
    )
    request = candidate.economy.family_loan_requests[option.request_id]
    notice = candidate.knowledge.family_loan_notices[option.notice_id]
    lender_account = candidate.economy.accounts[f"household:{actor.id}"]
    borrower_account = candidate.economy.accounts[request.account_id]
    max_lendable = _lendable_balance(
        candidate, candidate.society.population[actor.id], lender_account
    )
    if (
        request.status not in {"open", "partially_funded"}
        or notice.status != "requested"
        or candidate.clock.absolute_day > request.expires_day
        or option.principal
        > min(
            request.principal
            - sum(
                loan.principal
                for loan in candidate.economy.family_loans.values()
                if loan.request_id == request.id
            ),
            max_lendable,
        )
        or option.principal <= 0
        or borrower_account.owner_ref != request.borrower_ref
    ):
        raise ValueError("family loan offer is no longer materially available")
    loan_id = f"family-loan:{request.id}:{actor.id}"
    if loan_id in candidate.economy.family_loans:
        raise ValueError("this household already funded the request")
    origin = CausalOrigin.ACTOR_DECISION
    payload = {
        "decision_event_id": decision.id,
        "actor_ref": actor.to_dict(),
        "selected_affordance_id": option.id,
    }
    loan_ids = (*request.family_loan_ids, loan_id)
    funded_total = (
        sum(
            item.principal
            for item in candidate.economy.family_loans.values()
            if item.request_id == request.id
        )
        + option.principal
    )
    request_status = (
        "funded" if funded_total == request.principal else "partially_funded"
    )
    if funded_total > request.principal:
        raise ValueError("family loan contributions exceed the requested principal")
    notice_updates = [
        item
        for item in candidate.knowledge.family_loan_notices.values()
        if item.request_id == request.id
    ]
    notices_to_close = tuple(
        item
        for item in notice_updates
        if item.id == notice.id or request_status == "funded"
    )
    funded_notices = tuple(
        (
            item,
            item.model_copy(
                update={
                    "status": "funded",
                    "learned_day": candidate.clock.absolute_day,
                    "event_id": "pending",
                }
            ),
        )
        for item in notices_to_close
    )
    event = record_event(
        candidate,
        "family_loan_funded",
        "Uma família emprestou dinheiro existente à instituição.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=origin,
        causal_payload=payload,
        deltas=(
            _delta(
                "account",
                borrower_account.id,
                "balance",
                borrower_account.balance,
                borrower_account.balance + option.principal,
            ),
            _delta(
                "account",
                lender_account.id,
                "balance",
                lender_account.balance,
                lender_account.balance - option.principal,
            ),
            _delta(
                "family_loan_request",
                request.id,
                "status",
                request.status,
                request_status,
            ),
            _delta(
                "family_loan_request",
                request.id,
                "family_loan_ids",
                request.family_loan_ids,
                loan_ids,
            ),
            _delta("family_loan", loan_id, "created", False, True),
            _delta("family_loan", loan_id, "request_id", None, request.id),
            _delta("family_loan", loan_id, "principal", None, option.principal),
            _delta(
                "family_loan",
                loan_id,
                "due_day",
                None,
                candidate.clock.absolute_day + LOAN_TERM_DAYS,
            ),
            _delta(
                "family_loan",
                loan_id,
                "borrower_ref",
                None,
                request.borrower_ref.to_dict(),
            ),
            _delta("family_loan", loan_id, "lender_ref", None, actor.to_dict()),
            *(
                _delta(
                    "family_loan_notice",
                    old.id,
                    "observation",
                    old.observation(),
                    new.observation(),
                )
                for old, new in funded_notices
            ),
        ),
        cause_ids=_causes(
            decision.id,
            request.last_event_id,
            notice.event_id,
            *(old.event_id for old, _ in funded_notices),
            borrower_account.last_event_id,
            lender_account.last_event_id,
        ),
    )
    loan = FamilyLoan(
        id=loan_id,
        request_id=request.id,
        borrower_ref=request.borrower_ref,
        lender_ref=actor,
        borrower_account_id=borrower_account.id,
        lender_account_id=lender_account.id,
        lender_notice_id=notice.id,
        principal=option.principal,
        created_day=candidate.clock.absolute_day,
        due_day=candidate.clock.absolute_day + LOAN_TERM_DAYS,
        decision_event_id=decision.id,
        selected_affordance_id=option.id,
        funded_event_id=event.id,
        last_event_id=event.id,
    )
    candidate.economy.family_loans[loan.id] = loan
    candidate.economy.family_loan_requests[request.id] = request.model_copy(
        update={
            "status": request_status,
            "family_loan_ids": loan_ids,
            "last_event_id": event.id,
        }
    )
    candidate.economy.accounts[borrower_account.id] = borrower_account.model_copy(
        update={
            "balance": borrower_account.balance + option.principal,
            "last_event_id": event.id,
        }
    )
    candidate.economy.accounts[lender_account.id] = lender_account.model_copy(
        update={
            "balance": lender_account.balance - option.principal,
            "last_event_id": event.id,
        }
    )
    for old, pending in funded_notices:
        updated = pending.model_copy(update={"event_id": event.id})
        candidate.knowledge.family_loan_notices[old.id] = updated
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return loan


def repay_family_loan(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next(
        (
            item
            for item in family_loan_repayment_options(candidate, actor)
            if item.id == option_id
        ),
        None,
    )
    if option is None:
        raise ValueError("family loan repayment option is stale or unknown")
    decision = _selected_decision(
        candidate, decision_event_id, actor, REPAY_ACTION, option
    )
    require_authority(candidate, actor, "trade")
    require_authority(candidate, actor, "supply")
    loan = candidate.economy.family_loans[option.loan_id]
    borrower = candidate.economy.accounts[loan.borrower_account_id]
    lender = candidate.economy.accounts[loan.lender_account_id]
    notice = candidate.knowledge.family_loan_notices[loan.lender_notice_id]
    if (
        loan.status != "active"
        or candidate.clock.absolute_day < loan.due_day
        or borrower.balance < loan.principal
        or notice.status != "funded"
    ):
        raise ValueError("family loan is not currently repayable")
    origin = CausalOrigin.ACTOR_DECISION
    payload = {
        "decision_event_id": decision.id,
        "actor_ref": actor.to_dict(),
        "selected_affordance_id": option.id,
    }
    notice_after = notice.model_copy(
        update={
            "status": "repaid",
            "learned_day": candidate.clock.absolute_day,
            "event_id": "pending",
        }
    )
    repayment_event_id = f"event:{len(candidate.events) + 1}"
    event = record_event(
        candidate,
        "family_loan_repaid",
        "A instituição devolveu o principal do empréstimo à família.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=origin,
        causal_payload=payload,
        deltas=(
            _delta(
                "account",
                borrower.id,
                "balance",
                borrower.balance,
                borrower.balance - loan.principal,
            ),
            _delta(
                "account",
                lender.id,
                "balance",
                lender.balance,
                lender.balance + loan.principal,
            ),
            _delta("family_loan", loan.id, "status", "active", "repaid"),
            _delta(
                "family_loan", loan.id, "repayment_event_id", None, repayment_event_id
            ),
            _delta(
                "family_loan_notice",
                notice.id,
                "observation",
                notice.observation(),
                notice_after.observation(),
            ),
        ),
        cause_ids=_causes(
            decision.id,
            loan.last_event_id,
            loan.funded_event_id,
            borrower.last_event_id,
            lender.last_event_id,
            notice.event_id,
        ),
    )
    candidate.economy.accounts[borrower.id] = borrower.model_copy(
        update={"balance": borrower.balance - loan.principal, "last_event_id": event.id}
    )
    candidate.economy.accounts[lender.id] = lender.model_copy(
        update={"balance": lender.balance + loan.principal, "last_event_id": event.id}
    )
    candidate.economy.family_loans[loan.id] = loan.model_copy(
        update={
            "status": "repaid",
            "repayment_event_id": event.id,
            "last_event_id": event.id,
        }
    )
    candidate.knowledge.family_loan_notices[notice.id] = notice_after.model_copy(
        update={"event_id": event.id}
    )
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def _context(world, actor, options):
    result = {
        "you_are": actor.to_dict(),
        "today": world.clock.absolute_day,
        "terms": {
            "interest": 0,
            "term_days": LOAN_TERM_DAYS,
            "repayment_requires_new_decision": True,
        },
        "loan_decisions": [
            {
                "id": option.id,
                "principal": option.principal,
                "loan_id": getattr(option, "loan_id", None),
                "request_id": getattr(option, "request_id", None),
            }
            for option in options
        ],
    }
    if actor.kind == "population_group":
        group = world.society.population.get(actor.id)
        account = world.economy.accounts.get(f"household:{actor.id}")
        if group is not None and account is not None:
            lendable = _lendable_balance(world, group, account)
            result["own_household_credit"] = {
                "balance": account.balance,
                "food_reserve": account.balance - lendable,
                "lendable_after_food_reserve": lendable,
                "settlement_id": group.settlement_id,
            }
        result["known_requests"] = [
            {
                "request_id": notice.request_id,
                "borrower_ref": notice.borrower_ref.to_dict(),
                "settlement_id": notice.settlement_id,
                "purpose": notice.purpose,
                "requested_principal": notice.requested_principal,
                "expires_day": notice.expires_day,
                "status": notice.status,
            }
            for notice in world.knowledge.family_loan_notices_for_actor(actor)
        ]
    else:
        balances = {}
        for option in options:
            account_id = (
                option.account_id
                if isinstance(option, FamilyLoanRequestOption)
                else world.economy.family_loans[option.loan_id].borrower_account_id
                if isinstance(option, FamilyLoanRepaymentOption)
                else None
            )
            if account_id is not None and account_id in world.economy.accounts:
                balances[account_id] = world.economy.accounts[account_id].balance
        result["own_treasuries"] = [
            {"account_id": key, "balance": balances[key]} for key in sorted(balances)
        ]
    return result


def family_loan_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def adapter(name, options, label, action, execute):
        return DiscretionaryAdapter(
            name=name,
            family="family_credit",
            options_fn=options,
            label_fn=label,
            causes_fn=_option_causes,
            execute_fn=lambda world, actor, option_id, decision_id: execute(
                world, actor, option_id, decision_id
            ),
            situation_fn=_context,
        )

    return (
        adapter(
            "family_loan_request",
            family_loan_request_options,
            lambda option: (
                f"Pedir {option.principal} unidades para "
                f"{'uma folha não paga' if option.purpose == 'employment_payroll' else 'um lote de alimento limitado por folha'} "
                f"em {option.settlement_id}; sem juros, vencimento em 180 dias."
            ),
            REQUEST_ACTION,
            request_family_loan,
        ),
        adapter(
            "family_loan_lend",
            family_loan_options,
            lambda option: (
                f"Emprestar voluntariamente {option.principal} unidades à instituição, com principal devido em 180 dias e sem juros."
            ),
            LEND_ACTION,
            lend_to_polity,
        ),
        adapter(
            "family_loan_repayment",
            family_loan_repayment_options,
            lambda option: (
                f"Devolver {option.principal} unidades do empréstimo {option.loan_id}; transfere o principal agora."
            ),
            REPAY_ACTION,
            repay_family_loan,
        ),
    )


__all__ = [
    "family_loan_adapters",
    "family_loan_options",
    "family_loan_repayment_options",
    "family_loan_request_options",
    "lend_to_polity",
    "record_family_loan_decision",
    "repay_family_loan",
    "request_family_loan",
]
