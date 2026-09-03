from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from src.classes.core.world import World
from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.climate import ClimateState, RegionalWeather
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.region import NormalRegion
from src.classes.environment.tile import TileType
from src.classes.mechanical_language import (
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
)
from src.systems.semantic_world.resolvers import available_metric_keys, resolve_metric
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.regional_hydrology import CLIMATE_QUALIFIERS, HYDROLOGY_QUALIFIERS
from src.systems.time import Month, Year, create_month_stamp


HYDROLOGY_CONCEPTS = {
    "precipitation": PrimitiveDimension.LOAD,
    "soil_water": PrimitiveDimension.LOAD,
    "drainage": PrimitiveDimension.CAPACITY,
    "flooding": PrimitiveDimension.RISK,
}


def _expression_concepts(node: object) -> set[str]:
    if isinstance(node, dict):
        own = {str(node["concept_id"])} if node.get("op") == "metric" else set()
        return own.union(*(_expression_concepts(value) for value in node.values()))
    if isinstance(node, list):
        return set().union(*(_expression_concepts(value) for value in node))
    return set()


def _world(*, precipitation_ratio: float | None, water_management_integrity: float = 0.0) -> World:
    game_map = Map(width=4, height=2)
    terrain_rows = [
        [TileType.PLAIN, TileType.PLAIN, TileType.WATER, TileType.PLAIN],
        [TileType.PLAIN, TileType.PLAIN, TileType.PLAIN, TileType.PLAIN],
    ]
    game_map.set_geography(
        GeographyLayer(
            width=4,
            height=2,
            terrain_rows=terrain_rows,
            elevation_rows=[[8.0, 2.0, 0.0, 6.0], [9.0, 3.0, 1.0, 7.0]],
            water_bodies=[
                WaterBody(
                    id="river:south",
                    kind="river",
                    cell_refs=((2, 0),),
                    navigable=False,
                    region_id=101,
                    flow_direction=(0, 1),
                )
            ],
        )
    )
    region = NormalRegion(
        id=101,
        name="Vale Baixo",
        desc="",
        cors=[(0, 0), (1, 0), (2, 0)],
    )
    game_map.regions = {region.id: region}
    game_map.region_cors = {region.id: list(region.cors)}
    game_map.set_infrastructure_sites(
        [
            InfrastructureSite(
                id="site:water-gate",
                kind="drainage_gate",
                name="Comporta do rio",
                cell_refs=((1, 0),),
                region_ids=(region.id,),
                capability_ids=("water_management",),
                integrity=water_management_integrity,
                enabled=water_management_integrity > 0.0,
                last_event_id="event:gate-maintained",
            )
        ]
    )
    world = World(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    )
    if precipitation_ratio is not None:
        month = int(world.month_stamp)
        world.climate_state = ClimateState(
            regions={
                str(region.id): RegionalWeather(
                    region_id=str(region.id),
                    month=month,
                    precipitation=precipitation_ratio,
                    soil_saturation=precipitation_ratio,
                    previous_soil_saturation=max(0.0, precipitation_ratio - 0.1),
                    source_event_id="event:heavy-rain",
                )
            },
            last_updated_month=month,
        )
    else:
        world.climate_state = ClimateState()
    return world


def _key(region: NormalRegion, dimension: PrimitiveDimension, concept: str) -> MetricKey:
    qualifiers = (
        CLIMATE_QUALIFIERS
        if concept in {"precipitation", "soil_water"}
        else HYDROLOGY_QUALIFIERS
    )
    return MetricKey(
        dimension,
        "region",
        str(region.id),
        concept,
        qualifiers=qualifiers,
    )


def _hydrology_readings(world: World, region: NormalRegion) -> dict[str, object]:
    return {
        concept: resolve_metric(world, _key(region, dimension, concept), target=region)
        for concept, dimension in HYDROLOGY_CONCEPTS.items()
    }


def test_hydrology_keys_are_enumerated_only_with_current_climate_reading() -> None:
    world = _world(precipitation_ratio=0.92)
    region = world.map.regions[101]

    keys = {
        (key.dimension, key.concept_id)
        for key in available_metric_keys(world, region)
        if key.concept_id in HYDROLOGY_CONCEPTS
    }

    assert keys == {
        (dimension, concept)
        for concept, dimension in HYDROLOGY_CONCEPTS.items()
    }

    world_without_reading = _world(precipitation_ratio=None)
    region_without_reading = world_without_reading.map.regions[101]
    assert not {
        key.concept_id
        for key in available_metric_keys(world_without_reading, region_without_reading)
        if key.concept_id in HYDROLOGY_CONCEPTS
    }


