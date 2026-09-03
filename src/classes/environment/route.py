"""Explicit inter-region routes owned by :class:`environment.map.Map`."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, ClassVar


def _require_region_id(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_number(value: Any, field_name: str, *, minimum: float, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < minimum:
        raise ValueError(f"{field_name} must be finite and >= {minimum}")
    if maximum is not None and normalized > maximum:
        raise ValueError(f"{field_name} must be <= {maximum}")
    return normalized


def _normalize_resource_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("allowed_resource_ids must be a list")
    resource_ids: list[str] = []
    for resource_id in value:
        normalized = _require_non_empty_string(resource_id, "allowed_resource_ids item")
        if normalized in resource_ids:
            raise ValueError(f"Duplicate allowed resource id: {normalized}")
        resource_ids.append(normalized)
    return tuple(resource_ids)


@dataclass
class Route:
    """A stable, explicitly authored connection between exactly two regions.

    Route state is intentionally mutable only through the validated runtime
    fields.  The endpoint pair and policy remain stable after construction.
    """

    id: str
    endpoint_region_ids: tuple[int, int]
    mode: str
    capacity: float
    quality: float
    enabled: bool
    allowed_resource_ids: tuple[str, ...] = ()

    _IDENTITY_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"id", "endpoint_region_ids", "mode", "allowed_resource_ids"}
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._IDENTITY_FIELDS and getattr(self, "_identity_locked", False):
            raise AttributeError(f"Route identity field is immutable: {name}")
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        self.id = _require_non_empty_string(self.id, "id")
        if not isinstance(self.endpoint_region_ids, (list, tuple)) or len(self.endpoint_region_ids) != 2:
            raise ValueError("endpoint_region_ids must contain exactly two region ids")
        endpoints = tuple(
            _require_region_id(value, f"endpoint_region_ids[{index}]")
            for index, value in enumerate(self.endpoint_region_ids)
        )
        if endpoints[0] == endpoints[1]:
            raise ValueError("endpoint_region_ids must be distinct")
        self.endpoint_region_ids = endpoints
        self.mode = _require_non_empty_string(self.mode, "mode")
        self.capacity = _require_number(self.capacity, "capacity", minimum=0.0)
        self.quality = _require_number(self.quality, "quality", minimum=0.0, maximum=1.0)
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        self.allowed_resource_ids = _normalize_resource_ids(self.allowed_resource_ids)
        object.__setattr__(self, "_identity_locked", True)

    def connects(self, region_a: int, region_b: int) -> bool:
        """Return whether this route connects the pair in either direction."""
        endpoints = {
            _require_region_id(region_a, "region_a"),
            _require_region_id(region_b, "region_b"),
        }
        return len(endpoints) == 2 and endpoints == set(self.endpoint_region_ids)

    def allows_resource(self, resource_id: str | None) -> bool:
        if resource_id is not None:
            resource_id = _require_non_empty_string(resource_id, "resource_id")
        if resource_id is None or not self.allowed_resource_ids:
            return True
        return resource_id in self.allowed_resource_ids

    def update_runtime(
        self,
        *,
        capacity: float | None = None,
        quality: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Apply a validated runtime update without changing route identity."""
        if capacity is not None:
            self.capacity = _require_number(capacity, "capacity", minimum=0.0)
        if quality is not None:
            self.quality = _require_number(quality, "quality", minimum=0.0, maximum=1.0)
        if enabled is not None:
            if not isinstance(enabled, bool):
                raise ValueError("enabled must be a boolean")
            self.enabled = enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "endpoint_region_ids": list(self.endpoint_region_ids),
            "mode": self.mode,
            "capacity": self.capacity,
            "quality": self.quality,
            "enabled": self.enabled,
            "allowed_resource_ids": list(self.allowed_resource_ids),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Route":
        if not isinstance(data, dict):
            raise ValueError("Route must be an object")
        required = (
            "id",
            "endpoint_region_ids",
            "mode",
            "capacity",
            "quality",
            "enabled",
            "allowed_resource_ids",
        )
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(f"Route missing fields: {', '.join(missing)}")
        return cls(
            id=data["id"],
            endpoint_region_ids=data["endpoint_region_ids"],
            mode=data["mode"],
            capacity=data["capacity"],
            quality=data["quality"],
            enabled=data["enabled"],
            allowed_resource_ids=data["allowed_resource_ids"],
        )
