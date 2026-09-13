"""Dated route observations and their monthly bulletins.

The Map stays the only owner of a route: this module copies nothing into a
second registry. An administration observes the passages that touch its own
settlements, and may retell that observation through the physical network it
can actually reach. Nobody learns of a closure without being told.
"""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.knowledge import route_report_id, site_report_id
from src.classes.governance.models import RouteReport, SiteReport, route_observation, site_observation
from src.classes.mechanical_language import EntityRef
from .economy import _causes, _delta
from .events import record_event
from .logistics import _route_causes
from .routing import supply_path
from .travel import route_duration


def _administrations(world, route):
    """Only an endpoint administration with a current supply mandate observes."""
    actors = set()
    for settlement in world.society.settlements.values():
        if settlement.region_id not in route.endpoint_region_ids or settlement.administrator_id is None:
            continue
        actor = EntityRef("polity", settlement.administrator_id)
        if can_actor_act_for(world, actor, actor, "supply"):
            actors.add(actor)
    return sorted(actors, key=lambda r: (r.kind, r.id))


def _runtime(world, route_id):
    """Physical reading taken today; the report keeps it as a dated fact."""
    route = world.map.routes[route_id]
    capacity = float(world.map.get_route_operational_capacity(route_id))
    passable = capacity > 0 and route.mode in {"road", "river"} and route.quality > 0
    return capacity, route_duration(world, route_id) if passable else None


def _describe(world, route_id, travel_days):
    name = world.map.routes[route_id].id
    return (f"Passagem {name}: transitável em {travel_days} dias." if travel_days is not None
            else f"Passagem {name}: interrompida para carga.")


def _observe(world, actor, route_id, day, causes):
    key = route_report_id(actor, route_id)
    previous = world.knowledge.route_reports.get(key)
    capacity, travel_days = _runtime(world, route_id)
    if (previous is not None and previous.observed_day == day and previous.recipient_ref == previous.publisher_ref
            and previous.operational_capacity == capacity and previous.travel_days == travel_days):
        return previous
    observation = route_observation(route_id, actor, day, capacity, travel_days)
    event = record_event(world, "route_observed", _describe(world, route_id, travel_days),
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("route_report", key, "observation",
                                        previous.observation() if previous else None, observation),),
                         cause_ids=_causes(*causes))
    report = RouteReport(id=key, recipient_ref=actor, publisher_ref=actor, route_id=route_id, observed_day=day,
                         operational_capacity=capacity, travel_days=travel_days,
                         channel="administrative_route_report", event_id=event.id)
    world.knowledge.route_reports[key] = report
    return report


def _reachable(world, report, recipient, channels):
    """Aggregated monthly channel, but it still departs from the observed place.

    Only the administered endpoints of the observed route can retell it, so an
    institution holding two disconnected territories cannot teleport a bulletin
    from one to the other. A recipient in the observed settlement is reachable
    even when every passage out of it is closed.
    """
    publisher, route = report.publisher_ref, world.map.routes[report.route_id]
    key = (report.route_id, publisher, recipient)
    if key not in channels:
        origins = sorted(s.id for s in world.society.settlements.values()
                         if s.administrator_id == publisher.id and s.region_id in route.endpoint_region_ids)
        if recipient.kind == "population_group":
            group = world.society.population.get(recipient.id)
            targets = [group.settlement_id] if group is not None and world.society.available_count(group.id) > 0 else []
        else:
            targets = sorted({o.settlement_id for o in world.strategy.objectives.values() if o.actor_ref == recipient})
        channels[key] = any(supply_path(world, origin, target) is not None
                            for origin in origins for target in targets)
    return channels[key]


