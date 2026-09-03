from __future__ import annotations

from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.sim.simulator_engine.phases.world import phase_update_city_population
from tests.test_semantic_world_service import _add_city


def test_domain_invalidation_queue_deduplicates_and_drains_one_layer():
    queue = DomainInvalidationQueue()
    mechanical = DomainInvalidation(
        layer=DomainInvalidationLayer.MECHANICAL,
        domain="population",
        target_kind="region",
        target_id="302",
        reason=DomainInvalidationReason.POPULATION_CHANGED,
    )
    semantic = DomainInvalidation(
        layer=DomainInvalidationLayer.SEMANTIC,
        domain="population",
        target_kind="region",
        target_id="302",
        reason=DomainInvalidationReason.CONDITION_ACTIVATED,
        source_event_ids=("condition-event",),
        revision="condition-event",
    )
    queue.mark(mechanical)
    queue.mark(mechanical)
    queue.mark(semantic)

    assert queue.drain(layer=DomainInvalidationLayer.MECHANICAL) == [mechanical]
    assert queue.drain() == [semantic]


def test_nested_reactivity_consumes_one_shared_causal_budget(base_world):
    base_world.run_config_snapshot = {
        "semantic_evaluation_budget_per_month": 1,
        "domain_interpreter_budget_per_month": 1,
        "causal_propagation_budget_per_month": 1,
        "domain_mutation_budget_per_month": 1,
    }
    budget = CausalBudget.from_world(base_world)

    assert budget.consume_semantic_evaluation() is True
    assert budget.consume_semantic_evaluation() is False
    assert budget.consume_interpreter_call() is True
    assert budget.consume_interpreter_call() is False
    assert budget.consume_propagation_step() is True
    assert budget.consume_propagation_step() is False
    assert budget.consume_domain_mutation() is True
    assert budget.consume_domain_mutation() is False


def test_small_population_change_marks_only_mechanical_dirty_without_public_event(base_world):
    city = _add_city(base_world, 302, 0.50)
    queue = DomainInvalidationQueue()

    events = phase_update_city_population(base_world, invalidations=queue)

    assert events == []
    assert queue.drain() == [
        DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="population",
            target_kind="region",
            target_id=str(city.id),
            reason=DomainInvalidationReason.POPULATION_CHANGED,
            revision=f"population:{city.id}:{base_world.month_stamp}",
        )
    ]
