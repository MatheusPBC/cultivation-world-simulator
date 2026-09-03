from __future__ import annotations

import pytest

from src.classes.environment.city_state import (
    CityDistrict,
    CityState,
    UrbanAsset,
    UrbanPopulationGroup,
    UrbanServiceDemand,
)
from src.classes.environment.region import CityRegion
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    MeasurementAvailability,
    MetricKey,
    PrimitiveDimension,
    ReadingKind,
    evaluate_expression,
)
from src.classes.mechanical_language.expressions import infer_expression_unit
from src.systems.city_interpreter import derive_eligible_capability_ids
from src.systems.semantic_world.condition_semantics import is_regional_adversity
from src.systems.semantic_world.resolvers import (
    available_metric_keys,
    resolve_derived_metric,
    resolve_metric,
)
from src.systems.semantic_world.service import (
    _covered_metric_signatures,
    _discovery_surface_key,
    _metric_leaf_signature,
    _structural_hash,
)
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


SERVICE_QUALIFIERS = (("kind", "urban_service"),)


def _city(
    *,
    population: float = 100.0,
    assets: tuple[UrbanAsset, ...] = (
        UrbanAsset("waterworks", "core", ("clean_water",), 50.0, 1.0, 1.0),
    ),
) -> CityRegion:
    return CityRegion(
        id=501,
        name="Service City",
        desc="",
        cors=[(0, 0)],
        population=population,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=assets,
            service_demands=(UrbanServiceDemand("clean_water", 1.0),),
            population_groups=(
                UrbanPopulationGroup(
                    "priority_group", 0.5, {"clean_water": 2.0}
                ),
                UrbanPopulationGroup("other_group", 0.5, {"clean_water": 1.0}),
            ),
        ),
    )


def _key(dimension: PrimitiveDimension, *, group_id: str | None = None) -> MetricKey:
    return MetricKey(
        dimension,
        "region",
        "501",
        "clean_water",
        group_id=group_id,
        qualifiers=SERVICE_QUALIFIERS,
    )


def test_urban_service_overall_access_and_group_inequality_are_deterministic():
    city = _city()

    overall = resolve_metric(None, _key(PrimitiveDimension.ACCESS), target=city)
    priority = resolve_metric(
        None, _key(PrimitiveDimension.ACCESS, group_id="priority_group"), target=city
    )
    other = resolve_metric(
        None, _key(PrimitiveDimension.ACCESS, group_id="other_group"), target=city
    )

    assert overall.value == pytest.approx(0.5)
    assert priority.value == pytest.approx(2 / 3)
    assert other.value == pytest.approx(1 / 3)
    assert priority.value > other.value
    assert (
        0.5 * priority.value + 0.5 * other.value
    ) == pytest.approx(overall.value)
    assert all(item.reading_kind is ReadingKind.DERIVED for item in (overall, priority, other))


def test_urban_service_capacity_saturates_and_redistributes_surplus():
    city = _city(
        assets=(UrbanAsset("waterworks", "core", ("clean_water",), 80.0, 1.0, 1.0),)
    )

    priority = resolve_metric(
        None, _key(PrimitiveDimension.ACCESS, group_id="priority_group"), target=city
    )
    other = resolve_metric(
        None, _key(PrimitiveDimension.ACCESS, group_id="other_group"), target=city
    )

    assert priority.value == pytest.approx(1.0)
    assert other.value == pytest.approx(0.6)


def test_group_allocation_is_conservative_and_independent_of_group_order():
    city = _city()
    reversed_city = _city()
    reversed_city.city_state.population_groups = tuple(
        reversed(reversed_city.city_state.population_groups)
    )

    readings = {
        group_id: resolve_metric(
            None,
            _key(PrimitiveDimension.ACCESS, group_id=group_id),
            target=city,
        )
        for group_id in ("priority_group", "other_group")
    }
    reversed_readings = {
        group_id: resolve_metric(
            None,
            _key(PrimitiveDimension.ACCESS, group_id=group_id),
            target=reversed_city,
        )
        for group_id in ("priority_group", "other_group")
    }

    assert {
        group_id: reading.value for group_id, reading in readings.items()
    } == pytest.approx({
        group_id: reading.value for group_id, reading in reversed_readings.items()
    })
    allocated = sum(
        100.0 * 0.5 * float(reading.value)
        for reading in readings.values()
    )
    assert allocated == pytest.approx(50.0)


