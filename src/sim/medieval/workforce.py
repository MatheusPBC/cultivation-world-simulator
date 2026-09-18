"""Engine-owned, dated local farmer-to-artisan transitions.

Offers are merely knowledge receipts.  They reserve neither people nor money.
Only an accepting population group creates an auditable decision, and Society
then owns the temporary unavailability and the later occupational transfer.
"""

from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import workforce_demand_report_id, workforce_offer_notice_id
from src.classes.governance.models import (WorkforceDemandReport, WorkforceOfferNotice,
                                           workforce_demand_observation, workforce_offer_observation)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue
from src.classes.society.workforce import WorkforceTransition
from src.classes.state_delta import StateDelta
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event
from .migration_policy import _route_path
from .travel import route_duration


TRANSITION_DAYS = 30
MAX_GROUP_FRACTION_DENOMINATOR = 5


@dataclass(frozen=True, slots=True)
class _Demand:
    sponsor_ref: EntityRef
    work_kind: str
    work_id: str
    account_id: str
    count: int
    stipend_per_person: int
    source_event_id: str
    target_occupation: str


class WorkforceTransitionOption(SocietyValue):
    """Transient engine option.  A decider only selects this ID."""
    id: str
    notice_id: str
    group_id: str

    def decision(self):
        return {"action": "accept_workforce_offer",
                "actor_ref": EntityRef("population_group", self.group_id).to_dict(),
                "notice_id": self.notice_id, "option_id": self.id}


def _event(world, event_id):
    return next((event for event in world.events if event.id == event_id), None)


def labor_shortfall(event, owner_kind, work_id):
    """Read the typed material signal: workers still missing, or ``None``.

    The quantity is engine-owned and deterministic, emitted by production and
    by repair whenever labour is the binding constraint.  No text is parsed.
    """
    if event is None or event.fact_kind != FactKind.STATE_TRANSITION:
        return None
    for delta in event.deltas:
        if (delta.owner_kind == owner_kind and delta.owner_id == work_id
                and delta.aspect == "labor_shortfall" and delta.after.isdecimal() and int(delta.after) > 0):
            return int(delta.after)
    return None


