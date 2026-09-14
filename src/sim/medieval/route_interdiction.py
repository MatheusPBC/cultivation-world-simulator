"""Prepared force presence can restrict one local route without owning it.

Society records the actor and column. Map remains the capacity owner: its
runtime holds the active force cause alongside route enablement and explicit
infrastructure dependencies. No choice ever changes cargo by hand.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import RouteInterdiction
from src.classes.society.models import Identity

from .economy import _causes, _delta
from .events import record_event


INTERDICT_ACTION = "interdict_route"
LIFT_ACTION = "lift_route_interdiction"
REPORT_MAX_AGE = 30


@dataclass(frozen=True)
class RouteInterdictionOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    route_id: Identity
    kind: str
    interdiction_id: Identity | None = None

    def decision(self):
        return {"action": INTERDICT_ACTION if self.kind == "interdict" else LIFT_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _current_report(world, actor, route_id):
    report = world.knowledge.route_report(actor, route_id)
    return (report if report is not None and 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE
            else None)


def route_interdiction_options(world, actor, *, detachment_id=None):
    """Only an actor's own current route reading can expose this choice.

    Map truth is also checked while composing, so a route already made useless
    by any cause does not create a misleading affordance. The absence of an
    option discloses neither the cause nor another actor's identity.
    """
    if not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    active_by_detachment = {item.detachment_id for item in world.society.route_interdictions.values()
                            if item.stage == "active"}
    for detachment in world.society.detachments.values():
        if (detachment.owner_ref != actor or (detachment_id is not None and detachment.id != detachment_id)):
            continue
        own_interdictions = sorted((item for item in world.society.route_interdictions.values()
                                    if item.detachment_id == detachment.id and item.stage == "active"),
                                   key=lambda item: item.id)
        for interdiction in own_interdictions:
            options.append(RouteInterdictionOption(
                id=f"route-interdiction-lift:{interdiction.id}:{interdiction.last_event_id}", actor_ref=actor,
                detachment_id=detachment.id, route_id=interdiction.route_id, kind="lift",
                interdiction_id=interdiction.id))
        if (detachment.id in active_by_detachment or detachment.stage != "present"):
            continue
        position = world.society.force_positions.get(f"force-position:{detachment.id}")
        if position is None or position.stage != "prepared" or position.settlement_id != detachment.location_id:
            continue
        settlement = world.society.settlements[detachment.location_id]
        for route in world.map.routes.values():
            report = _current_report(world, actor, route.id)
            if (settlement.region_id not in route.endpoint_region_ids or report is None
                    or report.operational_capacity <= 0 or report.travel_days is None
                    or world.map.get_route_operational_capacity(route.id) <= 0
                    or route.id in world.map.force_route_interdictors):
                continue
            options.append(RouteInterdictionOption(
                id=(f"route-interdiction:{detachment.id}:{detachment.last_event_id}:{position.last_event_id}:"
                    f"{route.id}:{report.event_id}"), actor_ref=actor, detachment_id=detachment.id,
                route_id=route.id, kind="interdict"))
    return tuple(sorted(options, key=lambda item: item.id))


def _decision(world, decision_event_id, action):
    from .force import _decision as force_decision
    return force_decision(world, decision_event_id, action)


def execute_route_interdiction_option(world, actor, option_id, decision_event_id):
    """Recompose current force affordances, then let Map receive its own cause."""
    candidate = deepcopy(world)
    option = next((item for item in route_interdiction_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("route interdiction option is stale or unknown")
    action = INTERDICT_ACTION if option.kind == "interdict" else LIFT_ACTION
    decision, decided_by = _decision(candidate, decision_event_id, action)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("route interdiction has the wrong decision")
    require_authority(candidate, actor, "military")
    if option.kind == "interdict":
        _interdict(candidate, option, decision)
    else:
        _lift(candidate, candidate.society.route_interdictions[option.interdiction_id],
              cause_ids=(decision.id,), require_decision=True)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.route_interdictions.get(option.interdiction_id or f"route-interdiction:{decision.id}")


def _interdict(world, option, decision):
    detachment = world.society.detachments[option.detachment_id]
    position = world.society.force_positions.get(f"force-position:{detachment.id}")
    route = world.map.routes[option.route_id]
    settlement = world.society.settlements[detachment.location_id]
    report = _current_report(world, option.actor_ref, route.id)
    if (detachment.stage != "present" or position is None or position.stage != "prepared"
            or position.settlement_id != detachment.location_id
            or settlement.region_id not in route.endpoint_region_ids or report is None
            or report.operational_capacity <= 0 or report.travel_days is None
            or world.map.get_route_operational_capacity(route.id) <= 0
            or route.id in world.map.force_route_interdictors):
        raise ValueError("route interdiction is no longer possible")
    identity = f"route-interdiction:{decision.id}"
    interdiction = RouteInterdiction(id=identity, actor_ref=option.actor_ref, detachment_id=detachment.id,
                                     route_id=route.id, settlement_id=settlement.id,
                                     started_day=world.clock.absolute_day, decision_event_id=decision.id,
                                     last_event_id="pending")
    before = world.map.get_route_operational_capacity(route.id)
    event = record_event(
        world, "route_interdicted", "Uma coluna preparada restringiu fisicamente uma passagem local.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("route_interdiction", identity, "stage", None, "active"),
                _delta("route", route.id, "force_interdictor_id", None, identity),
                _delta("route", route.id, "operational_capacity", before, 0.0)),
        cause_ids=_causes(decision.id, detachment.last_event_id, position.last_event_id, report.event_id),
    )
    world.map.set_force_route_interdictor(route.id, identity)
    world.society.route_interdictions[identity] = interdiction.model_copy(update={"last_event_id": event.id})
    from .route_intelligence import refresh_route_reports
    refresh_route_reports(world, route_ids=(route.id,))
    return world.society.route_interdictions[identity]


def _lift(world, interdiction, *, cause_ids=(), require_decision=False):
    """Remove only this force cause; pre-existing route causes remain untouched."""
    if interdiction.stage != "active" or world.map.force_route_interdictors.get(interdiction.route_id) != interdiction.id:
        raise ValueError("route interdiction no longer holds")
    if require_decision:
        require_authority(world, interdiction.actor_ref, "military")
    before = world.map.get_route_operational_capacity(interdiction.route_id)
    world.map.clear_force_route_interdictor(interdiction.route_id, interdiction.id)
    after = world.map.get_route_operational_capacity(interdiction.route_id)
    event = record_event(
        world, "route_interdiction_lifted", "A restrição física da coluna sobre a passagem terminou.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("route_interdiction", interdiction.id, "stage", "active", "lifted"),
                _delta("route", interdiction.route_id, "force_interdictor_id", interdiction.id, None),
                _delta("route", interdiction.route_id, "operational_capacity", before, after)),
        cause_ids=_causes(interdiction.last_event_id, *cause_ids),
    )
    world.society.route_interdictions[interdiction.id] = interdiction.model_copy(
        update={"stage": "lifted", "lifted_day": world.clock.absolute_day, "last_event_id": event.id})
    from .route_intelligence import refresh_route_reports
    refresh_route_reports(world, route_ids=(interdiction.route_id,))
    return event


def revoke_route_interdictions_for(world, detachment, *, cause_ids=()):
    """Physical departure/lapse revokes its own restriction before the move fact."""
    lifted = []
    for interdiction in tuple(world.society.route_interdictions.values()):
        if interdiction.detachment_id == detachment.id and interdiction.stage == "active":
            lifted.append(_lift(world, interdiction, cause_ids=_causes(detachment.last_event_id, *cause_ids)))
    return tuple(lifted)


__all__ = ["INTERDICT_ACTION", "LIFT_ACTION", "RouteInterdictionOption",
           "execute_route_interdiction_option", "revoke_route_interdictions_for",
           "route_interdiction_options"]
