"""Typed observations and intents for material hazard impacts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real
from collections.abc import Iterable
from typing import Any

from src.classes.mechanical_language import EntityRef


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _ratio(value: Any, field_name: str, *, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    normalized = float(value)
    if (
        not math.isfinite(normalized)
        or normalized < 0.0
        or normalized > 1.0
        or (not allow_zero and normalized == 0.0)
    ):
        suffix = (
            "greater than 0 and at most 1"
            if not allow_zero
            else "between 0 and 1"
        )
        raise ValueError(f"{field_name} must be {suffix}")
    return normalized


def _identifiers(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be an array")
    normalized = tuple(
        dict.fromkeys(_identifier(value, f"{field_name} item") for value in values)
    )
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


class HazardImpactEffect(StrEnum):
    REDUCE_INTEGRITY = "reduce_integrity"


@dataclass(frozen=True, slots=True)
class HazardInteractionDefinition:
    """An engine law mapping exposure and target resistance to a bounded effect."""

    hazard_kind: str
    target_kind: str
    threshold: float
    resistance_weights: tuple[tuple[str, float], ...]
    effect: HazardImpactEffect
    minimum_magnitude: float
    maximum_magnitude: float
    curve_slope: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "hazard_kind", _identifier(self.hazard_kind, "hazard_kind"))
        object.__setattr__(self, "target_kind", _identifier(self.target_kind, "target_kind"))
        object.__setattr__(self, "threshold", _ratio(self.threshold, "threshold", allow_zero=False))
        if not isinstance(self.effect, HazardImpactEffect):
            raise ValueError("effect must be a HazardImpactEffect")
        minimum = _ratio(self.minimum_magnitude, "minimum_magnitude", allow_zero=False)
        maximum = _ratio(self.maximum_magnitude, "maximum_magnitude", allow_zero=False)
        if maximum < minimum:
            raise ValueError("maximum_magnitude must be at least minimum_magnitude")
        object.__setattr__(self, "minimum_magnitude", minimum)
        object.__setattr__(self, "maximum_magnitude", maximum)
        if (
            isinstance(self.curve_slope, bool)
            or not isinstance(self.curve_slope, Real)
            or not math.isfinite(float(self.curve_slope))
            or float(self.curve_slope) <= 0
        ):
            raise ValueError("curve_slope must be a positive finite number")
        object.__setattr__(self, "curve_slope", float(self.curve_slope))
        normalized: list[tuple[str, float]] = []
        for capability_id, weight in self.resistance_weights:
            normalized.append(
                (
                    _identifier(capability_id, "resistance capability"),
                    _ratio(weight, "resistance weight", allow_zero=False),
                )
            )
        if len({item[0] for item in normalized}) != len(normalized):
            raise ValueError("resistance capabilities must be unique")
        object.__setattr__(self, "resistance_weights", tuple(sorted(normalized)))

    def effective_exposure(
        self, exposure: float, capability_ids: Iterable[str]
    ) -> float:
        raw = _ratio(exposure, "exposure")
        capabilities = {str(item) for item in capability_ids}
        resistance = min(
            0.95,
            sum(weight for capability, weight in self.resistance_weights if capability in capabilities),
        )
        return raw * (1.0 - resistance)

    def magnitude(self, exposure: float, capability_ids: Iterable[str]) -> float | None:
        effective = self.effective_exposure(exposure, capability_ids)
        if effective < self.threshold:
            return None
        return min(
            self.maximum_magnitude,
            max(
                self.minimum_magnitude,
                (effective - self.threshold) * self.curve_slope + self.minimum_magnitude,
            ),
        )


@dataclass(frozen=True, slots=True)
class HazardExposure:
    """A read-only, mechanically calculated exposure of one canonical target."""

    hazard_kind: str
    occurrence_event_id: str
    target_ref: EntityRef
    exposure: float
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hazard_kind",
            _identifier(self.hazard_kind, "hazard_kind"),
        )
        object.__setattr__(
            self,
            "occurrence_event_id",
            _identifier(self.occurrence_event_id, "occurrence_event_id"),
        )
        if not isinstance(self.target_ref, EntityRef):
            raise ValueError("target_ref must be an EntityRef")
        object.__setattr__(self, "exposure", _ratio(self.exposure, "exposure"))
        object.__setattr__(
            self,
            "state_refs",
            _identifiers(self.state_refs, "state_refs"),
        )
        source_ids = _identifiers(self.source_event_ids, "source_event_ids")
        if self.occurrence_event_id not in source_ids:
            raise ValueError("source_event_ids must include occurrence_event_id")
        object.__setattr__(self, "source_event_ids", source_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hazard_kind": self.hazard_kind,
            "occurrence_event_id": self.occurrence_event_id,
            "target_ref": self.target_ref.to_dict(),
            "exposure": self.exposure,
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True, slots=True)
class HazardImpactProposal:
    """A request for one domain owner to apply a bounded material effect."""

    hazard_kind: str
    source_event_id: str
    target_ref: EntityRef
    effect: HazardImpactEffect
    magnitude: float
    exposure: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hazard_kind",
            _identifier(self.hazard_kind, "hazard_kind"),
        )
        object.__setattr__(
            self,
            "source_event_id",
            _identifier(self.source_event_id, "source_event_id"),
        )
        if not isinstance(self.target_ref, EntityRef):
            raise ValueError("target_ref must be an EntityRef")
        if not isinstance(self.effect, HazardImpactEffect):
            raise ValueError("effect must be a HazardImpactEffect")
        object.__setattr__(
            self,
            "magnitude",
            _ratio(self.magnitude, "magnitude", allow_zero=False),
        )
        object.__setattr__(self, "exposure", _ratio(self.exposure, "exposure"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_type": "hazard_impact",
            "hazard_kind": self.hazard_kind,
            "source_event_id": self.source_event_id,
            "target_ref": self.target_ref.to_dict(),
            "effect": self.effect.value,
            "magnitude": self.magnitude,
            "exposure": self.exposure,
        }


__all__ = [
    "HazardExposure",
    "HazardImpactEffect",
    "HazardImpactProposal",
    "HazardInteractionDefinition",
]
