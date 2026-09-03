"""Canonical, map-independent urban state owned by a :class:`CityRegion`.

This module intentionally contains only durable urban facts.  It does not
derive pressure, interpret events, or perform any simulation.  Those concerns
can consume this state later without becoming additional owners of it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any, Iterable

from src.classes.environment.urban_capacity_project import UrbanCapacityProject


Coordinate = tuple[int, int]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be finite and nonnegative")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def _bounded(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be bounded between 0 and 1")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"{label} must be bounded between 0 and 1")
    return result


def _positive(value: Any, label: str) -> float:
    result = _finite_nonnegative(value, label)
    if result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


def _coordinate(value: Any, label: str) -> Coordinate:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise ValueError(f"{label} must contain integer coordinates")
    return (value[0], value[1])


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
class CityDistrict:
    """A non-overlapping owned part of a city footprint."""

    id: str
    kind: str
    tile_refs: tuple[Coordinate, ...]
    population_weight: float

    def __post_init__(self) -> None:
        _require_string(self.id, "district id")
        _require_string(self.kind, "district kind")
        if not isinstance(self.tile_refs, (list, tuple)):
            raise ValueError("district tile_refs must be a list")
        normalized = tuple(_coordinate(tile, "district tile_refs") for tile in self.tile_refs)
        if len(set(normalized)) != len(normalized):
            raise ValueError("district tile_refs must be unique")
        object.__setattr__(self, "tile_refs", normalized)
        object.__setattr__(self, "population_weight", _bounded(self.population_weight, "population weight"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "tile_refs": [[x, y] for x, y in self.tile_refs],
            "population_weight": self.population_weight,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CityDistrict":
        payload = _require_mapping(data, "district")
        _strict_keys(payload, {"id", "kind", "tile_refs", "population_weight"}, "district")
        if not isinstance(payload["tile_refs"], list):
            raise ValueError("district tile_refs must be a list")
        return cls(
            id=payload["id"],
            kind=payload["kind"],
            tile_refs=tuple(_coordinate(tile, "district tile_refs") for tile in payload["tile_refs"]),
            population_weight=payload["population_weight"],
        )


@dataclass(frozen=True)
class UrbanAsset:
    """A generic urban capability-bearing asset."""

    id: str
    district_id: str
    capability_ids: tuple[str, ...]
    capacity: float
    quality: float
    integrity: float

    def __post_init__(self) -> None:
        _require_string(self.id, "asset id")
        _require_string(self.district_id, "asset district_id")
        if not isinstance(self.capability_ids, (list, tuple)) or not self.capability_ids:
            raise ValueError("asset capability_ids must be a non-empty list")
        capabilities = tuple(_require_string(item, "asset capability id") for item in self.capability_ids)
        if len(set(capabilities)) != len(capabilities):
            raise ValueError("asset capability_ids must be unique")
        object.__setattr__(self, "capability_ids", capabilities)
        object.__setattr__(self, "capacity", _finite_nonnegative(self.capacity, "asset capacity"))
        object.__setattr__(self, "quality", _bounded(self.quality, "asset quality"))
        object.__setattr__(self, "integrity", _bounded(self.integrity, "asset integrity"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "district_id": self.district_id,
            "capability_ids": list(self.capability_ids),
            "capacity": self.capacity,
            "quality": self.quality,
            "integrity": self.integrity,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UrbanAsset":
        payload = _require_mapping(data, "asset")
        _strict_keys(
            payload,
            {"id", "district_id", "capability_ids", "capacity", "quality", "integrity"},
            "asset",
        )
        if not isinstance(payload["capability_ids"], list):
            raise ValueError("asset capability_ids must be a list")
        return cls(
            id=payload["id"],
            district_id=payload["district_id"],
            capability_ids=tuple(payload["capability_ids"]),
            capacity=payload["capacity"],
            quality=payload["quality"],
            integrity=payload["integrity"],
        )


@dataclass(frozen=True)
class UrbanServiceDemand:
    """Declared population load for one dynamic urban capability."""

    capability_id: str
    demand_per_population: float

    def __post_init__(self) -> None:
        _require_string(self.capability_id, "service capability id")
        object.__setattr__(
            self,
            "demand_per_population",
            _positive(self.demand_per_population, "service demand per population"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "demand_per_population": self.demand_per_population,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UrbanServiceDemand":
        payload = _require_mapping(data, "urban service demand")
        _strict_keys(
            payload,
            {"capability_id", "demand_per_population"},
            "urban service demand",
        )
        return cls(
            capability_id=payload["capability_id"],
            demand_per_population=payload["demand_per_population"],
        )


@dataclass(frozen=True)
class UrbanPopulationGroup:
    """A weighted slice of city population, never a second population owner.

    Service priority weights describe relative access to constrained urban
    capacity.  Actual access is always calculated from population, declared
    demand and existing assets.
    """

    id: str
    population_weight: float
    service_priority_weights: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        _require_string(self.id, "urban population group id")
        weight = _bounded(self.population_weight, "urban population group weight")
        if weight <= 0:
            raise ValueError("urban population group weight must be positive")
        object.__setattr__(self, "population_weight", weight)
        raw = self.service_priority_weights
        items = raw.items() if isinstance(raw, Mapping) else raw
        normalized = tuple(
            sorted(
                (
                    _require_string(capability_id, "service priority capability id"),
                    _finite_nonnegative(priority, "service priority weight"),
                )
                for capability_id, priority in items
            )
        )
        if len({capability_id for capability_id, _ in normalized}) != len(normalized):
            raise ValueError("service priority capability ids must be unique")
        object.__setattr__(self, "service_priority_weights", normalized)

    def priority_for(self, capability_id: str) -> float:
        return dict(self.service_priority_weights).get(capability_id, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "population_weight": self.population_weight,
            "service_priority_weights": dict(self.service_priority_weights),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UrbanPopulationGroup":
        payload = _require_mapping(data, "urban population group")
        _strict_keys(
            payload,
            {"id", "population_weight", "service_priority_weights"},
            "urban population group",
        )
        if not isinstance(payload["service_priority_weights"], dict):
            raise ValueError("service priority weights must be an object")
        return cls(
            id=payload["id"],
            population_weight=payload["population_weight"],
            service_priority_weights=tuple(payload["service_priority_weights"].items()),
        )


@dataclass(frozen=True)
class CityGovernance:
    """Current administrative capacity and optional controller reference."""

    controller_kind: str
    controller_id: str
    administrative_capacity: float

    def __post_init__(self) -> None:
        _require_string(self.controller_kind, "governance controller_kind", allow_empty=True)
        _require_string(self.controller_id, "governance controller_id", allow_empty=True)
        if bool(self.controller_kind) != bool(self.controller_id):
            raise ValueError("governance controller kind and id must be provided together")
        object.__setattr__(
            self,
            "administrative_capacity",
            _finite_nonnegative(self.administrative_capacity, "administrative capacity"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "controller_kind": self.controller_kind,
            "controller_id": self.controller_id,
            "administrative_capacity": self.administrative_capacity,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CityGovernance":
        payload = _require_mapping(data, "governance")
        _strict_keys(payload, {"controller_kind", "controller_id", "administrative_capacity"}, "governance")
        return cls(
            controller_kind=payload["controller_kind"],
            controller_id=payload["controller_id"],
            administrative_capacity=payload["administrative_capacity"],
        )


@dataclass
class CityState:
    """Durable urban substrate owned by one city region."""

    districts: tuple[CityDistrict, ...] = field(default_factory=tuple)
    assets: tuple[UrbanAsset, ...] = field(default_factory=tuple)
    service_demands: tuple[UrbanServiceDemand, ...] = field(default_factory=tuple)
    population_groups: tuple[UrbanPopulationGroup, ...] = field(default_factory=tuple)
    governance: CityGovernance = field(default_factory=lambda: CityGovernance("", "", 0.0))
    capacity_projects: tuple[UrbanCapacityProject, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.districts = tuple(self.districts)
        self.assets = tuple(self.assets)
        self.service_demands = tuple(self.service_demands)
        self.population_groups = tuple(self.population_groups)
        self.capacity_projects = tuple(self.capacity_projects)
        if not isinstance(self.governance, CityGovernance):
            raise TypeError("governance must be a CityGovernance")
        if any(not isinstance(project, UrbanCapacityProject) for project in self.capacity_projects):
            raise TypeError("capacity_projects must contain UrbanCapacityProject values")
        if any(not isinstance(item, UrbanServiceDemand) for item in self.service_demands):
            raise TypeError("service_demands must contain UrbanServiceDemand values")
        if any(not isinstance(item, UrbanPopulationGroup) for item in self.population_groups):
            raise TypeError("population_groups must contain UrbanPopulationGroup values")

    def validate(self, city_tiles: Iterable[Coordinate] | None = None) -> None:
        if any(not isinstance(district, CityDistrict) for district in self.districts):
            raise TypeError("districts must contain CityDistrict values")
        if any(not isinstance(asset, UrbanAsset) for asset in self.assets):
            raise TypeError("assets must contain UrbanAsset values")
        if not self.districts:
            raise ValueError("city must have at least one district")
        district_ids = [district.id for district in self.districts]
        if len(set(district_ids)) != len(district_ids):
            raise ValueError("district ids must be unique")
        asset_ids = [asset.id for asset in self.assets]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("asset ids must be unique")
        service_ids = [item.capability_id for item in self.service_demands]
        if len(set(service_ids)) != len(service_ids):
            raise ValueError("urban service capability ids must be unique")
        group_ids = [item.id for item in self.population_groups]
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("urban population group ids must be unique")
        if self.population_groups and not math.isclose(
            sum(item.population_weight for item in self.population_groups),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("urban population group weights must sum to 1")
        declared_services = set(service_ids)
        for group in self.population_groups:
            unknown_priorities = {
                capability_id
                for capability_id, _ in group.service_priority_weights
                if capability_id not in declared_services
            }
            if unknown_priorities:
                raise ValueError("service priority must reference a declared urban service")
        weights = sum(district.population_weight for district in self.districts)
        if not math.isclose(weights, 1.0, abs_tol=1e-9):
            raise ValueError("district population weights must sum to 1")

        owned_tiles: set[Coordinate] = set()
        for district in self.districts:
            overlap = owned_tiles.intersection(district.tile_refs)
            if overlap:
                raise ValueError("district tile ownership overlap")
            owned_tiles.update(district.tile_refs)

        if city_tiles is not None:
            expected_tiles = {_coordinate(tile, "city tiles") for tile in city_tiles}
            if owned_tiles != expected_tiles:
                raise ValueError("district tile ownership must cover the city exactly")

        district_id_set = set(district_ids)
        for asset in self.assets:
            if asset.district_id not in district_id_set:
                raise ValueError("asset district reference is invalid")

        project_ids = [project.id for project in self.capacity_projects]
        if len(set(project_ids)) != len(project_ids):
            raise ValueError("capacity project ids must be unique")
        asset_id_set = set(asset_ids)
        if any(project.housing_asset_id not in asset_id_set for project in self.capacity_projects):
            raise ValueError("capacity project housing asset reference is invalid")
        if any(project.construction_work_asset_id not in asset_id_set for project in self.capacity_projects):
            raise ValueError("capacity project construction work asset reference is invalid")
        active_kinds = [
            project.kind
            for project in self.capacity_projects
            if project.status.value != "completed"
        ]
        if len(set(active_kinds)) != len(active_kinds):
            raise ValueError("at most one active capacity projects of each kind is allowed")

    def district_population(self, district_id: str, city_population: float) -> float:
        population = _finite_nonnegative(city_population, "city population")
        for district in self.districts:
            if district.id == district_id:
                return population * district.population_weight
        raise KeyError(district_id)

    def service_demand_for(self, capability_id: str) -> UrbanServiceDemand | None:
        return next(
            (
                demand
                for demand in self.service_demands
                if demand.capability_id == capability_id
            ),
            None,
        )

    def effective_service_capacity(self, capability_id: str) -> float:
        """Return usable capacity without creating a second asset state."""
        return float(sum(
            asset.capacity * asset.quality * asset.integrity
            for asset in self.assets
            if capability_id in asset.capability_ids
        ))

    def service_access(self, capability_id: str, city_population: float) -> float | None:
        """Measure satisfied declared demand for one aggregate city service."""
        demand = self.service_demand_for(capability_id)
        if demand is None:
            return None
        load = _finite_nonnegative(city_population, "city population") * demand.demand_per_population
        if load == 0:
            return 1.0
        return min(1.0, self.effective_service_capacity(capability_id) / load)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "districts": [district.to_dict() for district in self.districts],
            "assets": [asset.to_dict() for asset in self.assets],
            "service_demands": [item.to_dict() for item in self.service_demands],
            "population_groups": [item.to_dict() for item in self.population_groups],
            "governance": self.governance.to_dict(),
            "capacity_projects": [project.to_dict() for project in self.capacity_projects],
        }

    @classmethod
    def from_dict(
        cls,
        data: Any,
        *,
        city_tiles: Iterable[Coordinate] | None = None,
    ) -> "CityState":
        payload = _require_mapping(data, "city state")
        _strict_keys(
            payload,
            {
                "districts",
                "assets",
                "service_demands",
                "population_groups",
                "governance",
                "capacity_projects",
            },
            "city state",
        )
        if (
            not isinstance(payload["districts"], list)
            or not isinstance(payload["assets"], list)
            or not isinstance(payload["service_demands"], list)
            or not isinstance(payload["population_groups"], list)
            or not isinstance(payload["capacity_projects"], list)
        ):
            raise ValueError("city state collections must be lists")
        state = cls(
            districts=tuple(CityDistrict.from_dict(item) for item in payload["districts"]),
            assets=tuple(UrbanAsset.from_dict(item) for item in payload["assets"]),
            service_demands=tuple(
                UrbanServiceDemand.from_dict(item) for item in payload["service_demands"]
            ),
            population_groups=tuple(
                UrbanPopulationGroup.from_dict(item) for item in payload["population_groups"]
            ),
            governance=CityGovernance.from_dict(payload["governance"]),
            capacity_projects=tuple(
                UrbanCapacityProject.from_dict(item) for item in payload["capacity_projects"]
            ),
        )
        state.validate(city_tiles)
        return state

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str, *, city_tiles: Iterable[Coordinate] | None = None) -> "CityState":
        if not isinstance(value, str):
            raise ValueError("city state JSON must be a string")
        return cls.from_dict(json.loads(value), city_tiles=city_tiles)

    @classmethod
    def default_for_region(cls, city_tiles: Iterable[Coordinate]) -> "CityState":
        tiles = tuple(_coordinate(tile, "city tiles") for tile in city_tiles)
        return cls(
            districts=(CityDistrict("urban_core", "core", tiles, 1.0),),
            governance=CityGovernance("", "", 0.0),
        )

    @classmethod
    def from_profile_dict(
        cls,
        data: Any,
        *,
        city_tiles: Iterable[Coordinate],
    ) -> "CityState":
        payload = _require_mapping(data, "urban profile")
        _strict_keys(payload, {"districts", "assets", "governance"}, "urban profile")
        if not isinstance(payload["districts"], list) or len(payload["districts"]) != 1:
            raise ValueError("urban profile must contain exactly one map-independent district")
        district_profile = _require_mapping(payload["districts"][0], "urban profile district")
        _strict_keys(district_profile, {"id", "kind", "population_weight"}, "urban profile district")
        tiles = tuple(_coordinate(tile, "city tiles") for tile in city_tiles)
        district = CityDistrict(
            id=district_profile["id"],
            kind=district_profile["kind"],
            tile_refs=tiles,
            population_weight=district_profile["population_weight"],
        )
        if not isinstance(payload["assets"], list):
            raise ValueError("urban profile assets must be a list")
        state = cls(
            districts=(district,),
            assets=tuple(UrbanAsset.from_dict(item) for item in payload["assets"]),
            governance=CityGovernance.from_dict(payload["governance"]),
        )
        state.validate(tiles)
        return state
