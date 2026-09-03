from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import ConditionInstance
from src.classes.domain_proposal import PopulationDecisionKind, PopulationIntentKind
from src.systems.population_interpreter import interpret_population_transition
from src.utils.llm.runtime_mode import llm_test_mode_scope
from src.utils.llm.exceptions import LLMError
from src.utils.llm.test_mode_fallbacks import (
    registered_test_mode_tasks,
    resolve_test_mode_task,
)


def _transition(world, *, region_id: int = 10, condition_id: str = "overcrowded_settlement"):
    city = CityRegion(
        id=region_id,
        name="Crowded City",
        desc="",
        cors=[(2, 2)],
        population=95,
        population_capacity=100,
    )
    world.mechanical_language.add_condition_instance(ConditionInstance(
        id="condition-instance-1",
        definition_id=condition_id,
        target_kind="region",
        target_id=str(region_id),
        label="overcrowded settlement",
        intensity=0.9,
        started_month=int(world.month_stamp),
        cause_event_id="pressure-event-1",
        source_readings=({
            "key": {"dimension": "risk", "concept_id": "settlement_density_pressure"},
            "value": 0.95,
            "unit": "ratio",
        },),
    ))
    world.map.regions[region_id] = city
    return Event(
        month_stamp=world.month_stamp,
        content="A city entered an overcrowded settlement condition.",
        event_type="semantic_condition_activated",
        render_params={
            "region_id": str(region_id),
            "condition_definition_id": condition_id,
        },
        fact_kind=FactKind.DERIVED_CONDITION,
        id="transition-event-1",
    )


@pytest.mark.asyncio
async def test_interpretation_builds_typed_intent_and_response_causal_event(base_world):
    transition = _transition(base_world)
    destination = CityRegion(
        id=11,
        name="Open City",
        desc="",
        cors=[(8, 8)],
        population=30,
        population_capacity=100,
    )
    base_world.map.regions[destination.id] = destination
    llm = AsyncMock(return_value={
        "decision": "act",
        "reason": "A lower-load city can receive population.",
        "action_intent": {
            "action_kind": "population_transfer",
            "preferences": ["lower_settlement_load", "available_capacity"],
        },
    })

    decision, event = await interpret_population_transition(base_world, transition, llm_call=llm)

    assert decision.decision is PopulationDecisionKind.ACT
    assert decision.action_intent is not None
    assert decision.action_intent.action_kind is PopulationIntentKind.POPULATION_TRANSFER
    assert decision.action_intent.subject_kind == "population"
    assert decision.action_intent.subject_id == "region:10"
    assert decision.action_intent.motivation_event_ids == (transition.id,)
    assert decision.action_intent.preferences
    assert event.event_type == "population_interpretation_decision"
    assert event.fact_kind is FactKind.DECISION
    assert event.causal_payload["decision"]["subject_kind"] == "population"
    assert event.causal_payload["decision"]["chosen_chain"] == [decision.action_intent.to_dict()]
    assert event.causal_payload["decision"]["thinking"] == decision.reason
    assert event.causal_payload["interpretation"]["decision"] == "act"
    assert event.causal_payload["interpretation"]["action_intent"] == decision.action_intent.to_dict()
    assert event.causal_links[0].relation is CausalRelation.RESPONSE_TO
    assert event.causal_links[0].cause_event_id == transition.id


