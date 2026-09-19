"""Bounded civic demands from local aggregate groups.

This is intentionally not a disorder engine.  A group may choose to stop a
small, fixed quorum of its own work for three days after seeing an actual local
shortfall.  The administration may refuse.  Food and repairs remain owned by
their existing material systems; the due resolver only recognizes their real
receipts and releases the people either way.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.knowledge import civic_demand_notice_id
from src.classes.governance.models import CivicDemandNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.civic import CivicProtest
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta, apply_civic_refusal_pressure, apply_civic_resolution_relief
from .events import record_event


OPEN_ACTION = "open_civic_protest"
DISSOLVE_ACTION = "dissolve_civic_protest"
REFUSE_ACTION = "refuse_civic_demand"
PROTEST_DAYS = 3
PROTEST_QUORUM = 5
STRIKE_MIN_UNREST = 650
STRIKE_MIN_PARTICIPANTS = 10
HEALTH_FLOOR = 700
FOOD_DEMAND_CAP = 20


@dataclass(frozen=True)
class CivicProtestOption:
    id: str
    group_id: str
    settlement_id: str
    demand_kind: str
    food_quantity: int
    site_id: str | None
    site_integrity_before: float | None
    report_event_id: str
    participants: int = PROTEST_QUORUM

    def decision(self):
        return {"action": OPEN_ACTION,
                "actor_ref": EntityRef("population_group", self.group_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CivicTerminalOption:
    id: str
    actor_ref: EntityRef
    protest_id: str
    kind: str

    def decision(self):
        return {"action": DISSOLVE_ACTION if self.kind == "dissolve" else REFUSE_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _event(world, event_id):
    return next((item for item in world.events if item.id == event_id), None)


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("civic protest requires a current actor decision")
    try:
        return event, EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("civic protest decision has an invalid actor") from exc


def _own_report(world, group_id):
    actor = EntityRef("population_group", group_id)
    group = world.society.population.get(group_id)
    report = world.knowledge.settlement_report(actor, group.settlement_id) if group is not None else None
    if (group is None or report is None or report.recipient_ref != actor or report.publisher_ref != actor
            or report.channel != "local_settlement_report" or report.settlement_id != group.settlement_id
            or report.observed_day != world.clock.absolute_day):
        return None
    return group, report


def _damaged_site_options(world, group, report):
    actor = EntityRef("population_group", group.id)
    settlement = world.society.settlements[group.settlement_id]
    for site_report in sorted(world.knowledge.site_reports.values(), key=lambda item: item.id):
        site = world.map.infrastructure_sites.get(site_report.site_id)
        if (site_report.recipient_ref != actor or site_report.publisher_ref != actor
                or site_report.observed_day != world.clock.absolute_day or site is None
                or settlement.region_id not in site.region_ids
                or site_report.integrity >= 1.0):
            continue
        yield CivicProtestOption(
            id=(f"civic-protest-open:{group.id}:{report.event_id}:site_repair:{site.id}:"
                f"{site_report.event_id}"),
            group_id=group.id, settlement_id=group.settlement_id, demand_kind="site_repair",
            food_quantity=0, site_id=site.id, site_integrity_before=site_report.integrity,
            report_event_id=report.event_id)


def civic_protest_options(world, group_id):
    """Recompose only from the group's own current public local readings."""
    current = _own_report(world, group_id)
    if current is None:
        return ()
    group, report = current
    if ((report.missing_food <= 0 and report.unrest < 300 and report.health > HEALTH_FLOOR)
            or world.society.available_count(group.id) < PROTEST_QUORUM
            or any(item.stage == "open" and item.settlement_id == group.settlement_id
                   for item in world.society.civic_protests.values())):
        return ()
    options = []
    if report.missing_food > 0:
        food = min(FOOD_DEMAND_CAP, report.missing_food)
        options.append(CivicProtestOption(
            id=f"civic-protest-open:{group.id}:{report.event_id}:food_relief:{food}",
            group_id=group.id, settlement_id=group.settlement_id, demand_kind="food_relief",
            food_quantity=food, site_id=None, site_integrity_before=None, report_event_id=report.event_id))
    options.extend(_damaged_site_options(world, group, report))
    available = world.society.available_count(group.id)
    if report.unrest >= STRIKE_MIN_UNREST and available >= STRIKE_MIN_PARTICIPANTS:
        participants = min(available, max(STRIKE_MIN_PARTICIPANTS, group.count // 10))
        options.append(CivicProtestOption(
            id=f"civic-protest-open:{group.id}:{report.event_id}:organized_strike:{participants}",
            group_id=group.id, settlement_id=group.settlement_id, demand_kind="organized_strike",
            food_quantity=0, site_id=None, site_integrity_before=None, report_event_id=report.event_id,
            participants=participants))
    return tuple(sorted(options, key=lambda item: item.id))


def civic_dissolve_options(world, group_id):
    actor = EntityRef("population_group", group_id)
    return tuple(CivicTerminalOption(f"civic-protest-dissolve:{item.id}:{item.last_event_id}", actor, item.id, "dissolve")
                 for item in sorted(world.society.civic_protests.values(), key=lambda item: item.id)
                 if item.group_id == group_id and item.stage == "open")


def civic_refusal_options(world, actor):
    """The addressed, still-current city administrator may only refuse V1."""
    result = []
    for notice in world.knowledge.civic_demands_for_actor(actor):
        protest = world.society.civic_protests.get(notice.protest_id)
        settlement = world.society.settlements.get(notice.settlement_id)
        if (protest is None or protest.stage != "open" or settlement is None
                or settlement.administrator_id != actor.id or actor.kind != "polity"
                or not can_actor_act_for(world, actor, actor, "supply")):
            continue
        result.append(CivicTerminalOption(
            f"civic-protest-refuse:{notice.id}:{protest.last_event_id}", actor, protest.id, "refuse"))
    return tuple(sorted(result, key=lambda item: item.id))


def _notice(world, protest, opening_event_id):
    settlement = world.society.settlements[protest.settlement_id]
    if settlement.administrator_id is None:
        return None
    recipient = EntityRef("polity", settlement.administrator_id)
    notice = CivicDemandNotice(
        id=civic_demand_notice_id(protest.id, recipient), recipient_ref=recipient, protest_id=protest.id,
        group_id=protest.group_id, settlement_id=protest.settlement_id, demand_kind=protest.demand_kind,
        food_quantity=protest.food_quantity, site_id=protest.site_id, due_day=protest.due_day,
        learned_day=world.clock.absolute_day, event_id="pending")
    event = record_event(
        world, "civic_demand_received", "A administração recebeu uma demanda cívica local agregada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("civic_demand_notice", notice.id, "demand", None, protest.demand_kind),),
        cause_ids=_causes(opening_event_id))
    world.knowledge.civic_demand_notices[notice.id] = notice.model_copy(update={"event_id": event.id})
    return event


def open_civic_protest(world, group_id, option_id, decision_event_id):
    """Reserve a fixed local quorum after its group deliberately selected a valid demand."""
    candidate = deepcopy(world)
    option = next((item for item in civic_protest_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic protest option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id, OPEN_ACTION)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic protest has the wrong decision")
    group, report = _own_report(candidate, group_id)
    if group is None or report is None or candidate.society.available_count(group.id) < PROTEST_QUORUM:
        raise ValueError("civic protest no longer has its local quorum")
    protest = CivicProtest(
        id=f"civic-protest:{decision.id}", group_id=group.id, settlement_id=group.settlement_id,
        demand_kind=option.demand_kind, food_quantity=option.food_quantity, site_id=option.site_id,
        site_integrity_before=option.site_integrity_before, participants=option.participants,
        started_day=candidate.clock.absolute_day, due_day=candidate.clock.absolute_day + PROTEST_DAYS,
        report_event_id=option.report_event_id, decision_event_id=decision.id, last_event_id="pending")
    event = record_event(
        candidate, "civic_protest_opened", "Um grupo local interrompeu uma pequena parte do próprio trabalho e apresentou uma demanda.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("civic_protest", protest.id, "stage", None, "open"),
                _delta("civic_protest", protest.id, "workforce_reservation", 0, protest.participants)),
        cause_ids=_causes(decision.id, report.event_id, option.site_id and next(
            (item.event_id for item in candidate.knowledge.site_reports.values()
             if item.recipient_ref == EntityRef("population_group", group.id) and item.site_id == option.site_id), None)))
    protest = protest.model_copy(update={"last_event_id": event.id})
    candidate.society.civic_protests[protest.id] = protest
    candidate.agenda.schedule(ScheduledSituation(protest.id, "civic_protest", protest.due_day))
    notice_event = _notice(candidate, protest, event.id)
    if notice_event is not None:
        protest = protest.model_copy(update={"last_event_id": notice_event.id})
        candidate.society.civic_protests[protest.id] = protest
    from .settlement_intelligence import refresh_existing_local_settlement_reports
    refresh_existing_local_settlement_reports(candidate, protest.settlement_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.civic_protests[protest.id]


def _close(world, protest, stage, *, cause_ids=(), content=None):
    if protest.stage != "open":
        raise ValueError("civic protest is no longer open")
    event = record_event(
        world, f"civic_protest_{stage}", content or "A demanda cívica local foi encerrada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("civic_protest", protest.id, "stage", "open", stage),
                _delta("civic_protest", protest.id, "workforce_reservation", protest.participants, 0)),
        cause_ids=_causes(protest.last_event_id, *cause_ids))
    world.society.civic_protests[protest.id] = protest.model_copy(update={"stage": stage, "last_event_id": event.id})
    world.agenda.cancel(protest.id)
    from .settlement_intelligence import refresh_existing_local_settlement_reports
    refresh_existing_local_settlement_reports(world, protest.settlement_id)
    return world.society.civic_protests[protest.id]


def dissolve_civic_protest(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_dissolve_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic dissolve option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id, DISSOLVE_ACTION)
    if actor != option.actor_ref or decision.decision != option.decision():
        raise ValueError("civic protest has the wrong dissolve decision")
    _close(candidate, candidate.society.civic_protests[option.protest_id], "dissolved", cause_ids=(decision.id,),
           content="O próprio grupo encerrou sua demanda cívica.")
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.civic_protests[option.protest_id]


def refuse_civic_demand(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_refusal_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic refusal option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id, REFUSE_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("civic protest has the wrong refusal decision")
    settlement_id = candidate.society.civic_protests[option.protest_id].settlement_id
    _close(candidate, candidate.society.civic_protests[option.protest_id], "refused", cause_ids=(decision.id,),
           content="A administração recusou a demanda cívica local.")
    refusal_event_id = candidate.society.civic_protests[option.protest_id].last_event_id
    apply_civic_refusal_pressure(candidate, settlement_id, refusal_event_id=refusal_event_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.civic_protests[option.protest_id]


def _food_receipt(world, protest):
    stock_id = world.economy.needs[protest.settlement_id].stock_id
    stock = world.economy.stocks[stock_id]
    if stock.goods.get("food", 0) < protest.food_quantity:
        return None
    for event in reversed(world.events):
        if event.day < protest.started_day:
            break
        if event.event_type == "cargo_delivered" and any(
                delta.owner_kind == "stock" and delta.owner_id == stock_id and delta.aspect == "food"
                and int(delta.after) > int(delta.before) for delta in event.deltas):
            return event.id
    return None


def _repair_receipt(world, protest):
    site = world.map.infrastructure_sites.get(protest.site_id)
    if site is None or site.integrity <= protest.site_integrity_before:
        return None
    for event in reversed(world.events):
        if event.day < protest.started_day:
            break
        if any(delta.owner_kind == "site" and delta.owner_id == protest.site_id and delta.aspect == "integrity"
               and float(delta.after) > float(delta.before) for delta in event.deltas):
            return event.id
    return None


def resolve_civic_protests(world, situations):
    for situation in sorted(situations, key=lambda item: item.id):
        protest = world.society.civic_protests.get(situation.id)
        if (situation.kind != "civic_protest" or protest is None or protest.stage != "open"
                or protest.due_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent civic protest")
        receipt = _food_receipt(world, protest) if protest.demand_kind == "food_relief" else _repair_receipt(world, protest)
        closed = _close(world, protest, "answered" if receipt else "lapsed", cause_ids=(receipt,) if receipt else (),
                        content=("Uma entrega material respondeu à demanda cívica local."
                                 if receipt else "A demanda cívica local expirou sem a entrega material exigida."))
        if receipt:
            apply_civic_resolution_relief(world, protest.settlement_id,
                                          resolution_event_id=closed.last_event_id)


__all__ = ["CivicProtestOption", "CivicTerminalOption", "OPEN_ACTION", "DISSOLVE_ACTION", "REFUSE_ACTION",
           "civic_protest_options", "civic_dissolve_options", "civic_refusal_options", "open_civic_protest",
           "dissolve_civic_protest", "refuse_civic_demand", "resolve_civic_protests"]
