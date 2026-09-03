from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import ConditionInstance, DomainReactionReceipt
from src.classes.environment.city_state import CityDistrict, CityGovernance, CityState, UrbanAsset
from src.classes.environment.region import CityRegion
from src.classes.regional_economy import RegionalEconomyState
from src.sim.managers.event_manager import EventManager
from src.systems.time import MonthStamp
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    advance_urban_capacity_projects,
    start_urban_capacity_project,
)


def _world(month: int = 1):
    return SimpleNamespace(
        month_stamp=month,
        run_config_snapshot={"test_mode": True},
        event_manager=EventManager.create_in_memory(),
        mechanical_language=SimpleNamespace(
            condition_instances={},
            reaction_receipts={},
            derived_definitions={},
        ),
        map=SimpleNamespace(regions={
            "over": SimpleNamespace(population=130, population_capacity=100),
            "near": SimpleNamespace(population=90, population_capacity=100),
            "under": SimpleNamespace(population=10, population_capacity=100),
        }),
    )


def _event(
    month: int,
    event_id: str,
    event_type: str,
    *,
    origin: CausalOrigin = CausalOrigin.DETERMINISTIC,
    fact_kind: FactKind = FactKind.OCCURRENCE,
    payload: dict | None = None,
    causes: tuple[str, ...] = (),
) -> Event:
    event = Event(
        month,
        event_id,
        id=event_id,
        event_type=event_type,
        causal_origin=origin,
        fact_kind=fact_kind,
        causal_payload=payload,
    )
    event.causal_links = [
        CausalLink(
            event_id=event_id,
            cause_event_id=cause,
            relation=CausalRelation.TRIGGERED_BY,
        )
        for cause in causes
    ]
    return event


