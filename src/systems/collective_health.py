"""Grounded, read-only collective health projections.

The projection deliberately has a narrow H1 contract.  It observes living
avatars that are actually attached to the requested region, their existing
V1 individual consequence state, and explicit healing urban assets.
It does not create a population health state, infer disease, or mutate the
world while building a view.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.classes.environment.city_state import UrbanAsset
from src.classes.individual_consequence import IndividualConsequenceState
from src.classes.mechanical_language import MeasurementAvailability, ReadingKind


def _sorted_unique(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    try:
        return tuple(sorted({str(value) for value in values if value is not None and str(value)}))
    except TypeError:
        return (str(values),) if str(values) else ()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


@dataclass(frozen=True, slots=True)
class HealthReading:
    """One immutable measurement in a collective-health view."""

    value: int | float | None
    unit: str
    availability: MeasurementAvailability
    reading_kind: ReadingKind
    state_refs: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str) or not self.unit:
            raise ValueError("health reading unit must be non-empty")
        if self.value is not None:
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise ValueError("health reading values must be numeric")
            if not math.isfinite(float(self.value)) or self.value < 0:
                raise ValueError("health reading values must be finite and nonnegative")
        if self.reading_kind is ReadingKind.UNKNOWN and self.value is not None:
            raise ValueError("unknown health readings cannot carry a value")
        if self.reading_kind is not ReadingKind.UNKNOWN and self.value is None:
            raise ValueError("known health readings require a value")
        object.__setattr__(self, "state_refs", _sorted_unique(self.state_refs))
        object.__setattr__(self, "source_event_ids", _sorted_unique(self.source_event_ids))

    @property
    def kind(self) -> ReadingKind:
        """Short alias used by read-model consumers."""
        return self.reading_kind

    @property
    def is_unknown(self) -> bool:
        return self.reading_kind is ReadingKind.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "availability": _enum_value(self.availability),
            "reading_kind": _enum_value(self.reading_kind),
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HealthReading":
        return cls(
            value=data.get("value"),
            unit=str(data["unit"]),
            availability=MeasurementAvailability(str(data["availability"])),
            reading_kind=ReadingKind(str(data["reading_kind"])),
            state_refs=tuple(str(item) for item in data.get("state_refs", ())),
            source_event_ids=tuple(str(item) for item in data.get("source_event_ids", ())),
        )


@dataclass(frozen=True, slots=True)
class InjuryObservation:
    """An active V1 injury belonging to one included living avatar."""

    avatar_id: str
    severity: str
    hp_lost: int
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.avatar_id:
            raise ValueError("injury observations require an avatar id")
        if self.hp_lost < 0:
            raise ValueError("injury hp_lost must be nonnegative")
        object.__setattr__(self, "state_refs", _sorted_unique(self.state_refs))
        object.__setattr__(self, "source_event_ids", _sorted_unique(self.source_event_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "avatar_id": self.avatar_id,
            "severity": self.severity,
            "hp_lost": self.hp_lost,
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InjuryObservation":
        return cls(
            avatar_id=str(data["avatar_id"]),
            severity=str(data["severity"]),
            hp_lost=int(data["hp_lost"]),
            state_refs=tuple(str(item) for item in data.get("state_refs", ())),
            source_event_ids=tuple(str(item) for item in data.get("source_event_ids", ())),
        )


@dataclass(frozen=True, slots=True)
class HealingAssetObservation:
    """Usable capacity from an explicit healing urban asset."""

    asset_id: str
    capability_ids: tuple[str, ...]
    capacity: float
    state_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("healing asset observations require an asset id")
        if self.capacity < 0 or not math.isfinite(float(self.capacity)):
            raise ValueError("healing asset capacity must be finite and nonnegative")
        object.__setattr__(self, "capability_ids", _sorted_unique(self.capability_ids))
        object.__setattr__(self, "state_refs", _sorted_unique(self.state_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "capability_ids": list(self.capability_ids),
            "capacity": self.capacity,
            "state_refs": list(self.state_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HealingAssetObservation":
        return cls(
            asset_id=str(data["asset_id"]),
            capability_ids=tuple(str(item) for item in data.get("capability_ids", ())),
            capacity=float(data["capacity"]),
            state_refs=tuple(str(item) for item in data.get("state_refs", ())),
        )


@dataclass(frozen=True, slots=True)
class CollectiveHealthView:
    """Immutable collective-health read model for one region."""

    region_id: int
    grounding_status: str
    living_avatar_count: HealthReading
    active_wounded_count: HealthReading
    hp_deficit: HealthReading
    healing_capacity: HealthReading
    healing_access: HealthReading
    injuries: tuple[InjuryObservation, ...] = ()
    healing_assets: tuple[HealingAssetObservation, ...] = ()
    state_refs: tuple[str, ...] = ()
    source_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.grounding_status not in {"grounded", "unknown"}:
            raise ValueError("collective health grounding_status must be grounded or unknown")
        object.__setattr__(self, "injuries", tuple(self.injuries))
        object.__setattr__(self, "healing_assets", tuple(self.healing_assets))
        object.__setattr__(self, "state_refs", _sorted_unique(self.state_refs))
        object.__setattr__(self, "source_event_ids", _sorted_unique(self.source_event_ids))

    @property
    def grounded(self) -> bool:
        return self.grounding_status == "grounded"

    @property
    def status(self) -> str:
        return self.grounding_status

    @property
    def living_avatars(self) -> HealthReading:
        return self.living_avatar_count

    @property
    def active_wounded(self) -> HealthReading:
        return self.active_wounded_count

    @property
    def wounded_count(self) -> HealthReading:
        return self.active_wounded_count

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible data in a stable key and collection order."""
        return {
            "schema_version": 1,
            "region_id": self.region_id,
            "grounding_status": self.grounding_status,
            "grounded": self.grounded,
            "living_avatar_count": self.living_avatar_count.to_dict(),
            "active_wounded_count": self.active_wounded_count.to_dict(),
            "hp_deficit": self.hp_deficit.to_dict(),
            "healing_capacity": self.healing_capacity.to_dict(),
            "healing_access": self.healing_access.to_dict(),
            "injuries": [item.to_dict() for item in self.injuries],
            "healing_assets": [item.to_dict() for item in self.healing_assets],
            "state_refs": list(self.state_refs),
            "source_event_ids": list(self.source_event_ids),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CollectiveHealthView":
        return cls(
            region_id=int(data["region_id"]),
            grounding_status=str(data["grounding_status"]),
            living_avatar_count=HealthReading.from_dict(data["living_avatar_count"]),
            active_wounded_count=HealthReading.from_dict(data["active_wounded_count"]),
            hp_deficit=HealthReading.from_dict(data["hp_deficit"]),
            healing_capacity=HealthReading.from_dict(data["healing_capacity"]),
            healing_access=HealthReading.from_dict(data["healing_access"]),
            injuries=tuple(InjuryObservation.from_dict(item) for item in data.get("injuries", ())),
            healing_assets=tuple(
                HealingAssetObservation.from_dict(item)
                for item in data.get("healing_assets", ())
            ),
            state_refs=tuple(str(item) for item in data.get("state_refs", ())),
            source_event_ids=tuple(str(item) for item in data.get("source_event_ids", ())),
        )


def _region_for_id(world: Any, region_id: int | str) -> tuple[int, Any | None]:
    try:
        normalized_id = int(region_id)
    except (TypeError, ValueError):
        return -1, None
    game_map = getattr(world, "map", None)
    regions = getattr(game_map, "regions", None)
    if not isinstance(regions, Mapping):
        return normalized_id, None
    return normalized_id, regions.get(normalized_id, regions.get(str(normalized_id)))


def _avatars_in_region(world: Any, region: Any) -> tuple[tuple[Any, ...], bool]:
    manager = getattr(world, "avatar_manager", None)
    avatars = getattr(manager, "avatars", None)
    if not isinstance(avatars, Mapping):
        return (), False
    included: list[Any] = []
    region_id = str(getattr(region, "id", ""))
    for avatar in avatars.values():
        if getattr(avatar, "is_dead", False):
            continue
        tile = getattr(avatar, "tile", None)
        located_region = getattr(tile, "region", None) if tile is not None else None
        if located_region is not region and str(getattr(located_region, "id", "")) != region_id:
            continue
        included.append(avatar)
    included.sort(key=lambda avatar: str(getattr(avatar, "id", "")))
    return tuple(included), True


def _unknown_reading(unit: str, state_refs: tuple[str, ...] = ()) -> HealthReading:
    return HealthReading(
        value=None,
        unit=unit,
        availability=MeasurementAvailability.UNMEASURABLE,
        reading_kind=ReadingKind.UNKNOWN,
        state_refs=state_refs,
    )


def _known_reading(
    value: int | float,
    unit: str,
    reading_kind: ReadingKind,
    *,
    state_refs: Any = (),
    source_event_ids: Any = (),
) -> HealthReading:
    return HealthReading(
        value=value,
        unit=unit,
        availability=MeasurementAvailability.MEASURABLE,
        reading_kind=reading_kind,
        state_refs=_sorted_unique(state_refs),
        source_event_ids=_sorted_unique(source_event_ids),
    )


def _healing_assets(region: Any, region_id: int) -> tuple[tuple[HealingAssetObservation, ...], bool]:
    city_state = getattr(region, "city_state", None)
    assets = getattr(city_state, "assets", None)
    if not isinstance(assets, (list, tuple)):
        return (), False
    observations: list[HealingAssetObservation] = []
    for asset in assets:
        if not isinstance(asset, UrbanAsset):
            continue
        capabilities = tuple(
            sorted(
                {
                    str(capability)
                    for capability in asset.capability_ids
                    if str(capability) == "healing"
                }
            )
        )
        if not capabilities:
            continue
        observations.append(
            HealingAssetObservation(
                asset_id=str(asset.id),
                capability_ids=capabilities,
                capacity=float(asset.capacity * asset.quality * asset.integrity),
                state_refs=(
                    f"region:{region_id}:urban_asset:{asset.id}:capacity_quality_integrity",
                ),
            )
        )
    observations.sort(key=lambda item: item.asset_id)
    return tuple(observations), True


def _empty_view(region_id: int) -> CollectiveHealthView:
    unknown = _unknown_reading("unknown")
    return CollectiveHealthView(
        region_id=region_id,
        grounding_status="unknown",
        living_avatar_count=unknown,
        active_wounded_count=unknown,
        hp_deficit=unknown,
        healing_capacity=unknown,
        healing_access=unknown,
    )


def project_collective_health(world: Any, region_id: int | str) -> CollectiveHealthView:
    """Project grounded collective-health facts for ``region_id``.

    Living membership is based on the canonical avatar manager and the
    avatar's current tile-region relation.  Dead, detached, or merely
    historical avatars are never included.
    """
    normalized_id, region = _region_for_id(world, region_id)
    if region is None:
        return _empty_view(normalized_id)

    avatars, population_grounded = _avatars_in_region(world, region)
    region_ref = f"region:{normalized_id}"
    avatar_refs = [
        ref
        for avatar in avatars
        for ref in (
            f"avatar:{avatar.id}:location",
            f"avatar:{avatar.id}:life",
        )
    ]
    living_count = (
        _known_reading(
            len(avatars),
            "avatars",
            ReadingKind.EXACT,
            state_refs=(region_ref, f"{region_ref}:living_avatars", *avatar_refs),
        )
        if population_grounded
        else _unknown_reading("avatars", (region_ref,))
    )

    injuries: list[InjuryObservation] = []
    hp_deficit_value = 0
    hp_grounded = population_grounded
    for avatar in avatars:
        hp = getattr(avatar, "hp", None)
        current = getattr(hp, "cur", None)
        maximum = getattr(hp, "max", None)
        if (
            isinstance(current, bool)
            or isinstance(maximum, bool)
            or not isinstance(current, (int, float))
            or not isinstance(maximum, (int, float))
        ):
            hp_grounded = False
        else:
            hp_deficit_value += max(0, int(maximum) - int(current))

        consequence = getattr(avatar, "individual_consequences", None)
        if not isinstance(consequence, IndividualConsequenceState):
            continue
        injury = consequence.active_injury
        if injury is None:
            continue
        cause_ids = _sorted_unique(injury.cause_event_ids)
        injuries.append(
            InjuryObservation(
                avatar_id=str(avatar.id),
                severity=str(injury.severity),
                hp_lost=int(injury.hp_lost),
                state_refs=(
                    f"avatar:{avatar.id}:individual_consequences:active_injury",
                    f"avatar:{avatar.id}:hp",
                ),
                source_event_ids=cause_ids,
            )
        )
    injuries.sort(key=lambda item: item.avatar_id)

    injury_refs = [ref for injury in injuries for ref in injury.state_refs]
    injury_event_ids = [event_id for injury in injuries for event_id in injury.source_event_ids]
    active_wounded = _known_reading(
        len(injuries),
        "avatars",
        ReadingKind.DERIVED,
        state_refs=(region_ref, *injury_refs),
        source_event_ids=injury_event_ids,
    ) if population_grounded else _unknown_reading("avatars", (region_ref,))
    hp_deficit = (
        _known_reading(
            hp_deficit_value,
            "hp",
            ReadingKind.DERIVED,
            state_refs=(region_ref, *(f"avatar:{avatar.id}:hp" for avatar in avatars)),
            source_event_ids=injury_event_ids,
        )
        if hp_grounded
        else _unknown_reading("hp", (region_ref,))
    )

    healing_assets, assets_grounded = _healing_assets(region, normalized_id)
    healing_demand = getattr(region, "city_state", None)
    healing_demand = (
        healing_demand.service_demand_for("healing")
        if healing_demand is not None
        else None
    )
    healing_capacity = (
        _known_reading(
            sum(asset.capacity for asset in healing_assets),
            "capacity_units",
            ReadingKind.DERIVED,
            state_refs=(region_ref, *(ref for asset in healing_assets for ref in asset.state_refs)),
        )
        if assets_grounded and (healing_assets or healing_demand is not None)
        else _unknown_reading("capacity_units", (region_ref,))
    )
    access_value = (
        region.city_state.service_access("healing", float(region.population))
        if healing_demand is not None
        else None
    )
    healing_access = (
        _known_reading(
            access_value,
            "ratio",
            ReadingKind.DERIVED,
            state_refs=(
                region_ref,
                f"{region_ref}:population",
                f"{region_ref}:urban_service_demand:healing",
                *(ref for asset in healing_assets for ref in asset.state_refs),
            ),
        )
        if access_value is not None
        else _unknown_reading("ratio", (region_ref,))
    )

    readings = (
        living_count,
        active_wounded,
        hp_deficit,
        healing_capacity,
        healing_access,
    )
    return CollectiveHealthView(
        region_id=normalized_id,
        grounding_status="grounded" if any(not reading.is_unknown for reading in readings) else "unknown",
        living_avatar_count=living_count,
        active_wounded_count=active_wounded,
        hp_deficit=hp_deficit,
        healing_capacity=healing_capacity,
        healing_access=healing_access,
        injuries=tuple(injuries),
        healing_assets=healing_assets,
        state_refs=_sorted_unique((ref for reading in readings for ref in reading.state_refs)),
        source_event_ids=_sorted_unique(
            event_id for reading in readings for event_id in reading.source_event_ids
        ),
    )


build_collective_health_view = project_collective_health
get_collective_health_view = project_collective_health


__all__ = [
    "CollectiveHealthView",
    "HealthReading",
    "HealingAssetObservation",
    "InjuryObservation",
    "build_collective_health_view",
    "get_collective_health_view",
    "project_collective_health",
]
