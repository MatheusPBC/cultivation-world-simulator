"""Formal civic amnesties granted after a material negotiation."""

from pydantic import model_validator

from src.classes.mechanical_language import EntityRef
from .models import Count, Identity, SocietyValue


class CivicAmnesty(SocietyValue):
    id: Identity
    movement_id: Identity
    settlement_id: Identity
    administrator_ref: EntityRef
    granted_day: Count
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_shape(self):
        if (self.id != f"civic-amnesty:{self.decision_event_id}"
                or self.administrator_ref.kind != "polity"):
            raise ValueError("civic amnesty identity or administrator is inconsistent")
        return self
