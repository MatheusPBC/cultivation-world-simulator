from unittest.mock import AsyncMock

import pytest

from src.classes.environment.region import CityRegion
from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanServiceDemand,
)
from src.classes.hp import HP
from src.classes.mechanical_language import ConceptLifecycle, ConditionInstance, EntityRef
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.time import MonthStamp
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


def _add_city(world, region_id: int, ratio: float) -> CityRegion:
    city = CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[(region_id, 0)],
        population=ratio * 100,
        population_capacity=100,
    )
    world.map.regions[region_id] = city
    return city


def _proposal():
    return {
        "concepts": [{
            "id": "settlement_density_pressure",
            "label": "settlement density pressure",
            "concept_kind": "derived_metric",
        }, {
            "id": "overcrowded_settlement",
            "label": "overcrowded settlement",
            "concept_kind": "condition",
        }],
        "derived_metrics": [{
            "id": "settlement_density_pressure",
            "concept_id": "settlement_density_pressure",
            "dimension": "risk",
            "target_kind": "region",
            "expression": {
                "op": "divide",
                "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
                "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
            },
            "unit": "ratio",
        }],
        "conditions": [{
            "id": "overcrowded_settlement",
            "concept_id": "overcrowded_settlement",
            "target_kind": "region",
            "metric_definition_id": "settlement_density_pressure",
            "activate_above": 0.85,
            "resolve_below": 0.75,
            "activate_after_months": 2,
            "resolve_after_months": 2,
        }],
        "mechanic_proposals": [],
    }


def _economy_proposal():
    return {
        "concepts": [{
            "id": "grain_stock_ratio",
            "label": "grain stock ratio",
            "concept_kind": "derived_metric",
        }, {
            "id": "grain_shortage",
            "label": "grain shortage",
            "concept_kind": "condition",
        }],
        "derived_metrics": [{
            "id": "grain_stock_ratio",
            "concept_id": "grain_stock_ratio",
            "dimension": "risk",
            "target_kind": "region",
            "expression": {
                "op": "divide",
                "left": {"op": "metric", "dimension": "stock", "concept_id": "grain"},
                "right": {"op": "metric", "dimension": "capacity", "concept_id": "grain"},
            },
            "unit": "ratio",
        }],
        "conditions": [{
            "id": "grain_shortage",
            "concept_id": "grain_shortage",
            "target_kind": "region",
            "metric_definition_id": "grain_stock_ratio",
            "activate_above": 0.7,
            "resolve_below": 0.5,
            "activate_after_months": 1,
            "resolve_after_months": 1,
        }],
        "mechanic_proposals": [],
    }


def _urban_quality_proposal():
    return {
        "concepts": [{
            "id": "black_lotus_service_quality",
            "label": "black lotus service quality",
            "concept_kind": "derived_metric",
        }, {
            "id": "strong_black_lotus_service",
            "label": "strong black lotus service",
            "concept_kind": "condition",
        }],
        "derived_metrics": [{
            "id": "black_lotus_service_quality",
            "concept_id": "black_lotus_service_quality",
            "dimension": "quality",
            "target_kind": "region",
            "expression": {
                "op": "metric",
                "dimension": "quality",
                "concept_id": "black_lotus_healing",
            },
            "unit": "ratio",
        }],
        "conditions": [{
            "id": "strong_black_lotus_service",
            "concept_id": "strong_black_lotus_service",
            "target_kind": "region",
            "metric_definition_id": "black_lotus_service_quality",
            "activate_above": 0.7,
            "resolve_below": 0.5,
            "activate_after_months": 1,
            "resolve_after_months": 1,
        }],
        "mechanic_proposals": [],
    }


