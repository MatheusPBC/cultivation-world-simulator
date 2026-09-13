from typing import Literal

from pydantic import model_validator

from src.classes.society.models import Count, Identity, SocietyValue, Skills


class Activity(SocietyValue):
    id: Identity
    character_id: Identity
    kind: Literal["training", "study", "travel"]
    started_day: Count
    processed_day: Count
    decision_event_id: Identity
    skill: str | None = None
    progress_days: Count = 0
    origin_id: str | None = None
    destination_id: str | None = None
    route_id: str | None = None
    due_day: Count | None = None

    @model_validator(mode="after")
    def check_shape(self):
        if self.processed_day < self.started_day:
            raise ValueError("activity processing precedes its start")
        if self.kind == "travel":
            if (not self.origin_id or not self.destination_id or not self.route_id or self.skill is not None
                    or self.origin_id == self.destination_id or self.due_day is None
                    or self.due_day <= self.started_day):
                raise ValueError("invalid travel activity")
        elif (self.skill not in Skills.model_fields or self.due_day is not None
              or any((self.origin_id, self.destination_id, self.route_id)) or self.progress_days >= 30):
            raise ValueError("invalid practice activity")
        return self


def validate_activities(world) -> None:
    actors = set()
    events = {event.id: event for event in world.events}
    for activity_id, activity in world.activities.items():
        if not isinstance(activity, Activity) or activity_id != activity.id:
            raise ValueError("invalid activity registry")
        if activity.character_id not in world.society.characters or activity.character_id in actors:
            raise ValueError("unknown or busy activity actor")
        if not activity.started_day <= activity.processed_day <= world.clock.absolute_day:
            raise ValueError("activity is ahead of the world clock")
        actors.add(activity.character_id)
        decision = events.get(activity.decision_event_id)
        if decision is None or decision.decision is None or decision.decision.get("character_id") != activity.character_id:
            raise ValueError("activity has no supporting decision")
        if activity.kind == "travel":
            if (activity.origin_id not in world.society.settlements or activity.destination_id not in world.society.settlements
                    or activity.route_id not in world.map.routes):
                raise ValueError("unknown travel location or route")
            scheduled = world.agenda.get(activity.id)
            if scheduled is None or scheduled.kind != "activity" or scheduled.due_day != activity.due_day:
                raise ValueError("travel activity and agenda disagree")
    for entry in world.agenda.to_dict():
        if entry["kind"] == "activity" and (entry["id"] not in world.activities or world.activities[entry["id"]].kind != "travel"):
            raise ValueError("agenda references missing activity")
