from __future__ import annotations

import copy

from src.classes.causal_link import CausalRelation
from src.classes.core.world import World
from src.classes.environment.climate import ClimateState, RegionalWeather
from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.map import Map
from src.classes.environment.region import CityRegion
from src.classes.environment.regional_flood import RegionalFloodOccurrence
from src.systems.regional_hydrology import RegionalHydrologyProjection
from src.classes.environment.tile import TileType
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationReason,
    DomainInvalidationQueue,
)
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.regional_floods import advance_regional_floods
from src.systems.semantic_world.context import build_region_semantic_context
from src.systems.time import MonthStamp


def _world() -> World:
    game_map = Map(width=3, height=2)
    game_map.set_geography(
        GeographyLayer(
            width=3,
            height=2,
            terrain_rows=[
                [TileType.PLAIN, TileType.WATER, TileType.PLAIN],
                [TileType.PLAIN, TileType.PLAIN, TileType.PLAIN],
            ],
            elevation_rows=[[8.0, 0.0, 5.0], [9.0, 2.0, 7.0]],
            water_bodies=[
                WaterBody(
                    id="river:lowland",
                    kind="river",
                    cell_refs=((1, 0),),
                    navigable=False,
                    region_id=101,
                    flow_direction=(0, 1),
                )
            ],
        )
    )
    for y in range(game_map.height):
        for x in range(game_map.width):
            game_map.create_tile(x, y, game_map.get_terrain(x, y))
    region = CityRegion(
        id=101,
        name="Vale Baixo",
        desc="",
        cors=[(0, 0), (1, 0), (2, 0), (1, 1)],
        population=400.0,
        population_capacity=500.0,
    )
    game_map.regions = {region.id: region}
    game_map.region_cors = {region.id: list(region.cors)}
    for coordinate in region.cors:
        game_map.tiles[coordinate].region = region
    return World(
        map=game_map,
        month_stamp=MonthStamp(10),
        playthrough_id="flood-lifecycle",
    )


def _weather(world: World, *, month: int, ratio: float, event_id: str) -> None:
    world.month_stamp = MonthStamp(month)
    world.climate_state = ClimateState(
        regions={
            "101": RegionalWeather(
                region_id="101",
                month=month,
                precipitation=ratio,
                soil_saturation=ratio,
                previous_soil_saturation=ratio,
                source_event_id=event_id,
            )
        },
        last_updated_month=month,
    )


def _advance(world: World) -> tuple[list, DomainInvalidationQueue]:
    queue = DomainInvalidationQueue()
    return advance_regional_floods(world, invalidations=queue), queue


def test_two_consecutive_high_risk_months_start_one_grounded_flood() -> None:
    world = _world()
    region_before = copy.deepcopy(world.map.regions[101].to_runtime_dict())
    routes_before = copy.deepcopy(world.map.routes)
    sites_before = copy.deepcopy(world.map.infrastructure_sites)

    _weather(world, month=10, ratio=0.96, event_id="rain-10")
    first_events, _ = _advance(world)
    assert first_events == []
    assert world.regional_flood_state.activation_streaks == {"101": 1}

    _weather(world, month=11, ratio=0.96, event_id="rain-11")
    events, queue = _advance(world)

    assert [event.event_type for event in events] == ["regional_flood_started"]
    event = events[0]
    assert event.causal_payload["outcome"] == "started"
    assert event.causal_payload["deltas"][0]["owner_kind"] == "regional_flood"
    assert {link.cause_event_id for link in event.causal_links} == {
        "rain-10",
        "rain-11",
    }
    assert {link.relation for link in event.causal_links} == {
        CausalRelation.TRIGGERED_BY
    }
    occurrence = world.regional_flood_state.active_by_region["101"]
    assert occurrence.source_event_ids == ("rain-10", "rain-11")
    assert build_region_semantic_context(world, world.map.regions[101])[
        "active_hazards"
    ] == [{"kind": "regional_flood", **occurrence.to_dict()}]
    assert queue.drain()[0].reason is DomainInvalidationReason.REGIONAL_HAZARD_CHANGED
    assert world.map.regions[101].to_runtime_dict() == region_before
    assert world.map.routes == routes_before
    assert world.map.infrastructure_sites == sites_before