@pytest.mark.asyncio
async def test_discovery_on_city_a_is_reused_for_city_b_without_second_llm_call(base_world):
    city_a = _add_city(base_world, 302, 0.90)
    city_b = _add_city(base_world, 305, 0.91)
    llm = AsyncMock(return_value=_proposal())

    first_events = await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    second_events = await evaluate_semantic_world(base_world, llm_call=llm)

    assert llm.await_count == 1
    assert first_events == []
    assert {
        condition.definition_id
        for condition in base_world.mechanical_language.get_conditions_for_target(
            EntityRef("region", str(city_a.id))
        )
    } == {"overcrowded_settlement"}
    assert {
        condition.definition_id
        for condition in base_world.mechanical_language.get_conditions_for_target(
            EntityRef("region", str(city_b.id))
        )
    } == {"overcrowded_settlement"}
    assert len(second_events) == 2
    assert all(event.fact_kind.value == "derived_condition" for event in second_events)
    assert second_events[0].causal_payload["measurements"][0]["key"] == {
        "dimension": "risk",
        "subject_kind": "region",
        "subject_id": second_events[0].render_params["region_id"],
        "concept_id": "settlement_density_pressure",
    }
    definition = base_world.mechanical_language.derived_definitions["settlement_density_pressure"]
    assert definition.lifecycle is ConceptLifecycle.ACTIVE
    concept = base_world.mechanical_language.concepts["settlement_density_pressure"]
    grounding = base_world.mechanical_language.groundings[concept.grounded_by[0]]
    assert grounding.metric_definition_id == definition.id
    assert grounding.evidence_refs == (
        "region:305:population",
        "region:305:population_capacity",
    )


@pytest.mark.asyncio
async def test_health_recovery_strain_is_discovered_then_resolves_without_more_llm(
    base_world,
    dummy_avatar,
):
    city = _add_city(base_world, 302, 0.90)
    city.city_state = CityState(
        districts=(CityDistrict("core", "urban", tuple(city.cors), 1.0),),
        assets=(UrbanAsset("healing-hall", "core", ("healing",), 10, 0.1, 1.0),),
        service_demands=(UrbanServiceDemand("healing", 0.1),),
    )
    tile = next(iter(base_world.map.tiles.values()))
    tile.region = city
    dummy_avatar.tile = tile
    dummy_avatar.hp = HP(100, 50)
    dummy_avatar.individual_consequences.record_injury(
        month=int(base_world.month_stamp),
        max_hp=100,
        damage=50,
        cause_event_id="injury-source",
    )
    base_world.avatar_manager.register_avatar(dummy_avatar)

    async def discover(_task, _template, infos, **_kwargs):
        return resolve_test_mode_task("semantic_discovery", infos)

    llm = AsyncMock(side_effect=discover)
    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=llm)

    assert llm.await_count == 2
    assert "health_recovery_strain" in base_world.mechanical_language.derived_definitions
    assert "strained_health_recovery" in base_world.mechanical_language.condition_definitions
    assert base_world.mechanical_language.pending_streaks.get(
        "strained_health_recovery:region:302"
    ) == {
        "activate": 1,
        "resolve": 0,
        "activate_base": 0,
        "resolve_base": 0,
        "evaluated_month": int(base_world.month_stamp),
    }

    base_world.run_config_snapshot = {
        **(getattr(base_world, "run_config_snapshot", {}) or {}),
        "semantic_discovery_budget_per_month": 0,
    }
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    activated = await evaluate_semantic_world(base_world, llm_call=llm)
    activation = next(
        event
        for event in activated
        if event.render_params.get("condition_definition_id")
        == "strained_health_recovery"
    )
    assert {link.cause_event_id for link in activation.causal_links} == {
        "injury-source"
    }

    dummy_avatar.hp.recover(dummy_avatar.hp.max)
    resolved_injury = dummy_avatar.individual_consequences.resolve_if_recovered(
        month=int(base_world.month_stamp),
        current_hp=dummy_avatar.hp.cur,
        max_hp=dummy_avatar.hp.max,
    )
    assert resolved_injury is not None

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    assert await evaluate_semantic_world(
        base_world,
        llm_call=llm,
        health_source_event_ids_by_target={"region:302": ["recovery-source"]},
    ) == []
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    resolved = await evaluate_semantic_world(base_world, llm_call=llm)
    resolution = next(
        event
        for event in resolved
        if event.render_params.get("condition_definition_id")
        == "strained_health_recovery"
    )
    assert any(
        link.cause_event_id == activation.id and link.relation.value == "resolves"
        for link in resolution.causal_links
    )
    assert any(
        link.cause_event_id == "recovery-source"
        and link.relation.value == "enabled_by"
        for link in resolution.causal_links
    )
    assert llm.await_count == 2


