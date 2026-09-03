from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanServiceDemand,
)
from src.classes.event import Event, FactKind
from src.classes.hp import HP
from src.classes.mechanical_language import EntityRef
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.serialization import serialize_events_for_client
from src.server.services.game_queries import get_event_causal_detail
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationReason,
)
from src.sim.simulator_engine import phase_registry
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.time import MonthStamp
from src.utils.llm.test_mode_fallbacks import registered_test_mode_tasks, resolve_test_mode_task
from src.utils.llm.runtime_mode import llm_test_mode_scope

from tests.test_semantic_world_service import _add_city, _proposal


def test_semantic_phase_runs_after_population_and_before_appraisal():
    names = [phase.name for phase in get_simulation_phases()]

    assert names.index("update_city_population") < names.index("evaluate_semantic_world")
    assert names.index("update_regional_economy") < names.index("react_economy")
    assert names.index("react_economy") < names.index("evaluate_semantic_world")
    assert names.index("update_regional_climate") < names.index("evaluate_semantic_world")
    assert names.index("update_regional_climate") < names.index("update_regional_floods")
    assert names.index("update_regional_floods") < names.index("resolve_material_hazard_impacts")
    assert names.index("resolve_material_hazard_impacts") < names.index("update_route_infrastructure_dependencies")
    assert names.index("update_route_infrastructure_dependencies") < names.index("evaluate_semantic_world")
    assert names.index("evaluate_semantic_world") < names.index("generate_event_appraisals")
    assert names.index("evaluate_semantic_world") < names.index("react_government")
    assert names.index("evaluate_semantic_world") < names.index("react_organization")
    assert names.index("react_government") < names.index("react_city")
    assert names.index("react_organization") < names.index("react_city")
    assert names.index("evaluate_semantic_world") < names.index("react_population")
    assert names.index("react_population") < names.index("generate_event_appraisals")
    assert [phase.index for phase in get_simulation_phases()] == list(range(1, len(names) + 1))


@pytest.mark.asyncio
async def test_semantic_phase_routes_avatar_recovery_as_health_only_source(
    base_world,
    dummy_avatar,
    monkeypatch,
):
    city = _add_city(base_world, 302, 0.9)
    tile = base_world.map.tiles[(0, 0)]
    tile.region = city
    dummy_avatar.tile = tile
    base_world.avatar_manager.register_avatar(dummy_avatar)
    recovery = Event(
        base_world.month_stamp,
        "injury recovered",
        related_avatars=[dummy_avatar.id],
        fact_kind=FactKind.DERIVED_CONDITION,
        causal_payload={
            "deltas": [
                {
                    "event_id": "recovery-event",
                    "owner_kind": "avatar",
                    "owner_id": str(dummy_avatar.id),
                    "aspect": "recovery",
                    "before": "injured",
                    "after": "recovered",
                    "magnitude": 0.0,
                }
            ]
        },
        id="recovery-event",
    )
    captured = {}

    async def fake_evaluate(_world, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "src.systems.semantic_world.service.evaluate_semantic_world",
        fake_evaluate,
    )
    ctx = SimulationStepContext.create(base_world)
    ctx.events.append(recovery)

    await phase_registry.evaluate_semantic_world(Simulator(base_world), ctx)

    assert captured["source_event_ids_by_target"] == {}
    assert captured["health_source_event_ids_by_target"] == {
        "region:302": ["recovery-event"]
    }


@pytest.mark.asyncio
async def test_semantic_phase_routes_climate_evidence_only_to_climate_affinities(
    base_world,
    monkeypatch,
):
    captured = {}

    async def fake_evaluate(_world, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "src.systems.semantic_world.service.evaluate_semantic_world",
        fake_evaluate,
    )
    ctx = SimulationStepContext.create(base_world)
    ctx.invalidations.mark(DomainInvalidation(
        layer=DomainInvalidationLayer.MECHANICAL,
        domain="region",
        target_kind="region",
        target_id="302",
        reason=DomainInvalidationReason.CLIMATE_CHANGED,
        source_event_ids=("climate-event",),
        revision="climate:302:1",
    ))

    await phase_registry.evaluate_semantic_world(Simulator(base_world), ctx)

    assert captured["source_event_ids_by_target"] == {}
    assert captured["climate_source_event_ids_by_target"] == {
        "region:302": ["climate-event"]
    }


def test_semantic_discovery_has_deterministic_test_mode_fallback():
    assert "semantic_discovery" in registered_test_mode_tasks()
    result = resolve_test_mode_task("semantic_discovery", {"target": {"kind": "region", "id": "302"}})

    assert result["derived_metrics"][0]["id"] == "settlement_density_pressure"
    assert result["conditions"][0]["id"] == "overcrowded_settlement"


@pytest.mark.asyncio
async def test_twelve_month_semantic_smoke_uses_no_real_llm_and_emits_only_transitions(base_world, monkeypatch):
    city = _add_city(base_world, 302, 0.90)
    provider = AsyncMock(side_effect=AssertionError("test mode must not call a real provider"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    simulator = Simulator(base_world)
    events = []

    with llm_test_mode_scope(True):
        for _ in range(12):
            events.extend(await simulator.step())

    semantic_events = [event for event in events if event.event_type.startswith("semantic_condition_")]
    assert provider.await_count == 0
    assert [event.event_type for event in semantic_events] == ["semantic_condition_activated"]
    assert len(base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)), int(base_world.month_stamp)
    )) == 1
    assert "settlement_density_pressure" in base_world.mechanical_language.derived_definitions


