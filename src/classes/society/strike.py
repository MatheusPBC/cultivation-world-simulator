"""Persisted, bounded general strikes owned by Society."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import Count, Identity, SocietyValue

PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class CivicStrike(SocietyValue):
    id: Identity
    movement_id: Identity
    settlement_id: Identity
    participants_by_group: dict[Identity, PositiveCount]
    started_day: Count
    due_day: Count
    stage: Literal["active", "completed", "lapsed"] = "active"
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"civic-strike:{self.decision_event_id}"
                or not self.participants_by_group
                or self.due_day <= self.started_day):
            raise ValueError("civic strike identity or duration is inconsistent")
        return self
