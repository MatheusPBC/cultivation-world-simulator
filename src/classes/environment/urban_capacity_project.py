"""Durable canonical state for a city capacity expansion project."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.classes.regional_economy import QUANTITY_EPSILON


class UrbanCapacityProjectStatus(StrEnum):
    RUNNING = "running"
    STALLED = "stalled"
    COMPLETED = "completed"


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_int(value: Any, label: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_positive_finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number > 0")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be a finite number > 0")
    return result


def _strict_keys(data: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(data)
    missing = expected - actual
    unknown = actual - expected
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        raise ValueError(f"{label} has invalid fields: {', '.join(details)}")


@dataclass(frozen=True)
class UrbanCapacityProject:
    """A persistent, city-owned effort to expand settlement capacity."""

    id: str
    kind: str
    status: UrbanCapacityProjectStatus
    housing_asset_id: str
    construction_resource_id: str
    construction_work_asset_id: str
    started_month: int
    required_months: int
    completed_months: int
    capacity_increase: float
    material_required: float
    material_consumed: float
    motivation_event_ids: tuple[str, ...]
    last_event_id: str
    last_processed_month: int | None = None
    completed_month: int | None = None

    def __post_init__(self) -> None:
        _require_string(self.id, "project id")
        if self.kind != "settlement_capacity_expansion":
            raise ValueError("project kind must be settlement_capacity_expansion")
        if not isinstance(self.status, UrbanCapacityProjectStatus):
            raise TypeError("project status must be an UrbanCapacityProjectStatus")
        _require_string(self.housing_asset_id, "housing asset id")
        _require_string(self.construction_resource_id, "construction resource id")
        _require_string(self.construction_work_asset_id, "construction work asset id")
        started_month = _require_int(self.started_month, "started_month", minimum=0)
        required_months = _require_int(self.required_months, "required_months", minimum=1)
        completed_months = _require_int(self.completed_months, "completed_months", minimum=0)
        if completed_months > required_months:
            raise ValueError("completed_months must not exceed required_months")
        capacity_increase = _require_positive_finite(self.capacity_increase, "capacity_increase")
        material_required = _require_positive_finite(self.material_required, "material_required")
        material_consumed = _require_nonnegative_finite(self.material_consumed, "material_consumed")
        if material_consumed - material_required > QUANTITY_EPSILON:
            raise ValueError("material_consumed must not exceed material_required")
        if not isinstance(self.motivation_event_ids, (list, tuple)) or not self.motivation_event_ids:
            raise ValueError("motivation_event_ids must be a non-empty tuple")
        motivation_event_ids = tuple(
            _require_string(event_id, "motivation event id") for event_id in self.motivation_event_ids
        )
        last_event_id = _require_string(self.last_event_id, "last_event_id")

        if self.last_processed_month is not None:
            last_processed_month = _require_int(
                self.last_processed_month, "last_processed_month", minimum=started_month
            )
        else:
            last_processed_month = None

        if self.status is UrbanCapacityProjectStatus.COMPLETED:
            if completed_months != required_months:
                raise ValueError("completed_months must equal required_months when completed")
            if not math.isclose(
                material_consumed,
                material_required,
                abs_tol=QUANTITY_EPSILON,
            ):
                raise ValueError("material_consumed must equal material_required when completed")
            if self.completed_month is None:
                raise ValueError("completed_month is required when project is completed")
        elif self.completed_month is not None:
            raise ValueError("completed_month is only allowed when project is completed")
        elif completed_months == required_months:
            raise ValueError("completed project must use completed status")
        elif math.isclose(
            material_consumed,
            material_required,
            abs_tol=QUANTITY_EPSILON,
        ):
            raise ValueError("complete material consumption requires completed status")

        if self.completed_month is not None:
            completed_month = _require_int(self.completed_month, "completed_month", minimum=0)
            if completed_month < started_month:
                raise ValueError("completed_month must not precede started_month")
            object.__setattr__(self, "completed_month", completed_month)

        object.__setattr__(self, "started_month", started_month)
        object.__setattr__(self, "required_months", required_months)
        object.__setattr__(self, "completed_months", completed_months)
        object.__setattr__(self, "capacity_increase", capacity_increase)
        object.__setattr__(self, "material_required", material_required)
        object.__setattr__(self, "material_consumed", material_consumed)
        object.__setattr__(self, "motivation_event_ids", motivation_event_ids)
        object.__setattr__(self, "last_event_id", last_event_id)
        object.__setattr__(self, "last_processed_month", last_processed_month)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status.value,
            "housing_asset_id": self.housing_asset_id,
            "construction_resource_id": self.construction_resource_id,
            "construction_work_asset_id": self.construction_work_asset_id,
            "started_month": self.started_month,
            "required_months": self.required_months,
            "completed_months": self.completed_months,
            "capacity_increase": self.capacity_increase,
            "material_required": self.material_required,
            "material_consumed": self.material_consumed,
            "motivation_event_ids": list(self.motivation_event_ids),
            "last_event_id": self.last_event_id,
            "last_processed_month": self.last_processed_month,
            "completed_month": self.completed_month,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UrbanCapacityProject":
        if not isinstance(data, dict):
            raise ValueError("urban capacity project must be an object")
        _strict_keys(
            data,
            {
                "id",
                "kind",
                "status",
                "housing_asset_id",
                "construction_resource_id",
                "construction_work_asset_id",
                "started_month",
                "required_months",
                "completed_months",
                "capacity_increase",
                "material_required",
                "material_consumed",
                "motivation_event_ids",
                "last_event_id",
                "last_processed_month",
                "completed_month",
            },
            "urban capacity project",
        )
        if not isinstance(data["status"], str):
            raise ValueError("project status must be a string")
        try:
            status = UrbanCapacityProjectStatus(data["status"])
        except ValueError as exc:
            raise ValueError("project status is invalid") from exc
        if not isinstance(data["motivation_event_ids"], list):
            raise ValueError("motivation_event_ids must be a list")
        return cls(
            id=data["id"],
            kind=data["kind"],
            status=status,
            housing_asset_id=data["housing_asset_id"],
            construction_resource_id=data["construction_resource_id"],
            construction_work_asset_id=data["construction_work_asset_id"],
            started_month=data["started_month"],
            required_months=data["required_months"],
            completed_months=data["completed_months"],
            capacity_increase=data["capacity_increase"],
            material_required=data["material_required"],
            material_consumed=data["material_consumed"],
            motivation_event_ids=tuple(data["motivation_event_ids"]),
            last_event_id=data["last_event_id"],
            last_processed_month=data["last_processed_month"],
            completed_month=data["completed_month"],
        )


def _require_nonnegative_finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be finite and non-negative")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return result
