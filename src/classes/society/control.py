"""Durable territorial control, distinct from occupation and administration."""

from typing import Literal

from pydantic import model_validator

from .models import Count, Identity, SocietyValue


class TerritorialControl(SocietyValue):
    """A current political/military control mandate over one settlement.

    ``occupier_id`` records who is physically present and ``administrator_id``
    records who still governs.  This record is the durable middle layer: it is
    created by an explicit decision after material occupation and ends when
    the supporting garrison/control basis is materially lost.
    """

    id: Identity
    settlement_id: Identity
    controller_kind: Literal["polity", "organization"]
    controller_id: Identity
    basis: Literal["occupation", "concession"]
    stage: Literal["active", "lapsed", "withdrawn"] = "active"
    started_day: Count
    ended_day: Count | None = None
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if self.id != f"territorial-control:{self.settlement_id}":
            raise ValueError("territorial control identity must name its settlement")
        if (self.stage == "active") != (self.ended_day is None):
            raise ValueError("active territorial control cannot have an end day")
        if self.ended_day is not None and self.ended_day < self.started_day:
            raise ValueError("territorial control cannot end before it starts")
        return self
