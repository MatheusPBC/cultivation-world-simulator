from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .models import (
    MeasurementAvailability,
    MetricKey,
    MetricReading,
    PrimitiveDimension,
    ReadingKind,
)


MetricResolver = Callable[[Any, MetricKey, Any, int], MetricReading | None]
MetricEnumerator = Callable[[Any, Any], Iterable[MetricKey]]


@dataclass(frozen=True, slots=True)
class GroundedMetricBinding:
    """Runtime bridge between a mechanical key and canonical domain state.

    Bindings are engine code and are never persisted.  Saves contain only
    semantic definitions and stable IDs; Python callables are reconstructed by
    the current engine version.
    """

    id: str
    subject_kind: str
    dimension: PrimitiveDimension
    concept_pattern: str
    unit: str
    resolver: MetricResolver
    enumerate_keys: MetricEnumerator | None = None
    required_qualifiers: tuple[tuple[str, str], ...] = ()
    exact_qualifiers: bool = True

    def matches(self, key: MetricKey) -> bool:
        if self.subject_kind not in {"*", key.subject_kind}:
            return False
        if self.dimension is not key.dimension:
            return False
        if self.concept_pattern not in {"*", key.concept_id}:
            return False
        qualifiers = dict(key.qualifiers)
        if not all(
            qualifiers.get(name) == value
            for name, value in self.required_qualifiers
        ):
            return False
        return not self.exact_qualifiers or key.qualifiers == self.required_qualifiers


class MetricResolverRegistry:
    def __init__(self, bindings: Iterable[GroundedMetricBinding] = ()) -> None:
        self._bindings: list[GroundedMetricBinding] = []
        for binding in bindings:
            self.register(binding)

    def register(self, binding: GroundedMetricBinding) -> None:
        if any(item.id == binding.id for item in self._bindings):
            raise ValueError(f"duplicate metric binding id: {binding.id}")
        self._bindings.append(binding)

    def binding_for(self, key: MetricKey) -> GroundedMetricBinding | None:
        matches = [item for item in self._bindings if item.matches(key)]
        if not matches:
            return None
        return max(
            matches,
            key=lambda item: (
                item.subject_kind != "*",
                item.concept_pattern != "*",
                len(item.required_qualifiers),
            ),
        )

    def unit_for(self, key: MetricKey) -> str | None:
        binding = self.binding_for(key)
        return binding.unit if binding is not None else None

    def resolve(
        self,
        world: Any,
        key: MetricKey,
        *,
        target: Any,
        calculated_month: int,
    ) -> MetricReading:
        binding = self.binding_for(key)
        if binding is None:
            return _unknown(key, calculated_month)
        reading = binding.resolver(world, key, target, calculated_month)
        if reading is None:
            return _unknown(key, calculated_month, unit=binding.unit)
        if reading.key != key:
            raise ValueError(f"metric binding {binding.id} returned a mismatched key")
        if reading.unit != binding.unit:
            raise ValueError(f"metric binding {binding.id} returned a mismatched unit")
        return reading

    def available_keys(self, world: Any, target: Any) -> list[MetricKey]:
        found: dict[tuple[Any, ...], MetricKey] = {}
        for binding in self._bindings:
            if binding.enumerate_keys is None:
                continue
            for key in binding.enumerate_keys(world, target):
                if not binding.matches(key):
                    raise ValueError(f"metric binding {binding.id} enumerated an invalid key")
                found[key.identity] = key
        return sorted(
            found.values(),
            key=lambda key: (
                key.dimension.value,
                key.concept_id,
                key.group_id or "",
                key.qualifiers,
                key.subject_kind,
                key.subject_id,
            ),
        )


def exact_reading(
    key: MetricKey,
    value: float,
    unit: str,
    month: int,
    state_ref: str,
) -> MetricReading:
    return MetricReading(
        key=key,
        value=float(value),
        unit=unit,
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=ReadingKind.EXACT,
        calculated_month=month,
        state_refs=[state_ref],
    )


def _unknown(key: MetricKey, month: int, *, unit: str = "unknown") -> MetricReading:
    return MetricReading(
        key=key,
        value=None,
        unit=unit,
        availability=MeasurementAvailability.UNMEASURABLE,
        reading_kind=ReadingKind.UNKNOWN,
        calculated_month=month,
    )
