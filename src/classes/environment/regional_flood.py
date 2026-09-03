"""Canonical lifecycle state for material regional flood occurrences."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Any


def _non_empty(value: Any, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _month(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return normalized


def _source_ids(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    normalized = tuple(
        dict.fromkeys(_non_empty(value, field_name) for value in values)
    )
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _streaks(values: Any, field_name: str) -> dict[str, int]:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name} must be an object")
    normalized: dict[str, int] = {}
    for region_id, count in values.items():
        key = _non_empty(region_id, field_name)
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError(f"{field_name} values must be positive integers")
        normalized[key] = count
    return normalized


def _source_map(values: Any, field_name: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name} must be an object")
    return {
        _non_empty(region_id, field_name): _source_ids(source_ids, field_name)
        for region_id, source_ids in values.items()
    }


@dataclass(frozen=True, slots=True)
class RegionalFloodOccurrence:
    """One active physical flood, grounded by hydrological evidence."""

    region_id: str
    started_month: int
    activation_risk: float
    source_event_ids: tuple[str, ...]
    last_event_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", _non_empty(self.region_id, "region_id"))
        object.__setattr__(self, "started_month", _month(self.started_month, "started_month"))
        object.__setattr__(self, "activation_risk", _ratio(self.activation_risk, "activation_risk"))
        object.__setattr__(
            self,
            "source_event_ids",
            _source_ids(self.source_event_ids, "source_event_ids"),
        )
        object.__setattr__(self, "last_event_id", _non_empty(self.last_event_id, "last_event_id"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "started_month": self.started_month,
            "activation_risk": self.activation_risk,
            "source_event_ids": list(self.source_event_ids),
            "last_event_id": self.last_event_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalFloodOccurrence":
        if not isinstance(data, dict) or set(data) != {
            "region_id",
            "started_month",
            "activation_risk",
            "source_event_ids",
            "last_event_id",
        }:
            raise ValueError("Regional flood occurrence fields do not match the current schema")
        return cls(**data)


@dataclass(slots=True)
class RegionalFloodState:
    """World-owned active floods and their persistence observations."""

    active_by_region: dict[str, RegionalFloodOccurrence] = field(default_factory=dict)
    activation_streaks: dict[str, int] = field(default_factory=dict)
    resolution_streaks: dict[str, int] = field(default_factory=dict)
    activation_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    resolution_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    last_evaluated_month: int | None = None

    def __post_init__(self) -> None:
        active: dict[str, RegionalFloodOccurrence] = {}
        for region_id, occurrence in self.active_by_region.items():
            if not isinstance(occurrence, RegionalFloodOccurrence):
                raise TypeError("active_by_region must contain RegionalFloodOccurrence values")
            key = _non_empty(region_id, "active_by_region")
            if key != occurrence.region_id:
                raise ValueError("active flood key must match occurrence region_id")
            active[key] = occurrence
        self.active_by_region = active
        self.activation_streaks = _streaks(self.activation_streaks, "activation_streaks")
        self.resolution_streaks = _streaks(self.resolution_streaks, "resolution_streaks")
        self.activation_sources = _source_map(self.activation_sources, "activation_sources")
        self.resolution_sources = _source_map(self.resolution_sources, "resolution_sources")
        if set(self.activation_sources) != set(self.activation_streaks):
            raise ValueError("activation source keys must match activation streak keys")
        if set(self.resolution_sources) != set(self.resolution_streaks):
            raise ValueError("resolution source keys must match resolution streak keys")
        if self.last_evaluated_month is not None:
            self.last_evaluated_month = _month(
                self.last_evaluated_month,
                "last_evaluated_month",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_by_region": {
                region_id: occurrence.to_dict()
                for region_id, occurrence in sorted(self.active_by_region.items())
            },
            "activation_streaks": dict(sorted(self.activation_streaks.items())),
            "resolution_streaks": dict(sorted(self.resolution_streaks.items())),
            "activation_sources": {
                region_id: list(source_ids)
                for region_id, source_ids in sorted(self.activation_sources.items())
            },
            "resolution_sources": {
                region_id: list(source_ids)
                for region_id, source_ids in sorted(self.resolution_sources.items())
            },
            "last_evaluated_month": self.last_evaluated_month,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalFloodState":
        if not isinstance(data, dict) or set(data) != {
            "active_by_region",
            "activation_streaks",
            "resolution_streaks",
            "activation_sources",
            "resolution_sources",
            "last_evaluated_month",
        }:
            raise ValueError("Regional flood state fields do not match the current schema")
        raw_active = data["active_by_region"]
        if not isinstance(raw_active, dict):
            raise ValueError("active_by_region must be an object")
        return cls(
            active_by_region={
                str(region_id): RegionalFloodOccurrence.from_dict(occurrence)
                for region_id, occurrence in raw_active.items()
            },
            activation_streaks=data["activation_streaks"],
            resolution_streaks=data["resolution_streaks"],
            activation_sources=data["activation_sources"],
            resolution_sources=data["resolution_sources"],
            last_evaluated_month=data["last_evaluated_month"],
        )


__all__ = ["RegionalFloodOccurrence", "RegionalFloodState"]
