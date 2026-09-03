"""Deterministic monthly regional weather over canonical physical geography."""

from __future__ import annotations

import hashlib
import math
import uuid
from typing import Any

from src.classes.causal_origin import CausalOrigin
from src.classes.environment.climate import RegionalWeather
from src.classes.environment.tile import TileType
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)


_TERRAIN_MOISTURE: dict[TileType, float] = {
    TileType.PLAIN: 0.48,
    TileType.WATER: 0.95,
    TileType.SEA: 0.88,
    TileType.MOUNTAIN: 0.42,
    TileType.FOREST: 0.66,
    TileType.DESERT: 0.12,
    TileType.RAINFOREST: 0.86,
    TileType.GLACIER: 0.46,
    TileType.SNOW_MOUNTAIN: 0.52,
    TileType.VOLCANO: 0.24,
    TileType.GRASSLAND: 0.44,
    TileType.SWAMP: 0.90,
    TileType.FARM: 0.54,
    TileType.ISLAND: 0.70,
    TileType.BAMBOO: 0.68,
    TileType.GOBI: 0.16,
    TileType.TUNDRA: 0.30,
    TileType.MARSH: 0.92,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _stable_fraction(*parts: object) -> float:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / float((1 << 64) - 1)


def _region_baseline(world: Any, region_id: int) -> tuple[float, float, float]:
    game_map = world.map
    coordinates = game_map.get_region_coordinates(region_id)
    terrain_values: list[float] = []
    elevations: list[float] = []
    for x, y in coordinates:
        terrain = game_map.get_terrain(x, y)
        elevation = game_map.get_elevation(x, y)
        if terrain is not None:
            terrain_values.append(_TERRAIN_MOISTURE.get(terrain, 0.45))
        if elevation is not None:
            elevations.append(float(elevation))
    moisture = sum(terrain_values) / len(terrain_values) if terrain_values else 0.45
    average_elevation = sum(elevations) / len(elevations) if elevations else 0.0
    water_bonus = min(
        0.14,
        0.045 * len(game_map.get_water_bodies_touching_region(region_id)),
    )
    orographic = min(0.08, max(0.0, average_elevation) / 30_000.0)
    average_y = (
        sum(y for _, y in coordinates) / len(coordinates)
        if coordinates
        else world.map.height / 2
    )
    latitude = average_y / max(1, world.map.height - 1)
    return _clamp(moisture + water_bonus + orographic), moisture, latitude


def _regional_weather(world: Any, region_id: int, month: int) -> RegionalWeather:
    baseline, retention, latitude = _region_baseline(world, region_id)
    phase = (latitude - 0.5) * 0.9
    seasonal = 0.13 * math.sin((month % 12) / 12.0 * math.tau + phase)
    shared_anomaly = (
        _stable_fraction(world.playthrough_id, month, "weather-front") - 0.5
    ) * 0.20
    local_anomaly = (
        _stable_fraction(world.playthrough_id, region_id, month, "rain") - 0.5
    ) * 0.08
    anomaly = shared_anomaly + local_anomaly
    precipitation = _clamp(baseline * 0.74 + seasonal + anomaly)

    previous = world.climate_state.get(region_id)
    previous_saturation = (
        previous.soil_saturation
        if previous is not None and previous.month < month
        else _clamp(retention * 0.55)
    )
    evaporation = 0.10 + max(0.0, seasonal) * 0.20
    soil_saturation = _clamp(
        previous_saturation * 0.58
        + precipitation * 0.48
        + retention * 0.10
        - evaporation
    )
    return RegionalWeather(
        region_id=str(region_id),
        month=month,
        precipitation=precipitation,
        soil_saturation=soil_saturation,
        previous_soil_saturation=previous_saturation,
    )


def advance_regional_climate(
    world: Any,
    *,
    invalidations: DomainInvalidationQueue,
) -> list[Event]:
    """Advance weather once for the current month and publish causal evidence."""
    month = int(world.month_stamp)
    state = world.climate_state
    if state.last_updated_month == month:
        return []

    region_ids = sorted(int(region_id) for region_id in world.map.regions)
    if not region_ids:
        state.last_updated_month = month
        return []

    new_weather = {
        str(region_id): _regional_weather(world, region_id, month)
        for region_id in region_ids
    }
    event_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"cultivation-world:{world.playthrough_id}:regional-climate:{month}",
        )
    )
    event = Event(
        month_stamp=world.month_stamp,
        content=t(
            "Regional weather changed across {count} regions.",
            count=len(region_ids),
        ),
        event_type="regional_climate_updated",
        render_key="regional_climate_updated",
        render_params={
            "count": len(region_ids),
            "region_ids": [str(region_id) for region_id in region_ids],
        },
        id=event_id,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
    )

    deltas: list[StateDelta] = []
    for region_id in region_ids:
        key = str(region_id)
        before = state.regions.get(key)
        weather = new_weather[key]
        weather = RegionalWeather(
            region_id=weather.region_id,
            month=weather.month,
            precipitation=weather.precipitation,
            soil_saturation=weather.soil_saturation,
            previous_soil_saturation=weather.previous_soil_saturation,
            source_event_id=event.id,
        )
        new_weather[key] = weather
        deltas.extend(
            (
                StateDelta(
                    event_id=event.id,
                    owner_kind="climate",
                    owner_id=key,
                    aspect="precipitation",
                    before=(str(before.precipitation) if before is not None else None),
                    after=str(weather.precipitation),
                    magnitude=(
                        weather.precipitation - before.precipitation
                        if before is not None
                        else weather.precipitation
                    ),
                ),
                StateDelta(
                    event_id=event.id,
                    owner_kind="climate",
                    owner_id=key,
                    aspect="soil_saturation",
                    before=(str(before.soil_saturation) if before is not None else None),
                    after=str(weather.soil_saturation),
                    magnitude=(
                        weather.soil_saturation - before.soil_saturation
                        if before is not None
                        else weather.soil_saturation
                    ),
                ),
            )
        )

    state.regions = new_weather
    state.last_updated_month = month
    event.causal_payload = {
        "outcome": "updated",
        "deltas": [delta.to_dict() for delta in deltas],
    }
    for region_id in region_ids:
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="region",
                target_kind="region",
                target_id=str(region_id),
                reason=DomainInvalidationReason.CLIMATE_CHANGED,
                source_event_ids=(event.id,),
                revision=f"climate:{region_id}:{month}",
            )
        )
    return [event]


__all__ = ["advance_regional_climate"]