@pytest.mark.asyncio
async def test_world_test_mode_discovery_never_calls_provider(base_world):
    _add_city(base_world, 302, 0.90)
    base_world.run_config_snapshot = {"test_mode": True}
    provider = AsyncMock(side_effect=AssertionError("test mode called provider"))

    await evaluate_semantic_world(base_world, llm_call=provider)

    assert provider.await_count == 0
    assert "settlement_density_pressure" in base_world.mechanical_language.derived_definitions


@pytest.mark.asyncio
async def test_world_test_mode_discovers_new_dynamic_ratio_surface_without_provider(base_world):
    city = _add_city(base_world, 302, 0.90)
    city.city_state = CityState(
        districts=(CityDistrict("core", "mixed", tuple(city.cors), 1.0),),
        assets=(UrbanAsset(
            "lotus-clinic",
            "core",
            ("black_lotus_healing",),
            10.0,
            0.9,
            0.9,
        ),),
    )
    base_world.run_config_snapshot = {"test_mode": True}
    provider = AsyncMock(side_effect=AssertionError("test mode called provider"))

    await evaluate_semantic_world(base_world, llm_call=provider)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=provider)

    assert provider.await_count == 0
    assert "observed_black_lotus_healing_deficit" in (
        base_world.mechanical_language.derived_definitions
    )


@pytest.mark.asyncio
async def test_economic_observations_are_discovered_after_settlement_and_reused(base_world):
    city = _add_city(base_world, 302, 0.90)
    city.economy.stocks = {"grain": 8}
    city.economy.capacities = {"grain": 10}
    llm = AsyncMock(side_effect=[_proposal(), _economy_proposal()])

    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=llm)
    assert "grain_stock_ratio" in base_world.mechanical_language.derived_definitions
    assert llm.await_count == 2

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=llm)
    assert llm.await_count == 2


@pytest.mark.asyncio
async def test_new_urban_capability_surface_is_discovered_without_catalog_code(base_world):
    city = _add_city(base_world, 302, 0.90)
    city.city_state = CityState(
        districts=(CityDistrict("core", "mixed", tuple(city.cors), 1.0),),
        assets=(UrbanAsset(
            "lotus-clinic",
            "core",
            ("black_lotus_healing",),
            10.0,
            0.9,
            0.9,
        ),),
    )
    llm = AsyncMock(side_effect=[_proposal(), _urban_quality_proposal()])

    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    events = await evaluate_semantic_world(base_world, llm_call=llm)

    assert llm.await_count == 2
    assert "black_lotus_service_quality" in (
        base_world.mechanical_language.derived_definitions
    )
    assert [event.event_type for event in events] == [
        "semantic_condition_activated",
        "semantic_condition_activated",
    ]
    assert {
        event.render_params["condition_definition_id"] for event in events
    } == {"overcrowded_settlement", "strong_black_lotus_service"}

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=llm)
    assert llm.await_count == 2


@pytest.mark.asyncio
async def test_condition_persistence_counts_months_not_repeated_evaluations(base_world):
    city = _add_city(base_world, 302, 0.90)
    llm = AsyncMock(return_value=_proposal())

    assert await evaluate_semantic_world(base_world, llm_call=llm) == []
    assert await evaluate_semantic_world(base_world, llm_call=llm) == []
    assert base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(city.id))
    ) == []

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    events = await evaluate_semantic_world(base_world, llm_call=llm)

    assert [event.event_type for event in events] == ["semantic_condition_activated"]


