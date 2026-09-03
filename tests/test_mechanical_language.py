import math

import pytest

from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import (
    ConditionDefinition,
    DerivedMetricDefinition,
    ExpressionValidationError,
    Grounding,
    GroundingStatus,
    MechanicalLanguageState,
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
    evaluate_expression,
    validate_expression,
)
from src.classes.mechanical_language.expressions import infer_expression_unit
from src.systems.semantic_world.resolvers import resolve_metric
from src.config.settings_schema import RunConfig


def _city(region_id: int = 302, *, population: float = 90.0, capacity: float = 100.0) -> CityRegion:
    return CityRegion(
        id=region_id,
        name=f"City {region_id}",
        desc="",
        cors=[(0, 0)],
        population=population,
        population_capacity=capacity,
    )


def test_primitive_set_v1_is_closed_and_versioned():
    assert {item.value for item in PrimitiveDimension} == {
        "stock",
        "flow",
        "load",
        "capacity",
        "access",
        "quality",
        "risk",
        "influence",
        "dependency",
    }

    state = MechanicalLanguageState()
    assert state.language_version == 1
    assert MechanicalLanguageState.from_dict(state.to_dict()).language_version == 1


def test_mechanical_language_persistence_requires_explicit_current_version():
    with pytest.raises(KeyError, match="language_version"):
        MechanicalLanguageState.from_dict({})

    with pytest.raises(TypeError, match="mapping"):
        MechanicalLanguageState.from_dict(None)  # type: ignore[arg-type]


def test_semantic_guardrails_are_run_configuration_not_world_laws():
    config = RunConfig()

    assert config.semantic_discovery_budget_per_month == 2
    assert config.semantic_evaluation_budget_per_month == 256
    assert config.semantic_max_ast_nodes == 32
    assert config.semantic_max_ast_depth == 8
    assert config.semantic_dormant_after_months == 24
    assert config.semantic_discovery_retry_after_months == 12


def test_metric_key_is_resolved_from_canonical_city_state():
    city = _city(population=90.0, capacity=100.0)

    load = resolve_metric(None, MetricKey(PrimitiveDimension.LOAD, "region", "302", "settlement"), target=city)
    capacity = resolve_metric(None, MetricKey(PrimitiveDimension.CAPACITY, "region", "302", "settlement"), target=city)

    assert load.value == 90.0
    assert load.reading_kind is ReadingKind.EXACT
    assert load.availability is MeasurementAvailability.MEASURABLE
    assert load.state_refs == ["region:302:population"]
    assert capacity.value == 100.0
    assert capacity.state_refs == ["region:302:population_capacity"]


def test_unsupported_metric_is_unmeasurable_unknown_not_a_guessed_number():
    reading = resolve_metric(
        None,
        MetricKey(PrimitiveDimension.ACCESS, "region", "302", "healing"),
        target=_city(),
    )

    assert reading.value is None
    assert reading.reading_kind is ReadingKind.UNKNOWN
    assert reading.availability is MeasurementAvailability.UNMEASURABLE
    assert reading.confidence is None


def test_derived_expression_is_validated_and_keeps_metric_provenance():
    city = _city()
    expression = {
        "op": "divide",
        "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
        "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
    }
    validate_expression(expression, max_nodes=32, max_depth=8)

    reading = evaluate_expression(expression, world=None, target=city, target_kind="region")

    assert reading.value == pytest.approx(0.9)
    assert reading.reading_kind is ReadingKind.DERIVED
    assert reading.availability is MeasurementAvailability.MEASURABLE
    assert {item["dimension"] for item in reading.derived_from} == {"load", "capacity"}
    assert reading.state_refs == ["region:302:population", "region:302:population_capacity"]


