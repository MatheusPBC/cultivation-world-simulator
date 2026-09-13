"""Dated activity resolution and monthly practice; all effects have causal facts."""

from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.systems.calendar_agenda import ScheduledSituation
from .events import record_event


def _effect(world, activity, event_type, content, aspect, before, after, *, owner_kind="activity", owner_id=None):
    return record_event(world, event_type, content, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind=owner_kind, owner_id=owner_id or activity.id,
                           aspect=aspect, before=str(before), after=str(after)),),
        cause_ids=(activity.decision_event_id,))


def resolve_dated_activities(world, situations) -> None:
    for situation in situations:
        if situation.kind != "activity" or situation.id not in world.activities:
            raise ValueError(f"no resolver for scheduled situation {situation.id}")
        activity = world.activities[situation.id]
        character = world.society.characters[activity.character_id]
        if character.death_day is not None:
            del world.activities[activity.id]
            _effect(world, activity, "activity_cancelled", "A atividade cessou após a morte do participante.", "status", "active", "cancelled")
        elif world.map.get_route_operational_capacity(activity.route_id) <= 0:
            due = world.clock.absolute_day + 1
            world.activities[activity.id] = activity.model_copy(update={"due_day": due, "processed_day": world.clock.absolute_day})
            world.agenda.schedule(ScheduledSituation(activity.id, "activity", due))
            _effect(world, activity, "travel_delayed", "A passagem está indisponível; a viagem aguarda.", "due_day", activity.due_day, due)
        else:
            world.society.characters[character.id] = character.model_copy(update={"location_id": activity.destination_id})
            del world.activities[activity.id]
            _effect(world, activity, "travel_arrived", f"{character.name} chegou ao destino.",
                    "location_id", character.location_id, activity.destination_id, owner_kind="character", owner_id=character.id)


def advance_monthly_practice(world) -> None:
    for activity in tuple(world.activities.values()):
        if activity.kind == "travel":
            continue
        character = world.society.characters[activity.character_id]
        if character.death_day is not None:
            del world.activities[activity.id]
            _effect(world, activity, "activity_cancelled", "A atividade cessou após a morte do participante.", "status", "active", "cancelled")
            continue
        elapsed = world.clock.absolute_day - activity.processed_day
        increase, remaining = divmod(elapsed + activity.progress_days, 30)
        before = getattr(character.skills, activity.skill)
        after = min(100, before + increase)
        world.activities[activity.id] = activity.model_copy(update={
            "processed_day": world.clock.absolute_day, "progress_days": remaining,
        })
        if after != before:
            skills = character.skills.model_copy(update={activity.skill: after})
            world.society.characters[character.id] = character.model_copy(update={"skills": skills})
            _effect(world, activity, "skill_improved", f"{character.name} aperfeiçoou uma habilidade.",
                    f"skills.{activity.skill}", before, after, owner_kind="character", owner_id=character.id)
        if after == 100:
            del world.activities[activity.id]
            _effect(world, activity, "practice_completed", "A prática alcançou seu limite atual.", "status", "active", "completed")
