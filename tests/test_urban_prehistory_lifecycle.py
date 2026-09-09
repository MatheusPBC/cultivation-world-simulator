"""End-to-end contracts for the urban subset of institutional prehistory."""

from __future__ import annotations

import random
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

import pytest

from src.classes.age import Age
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.dynasty import Dynasty
from src.classes.core.world import World
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.city_state import (
    CityDistrict,
    CityGovernance,
    CityState,
    UrbanAsset,
    UrbanServiceDemand,
)
from src.classes.environment.region import CityRegion
from src.classes.environment.route import Route
from src.classes.mechanical_language import (
    ConditionDefinition,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.classes.event import FactKind
from src.classes.regional_economy import RegionalEconomyState
from src.sim.simulator import Simulator
from src.sim.simulator_engine.prehistory import (
    genesis_month_stamp,
    run_institutional_prehistory,
)
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, Year, create_month_stamp
from src.systems.urban_capacity_project import PROJECT_KIND


PLAYABLE_START = create_month_stamp(Year(100), Month.JANUARY)


def _world(base_map) -> World:
    world = World(map=base_map, month_stamp=genesis_month_stamp(PLAYABLE_START))
    world.run_config_snapshot = {
        "map_id": "classic",
        "test_mode": True,
        "provider": "test",
        "content_locale": "pt-BR",
        "init_npc_num": 0,
        "sect_num": 0,
        "npc_awakening_rate_per_month": 0.0,
        "world_lore": "",
    }
    emperor = Avatar(
        world=world,
        name="Prehistory Emperor",
        id="emperor",
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
    )
    world.avatar_manager.register_avatar(emperor)
    world.dynasty = Dynasty(1, "Prehistory Dynasty", "", current_emperor_id=emperor.id)

    for region_id in (302, 305):
        cell = (region_id % 10, 0)
        region = CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[cell],
            economy=RegionalEconomyState(
                stocks={"grain": 18.0},
                capacities={"grain": 20.0},
                access={"grain": 1.0},
            ),
        )
        region.city_state.governance = CityGovernance("dynasty", "1", 1.0)
        world.map.regions[region_id] = region
        world.map.region_cors[region_id] = [cell]
        world.map.tiles[cell].region = region
    world.map.set_routes((Route("aid-road", (302, 305), "road", 2, 1.0, True),))
    bootstrap_institutional_authority(world)
    return world


def _damaged_city(world: World, *, governed: bool) -> CityRegion:
    cell = (1, 1)
    city = CityRegion(
        id=301,
        name="Strained City",
        desc="",
        cors=[cell],
        city_state=CityState(
            districts=(CityDistrict("core", "urban", (cell,), 1.0),),
            assets=(UrbanAsset("clinic", "core", ("healing",), 10, 0.4, 0.2),),
            service_demands=(UrbanServiceDemand("healing", 1.0),),
            governance=CityGovernance("dynasty" if governed else "", "1" if governed else "", 0.8),
        ),
    )
    city.population = 40
    city.population_capacity = 400
    world.map.regions[city.id] = city
    world.map.region_cors[city.id] = [cell]
    world.map.tiles[cell].region = city

    month = int(world.month_stamp)
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
            created_month=month,
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
            created_month=month,
        )
    )
    return city


async def _run(world: World):
    return await run_institutional_prehistory(
        Simulator(world), playable_start_month=PLAYABLE_START
    )


def _select_city_affordance(action_kind: str):
    """Select only an actual option from the city's shared interpreter entry."""
    import src.systems.city_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        offered = tuple(kwargs.get("affordances") or ())
        chosen = next((item for item in offered if item.action_kind == action_kind), None)
        if chosen is None:
            return await original(*args, **kwargs)
        return await original(
            *args,
            **{
                **kwargs,
                "injected_decision": DomainDecision(
                    DomainDecisionKind.ACT,
                    "The city builds.",
                    chosen.id,
                ),
            },
        )

    @contextmanager
    def scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return scope()


def _select_government_affordance(action_kind: str):
    import src.systems.government_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        offered = tuple(kwargs.get("affordances") or ())
        chosen = next((item for item in offered if item.action_kind == action_kind), None)
        if chosen is None:
            return await original(*args, **kwargs)
        return await original(
            *args,
            **{
                **kwargs,
                "injected_decision": DomainDecision(
                    DomainDecisionKind.ACT,
                    "The city is repaired.",
                    chosen.id,
                ),
            },
        )

    @contextmanager
    def scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return scope()


