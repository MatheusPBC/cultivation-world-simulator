"""Read-only regional hydrology derived from weather and physical geography."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.classes.environment.tile import TileType


PRECIPITATION_CONCEPT = "precipitation"
SOIL_WATER_CONCEPT = "soil_water"
DRAINAGE_CONCEPT = "drainage"
FLOODING_CONCEPT = "flooding"
CLIMATE_QUALIFIERS = (("kind", "regional_climate"),)
HYDROLOGY_QUALIFIERS = (("kind", "regional_hydrology"),)
WATER_MANAGEMENT_CAPABILITIES = frozenset(
    {"water_management", "drainage", "flood_control"}
)


_TERRAIN_DRAINAGE: dict[TileType, float] = {
    TileType.PLAIN: 0.52,
    TileType.WATER: 0.08,
    TileType.SEA: 0.10,
    TileType.MOUNTAIN: 0.78,
    TileType.FOREST: 0.58,
    TileType.DESERT: 0.70,
    TileType.RAINFOREST: 0.40,
    TileType.GLACIER: 0.24,
    TileType.SNOW_MOUNTAIN: 0.60,
    TileType.VOLCANO: 0.74,
    TileType.GRASSLAND: 0.56,
    TileType.SWAMP: 0.10,
    TileType.FARM: 0.44,
    TileType.ISLAND: 0.48,
    TileType.BAMBOO: 0.54,
    TileType.GOBI: 0.72,
    TileType.TUNDRA: 0.28,
    TileType.MARSH: 0.08,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True, slots=True)
class RegionalHydrologyProjection:
    region_id: str
    month: int
    precipitation: float
    soil_water: float
    drainage: float
    flooding: float
    state_refs: tuple[str, ...]
    source_event_ids: tuple[str, ...]


def _region_sites(world: Any, region_id: int) -> list[Any]:
    sites = getattr(world.map, "infrastructure_sites", {})
    if not isinstance(sites, dict):
        return []
    return sorted(
        (
            site
            for site in sites.values()
            if region_id in site.region_ids
            and WATER_MANAGEMENT_CAPABILITIES.intersection(site.capability_ids)
        ),
        key=lambda site: site.id,
    )


def project_regional_hydrology(
    world: Any,
    region_id: int | str,
) -> RegionalHydrologyProjection | None:
    """Project hydrology without creating a second physical state owner."""
    try:
        normalized_region_id = int(region_id)
    except (TypeError, ValueError):
        return None
    if world.map.regions.get(normalized_region_id) is None:
        return None
    climate_state = getattr(world, "climate_state", None)
    if climate_state is None:
        return None
    weather = climate_state.get(normalized_region_id, int(world.month_stamp))
    if weather is None:
        return None

    coordinates = world.map.get_region_coordinates(normalized_region_id)
    terrain_drainage: list[float] = []
    elevations: list[float] = []
    geography_refs: list[str] = []
    for x, y in sorted(coordinates):
        terrain = world.map.get_terrain(x, y)
        elevation = world.map.get_elevation(x, y)
        if terrain is not None:
            terrain_drainage.append(_TERRAIN_DRAINAGE.get(terrain, 0.50))
            geography_refs.append(f"map:geography:{x}:{y}:terrain")
        if elevation is not None:
            elevations.append(float(elevation))
            geography_refs.append(f"map:geography:{x}:{y}:elevation")

    base_drainage = (
        sum(terrain_drainage) / len(terrain_drainage)
        if terrain_drainage
        else 0.50
    )
    elevation_range = max(elevations) - min(elevations) if elevations else 0.0
    slope_drainage = min(0.18, elevation_range / 2_000.0)

    touching_water = world.map.get_water_bodies_touching_region(normalized_region_id)
    water_weight = {"river": 0.20, "lake": 0.13, "sea": 0.09}
    water_exposure = _clamp(
        sum(water_weight.get(body.kind.value, 0.05) for body in touching_water)
    )
    water_refs = [f"map:water_body:{body.id}" for body in touching_water]

    sites = _region_sites(world, normalized_region_id)
    site_bonus = min(
        0.38,
        sum(float(site.integrity) * 0.20 for site in sites if site.enabled),
    )
    site_refs = [
        ref
        for site in sites
        for ref in (
            f"map:infrastructure_site:{site.id}:enabled",
            f"map:infrastructure_site:{site.id}:integrity",
            *(
                f"map:infrastructure_site:{site.id}:capability:{capability_id}"
                for capability_id in site.capability_ids
                if capability_id in WATER_MANAGEMENT_CAPABILITIES
            ),
        )
    ]
    source_event_ids = tuple(
        dict.fromkeys(
            event_id
            for event_id in (
                weather.source_event_id,
                *(site.last_event_id for site in sites),
            )
            if event_id
        )
    )

    drainage = _clamp(base_drainage * 0.68 + slope_drainage + site_bonus)
    surface_load = _clamp(
        weather.precipitation * 0.56
        + weather.soil_saturation * 0.34
        + water_exposure
    )
    average_elevation = sum(elevations) / len(elevations) if elevations else 0.0
    all_elevations = [
        float(value)
        for row in world.map.geography.elevation_rows
        for value in row
    ]
    global_range = max(all_elevations) - min(all_elevations) if all_elevations else 0.0
    low_elevation = (
        1.0 - (average_elevation - min(all_elevations)) / global_range
        if global_range > 0
        else 0.5
    )
    flooding = _clamp(surface_load - drainage + _clamp(low_elevation) * 0.22)

    state_refs = tuple(
        dict.fromkeys(
            (
                f"climate:region:{normalized_region_id}:precipitation",
                f"climate:region:{normalized_region_id}:soil_saturation",
                *geography_refs,
                *water_refs,
                *site_refs,
            )
        )
    )
    return RegionalHydrologyProjection(
        region_id=str(normalized_region_id),
        month=int(world.month_stamp),
        precipitation=weather.precipitation,
        soil_water=weather.soil_saturation,
        drainage=drainage,
        flooding=flooding,
        state_refs=state_refs,
        source_event_ids=source_event_ids,
    )


__all__ = [
    "CLIMATE_QUALIFIERS",
    "DRAINAGE_CONCEPT",
    "FLOODING_CONCEPT",
    "HYDROLOGY_QUALIFIERS",
    "PRECIPITATION_CONCEPT",
    "RegionalHydrologyProjection",
    "SOIL_WATER_CONCEPT",
    "project_regional_hydrology",
]
