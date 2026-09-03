import pytest

from src.config.settings_schema import RunConfig
from src.classes.domain_proposal import (
    PopulationTransferIntentProposal,
    PopulationDecision,
    PopulationDecisionKind,
    PopulationIntentKind,
    PopulationPreference,
)
from src.classes.mechanical_language import (
    ConditionDefinition,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.phases.world import phase_update_city_population
from src.systems.semantic_world.condition_semantics import is_settlement_pressure

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


def test_settlement_pressure_helper_uses_metric_leaves_not_definition_ids(base_world):
    base_world.mechanical_language.derived_definitions["metric-arbitrary"] = (
        DerivedMetricDefinition(
            id="metric-arbitrary",
            concept_id="density-with-a-different-name",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "divide",
                "left": {
                    "op": "metric",
                    "dimension": "load",
                    "concept_id": "settlement",
                },
                "right": {
                    "op": "max",
                    "left": {
                        "op": "metric",
                        "dimension": "capacity",
                        "concept_id": "settlement",
                    },
                    "right": {"op": "constant", "value": 1, "unit": "scalar"},
                },
            },
            unit="ratio",
            created_month=1,
        )
    )
    base_world.mechanical_language.condition_definitions["condition-arbitrary"] = (
        ConditionDefinition(
            id="condition-arbitrary",
            concept_id="unrelated-label",
            target_kind="region",
            metric_definition_id="metric-arbitrary",
            activate_above=0.85,
            resolve_below=0.75,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=1,
        )
    )

    assert is_settlement_pressure(base_world, "condition-arbitrary") is True


@pytest.mark.parametrize(
    ("target_kind", "expression"),
    [
        (
            "region",
            {
                "op": "metric",
                "dimension": "load",
                "concept_id": "settlement",
            },
        ),
        (
            "region",
            {
                "op": "divide",
                "left": {
                    "op": "metric",
                    "dimension": "load",
                    "concept_id": "settlement",
                },
                "right": {
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": "grain",
                },
            },
        ),
        (
            "organization",
            {
                "op": "divide",
                "left": {
                    "op": "metric",
                    "dimension": "load",
                    "concept_id": "settlement",
                },
                "right": {
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": "settlement",
                },
            },
        ),
    ],
)
def test_settlement_pressure_helper_rejects_unrelated_conditions(
    base_world,
    target_kind,
    expression,
):
    base_world.mechanical_language.derived_definitions["metric-false-positive"] = (
        DerivedMetricDefinition(
            id="metric-false-positive",
            concept_id="not-settlement-pressure",
            dimension=PrimitiveDimension.RISK,
            target_kind=target_kind,
            expression=expression,
            unit="ratio",
            created_month=1,
        )
    )
    base_world.mechanical_language.condition_definitions["condition-arbitrary"] = (
        ConditionDefinition(
            id="condition-arbitrary",
            concept_id="another-unrelated-label",
            target_kind=target_kind,
            metric_definition_id="metric-false-positive",
            activate_above=0.85,
            resolve_below=0.75,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=1,
        )
    )

    assert is_settlement_pressure(base_world, "condition-arbitrary") is False


def test_population_reactivity_limits_are_run_configuration():
    config = RunConfig()

    assert config.population_interpreter_llm_budget_per_month == 2
    assert config.population_reaction_evaluation_budget_per_month == 8
    assert config.population_transfer_max_fraction_per_reaction == 0.20
    assert config.population_failed_transfer_retry_after_months == 12
    assert config.domain_interpreter_budget_per_month == 8
    assert config.causal_propagation_budget_per_month == 32
    assert config.domain_mutation_budget_per_month == 32


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


def test_action_intent_is_typed_and_contains_no_world_delta_or_amount():
    intent = PopulationTransferIntentProposal(
        action_kind=PopulationIntentKind.POPULATION_TRANSFER,
        subject_kind="population",
        subject_id="region:302",
        motivation_event_ids=("condition-event",),
        preferences=(
            PopulationPreference.LOWER_SETTLEMENT_LOAD,
            PopulationPreference.AVAILABLE_CAPACITY,
        ),
        reason="Seek a less pressured settlement.",
    )

    payload = intent.to_dict()

    assert payload["proposal_type"] == "action_intent"
    assert payload["action_kind"] == "population_transfer"
    assert "amount" not in payload
    assert "destination" not in payload
    assert "deltas" not in payload
    assert PopulationTransferIntentProposal.from_dict(payload) == intent


def test_population_decision_requires_intent_only_when_acting():
    with pytest.raises(ValueError, match="requires an action intent"):
        PopulationDecision(decision=PopulationDecisionKind.ACT, reason="leave")

    intent = PopulationTransferIntentProposal(
        action_kind=PopulationIntentKind.POPULATION_TRANSFER,
        subject_kind="population",
        subject_id="region:302",
        motivation_event_ids=("condition-event",),
    )
    with pytest.raises(ValueError, match="cannot carry an action intent"):
        PopulationDecision(
            decision=PopulationDecisionKind.MAINTAIN,
            reason="pressure is tolerable",
            action_intent=intent,
        )

    maintain = PopulationDecision(
        decision=PopulationDecisionKind.MAINTAIN,
        reason="pressure is tolerable",
    )
    assert maintain.to_dict() == {
        "decision": "maintain",
        "reason": "pressure is tolerable",
        "action_intent": None,
    }


def test_small_population_change_marks_only_mechanical_dirty_without_public_event(base_world):
    city = _add_city(base_world, 302, 0.50)
    queue = DomainInvalidationQueue()

    events = phase_update_city_population(base_world, invalidations=queue)

    assert events == []
    dirty = queue.drain()
    assert dirty == [DomainInvalidation(
        layer=DomainInvalidationLayer.MECHANICAL,
        domain="population",
        target_kind="region",
        target_id=str(city.id),
        reason=DomainInvalidationReason.POPULATION_CHANGED,
        revision=f"population:{city.id}:{base_world.month_stamp}",
    )]
