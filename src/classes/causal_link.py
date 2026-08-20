"""
Typed causal edge between two `Event`s.

Direction is always effect -> cause: `event_id` is the effect, `cause_event_id`
is the cause. Multifactor causality is expressed as several links on one
effect event, which is why `weight` lives on the edge rather than on the
event.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional
import time
import uuid

# A recorder may only attach this many causal links to a single effect event.
# See docs/specs/causal-world-kernel.md section 10 (performance risk #4).
MAX_CAUSAL_LINKS_PER_EVENT = 8


class CausalRelation(StrEnum):
    TRIGGERED_BY = "triggered_by"
    ENABLED_BY = "enabled_by"
    MOTIVATED_BY = "motivated_by"
    RESPONSE_TO = "response_to"
    RESOLVES = "resolves"
    PREVENTED_BY = "prevented_by"
    CONTRIBUTED_TO = "contributed_to"


@dataclass
class CausalLink:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""            # the effect; set by EventStorage.add_event
    cause_event_id: str = ""      # the cause; may point at a pruned event
    relation: CausalRelation = CausalRelation.TRIGGERED_BY
    weight: float = 1.0           # multifactor contribution, 0..1
    note_key: Optional[str] = None   # i18n key, never a rendered sentence
    note_params: Optional[dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "cause_event_id": self.cause_event_id,
            "relation": str(self.relation),
            "weight": self.weight,
            "note_key": self.note_key,
            "note_params": self.note_params,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CausalLink":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            event_id=data.get("event_id", ""),
            cause_event_id=data.get("cause_event_id", ""),
            relation=CausalRelation(data.get("relation", CausalRelation.TRIGGERED_BY.value)),
            weight=data.get("weight", 1.0),
            note_key=data.get("note_key"),
            note_params=data.get("note_params"),
            created_at=data.get("created_at", time.time()),
        )