def test_same_month_is_idempotent_and_persistent_flood_does_not_spam_events() -> None:
    world = _world()
    for month in (10, 11):
        _weather(world, month=month, ratio=0.96, event_id=f"rain-{month}")
        events, _ = _advance(world)
    assert len(events) == 1

    state_before = world.regional_flood_state.to_dict()
    repeated, _ = _advance(world)
    assert repeated == []
    assert world.regional_flood_state.to_dict() == state_before

    _weather(world, month=12, ratio=0.96, event_id="rain-12")
    continued, _ = _advance(world)
    assert continued == []
    assert "101" in world.regional_flood_state.active_by_region


def test_two_low_risk_months_resolve_and_link_to_the_flood_start() -> None:
    world = _world()
    for month in (10, 11):
        _weather(world, month=month, ratio=0.96, event_id=f"rain-{month}")
        started, _ = _advance(world)
    start_event = started[0]

    _weather(world, month=12, ratio=0.05, event_id="dry-12")
    first_low, _ = _advance(world)
    assert first_low == []
    assert "101" in world.regional_flood_state.active_by_region

    _weather(world, month=13, ratio=0.05, event_id="dry-13")
    resolved, _ = _advance(world)

    assert [event.event_type for event in resolved] == ["regional_flood_resolved"]
    event = resolved[0]
    assert "101" not in world.regional_flood_state.active_by_region
    assert any(
        link.cause_event_id == start_event.id
        and link.relation is CausalRelation.RESOLVES
        for link in event.causal_links
    )
    assert {"dry-12", "dry-13"}.issubset(
        {link.cause_event_id for link in event.causal_links}
    )


def test_resolution_requires_flooding_strictly_below_threshold(monkeypatch) -> None:
    world = _world()
    world.regional_flood_state.active_by_region["101"] = RegionalFloodOccurrence(
        region_id="101",
        started_month=8,
        activation_risk=0.8,
        source_event_ids=("rain-7", "rain-8"),
        last_event_id="flood-start",
    )
    world.regional_flood_state.last_evaluated_month = 9

    def projection_with_flooding(value: float):
        return lambda _world, _region_id: RegionalHydrologyProjection(
            region_id="101",
            month=int(world.month_stamp),
            precipitation=0.0,
            soil_water=0.0,
            drainage=0.0,
            flooding=value,
            state_refs=("climate:region:101:precipitation",),
            source_event_ids=(f"weather-{int(world.month_stamp)}",),
        )

    monkeypatch.setattr(
        "src.systems.regional_floods.project_regional_hydrology",
        projection_with_flooding(0.45),
    )
    world.month_stamp = MonthStamp(10)
    assert _advance(world)[0] == []
    assert world.regional_flood_state.resolution_streaks == {}

    monkeypatch.setattr(
        "src.systems.regional_floods.project_regional_hydrology",
        projection_with_flooding(0.44),
    )
    world.month_stamp = MonthStamp(11)
    assert _advance(world)[0] == []
    assert world.regional_flood_state.resolution_streaks == {"101": 1}

    world.month_stamp = MonthStamp(12)
    events, _ = _advance(world)
    assert [event.event_type for event in events] == ["regional_flood_resolved"]
    assert "101" not in world.regional_flood_state.active_by_region


def test_unknown_hydrology_never_resolves_an_active_flood() -> None:
    world = _world()
    world.regional_flood_state.active_by_region["101"] = RegionalFloodOccurrence(
        region_id="101",
        started_month=8,
        activation_risk=0.8,
        source_event_ids=("rain-7", "rain-8"),
        last_event_id="flood-start",
    )
    world.regional_flood_state.last_evaluated_month = 9
    world.month_stamp = MonthStamp(10)
    world.climate_state = ClimateState()

    events, _ = _advance(world)

    assert events == []
    assert "101" in world.regional_flood_state.active_by_region
    assert world.regional_flood_state.resolution_streaks == {}


def test_flood_state_survives_save_load_and_month_rollback(tmp_path) -> None:
    world = _world()
    for month in (10, 11):
        _weather(world, month=month, ratio=0.96, event_id=f"rain-{month}")
        _advance(world)
    world.run_config_snapshot = {
        "content_locale": "pt-BR",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
        "test_mode": True,
    }

    checkpoint = SimulationMonthCheckpoint.capture(world)
    before = world.regional_flood_state.to_dict()
    world.regional_flood_state.active_by_region.clear()
    checkpoint.restore()
    assert world.regional_flood_state.to_dict() == before

    save_path = tmp_path / "flood.json"
    success, message = save_game(world, Simulator(world), [], save_path=save_path)
    assert success, message
    loaded_world, _, _ = load_game(save_path)
    assert loaded_world.regional_flood_state.to_dict() == before
