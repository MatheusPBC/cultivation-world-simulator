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


def _context_ids(values: Any, field_name: str) -> tuple[str, ...]:
    """Contextual evidence may legitimately be absent for a region."""
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    return tuple(dict.fromkeys(_non_empty(value, field_name) for value in values))


def _refs(values: Any, field_name: str) -> tuple[str, ...]:
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


@dataclass(frozen=True, slots=True)
class DrainageObservation:
    """The drainage capacity actually observed in one month of a window.

    The value is stored as it was read that month, together with the
    infrastructure works that grounded it, so later readers never have to
    recompute a past month from the current world.
    """

    month: int
    drainage: float
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "month", _month(self.month, "month"))
        object.__setattr__(self, "drainage", _ratio(self.drainage, "drainage"))
        object.__setattr__(self, "state_refs", _refs(self.state_refs, "state_refs"))
        object.__setattr__(
            self,
            "source_event_ids",
            _context_ids(self.source_event_ids, "source_event_ids"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "drainage": self.drainage,
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "DrainageObservation":
        if not isinstance(data, dict) or set(data) != {
            "month",
            "drainage",
            "state_refs",
            "source_event_ids",
        }:
            raise ValueError("Drainage observation fields do not match the current schema")
        return cls(**data)


def _observations(values: Any, field_name: str) -> tuple[DrainageObservation, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[DrainageObservation] = []
    seen: set[int] = set()
    for observation in values:
        if not isinstance(observation, DrainageObservation):
            raise TypeError(f"{field_name} must contain DrainageObservation values")
        if observation.month in seen:
            raise ValueError(f"{field_name} must hold one observation per month")
        seen.add(observation.month)
        normalized.append(observation)
    return tuple(sorted(normalized, key=lambda item: item.month))


@dataclass(frozen=True, slots=True)
class FloodWindowEvidence:
    """Evidence accumulated across every month of a flood transition window.

    ``source_event_ids`` are the weather observations that can causally drive
    the transition.  ``drainage_observations`` keep one reading per month of
    the window: drainage explains how much water the region could shed, never
    why water arrived, so it stays contextual.  Every month is kept because a
    site's last event changes between the months of the same window.
    """

    source_event_ids: tuple[str, ...]
    drainage_observations: tuple[DrainageObservation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_event_ids",
            _source_ids(self.source_event_ids, "source_event_ids"),
        )
        object.__setattr__(
            self,
            "drainage_observations",
            _observations(self.drainage_observations, "drainage_observations"),
        )

    @property
    def infrastructure_context_event_ids(self) -> tuple[str, ...]:
        """Every infrastructure work observed across the whole window."""
        return tuple(
            dict.fromkeys(
                event_id
                for observation in self.drainage_observations
                for event_id in observation.source_event_ids
            )
        )

    def extended(
        self,
        *,
        source_event_ids: tuple[str, ...],
        drainage: DrainageObservation,
    ) -> "FloodWindowEvidence":
        """Return this window plus one more month of observations."""
        return FloodWindowEvidence(
            source_event_ids=(*self.source_event_ids, *source_event_ids),
            drainage_observations=(
                *(
                    observation
                    for observation in self.drainage_observations
                    if observation.month != drainage.month
                ),
                drainage,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_event_ids": list(self.source_event_ids),
            "drainage_observations": [
                observation.to_dict() for observation in self.drainage_observations
            ],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "FloodWindowEvidence":
        if not isinstance(data, dict) or set(data) != {
            "source_event_ids",
            "drainage_observations",
        }:
            raise ValueError("Flood window evidence fields do not match the current schema")
        raw_observations = data["drainage_observations"]
        if not isinstance(raw_observations, list):
            raise ValueError("drainage_observations must be an array")
        return cls(
            source_event_ids=data["source_event_ids"],
            drainage_observations=tuple(
                DrainageObservation.from_dict(observation)
                for observation in raw_observations
            ),
        )


def _evidence_map(values: Any, field_name: str) -> dict[str, FloodWindowEvidence]:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name} must be an object")
    normalized: dict[str, FloodWindowEvidence] = {}
    for region_id, evidence in values.items():
        if not isinstance(evidence, FloodWindowEvidence):
            raise TypeError(f"{field_name} must contain FloodWindowEvidence values")
        normalized[_non_empty(region_id, field_name)] = evidence
    return normalized


def _validate_window(
    evidence_by_region: dict[str, "FloodWindowEvidence"],
    streaks: dict[str, int],
    last_evaluated_month: int | None,
    field_name: str,
) -> None:
    """A pending window must be the consecutive months just evaluated.

    One drainage observation per streak month, ending on the last evaluated
    month, is what keeps the window an actual observation history instead of
    a set of months invented at load time.
    """
    for region_id, evidence in evidence_by_region.items():
        months = [observation.month for observation in evidence.drainage_observations]
        if len(months) != streaks[region_id]:
            raise ValueError(f"{field_name} must hold one observation per streak month")
        if last_evaluated_month is None:
            raise ValueError(f"{field_name} requires an evaluated month")
        if months != list(
            range(last_evaluated_month - len(months) + 1, last_evaluated_month + 1)
        ):
            raise ValueError(
                f"{field_name} months must be the consecutive window ending at "
                "last_evaluated_month"
            )


@dataclass(frozen=True, slots=True)
class RegionalFloodOccurrence:
    """One active physical flood, grounded by hydrological evidence."""

    region_id: str
    started_month: int
    activation_risk: float
    source_event_ids: tuple[str, ...]
    last_event_id: str
    drainage_observations: tuple[DrainageObservation, ...] = ()

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
        object.__setattr__(
            self,
            "drainage_observations",
            _observations(self.drainage_observations, "drainage_observations"),
        )

    @property
    def infrastructure_context_event_ids(self) -> tuple[str, ...]:
        """Infrastructure works observed across the activation window."""
        return tuple(
            dict.fromkeys(
                event_id
                for observation in self.drainage_observations
                for event_id in observation.source_event_ids
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "started_month": self.started_month,
            "activation_risk": self.activation_risk,
            "source_event_ids": list(self.source_event_ids),
            "last_event_id": self.last_event_id,
            "drainage_observations": [
                observation.to_dict() for observation in self.drainage_observations
            ],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalFloodOccurrence":
        if not isinstance(data, dict) or set(data) != {
            "region_id",
            "started_month",
            "activation_risk",
            "source_event_ids",
            "last_event_id",
            "drainage_observations",
        }:
            raise ValueError("Regional flood occurrence fields do not match the current schema")
        raw_observations = data["drainage_observations"]
        if not isinstance(raw_observations, list):
            raise ValueError("drainage_observations must be an array")
        return cls(
            region_id=data["region_id"],
            started_month=data["started_month"],
            activation_risk=data["activation_risk"],
            source_event_ids=data["source_event_ids"],
            last_event_id=data["last_event_id"],
            drainage_observations=tuple(
                DrainageObservation.from_dict(observation)
                for observation in raw_observations
            ),
        )


@dataclass(slots=True)
class RegionalFloodState:
    """World-owned active floods and their persistence observations."""

    active_by_region: dict[str, RegionalFloodOccurrence] = field(default_factory=dict)
    activation_streaks: dict[str, int] = field(default_factory=dict)
    resolution_streaks: dict[str, int] = field(default_factory=dict)
    activation_evidence: dict[str, FloodWindowEvidence] = field(default_factory=dict)
    resolution_evidence: dict[str, FloodWindowEvidence] = field(default_factory=dict)
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
        self.activation_evidence = _evidence_map(
            self.activation_evidence, "activation_evidence"
        )
        self.resolution_evidence = _evidence_map(
            self.resolution_evidence, "resolution_evidence"
        )
        if set(self.activation_evidence) != set(self.activation_streaks):
            raise ValueError("activation evidence keys must match activation streak keys")
        if set(self.resolution_evidence) != set(self.resolution_streaks):
            raise ValueError("resolution evidence keys must match resolution streak keys")
        if self.last_evaluated_month is not None:
            self.last_evaluated_month = _month(
                self.last_evaluated_month,
                "last_evaluated_month",
            )
        _validate_window(
            self.activation_evidence,
            self.activation_streaks,
            self.last_evaluated_month,
            "activation_evidence",
        )
        _validate_window(
            self.resolution_evidence,
            self.resolution_streaks,
            self.last_evaluated_month,
            "resolution_evidence",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_by_region": {
                region_id: occurrence.to_dict()
                for region_id, occurrence in sorted(self.active_by_region.items())
            },
            "activation_streaks": dict(sorted(self.activation_streaks.items())),
            "resolution_streaks": dict(sorted(self.resolution_streaks.items())),
            "activation_evidence": {
                region_id: evidence.to_dict()
                for region_id, evidence in sorted(self.activation_evidence.items())
            },
            "resolution_evidence": {
                region_id: evidence.to_dict()
                for region_id, evidence in sorted(self.resolution_evidence.items())
            },
            "last_evaluated_month": self.last_evaluated_month,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalFloodState":
        if not isinstance(data, dict) or set(data) != {
            "active_by_region",
            "activation_streaks",
            "resolution_streaks",
            "activation_evidence",
            "resolution_evidence",
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
            activation_evidence=_decoded_evidence(
                data["activation_evidence"], "activation_evidence"
            ),
            resolution_evidence=_decoded_evidence(
                data["resolution_evidence"], "resolution_evidence"
            ),
            last_evaluated_month=data["last_evaluated_month"],
        )


def _decoded_evidence(values: Any, field_name: str) -> dict[str, FloodWindowEvidence]:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name} must be an object")
    return {
        str(region_id): FloodWindowEvidence.from_dict(evidence)
        for region_id, evidence in values.items()
    }


__all__ = [
    "DrainageObservation",
    "FloodWindowEvidence",
    "RegionalFloodOccurrence",
    "RegionalFloodState",
]
