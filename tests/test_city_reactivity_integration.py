import pytest
from types import SimpleNamespace

from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
)
from src.classes.environment.region import CityRegion
from src.classes.regional_economy import RegionalEconomyState
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
)
from src.systems.city_reactivity import (
    enqueue_city_transitions,
    process_city_reactivity,
)
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    advance_urban_capacity_projects,
)
from src.systems.time import MonthStamp


def _setup(
    world,
    *,
    risk_dimension=PrimitiveDimension.RISK,
    quality=True,
    admin=0.8,
    integrity=0.5,
):
    city = CityRegion(
        id=301,
        name="Border City",
        desc="",
        cors=[(0, 0)],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, 0.4, integrity),)
            if quality
            else (),
            governance=CityGovernance("", "", admin),
        ),
    )
    world.map.regions[301] = city
    metric_expression = (
        {"op": "metric", "dimension": "quality", "concept_id": "healing"}
        if quality
        else {"op": "metric", "dimension": "load", "concept_id": "settlement"}
    )
    world.mechanical_language.derived_definitions["metric-1"] = DerivedMetricDefinition(
        id="metric-1",
        concept_id="metric-1",
        dimension=risk_dimension,
        target_kind="region",
        expression=metric_expression,
        unit="ratio",
        created_month=int(world.month_stamp),
    )
    world.mechanical_language.condition_definitions["condition-1"] = (
        ConditionDefinition(
            id="condition-1",
            concept_id="condition-1",
            target_kind="region",
            metric_definition_id="metric-1",
            activate_above=0.7,
            resolve_below=0.5,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )
    trigger = Event(
        world.month_stamp,
        "An urban risk became persistent.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={"region_id": "301", "condition_definition_id": "condition-1"},
        id="trigger-1",
    )
    instance_id = f"condition-instance-{risk_dimension.value}-{quality}"
    world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id=instance_id,
            definition_id="condition-1",
            target_kind="region",
            target_id="301",
            label="risk",
            intensity=0.9,
            started_month=int(world.month_stamp),
            cause_event_id=trigger.id,
        )
    )
    return city, trigger


def _setup_settlement_pressure(world):
    city = CityRegion(
        id=702,
        name="River City",
        desc="",
        cors=[(0, 0)],
        population=110,
        population_capacity=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((0, 0),), 1.0),),
            assets=(
                UrbanAsset("homes", "core", ("housing",), 100, 0.8, 0.9),
                UrbanAsset("builders", "core", ("construction_work",), 10, 1.0, 1.0),
            ),
            governance=CityGovernance("", "", 1.0),
        ),
        economy=RegionalEconomyState(
            stocks={"stone": 100.0},
            capacities={"stone": 200.0},
            access={"stone": 1.0},
            project_resources={PROJECT_KIND: "stone"},
        ),
    )
    world.map.regions[city.id] = city
    world.mechanical_language.derived_definitions["density-pressure"] = (
        DerivedMetricDefinition(
            id="density-pressure",
            concept_id="density-pressure",
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
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": "settlement",
                },
            },
            unit="ratio",
            created_month=int(world.month_stamp),
        )
    )
    world.mechanical_language.condition_definitions["pressure-condition"] = (
        ConditionDefinition(
            id="pressure-condition",
            concept_id="pressure-condition",
            target_kind="region",
            metric_definition_id="density-pressure",
            activate_above=0.85,
            resolve_below=0.75,
            activate_after_months=1,
            resolve_after_months=1,
            created_month=int(world.month_stamp),
        )
    )
    trigger = Event(
        world.month_stamp,
        "Settlement pressure became persistent.",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={
            "region_id": str(city.id),
            "condition_definition_id": "pressure-condition",
        },
        id="pressure-trigger",
    )
    world.mechanical_language.add_condition_instance(
        ConditionInstance(
            id="pressure-instance",
            definition_id="pressure-condition",
            target_kind="region",
            target_id=str(city.id),
            label="density pressure",
            intensity=1.1,
            started_month=int(world.month_stamp),
            cause_event_id=trigger.id,
        )
    )
    return city, trigger


@pytest.mark.asyncio
async def test_city_reactivity_requires_quality_risk_and_executes_once(base_world):
    city, trigger = _setup(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()
    enqueue_city_transitions(base_world, [trigger], queue)
    assert len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="city")) == 1
    enqueue_city_transitions(base_world, [trigger], queue)
    events = await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert [event.event_type for event in events] == [
        "city_interpretation_decision",
        "city_maintenance_completed",
    ]
    assert city.city_state.assets[0].integrity > 0.5
    second = await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )
    assert second == []