def test_group_allocation_normalizes_extreme_relative_priorities_without_nan():
    city = _city()
    city.city_state.population_groups = (
        UrbanPopulationGroup("priority_group", 0.5, {"clean_water": 1e308}),
        UrbanPopulationGroup("other_group", 0.5, {"clean_water": 1.0}),
    )

    priority = resolve_metric(
        None,
        _key(PrimitiveDimension.ACCESS, group_id="priority_group"),
        target=city,
    )
    other = resolve_metric(
        None,
        _key(PrimitiveDimension.ACCESS, group_id="other_group"),
        target=city,
    )

    assert priority.value == pytest.approx(1.0)
    assert other.value == pytest.approx(0.0)
    assert 50.0 * float(priority.value) + 50.0 * float(other.value) == pytest.approx(
        50.0
    )


def test_declared_service_without_assets_is_measurable_zero_and_zero_load_is_finite():
    city = _city(population=0.0, assets=())

    capacity = resolve_metric(None, _key(PrimitiveDimension.CAPACITY), target=city)
    access = resolve_metric(None, _key(PrimitiveDimension.ACCESS), target=city)

    assert capacity.value == 0.0
    assert capacity.availability is MeasurementAvailability.MEASURABLE
    assert access.value == 1.0
    assert access.availability is MeasurementAvailability.MEASURABLE


def test_undeclared_urban_service_is_unknown():
    city = _city()
    reading = resolve_metric(
        None,
        MetricKey(
            PrimitiveDimension.ACCESS,
            "region",
            "501",
            "security",
            qualifiers=SERVICE_QUALIFIERS,
        ),
        target=city,
    )

    assert reading.value is None
    assert reading.availability is MeasurementAvailability.UNMEASURABLE
    assert reading.reading_kind is ReadingKind.UNKNOWN


def test_unknown_urban_service_qualifier_is_not_given_aggregate_meaning():
    reading = resolve_metric(
        None,
        MetricKey(
            PrimitiveDimension.ACCESS,
            "region",
            "501",
            "clean_water",
            qualifiers=(("access_class", "poor"), ("kind", "urban_service")),
        ),
        target=_city(),
    )

    assert reading.value is None
    assert reading.availability is MeasurementAvailability.UNMEASURABLE
    assert reading.reading_kind is ReadingKind.UNKNOWN
    assert infer_expression_unit(
        {
            "op": "metric",
            "dimension": "access",
            "concept_id": "clean_water",
            "qualifiers": {
                "kind": "urban_service",
                "access_class": "poor",
            },
        },
        require_grounded=False,
    ) is None


def test_group_access_provenance_contains_population_demand_assets_and_profiles():
    reading = resolve_metric(
        None,
        _key(PrimitiveDimension.ACCESS, group_id="priority_group"),
        target=_city(),
    )

    assert "region:501:population" in reading.state_refs
    assert "region:501:urban_service_demand:clean_water" in reading.state_refs
    assert "region:501:urban_asset:waterworks:capacity_quality_integrity" in reading.state_refs
    assert "region:501:urban_population_group:priority_group:profile" in reading.state_refs
    assert "region:501:urban_population_group:other_group:profile" in reading.state_refs
    assert {
        (item["dimension"], item["concept_id"])
        for item in reading.derived_from
    } == {("load", "clean_water"), ("capacity", "clean_water")}


def test_metric_expression_preserves_group_id_in_unit_inference_and_evaluation():
    city = _city()
    expression = {
        "op": "metric",
        "dimension": "access",
        "concept_id": "clean_water",
        "group_id": "priority_group",
        "qualifiers": dict(SERVICE_QUALIFIERS),
    }

    reading = evaluate_expression(
        expression,
        world=None,
        target=city,
        target_kind="region",
    )

    assert reading.value == pytest.approx(2 / 3)
    assert reading.derived_from[0]["group_id"] == "priority_group"
    assert reading.derived_from[0]["qualifiers"] == dict(SERVICE_QUALIFIERS)


def test_resolved_derived_metric_exposes_unambiguous_group_identity():
    definition = DerivedMetricDefinition(
        id="priority_access_deficit",
        concept_id="priority_access_deficit",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "subtract",
            "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
            "right": {
                "op": "metric",
                "dimension": "access",
                "concept_id": "clean_water",
                "group_id": "priority_group",
                "qualifiers": dict(SERVICE_QUALIFIERS),
            },
        },
        unit="ratio",
        created_month=1,
    )

    reading = resolve_derived_metric(
        None,
        definition,
        target=_city(),
        calculated_month=2,
        definitions={definition.id: definition},
    )

    assert reading.key.group_id == "priority_group"
    assert reading.key.qualifiers == SERVICE_QUALIFIERS


