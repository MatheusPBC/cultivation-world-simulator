"""Persistent, causal conditions owned by a map region.

Conditions are deliberately data only.  Systems may interpret their ``kind``
but the region remains the sole owner of their lifetime and origin.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionCondition:
    kind: str
    intensity: float = 1.0
    started_month: int = 0
    cause_event_id: str | None = None
    expires_month: int | None = None

    def __post_init__(self) -> None:
        if not str(self.kind).strip():
            raise ValueError("RegionCondition.kind must not be empty")
        object.__setattr__(self, "kind", str(self.kind).strip())
        object.__setattr__(self, "intensity", max(0.0, min(1.0, float(self.intensity))))
        if self.expires_month is not None and self.expires_month <= self.started_month:
            raise ValueError("expires_month must be after started_month")

    def is_active(self, current_month: int) -> bool:
        return self.expires_month is None or int(current_month) < self.expires_month

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "intensity": self.intensity,
            "started_month": self.started_month,
            "cause_event_id": self.cause_event_id,
            "expires_month": self.expires_month,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionCondition":
        return cls(
            kind=data["kind"],
            intensity=data.get("intensity", 1.0),
            started_month=data.get("started_month", 0),
            cause_event_id=data.get("cause_event_id"),
            expires_month=data.get("expires_month"),
        )
