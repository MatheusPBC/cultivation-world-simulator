"""
Semantic evidence of a domain-owned state change, attached to the `Event`
that describes it.

`before`/`after` are strings for display and diffing only. No code may parse
them back into domain values, and nothing may write them into a domain
object — the state itself stays owned by whichever subsystem produced it
(`Avatar`, `CityRegion`, `Sect`, ...). `StateDelta` is evidence, never a patch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class StateDelta:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    owner_kind: str = ""     # "avatar" | "region" | "sect" | "poi" | "dynasty" | "world"
    owner_id: str = ""       # the domain owner's own id
    aspect: str = ""         # owner-declared semantic label, e.g. "population"
    before: Optional[str] = None
    after: Optional[str] = None
    magnitude: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "owner_kind": self.owner_kind,
            "owner_id": self.owner_id,
            "aspect": self.aspect,
            "before": self.before,
            "after": self.after,
            "magnitude": self.magnitude,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StateDelta":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            event_id=data.get("event_id", ""),
            owner_kind=data.get("owner_kind", ""),
            owner_id=data.get("owner_id", ""),
            aspect=data.get("aspect", ""),
            before=data.get("before"),
            after=data.get("after"),
            magnitude=data.get("magnitude"),
        )
