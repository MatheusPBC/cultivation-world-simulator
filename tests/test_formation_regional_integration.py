import json
from unittest.mock import patch

import pytest

from src.classes.action.set_formation import SetFormation
from src.classes.environment.region import CultivateRegion
from src.classes.environment.tile import Tile, TileType
from src.classes.items.auxiliary import auxiliaries_by_id
from src.classes.items.magic_stone import MagicStone
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.systems.formation import FORMATION_HEALING


def _setup_region(world, avatar):
    region = CultivateRegion(id=301, name="Formation Valley", desc="", cors=[(0, 0)])
    tile = Tile(0, 0, TileType.CAVE)
    tile.region = region
    avatar.tile = tile
    world.map.tiles[(0, 0)] = tile
    world.map.regions[region.id] = region
    world.map.region_cors[region.id] = [(0, 0)]
    avatar.auxiliary = auxiliaries_by_id[2082].instantiate()
    avatar.recalc_effects()
    avatar.magic_stone = 1000
    return region


@pytest.mark.asyncio
async def test_formation_finish_creates_causal_region_condition(dummy_avatar, base_world):
    region = _setup_region(base_world, dummy_avatar)
    action = SetFormation(dummy_avatar, base_world)

    with patch("random.randint", return_value=0):
        action._execute(FORMATION_HEALING)
    event = (await action.finish(FORMATION_HEALING))[0]

    condition = region.conditions[-1]
    assert event.is_major is True
    assert event.fact_kind.value == "derived_condition"
    assert condition.kind == "healing_formation"
    assert condition.started_month == int(base_world.month_stamp)
    assert condition.expires_month == (
        int(base_world.month_stamp) + base_world.map.region_formations[region.id]["duration"]
    )
    assert condition.cause_event_id == event.id
    delta = event.causal_payload["deltas"][0]
    assert delta["owner_kind"] == "region"
    assert delta["owner_id"] == str(region.id)
    assert delta["aspect"] == "condition:healing_formation"
    assert json.loads(delta["after"])["cause_event_id"] == event.id


def test_formation_region_condition_survives_save_load(dummy_avatar, base_world, tmp_path):
    region = _setup_region(base_world, dummy_avatar)
    dummy_avatar.magic_stone = MagicStone(int(dummy_avatar.magic_stone))
    dummy_avatar.weapon = None
    dummy_avatar.auxiliary = None
    region.add_condition(
        __import__("src.classes.environment.region_condition", fromlist=["RegionCondition"]).RegionCondition(
            kind="healing_formation",
            intensity=1.0,
            started_month=int(base_world.month_stamp),
            expires_month=int(base_world.month_stamp) + 26,
            cause_event_id="event-formation",
        )
    )
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
    }
    save_path = tmp_path / "formation_condition_save.json"
    success, _ = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert success
    with open(save_path, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["world"]["regions_status"]["301"]["conditions"][0]["cause_event_id"] == "event-formation"

    loaded_world, _, _ = load_game(save_path)
    loaded = loaded_world.map.regions[301].conditions[0]
    assert loaded.kind == "healing_formation"
    assert loaded.cause_event_id == "event-formation"
