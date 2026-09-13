"""Internal executors: checked intent -> decision fact -> owner state change."""

from src.classes.event import FactKind
from src.classes.society.models import Skills
from src.classes.state_delta import StateDelta
from src.systems.calendar_agenda import ScheduledSituation
from .activities import Activity
from .events import record_event
from .travel import route_duration


def _available_actor(world, character_id):
    character = world.society.characters.get(character_id)
    if character is None or character.death_day is not None:
        raise ValueError("character is not alive")
    if any(a.character_id == character_id for a in world.activities.values()):
        raise ValueError("character is busy")
    return character


def _begin(world, activity):
    record_event(world, "activity_decided", "Uma nova atividade foi escolhida.", fact_kind=FactKind.DECISION,
                 decision={"character_id": activity.character_id, "action": activity.kind,
                           "skill": activity.skill, "destination_id": activity.destination_id, "route_id": activity.route_id})
    world.activities[activity.id] = activity
    if activity.due_day is not None:
        world.agenda.schedule(ScheduledSituation(activity.id, "activity", activity.due_day))
    record_event(world, "activity_started", "A atividade foi iniciada.", fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(StateDelta(owner_kind="activity", owner_id=activity.id, aspect="status", before="idle", after="active"),),
                 cause_ids=(activity.decision_event_id,))
    return activity


def start_practice(world, character_id: str, skill: str, *, kind: str = "training") -> Activity:
    character = _available_actor(world, character_id)
    if skill not in Skills.model_fields or kind not in {"training", "study"}:
        raise ValueError("unknown skill or practice kind")
    if getattr(character.skills, skill) >= 100:
        raise ValueError("skill is already at maximum")
    sequence = len(world.events) + 1
    activity = Activity(id=f"activity:{sequence}", character_id=character_id, kind=kind,
        skill=skill, started_day=world.clock.absolute_day, processed_day=world.clock.absolute_day,
        decision_event_id=f"event:{sequence}")
    return _begin(world, activity)


def start_travel(world, character_id: str, route_id: str, destination_id: str) -> Activity:
    character = _available_actor(world, character_id)
    origin = world.society.settlements[character.location_id]
    destination = world.society.settlements.get(destination_id)
    route = world.map.routes.get(route_id)
    if (destination is None or route is None or not route.connects(origin.region_id, destination.region_id)
            or world.map.get_route_operational_capacity(route_id) <= 0):
        raise ValueError("destination is not reachable by this route")
    if route.mode not in {"road", "river"}:
        raise ValueError("unsupported travel mode")
    duration = route_duration(world, route_id)
    sequence = len(world.events) + 1
    activity = Activity(id=f"activity:{sequence}", character_id=character_id, kind="travel",
        started_day=world.clock.absolute_day, processed_day=world.clock.absolute_day,
        decision_event_id=f"event:{sequence}", origin_id=origin.id, destination_id=destination_id,
        route_id=route_id, due_day=world.clock.absolute_day + duration)
    return _begin(world, activity)
