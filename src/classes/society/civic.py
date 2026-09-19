"""Persistent, aggregate civic demands; people remain Society-owned."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from .models import Count, Identity, SocietyValue


class CivicProtest(SocietyValue):
    """A bounded local work stoppage, never a rebellion or authority claim."""

    id: Identity
    group_id: Identity
    settlement_id: Identity
    demand_kind: Literal["food_relief", "site_repair", "organized_strike"]
    food_quantity: Count = 0
    site_id: Identity | None = None
    site_integrity_before: float | None = Field(default=None, ge=0, le=1)
    participants: Annotated[int, Field(strict=True, gt=0)]
    started_day: Count
    due_day: Count
    stage: Literal["open", "answered", "refused", "lapsed", "dissolved"] = "open"
    report_event_id: Identity
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"civic-protest:{self.decision_event_id}" or self.due_day != self.started_day + 3
                or (self.demand_kind == "food_relief") != (self.food_quantity > 0 and self.site_id is None
                                                            and self.site_integrity_before is None)
                or (self.demand_kind == "site_repair") != (self.food_quantity == 0 and self.site_id is not None
                                                            and self.site_integrity_before is not None)
                or (self.demand_kind == "organized_strike") != (self.food_quantity == 0 and self.site_id is None
                                                                  and self.site_integrity_before is None)):
            raise ValueError("civic protest identity, timing or demand is inconsistent")
        return self