def _current_demands(world):
    """Enumerate one conservative worker need from material work completed today."""
    day = world.clock.absolute_day
    demands = []
    for facility in sorted(world.economy.facilities.values(), key=lambda item: item.id):
        event = _event(world, facility.last_event_id)
        stock = world.economy.stocks[facility.stock_id]
        recipe = world.economy.recipes[facility.recipe_id]
        shortfall = labor_shortfall(event, "production", facility.id)
        if (recipe.occupation != "artisan" or facility.last_batches >= facility.max_batches
                or shortfall is None
                or event.day != day or event.event_type not in {"production_completed", "production_limited"}
                or not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, "supply")
                or not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, "trade")):
            continue
        account = world.economy.accounts[facility.payroll_account_id]
        if account.owner_ref != stock.owner_ref:
            continue
        # A labour limit proves at least one missing worker, but not a whole
        # replacement cohort.  One is the bounded, engine-owned V1 demand.
        demands.append(_Demand(stock.owner_ref, "facility", facility.id, account.id, 1,
                               facility.wage_per_worker, event.id, "artisan"))
    for project in sorted(world.economy.repairs.values(), key=lambda item: item.id):
        event = _event(world, project.last_event_id)
        if (project.last_work_day != day or project.stage != "blocked" or project.blocker != "labor"
                or event is None or event.day != day or event.event_type != "repair_progressed"
                or labor_shortfall(event, "repair", project.id) is None
                or not can_actor_act_for(world, project.maintainer_ref, project.maintainer_ref, "supply")
                or not can_actor_act_for(world, project.maintainer_ref, project.maintainer_ref, "trade")):
            continue
        account = world.economy.accounts.get(project.account_id)
        blueprint = world.economy.repair_blueprints.get(project.blueprint_id)
        if account is None or blueprint is None or account.owner_ref != project.maintainer_ref:
            continue
        demands.append(_Demand(project.maintainer_ref, "repair", project.id, account.id, 1,
                               blueprint.wage_per_worker, event.id, "artisan"))
    # A staffed post becomes a merchant-work demand only after its existing,
    # paid inspection capacity was actually exhausted today.  This is a typed
    # material signal from the checkpoint itself, not dispatch on a narrative
    # event name.  A local, fully available merchant makes retraining needless.
    from .customs import (CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY, CUSTOMS_STAFF_WAGE,
                          checkpoint_active)
    for checkpoint in sorted(world.economy.customs_checkpoints.values(), key=lambda item: item.id):
        event = _event(world, checkpoint.last_event_id)
        shortfall = labor_shortfall(event, "customs_checkpoint", checkpoint.id)
        site = world.map.infrastructure_sites.get(checkpoint.site_id)
        account = world.economy.accounts.get(checkpoint.account_id)
        local_merchants = (
            group for group in world.society.population.values()
            if site is not None
            and world.society.settlements[group.settlement_id].region_id in site.region_ids
            and group.occupation == "merchant"
            and world.society.available_count(group.id) >= checkpoint.staff_count
        )
        if (event is None or event.day != day or shortfall is None
                or not checkpoint_active(world, checkpoint)
                or checkpoint.inspection_day != day
                or checkpoint.inspection_slots_used < checkpoint.staff_count * CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY
                or next(local_merchants, None) is not None
                or account is None or account.owner_ref != checkpoint.operator_ref
                or not can_actor_act_for(world, checkpoint.operator_ref, checkpoint.operator_ref, "supply")
                or not can_actor_act_for(world, checkpoint.operator_ref, checkpoint.operator_ref, "trade")):
            continue
        demands.append(_Demand(checkpoint.operator_ref, "customs", checkpoint.id, account.id,
                               min(1, shortfall), CUSTOMS_STAFF_WAGE, event.id, "merchant"))
    return tuple(demands)


def _report_from_demand(world, demand):
    return WorkforceDemandReport(
        id=workforce_demand_report_id(demand.sponsor_ref, demand.work_kind, demand.work_id),
        recipient_ref=demand.sponsor_ref, publisher_ref=demand.sponsor_ref, sponsor_ref=demand.sponsor_ref,
        work_kind=demand.work_kind, work_id=demand.work_id, target_occupation=demand.target_occupation,
        account_id=demand.account_id,
        count=demand.count, stipend_per_person=demand.stipend_per_person,
        observed_day=world.clock.absolute_day, source_event_id=demand.source_event_id,
        event_id="pending",
    )


def _same_demand(previous, report):
    return (previous is not None and previous.observed_day == report.observed_day
            and previous.source_event_id == report.source_event_id
            and previous.target_occupation == report.target_occupation and previous.count == report.count
            and previous.stipend_per_person == report.stipend_per_person and previous.account_id == report.account_id)


def _committed(world, demand_id):
    """An accepted transition still cites this demand and its own notice."""
    return any(item.demand_id == demand_id for item in world.society.workforce_transitions.values())


def _retract_offers(world, demand_id, source_event_id):
    """Withdraw superseded offers as a fact; knowledge never vanishes silently."""
    retired = tuple(notice for _, notice in sorted(world.knowledge.workforce_offer_notices.items())
                    if notice.demand_id == demand_id)
    if not retired:
        return
    record_event(
        world, "workforce_offer_retracted", "A administração retirou propostas cujos termos deixaram de valer.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(_delta("workforce_offer", notice.id, "observation", notice.observation(), None)
                     for notice in retired),
        cause_ids=_causes(source_event_id))
    for notice in retired:
        del world.knowledge.workforce_offer_notices[notice.id]


