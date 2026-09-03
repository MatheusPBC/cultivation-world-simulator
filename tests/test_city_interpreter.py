from unittest.mock import AsyncMock

import pytest

from src.classes.domain_proposal import CityDecisionKind, CityIntentKind
from src.classes.environment.city_state import CityDistrict, CityGovernance, CityState, UrbanAsset
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import ConditionDefinition, ConditionInstance, DerivedMetricDefinition, PrimitiveDimension
from src.systems.city_interpreter import CITY_INTERPRETER_TASK, interpret_city_transition
from src.utils.llm.runtime_mode import llm_test_mode_scope
from src.utils.llm.test_mode_fallbacks import registered_test_mode_tasks


def _city(world, *, quality=0.4, integrity=0.5, admin=0.8):
    city = CityRegion(
        id=301,
        name="Border City",
        desc="",
        cors=[(0, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, quality, integrity),),
            governance=CityGovernance("dynasty", "house-1", admin),
        ),
    )
    world.map.regions[city.id] = city
    trigger = Event(
        world.month_stamp,
        "The clinic became a regional risk.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={"region_id": "301", "condition_definition_id": "clinic_risk"},
        id="urban-risk-event",
    )
    condition = ConditionInstance(
        id="clinic-risk-instance",
        definition_id="clinic_risk",
        target_kind="region",
        target_id="301",
        label="clinic risk",
        intensity=0.8,
        started_month=int(world.month_stamp),
        cause_event_id=trigger.id,
        source_readings=({"key": {"dimension": "quality", "concept_id": "healing"}, "value": 0.2},),
    )
    world.mechanical_language.add_condition_instance(condition)
    world.mechanical_language.derived_definitions["clinic_quality_risk"] = DerivedMetricDefinition(
        id="clinic_quality_risk",
        concept_id="clinic_quality_risk",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={"op": "subtract", "left": {"op": "constant", "value": 1.0, "unit": "ratio"}, "right": {"op": "metric", "dimension": "quality", "concept_id": "healing"}},
        unit="ratio",
        created_month=int(world.month_stamp),
    )
    world.mechanical_language.condition_definitions["clinic_risk"] = ConditionDefinition(
        id="clinic_risk",
        concept_id="clinic_risk",
        target_kind="region",
        metric_definition_id="clinic_quality_risk",
        activate_above=0.7,
        resolve_below=0.5,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(world.month_stamp),
    )
    return city, trigger, condition


@pytest.mark.asyncio
async def test_city_interpreter_returns_grounded_typed_intent_and_causal_payload(base_world):
    city, trigger, condition = _city(base_world)
    provider = AsyncMock(return_value={
        "decision": "urban_maintenance",
        "reason": "The clinic is the grounded weak capability.",
        "action_intent": {"action_kind": "urban_maintenance", "capability_id": "healing"},
    })

    decision, event = await interpret_city_transition(
        base_world,
        trigger,
        condition,
        city.city_state.assets,
        city.city_state.governance,
        llm_call=provider,
    )

    assert provider.await_count == 1
    assert decision.decision is CityDecisionKind.URBAN_MAINTENANCE
    assert decision.action_intent is not None
    assert decision.action_intent.action_kind is CityIntentKind.URBAN_MAINTENANCE
    assert decision.action_intent.capability_id == "healing"
    payload = decision.action_intent.to_dict()
    assert "amount" not in payload
    assert "delta" not in payload
    assert event.fact_kind is FactKind.DECISION
    assert event.causal_payload["interpretation"]["condition_instance_id"] == condition.id
    assert event.causal_payload["interpretation"]["source_readings"]
    assert event.causal_links[0].cause_event_id == trigger.id


@pytest.mark.asyncio
async def test_city_interpreter_rejects_untrusted_capability_to_maintain(base_world):
    city, trigger, condition = _city(base_world)
    city.city_state = CityState(
        districts=city.city_state.districts,
        assets=(
            city.city_state.assets[0],
            UrbanAsset("warehouse", "core", ("housing",), 10, 0.1, 0.1),
        ),
        governance=city.city_state.governance,
    )
    provider = AsyncMock(return_value={
        "decision": "urban_maintenance",
        "reason": "Invent a new service.",
        "action_intent": {"action_kind": "urban_maintenance", "capability_id": "housing"},
    })

    decision, _ = await interpret_city_transition(
        base_world, trigger, condition, city.city_state.assets, city.city_state.governance, llm_call=provider
    )

    assert decision.decision is CityDecisionKind.MAINTAIN
    assert decision.action_intent is None


@pytest.mark.asyncio
async def test_city_context_exposes_only_quality_grounded_capabilities(base_world):
    city, trigger, condition = _city(base_world)
    captured = {}

    async def provider(_task, _template, infos, *, output_schema):
        captured.update(infos=infos, schema=output_schema)
        return {"decision": "maintain", "reason": "Observe."}

    await interpret_city_transition(
        base_world,
        trigger,
        condition,
        city.city_state.assets,
        city.city_state.governance,
        llm_call=provider,
    )

    assert captured["infos"]["eligible_capability_ids"] == ["healing"]
    assert "capability_id" in captured["schema"]["oneOf"][1]["properties"]["action_intent"]["properties"]


@pytest.mark.asyncio
async def test_city_interpreter_test_mode_never_calls_provider(base_world):
    city, trigger, condition = _city(base_world)
    provider = AsyncMock(side_effect=AssertionError("provider must not be called"))

    with llm_test_mode_scope(True):
        decision, event = await interpret_city_transition(
            base_world, trigger, condition, city.city_state.assets, city.city_state.governance, llm_call=provider
        )

    assert provider.await_count == 0
    assert CITY_INTERPRETER_TASK in registered_test_mode_tasks()
    assert decision.decision is CityDecisionKind.URBAN_MAINTENANCE
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_city_interpreter_can_propose_capacity_project_without_choosing_numbers(base_world):
    city, trigger, condition = _city(base_world)
    city.city_state = CityState(
        districts=city.city_state.districts,
        assets=(UrbanAsset("homes", "core", ("housing",), 100, 0.8, 0.9),),
        governance=city.city_state.governance,
    )
    provider = AsyncMock(return_value={
        "decision": "urban_capacity_project",
        "reason": "Persistent settlement pressure warrants expansion.",
        "action_intent": {
            "action_kind": "urban_capacity_project",
            "project_kind": "settlement_capacity_expansion",
        },
    })

    decision, _ = await interpret_city_transition(
        base_world,
        trigger,
        condition,
        city.city_state.assets,
        city.city_state.governance,
        eligible_project_kinds=("settlement_capacity_expansion",),
        llm_call=provider,
    )

    assert decision.decision.value == "urban_capacity_project"
    assert decision.action_intent is not None
    payload = decision.action_intent.to_dict()
    assert payload["project_kind"] == "settlement_capacity_expansion"
    assert "duration" not in payload
    assert "capacity_increase" not in payload
    assert "cost" not in payload
