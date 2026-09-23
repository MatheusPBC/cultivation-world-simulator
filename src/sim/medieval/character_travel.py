"""One individual turn: a free person may walk one adjacent road, or stay.

This is not a planner and not a personal-life simulator. The engine enumerates
the legs that physically leave the settlement where the person actually stands;
the provider selects one existing ID or nothing at all. A journey is a real
``travel`` activity with its dated arrival, so a traveller is busy and composes
no local affordance until it truly arrives, and a passage that closes later
holds the traveller on the road instead of teleporting anyone.

Only one leg is ever chosen. Longer journeys are sequences of later decisions
taken with whatever the person knows after arriving, never a planned route.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.classes.state_delta import StateDelta
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .activities import Activity, validate_activities
from .events import record_event
from .travel import route_duration

TRAVEL_ACTION = "travel_character"
REVIEW_KIND = "character_travel_review"
_PREFIX = "character-travel-review:"
_DAY_MARKER = ":day:"


@dataclass(frozen=True)
class TravelOption:
    """Transient engine option; a decider only ever selects this ID."""
    id: Identity
    actor_ref: EntityRef
    character_id: Identity
    origin_id: Identity
    destination_id: Identity
    route_id: Identity
    travel_days: int

    def decision(self):
        return {"action": TRAVEL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def is_traveling(world, character_id) -> bool:
    """A person on the road is not present anywhere and may not be used."""
    return any(item.character_id == character_id and item.kind == "travel"
               for item in world.activities.values())


def _free(world, character_id):
    character = world.society.characters.get(character_id)
    if (character is None or character.death_day is not None
            or any(item.character_id == character_id for item in world.activities.values())):
        return None
    return character


def travel_options(world, character_id):
    """Legs that physically leave the settlement this person stands in.

    Only the roads touching the traveller's own region are enumerated: this is
    the knowledge of somebody standing at a crossing, not a map of the world.
    Nothing about the destination beyond its public identity is read.
    """
    character = _free(world, character_id)
    origin = world.society.settlements.get(character.location_id) if character is not None else None
    if origin is None:
        return ()
    actor = EntityRef("character", character_id)
    options = []
    for route_id, route in sorted(world.map.routes.items()):
        if (origin.region_id not in route.endpoint_region_ids or route.mode not in {"road", "river"}
                or world.map.get_route_operational_capacity(route_id) <= 0):
            continue
        other = next(region for region in route.endpoint_region_ids if region != origin.region_id)
        destination = next((item for _, item in sorted(world.society.settlements.items())
                            if item.region_id == other), None)
        if destination is None or destination.id == origin.id:
            continue
        days = route_duration(world, route_id)
        options.append(TravelOption(
            id=f"character-travel:{character_id}:{origin.id}:{route_id}:{destination.id}:{days}",
            actor_ref=actor, character_id=character_id, origin_id=origin.id,
            destination_id=destination.id, route_id=route_id, travel_days=days))
    return tuple(options)


def _decision(world, decision_event_id, character_id):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != TRAVEL_ACTION
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}
            or event.decision.get("actor_ref") != EntityRef("character", character_id).to_dict()):
        raise ValueError("travel requires a current decision of this person")
    return event


def travel_character(world, character_id, option_id, decision_event_id):
    """Begin one real leg; Map keeps the passage, Society keeps the person."""
    candidate = deepcopy(world)
    decision = _decision(candidate, decision_event_id, character_id)
    option = next((item for item in travel_options(candidate, character_id) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("travel option is stale or unknown")
    day = candidate.clock.absolute_day
    sequence = len(candidate.events) + 1
    identity = f"activity:{sequence}"
    if identity in candidate.activities or candidate.agenda.get(identity) is not None:
        raise ValueError("travel identity collision")
    activity = Activity(id=identity, character_id=character_id, kind="travel", started_day=day,
                        processed_day=day, decision_event_id=decision.id, origin_id=option.origin_id,
                        destination_id=option.destination_id, route_id=option.route_id,
                        due_day=day + option.travel_days)
    record_event(candidate, "character_travel_started",
                 "Uma pessoa deixou o lugar onde estava por uma estrada conhecida.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(StateDelta(owner_kind="activity", owner_id=activity.id, aspect="status",
                                    before="idle", after="active"),),
                 cause_ids=(decision.id,))
    candidate.activities[activity.id] = activity
    candidate.agenda.schedule(ScheduledSituation(activity.id, "activity", activity.due_day))
    validate_activities(candidate)
    candidate.society.validate(set(candidate.map.regions), candidate)
    world.__dict__.update(candidate.__dict__)
    return world.activities[activity.id]


def review_id(character_id, day):
    return f"{_PREFIX}{character_id}{_DAY_MARKER}{day}"


def _parse_review(situation):
    if situation.kind != REVIEW_KIND or not situation.id.startswith(_PREFIX):
        return None
    character_id, marker, day = situation.id[len(_PREFIX):].rpartition(_DAY_MARKER)
    if not character_id or marker != _DAY_MARKER or not day.isdecimal():
        return None
    return character_id


def _actor_turn_available(world):
    """Whether a provider slot exists to schedule an individual turn."""
    return ai_decider.provider_available() and ai_decider.within_budget(world)


def schedule_character_travel_reviews(world):
    """A free person with a road at hand earns a turn; it never chooses one."""
    if not world.config.ai_enabled or not _actor_turn_available(world):
        return ()
    scheduled = []
    due_day = world.clock.absolute_day + 1
    for character_id in sorted(world.society.characters):
        if not travel_options(world, character_id):
            continue
        situation_id = review_id(character_id, due_day)
        if world.agenda.get(situation_id) is None:
            world.agenda.schedule(ScheduledSituation(situation_id, REVIEW_KIND, due_day))
            scheduled.append(situation_id)
    return tuple(scheduled)


def _situation(world, character):
    """Self-knowledge and the ground underfoot; nothing about the destination."""
    return {"you_are": {"id": character.id, "name": character.name,
                        "standing_in": character.location_id,
                        "personality": character.personality.model_dump(mode="json"),
                        "motivations": list(character.motivations)},
            "today": world.clock.absolute_day}


async def _travel_turn(world, character_id):
    options = travel_options(world, character_id)
    character = _free(world, character_id)
    if not options or character is None:
        return False
    names = world.society.settlements
    choices = [{"id": option.id,
                "label": (f"Viajar de {names[option.origin_id].name} até {names[option.destination_id].name} "
                          f"por {option.route_id}, {option.travel_days} dias de caminho.")}
               for option in options]
    start = len(world.events)
    selected = await ai_decider.select_option(world, EntityRef("character", character_id),
                                              _situation(world, character), choices)
    interpretations = tuple(event.id for event in world.events[start:]
                            if event.causal_origin.value == "llm_interpretation")
    if selected in (None, ai_decider.NO_ACTION):
        return False
    option = next((item for item in travel_options(world, character_id) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for character:{character_id}: travel affordance became stale"
        )
    # The interpretation may only cause this delta-free decision; the material
    # departure is caused by the decision alone.
    decision = record_event(world, "character_travel_decided", "Uma pessoa escolheu entre suas estradas.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=interpretations)
    try:
        travel_character(world, character_id, option.id, decision.id)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for character:{character_id}: travel affordance became stale"
        ) from exc
    return True


def note_arrivals(world):
    """Somebody who just arrived stands somewhere new and free: it earns the
    next turn from that fact, not from a clock that asks everyone every day."""
    if not world.config.ai_enabled or not _actor_turn_available(world):
        return ()
    day = world.clock.absolute_day
    arrived = set()
    for event in reversed(world.events):
        if event.day != day:
            break
        if event.event_type != "travel_arrived":
            continue
        arrived.update(delta.owner_id for delta in event.deltas
                       if delta.owner_kind == "character" and delta.aspect == "location_id")
    scheduled = []
    for character_id in sorted(arrived):
        if not travel_options(world, character_id):
            continue
        situation_id = review_id(character_id, day + 1)
        if world.agenda.get(situation_id) is None:
            world.agenda.schedule(ScheduledSituation(situation_id, REVIEW_KIND, day + 1))
            scheduled.append(situation_id)
    return tuple(scheduled)


async def review_character_travel(world, situations):
    """Resolve only scheduled individual travel turns, at most one per person."""
    note_arrivals(world)
    reviewed = set()
    for situation in sorted(situations, key=lambda item: item.id):
        character_id = _parse_review(situation)
        if character_id is None or character_id in reviewed:
            continue
        reviewed.add(character_id)
        await _travel_turn(world, character_id)


__all__ = ["REVIEW_KIND", "TRAVEL_ACTION", "is_traveling", "note_arrivals", "review_character_travel",
           "schedule_character_travel_reviews", "travel_character", "travel_options"]
