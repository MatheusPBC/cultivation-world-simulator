"""Persistent, bounded civic movements owned by Society.

This is the next rung after a local protest or tumult.  A movement starts with
one consenting group; other groups join through their own dated decisions.
It names a living leader but grants no authority, territory or outcome.
"""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import Count, Identity, SocietyValue

PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class CivicMovement(SocietyValue):
    id: Identity
    initiator_group_id: Identity
    settlement_id: Identity
    member_group_ids: tuple[Identity, ...]
    participants_by_group: dict[Identity, PositiveCount]
    leader_character_id: Identity
    started_day: Count
    stage: Literal["active", "rebellion", "revolution", "negotiating", "dissolved", "suppressed"] = "active"
    report_event_ids: tuple[Identity, ...]
    catalyst_event_id: Identity
    decision_event_id: Identity
    last_event_id: Identity
    # A negotiation may carry a material offer from the current administrator.
    # The stock remains Economy-owned and is consumed only on acceptance.
    negotiation_stock_id: Identity | None = None
    negotiation_food: int = Field(strict=True, ge=0, default=0)
    negotiation_offer_event_id: Identity | None = None

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"civic-movement:{self.decision_event_id}"
                or not self.member_group_ids
                or len(set(self.member_group_ids)) != len(self.member_group_ids)
                or set(self.participants_by_group) != set(self.member_group_ids)
                or self.initiator_group_id not in self.member_group_ids
                or not self.report_event_ids
                or len(set(self.report_event_ids)) != len(self.report_event_ids)):
            raise ValueError("civic movement identity or membership is inconsistent")
        if (self.negotiation_food > 0) != (self.negotiation_stock_id is not None
                                           and self.negotiation_offer_event_id is not None):
            raise ValueError("material civic negotiation requires its stock and offer receipt")
        return self
