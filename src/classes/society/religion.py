"""Chosen affiliation belongs to Society, invitation knowledge does not."""

from pydantic import model_validator
from src.classes.mechanical_language import EntityRef
from .models import SocietyValue, Identity, Count


class ReligiousAdherence(SocietyValue):
    id: Identity
    actor_ref: EntityRef
    organization_id: Identity
    joined_day: Count
    invitation_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_actor(self):
        if self.actor_ref.kind not in {"character", "population_group"}:
            raise ValueError("religious adherence requires a resident actor")
        if self.id != f"religious-adherence:{self.actor_ref.kind}:{self.actor_ref.id}":
            raise ValueError("invalid religious adherence identity")
        return self
