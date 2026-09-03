from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_proposal import OrganizationDecisionKind, OrganizationIntentKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import (
    ConditionDefinition,
    ConditionInstance,
    DerivedMetricDefinition,
    PrimitiveDimension,
)
from src.classes.root import Root
from src.systems.cultivation import Realm
from src.systems.organization_interpreter import (
    ORGANIZATION_INTERPRETER_SCHEMA,
    interpret_organization_transition,
)
from src.systems.sect_member_support import eligible_member_ids
from src.systems.time import Month, Year, create_month_stamp


def _setup(world):
    sect = Sect(
        1,
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
    region = CityRegion(7, "Border City", "", cors=[(0, 0)])
    world.map.regions[region.id] = region
    avatar.tile.region = region
    avatar.join_sect(sect, None)
    avatar.magic_stone.value = 0
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects(world.existed_sects)
    trigger = Event(
        world.month_stamp,
        "pressure",
        event_type="semantic_condition_activated",
        fact_kind=FactKind.DERIVED_CONDITION,
        render_params={"region_id": "7", "condition_definition_id": "pressure"},
        id="condition-event",
    )
    condition = ConditionInstance(
        "condition-1",
        "pressure",
        "region",
        "7",
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
    return sect, avatar, region, trigger, condition


@pytest.mark.asyncio
async def test_organization_interpreter_test_mode_supports_only_eligible_id(base_world):
    sect, avatar, region, trigger, condition = _setup(base_world)
    base_world.run_config_snapshot = {"test_mode": True}
    decision, event = await interpret_organization_transition(
        base_world,
        sect,
        region,
        condition,
        trigger,
        eligible_member_ids(sect, region_id="7"),
    )

    assert decision.decision is OrganizationDecisionKind.SUPPORT_MEMBER
    assert decision.action_intent.member_id == avatar.id
    assert decision.action_intent.action_kind is OrganizationIntentKind.SUPPORT_MEMBER
    assert event.causal_origin.value == "deterministic"
    assert event.causal_links[0].cause_event_id == trigger.id


@pytest.mark.asyncio
async def test_organization_interpreter_rejects_llm_member_outside_grounded_ids(
    base_world,
):
    sect, _, region, trigger, condition = _setup(base_world)
    llm = AsyncMock(
        return_value={
            "decision": "support_member",
            "reason": "bad",
            "action_intent": {"action_kind": "support_member", "member_id": "other"},
        }
    )
    decision, event = await interpret_organization_transition(
        base_world, sect, region, condition, trigger, ("member",), llm_call=llm
    )

    assert decision.decision is OrganizationDecisionKind.SUPPORT_MEMBER
    assert decision.action_intent.member_id == "member"
    assert event.causal_origin.value == "deterministic"
    assert llm.await_args.kwargs["output_schema"] == ORGANIZATION_INTERPRETER_SCHEMA


@pytest.mark.asyncio
async def test_organization_interpreter_rejects_stale_context(base_world):
    sect, _, region, trigger, condition = _setup(base_world)
    stale = ConditionInstance(
        id=condition.id,
        definition_id=condition.definition_id,
        target_kind=condition.target_kind,
        target_id=condition.target_id,
        label=condition.label,
        intensity=condition.intensity,
        started_month=condition.started_month,
        cause_event_id=condition.cause_event_id,
        resolved_month=int(base_world.month_stamp),
    )

    with pytest.raises(ValueError, match="matching active condition"):
        await interpret_organization_transition(
            base_world, sect, region, stale, trigger, ("member",)
        )