def _observe_demand(world, demand):
    report = _report_from_demand(world, demand)
    previous = world.knowledge.workforce_demand_reports.get(report.id)
    if _same_demand(previous, report):
        return previous
    if previous is not None and _committed(world, previous.id):
        # An accepted transition still rests on this receipt and its notice.
        # The last usable terms stay exactly as the group accepted them instead
        # of being rewritten underneath an obligation that is already running.
        return None
    # The registry contains the latest usable receipt for this opportunity.
    # Replacing a demand retracts its old direct offers rather than leaving a
    # group with a notice whose terms no longer name the current demand.
    _retract_offers(world, report.id, demand.source_event_id)
    event = record_event(
        world, "workforce_demand_observed", "A administração registrou uma falta local de trabalho material.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("workforce_demand", report.id, "observation",
                       previous.observation() if previous else None, report.observation()),),
        cause_ids=_causes(demand.source_event_id))
    report = report.model_copy(update={"event_id": event.id})
    world.knowledge.workforce_demand_reports[report.id] = report
    return report


def _work_settlement_id(world, work_kind, work_id):
    """The one settlement a facility or repair demand belongs to.

    ``None`` for customs: a checkpoint's region can touch more than one
    settlement, so it has no single destination a recruit could travel to.
    """
    if work_kind == "facility":
        return world.economy.stocks[world.economy.facilities[work_id].stock_id].location_id
    if work_kind == "repair":
        return world.economy.stocks[world.economy.repairs[work_id].stock_id].location_id
    return None


def _eligible_groups(world, demand):
    """Only fully available farmers can receive a finite direct offer.

    A customs checkpoint's merchant demand only ever reaches a farmer already
    standing somewhere its own region touches, exactly as before. A
    facility/repair artisan demand also reaches this settlement's own farmers
    first, but when none exist here a farmer group elsewhere in a settlement
    the same sponsor administers, and that the sponsor's own current route
    knowledge actually connects to this one, is offered too -- the mechanism
    that ends the wait, not a bypass of the labour deficit it still proves.
    """
    settlement_id = _work_settlement_id(world, demand.work_kind, demand.work_id)
    if settlement_id is None:
        checkpoint = world.economy.customs_checkpoints[demand.work_id]
        site = world.map.infrastructure_sites[checkpoint.site_id]
        settlements = {settlement.id for settlement in world.society.settlements.values()
                       if settlement.region_id in site.region_ids}
        for group in sorted(world.society.population.values(), key=lambda item: item.id):
            if (group.settlement_id in settlements and group.occupation == "farmer"
                    and world.society.available_count(group.id) == group.count):
                yield group
        return
    for group in sorted(world.society.population.values(), key=lambda item: item.id):
        if (group.settlement_id == settlement_id and group.occupation == "farmer"
                and world.society.available_count(group.id) == group.count):
            yield group
    if demand.sponsor_ref.kind != "polity":
        return
    for group in sorted(world.society.population.values(), key=lambda item: item.id):
        settlement = world.society.settlements.get(group.settlement_id)
        if (group.settlement_id == settlement_id or group.occupation != "farmer"
                or world.society.available_count(group.id) != group.count
                or settlement is None or settlement.administrator_id != demand.sponsor_ref.id
                or _route_path(world, demand.sponsor_ref, group.settlement_id, settlement_id) is None):
            continue
        yield group