def test_hydrology_projection_is_ratio_valued_and_carries_provenance() -> None:
    world = _world(precipitation_ratio=0.92, water_management_integrity=0.25)
    region = world.map.regions[101]

    readings = _hydrology_readings(world, region)

    assert set(readings) == set(HYDROLOGY_CONCEPTS)
    for reading in readings.values():
        assert reading.unit == "ratio"
        assert 0.0 <= reading.value <= 1.0
        assert reading.availability is MeasurementAvailability.MEASURABLE
        expected_kind = (
            ReadingKind.EXACT
            if reading.key.concept_id in {"precipitation", "soil_water"}
            else ReadingKind.DERIVED
        )
        assert reading.reading_kind is expected_kind
        assert reading.state_refs
        assert reading.source_event_ids


def test_water_and_high_precipitation_increase_flood_exposure() -> None:
    dry_world = _world(precipitation_ratio=0.15)
    wet_world = _world(precipitation_ratio=0.95)
    dry_region = dry_world.map.regions[101]
    wet_region = wet_world.map.regions[101]

    dry = _hydrology_readings(dry_world, dry_region)
    wet = _hydrology_readings(wet_world, wet_region)

    assert wet["precipitation"].value > dry["precipitation"].value
    assert wet["soil_water"].value > dry["soil_water"].value
    assert wet["flooding"].value > dry["flooding"].value


def test_intact_water_management_increases_drainage_and_reduces_flooding() -> None:
    unmanaged_world = _world(precipitation_ratio=0.9, water_management_integrity=0.0)
    managed_world = _world(precipitation_ratio=0.9, water_management_integrity=1.0)
    unmanaged_region = unmanaged_world.map.regions[101]
    managed_region = managed_world.map.regions[101]

    unmanaged = _hydrology_readings(unmanaged_world, unmanaged_region)
    managed = _hydrology_readings(managed_world, managed_region)

    assert managed["drainage"].value > unmanaged["drainage"].value
    assert managed["flooding"].value < unmanaged["flooding"].value


def test_hydrology_projection_is_read_only_and_does_not_change_domain_owners() -> None:
    world = _world(precipitation_ratio=0.9, water_management_integrity=1.0)
    region = world.map.regions[101]
    map_before = {
        "terrain_rows": deepcopy(world.map.geography.terrain_rows),
        "elevation_rows": deepcopy(world.map.geography.elevation_rows),
        "water_bodies": deepcopy(world.map.geography.water_bodies),
        "routes": deepcopy(world.map.routes),
        "region_cors": deepcopy(world.map.region_cors),
    }
    region_before = region.to_runtime_dict()
    site_before = world.map.infrastructure_sites["site:water-gate"].to_dict()

    _hydrology_readings(world, region)

    assert world.map.geography.terrain_rows == map_before["terrain_rows"]
    assert world.map.geography.elevation_rows == map_before["elevation_rows"]
    assert world.map.geography.water_bodies == map_before["water_bodies"]
    assert world.map.routes == map_before["routes"]
    assert world.map.region_cors == map_before["region_cors"]
    assert region.to_runtime_dict() == region_before
    assert world.map.infrastructure_sites["site:water-gate"].to_dict() == site_before


def test_missing_climate_reading_is_unknown_when_requested_explicitly() -> None:
    world = _world(precipitation_ratio=None)
    region = world.map.regions[101]

    reading = resolve_metric(
        world,
        _key(region, PrimitiveDimension.RISK, "flooding"),
        target=region,
    )

    assert reading.value is None
    assert reading.availability is MeasurementAvailability.UNMEASURABLE
    assert reading.reading_kind is ReadingKind.UNKNOWN


@pytest.mark.asyncio
async def test_hydrology_surface_reaches_existing_semantic_discovery_in_test_mode() -> None:
    world = _world(precipitation_ratio=0.95, water_management_integrity=1.0)
    world.map.set_infrastructure_sites([])
    world.run_config_snapshot = {
        "test_mode": True,
        "semantic_discovery_budget_per_month": 1,
    }
    provider = AsyncMock(side_effect=AssertionError("real LLM must not be called"))

    await evaluate_semantic_world(world, llm_call=provider)

    assert provider.await_count == 0
    assert any(
        _expression_concepts(definition.expression).intersection(HYDROLOGY_CONCEPTS)
        for definition in world.mechanical_language.derived_definitions.values()
        if isinstance(definition.expression, dict)
    )