@pytest.mark.asyncio
async def test_llm_context_is_grounded_and_schema_is_closed(base_world):
    transition = _transition(base_world)
    base_world.map.regions[11] = CityRegion(
        id=11,
        name="Open City",
        desc="",
        cors=[(8, 8)],
        population=30,
        population_capacity=100,
    )
    captured = {}

    async def llm(task_name, template_path, infos, *, output_schema):
        captured.update(task_name=task_name, template_path=template_path, infos=infos, schema=output_schema)
        return {"decision": "maintain", "reason": "The transition is being observed."}

    await interpret_population_transition(base_world, transition, llm_call=llm)

    assert captured["task_name"] == "population_interpreter"
    assert captured["template_path"].name == "population_interpreter.txt"
    assert captured["infos"]["origin"]["population"] == 95
    assert captured["infos"]["origin"]["capacity"] == 100
    assert captured["infos"]["origin"]["ratio"] == pytest.approx(0.95)
    assert captured["infos"]["origin"]["source_readings"][0]["value"] == 0.95
    assert captured["infos"]["candidates"] == [{
        "id": "11",
        "name": "Open City",
        "population": 30,
        "capacity": 100,
        "ratio": pytest.approx(0.3),
        "distance": 12,
    }]
    assert "housing" not in str(captured["infos"])
    assert "route" not in str(captured["infos"])
    assert "wealth" not in str(captured["infos"])
    assert captured["schema"]["additionalProperties"] is False
    assert captured["schema"]["oneOf"][0]["additionalProperties"] is False
    assert captured["schema"]["oneOf"][1]["properties"]["action_intent"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_provider_failure_degrades_to_rule_maintain_without_aborting(base_world):
    transition = _transition(base_world)

    async def failing_llm(*args, **kwargs):
        raise LLMError("provider unavailable")

    decision, event = await interpret_population_transition(base_world, transition, llm_call=failing_llm)

    assert decision.decision is PopulationDecisionKind.MAINTAIN
    assert decision.reason
    assert event.causal_payload["decision"]["source"] == "rule"
    assert event.causal_payload["decision"]["chosen_chain"] == []


@pytest.mark.asyncio
async def test_response_with_untrusted_destination_is_rejected_to_rule_maintain(base_world):
    transition = _transition(base_world)

    async def untrusted_llm(*args, **kwargs):
        return {
            "decision": "act",
            "reason": "Move people to city 999.",
            "action_intent": {
                "action_kind": "population_transfer",
                "preferences": [],
                "destination": "region:999",
            },
        }

    decision, event = await interpret_population_transition(base_world, transition, llm_call=untrusted_llm)

    assert decision.decision is PopulationDecisionKind.MAINTAIN
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_world_test_mode_snapshot_never_calls_injected_provider(base_world):
    transition = _transition(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    provider = AsyncMock(side_effect=AssertionError("provider must not be called"))

    decision, event = await interpret_population_transition(
        base_world,
        transition,
        llm_call=provider,
    )

    assert provider.await_count == 0
    assert decision.decision is PopulationDecisionKind.MAINTAIN
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_scoped_test_mode_never_calls_injected_provider(base_world):
    transition = _transition(base_world)
    provider = AsyncMock(side_effect=AssertionError("provider must not be called"))

    with llm_test_mode_scope(True):
        decision, event = await interpret_population_transition(
            base_world,
            transition,
            llm_call=provider,
        )

    assert provider.await_count == 0
    assert decision.decision is PopulationDecisionKind.MAINTAIN
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_invalid_transition_is_rejected(base_world):
    event = Event(base_world.month_stamp, "not a transition", event_type="other")

    with pytest.raises(ValueError, match="semantic_condition_activated"):
        await interpret_population_transition(base_world, event)


def test_population_interpreter_test_mode_fallback_prefers_lower_load_with_capacity():
    assert "population_interpreter" in registered_test_mode_tasks()
    with llm_test_mode_scope(True):
        result = resolve_test_mode_task("population_interpreter", {
            "origin": {"ratio": 0.9},
            "candidates": [{"ratio": 0.4, "population": 40, "capacity": 100}],
        })

    assert result == {
        "decision": "act",
        "reason": "A lower-load city has available capacity.",
        "action_intent": {
            "action_kind": "population_transfer",
            "preferences": ["lower_settlement_load", "available_capacity"],
        },
    }


def test_population_interpreter_test_mode_fallback_maintains_without_candidate_capacity():
    with llm_test_mode_scope(True):
        result = resolve_test_mode_task("population_interpreter", {
            "origin": {"ratio": 0.9},
            "candidates": [{"ratio": 0.4, "population": 100, "capacity": 100}],
        })

    assert result["decision"] == "maintain"
    assert "action_intent" not in result
