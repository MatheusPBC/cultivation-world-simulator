from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import (
    Concept,
    ConceptLifecycle,
    ConditionDefinition,
    DerivedMetricDefinition,
    GroundingStatus,
    PrimitiveDimension,
)
from src.run.load_map import load_cultivation_world_map
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _seed_grounded_urban_risk(world, city: CityRegion) -> tuple[str, str]:
    capability_id = city.city_state.assets[1].capability_ids[0]
    metric_id = "smoke_urban_capability_deficit"
    condition_id = "smoke_urban_maintenance_need"
    state = world.mechanical_language
    state.concepts[metric_id] = Concept(
        id=metric_id,
        label="urban capability deficit",
        concept_kind="derived_metric",
        grounding_status=GroundingStatus.GROUNDED,
        lifecycle=ConceptLifecycle.ACTIVE,
        created_month=int(world.month_stamp),
        last_used_month=int(world.month_stamp),
    )
    state.concepts[condition_id] = Concept(
        id=condition_id,
        label="urban maintenance need",
        concept_kind="condition",
        grounding_status=GroundingStatus.GROUNDED,
        lifecycle=ConceptLifecycle.ACTIVE,
        created_month=int(world.month_stamp),
        last_used_month=int(world.month_stamp),
    )
    state.add_derived_definition(DerivedMetricDefinition(
        id=metric_id,
        concept_id=metric_id,
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "subtract",
            "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
            "right": {
                "op": "metric",
                "dimension": "quality",
                "concept_id": capability_id,
            },
        },
        unit="ratio",
        created_month=int(world.month_stamp),
        lifecycle=ConceptLifecycle.ACTIVE,
        last_used_month=int(world.month_stamp),
    ))
    state.add_condition_definition(ConditionDefinition(
        id=condition_id,
        concept_id=condition_id,
        target_kind="region",
        metric_definition_id=metric_id,
        activate_above=0.57,
        resolve_below=0.56,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(world.month_stamp),
        lifecycle=ConceptLifecycle.ACTIVE,
    ))
    return capability_id, condition_id


@pytest.mark.asyncio
async def test_two_year_causal_cycle_survives_save_load_without_real_llm(
    base_world,
    tmp_path,
    monkeypatch,
):
    base_world.map = load_cultivation_world_map("classic")
    cities = [
        region
        for region in base_world.map.regions.values()
        if isinstance(region, CityRegion)
    ]
    for city in cities:
        city.population = city.population_capacity * 0.40
    pressured = base_world.map.regions[302]
    destination = base_world.map.regions[305]
    pressured.population = pressured.population_capacity * 1.05
    capability_id, city_condition_id = _seed_grounded_urban_risk(base_world, pressured)
    initial_integrity = next(
        asset.integrity
        for asset in pressured.city_state.assets
        if capability_id in asset.capability_ids
    )

    provider = AsyncMock(side_effect=AssertionError("test mode must not call a provider"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)
    base_world.run_config_snapshot = {
        "content_locale": "zh-CN",
        "map_id": "classic",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.0,
        "world_lore": "",
        "test_mode": True,
        "domain_affordance_action_urgency_threshold": 0.0,
        "semantic_discovery_budget_per_month": 2,
        "population_interpreter_llm_budget_per_month": 2,
        "economy_interpreter_llm_budget_per_month": 2,
        "city_interpreter_llm_budget_per_month": 2,
    }
    simulator = Simulator(base_world)
    event_types: list[str] = []

    with llm_test_mode_scope(True):
        for _ in range(12):
            event_types.extend(event.event_type for event in await simulator.step())

    save_path = tmp_path / "causal-world-multimonth.json"
    success, message = save_game(base_world, simulator, [], save_path=save_path)
    assert success, message
    loaded_world, loaded_simulator, _ = load_game(save_path)

    with llm_test_mode_scope(True):
        for _ in range(12):
            event_types.extend(event.event_type for event in await loaded_simulator.step())

    assert provider.await_count == 0
    assert "regional_production" in event_types
    assert "regional_consumption" in event_types
    assert "semantic_condition_activated" in event_types
    assert "city_interpretation_decision" in event_types
    assert "city_maintenance_completed" in event_types
    assert "semantic_condition_resolved" in event_types
    assert "population_interpretation_decision" in event_types
    assert "population_transfer_completed" in event_types

    loaded_pressured = loaded_world.map.regions[302]
    loaded_destination = loaded_world.map.regions[305]
    maintained_integrity = next(
        asset.integrity
        for asset in loaded_pressured.city_state.assets
        if capability_id in asset.capability_ids
    )
    assert maintained_integrity > initial_integrity
    assert loaded_pressured.population < pressured.population_capacity * 1.05
    assert loaded_destination.population > destination.population_capacity * 0.40
    assert city_condition_id in loaded_world.mechanical_language.condition_definitions
    assert loaded_world.mechanical_language.reaction_receipts
    assert loaded_world.map.get_routes_between(302, 305)

    maintenance_events = [
        event
        for event in loaded_world.event_manager.get_recent_events(500)
        if event.event_type == "city_maintenance_completed"
        and event.render_params.get("region_id") == str(loaded_pressured.id)
        and event.render_params.get("capability_id") == capability_id
    ]
    assert maintenance_events
    for maintenance in maintenance_events:
        links = loaded_world.event_manager.get_causal_links_for_event(maintenance.id)
        assert {link.relation.value for link in links} >= {
            "motivated_by",
            "triggered_by",
        }
    resolution = next(
        event
        for event in loaded_world.event_manager.get_recent_events(500)
        if event.event_type == "semantic_condition_resolved"
        and event.render_params.get("condition_definition_id") == city_condition_id
    )
    resolution_links = loaded_world.event_manager.get_causal_links_for_event(resolution.id)
    assert any(
        link.cause_event_id in {event.id for event in maintenance_events}
        and link.relation.value == "enabled_by"
        for link in resolution_links
    )
