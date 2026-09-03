from __future__ import annotations

import copy

import pytest

from src.classes.core.world import World
from src.classes.environment.geography import GeographyLayer, WaterBody, WaterBodyKind
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion, NormalRegion
from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationReason,
    DomainInvalidationQueue,
)
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.run.load_map import load_cultivation_world_map
from src.classes.environment.climate import ClimateState
from src.systems.regional_climate import advance_regional_climate
from src.systems.time import MonthStamp


def _world_with_geography(*, month: int = 14, playthrough_id: str = "climate-seed") -> World:
    game_map = Map(width=4, height=2)
    for y in range(2):
        for x in range(4):
            game_map.create_tile(x, y, game_map.get_terrain(x, y))

    game_map.set_geography(
        GeographyLayer(
            width=4,
            height=2,
            terrain_rows=[
                ["plain", "marsh", "plain", "plain"],
                ["plain", "plain", "water", "plain"],
            ],
            elevation_rows=[
                [110.0, 25.0, 90.0, 140.0],
                [100.0, 40.0, 0.0, 130.0],
            ],
            water_bodies=[
                WaterBody(
                    id="river:climate-test",
                    kind=WaterBodyKind.RIVER,
                    cell_refs=((1, 0), (2, 1)),
                    navigable=False,
                    region_id=1,
                    flow_direction=(1, 1),
                )
            ],
        )
    )
    city = CityRegion(
        id=1,
        name="Lowland City",
        desc="",
        cors=[(1, 0), (2, 1)],
        population=100.0,
        population_capacity=120.0,
    )
    upland = NormalRegion(id=2, name="Upland", desc="", cors=[(0, 0), (3, 1)])
    game_map.regions = {city.id: city, upland.id: upland}
    game_map.region_cors = {city.id: list(city.cors), upland.id: list(upland.cors)}
    for region in game_map.regions.values():
        for coordinate in region.cors:
            if coordinate in game_map.tiles:
                game_map.tiles[coordinate].region = region

    return World(
        map=game_map,
        month_stamp=MonthStamp(month),
        start_year=0,
        playthrough_id=playthrough_id,
        climate_state=ClimateState(),
    )


def _run(world: World) -> tuple[list, DomainInvalidationQueue]:
    invalidations = DomainInvalidationQueue()
    events = advance_regional_climate(world, invalidations=invalidations)
    return events, invalidations


def _event_signature(event) -> tuple:
    """Compare deterministic climate evidence without UUID/timestamp identity."""
    return (
        int(event.month_stamp),
        event.content,
        event.event_type,
        str(event.fact_kind),
        str(event.causal_origin),
        event.render_key,
        event.render_params,
        tuple(
            sorted(
                (
                    delta["owner_kind"],
                    delta["owner_id"],
                    delta["aspect"],
                    delta["before"],
                    delta["after"],
                    delta["magnitude"],
                )
                for delta in event.causal_payload["deltas"]
            )
        ),
    )


def test_monthly_climate_is_deterministic_and_bounded_for_every_region():
    first = _world_with_geography()
    second = _world_with_geography()

    first_events, _ = _run(first)
    second_events, _ = _run(second)

    assert first.climate_state.to_dict() == second.climate_state.to_dict()
    assert [_event_signature(event) for event in first_events] == [
        _event_signature(event) for event in second_events
    ]
    assert set(first.climate_state.regions) == {"1", "2"}
    for reading in first.climate_state.regions.values():
        assert 0.0 <= reading.precipitation <= 1.0
        assert 0.0 <= reading.soil_saturation <= 1.0


def test_next_month_uses_previous_soil_saturation_without_replacing_climate_state():
    world = _world_with_geography(month=14)
    _run(world)
    previous = copy.deepcopy(world.climate_state.regions)

    world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
    _run(world)

    for region_id, current in world.climate_state.regions.items():
        assert current.previous_soil_saturation == pytest.approx(
            previous[region_id].soil_saturation
        )
        assert 0.0 <= current.soil_saturation <= 1.0


def test_climate_event_contains_state_deltas_and_mechanical_region_invalidations():
    world = _world_with_geography()
    invalidations = DomainInvalidationQueue()

    events = advance_regional_climate(world, invalidations=invalidations)

    assert len(events) == 1
    event = events[0]
    assert event.fact_kind is FactKind.STATE_TRANSITION
    assert event.causal_origin.value == "deterministic"
    assert event.event_type == "regional_climate_updated"
    assert event.render_params["region_ids"] == ["1", "2"]

    deltas = [StateDelta.from_dict(raw) for raw in event.causal_payload["deltas"]]
    assert {delta.owner_kind for delta in deltas} == {"climate"}
    assert {delta.owner_id for delta in deltas} == {"1", "2"}
    assert {delta.aspect for delta in deltas} == {
        "precipitation",
        "soil_saturation",
    }
    assert all(delta.event_id == event.id for delta in deltas)

    pending = invalidations.drain(layer=DomainInvalidationLayer.MECHANICAL)
    assert {
        (item.domain, item.target_kind, item.target_id, item.reason)
        for item in pending
    } == {
        ("region", "region", "1", DomainInvalidationReason.CLIMATE_CHANGED),
        ("region", "region", "2", DomainInvalidationReason.CLIMATE_CHANGED),
    }
    assert all(item.source_event_ids for item in pending)

    assert advance_regional_climate(world, invalidations=invalidations) == []


def test_climate_only_changes_its_canonical_state_and_does_not_mutate_other_domains():
    world = _world_with_geography()
    before_population = {
        region_id: region.population
        for region_id, region in world.map.regions.items()
        if isinstance(region, CityRegion)
    }
    before_economy = {
        region_id: copy.deepcopy(region.economy.to_dict())
        for region_id, region in world.map.regions.items()
        if isinstance(region, CityRegion)
    }
    before_sites = copy.deepcopy(world.map.infrastructure_sites)
    before_routes = copy.deepcopy(world.map.routes)

    _run(world)

    assert {
        region_id: region.population
        for region_id, region in world.map.regions.items()
        if isinstance(region, CityRegion)
    } == before_population
    assert {
        region_id: region.economy.to_dict()
        for region_id, region in world.map.regions.items()
        if isinstance(region, CityRegion)
    } == before_economy
    assert world.map.infrastructure_sites == before_sites
    assert world.map.routes == before_routes


def test_climate_state_round_trips_through_json_primitives():
    world = _world_with_geography()
    _run(world)

    encoded = world.climate_state.to_dict()
    restored = ClimateState.from_dict(encoded)

    assert restored.to_dict() == encoded
    assert restored is not world.climate_state
    assert restored.regions is not world.climate_state.regions


def test_climate_state_survives_world_save_and_load(tmp_path):
    world = World(
        map=load_cultivation_world_map("classic"),
        month_stamp=MonthStamp(14),
        playthrough_id="climate-save-load",
    )
    _run(world)
    world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
        "test_mode": True,
    }
    save_path = tmp_path / "climate.json"

    success, message = save_game(
        world,
        Simulator(world),
        [],
        save_path=save_path,
    )

    assert success, message
    loaded_world, _, _ = load_game(save_path)
    assert loaded_world.climate_state.to_dict() == world.climate_state.to_dict()


def test_month_checkpoint_restores_climate_state_after_failed_step():
    world = _world_with_geography()
    before = world.climate_state.to_dict()
    checkpoint = SimulationMonthCheckpoint.capture(world)

    _run(world)
    assert world.climate_state.to_dict() != before

    checkpoint.restore()
    assert world.climate_state.to_dict() == before