def test_expression_units_allow_settlement_ratio_and_preserve_clamp_unit():
    settlement_load = {"op": "metric", "dimension": "load", "concept_id": "settlement"}
    settlement_capacity = {"op": "metric", "dimension": "capacity", "concept_id": "settlement"}

    assert infer_expression_unit({"op": "divide", "left": settlement_load, "right": settlement_capacity}) == "ratio"
    assert infer_expression_unit({"op": "clamp", "value": settlement_load, "min": 0, "max": 100}) == "ten_thousand_people"
    assert infer_expression_unit({"op": "add", "left": settlement_load, "right": settlement_capacity}) == "ten_thousand_people"
    assert infer_expression_unit({
        "op": "multiply",
        "left": {"op": "constant", "value": 2},
        "right": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
    }) == "ten_thousand_people"
    reading = evaluate_expression(
        {"op": "clamp", "value": settlement_load, "min": 0, "max": 100},
        world=None,
        target=_city(population=120.0),
        target_kind="region",
    )
    assert reading.value == 100.0
    assert reading.unit == "ten_thousand_people"


@pytest.mark.parametrize("operator", ["add", "subtract", "min", "max"])
def test_expression_units_reject_incompatible_binary_operations(operator):
    with pytest.raises(ExpressionValidationError, match="incompatible expression units"):
        infer_expression_unit({
            "op": operator,
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "stock", "concept_id": "spirit_stone"},
        })


def test_expression_units_require_weighted_sum_items_to_match():
    with pytest.raises(ExpressionValidationError, match="incompatible expression units"):
        infer_expression_unit({
            "op": "weighted_sum",
            "items": [
                {"weight": 0.5, "expression": {"op": "metric", "dimension": "load", "concept_id": "settlement"}},
                {"weight": 0.5, "expression": {"op": "metric", "dimension": "stock", "concept_id": "spirit_stone"}},
            ],
        })


@pytest.mark.parametrize("operator", ["multiply", "divide"])
def test_expression_units_reject_nonsensical_combinations(operator):
    with pytest.raises(ExpressionValidationError, match="incompatible expression units"):
        infer_expression_unit({
            "op": operator,
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "stock", "concept_id": "spirit_stone"},
        })


def test_unknown_leaf_cannot_be_registered_as_grounded_definition():
    state = MechanicalLanguageState()

    with pytest.raises(ExpressionValidationError, match="unknown or unmeasurable"):
        state.add_derived_definition(DerivedMetricDefinition(
            id="healing_access_gap",
            concept_id="healing_access_gap",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={"op": "metric", "dimension": "risk", "concept_id": "healing"},
            unit="ratio",
            created_month=1,
        ))


def test_dynamic_metric_key_round_trips_relationship_group_and_qualifiers():
    from src.classes.mechanical_language import EntityRef, MetricKey

    key = MetricKey(
        PrimitiveDimension.ACCESS,
        "region",
        "302",
        "healing",
        related=EntityRef("sect", "17"),
        group_id="poor",
        qualifiers=(("mode", "public"), ("tier", "mortal")),
    )

    assert MetricKey.from_dict(key.to_dict()) == key
    assert key.qualifier("tier") == "mortal"


def test_dynamic_bound_economy_leaf_has_unit_without_hardcoded_concept():
    assert infer_expression_unit({
        "op": "metric",
        "dimension": "stock",
        "concept_id": "black_lotus_seed",
    }) == "units"
    assert infer_expression_unit({
        "op": "metric",
        "dimension": "flow",
        "concept_id": "black_lotus_seed",
        "qualifiers": {"kind": "production"},
    }) == "units_per_month"


def test_ratio_constant_can_express_complement_without_new_story_rule():
    expression = {
        "op": "subtract",
        "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
        "right": {
            "op": "metric",
            "dimension": "quality",
            "concept_id": "black_lotus_healing",
        },
    }

    validate_expression(expression, max_nodes=32, max_depth=8)
    assert infer_expression_unit(expression) == "ratio"

    with pytest.raises(ExpressionValidationError, match="scalar or ratio"):
        validate_expression(
            {"op": "constant", "value": 1.0, "unit": "spirit_stone"},
            max_nodes=32,
            max_depth=8,
        )