def _publish(world, report, recipients, day, channels):
    publisher = report.publisher_ref
    if not can_actor_act_for(world, publisher, publisher, "trade"):
        return

    def same_reading(previous):
        return (previous is not None and previous.observed_day == report.observed_day
                and previous.operational_capacity == report.operational_capacity
                and previous.travel_days == report.travel_days)

    targets = [r for r in recipients if r != publisher
               and (world.knowledge.route_report(r, report.route_id) is None
                    or not same_reading(world.knowledge.route_report(r, report.route_id)))
               and _reachable(world, report, r, channels)]
    if not targets:
        return
    observation = report.observation()
    decision = record_event(world, "route_report_published", _describe(world, report.route_id, report.travel_days),
                            fact_kind=FactKind.DECISION,
                            decision={"action": "publish_route_report", "actor_ref": publisher.to_dict(),
                                      "route_id": report.route_id, "observation": observation,
                                      "recipients": [r.to_dict() for r in targets]},
                            cause_ids=(report.event_id,))
    # Deciding to publish is not delivering: the channel emits its own receipt.
    keys = {recipient: route_report_id(recipient, report.route_id) for recipient in targets}
    previous = {recipient: world.knowledge.route_reports.get(key) for recipient, key in keys.items()}
    delivery = record_event(world, "route_report_received", _describe(world, report.route_id, report.travel_days),
                            fact_kind=FactKind.STATE_TRANSITION,
                            deltas=tuple(_delta("route_report", keys[recipient], "observation",
                                                previous[recipient].observation() if previous[recipient] else None,
                                                observation) for recipient in targets),
                            cause_ids=_causes(decision.id, report.event_id))
    for recipient in targets:
        world.knowledge.route_reports[keys[recipient]] = report.model_copy(update={
            "id": keys[recipient], "recipient_ref": recipient, "channel": "route_bulletin", "event_id": delivery.id})


def _present(world, actor, site):
    """Verifiable local presence: own stock at the place, or administering it."""
    for settlement in world.society.settlements.values():
        if settlement.region_id not in site.region_ids:
            continue
        if actor.kind == "polity" and settlement.administrator_id == actor.id:
            return True
        if any(s.owner_ref == actor and s.location_id == settlement.id for s in world.economy.stocks.values()):
            return True
    return False


def refresh_site_reports(world, *, site_ids=None):
    """Authorized owner/maintainer observers see a local site, never remotely."""
    day = world.clock.absolute_day
    for site_id in sorted(world.map.infrastructure_sites if site_ids is None else site_ids):
        site = world.map.infrastructure_sites[site_id]
        actors = {actor for actor in (site.owner_ref, site.maintainer_ref) if actor is not None}
        for actor in sorted(actors, key=lambda ref: (ref.kind, ref.id)):
            if not can_actor_act_for(world, actor, actor, "supply") or not _present(world, actor, site):
                continue
            key = site_report_id(actor, site_id)
            previous = world.knowledge.site_reports.get(key)
            if (previous is not None and previous.observed_day == day and previous.integrity == site.integrity
                    and previous.enabled == site.enabled and previous.service_suspended == site.service_suspended):
                continue
            observation = site_observation(site_id, actor, day, site.integrity, site.enabled, site.service_suspended)
            suffix = ", serviço suspenso." if site.service_suspended else ("." if site.enabled else ", instalação interditada.")
            event = record_event(world, "site_observed",
                                 f"{site.name}: integridade de {round(site.integrity * 100)}%" + suffix,
                                 fact_kind=FactKind.STATE_TRANSITION,
                                 deltas=(_delta("site_report", key, "observation",
                                                previous.observation() if previous else None, observation),),
                                 cause_ids=_causes(site.last_event_id))
            world.knowledge.site_reports[key] = SiteReport(
                id=key, recipient_ref=actor, publisher_ref=actor, site_id=site_id, observed_day=day,
                integrity=site.integrity, enabled=site.enabled, service_suspended=site.service_suspended,
                event_id=event.id)


def refresh_route_reports(world, *, route_ids=None):
    """Monthly boundary of the route channel; no quota of closures or crises."""
    day = world.clock.absolute_day
    recipients = {o.actor_ref for o in world.strategy.objectives.values()}
    recipients |= {EntityRef("population_group", group.id) for group in world.society.population.values()
                   if world.society.available_count(group.id) > 0}
    recipients = sorted(recipients, key=lambda r: (r.kind, r.id))
    route_ids = sorted(world.map.routes if route_ids is None else route_ids)
    causes = _route_causes(world, route_ids)
    channels = {}
    for route_id in route_ids:
        for actor in _administrations(world, world.map.routes[route_id]):
            report = _observe(world, actor, route_id, day, causes[route_id])
            _publish(world, report, recipients, day, channels)
