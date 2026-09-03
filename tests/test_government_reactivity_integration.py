import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
)
from src.systems.government_reactivity import (
    enqueue_government_transitions,
    enqueue_unreacted_government_conditions,
    process_government_reactivity,
)
from tests.test_government_interpreter import _setup


@pytest.mark.asyncio
async def test_government_reactivity_executes_once_and_persists_government_receipt(
    base_world,
):
    city, trigger, condition = _setup(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()

    enqueue_government_transitions(base_world, [trigger], queue)
    assert (
        len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="government"))
        == 1
    )
    enqueue_government_transitions(base_world, [trigger], queue)
    events = await process_government_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert [event.event_type for event in events] == [
        "government_interpretation_decision",
        "city_maintenance_completed",
    ]
    assert city.city_state.assets[0].integrity > 0.5
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.domain == "government:1"
    assert receipt.trigger_revision == trigger.id
    assert receipt.completed is True
    assert receipt.condition_instance_id == condition.id
    assert (
        await process_government_reactivity(
            base_world,
            current_events=[trigger],
            invalidations=queue,
            budget=CausalBudget.from_world(base_world),
        )
        == []
    )


def test_government_reactivity_requires_matching_controller(base_world):
    _, trigger, _ = _setup(base_world, controller_id="other-dynasty")
    queue = DomainInvalidationQueue()

    enqueue_government_transitions(base_world, [trigger], queue)

    assert (
        queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="government") == []
    )


@pytest.mark.asyncio
async def test_government_budget_zero_preserves_trigger(base_world):
    _, trigger, _ = _setup(base_world)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "government_reaction_evaluation_budget_per_month": 0,
    }
    queue = DomainInvalidationQueue()
    enqueue_government_transitions(base_world, [trigger], queue)

    assert (
        await process_government_reactivity(
            base_world,
            current_events=[trigger],
            invalidations=queue,
            budget=CausalBudget.from_world(base_world),
        )
        == []
    )
    assert (
        len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="government"))
        == 1
    )


@pytest.mark.asyncio
async def test_government_blocked_maintenance_retries_without_repeating_decision(
    base_world,
):
    _, trigger, condition = _setup(base_world, integrity=1.0)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()
    enqueue_government_transitions(base_world, [trigger], queue)

    events = await process_government_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert events[-1].event_type == "city_maintenance_blocked"
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.domain == "government:1"
    assert receipt.completed is False
    assert receipt.next_eligible_month == int(base_world.month_stamp) + 1
    assert receipt.condition_instance_id == condition.id


@pytest.mark.asyncio
async def test_government_unreacted_enqueue_skips_completed_receipt(base_world):
    _, trigger, condition = _setup(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()
    enqueue_government_transitions(base_world, [trigger], queue)
    await process_government_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    enqueue_unreacted_government_conditions(base_world, queue)

    assert (
        queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="government") == []
    )
    world_condition = base_world.mechanical_language.get_active_conditions(
        EntityRef("region", "301"), int(base_world.month_stamp)
    )
    assert world_condition
    assert world_condition[0].id == condition.id