def _publish_offers(world, report):
    """Deliver direct notices only to current local groups; no stock is reserved."""
    account = world.economy.accounts.get(report.account_id)
    if (account is None or account.owner_ref != report.sponsor_ref
            or not can_actor_act_for(world, report.sponsor_ref, report.sponsor_ref, "supply")
            or not can_actor_act_for(world, report.sponsor_ref, report.sponsor_ref, "trade")):
        return
    remaining = report.count
    for group in _eligible_groups(world, report):
        if remaining <= 0:
            break
        # A group never converts more than one fifth at once, and the report
        # never offers more people than the material deficit it proved.
        amount = min(remaining, group.count // MAX_GROUP_FRACTION_DENOMINATOR)
        if amount <= 0:
            continue
        if account.balance < amount * report.stipend_per_person:
            continue
        notice_id = workforce_offer_notice_id(group.id, report.id)
        notice = WorkforceOfferNotice(
            id=notice_id, recipient_ref=EntityRef("population_group", group.id), publisher_ref=report.sponsor_ref,
            sponsor_ref=report.sponsor_ref, demand_id=report.id, source_group_id=group.id,
            target_occupation=report.target_occupation, count=amount,
            stipend_per_person=report.stipend_per_person, observed_day=report.observed_day, event_id="pending")
        previous = world.knowledge.workforce_offer_notices.get(notice.id)
        if (previous is not None and previous.observed_day == notice.observed_day
                and previous.demand_id == notice.demand_id
                and previous.target_occupation == notice.target_occupation and previous.count == notice.count
                and previous.stipend_per_person == notice.stipend_per_person):
            remaining -= amount
            continue
        event = record_event(
            world, "workforce_offer_received", "Um grupo local recebeu uma proposta de transição ocupacional.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("workforce_offer", notice.id, "observation",
                           previous.observation() if previous else None, notice.observation()),),
            cause_ids=_causes(report.event_id))
        world.knowledge.workforce_offer_notices[notice.id] = notice.model_copy(update={"event_id": event.id})
        remaining -= amount


def refresh_workforce_notices(world):
    """Refresh today's sponsor-only demand receipts and direct local offers."""
    for demand in _current_demands(world):
        report = _observe_demand(world, demand)
        if report is not None:
            _publish_offers(world, report)


def _current_report(world, report):
    if report.observed_day != world.clock.absolute_day:
        return None
    return next((candidate for candidate in _current_demands(world)
                 if (candidate.sponsor_ref == report.sponsor_ref and candidate.work_kind == report.work_kind
                     and candidate.work_id == report.work_id
                     and candidate.target_occupation == report.target_occupation and candidate.account_id == report.account_id
                     and candidate.count == report.count and candidate.stipend_per_person == report.stipend_per_person
                     and candidate.source_event_id == report.source_event_id)), None)


def workforce_transition_options(world, group_id):
    """Recompose options from valid current receipts; no offer is persisted as an action."""
    group = world.society.population.get(group_id)
    if (group is None or group.occupation != "farmer" or world.society.available_count(group_id) != group.count):
        return ()
    options = []
    events = {event.id: event for event in world.events}
    for notice in world.knowledge.workforce_offers_for(group_id):
        report = world.knowledge.workforce_demand_reports.get(notice.demand_id)
        try:
            world.knowledge._validate_workforce_offer(world, events, notice)
            if report is None:
                continue
            world.knowledge._validate_workforce_demand(world, events, report)
        except ValueError:
            continue
        if (notice.observed_day != world.clock.absolute_day or report.observed_day != world.clock.absolute_day
                or notice.count > group.count or _current_report(world, report) is None):
            continue
        options.append(WorkforceTransitionOption(
            id=f"workforce_transition:{group.id}:{notice.id}:{notice.event_id}",
            notice_id=notice.id, group_id=group.id))
    return tuple(sorted(options, key=lambda item: item.id))


