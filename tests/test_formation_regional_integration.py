import json
from unittest.mock import patch

import pytest

from src.classes.action.set_formation import SetFormation
from src.classes.environment.region import CultivateRegion
from src.classes.items.auxiliary import auxiliaries_by_id
from src.classes.items.magic_stone import MagicStone
from src.classes.causal_link import CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phase_registry import expire_region_formations
from src.classes.mechanical_language import ConditionInstance, EntityRef
from src.systems.formation import (
    FORMATION_HEALING,
    cleanup_expired_region_formations,
)


def _setup_region(world, avatar):
    world.map = load_cultivation_world_map("classic")
    region = next(
        item for item in world.map.regions.values()
        if isinstance(item, CultivateRegion)
    )
    tile = world.map.get_tile(*region.cors[0])
    avatar.tile = tile
    avatar.pos_x, avatar.pos_y = region.cors[0]
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

    condition = base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(region.id))
    )[-1]
    assert event.is_major is True
    assert event.fact_kind.value == "state_transition"
    assert condition.definition_id == "formation:healing_formation"
    assert condition.started_month == int(base_world.month_stamp)
    assert condition.expires_month == (
        int(base_world.month_stamp) + base_world.map.region_formations[region.id]["duration"]
    )
    assert condition.cause_event_id == event.id
    assert base_world.map.region_formations[region.id]["source_event_id"] == event.id
    delta = next(
        item for item in event.causal_payload["deltas"]
        if item["aspect"] == "condition:healing_formation"
    )
    assert delta["owner_kind"] == "region"
    assert delta["owner_id"] == str(region.id)
    assert delta["aspect"] == "condition:healing_formation"
    assert json.loads(delta["after"])["cause_event_id"] == event.id


@pytest.mark.asyncio
async def test_formation_expiration_is_a_causal_state_transition(dummy_avatar, base_world):
    region = _setup_region(base_world, dummy_avatar)
    action = SetFormation(dummy_avatar, base_world)

    with patch("random.randint", return_value=0):
        action._execute(FORMATION_HEALING)
    establishment = (await action.finish(FORMATION_HEALING))[0]
    expires_month = base_world.map.region_formations[region.id]["start_month"] + base_world.map.region_formations[region.id]["duration"]

    expiration_events = cleanup_expired_region_formations(base_world, expires_month)

    assert base_world.map.region_formations == {}
    assert len(expiration_events) == 1
    expiration = expiration_events[0]
    assert expiration.fact_kind.value == "state_transition"
    assert expiration.causal_origin is CausalOrigin.DETERMINISTIC
    assert len(expiration.causal_links) == 1
    assert expiration.causal_links[0].cause_event_id == establishment.id
    assert expiration.causal_links[0].relation is CausalRelation.RESOLVES
    assert expiration.causal_payload["deltas"][0]["owner_id"] == str(region.id)
    assert expiration.causal_payload["deltas"][0]["after"] is None
    condition = base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(region.id))
    )[-1]
    assert condition.resolution_event_id == expiration.id


def test_monthly_formation_expiration_phase_adds_event_to_context(dummy_avatar, base_world):
    region = _setup_region(base_world, dummy_avatar)
    base_world.map.region_formations[region.id] = {
        "formation_type": FORMATION_HEALING,
        "start_month": int(base_world.month_stamp),
        "duration": 1,
        "effects": {},
        "source_event_id": "event-formation",
    }
    base_world.month_stamp = base_world.month_stamp + 1
    ctx = SimulationStepContext.create(base_world)

    expire_region_formations(None, ctx)

    assert len(ctx.events) == 1
    assert ctx.events[0].causal_links[0].relation is CausalRelation.RESOLVES
    assert ctx.events[0].causal_payload["formation_expiration"]["source_event_id"] == "event-formation"
    assert base_world.map.region_formations == {}


def test_formation_region_condition_survives_save_load(dummy_avatar, base_world, tmp_path):
    region = _setup_region(base_world, dummy_avatar)
    dummy_avatar.magic_stone = MagicStone(int(dummy_avatar.magic_stone))
    dummy_avatar.weapon = None
    dummy_avatar.auxiliary = None
    base_world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="formation-condition",
            definition_id="formation:healing_formation",
            target_kind="region",
            target_id=str(region.id),
            label="healing_formation",
            intensity=1.0,
            started_month=int(base_world.month_stamp),
            expires_month=int(base_world.month_stamp) + 26,
            cause_event_id="event-formation",
        )
    )
    base_world.map.region_formations[region.id] = {
        "formation_type": FORMATION_HEALING,
        "start_month": int(base_world.month_stamp),
        "duration": 26,
        "effects": {},
        "source_event_id": "event-formation",
    }
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
    assert data["world"]["region_formations"][str(region.id)]["source_event_id"] == "event-formation"
    assert data["world"]["mechanical_language"]["condition_instances"]["formation-condition"]["cause_event_id"] == "event-formation"

    loaded_world, _, _ = load_game(save_path)
    loaded = loaded_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(region.id))
    )[0]
    assert loaded.definition_id == "formation:healing_formation"
    assert loaded.cause_event_id == "event-formation"
