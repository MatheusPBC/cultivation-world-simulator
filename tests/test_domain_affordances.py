from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.domain_affordance import (
    DomainAffordance,
    DomainDecisionKind,
)
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import ConditionInstance, EntityRef
from src.systems.collective_affordances import population_affordances
from src.systems.domain_affordance_registry import (
    AffordanceContext,
    DomainAffordanceRegistry,
    StaleAffordanceError,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.utils.llm.exceptions import LLMError, ProviderCallError, ProviderFailureKind
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _option(trigger: Event, *, urgency: float = 0.8) -> DomainAffordance:
    return DomainAffordance(
        domain="test-domain",
        actor_ref=EntityRef("organization", "actor-1"),
        action_kind="repair",
        target_refs=(EntityRef("site", "bridge-1"),),
        parameters={"amount": 4.0},
        urgency=urgency,
        motivation_event_ids=(trigger.id,),
    )


def test_affordance_id_is_deterministic_and_parameters_are_immutable(base_world):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    first = _option(trigger)
    second = _option(trigger)

    assert first.id == second.id
    assert first.id.startswith("aff-")
    with pytest.raises(TypeError):
        first.parameters["amount"] = 9.0


@pytest.mark.asyncio
async def test_interpreter_exposes_only_ids_and_rejects_invented_id(base_world):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    option = _option(trigger)
    provider = AsyncMock(
        return_value={
            "decision": "act",
            "reason": "invent a target",
            "selected_affordance_id": "aff-invented",
        }
    )

    decision, event = await interpret_domain_affordances(
        base_world,
        domain=option.domain,
        actor_ref=option.actor_ref,
        actor_label="Actor",
        trigger_event=trigger,
        affordances=(option,),
        task_name="test",
        template_name="population_interpreter.txt",
        llm_call=provider,
    )

    assert decision.decision is DomainDecisionKind.MAINTAIN
    assert decision.selected_affordance_id is None
    assert event.fact_kind is FactKind.DECISION
    assert event.causal_payload["decision"]["source"] == "llm_rejected"
    assert event.causal_payload["deltas"] == []


@pytest.mark.asyncio
async def test_no_affordance_records_deterministic_receipt_without_llm(base_world):
    trigger = Event(base_world.month_stamp, "observation", id="observation-1")
    provider = AsyncMock(side_effect=AssertionError("provider must not run"))

    decision, event = await interpret_domain_affordances(
        base_world,
        domain="test-domain",
        actor_ref=EntityRef("organization", "actor-1"),
        actor_label="Actor",
        trigger_event=trigger,
        affordances=(),
        task_name="test",
        template_name="population_interpreter.txt",
        llm_call=provider,
    )

    assert provider.await_count == 0
    assert decision.decision is DomainDecisionKind.MAINTAIN
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        LLMError("provider retries exhausted"),
        ProviderCallError(ProviderFailureKind.NETWORK, "connection refused"),
    ],
    ids=["llm-error", "provider-call-error"],
)
async def test_provider_failure_maintains_even_for_high_urgency_affordance(
    base_world, failure
):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    option = _option(trigger, urgency=1.0)
    provider = AsyncMock(side_effect=failure)

    decision, event = await interpret_domain_affordances(
        base_world,
        domain=option.domain,
        actor_ref=option.actor_ref,
        actor_label="Actor",
        trigger_event=trigger,
        affordances=(option,),
        task_name="test",
        template_name="population_interpreter.txt",
        llm_call=provider,
    )

    assert provider.await_count == 1
    assert decision.decision is DomainDecisionKind.MAINTAIN
    assert decision.selected_affordance_id is None
    assert event.causal_payload["decision"]["source"] == "rule"