@pytest.mark.asyncio
async def test_condition_transition_links_to_material_source_event(base_world):
    _add_city(base_world, 302, 0.90)
    llm = AsyncMock(return_value=_proposal())
    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)

    events = await evaluate_semantic_world(
        base_world,
        llm_call=llm,
        source_event_ids_by_target={"region:302": ["population-event"]},
    )

    assert events[0].causal_payload["measurements"][0]["source_event_ids"] == [
        "population-event"
    ]
    assert events[0].causal_links[0].cause_event_id == "population-event"


@pytest.mark.asyncio
async def test_deferred_transition_preserves_material_source_event(base_world):
    first = _add_city(base_world, 302, 0.90)
    second = _add_city(base_world, 305, 0.90)
    base_world.run_config_snapshot = {"semantic_evaluation_budget_per_month": 1}
    proposal = _proposal()
    proposal["conditions"][0]["activate_after_months"] = 1
    llm = AsyncMock(return_value=proposal)

    await evaluate_semantic_world(
        base_world,
        llm_call=llm,
        source_event_ids_by_target={
            f"region:{first.id}": ["first-population-event"],
            f"region:{second.id}": ["second-population-event"],
        },
    )
    assert base_world.mechanical_language.pending_source_event_ids == {
        f"settlement_density_pressure|region:{second.id}": ["second-population-event"],
    }

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    events = await evaluate_semantic_world(base_world, llm_call=llm)

    transition = next(
        event
        for event in events
        if event.render_params["region_id"] == str(second.id)
    )
    assert transition.causal_links[0].cause_event_id == "second-population-event"
    assert (
        f"settlement_density_pressure|region:{second.id}"
        not in base_world.mechanical_language.pending_source_event_ids
    )


@pytest.mark.asyncio
async def test_condition_persistence_requires_consecutive_calendar_months(base_world):
    city = _add_city(base_world, 302, 0.90)
    llm = AsyncMock(return_value=_proposal())

    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 2)
    assert await evaluate_semantic_world(base_world, llm_call=llm) == []
    assert base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(city.id))
    ) == []

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    events = await evaluate_semantic_world(base_world, llm_call=llm)

    assert [event.event_type for event in events] == ["semantic_condition_activated"]


@pytest.mark.asyncio
async def test_condition_resolves_deterministically_after_hysteresis_without_llm(base_world):
    city = _add_city(base_world, 302, 0.90)
    llm = AsyncMock(return_value=_proposal())
    await evaluate_semantic_world(base_world, llm_call=llm)
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=llm)
    assert len(base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)), int(base_world.month_stamp)
    )) == 1

    city.population = 70
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    assert await evaluate_semantic_world(base_world, llm_call=llm) == []
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    events = await evaluate_semantic_world(base_world, llm_call=llm)

    assert llm.await_count == 1
    assert len(events) == 1
    assert events[0].event_type == "semantic_condition_resolved"
    assert base_world.mechanical_language.get_active_conditions(
        EntityRef("region", str(city.id)), int(base_world.month_stamp)
    ) == []
    condition = base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(city.id))
    )[0]
    assert condition.resolved_month == int(base_world.month_stamp)


@pytest.mark.asyncio
async def test_unknown_metric_cannot_activate_condition(base_world):
    city = _add_city(base_world, 302, 0.90)
    proposal = _proposal()
    proposal["derived_metrics"][0]["expression"] = {
        "op": "metric",
        "dimension": "access",
        "concept_id": "healing",
    }
    llm = AsyncMock(return_value=proposal)

    for _ in range(3):
        assert await evaluate_semantic_world(base_world, llm_call=llm) == []
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)

    assert base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(city.id))
    ) == []


@pytest.mark.asyncio
async def test_rejected_proposal_does_not_partially_mutate_semantic_registry(base_world):
    _add_city(base_world, 302, 0.90)
    proposal = _proposal()
    proposal["conditions"][0]["resolve_below"] = 0.84
    llm = AsyncMock(return_value=proposal)

    assert await evaluate_semantic_world(base_world, llm_call=llm) == []

    state = base_world.mechanical_language
    assert state.concepts == {}
    assert state.derived_definitions == {}
    assert state.condition_definitions == {}
    assert state.mechanic_proposals == {}


