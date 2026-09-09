"""A sect may answer a member's need inside the prehistory window.

`react_organization` now belongs to the fixed three-month subset, after
`react_government` and in registry order. It reuses the existing provider and
owner: the same authority gate, the same `support_member` affordance, the same
`execute_sect_member_support`. Nothing annual runs here, no planner, and no
scripted event.

The pressure is derived, not seeded: material state and the engine-owned rule
are declared, and the real semantic pass has to produce the condition. Only the
selection among options the engine composed is injected, and only in tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.event import FactKind
from src.classes.items.magic_stone import MagicStone
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, Year, create_month_stamp
from tests.test_institutional_prehistory import (
    PLAYABLE_START,
    _declare_urban_pressure,
    _run,
    _world,
)

SUPPORT_EVENT_TYPE = "sect_member_support_completed"


def _member(world, city, *, avatar_id: str, stones: int) -> Avatar:
    """A living, registered avatar standing in the pressured city."""
    avatar = Avatar(
        world=world,
        name=avatar_id,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        pos_x=1,
        pos_y=1,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    avatar.magic_stone = MagicStone(stones)
    avatar.tile = world.map.get_tile(1, 1)
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _sect_in_need(world, city):
    """A sect with a living patriarch and one member who needs support."""
    sect = Sect(
        7, "Azure Sect", "", "", Alignment.RIGHTEOUS,
        SectHeadQuarter("Azure Hall", "", Path("")), [], magic_stone=1000,
    )
    patriarch = _member(world, city, avatar_id="patriarch", stones=1000)
    patriarch.join_sect(sect, SectRank.Patriarch)
    needy = _member(world, city, avatar_id="needy", stones=0)
    needy.join_sect(sect, SectRank.OuterDisciple)
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects(world.existed_sects)
    bootstrap_institutional_authority(world)
    return sect, patriarch, needy


def _inject_support_choice(*, act: bool = True, offered: list | None = None):
    """Decide the sect's round explicitly, among options the engine composed.

    With ``act`` the offered support is selected; without it the round is an
    explicit MAINTAIN, so "left alone" is a decision that really happened
    rather than an absence the test could mistake for one. ``offered`` records
    what the engine actually put on the menu.
    """
    from contextlib import contextmanager
    from unittest.mock import patch

    from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
    import src.systems.organization_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        options = tuple(kwargs.get("affordances") or ())
        if offered is not None:
            offered.extend(options)
        chosen = next(
            (item for item in options if item.action_kind == "support_member"), None
        )
        if chosen is None:
            return await original(*args, **kwargs)
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "The sect helps its own.", chosen.id)
            if act
            else DomainDecision(
                DomainDecisionKind.MAINTAIN, "The sect keeps its stones."
            )
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    @contextmanager
    def _scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return _scope()


def _organization_receipts(world, sect):
    return {
        key: receipt
        for key, receipt in world.mechanical_language.reaction_receipts.items()
        if receipt.domain == f"organization:{sect.id}"
    }


def _pressured_condition(world, city):
    """The clinic-risk instance of this very city, not whatever came first."""
    return next(
        item
        for item in world.mechanical_language.condition_instances.values()
        if str(item.target_id) == str(city.id)
        and str(item.definition_id) == "clinic-risk"
    )


@pytest.mark.asyncio
async def test_a_sect_supports_a_member_inside_the_prehistory(base_map) -> None:
    """The whole chain, before play, through the existing owner."""
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    sect, patriarch, needy = _sect_in_need(world, city)
    assert world.mechanical_language.condition_instances == {}
    before_sect = int(sect.magic_stone)

    with _inject_support_choice():
        events = await _run(world)

    # The semantic pass derived the condition; nothing seeded it.
    assert [
        event for event in events
        if event.event_type == "semantic_condition_activated"
        and str((event.render_params or {}).get("region_id")) == str(city.id)
    ]

    supports = [event for event in events if event.event_type == SUPPORT_EVENT_TYPE]
    assert supports, "the sect answered nothing inside the prehistory"
    support = supports[0]
    assert support.fact_kind is FactKind.STATE_TRANSITION

    # Two real owners moved.
    deltas = {
        (item["owner_kind"], item["owner_id"]): item
        for item in support.causal_payload["deltas"]
    }
    assert set(deltas) == {("sect", str(sect.id)), ("avatar", str(needy.id))}
    assert int(sect.magic_stone) < before_sect
    assert int(needy.magic_stone.value) > 0
    assert all(item["event_id"] == support.id for item in deltas.values())

    # It cites the sect's own decision and the grievance's own cause.
    decisions = [
        event for event in events
        if event.fact_kind is FactKind.DECISION
        and event.id in {link.cause_event_id for link in support.causal_links}
    ]
    assert decisions, "the support cites no decision produced in the window"
    cited = {link.cause_event_id for link in support.causal_links}
    condition = _pressured_condition(world, city)
    assert condition.cause_event_id in cited

    # This sect's own acting receipt, not merely some receipt in the world.
    receipts = _organization_receipts(world, sect)
    assert len(receipts) == 1
    receipt = next(iter(receipts.values()))
    assert receipt.condition_instance_id == condition.id
    assert receipt.decision == "act"
    assert receipt.affordance_id == support.causal_payload["affordance_id"]
    assert receipt.decision_event_ids == (decisions[0].id,)

    assert int(world.month_stamp) == int(PLAYABLE_START)
    for event in (support, *decisions):
        assert int(event.month_stamp) < int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_a_sect_with_no_need_supports_nobody(base_map) -> None:
    """No need, no action: the phase forces nothing."""
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    sect, patriarch, comfortable = _sect_in_need(world, city)
    # Nobody is poor any more.
    comfortable.magic_stone = MagicStone(1000)
    before_sect = int(sect.magic_stone)

    with _inject_support_choice():
        events = await _run(world)

    assert not [e for e in events if e.event_type == SUPPORT_EVENT_TYPE]
    assert int(sect.magic_stone) == before_sect


@pytest.mark.asyncio
async def test_a_real_need_may_still_be_left_alone(base_map) -> None:
    """Maintaining is a valid answer: the need alone compels nothing.

    An explicit MAINTAIN with the support really on the menu, so this proves a
    decision that happened rather than an absence.
    """
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    sect, patriarch, needy = _sect_in_need(world, city)
    before_sect = int(sect.magic_stone)
    before_member = int(needy.magic_stone.value)
    offered: list = []

    with _inject_support_choice(act=False, offered=offered):
        events = await _run(world)

    # The material option really was there, and was declined.
    assert [item for item in offered if item.action_kind == "support_member"]
    assert not [e for e in events if e.event_type == SUPPORT_EVENT_TYPE]
    assert int(sect.magic_stone) == before_sect
    assert int(needy.magic_stone.value) == before_member

    receipts = _organization_receipts(world, sect)
    assert len(receipts) == 1
    receipt = next(iter(receipts.values()))
    assert receipt.decision == "maintain"
    assert receipt.affordance_id is None
    assert receipt.condition_instance_id == _pressured_condition(world, city).id
    assert int(world.month_stamp) == int(PLAYABLE_START)


@pytest.mark.asyncio
async def test_the_window_calls_no_provider(base_map) -> None:
    """Test mode, and the sect phase must not change that."""
    from unittest.mock import AsyncMock, patch

    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    _sect_in_need(world, city)
    provider = AsyncMock(side_effect=AssertionError("prehistory called a provider"))

    with patch("src.utils.llm.client.call_llm_with_template", provider), \
            _inject_support_choice():
        await _run(world)

    provider.assert_not_awaited()
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_the_support_survives_a_real_save_and_load(base_map, tmp_path) -> None:
    """Receipts and both balances come back through the project's own path."""
    from src.sim.load.load_game import load_game
    from src.sim.save.save_game import save_game
    from src.sim.simulator import Simulator

    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    sect, patriarch, needy = _sect_in_need(world, city)

    with _inject_support_choice():
        events = await _run(world)
    supports = [event for event in events if event.event_type == SUPPORT_EVENT_TYPE]
    assert supports
    support = supports[0]
    decision = next(
        event for event in events
        if event.fact_kind is FactKind.DECISION
        and event.id in {link.cause_event_id for link in support.causal_links}
    )
    activation = next(
        event for event in events
        if event.event_type == "semantic_condition_activated"
        and str((event.render_params or {}).get("region_id")) == str(city.id)
    )
    receipts = {
        key: receipt.to_dict()
        for key, receipt in world.mechanical_language.reaction_receipts.items()
    }
    sect_stones = int(sect.magic_stone)
    member_stones = int(needy.magic_stone.value)

    save_path = tmp_path / "sect_prehistory.json"
    success, _message = save_game(world, Simulator(world), [sect], save_path)
    assert success
    world.event_manager.close()
    # The loader rebuilds from the save itself, so nothing is handed back to
    # it: the restored objects are genuinely independent of the live ones.
    loaded, _simulator, _sects = load_game(save_path)
    assert loaded is not world
    assert loaded.sect_context is not world.sect_context

    # The whole chain is still stored, deltas included.
    for original in (support, decision, activation):
        assert loaded.event_manager.get_event_by_id(original.id) is not None
    restored_support = loaded.event_manager.get_event_by_id(support.id)
    assert restored_support.causal_payload["deltas"] == (
        support.causal_payload["deltas"]
    )
    # Receipts compared whole, not by key.
    assert {
        key: receipt.to_dict()
        for key, receipt in loaded.mechanical_language.reaction_receipts.items()
    } == receipts
    restored = next(
        item for item in loaded.sect_context.get_active_sects()
        if str(item.id) == str(sect.id)
    )
    assert int(restored.magic_stone) == sect_stones
    assert int(
        loaded.avatar_manager.get_avatar(str(needy.id)).magic_stone.value
    ) == member_stones