@pytest.mark.asyncio
async def test_test_mode_still_uses_conservative_highest_urgency_rule(
    base_world,
):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    lower = _option(trigger, urgency=0.8)
    higher = DomainAffordance(
        domain=lower.domain,
        actor_ref=lower.actor_ref,
        action_kind="repair",
        target_refs=(EntityRef("site", "bridge-2"),),
        parameters={"amount": 5.0},
        urgency=1.0,
        motivation_event_ids=(trigger.id,),
    )
    provider = AsyncMock(side_effect=AssertionError("test mode must not call provider"))

    with llm_test_mode_scope(True):
        decision, event = await interpret_domain_affordances(
            base_world,
            domain=lower.domain,
            actor_ref=lower.actor_ref,
            actor_label="Actor",
            trigger_event=trigger,
            affordances=(lower, higher),
            task_name="test",
            template_name="population_interpreter.txt",
            llm_call=provider,
        )

    assert provider.await_count == 0
    assert decision.decision is DomainDecisionKind.ACT
    assert decision.selected_affordance_id == higher.id
    assert event.causal_payload["decision"]["source"] == "rule"


def test_registry_recomposes_and_blocks_a_stale_selection(base_world):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    context = AffordanceContext(
        base_world,
        "test-domain",
        EntityRef("organization", "actor-1"),
        trigger,
    )
    state = {"available": True}
    registry = DomainAffordanceRegistry()
    registry.register_provider(
        "test-domain", lambda _: (_option(trigger),) if state["available"] else ()
    )
    registry.register_executor("repair", lambda *_args, **_kwargs: trigger)
    selected = registry.compose(context)[0]

    state["available"] = False

    with pytest.raises(StaleAffordanceError, match="absent or stale"):
        registry.execute(context, selected.id)


@pytest.mark.asyncio
async def test_registry_execute_async_revalidates_and_awaits_async_executor(base_world):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    context = AffordanceContext(
        base_world,
        "test-domain",
        EntityRef("organization", "actor-1"),
        trigger,
    )
    state = {"available": True}
    registry = DomainAffordanceRegistry()
    registry.register_provider(
        "test-domain", lambda _: (_option(trigger),) if state["available"] else ()
    )
    executor = AsyncMock(return_value=trigger)
    registry.register_executor("repair", executor)
    selected = registry.compose(context)[0]

    assert await registry.execute_async(context, selected.id) is trigger
    assert executor.await_count == 1

    state["available"] = False
    with pytest.raises(StaleAffordanceError, match="absent or stale"):
        await registry.execute_async(context, selected.id)
    assert executor.await_count == 1


@pytest.mark.asyncio
async def test_registry_execute_async_adapts_sync_executor(base_world):
    trigger = Event(base_world.month_stamp, "damage", id="damage-1")
    context = AffordanceContext(
        base_world,
        "test-domain",
        EntityRef("organization", "actor-1"),
        trigger,
    )
    registry = DomainAffordanceRegistry()
    registry.register_provider("test-domain", lambda _: (_option(trigger),))
    registry.register_executor("repair", lambda *_args, **_kwargs: trigger)
    selected = registry.compose(context)[0]

    assert await registry.execute_async(context, selected.id) is trigger


def test_population_affordance_is_condition_agnostic_and_bounded(base_world):
    origin = CityRegion(
        1,
        "Origin",
        "",
        population=100,
        population_capacity=100,
        cors=[(0, 0)],
    )
    destination = CityRegion(
        2,
        "Destination",
        "",
        population=70,
        population_capacity=100,
        cors=[(1, 0)],
    )
    base_world.map.regions = {1: origin, 2: destination}
    base_world.map.set_routes([Route("route-1-2", (1, 2), "road", 50, 1.0, True)])
    trigger = Event(base_world.month_stamp, "pressure", id="condition-event")
    condition = ConditionInstance(
        "condition-instance",
        "any-grounded-pressure",
        "region",
        "1",
        "pressure",
        0.9,
        int(base_world.month_stamp),
        trigger.id,
    )
    context = AffordanceContext(
        base_world,
        "population",
        EntityRef("population", "region:1"),
        trigger,
        condition,
    )

    options = population_affordances(context)

    assert len(options) == 1
    assert options[0].action_kind == "population_transfer"
    assert 0 < options[0].parameters["amount"] <= 20
    assert destination.population + options[0].parameters["amount"] <= 85
