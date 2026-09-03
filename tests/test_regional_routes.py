from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.run.load_map import load_cultivation_world_map
from src.run.map_source import map_source_to_dict, read_map_source
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.time import Month, Year, create_month_stamp


def test_route_is_strict_and_runtime_updates_preserve_identity() -> None:
    route = Route(
        id="road-1",
        endpoint_region_ids=(101, 102),
        mode="road",
        capacity=10,
        quality=0.75,
        enabled=True,
        allowed_resource_ids=("grain",),
    )

    route.update_runtime(capacity=4, quality=0.4, enabled=False)
    assert route.to_dict() == {
        "id": "road-1",
        "endpoint_region_ids": [101, 102],
        "mode": "road",
        "capacity": 4.0,
        "quality": 0.4,
        "enabled": False,
        "allowed_resource_ids": ["grain"],
    }

    with pytest.raises(ValueError, match="distinct"):
        Route("bad", (101, 101), "road", 1, 0.5, True)
    with pytest.raises(ValueError, match="quality"):
        Route("bad", (101, 102), "road", 1, 1.1, True)
    with pytest.raises(ValueError, match="capacity"):
        Route("bad", (101, 102), "road", -1, 0.5, True)


def test_map_never_infers_connectivity_and_filters_routes_deterministically() -> None:
    game_map = Map(width=1, height=1)
    game_map.set_routes(
        [
            Route("b", (1, 2), "road", 2, 0.8, True),
            Route("a", (2, 1), "river", 3, 0.7, True, ("grain",)),
            Route("disabled", (1, 2), "road", 9, 1, False),
        ]
    )

    assert [route.id for route in game_map.get_routes_between(1, 3)] == []
    assert [route.id for route in game_map.get_routes_between(1, 2)] == ["a", "b"]
    assert [route.id for route in game_map.get_routes_between(2, 1, resource_id="grain")] == ["a", "b"]
    assert [route.id for route in game_map.get_routes_between(1, 2, resource_id="medicine")] == ["b"]


def test_map_source_roundtrip_and_all_presets_have_explicit_routes(tmp_path) -> None:
    for map_id in ("classic", "island_seas", "mountain_frontier"):
        source = read_map_source(
            Path("static/game_configs/maps") / map_id / "map.json"
        )
        payload = map_source_to_dict(source)
        assert payload["schema_version"] == 4
        assert payload["routes"]
        assert map_source_to_dict(read_map_source_from_payload(payload, map_id, tmp_path)) == payload


def read_map_source_from_payload(payload: dict, map_id: str, tmp_path: Path):
    path = tmp_path / f"{map_id}-routes-map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        return read_map_source(path)
    finally:
        path.unlink()


def test_save_load_preserves_route_runtime_by_stable_id(tmp_path) -> None:
    game_map = load_cultivation_world_map("classic")
    route = game_map.routes["classic-301-405"]
    route.update_runtime(capacity=17, quality=0.21, enabled=False)
    world = World.create_with_db(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        events_db_path=tmp_path / "routes-events.db",
    )
    world.run_config_snapshot = {"content_locale": "zh-CN", "map_id": "classic", "init_npc_num": 0, "sect_num": 0}
    success, _ = save_game(world, Simulator(world), [], save_path=tmp_path / "routes-save.json")
    assert success

    with open(tmp_path / "routes-save.json", encoding="utf-8") as file:
        save_data = json.load(file)
    saved_route = next(item for item in save_data["world"]["routes"] if item["id"] == route.id)
    assert saved_route["capacity"] == 17.0
    assert saved_route["quality"] == 0.21
    assert saved_route["enabled"] is False

    loaded_world, _, _ = load_game(tmp_path / "routes-save.json")
    loaded_route = loaded_world.map.routes[route.id]
    assert loaded_route.capacity == 17.0
    assert loaded_route.quality == 0.21
    assert loaded_route.enabled is False