@pytest.mark.asyncio
async def test_definition_survives_save_and_applies_to_city_c_without_llm(base_world, tmp_path):
    _add_city(base_world, 302, 0.90)
    _add_city(base_world, 305, 0.91)
    discover = AsyncMock(return_value=_proposal())
    await evaluate_semantic_world(base_world, llm_call=discover)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=discover)

    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
        "test_mode": True,
    }
    save_path = tmp_path / "semantic-world.json"
    ok, message = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert ok, message

    loaded_world, _, _ = load_game(save_path)
    city_c = CityRegion(
        id=399,
        name="City C",
        desc="",
        cors=[(9, 9)],
        population=92,
        population_capacity=100,
    )
    loaded_world.map.regions[399] = city_c
    forbidden_llm = AsyncMock(side_effect=AssertionError("persisted definitions must be reused"))
    assert await evaluate_semantic_world(loaded_world, llm_call=forbidden_llm) == []
    loaded_world.month_stamp = MonthStamp(int(loaded_world.month_stamp) + 1)
    events = await evaluate_semantic_world(loaded_world, llm_call=forbidden_llm)

    assert forbidden_llm.await_count == 0
    assert [event.event_type for event in events] == ["semantic_condition_activated"]
    assert loaded_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city_c.id)), int(loaded_world.month_stamp)
    )[0].definition_id == "overcrowded_settlement"


@pytest.mark.asyncio
async def test_health_definition_condition_and_injury_evidence_survive_save_load(
    base_world,
    dummy_avatar,
    tmp_path,
):
    city = _add_city(base_world, 302, 0.9)
    city.cors = [(0, 0)]
    city.city_state = CityState(
        districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
        assets=(UrbanAsset("healing-hall", "core", ("healing",), 10, 0.1, 1.0),),
        service_demands=(UrbanServiceDemand("healing", 0.1),),
    )
    base_world.map.tiles[(0, 0)].region = city
    dummy_avatar.tile = base_world.map.tiles[(0, 0)]
    dummy_avatar.weapon = None
    dummy_avatar.hp = HP(100, 50)
    dummy_avatar.individual_consequences.record_injury(
        month=int(base_world.month_stamp),
        max_hp=100,
        damage=50,
        cause_event_id="persisted-injury-source",
    )
    base_world.avatar_manager.register_avatar(dummy_avatar)

    async def discover(_task, _template, infos, **_kwargs):
        return resolve_test_mode_task("semantic_discovery", infos)

    discovery = AsyncMock(side_effect=discover)
    await evaluate_semantic_world(base_world, llm_call=discovery)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=discovery)
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.01,
        "world_lore": "",
        "test_mode": True,
        "semantic_discovery_budget_per_month": 0,
    }
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=discovery)

    active = base_world.mechanical_language.get_active_conditions(
        EntityRef("region", "302"),
        int(base_world.month_stamp),
    )
    health = next(
        condition
        for condition in active
        if condition.definition_id == "strained_health_recovery"
    )
    assert health.source_readings[0]["source_event_ids"] == [
        "persisted-injury-source"
    ]

    save_path = tmp_path / "health-semantic-world.json"
    ok, message = save_game(base_world, Simulator(base_world), [], save_path=save_path)
    assert ok, message
    loaded_world, _, _ = load_game(save_path)

    assert "health_recovery_strain" in loaded_world.mechanical_language.derived_definitions
    loaded_health = next(
        condition
        for condition in loaded_world.mechanical_language.get_active_conditions(
            EntityRef("region", "302"),
            int(loaded_world.month_stamp),
        )
        if condition.definition_id == "strained_health_recovery"
    )
    assert loaded_health.id == health.id
    assert loaded_health.source_readings[0]["source_event_ids"] == [
        "persisted-injury-source"
    ]
    loaded_avatar = loaded_world.avatar_manager.get_avatar(dummy_avatar.id)
    assert loaded_avatar.individual_consequences.active_injury.cause_event_ids == [
        "persisted-injury-source"
    ]

    forbidden_llm = AsyncMock(
        side_effect=AssertionError("persisted health definitions must be reused")
    )
    assert await evaluate_semantic_world(
        loaded_world,
        llm_call=forbidden_llm,
    ) == []
    assert forbidden_llm.await_count == 0


def test_why_service_exposes_semantic_measurements_without_testclient_threadpool(base_world):
    measurement = {
        "key": {
            "dimension": "risk",
            "subject_kind": "region",
            "subject_id": "302",
            "concept_id": "settlement_density_pressure",
        },
        "value": 0.9,
        "unit": "ratio",
        "availability": "measurable",
        "reading_kind": "derived",
        "state_refs": ["region:302:population", "region:302:population_capacity"],
        "source_event_ids": [],
    }
    event = Event(
        base_world.month_stamp,
        "condition activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        causal_payload={"deltas": [], "measurements": [measurement]},
    )
    base_world.event_manager.add_event(event)
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_world_and_sim(base_world, None)

    detail = get_event_causal_detail(
        runtime,
        serialize_events_for_client=lambda events, **kwargs: serialize_events_for_client(
            events, world=base_world
        ),
        event_id=event.id,
    )

    assert detail["measurements"] == [measurement]