def test_service_surface_signatures_and_structural_hash_distinguish_groups():
    group_a = {
        "op": "metric",
        "dimension": "access",
        "concept_id": "clean_water",
        "group_id": "priority_group",
        "qualifiers": dict(SERVICE_QUALIFIERS),
    }
    group_b = {**group_a, "group_id": "other_group"}

    assert _metric_leaf_signature(group_a) != _metric_leaf_signature(group_b)
    assert _structural_hash(group_a, "region") != _structural_hash(group_b, "region")
    assert _discovery_surface_key([_key(PrimitiveDimension.ACCESS, group_id="priority_group")]) != _discovery_surface_key([
        _key(PrimitiveDimension.ACCESS, group_id="other_group")
    ])


def test_covered_signatures_keep_group_specific_surface_uncovered():
    from src.classes.mechanical_language import MechanicalLanguageState

    state = MechanicalLanguageState()
    state.derived_definitions["priority_access"] = DerivedMetricDefinition(
        id="priority_access",
        concept_id="priority_access",
        dimension=PrimitiveDimension.ACCESS,
        target_kind="region",
        expression={
            "op": "metric",
            "dimension": "access",
            "concept_id": "clean_water",
            "group_id": "priority_group",
            "qualifiers": dict(SERVICE_QUALIFIERS),
        },
        unit="ratio",
        created_month=1,
    )

    covered = _covered_metric_signatures(state)
    assert _metric_leaf_signature(state.derived_definitions["priority_access"].expression) in covered
    assert _metric_leaf_signature({
        "op": "metric",
        "dimension": "access",
        "concept_id": "clean_water",
        "group_id": "other_group",
        "qualifiers": dict(SERVICE_QUALIFIERS),
    }) not in covered


def test_urban_service_risk_makes_declared_asset_capability_eligible(base_world):
    city = _city()
    base_world.map.regions[city.id] = city
    metric = DerivedMetricDefinition(
        id="water_access_risk",
        concept_id="water_access_risk",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "subtract",
            "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
            "right": {
                "op": "metric",
                "dimension": "access",
                "concept_id": "clean_water",
                "qualifiers": dict(SERVICE_QUALIFIERS),
            },
        },
        unit="ratio",
        created_month=int(base_world.month_stamp),
    )
    condition = ConditionDefinition(
        id="water_access_condition",
        concept_id="water_access_condition",
        target_kind="region",
        metric_definition_id=metric.id,
        activate_above=0.7,
        resolve_below=0.5,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(base_world.month_stamp),
    )
    base_world.mechanical_language.derived_definitions[metric.id] = metric
    base_world.mechanical_language.condition_definitions[condition.id] = condition
    instance = ConditionInstance(
        id="water-access-instance",
        definition_id=condition.id,
        target_kind="region",
        target_id=str(city.id),
        label="water access risk",
        intensity=0.8,
        started_month=int(base_world.month_stamp),
        cause_event_id="water-risk-event",
    )

    assert derive_eligible_capability_ids(
        base_world, city, instance, city.city_state.assets
    ) == ("clean_water",)


def test_group_specific_urban_risk_does_not_trigger_generic_sect_reaction(base_world):
    metric = DerivedMetricDefinition(
        id="priority_water_risk",
        concept_id="priority_water_risk",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={
            "op": "subtract",
            "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
            "right": {
                "op": "metric",
                "dimension": "access",
                "concept_id": "clean_water",
                "group_id": "priority_group",
                "qualifiers": dict(SERVICE_QUALIFIERS),
            },
        },
        unit="ratio",
        created_month=int(base_world.month_stamp),
    )
    condition = ConditionDefinition(
        id="priority_water_condition",
        concept_id="priority_water_condition",
        target_kind="region",
        metric_definition_id=metric.id,
        activate_above=0.7,
        resolve_below=0.5,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(base_world.month_stamp),
    )
    base_world.mechanical_language.derived_definitions[metric.id] = metric
    base_world.mechanical_language.condition_definitions[condition.id] = condition

    assert is_regional_adversity(base_world, condition.id) is False


