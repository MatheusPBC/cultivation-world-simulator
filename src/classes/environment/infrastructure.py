"""Canonical, map-owned infrastructure sites."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

from src.classes.mechanical_language import EntityRef

CellRef = tuple[int, int]


def _require_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _normalize_ids(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list or tuple")
    result = tuple(_require_id(item, f"{field_name} item") for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{field_name} must not contain duplicates")
    return result


def _normalize_region_ids(value: Any) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("region_ids must be a non-empty list or tuple")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError("region_ids must contain positive integers")
        result.append(item)
    if len(set(result)) != len(result):
        raise ValueError("region_ids must not contain duplicates")
    return tuple(result)


def _normalize_cell_refs(value: Any) -> tuple[CellRef, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("cell_refs must be a non-empty list or tuple")
    result: list[CellRef] = []
    for cell in value:
        if not isinstance(cell, (list, tuple)) or len(cell) != 2:
            raise ValueError("cell_refs must contain coordinate pairs")
        x, y = cell
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
        ):
            raise ValueError("cell_refs coordinates must be integers")
        result.append((x, y))
    normalized = tuple(result)
    if len(set(normalized)) != len(normalized):
        raise ValueError("cell_refs must not contain duplicates")
    return normalized


def _normalize_integrity(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("integrity must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError("integrity must be between 0 and 1")
    return normalized


@dataclass
class InfrastructureSite:
    """A stable spatial asset whose runtime state is map-owned.

    Identity fields are immutable after construction.  Runtime updates are
    deliberately limited to condition, availability, and causal provenance.
    The site does not own route flow, stocks, production, or downstream
    consequences.
    """

    id: str
    kind: str
    name: str
    cell_refs: tuple[CellRef, ...]
    region_ids: tuple[int, ...]
    route_ids: tuple[str, ...] = ()
    water_body_ids: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    owner_ref: EntityRef | None = None
    maintainer_ref: EntityRef | None = None
    integrity: float = 1.0
    enabled: bool = True
    last_event_id: str | None = None

    _IDENTITY_FIELDS = frozenset(
        {
            "id",
            "kind",
            "name",
            "cell_refs",
            "region_ids",
            "route_ids",
            "water_body_ids",
            "capability_ids",
            "owner_ref",
            "maintainer_ref",
        }
    )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._IDENTITY_FIELDS and getattr(self, "_identity_locked", False):
            raise AttributeError(f"InfrastructureSite identity field is immutable: {name}")
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        self.id = _require_id(self.id, "id")
        self.kind = _require_id(self.kind, "kind")
        self.name = _require_id(self.name, "name")
        self.cell_refs = _normalize_cell_refs(self.cell_refs)
        self.region_ids = _normalize_region_ids(self.region_ids)
        self.route_ids = _normalize_ids(self.route_ids, "route_ids")
        self.water_body_ids = _normalize_ids(self.water_body_ids, "water_body_ids")
        self.capability_ids = _normalize_ids(self.capability_ids, "capability_ids")
        if self.owner_ref is not None and not isinstance(self.owner_ref, EntityRef):
            raise ValueError("owner_ref must be an EntityRef or None")
        if self.maintainer_ref is not None and not isinstance(self.maintainer_ref, EntityRef):
            raise ValueError("maintainer_ref must be an EntityRef or None")
        self.integrity = _normalize_integrity(self.integrity)
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if self.last_event_id is not None:
            self.last_event_id = _require_id(self.last_event_id, "last_event_id")
        object.__setattr__(self, "_identity_locked", True)

    @property
    def status(self) -> str:
        if self.integrity <= 0.0:
            return "destroyed"
        if not self.enabled or self.integrity < 1.0:
            return "impaired"
        return "active"

    def validate_runtime(
        self,
        *,
        integrity: float | None = None,
        enabled: bool | None = None,
        last_event_id: str | None = None,
    ) -> None:
        if integrity is not None:
            _normalize_integrity(integrity)
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        if last_event_id is not None:
            _require_id(last_event_id, "last_event_id")

    def update_runtime(
        self,
        *,
        integrity: float | None = None,
        enabled: bool | None = None,
        last_event_id: str | None = None,
    ) -> bool:
        """Apply only validated runtime fields and return whether state changed."""
        self.validate_runtime(
            integrity=integrity,
            enabled=enabled,
            last_event_id=last_event_id,
        )
        changed = any(
            (
                integrity is not None and _normalize_integrity(integrity) != self.integrity,
                enabled is not None and enabled != self.enabled,
                last_event_id is not None and last_event_id != self.last_event_id,
            )
        )
        if integrity is not None:
            self.integrity = _normalize_integrity(integrity)
        if enabled is not None:
            self.enabled = enabled
        if last_event_id is not None:
            self.last_event_id = last_event_id
        return changed

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "cell_refs": [list(cell) for cell in self.cell_refs],
            "region_ids": list(self.region_ids),
            "route_ids": list(self.route_ids),
            "water_body_ids": list(self.water_body_ids),
            "capability_ids": list(self.capability_ids),
            "owner_ref": self.owner_ref.to_dict() if self.owner_ref is not None else None,
            "maintainer_ref": (
                self.maintainer_ref.to_dict() if self.maintainer_ref is not None else None
            ),
            "integrity": self.integrity,
            "enabled": self.enabled,
            "last_event_id": self.last_event_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "InfrastructureSite":
        if not isinstance(data, dict):
            raise ValueError("Infrastructure site must be an object")
        required = (
            "id",
            "kind",
            "name",
            "cell_refs",
            "region_ids",
            "route_ids",
            "water_body_ids",
            "capability_ids",
            "integrity",
            "enabled",
        )
        missing = [field_name for field_name in required if field_name not in data]
        if missing:
            raise ValueError(
                "Infrastructure site missing fields: " + ", ".join(missing)
            )
        allowed = {*required, "owner_ref", "maintainer_ref", "last_event_id"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "Infrastructure site has unknown fields: " + ", ".join(sorted(unknown))
            )
        owner_data = data.get("owner_ref")
        maintainer_data = data.get("maintainer_ref")
        if owner_data is not None and not isinstance(owner_data, dict):
            raise ValueError("owner_ref must be an object or null")
        if maintainer_data is not None and not isinstance(maintainer_data, dict):
            raise ValueError("maintainer_ref must be an object or null")
        try:
            owner_ref = EntityRef.from_dict(owner_data) if owner_data is not None else None
            maintainer_ref = (
                EntityRef.from_dict(maintainer_data) if maintainer_data is not None else None
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("owner_ref and maintainer_ref must contain kind and id") from exc
        return cls(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            cell_refs=data["cell_refs"],
            region_ids=data["region_ids"],
            route_ids=data["route_ids"],
            water_body_ids=data["water_body_ids"],
            capability_ids=data["capability_ids"],
            owner_ref=owner_ref,
            maintainer_ref=maintainer_ref,
            integrity=data["integrity"],
            enabled=data["enabled"],
            last_event_id=data.get("last_event_id"),
        )


__all__ = ["CellRef", "InfrastructureSite"]