@pytest.mark.asyncio
async def test_failed_discovery_uses_persisted_retry_cooldown(base_world):
    _add_city(base_world, 302, 0.90)
    failing = AsyncMock(side_effect=ValueError("invalid proposal"))

    await evaluate_semantic_world(base_world, llm_call=failing)
    for _ in range(11):
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
        await evaluate_semantic_world(base_world, llm_call=failing)

    assert failing.await_count == 1
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=failing)
    assert failing.await_count == 2


@pytest.mark.asyncio
async def test_evaluation_budget_resumes_dirty_targets_without_starvation(base_world):
    first = _add_city(base_world, 302, 0.90)
    second = _add_city(base_world, 305, 0.80)
    base_world.run_config_snapshot = {"semantic_evaluation_budget_per_month": 1}
    discovery = AsyncMock(return_value=_proposal())

    await evaluate_semantic_world(base_world, llm_call=discovery)
    definition = base_world.mechanical_language.derived_definitions["settlement_density_pressure"]
    assert definition.reuse_contexts == (f"region:{first.id}",)
    assert base_world.mechanical_language.dirty_targets == [
        f"settlement_density_pressure|region:{second.id}",
        f"settlement_density_pressure|region:{first.id}",
    ]

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    await evaluate_semantic_world(base_world, llm_call=discovery)
    definition = base_world.mechanical_language.derived_definitions["settlement_density_pressure"]
    assert definition.reuse_contexts == (
        f"region:{first.id}",
        f"region:{second.id}",
    )


@pytest.mark.asyncio
async def test_clean_target_is_not_recomputed_after_transition(base_world):
    _add_city(base_world, 302, 0.90)
    proposal = _proposal()
    proposal["conditions"][0]["activate_after_months"] = 1
    discovery = AsyncMock(return_value=proposal)

    events = await evaluate_semantic_world(base_world, llm_call=discovery)
    assert [event.event_type for event in events] == [
        "semantic_condition_activated"
    ]
    definition = base_world.mechanical_language.derived_definitions[
        "settlement_density_pressure"
    ]
    evaluated_month = definition.last_used_month

    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
    assert await evaluate_semantic_world(base_world, llm_call=discovery) == []

    unchanged = base_world.mechanical_language.derived_definitions[
        "settlement_density_pressure"
    ]
    assert unchanged.last_used_month == evaluated_month
    assert base_world.mechanical_language.dirty_targets == []


@pytest.mark.asyncio
async def test_unmeasurable_gap_can_be_recorded_as_observational_mechanic_proposal(base_world):
    _add_city(base_world, 302, 0.90)
    llm = AsyncMock(return_value={
        "concepts": [],
        "derived_metrics": [],
        "conditions": [],
        "mechanic_proposals": [{
            "concept": "healing_access",
            "reason": "No canonical healing-capability state exists yet.",
            "unmeasurable_keys": [{
                "dimension": "access",
                "subject_kind": "region",
                "subject_id": "302",
                "concept_id": "healing",
            }],
        }],
    })

    assert await evaluate_semantic_world(base_world, llm_call=llm) == []

    proposal = next(iter(base_world.mechanical_language.mechanic_proposals.values()))
    assert proposal.concept == "healing_access"
    assert proposal.unmeasurable_keys[0]["dimension"] == "access"
    assert base_world.mechanical_language.derived_definitions == {}


def test_condition_instances_are_owned_by_world_registry(base_world):
    city = _add_city(base_world, 302, 0.90)
    instance = ConditionInstance(
        id="condition-1",
        definition_id="overcrowded_settlement",
        target_kind="region",
        target_id="302",
        label="overcrowded settlement",
        intensity=0.5,
        started_month=1,
        cause_event_id="event-1",
    )
    base_world.mechanical_language.add_condition_instance(instance)

    assert base_world.mechanical_language.condition_instances == {instance.id: instance}
    assert base_world.mechanical_language.get_conditions_for_target(
        EntityRef("region", str(city.id))
    ) == [instance]
