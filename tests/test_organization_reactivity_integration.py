from pathlib import Path

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.classes.sect_ranks import get_rank_from_realm
from src.classes.root import Root
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidationLayer,
    DomainInvalidationQueue,
)
from src.systems.cultivation import Realm
from src.systems.organization_reactivity import (
    enqueue_organization_transitions,
    process_organization_reactivity,
)
from src.systems.time import Month, Year, create_month_stamp


def _setup(world):
    city = CityRegion(21, "Border City", "", cors=[(0, 0)])
    world.map.regions[city.id] = city
    sect = Sect(
        3,
        "Azure Sect",
        "",
        "",
        Alignment.RIGHTEOUS,
        SectHeadQuarter("HQ", "", Path("")),
        [],
        magic_stone=1000,
    )
    avatar = Avatar(
        world,
        "member",
        "member",
        create_month_stamp(Year(1), Month.JANUARY),
        Age(20, Realm.Qi_Refinement),
        Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.tile.region = city
    avatar.join_sect(sect, get_rank_from_realm(avatar.cultivation_progress.realm))
    avatar.magic_stone.value = 0
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects(world.existed_sects)
    trigger = Event(
        world.month_stamp,
        "pressure activated",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={
            "region_id": str(city.id),
            "condition_definition_id": "pressure",
        },
        id="pressure-event",
    )
    condition = ConditionInstance(
        "pressure-instance",
        "pressure",
        "region",
        str(city.id),
        "pressure",
        0.9,
        int(world.month_stamp),
        trigger.id,
    )
    world.mechanical_language.derived_definitions["regional-risk"] = (
        DerivedMetricDefinition(
            id="regional-risk",
            concept_id="regional-risk",
            dimension=PrimitiveDimension.RISK,
            target_kind="region",
            expression={
                "op": "metric",
                "dimension": "risk",
                "concept_id": "regional-risk",
            },
            unit="ratio",
            created_month=int(world.month_stamp),
        )
    )
    world.mechanical_language.condition_definitions["pressure"] = ConditionDefinition(
        id="pressure",
        concept_id="regional-pressure",
        target_kind="region",
        metric_definition_id="regional-risk",
        activate_above=0.7,
        resolve_below=0.5,
        activate_after_months=1,
        resolve_after_months=1,
        created_month=int(world.month_stamp),
    )
    world.mechanical_language.add_condition_instance(condition)
    return sect, avatar, city, trigger, condition


@pytest.mark.asyncio
async def test_reactivity_supports_each_eligible_sect_once_and_is_receipted(base_world):
    sect, avatar, city, trigger, condition = _setup(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    queue = DomainInvalidationQueue()
    enqueue_organization_transitions(base_world, [trigger], queue)
    assert (
        len(queue.drain(layer=DomainInvalidationLayer.SEMANTIC, domain="organization"))
        == 1
    )
    enqueue_organization_transitions(base_world, [trigger], queue)
    events = await process_organization_reactivity(
        base_world,
        current_events=[trigger],
        invalidations=queue,
        budget=CausalBudget.from_world(base_world),
    )

    assert [event.event_type for event in events] == [
        "organization_interpretation_decision",
        "sect_member_support_completed",
    ]
    assert sect.magic_stone == 700
    assert avatar.magic_stone.value == 300
    receipt = next(iter(base_world.mechanical_language.reaction_receipts.values()))
    assert receipt.domain == "organization:3"
    assert receipt.completed
    assert (
        await process_organization_reactivity(
            base_world,
            current_events=[trigger, *events],
            invalidations=queue,
            budget=CausalBudget.from_world(base_world),
        )
        == []
    )


@pytest.mark.asyncio
async def test_reactivity_budget_zero_keeps_invalidation_and_never_calls_llm(
    base_world,
):
    _setup(base_world)
    base_world.run_config_snapshot = {
        "test_mode": True,
        "organization_reaction_evaluation_budget_per_month": 0,
    }
    queue = DomainInvalidationQueue()
    trigger = Event(
        base_world.month_stamp,
        "pressure activated",
        event_type="semantic_condition_activated",
        render_params={"region_id": "21", "condition_definition_id": "pressure"},
        id="pressure-event-2",
    )
    # No matching instance means enqueue must not invent a trigger.
    enqueue_organization_transitions(base_world, [trigger], queue)
    assert queue.drain() == []


def test_reactivity_ignores_unregistered_condition(base_world):
    _, _, _, trigger, condition = _setup(base_world)
    base_world.mechanical_language.condition_definitions.pop(condition.definition_id)
    queue = DomainInvalidationQueue()

    enqueue_organization_transitions(base_world, [trigger], queue)

    assert queue.drain() == []