@pytest.mark.asyncio
async def test_unclaimed_crowded_city_starts_and_advances_canonical_project(base_map) -> None:
    world = _world(base_map)
    city = _damaged_city(world, governed=False)
    city.city_state = replace(
        city.city_state,
        assets=(
            *city.city_state.assets,
            UrbanAsset("housing", "core", ("housing",), 400, 1.0, 1.0),
            UrbanAsset("yard", "core", ("construction_work",), 10, 1.0, 1.0),
        ),
    )
    city.economy = RegionalEconomyState(
        stocks={"stone": 5000.0},
        capacities={"stone": 10000.0},
        access={"stone": 1.0},
        project_resources={PROJECT_KIND: "stone"},
    )
    city.population = 380
    city.population_capacity = 400
    stone_before = city.economy.stocks["stone"]

    # The semantic service, not this fixture, must create both of these facts.
    assert world.mechanical_language.condition_instances == {}
    assert world.event_manager.count() == 0

    with _select_city_affordance("urban_capacity_project"):
        events = await _run(world)

    assert any(event.event_type == "semantic_condition_activated" for event in events)
    started = [event for event in events if event.event_type == "urban_capacity_project_started"]
    progressed = [
        event for event in events if event.event_type == "urban_capacity_project_progressed"
    ]
    assert started
    assert progressed
    assert all(int(event.month_stamp) < int(PLAYABLE_START) for event in (*started, *progressed))
    events_by_id = {event.id: event for event in events}
    assert any(
        events_by_id.get(link.cause_event_id, object()).fact_kind is FactKind.DECISION
        for event in started
        for link in event.causal_links
    )
    assert any(
        delta["aspect"] == "urban_capacity_project_progress"
        for event in progressed
        for delta in event.causal_payload["deltas"]
    )
    assert city.city_state.capacity_projects
    project = city.city_state.capacity_projects[0]
    assert project.completed_months > 0
    assert project.material_consumed > 0
    assert city.economy.stocks["stone"] < stone_before
    assert int(world.month_stamp) == int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_failed_finalizer_rolls_back_urban_month_but_keeps_prior_commits(
    base_map, monkeypatch
) -> None:
    """A maintenance transition before finalization cannot leak from a failed month."""
    from src.sim.simulator_engine import phase_registry

    world = _world(base_map)
    city = _damaged_city(world, governed=True)
    original_finalize = phase_registry.finalize_step
    calls = 0
    committed_snapshot: dict[str, object] = {}

    def failing_finalize(ctx):
        nonlocal calls
        calls += 1
        if calls == 3:
            # The owner has already mutated canonical state in this month.
            assert city.city_state.assets[0].integrity > committed_snapshot["integrity"]
            assert any(event.event_type == "city_maintenance_completed" for event in ctx.events)
            random.random()  # The checkpoint must roll this consumption back too.
            raise RuntimeError("finalizer failure after urban mutation")

        result = original_finalize(ctx)
        if calls == 2:
            committed_snapshot.update(
                integrity=city.city_state.assets[0].integrity,
                month=int(world.month_stamp),
                event_ids=tuple(event.id for event in world.event_manager._memory_events),
                receipts=tuple(sorted(world.mechanical_language.reaction_receipts.items())),
                memories=world.institutional_relations.to_dict(),
                random_state=random.getstate(),
            )
        return result

    # The registry holds `finalize_step_phase`; its wrapper resolves this symbol.
    monkeypatch.setattr(phase_registry, "finalize_step", failing_finalize)

    with _select_government_affordance("urban_maintenance"):
        with pytest.raises(RuntimeError, match="finalizer failure after urban mutation"):
            await _run(world)

    assert calls == 3
    assert city.city_state.assets[0].integrity == pytest.approx(committed_snapshot["integrity"])
    assert int(world.month_stamp) == committed_snapshot["month"]
    assert tuple(event.id for event in world.event_manager._memory_events) == committed_snapshot["event_ids"]
    assert tuple(sorted(world.mechanical_language.reaction_receipts.items())) == committed_snapshot["receipts"]
    assert world.institutional_relations.to_dict() == committed_snapshot["memories"]
    assert random.getstate() == committed_snapshot["random_state"]
