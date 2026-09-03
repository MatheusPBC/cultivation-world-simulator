from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


QUANTITY_EPSILON = 1e-9


def _non_negative(value: float, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be finite and non-negative")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return number


def _ratio(value: float, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be finite and in [0, 1]")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be finite and in [0, 1]")
    return number


@dataclass
class RegionalEconomyState:
    """Canonical quantitative economy owned by one region.

    Keys are world concepts (``grain``, ``spirit_stone``, ``healing``), not
    Python enums.  Empty maps mean that the world has no grounded fact for
    that concept; readers must return ``unknown`` instead of guessing.
    """

    stocks: dict[str, float] = field(default_factory=dict)
    capacities: dict[str, float] = field(default_factory=dict)
    production_rates: dict[str, float] = field(default_factory=dict)
    demand_rates: dict[str, float] = field(default_factory=dict)
    access: dict[str, float] = field(default_factory=dict)
    dependencies: dict[str, float] = field(default_factory=dict)
    reservations: dict[str, dict[str, float]] = field(default_factory=dict)
    project_resources: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stocks = self._normalize_non_negative_map(self.stocks, "stock")
        self.capacities = self._normalize_non_negative_map(self.capacities, "capacity")
        self.production_rates = self._normalize_non_negative_map(
            self.production_rates, "production rate"
        )
        self.demand_rates = self._normalize_non_negative_map(self.demand_rates, "demand rate")
        self.access = self._normalize_ratio_map(self.access, "access")
        self.dependencies = self._normalize_ratio_map(self.dependencies, "dependency")
        self.reservations = self._normalize_reservations(self.reservations)
        self.project_resources = self._normalize_project_resources(self.project_resources)
        self._validate_invariants()

    @staticmethod
    def _normalize_non_negative_map(values: dict[str, float], label: str) -> dict[str, float]:
        if not isinstance(values, dict):
            raise ValueError(f"{label} must be an object")
        return {str(key): _non_negative(value, field_name=label) for key, value in values.items()}

    @staticmethod
    def _normalize_ratio_map(values: dict[str, float], label: str) -> dict[str, float]:
        if not isinstance(values, dict):
            raise ValueError(f"{label} must be an object")
        return {str(key): _ratio(value, field_name=label) for key, value in values.items()}

    @staticmethod
    def _normalize_reservations(values: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        if not isinstance(values, dict):
            raise ValueError("reservations must be an object")
        normalized: dict[str, dict[str, float]] = {}
        for project_id, resources in values.items():
            if not isinstance(project_id, str) or not project_id.strip():
                raise ValueError("reservation project id must be a non-empty string")
            if not isinstance(resources, dict) or not resources:
                raise ValueError("reservation resources must be a non-empty object")
            normalized_resources: dict[str, float] = {}
            for resource_id, quantity in resources.items():
                resource_id = _require_id(resource_id, "reservation resource id")
                normalized_resources[resource_id] = _positive_finite(
                    quantity,
                    "reservation quantity",
                )
            normalized[project_id] = normalized_resources
        return normalized

    @staticmethod
    def _normalize_project_resources(values: dict[str, str]) -> dict[str, str]:
        if not isinstance(values, dict):
            raise ValueError("project_resources must be an object")
        normalized: dict[str, str] = {}
        for project_kind, resource_id in values.items():
            project_kind = _require_id(project_kind, "project resource kind")
            resource_id = _require_id(resource_id, "project resource id")
            normalized[project_kind] = resource_id
        return normalized

    def _validate_invariants(self) -> None:
        self._normalize_project_resources(self.project_resources)
        for resource_id, capacity in self.capacities.items():
            if self.stocks.get(resource_id, 0.0) > capacity:
                raise ValueError("stock cannot exceed its declared capacity")
        reserved_by_resource: dict[str, float] = {}
        for project_id, resources in self.reservations.items():
            _require_id(project_id, "reservation project id")
            if not isinstance(resources, dict) or not resources:
                raise ValueError("reservation resources must be a non-empty object")
            for resource_id, quantity in resources.items():
                _require_id(resource_id, "reservation resource id")
                quantity = _positive_finite(quantity, "reservation quantity")
                if resource_id not in self.stocks:
                    raise ValueError("reservation resource must be declared in stocks")
                reserved_by_resource[resource_id] = reserved_by_resource.get(resource_id, 0.0) + quantity
        for resource_id, quantity in reserved_by_resource.items():
            if quantity - self.stocks[resource_id] > QUANTITY_EPSILON:
                raise ValueError("reservations cannot exceed physical stock")

    def available_stock(self, concept_id: str) -> float | None:
        """Return physical stock less every reservation, or ``None`` if unknown."""
        if concept_id not in self.stocks:
            return None
        reserved = sum(
            resources.get(concept_id, 0.0)
            for resources in self.reservations.values()
        )
        available = float(self.stocks[concept_id]) - reserved
        return 0.0 if abs(available) <= QUANTITY_EPSILON else max(0.0, available)

    def reserve_stock(self, project_id: str, resource_id: str, quantity: float) -> None:
        project_id = _require_id(project_id, "project id")
        resource_id = _require_id(resource_id, "resource id")
        quantity = _positive_finite(quantity, "reservation quantity")
        available = self.available_stock(resource_id)
        if available is None:
            raise KeyError(resource_id)
        if quantity - available > QUANTITY_EPSILON:
            raise ValueError("insufficient available stock for reservation")
        resources = self.reservations.setdefault(project_id, {})
        resources[resource_id] = resources.get(resource_id, 0.0) + quantity

    def consume_reserved_stock(self, project_id: str, resource_id: str, quantity: float) -> float:
        project_id = _require_id(project_id, "project id")
        resource_id = _require_id(resource_id, "resource id")
        quantity = _positive_finite(quantity, "consumption quantity")
        reserved = self.reservations.get(project_id, {}).get(resource_id)
        if reserved is None:
            raise ValueError("insufficient reserved stock")
        if quantity > reserved:
            if not math.isclose(quantity, reserved, abs_tol=QUANTITY_EPSILON):
                raise ValueError("insufficient reserved stock")
            quantity = reserved
        physical = self.stocks.get(resource_id)
        if physical is None or quantity - physical > QUANTITY_EPSILON:
            raise ValueError("insufficient physical stock")
        next_stock = physical - quantity
        self.stocks[resource_id] = (
            0.0 if abs(next_stock) <= QUANTITY_EPSILON else next_stock
        )
        remaining = reserved - quantity
        resources = self.reservations[project_id]
        if math.isclose(remaining, 0.0, abs_tol=QUANTITY_EPSILON):
            del resources[resource_id]
        else:
            resources[resource_id] = remaining
        if not resources:
            del self.reservations[project_id]
        return self.stocks[resource_id]

    def release_reservation(self, project_id: str) -> dict[str, float]:
        project_id = _require_id(project_id, "project id")
        return dict(self.reservations.pop(project_id, {}))

    def set_stock(self, concept_id: str, value: float) -> None:
        value = _non_negative(value, field_name="stock")
        capacity = self.capacities.get(concept_id)
        if capacity is not None and value > capacity:
            raise ValueError("stock cannot exceed its declared capacity")
        reserved = sum(resources.get(concept_id, 0.0) for resources in self.reservations.values())
        if reserved - value > QUANTITY_EPSILON:
            raise ValueError("stock cannot be below its reservations")
        self.stocks[str(concept_id)] = value

    def change_stock(self, concept_id: str, delta: float) -> float:
        if concept_id not in self.stocks:
            raise KeyError(concept_id)
        if isinstance(delta, bool) or not math.isfinite(float(delta)):
            raise ValueError("stock delta must be finite")
        current = float(self.stocks[concept_id])
        next_value = current + float(delta)
        capacity = self.capacities.get(concept_id)
        if capacity is not None:
            next_value = min(next_value, capacity)
        next_value = max(0.0, next_value)
        reserved = sum(resources.get(concept_id, 0.0) for resources in self.reservations.values())
        if reserved - next_value > QUANTITY_EPSILON:
            raise ValueError("stock cannot be below its reservations")
        if abs(next_value - reserved) <= QUANTITY_EPSILON:
            next_value = reserved
        self.stocks[concept_id] = next_value
        return next_value

    def set_capacity(self, concept_id: str, value: float) -> None:
        value = _non_negative(value, field_name="capacity")
        if self.stocks.get(concept_id, 0.0) > value:
            raise ValueError("capacity cannot be below current stock")
        self.capacities[str(concept_id)] = value

    def set_production_rate(self, concept_id: str, value: float) -> None:
        self.production_rates[str(concept_id)] = _non_negative(value, field_name="production rate")

    def set_demand_rate(self, concept_id: str, value: float) -> None:
        self.demand_rates[str(concept_id)] = _non_negative(value, field_name="demand rate")

    def set_access(self, concept_id: str, value: float) -> None:
        self.access[str(concept_id)] = _ratio(value, field_name="access")

    def set_dependency(self, concept_id: str, value: float) -> None:
        self.dependencies[str(concept_id)] = _ratio(value, field_name="dependency")

    def to_dict(self) -> dict[str, Any]:
        self._validate_invariants()
        return {
            "stocks": dict(self.stocks),
            "capacities": dict(self.capacities),
            "production_rates": dict(self.production_rates),
            "demand_rates": dict(self.demand_rates),
            "access": dict(self.access),
            "dependencies": dict(self.dependencies),
            "reservations": {
                project_id: dict(resources)
                for project_id, resources in self.reservations.items()
            },
            "project_resources": dict(self.project_resources),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RegionalEconomyState":
        if not isinstance(data, dict):
            raise ValueError("regional economy must be an object")
        expected = {
            "stocks",
            "capacities",
            "production_rates",
            "demand_rates",
            "access",
            "dependencies",
            "reservations",
            "project_resources",
        }
        if set(data) != expected:
            raise ValueError("regional economy has invalid fields")
        for field_name in expected:
            if not isinstance(data[field_name], dict):
                raise ValueError(f"regional economy {field_name} must be an object")
        if any(not isinstance(resources, dict) for resources in data["reservations"].values()):
            raise ValueError("regional economy reservation resources must be objects")
        return cls(
            stocks=dict(data["stocks"]),
            capacities=dict(data["capacities"]),
            production_rates=dict(data["production_rates"]),
            demand_rates=dict(data["demand_rates"]),
            access=dict(data["access"]),
            dependencies=dict(data["dependencies"]),
            reservations={
                project_id: {
                    resource_id: quantity
                    for resource_id, quantity in resources.items()
                }
                for project_id, resources in data["reservations"].items()
            },
            project_resources=dict(data["project_resources"]),
        )


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _positive_finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be finite and positive")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be finite and positive") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


@dataclass
class InfrastructureState:
    """Canonical local infrastructure facts; routes remain map-owned."""

    capacities: dict[str, float] = field(default_factory=dict)
    quality: dict[str, float] = field(default_factory=dict)

    def set_capacity(self, concept_id: str, value: float) -> None:
        self.capacities[str(concept_id)] = _non_negative(value, field_name="infrastructure capacity")

    def set_quality(self, concept_id: str, value: float) -> None:
        self.quality[str(concept_id)] = _ratio(value, field_name="infrastructure quality")

    def to_dict(self) -> dict[str, Any]:
        return {"capacities": dict(self.capacities), "quality": dict(self.quality)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InfrastructureState":
        state = cls(
            capacities={str(k): float(v) for k, v in dict(data.get("capacities", {})).items()},
            quality={str(k): float(v) for k, v in dict(data.get("quality", {})).items()},
        )
        for value in state.capacities.values():
            _non_negative(value, field_name="infrastructure capacity")
        for value in state.quality.values():
            _ratio(value, field_name="infrastructure quality")
        return state
