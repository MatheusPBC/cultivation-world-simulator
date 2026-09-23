"""Economy-owned standing local payrolls.

The contract is created only from an employer's current affordance and exact
decision.  It creates neither people nor money.  At each later monthly
boundary the Economy revalidates local workers and funds, then delegates the
actual payment/reservation to ``settle_work``.
"""

from copy import deepcopy
from hashlib import sha256

from src.classes.economy.models import PermanentEmploymentContract
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue

from .economy import _causes, _delta
from .events import record_event
from .labor import settle_work
from .actor_dossier import _own_production_readings


ACTION = "create_permanent_employment"
MAX_COHORT_FRACTION_DENOMINATOR = 5
PRESSURED_COHORT_FRACTION_DENOMINATOR = 2


class PermanentEmploymentOption(SocietyValue):
    """One engine-bounded employer offer.  Only this ID is decided."""

    id: str
    employer_ref: EntityRef
    settlement_id: str
    cohort_id: str
    work_site_id: str
    occupation: str
    stock_id: str
    account_id: str
    workforce_limit: int
    wage_per_worker: int

    def decision(self):
        return {"action": ACTION, "actor_ref": self.employer_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    return next((event for event in world.events if event.id == event_id), None)


def _contract_id(group_id):
    return f"employment:{group_id}"


def _site_supports_occupation(world, site, occupation):
    facilities = tuple(facility for facility in world.economy.facilities.values()
                        if facility.site_id == site.id)
    if not facilities:
        return True
    return occupation in {world.economy.recipes[facility.recipe_id].occupation
                          for facility in facilities}


def _site_wage(world, site, occupation):
    """Reuse the authored wage of a compatible local production line.

    A standing job cannot invent a salary. Sites without a facility retain the
    conservative V1 floor of one unit; authored facilities provide the shared
    payroll premise used by production and household income.
    """
    wages = tuple(
        facility.wage_per_worker
        for facility in world.economy.facilities.values()
        if facility.site_id == site.id
        and world.economy.recipes[facility.recipe_id].occupation == occupation
    )
    return max(wages, default=1)


def _workforce_limit(world, group):
    """Scale one standing offer only when the settlement has material pressure.

    The limit is still engine-owned and bounded.  A quiet settlement keeps the
    conservative one-fifth offer; observed food, health or unrest pressure may
    justify a half-cohort payroll so recovery can actually reach households.
    The owner still revalidates the available workers and treasury at execution.
    """
    needs = world.economy.needs.get(group.settlement_id)
    pressured = (needs is not None and
                 (needs.missing_food > 0 or needs.health < 700 or needs.unrest >= 250))
    denominator = (PRESSURED_COHORT_FRACTION_DENOMINATOR if pressured
                   else MAX_COHORT_FRACTION_DENOMINATOR)
    return max(1, group.count // denominator)


def _food_labor_pressure(world, settlement_id):
    """Whether a dated food line is already short of workers.

    A standing contract for the same farmer cohort would reserve people before
    production and make the shortage self-reinforcing.  This reading comes
    only from the latest typed production receipt and current settlement
    condition; it does not infer a policy or move anyone.
    """
    need = world.economy.needs.get(settlement_id)
    if need is None:
        return False
    for facility in world.economy.facilities.values():
        stock = world.economy.stocks.get(facility.stock_id)
        recipe = world.economy.recipes.get(facility.recipe_id)
        if (stock is None or recipe is None or stock.location_id != settlement_id
                or recipe.occupation != "farmer" or "food" not in recipe.outputs):
            continue
        event = next((item for item in reversed(world.events) if item.id == facility.last_event_id), None)
        if event is None or event.day != world.clock.absolute_day:
            continue
        if any(delta.owner_kind == "production" and delta.owner_id == facility.id
               and delta.aspect == "labor_shortfall" and delta.after.isdecimal()
               and int(delta.after) > 0 for delta in event.deltas):
            return True
    return False


def _standing_monthly_cost(world, account_id):
    """Cost of one payroll account's already accepted recurring payrolls.

    A permanent-employment option creates a new obligation rather than a
    one-shot purchase.  The option builder therefore must not offer another
    contract when the current owner account cannot cover the existing
    obligations plus its first payroll.  This conservative reading never
    forecasts revenue or creates credit; a later dated decision can observe a
    genuinely replenished balance and re-open the option.
    """
    return sum(
        contract.workforce_limit * contract.wage_per_worker
        for contract in world.economy.employment_contracts.values()
        if contract.account_id == account_id
    )


def permanent_employment_options(world, employer):
    """Enumerate only funded, local, currently authorized standing jobs.

    A fifth of an existing working cohort is the V1 ceiling.  The engine owns
    that workforce limit and wage; the institution may choose only which
    concrete offer to establish.  Nothing is reserved until the later payroll.
    """
    if (not isinstance(employer, EntityRef)
            or employer.kind not in {"polity", "organization"}
            or any(not can_actor_act_for(world, employer, employer, scope) for scope in ("supply", "trade"))):
        return ()
    contracted = {contract.cohort_id for contract in world.economy.employment_contracts.values()}
    options = []
    for group in sorted(world.society.population.values(), key=lambda item: item.id):
        if group.id in contracted or group.occupation == "dependent" or group.count <= 0:
            continue
        # Do not create a standing reservation for farmers while a current
        # food line is labor-bound.  The group may still receive and accept a
        # workforce transition affordance when another owner enumerates one.
        if group.occupation == "farmer" and _food_labor_pressure(world, group.settlement_id):
            continue
        workforce_limit = _workforce_limit(world, group)
        sites = sorted((site for site in world.map.infrastructure_sites.values()
                        if site.owner_ref == employer and site.enabled and site.integrity > 0
                        and group.settlement_id in {settlement.id for settlement in world.society.settlements.values()
                                                    if settlement.region_id in site.region_ids}
                        and _site_supports_occupation(world, site, group.occupation)),
                       key=lambda item: item.id)
        stocks = sorted((stock for stock in world.economy.stocks.values()
                         if stock.owner_ref == employer and stock.location_id == group.settlement_id),
                        key=lambda item: item.id)
        accounts = sorted((account for account in world.economy.accounts.values()
                           if account.owner_ref == employer), key=lambda item: item.id)
        for site in sites:
            for stock in stocks:
                for account in accounts:
                    wage = _site_wage(world, site, group.occupation)
                    candidate_cost = workforce_limit * wage
                    committed_cost = _standing_monthly_cost(world, account.id)
                    if (account.balance < candidate_cost
                            or committed_cost + candidate_cost > account.balance):
                        continue
                    opaque_terms = "|".join((stock.id, account.id, str(group.last_event_id),
                                              repr(sorted(stock.last_event_ids.items())),
                                              str(account.last_event_id)))
                    option = PermanentEmploymentOption(
                        id=(f"permanent-employment:{employer.kind}:{employer.id}:{group.settlement_id}:{group.id}:"
                            f"{site.id}:{group.occupation}:{workforce_limit}:{wage}:{world.clock.absolute_day}:"
                            f"{sha256(opaque_terms.encode()).hexdigest()[:12]}"),
                        employer_ref=employer, settlement_id=group.settlement_id, cohort_id=group.id,
                        work_site_id=site.id, occupation=group.occupation, stock_id=stock.id, account_id=account.id,
                        workforce_limit=workforce_limit, wage_per_worker=wage,
                    )
                    options.append(option)
    return tuple(options)


def record_permanent_employment_decision(world, employer, option_id):
    option = next((item for item in permanent_employment_options(world, employer) if item.id == option_id), None)
    if option is None:
        raise ValueError("permanent employment option is stale or unknown")
    return record_event(world, "permanent_employment_decided",
                        "A instituição decidiu estabelecer um vínculo de trabalho local.",
                        fact_kind=FactKind.DECISION, decision=option.decision(),
                        cause_ids=_causes(*_event_provenance(world, option)))


def _event_provenance(world, option):
    group = world.society.population[option.cohort_id]
    stock = world.economy.stocks[option.stock_id]
    account = world.economy.accounts[option.account_id]
    return (group.last_event_id, *(stock.last_event_ids.values()), account.last_event_id)


def _current_option(world, decision):
    payload = decision.decision if decision is not None else None
    try:
        employer = EntityRef.from_dict(payload.get("actor_ref")) if isinstance(payload, dict) else None
    except (KeyError, TypeError, ValueError):
        employer = None
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != world.clock.absolute_day
            or not isinstance(payload, dict) or set(payload) != {"action", "actor_ref", "selected_affordance_id"}
            or payload.get("action") != ACTION):
        return None
    return next((option for option in permanent_employment_options(world, employer)
                 if option.id == payload.get("selected_affordance_id") and option.decision() == payload), None)


def create_permanent_employment(world, option_id, *, decision_event_id):
    """Materially establish one contract after recompiling the selected option."""
    candidate = deepcopy(world)
    decision = _event(candidate, decision_event_id)
    option = _current_option(candidate, decision)
    if option is None or option.id != option_id:
        raise ValueError("permanent employment option is stale or unknown")
    contract_id = _contract_id(option.cohort_id)
    if contract_id in candidate.economy.employment_contracts:
        raise ValueError("cohort already has a permanent employment contract")
    require_authority(candidate, option.employer_ref, "supply")
    require_authority(candidate, option.employer_ref, "trade")
    # Revalidate every physical term immediately before persistence.  The
    # option itself is transient; these are canonical contract terms.
    group = candidate.society.population.get(option.cohort_id)
    stock = candidate.economy.stocks.get(option.stock_id)
    account = candidate.economy.accounts.get(option.account_id)
    if (group is None or group.settlement_id != option.settlement_id or group.occupation != option.occupation
            or candidate.society.available_count(group.id) < option.workforce_limit
            or stock is None or stock.owner_ref != option.employer_ref or stock.location_id != option.settlement_id
            or account is None or account.owner_ref != option.employer_ref
            or account.balance < option.workforce_limit * option.wage_per_worker):
        raise ValueError("permanent employment terms are no longer material")
    provisional = PermanentEmploymentContract(
        id=contract_id, employer_ref=option.employer_ref, settlement_id=option.settlement_id,
        cohort_id=option.cohort_id, work_site_id=option.work_site_id, occupation=option.occupation, stock_id=option.stock_id,
        account_id=option.account_id, workforce_limit=option.workforce_limit,
        wage_per_worker=option.wage_per_worker, created_day=candidate.clock.absolute_day,
        decision_event_id=decision.id, selected_affordance_id=option.id,
        created_event_id="pending", last_reviewed_day=candidate.clock.absolute_day,
        last_outcome="created", last_event_id="pending",
    )
    event = record_event(
        candidate, "permanent_employment_created",
        f"{group.id}: vínculo permanente local de até {option.workforce_limit} trabalhador(es) estabelecido.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("employment_contract", contract_id, "created", False, True),),
        cause_ids=_causes(decision.id, *_event_provenance(candidate, option)),
    )
    contract = provisional.model_copy(update={"created_event_id": event.id, "last_event_id": event.id})
    candidate.economy.employment_contracts[contract.id] = contract
    candidate.economy.validate(candidate)
    candidate.society.validate(set(candidate.map.regions), candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.employment_contracts[contract.id]


def _blocker(world, contract, available):
    group = world.society.population.get(contract.cohort_id)
    site = world.map.infrastructure_sites.get(contract.work_site_id)
    stock = world.economy.stocks.get(contract.stock_id)
    account = world.economy.accounts.get(contract.account_id)
    if (site is None or site.owner_ref != contract.employer_ref or not site.enabled or site.integrity <= 0
            or contract.settlement_id not in {settlement.id for settlement in world.society.settlements.values()
                                              if settlement.region_id in site.region_ids}
            or stock is None or stock.owner_ref != contract.employer_ref or stock.location_id != contract.settlement_id
            or account is None or account.owner_ref != contract.employer_ref
            or any(not can_actor_act_for(world, contract.employer_ref, contract.employer_ref, scope)
                   for scope in ("supply", "trade"))):
        return "unavailable"
    if (group is None or group.settlement_id != contract.settlement_id
            or group.occupation != contract.occupation
            or available.get(contract.cohort_id, 0) < contract.workforce_limit):
        return "unpaid_labor"
    if account.balance < contract.workforce_limit * contract.wage_per_worker:
        return "unpaid_funds"
    return None


def settle_permanent_employment(world, available):
    """Attempt every standing contract once per monthly boundary.

    The contract is never a scheduled transfer.  Economy still revalidates its
    current account, local cohort, authority, and shared work availability.
    """
    for contract in sorted(world.economy.employment_contracts.values(), key=lambda item: item.id):
        if contract.last_reviewed_day == world.clock.absolute_day:
            continue
        blocker = _blocker(world, contract, available)
        group = world.society.population.get(contract.cohort_id)
        account = world.economy.accounts.get(contract.account_id)
        causes = _causes(contract.last_event_id,
                          group.last_event_id if group is not None else None,
                          account.last_event_id if account is not None else None)
        if blocker is not None:
            event = record_event(
                world, "permanent_employment_unpaid",
                f"{contract.cohort_id}: vínculo local não foi pago ({blocker}).",
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(
        _delta("employment_contract", contract.id, "last_reviewed_day",
                           contract.last_reviewed_day, world.clock.absolute_day),
                    _delta("employment_contract", contract.id, "last_outcome", contract.last_outcome, blocker),
                ),
                cause_ids=causes,
            )
            world.economy.employment_contracts[contract.id] = contract.model_copy(
                update={"last_reviewed_day": world.clock.absolute_day, "last_outcome": blocker,
                        "last_event_id": event.id})
            continue
        settle_work(
            world, work_id=contract.id, account_id=contract.account_id, stock_id=contract.stock_id,
            occupation=contract.occupation, worker_count=contract.workforce_limit,
            wage=contract.wage_per_worker, available=available, production_event_id=contract.last_event_id,
            required_workers={contract.cohort_id: contract.workforce_limit},
        )
        payroll = world.economy.payrolls[contract.id]
        event = record_event(
            world, "permanent_employment_settled",
            f"{contract.cohort_id}: vínculo local pagou {payroll.gross} unidade(s) de salário.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(
                _delta("employment_contract", contract.id, "last_reviewed_day",
                       contract.last_reviewed_day, world.clock.absolute_day),
                _delta("employment_contract", contract.id, "last_outcome", contract.last_outcome, "paid"),
            ),
            cause_ids=_causes(contract.last_event_id, payroll.last_event_id),
        )
        world.economy.employment_contracts[contract.id] = contract.model_copy(
            update={"last_reviewed_day": world.clock.absolute_day, "last_outcome": "paid",
                    "last_event_id": event.id})


def _situation(world, actor, options):
    """Expose public labor pressure without leaking employer balances.

    Employment choices are institution-owned, but the decision is better
    grounded when the provider can compare the current settlement reports
    with the concrete, already-funded jobs the engine enumerated.  Account
    balances, stock quantities and other private terms stay inside the owner
    and are revalidated by ``create_permanent_employment``.
    """
    reports = {
        report.settlement_id: report
        for report in world.knowledge.settlements_for_actor(actor)
        if report.publisher_ref == actor
    }
    return {
        "you_are": actor.to_dict(),
        "today": world.clock.absolute_day,
        "own_production_readings": _own_production_readings(world, actor),
        "settlement_reports": [
            {"settlement_id": report.settlement_id, "missing_food": report.missing_food,
             "health": report.health, "unrest": report.unrest,
             "observed_day": report.observed_day, "event_id": report.event_id}
            for report in sorted(reports.values(), key=lambda item: item.settlement_id)
        ],
        "employment_options": [
            {"id": option.id, "settlement_id": option.settlement_id,
             "cohort_id": option.cohort_id, "occupation": option.occupation,
             "work_site_id": option.work_site_id,
             "workforce_limit": option.workforce_limit,
             "wage_per_worker": option.wage_per_worker,
             "pressure": ({"missing_food": reports[option.settlement_id].missing_food,
                           "health": reports[option.settlement_id].health,
                           "unrest": reports[option.settlement_id].unrest}
                          if option.settlement_id in reports else None)}
            for option in options
        ],
    }


def permanent_employment_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def execute(world, actor, option_id, decision_event_id):
        create_permanent_employment(world, option_id, decision_event_id=decision_event_id)

    return (DiscretionaryAdapter(
        name="permanent_employment", family="employment", options_fn=permanent_employment_options,
        label_fn=lambda option: f"Estabelecer vínculo local para {option.cohort_id}.",
        # A stock, cohort and treasury can share the same latest receipt.  The
        # event ledger requires causal links to be unique, so normalize the
        # owner evidence exactly as the direct decision path does.
        causes_fn=lambda world, option: _causes(*_event_provenance(world, option)), execute_fn=execute,
        situation_fn=_situation,
    ),)


def review_permanent_employment_fallback(world, *, excluded_actors=()):
    """Choose one current job for an actor without a completed provider turn.

    This is the offline/test-mode safety net, not a second planner.  It uses
    the same transient affordances and material executor as the institutional
    turn, and only considers a public settlement already under pressure. A
    provider-consulted actor is excluded by the caller; an actor skipped by the
    shared provider budget still receives this bounded deterministic fallback.
    """
    excluded = set(excluded_actors)
    created = []
    employers = {EntityRef("polity", identity) for identity in world.society.polities}
    employers.update(office.institution_ref for office in world.authority.offices.values())
    for employer in sorted(
            {option.employer_ref for actor in employers
             for option in permanent_employment_options(world, actor)},
            key=lambda ref: (ref.kind, ref.id)):
        if employer in excluded:
            continue
        options = permanent_employment_options(world, employer)
        pressured = []
        for option in options:
            report = world.knowledge.settlement_report(employer, option.settlement_id)
            if report is None or report.observed_day != world.clock.absolute_day:
                continue
            if report.missing_food <= 0 and report.health >= 700 and report.unrest < 250:
                continue
            # When local food is short, prefer a real food-producing job over
            # another occupation at the same observed pressure.  The option
            # is still fully engine-enumerated and the owner revalidates all
            # terms; this only makes the conservative offline policy choose
            # the material recovery path when it is available.
            food_priority = int(report.missing_food > 0 and option.occupation == "farmer")
            pressure = (report.missing_food, 1000 - report.health, report.unrest,
                        food_priority)
            pressured.append((pressure, option))
        if not pressured:
            continue
        _, option = max(pressured, key=lambda item: (item[0], tuple(reversed(item[1].id))))
        decision = record_permanent_employment_decision(world, employer, option.id)
        created.append(create_permanent_employment(world, option.id, decision_event_id=decision.id))
    return tuple(created)


__all__ = ["ACTION", "PermanentEmploymentOption", "permanent_employment_options",
           "record_permanent_employment_decision", "create_permanent_employment",
           "settle_permanent_employment", "permanent_employment_adapters",
           "review_permanent_employment_fallback"]