def accept_workforce_transition(world, option_id, *, decision_event_id):
    """Validate an acceptance, pay the dated stipend, and reserve Society time."""
    decision = _event(world, decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != world.clock.absolute_day
            or not isinstance(decision.decision, dict) or decision.decision.get("action") != "accept_workforce_offer"):
        raise ValueError("workforce transition requires a current acceptance decision")
    group_ref = decision.decision.get("actor_ref")
    group_id = group_ref.get("id") if isinstance(group_ref, dict) and group_ref.get("kind") == "population_group" else None
    option = next((item for item in workforce_transition_options(world, group_id) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("workforce transition option is stale or was not selected by this group")
    notice = world.knowledge.workforce_offer_notices[option.notice_id]
    report = world.knowledge.workforce_demand_reports[notice.demand_id]
    group = world.society.population[group_id]
    sponsor_account = world.economy.accounts.get(report.account_id)
    household_id = f"household:{group_id}"
    household = world.economy.accounts.get(household_id)
    transition_id = f"workforce:{decision_event_id}"
    stipend = notice.count * notice.stipend_per_person
    if (sponsor_account is None or household is None or sponsor_account.owner_ref != report.sponsor_ref
            or household.owner_ref != EntityRef("population_group", group_id) or sponsor_account.balance < stipend
            or transition_id in world.society.workforce_transitions
            or any(item.decision_event_id == decision_event_id for item in world.society.workforce_transitions.values())):
        raise ValueError("workforce transition lacks current group or sponsor funds")
    # V1 does not retitle named characters behind the player's back.  The
    # aggregate option is executable only when its anonymous members exist.
    world.society._select_people(group_id, notice.count, ())
    require_authority(world, report.sponsor_ref, "supply")
    require_authority(world, report.sponsor_ref, "trade")
    destination_settlement_id = _work_settlement_id(world, report.work_kind, report.work_id) or group.settlement_id
    if destination_settlement_id == group.settlement_id:
        due_day = world.clock.absolute_day + TRANSITION_DAYS
    else:
        # Revalidated fresh, exactly like every other executor here: the
        # eligibility check that surfaced this group is not trusted to still
        # hold at acceptance time.
        path = _route_path(world, report.sponsor_ref, group.settlement_id, destination_settlement_id)
        if path is None:
            raise ValueError("workforce recruitment route is no longer known")
        due_day = world.clock.absolute_day + sum(route_duration(world, route_id) for route_id in path[0])
    event = record_event(
        world, "workforce_transition_started", "Um grupo aceitou uma transição local de agricultor para artesão.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("account", sponsor_account.id, "balance", sponsor_account.balance,
                       sponsor_account.balance - stipend),
                _delta("account", household.id, "balance", household.balance, household.balance + stipend),
                _delta("workforce_transition", transition_id, "stage", None, "training")),
        cause_ids=_causes(decision_event_id, notice.event_id, report.event_id,
                          sponsor_account.last_event_id, household.last_event_id, group.last_event_id))
    world.economy.accounts[sponsor_account.id] = sponsor_account.model_copy(
        update={"balance": sponsor_account.balance - stipend, "last_event_id": event.id})
    world.economy.accounts[household.id] = household.model_copy(
        update={"balance": household.balance + stipend, "last_event_id": event.id})
    transition = WorkforceTransition(
        id=transition_id, source_group_id=group.id,
        target_group_id=f"pop:{destination_settlement_id}:{group.people}:{report.target_occupation}",
        sponsor_ref=report.sponsor_ref,
        demand_id=report.id, notice_id=notice.id, work_kind=report.work_kind, work_id=report.work_id,
        target_occupation=report.target_occupation, destination_settlement_id=destination_settlement_id,
        count=notice.count, stipend_per_person=notice.stipend_per_person, started_day=world.clock.absolute_day,
        due_day=due_day, decision_event_id=decision_event_id, last_event_id=event.id)
    world.society.workforce_transitions[transition.id] = transition
    world.agenda.schedule(ScheduledSituation(transition.id, "workforce_transition", transition.due_day))
    return transition


