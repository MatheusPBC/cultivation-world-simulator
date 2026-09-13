"""Economic provisions carried by an in-flight population journey."""

from pydantic import Field

from src.classes.society.models import Count, Identity, SocietyValue


class MigrationProvision(SocietyValue):
    id: Identity
    journey_id: Identity
    account_id: Identity
    food: Count
    missing_food: Count = 0
    health: int = Field(strict=True, ge=0, le=1000, default=1000)
    consumed_day: Count | None = None
    consumed_event_id: Identity | None = None
    last_event_id: Identity