def test_reaction_receipts_are_idempotent_per_domain_and_round_trip():
    from src.classes.mechanical_language import DomainReactionReceipt

    state = MechanicalLanguageState()
    population = DomainReactionReceipt.create(
        "condition-1",
        "population",
        "activation-event",
        decision_event_ids=("population-decision",),
        completed=True,
    )
    economy = DomainReactionReceipt.create(
        "condition-1",
        "economy",
        "activation-event",
        decision_event_ids=("economy-decision",),
        completed=True,
    )
    state.reaction_receipts[population.id] = population
    state.reaction_receipts[economy.id] = economy

    restored = MechanicalLanguageState.from_dict(state.to_dict())

    assert set(restored.reaction_receipts) == {population.id, economy.id}


def test_definition_unit_must_match_expression_unit():
    with pytest.raises(ExpressionValidationError, match="does not match inferred unit"):
        MechanicalLanguageState().add_derived_definition(DerivedMetricDefinition(
            id="settlement_density_pressure",
            concept_id="settlement_density_pressure",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "divide",
                "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
                "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
            },
            unit="ten_thousand_people",
            created_month=1,
        ))


def test_invalid_definition_does_not_mutate_existing_registry():
    state = MechanicalLanguageState()
    valid = DerivedMetricDefinition(
        id="settlement_density_pressure",
        concept_id="settlement_density_pressure",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "divide",
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
        },
        unit="ratio",
        created_month=1,
    )
    state.add_derived_definition(valid)
    before = state.to_dict()

    with pytest.raises(ExpressionValidationError):
        state.add_derived_definition(DerivedMetricDefinition(
            id="broken_metric",
            concept_id="broken_metric",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "add",
                "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
                "right": {"op": "metric", "dimension": "stock", "concept_id": "spirit_stone"},
            },
            unit="ten_thousand_people",
            created_month=1,
        ))

    assert state.to_dict() == before


def test_pending_semantic_provenance_survives_round_trip():
    state = MechanicalLanguageState(
        pending_source_event_ids={
            "settlement_density_pressure|region:302": ["population-event"],
        },
        pending_affinity_source_event_ids={
            "region:302": {
                "urban_service:healing": ["healing-maintenance-event"],
            }
        },
    )

    loaded = MechanicalLanguageState.from_dict(state.to_dict())

    assert loaded.pending_source_event_ids == state.pending_source_event_ids
    assert (
        loaded.pending_affinity_source_event_ids
        == state.pending_affinity_source_event_ids
    )


def test_registry_rejects_duplicate_ids_missing_references_and_invalid_loaded_data():
    state = MechanicalLanguageState()
    valid = DerivedMetricDefinition(
        id="settlement_density_pressure",
        concept_id="settlement_density_pressure",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "divide",
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
        },
        unit="ratio",
        created_month=1,
    )
    state.add_derived_definition(valid)

    with pytest.raises(ExpressionValidationError, match="duplicate derived metric id"):
        state.add_derived_definition(valid)
    with pytest.raises(ExpressionValidationError, match="unknown derived metric reference"):
        state.add_derived_definition(DerivedMetricDefinition(
            id="broken_reference",
            concept_id="broken_reference",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={"op": "derived", "definition_id": "missing"},
            unit="ratio",
            created_month=1,
        ))
    with pytest.raises(ValueError, match="unknown metric definition"):
        state.add_condition_definition(ConditionDefinition(
            id="broken_condition",
            concept_id="broken_condition",
            target_kind="region",
            metric_definition_id="missing",
            activate_above=0.8,
            resolve_below=0.7,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=1,
        ))

    payload = state.to_dict()
    payload["derived_definitions"][valid.id]["unit"] = "spirit_stone"
    with pytest.raises(ExpressionValidationError, match="does not match inferred unit"):
        MechanicalLanguageState.from_dict(payload)


