"""Dated, aggregate settlement observations and physically delivered bulletins."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.knowledge import settlement_report_id
from src.classes.governance.models import SettlementReport, settlement_observation
from src.classes.mechanical_language import EntityRef
from .economy import _causes, _delta
from .events import record_event
from .routing import supply_path


def _sources(world, settlement_id):
    need = world.economy.needs[settlement_id]
    resident_events = [group.last_event_id for group in world.society.population.values()
                       if group.settlement_id == settlement_id]
    return _causes(need.last_event_id, *resident_events)


def _observe(world, actor, settlement_id, *, presence_causes=()):
    day = world.clock.absolute_day
    key = settlement_report_id(actor, settlement_id)
    previous = world.knowledge.settlement_reports.get(key)
    if (previous is not None and previous.observed_day == day
            and previous.recipient_ref == actor and previous.publisher_ref == actor):
        return previous
    settlement = world.society.settlements[settlement_id]
    need = world.economy.needs[settlement_id]
    report = SettlementReport(id=key, recipient_ref=actor, publisher_ref=actor, settlement_id=settlement_id,
                              observed_day=day, population=world.society.population_at(settlement_id),
                              present_population=world.society.present_population_at(settlement_id),
                              housing_capacity=settlement.housing_capacity, health=need.health,
                              missing_food=need.missing_food, unrest=need.unrest,
                              channel="local_settlement_report", event_id="pending")
    event = record_event(world, "settlement_observed",
                         f"{settlement.name}: {report.present_population}/{report.population} presentes, saúde {report.health}/1000.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("settlement_report", key, "observation",
                                        previous.observation() if previous else None, report.observation()),),
                         cause_ids=_causes(*_sources(world, settlement_id), *presence_causes))
    report = report.model_copy(update={"event_id": event.id})
    world.knowledge.settlement_reports[key] = report
    return report


def observe_present_household(world, group_id, settlement_id, journey_event_id):
    """A household stranded at an endpoint may observe where it physically is."""
    journey = next((item for item in world.society.migrations.values()
                    if item.source_group_id == group_id and item.destination_id == settlement_id
                    and item.stage == "stranded" and item.last_event_id == journey_event_id), None)
    if journey is None:
        raise ValueError("settlement observation requires the household's stranded journey")
    return _observe(world, EntityRef("population_group", group_id), settlement_id,
                    presence_causes=(journey_event_id,))


def _recipients(world):
    return [EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
            if world.society.available_count(group_id) > 0]


def _reachable(world, settlement_id, recipient):
    group = world.society.population.get(recipient.id)
    return group is not None and world.society.available_count(group.id) > 0 and (
        supply_path(world, settlement_id, group.settlement_id) is not None)


def _publish(world, report):
    publisher = report.publisher_ref
    if not can_actor_act_for(world, publisher, publisher, "trade"):
        return
    targets = [recipient for recipient in _recipients(world) if recipient != publisher
               and (world.knowledge.settlement_report(recipient, report.settlement_id) is None
                    or world.knowledge.settlement_report(recipient, report.settlement_id).observed_day != report.observed_day)
               and _reachable(world, report.settlement_id, recipient)]
    if not targets:
        return
    observation = report.observation()
    decision = record_event(world, "settlement_report_published",
                            f"Boletim público de {world.society.settlements[report.settlement_id].name} publicado.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "publish_settlement_report", "actor_ref": publisher.to_dict(),
                                      "settlement_id": report.settlement_id, "observation": observation,
                                      "recipients": [recipient.to_dict() for recipient in targets]},
                            cause_ids=(report.event_id,))
    keys = {recipient: settlement_report_id(recipient, report.settlement_id) for recipient in targets}
    previous = {recipient: world.knowledge.settlement_reports.get(key) for recipient, key in keys.items()}
    delivery = record_event(world, "settlement_report_received",
                            f"Boletim de {world.society.settlements[report.settlement_id].name} entregue.",
                            fact_kind=FactKind.STATE_TRANSITION,
                            deltas=tuple(_delta("settlement_report", keys[recipient], "observation",
                                                previous[recipient].observation() if previous[recipient] else None,
                                                observation) for recipient in targets),
                            cause_ids=_causes(decision.id, report.event_id))
    for recipient in targets:
        world.knowledge.settlement_reports[keys[recipient]] = report.model_copy(update={
            "id": keys[recipient], "recipient_ref": recipient, "channel": "settlement_bulletin", "event_id": delivery.id})


def refresh_settlement_reports(world):
    """Publish no mandatory gossip: only supplied administrations and local cohorts observe."""
    for settlement_id in sorted(world.society.settlements):
        settlement = world.society.settlements[settlement_id]
        actors = []
        if settlement.administrator_id is not None:
            admin = EntityRef("polity", settlement.administrator_id)
            if can_actor_act_for(world, admin, admin, "supply"):
                actors.append(admin)
        actors.extend(EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
                      if world.society.population[group_id].settlement_id == settlement_id
                      and world.society.available_count(group_id) > 0)
        for actor in actors:
            report = _observe(world, actor, settlement_id)
            if actor.kind == "polity":
                _publish(world, report)
