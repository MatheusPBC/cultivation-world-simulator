from unittest.mock import AsyncMock

import pytest

from src.classes.core.dynasty import Dynasty
from src.classes.domain_proposal import GovernmentDecisionKind, GovernmentIntentKind
from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
)
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.systems.government_interpreter import (
    GOVERNMENT_INTERPRETER_TASK,
    interpret_government_transition,
)
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _setup(world, *, controller_id="1", integrity=0.5):
    world.dynasty = Dynasty(
        id=1, name="Test Dynasty", desc="", current_emperor_id="emperor-1"
    )
    city = CityRegion(
        id=301,
        name="Border City",
        desc="",
        cors=[(0, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, 0.4, integrity),),
            governance=CityGovernance("dynasty", controller_id, 0.8),
        ),
    )
    world.map.regions[city.id] = city
    world.mechanical_language.derived_definitions["clinic-risk-metric"] = (
        DerivedMetricDefinition(
            id="clinic-risk-metric",
            concept_id="clinic-risk-metric",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": {
                    "op": "metric",
                    "dimension": "quality",
                    "concept_id": "healing",
                },
            },
            unit="ratio",
            created_month=int(world.month_stamp),
        )
    )
    world.mechanical_language.condition_definitions["clinic-risk"] = (
        ConditionDefinition(
            id="clinic-risk",
            concept_id="clinic-risk",
            target_kind="region",
            metric_definition_id="clinic-risk-metric",
            activate_above=0.7,
            resolve_below=0.5,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )
    trigger = Event(
        world.month_stamp,
        "The clinic became a regional risk.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={"region_id": "301", "condition_definition_id": "clinic-risk"},
        id="government-trigger",
    )
    condition = ConditionInstance(
        id="government-condition",
        definition_id="clinic-risk",
        target_kind="region",
        target_id="301",
        label="clinic risk",
        intensity=0.8,
        started_month=int(world.month_stamp),
        cause_event_id=trigger.id,
        source_readings=(
            {"key": {"dimension": "quality", "concept_id": "healing"}, "value": 0.2},
        ),
    )
    world.mechanical_language.add_condition_instance(condition)
    return city, trigger, condition


@pytest.mark.asyncio
async def test_government_interpreter_returns_grounded_intent_and_response_link(
    base_world,
):
    city, trigger, condition = _setup(base_world)
    provider = AsyncMock(
        return_value={
            "decision": "urban_maintenance",
            "reason": "The dynasty addresses the grounded clinic risk.",
            "action_intent": {
                "action_kind": "urban_maintenance",
                "capability_id": "healing",
            },
        }
    )

    decision, event = await interpret_government_transition(
        base_world, trigger, condition, llm_call=provider
    )

    assert provider.await_count == 1
    assert decision.decision is GovernmentDecisionKind.URBAN_MAINTENANCE
    assert decision.action_intent is not None
    assert decision.action_intent.action_kind is GovernmentIntentKind.URBAN_MAINTENANCE
    payload = decision.action_intent.to_dict()
    assert payload["subject_id"] == "dynasty:1"
    assert "amount" not in payload
    assert "delta" not in payload
    assert event.event_type == "government_interpretation_decision"
    assert event.related_avatars == ["emperor-1"]
    assert event.causal_links[0].cause_event_id == trigger.id
    assert event.causal_links[0].relation.value == "response_to"
    assert event.causal_payload["decision"]["subject_kind"] == "dynasty"


@pytest.mark.asyncio
async def test_government_rejects_untrusted_capability_to_maintain(base_world):
    _, trigger, condition = _setup(base_world)
    provider = AsyncMock(
        return_value={
            "decision": "urban_maintenance",
            "reason": "Invent a new service.",
            "action_intent": {
                "action_kind": "urban_maintenance",
                "capability_id": "housing",
            },
        }
    )

    decision, _ = await interpret_government_transition(
        base_world, trigger, condition, llm_call=provider
    )

    assert decision.decision is GovernmentDecisionKind.MAINTAIN
    assert decision.action_intent is None


@pytest.mark.asyncio
async def test_government_test_mode_uses_local_rule_without_provider(base_world):
    _, trigger, condition = _setup(base_world)
    provider = AsyncMock(side_effect=AssertionError("real provider must not be called"))

    with llm_test_mode_scope(True):
        decision, event = await interpret_government_transition(
            base_world, trigger, condition, llm_call=provider
        )

    assert provider.await_count == 0
    assert decision.decision is GovernmentDecisionKind.URBAN_MAINTENANCE
    assert event.causal_payload["decision"]["source"] == "rule"
    assert GOVERNMENT_INTERPRETER_TASK == "government_interpreter"


@pytest.mark.asyncio
async def test_government_requires_explicit_matching_dynasty_control(base_world):
    _, trigger, condition = _setup(base_world, controller_id="other-dynasty")

    with pytest.raises(ValueError, match="explicit dynasty control"):
        await interpret_government_transition(
            base_world, trigger, condition, force_rule=True
        )


@pytest.mark.asyncio
async def test_government_can_select_capacity_project_without_numbers(base_world):
    city, trigger, condition = _setup(base_world)
    city.city_state = CityState(
        districts=city.city_state.districts,
        assets=(
            UrbanAsset("homes", "core", ("housing",), 100, 0.8, 0.9),
            UrbanAsset("builders", "core", ("construction_work",), 10, 1.0, 1.0),
        ),
        governance=city.city_state.governance,
    )
    provider = AsyncMock(
        return_value={
            "decision": "urban_capacity_project",
            "reason": "Authorize grounded expansion.",
            "action_intent": {
                "action_kind": "urban_capacity_project",
                "project_kind": "settlement_capacity_expansion",
            },
        }
    )

    decision, _ = await interpret_government_transition(
        base_world,
        trigger,
        condition,
        llm_call=provider,
        capabilities=(),
        project_kinds=("settlement_capacity_expansion",),
    )

    assert decision.decision is GovernmentDecisionKind.URBAN_CAPACITY_PROJECT
    assert decision.action_intent is not None
    assert "cost" not in decision.action_intent.to_dict()
    assert "duration" not in decision.action_intent.to_dict()
