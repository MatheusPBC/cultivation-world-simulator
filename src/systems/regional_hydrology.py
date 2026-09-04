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
_OPEN_WATER_TERRAINS = frozenset({TileType.WATER, TileType.SEA})


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
    climate_state_refs: tuple[str, ...]
    drainage_state_refs: tuple[str, ...]
    flooding_state_refs: tuple[str, ...]
    climate_source_event_ids: tuple[str, ...]
    drainage_source_event_ids: tuple[str, ...]

    @property
    def flooding_trigger_event_ids(self) -> tuple[str, ...]:
        """Weather observations that can causally trigger a flood."""
        return self.climate_source_event_ids

    @property
    def flooding_context_event_ids(self) -> tuple[str, ...]:
        """Infrastructure history that explains mitigation, not occurrence."""
        return self.drainage_source_event_ids


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


def region_has_floodable_land(world: Any, region_id: int) -> bool | None:
    """Whether a known regional footprint contains land a flood can occupy.

    Marsh and swamp remain floodable transitional land.  Missing footprint or
    terrain data is unknown (``None``), never invented as dry land.
    """
    coordinates = world.map.get_region_coordinates(region_id)
    if not coordinates:
        return None
    terrains = [world.map.get_terrain(x, y) for x, y in coordinates]
    if any(terrain is None for terrain in terrains):
        return None
    return any(terrain not in _OPEN_WATER_TERRAINS for terrain in terrains)


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
    floodable_land = region_has_floodable_land(world, normalized_region_id)
    if floodable_land is None:
        return None
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
    climate_source_event_ids = (
        (weather.source_event_id,) if weather.source_event_id else ()
    )
    drainage_source_event_ids = tuple(
        dict.fromkeys(site.last_event_id for site in sites if site.last_event_id)
    )

    drainage = _clamp(base_drainage * 0.68 + slope_drainage + site_bonus)
    # The normalized weighted rainfall/soil response keeps ordinary
    # humid/wetland weather below a disaster load while retaining severe,
    # near-saturated weather as a real trigger; it does not add a new state or
    # an arbitrary occurrence quota.
    weather_soil_load = _clamp(
        (weather.precipitation * 0.56 + weather.soil_saturation * 0.34) / 0.90
    )
    surface_load = 0.90 * weather_soil_load**1.5
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
    # Geography is susceptibility, not water arriving anew every month. Nearby
    # water and low elevation amplify that real weather/soil load, after which
    # drainage removes a bounded share.
    # Cap combined water adjacency so densely authored coast/river maps cannot
    # manufacture arbitrary monthly risk from static topology.
    water_susceptibility = min(0.25, water_exposure)
    susceptibility = (
        1.0 + water_susceptibility * 0.65 + _clamp(low_elevation) * 0.20
    )
    flooding = (
        _clamp(surface_load * susceptibility - drainage)
        if floodable_land
        else 0.0
    )

    climate_state_refs = (
        f"climate:region:{normalized_region_id}:precipitation",
        f"climate:region:{normalized_region_id}:soil_saturation",
    )
    drainage_state_refs = tuple(dict.fromkeys((*geography_refs, *site_refs)))
    # Low-elevation normalizes against the canonical map-wide elevation matrix.
    # A compact aggregate owner ref records that dependency without making every
    # regional reading enumerate the full map.
    flooding_state_refs = tuple(
        dict.fromkeys(
            (*climate_state_refs, *drainage_state_refs, *water_refs,
             "map:geography:elevation_rows")
        )
    )
    return RegionalHydrologyProjection(
        region_id=str(normalized_region_id),
        month=int(world.month_stamp),
        precipitation=weather.precipitation,
        soil_water=weather.soil_saturation,
        drainage=drainage,
        flooding=flooding,
        climate_state_refs=climate_state_refs,
        drainage_state_refs=drainage_state_refs,
        flooding_state_refs=flooding_state_refs,
        climate_source_event_ids=climate_source_event_ids,
        drainage_source_event_ids=drainage_source_event_ids,
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
    "region_has_floodable_land",
]