def test_city_reactivity_ignores_high_quality_and_non_quality_conditions(base_world):
    for kwargs in ({"quality": False}, {"risk_dimension": PrimitiveDimension.QUALITY}):
        _, trigger = _setup(base_world, **kwargs)
        queue = DomainInvalidationQueue()
        enqueue_city_transitions(base_world, [trigger], queue)
        assert queue.drain() == []


def test_city_reactivity_defers_to_explicit_current_dynasty_controller(base_world):
    city, trigger = _setup(base_world)
    base_world.dynasty = SimpleNamespace(id="house-1")
    city.city_state.governance = CityGovernance("dynasty", "house-1", 0.8)
    queue = DomainInvalidationQueue()

    enqueue_city_transitions(base_world, [trigger], queue)

    assert queue.drain() == []


@pytest.mark.parametrize(
    ("controller_kind", "controller_id"),
    (("dynasty", "foreign-house"), ("sect", "sect-9")),
)
def test_city_reactivity_never_acts_for_an_explicit_institutional_controller(
    base_world,
    controller_kind,
    controller_id,
):
    city, trigger = _setup(base_world)
    base_world.dynasty = SimpleNamespace(id="house-1")
    city.city_state.governance = CityGovernance(controller_kind, controller_id, 0.8)
    queue = DomainInvalidationQueue()

    enqueue_city_transitions(base_world, [trigger], queue)

    assert queue.drain() == []


def test_city_reactivity_remains_available_to_unclaimed_city(base_world):
    city, trigger = _setup(base_world)
    base_world.dynasty = SimpleNamespace(id="house-1")
    city.city_state.governance = CityGovernance("", "", 0.8)
    queue = DomainInvalidationQueue()

    enqueue_city_transitions(base_world, [trigger], queue)

    assert len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="city")) == 1


@pytest.mark.asyncio
async def test_blocked_city_maintenance_receipt_is_scheduled_for_next_month(base_world):
    _, trigger = _setup(base_world, integrity=1.0)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()
    enqueue_city_transitions(base_world, [trigger], queue)

    events = await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert events[-1].event_type == "city_maintenance_blocked"
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.domain == "city"
    assert receipt.completed is False
    assert receipt.next_eligible_month == int(base_world.month_stamp) + 1


@pytest.mark.asyncio
async def test_city_reaction_budget_zero_performs_no_evaluations(base_world):
    _, trigger = _setup(base_world)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "city_reaction_evaluation_budget_per_month": 0,
    }
    queue = DomainInvalidationQueue()
    enqueue_city_transitions(base_world, [trigger], queue)

    events = await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert events == []
    assert len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="city")) == 1


@pytest.mark.asyncio
async def test_settlement_pressure_starts_grounded_capacity_project(base_world):
    city, trigger = _setup_settlement_pressure(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()

    enqueue_city_transitions(base_world, [trigger], queue)
    events = await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert [event.event_type for event in events] == [
        "city_interpretation_decision",
        "urban_capacity_project_started",
    ]
    assert city.population_capacity == 100
    assert city.city_state.capacity_projects[0].motivation_event_ids == (
        events[0].id,
        trigger.id,
    )
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.completed is True


@pytest.mark.asyncio
async def test_completed_capacity_project_can_resolve_pressure_with_completion_as_evidence(
    base_world,
):
    city, trigger = _setup_settlement_pressure(base_world)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "semantic_discovery_budget_per_month": 0,
    }
    queue = DomainInvalidationQueue()
    enqueue_city_transitions(base_world, [trigger], queue)
    await process_city_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )
    project = city.city_state.capacity_projects[0]
    project_events = []
    for _ in range(project.required_months):
        base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)
        project_events.extend(
            advance_urban_capacity_projects(base_world, invalidations=queue)
        )
    completion = next(
        event
        for event in project_events
        if event.event_type == "urban_capacity_project_completed"
    )
    base_world.month_stamp = MonthStamp(int(base_world.month_stamp) + 1)

    semantic_events = await evaluate_semantic_world(
        base_world,
        source_event_ids_by_target={f"region:{city.id}": [completion.id]},
    )

    resolved = next(
        event
        for event in semantic_events
        if event.event_type == "semantic_condition_resolved"
    )
    assert completion.id in {link.cause_event_id for link in resolved.causal_links}
    assert resolved.causal_payload["measurements"][0]["value"] < 0.75