def _completion_plan(world, transition):
    """Derive and check the whole transfer before any fact is appended.

    Mirrors every precondition of ``SocietyState.transfer_people`` so that a
    recorded completion can no longer be followed by an exception.  Returns
    ``None`` when a legitimate change of the world made the accepted transition
    impossible; that is a material outcome, not a technical failure.
    """
    source = world.society.population.get(transition.source_group_id)
    if (source is None or source.occupation != "farmer"
            or source.settlement_id not in world.society.settlements
            or transition.destination_settlement_id not in world.society.settlements):
        return None
    try:
        # No named character is moved by this V1 aggregate classification change.
        world.society._select_people(source.id, transition.count, ())
    except (KeyError, ValueError):
        return None
    target = next((group for group in world.society.population.values()
                   if (group.settlement_id, group.people, group.occupation)
                   == (transition.destination_settlement_id, source.people, transition.target_occupation)), None)
    target_id = (target.id if target
                else f"pop:{transition.destination_settlement_id}:{source.people}:{transition.target_occupation}")
    if target_id != transition.target_group_id or (target is None and target_id in world.society.population):
        return None
    checkpoint = None
    if transition.work_kind == "customs":
        from .customs import CUSTOMS_SITE_KINDS, _operator_can_run
        checkpoint = world.economy.customs_checkpoints.get(transition.work_id)
        site = world.map.infrastructure_sites.get(checkpoint.site_id) if checkpoint is not None else None
        account = world.economy.accounts.get(checkpoint.account_id) if checkpoint is not None else None
        if (checkpoint is None or site is None or site.kind not in CUSTOMS_SITE_KINDS
                or site.owner_ref != checkpoint.operator_ref or not site.enabled or site.service_suspended
                or site.integrity < 1.0 or account is None or account.owner_ref != checkpoint.operator_ref
                or not _operator_can_run(world, checkpoint.operator_ref)):
            return None
    return source, target, target_id, checkpoint


def _abandon_transition(world, transition):
    """Record the impossibility and release the people reserved by Society.

    The stipend already paid is not reversed here: no counterparty decided to
    return it, and this executor does not move money on its own.
    """
    source = world.society.population.get(transition.source_group_id)
    record_event(
        world, "workforce_transition_failed",
        "A transição aceita deixou de ser possível; o grupo reservado foi liberado.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("workforce_transition", transition.id, "stage", "training", "failed"),),
        cause_ids=_causes(transition.last_event_id, transition.decision_event_id,
                          source.last_event_id if source is not None else None))
    del world.society.workforce_transitions[transition.id]


def _complete_transition(world, transition):
    plan = _completion_plan(world, transition)
    if plan is None:
        _abandon_transition(world, transition)
        return
    source, target, target_id, checkpoint = plan
    checkpoint_deltas = ()
    if checkpoint is not None:
        checkpoint_deltas = (_delta("customs_checkpoint", checkpoint.id, "staff_group_id",
                                    checkpoint.staff_group_id, target_id),)
    event = record_event(
        world, "workforce_transition_completed", "A transição local alterou a classificação econômica do grupo.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("workforce_transition", transition.id, "stage", "training", "completed"),
                _delta("population", source.id, "count", source.count, source.count - transition.count),
                _delta("population", target_id, "count", target.count if target else 0,
                       (target.count if target else 0) + transition.count), *checkpoint_deltas),
        cause_ids=_causes(transition.last_event_id, transition.decision_event_id, source.last_event_id,
                          target.last_event_id if target else None,
                          checkpoint.last_event_id if checkpoint is not None else None))
    world.society.transfer_people(source.id, transition.destination_settlement_id, transition.target_occupation,
                                  transition.count)
    updated_source = world.society.population[source.id]
    updated_target = world.society.population[target_id]
    world.society.population[source.id] = updated_source.model_copy(update={"last_event_id": event.id})
    world.society.population[target_id] = updated_target.model_copy(update={"last_event_id": event.id})
    if checkpoint is not None:
        world.economy.customs_checkpoints[checkpoint.id] = checkpoint.model_copy(
            update={"staff_group_id": target_id, "last_event_id": event.id})
    del world.society.workforce_transitions[transition.id]


def resolve_workforce_transitions(world, situations):
    for situation in situations:
        transition = world.society.workforce_transitions.get(situation.id)
        if (situation.kind != "workforce_transition" or transition is None
                or transition.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent workforce transition")
        _complete_transition(world, transition)
