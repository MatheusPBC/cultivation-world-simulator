"""Persisted population journeys; residence remains in Society until arrival."""

from typing import Annotated, Literal

from pydantic import Field

from src.classes.society.models import Count, Identity, SocietyValue

PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class MigrationJourney(SocietyValue):
    id: Identity
    source_group_id: Identity
    destination_id: Identity
    initial_destination_id: Identity
    count: PositiveCount
    character_ids: tuple[Identity, ...]
    route_ids: tuple[Identity, ...]
    initial_route_ids: tuple[Identity, ...]
    route_index: Count = 0
    stage: Literal["waiting", "traveling", "stranded"] = "waiting"
    returning: bool = False
    due_day: Count
    decision_event_id: Identity
    provision_id: Identity
    last_event_id: Identity