def test_indirect_group_specific_risk_does_not_trigger_generic_sect_reaction(
    base_world,
):
    base_world.mechanical_language.derived_definitions["group_access"] = (
        DerivedMetricDefinition(
            id="group_access",
            concept_id="group_access",
            dimension=PrimitiveDimension.ACCESS,
            target_kind="region",
            expression={
                "op": "metric",
                "dimension": "access",
                "concept_id": "clean_water",
                "group_id": "priority_group",
                "qualifiers": dict(SERVICE_QUALIFIERS),
            },
            unit="ratio",
            created_month=int(base_world.month_stamp),
        )
    )
    base_world.mechanical_language.derived_definitions["indirect_group_risk"] = (
        DerivedMetricDefinition(
            id="indirect_group_risk",
            concept_id="indirect_group_risk",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": {"op": "derived", "definition_id": "group_access"},
            },
            unit="ratio",
            created_month=int(base_world.month_stamp),
        )
    )
    condition = ConditionDefinition(
        id="indirect_group_condition",
        concept_id="indirect_group_condition",
        target_kind="region",
        metric_definition_id="indirect_group_risk",
        activate_above=0.7,
        resolve_below=0.5,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(base_world.month_stamp),
    )
    base_world.mechanical_language.condition_definitions[condition.id] = condition

    assert is_regional_adversity(base_world, condition.id) is False


def test_test_mode_discovery_is_provider_free_and_group_ids_do_not_collide():
    result_a = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [
                {
                    "dimension": "access",
                    "concept_id": "clean_water",
                    "group_id": "priority_group",
                    "qualifiers": dict(SERVICE_QUALIFIERS),
                    "unit": "ratio",
                }
            ]
        },
    )
    result_b = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [
                {
                    "dimension": "access",
                    "concept_id": "clean_water",
                    "group_id": "other_group",
                    "qualifiers": dict(SERVICE_QUALIFIERS),
                    "unit": "ratio",
                }
            ]
        },
    )

    expression_a = result_a["derived_metrics"][0]["expression"]
    expression_b = result_b["derived_metrics"][0]["expression"]
    assert expression_a["right"]["group_id"] == "priority_group"
    assert expression_b["right"]["group_id"] == "other_group"
    assert result_a["derived_metrics"][0]["id"] != result_b["derived_metrics"][0]["id"]
    assert result_a["conditions"][0]["id"] != result_b["conditions"][0]["id"]


def test_available_service_surface_contains_aggregate_and_group_access_keys():
    keys = available_metric_keys(None, _city())
    service_keys = [key for key in keys if key.qualifiers == SERVICE_QUALIFIERS]

    assert {key.dimension for key in service_keys} == {
        PrimitiveDimension.LOAD,
        PrimitiveDimension.CAPACITY,
        PrimitiveDimension.ACCESS,
    }
    assert {
        key.group_id for key in service_keys if key.dimension is PrimitiveDimension.ACCESS
    } == {None, "priority_group", "other_group"}


def test_test_mode_discovers_grounded_health_recovery_strain_composite():
    result = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [
                {
                    "dimension": "risk",
                    "concept_id": "injury_burden",
                    "qualifiers": {"kind": "collective_health"},
                    "unit": "ratio",
                },
                {
                    "dimension": "access",
                    "concept_id": "healing",
                    "qualifiers": {"kind": "urban_service"},
                    "unit": "ratio",
                },
            ]
        },
    )

    metric = result["derived_metrics"][0]
    condition = result["conditions"][0]
    assert metric["id"] == "health_recovery_strain"
    assert metric["expression"] == {
        "op": "clamp",
        "min": 0.0,
        "max": 1.0,
        "value": {
            "op": "multiply",
            "left": {
                "op": "metric",
                "dimension": "risk",
                "concept_id": "injury_burden",
                "qualifiers": {"kind": "collective_health"},
            },
            "right": {
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": {
                    "op": "metric",
                    "dimension": "access",
                    "concept_id": "healing",
                    "qualifiers": {"kind": "urban_service"},
                },
            },
        },
    }
    assert condition == {
        "id": "strained_health_recovery",
        "concept_id": "strained_health_recovery",
        "target_kind": "region",
        "metric_definition_id": "health_recovery_strain",
        "activate_above": 0.20,
        "resolve_below": 0.05,
        "activate_after_months": 2,
        "resolve_after_months": 2,
    }