def test_persisted_registries_reject_duplicate_internal_ids():
    state = MechanicalLanguageState()
    metric = DerivedMetricDefinition(
        id="settlement_density_pressure",
        concept_id="settlement_density_pressure",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "divide",
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
        },
        unit="ratio",
        created_month=1,
    )
    state.add_derived_definition(metric)
    condition = ConditionDefinition(
        id="overcrowded_settlement",
        concept_id="overcrowded_settlement",
        target_kind="region",
        metric_definition_id=metric.id,
        activate_above=0.85,
        resolve_below=0.75,
        activate_after_months=2,
        resolve_after_months=2,
        created_month=1,
    )
    state.add_condition_definition(condition)

    metric_payload = state.to_dict()
    metric_payload["derived_definitions"]["duplicate-key"] = metric.to_dict()
    with pytest.raises(ValueError, match="duplicate persisted derived_definitions id"):
        MechanicalLanguageState.from_dict(metric_payload)

    condition_payload = state.to_dict()
    condition_payload["condition_definitions"]["duplicate-key"] = condition.to_dict()
    with pytest.raises(ValueError, match="duplicate persisted condition_definitions id"):
        MechanicalLanguageState.from_dict(condition_payload)


@pytest.mark.parametrize("invalid", [True, math.nan, math.inf, -math.inf])
def test_expression_rejects_non_finite_or_boolean_numbers(invalid):
    with pytest.raises(ExpressionValidationError):
        validate_expression({"op": "constant", "value": invalid}, max_nodes=32, max_depth=8)


def test_grounding_is_typed_and_persisted_separately_from_measurements():
    grounding = Grounding(
        id="grounding-density-302",
        concept_id="settlement_density_pressure",
        subject_kind="region",
        subject_id="302",
        dimension=PrimitiveDimension.RISK,
        metric_definition_id="settlement_density_pressure",
        evidence_refs=("region:302:population", "region:302:population_capacity"),
        status=GroundingStatus.GROUNDED,
        created_month=12,
    )
    state = MechanicalLanguageState(groundings={grounding.id: grounding})

    restored = MechanicalLanguageState.from_dict(state.to_dict())

    assert restored.groundings[grounding.id] == grounding


def test_expression_rejects_arbitrary_code_and_cycles():
    with pytest.raises(ExpressionValidationError):
        validate_expression({"op": "python", "code": "population -= 50"}, max_nodes=32, max_depth=8)

    payload = MechanicalLanguageState().to_dict()
    payload["derived_definitions"] = {
        "a": DerivedMetricDefinition(
            id="a",
            concept_id="a",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={"op": "derived", "definition_id": "b"},
            unit="ratio",
            created_month=1,
        ).to_dict(),
        "b": DerivedMetricDefinition(
            id="b",
            concept_id="b",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={"op": "derived", "definition_id": "a"},
            unit="ratio",
            created_month=1,
        ).to_dict(),
    }
    with pytest.raises(ExpressionValidationError, match="dependency cycle"):
        MechanicalLanguageState.from_dict(payload)


def test_condition_definition_and_instance_are_distinct_persisted_types():
    state = MechanicalLanguageState()
    state.add_derived_definition(DerivedMetricDefinition(
        id="settlement_density_pressure",
        concept_id="settlement_density_pressure",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "divide",
            "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
            "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
        },
        unit="ratio",
        created_month=1,
    ))
    definition = ConditionDefinition(
        id="overcrowded_settlement",
        concept_id="overcrowded_settlement",
        target_kind="region",
        metric_definition_id="settlement_density_pressure",
        activate_above=0.85,
        resolve_below=0.75,
        activate_after_months=2,
        resolve_after_months=2,
        created_month=1,
    )
    state.add_condition_definition(definition)

    restored = MechanicalLanguageState.from_dict(state.to_dict())

    assert restored.condition_definitions[definition.id] == definition
    assert restored.condition_instances == {}