def test_observatory_aggregates_conditions_reactions_materials_and_reuse():
    from src.classes.mechanical_language import (
        ConceptLifecycle,
        DerivedMetricDefinition,
        PrimitiveDimension,
    )
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    cause = _event(1, "cause", "population_growth")
    activated = _event(
        2,
        "activated",
        "semantic_condition_activated",
        origin=CausalOrigin.DERIVED_CONDITION,
        fact_kind=FactKind.DERIVED_CONDITION,
        causes=(cause.id,),
    )
    decision = _event(
        2,
        "decision",
        "population_interpretation_decision",
        origin=CausalOrigin.LLM_INTERPRETATION,
        fact_kind=FactKind.DECISION,
        payload={"interpretation": {"decision": "act"}},
        causes=(activated.id,),
    )
    migration = _event(
        2,
        "migration",
        "population_transfer_completed",
        origin=CausalOrigin.ACTOR_DECISION,
        fact_kind=FactKind.STATE_TRANSITION,
        payload={"outcome": "observed", "affordance": {"kind": "population_transfer"}},
        causes=(decision.id,),
    )
    resolved = _event(
        4,
        "resolved",
        "semantic_condition_resolved",
        origin=CausalOrigin.DERIVED_CONDITION,
        fact_kind=FactKind.DERIVED_CONDITION,
        causes=(activated.id,),
    )
    for event in (cause, activated, decision, migration, resolved):
        assert world.event_manager.add_event(event)

    instance = ConditionInstance(
        id="condition-1",
        definition_id="overcrowding",
        target_kind="region",
        target_id="302",
        label="overcrowding",
        intensity=0.9,
        started_month=2,
        cause_event_id=activated.id,
        resolved_month=4,
        resolution_event_id=resolved.id,
    )
    world.mechanical_language.condition_instances[instance.id] = instance
    receipt = DomainReactionReceipt.create(
        instance.id,
        "population",
        activated.id,
        decision_event_ids=(decision.id,),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt
    world.mechanical_language.derived_definitions["density"] = DerivedMetricDefinition(
        id="density",
        concept_id="density",
        dimension=PrimitiveDimension.RISK,
        target_kind="region",
        expression={"op": "constant", "value": 0.9, "unit": "ratio"},
        unit="ratio",
        created_month=1,
        lifecycle=ConceptLifecycle.ACTIVE,
        reuse_contexts=("region:302", "region:305"),
        last_used_month=4,
    )

    report = CausalObservatory().observe(world, start_month=1, end_month=4)

    assert report.condition_activated == 1
    assert report.condition_resolved == 1
    assert report.condition_durations == {"overcrowding:region:302:2:4": 3}
    assert report.reactions == {
        "decisions": 1,
        "no_action": 0,
        "successful": 1,
        "failed_affordance": 0,
        "affordance_attempts": 1,
        "post_attempt_lifecycle_events": 0,
        "terminal_reasons": {},
    }
    assert report.material_events == {
        "migration": 1,
        "economic_transfer": 0,
        "maintenance": 0,
        "capacity_project": 0,
        "institutional_support": 0,
    }
    assert report.urban_extremes == {
        "city_months_observed": 3,
        "city_months_near_capacity": 2,
        "city_months_over_capacity": 1,
        "city_months_severe_overcrowding": 1,
        "city_months_underused": 1,
        "peak_load_ratio": 1.3,
    }
    assert report.derived_metric_reuse == {"definitions_reused": 1, "contexts": 2}
    assert report.causal_telemetry["events"] == 5
    assert report.causal_telemetry["chain_depth_distribution"]["3"] == 1
    assert report.causal_chains == {
        "root_events": 1,
        "terminal_events": 2,
        "broken_events": 0,
        "out_of_window_events": 0,
    }
    assert report.event_quality["untyped_events"] == 0
    assert report.event_quality["dominant_event_type"] == "population_growth"
    assert report.causal_graph["links"] == 4
    assert report.causal_graph["max_fan_out"] == 2
    assert report.causal_graph["by_relation"] == {"triggered_by": 4}


def test_observatory_counts_no_action_blocked_affordance_and_broken_chain():
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    events = (
        _event(
            1,
            "maintain",
            "economy_interpretation_decision",
            fact_kind=FactKind.DECISION,
            payload={"interpretation": {"decision": "maintain"}},
        ),
        _event(
            1,
            "blocked",
            "regional_resource_transfer_blocked",
            fact_kind=FactKind.OCCURRENCE,
            payload={"outcome": "blocked", "affordance": {"kind": "resource_transfer"}},
            causes=("missing-cause",),
        ),
    )
    for event in events:
        assert world.event_manager.add_event(event)

    report = CausalObservatory().observe(world, start_month=1, end_month=1)

    assert report.reactions["no_action"] == 1
    assert report.reactions["failed_affordance"] == 1
    assert report.reactions["terminal_reasons"] == {"unknown": 1}
    assert report.reactions["successful"] == 0
    assert report.material_events["migration"] == 0
    assert report.causal_telemetry["broken_cause_count"] == 1
    assert report.causal_chains["root_events"] == 1
    assert report.causal_chains["terminal_events"] == 2
    assert report.causal_chains["broken_events"] == 1
    assert report.causal_chains["out_of_window_events"] == 0


def test_observatory_does_not_call_a_valid_out_of_window_cause_broken():
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    cause = _event(1, "earlier", "population_growth")
    effect = _event(
        2,
        "later",
        "semantic_condition_activated",
        causes=(cause.id,),
    )
    assert world.event_manager.add_event(cause)
    assert world.event_manager.add_event(effect)

    report = CausalObservatory().observe(world, start_month=2, end_month=2)

    assert report.causal_chains["broken_events"] == 0
    assert report.causal_chains["out_of_window_events"] == 1
    assert report.causal_telemetry["broken_cause_count"] == 0
    assert report.causal_telemetry["out_of_window_cause_count"] == 1


def test_observatory_separates_attempts_from_project_lifecycle_and_reports_quality():
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    events = (
        _event(1, "untyped", ""),
        _event(
            1,
            "started",
            "urban_capacity_project_started",
            payload={
                "outcome": "started",
                "affordance": {"kind": "settlement_capacity_expansion"},
            },
        ),
        _event(
            2,
            "progress",
            "urban_capacity_project_progressed",
            payload={"outcome": "progressed", "project_id": "project-1"},
        ),
        _event(
            2,
            "blocked",
            "population_transfer_blocked",
            payload={
                "outcome": "blocked",
                "reason": "no_reachable_destination_or_quantity",
                "affordance": {"kind": "population_transfer"},
            },
        ),
    )
    for event in events:
        assert world.event_manager.add_event(event)

    report = CausalObservatory().observe(world, start_month=1, end_month=2)

    assert report.reactions["affordance_attempts"] == 2
    assert report.reactions["post_attempt_lifecycle_events"] == 1
    assert report.reactions["successful"] == 1
    assert report.reactions["failed_affordance"] == 1
    assert report.reactions["terminal_reasons"] == {
        "no_reachable_destination_or_quantity": 1
    }
    assert report.event_quality["untyped_events"] == 1
    assert report.event_quality["repeated_type_month_pairs"] == 0


def test_observatory_does_not_count_no_action_receipt_as_successful_affordance():
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    decision = _event(
        1,
        "maintain",
        "government_interpretation_decision",
        origin=CausalOrigin.ACTOR_DECISION,
        fact_kind=FactKind.DECISION,
        payload={"decision": {"decision": "maintain"}},
    )
    assert world.event_manager.add_event(decision)
    receipt = DomainReactionReceipt.create(
        "condition-1",
        "government",
        "revision-1",
        decision_event_ids=(decision.id,),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt

    report = CausalObservatory().observe(world, start_month=1, end_month=1)

    assert report.reactions["decisions"] == 1
    assert report.reactions["no_action"] == 1
    assert report.reactions["affordance_attempts"] == 0
    assert report.reactions["successful"] == 0


def _construction_city(region_id: int) -> CityRegion:
    return CityRegion(
        id=region_id,
        name=f"Construction City {region_id}",
        desc="",
        cors=[(region_id, 0)],
        population=110,
        population_capacity=100,
        city_state=CityState(
            districts=(CityDistrict("core", "urban", ((region_id, 0),), 1.0),),
            assets=(
                UrbanAsset("homes", "core", ("housing",), 100, 0.8, 0.9),
                UrbanAsset("works", "core", ("construction_work",), 10, 0.8, 0.9),
            ),
            governance=CityGovernance("dynasty", "house-1", 1.0),
        ),
        economy=RegionalEconomyState(
            stocks={"stone": 100.0},
            capacities={"stone": 200.0},
            access={"stone": 1.0},
            project_resources={PROJECT_KIND: "stone"},
        ),
    )


def test_observatory_reports_real_capacity_project_material_and_reservations():
    from src.systems.causal_observatory import CausalObservatory

    world = _world(month=12)
    city = _construction_city(702)
    world.map.regions[city.id] = city
    started = start_urban_capacity_project(
        world,
        city,
        decision_event_id="decision-project",
        trigger_event_id="condition-project",
    )
    assert started.event_type == "urban_capacity_project_started"
    events = [started]
    world.event_manager.add_event(started)
    project = city.city_state.capacity_projects[0]
    for month in range(project.required_months):
        if month:
            world.month_stamp = MonthStamp(int(world.month_stamp) + 1)
        progressed = advance_urban_capacity_projects(world)
        events.extend(progressed)
        for event in progressed:
            assert world.event_manager.add_event(event)

    completion = next(
        event for event in events
        if event.event_type == "urban_capacity_project_completed"
    )
    assert completion.causal_payload["project_id"] == project.id

    report = CausalObservatory().observe(world, start_month=12, end_month=16)

    assert report.urban_projects == {
        "started": 1,
        "progressed": project.required_months,
        "stalled": 0,
        "resumed": 0,
        "blocked": 0,
        "completed": 1,
        "capacity_delta_total": project.capacity_increase,
        "material_reserved_total": project.material_required,
        "material_consumed_total": project.material_required,
        "active_reserved_material": 0.0,
        "projects_with_active_reservations": 0,
        "completed_with_reservation_leak": 0,
    }


def test_observatory_counts_active_project_reservation():
    from src.systems.causal_observatory import CausalObservatory

    world = _world(month=12)
    city = _construction_city(703)
    world.map.regions[city.id] = city
    started = start_urban_capacity_project(
        world,
        city,
        decision_event_id="decision-active-project",
        trigger_event_id="condition-active-project",
    )
    world.event_manager.add_event(started)
    project = city.city_state.capacity_projects[0]

    report = CausalObservatory().observe(world, start_month=12, end_month=12)

    assert report.urban_projects["material_reserved_total"] == pytest.approx(
        project.material_required
    )
    assert report.urban_projects["material_consumed_total"] == 0.0
    assert report.urban_projects["active_reserved_material"] == pytest.approx(
        project.material_required
    )
    assert report.urban_projects["projects_with_active_reservations"] == 1
    assert report.urban_projects["completed_with_reservation_leak"] == 0


def test_observatory_reconstructs_historical_construction_reservations_only():
    from src.systems.causal_observatory import CausalObservatory

    world = _world(month=4)
    world.map.regions[704] = SimpleNamespace(
        economy=RegionalEconomyState(
            stocks={"stone": 200.0},
            reservations={
                "commercial-order": {"stone": 90.0},
                "project-after-window": {"stone": 30.0},
            },
        ),
    )
    start = _event(
        1,
        "project-start",
        "urban_capacity_project_started",
        payload={"project_id": "project-historical", "material_required": 10.0},
    )
    progress = _event(
        2,
        "project-progress",
        "urban_capacity_project_progressed",
        payload={"project_id": "project-historical", "material_delta": 4.0},
    )
    later_start = _event(
        3,
        "project-later-start",
        "urban_capacity_project_started",
        payload={"project_id": "project-after-window", "material_required": 30.0},
    )
    for event in (start, progress, later_start):
        assert world.event_manager.add_event(event)

    report = CausalObservatory().observe(world, start_month=1, end_month=2)

    assert report.urban_projects["material_reserved_total"] == pytest.approx(10.0)
    assert report.urban_projects["material_consumed_total"] == pytest.approx(4.0)
    assert report.urban_projects["active_reserved_material"] == pytest.approx(6.0)
    assert report.urban_projects["projects_with_active_reservations"] == 1


def test_observatory_reports_causal_reservation_leak_on_completion():
    from src.systems.causal_observatory import CausalObservatory

    world = _world(month=3)
    events = (
        _event(
            1,
            "leaky-project-start",
            "urban_capacity_project_started",
            payload={"project_id": "leaky-project", "material_required": 10.0},
        ),
        _event(
            2,
            "leaky-project-progress",
            "urban_capacity_project_progressed",
            payload={"project_id": "leaky-project", "material_delta": 4.0},
        ),
        _event(
            3,
            "leaky-project-complete",
            "urban_capacity_project_completed",
            payload={"project_id": "leaky-project"},
        ),
    )
    for event in events:
        assert world.event_manager.add_event(event)

    report = CausalObservatory().observe(world, start_month=1, end_month=3)

    assert report.urban_projects["active_reserved_material"] == pytest.approx(6.0)
    assert report.urban_projects["projects_with_active_reservations"] == 1
    assert report.urban_projects["completed_with_reservation_leak"] == 1


def test_observatory_does_not_count_blocked_transfer_as_material_migration():
    from src.systems.causal_observatory import CausalObservatory

    world = _world()
    blocked = _event(
        1,
        "blocked-migration",
        "population_transfer_blocked",
        fact_kind=FactKind.OCCURRENCE,
        payload={
            "outcome": "blocked",
            "affordance": {"kind": "population_transfer"},
        },
    )
    assert world.event_manager.add_event(blocked)

    report = CausalObservatory().observe(world, start_month=1, end_month=1)

    assert report.reactions["failed_affordance"] == 1
    assert report.material_events["migration"] == 0


@pytest.mark.asyncio
async def test_runner_is_deterministic_test_only_and_does_not_call_provider(
    monkeypatch,
):
    from src.systems.causal_observatory import (
        CausalTortureConfig,
        CausalTortureRunner,
        RealProviderBlocked,
    )

    created: list[tuple[int, int]] = []
    step_calls = 0
    provider = AsyncMock(side_effect=AssertionError("real provider must not run"))
    monkeypatch.setattr("src.utils.llm.client.call_llm_with_template", provider)

    def factory(world_index: int, world_seed: int):
        created.append((world_index, world_seed))
        return _world()

    async def step(world):
        nonlocal step_calls
        step_calls += 1
        from src.utils.llm.client import call_llm_with_task_name

        await call_llm_with_task_name("relation_delta", "unused-template.txt", infos={})
        event = _event(int(world.month_stamp), f"step-{world.month_stamp}", "tick")
        world.event_manager.add_event(event)
        world.month_stamp += 1
        return [event]

    config = CausalTortureConfig(worlds=2, months=3, seed=19)
    first = await CausalTortureRunner(config).run(world_factory=factory, step=step)
    second = await CausalTortureRunner(config).run(world_factory=factory, step=step)

    assert first.to_dict() == second.to_dict()
    assert created[:2] == [(0, 19), (1, 20)]
    assert step_calls == 12
    assert all(run.months_completed == 3 for run in first.runs)
    provider.assert_not_awaited()

    from src.classes.core.sect import sects_by_id, sects_by_name

    sects_before = dict(sects_by_id)
    sect_names_before = dict(sects_by_name)
    default_report = await CausalTortureRunner(
        CausalTortureConfig(worlds=1, months=2, seed=19),
    ).run()
    assert default_report.totals["worlds"] == 1
    assert default_report.totals["months"] == 2
    assert default_report.runs[0].months_completed == 2
    assert default_report.runs[0].urban_extremes["city_months_observed"] == 10
    assert dict(sects_by_id) == sects_before
    assert dict(sects_by_name) == sect_names_before
    provider.assert_not_awaited()

    with pytest.raises(RealProviderBlocked):
        CausalTortureConfig(worlds=1, months=1, provider="openrouter")


@pytest.mark.asyncio
async def test_runner_rejects_persistent_event_storage():
    from src.systems.causal_observatory import (
        CausalTortureConfig,
        CausalTortureRunner,
        PersistentStorageBlocked,
    )

    world = _world()
    world.event_manager._storage = object()

    with pytest.raises(PersistentStorageBlocked):
        await CausalTortureRunner(CausalTortureConfig(worlds=1, months=1)).run(
            world_factory=lambda _index, _seed: world,
        )


@pytest.mark.asyncio
async def test_runner_restores_world_and_global_custom_content_after_success():
    from src.classes.custom_content import CustomContentRegistry
    from src.systems.causal_observatory import CausalTortureConfig, CausalTortureRunner

    world = _world()
    original_month = world.month_stamp
    original_events = list(world.event_manager._memory_events)
    original_next_ids = dict(CustomContentRegistry.next_ids)
    seen_next_ids: list[int] = []

    async def step(current_world):
        seen_next_ids.append(CustomContentRegistry.next_ids["technique"])
        CustomContentRegistry.next_ids["technique"] += 100
        current_world.event_manager.add_event(
            _event(int(current_world.month_stamp), "temporary", "temporary_mutation")
        )
        current_world.month_stamp += 1

    await CausalTortureRunner(CausalTortureConfig(worlds=2, months=1)).run(
        world_factory=lambda _index, _seed: world,
        step=step,
    )

    assert seen_next_ids == [original_next_ids["technique"]] * 2
    assert world.month_stamp == original_month
    assert world.event_manager._memory_events == original_events
    assert CustomContentRegistry.next_ids == original_next_ids


def test_runner_requires_test_mode():
    from src.systems.causal_observatory import CausalTortureConfig, TestModeRequired

    with pytest.raises(TestModeRequired):
        CausalTortureConfig(test_mode=False)
