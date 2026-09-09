"""A failed sect reaction cannot leak from the institutional prehistory window."""

from __future__ import annotations

import random
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.event import FactKind
from src.classes.items.magic_stone import MagicStone
from src.classes.sect_ranks import SectRank, get_rank_from_realm
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, Year, create_month_stamp
from tests.test_institutional_prehistory import _declare_urban_pressure, _run, _world


def _avatar(world, *, avatar_id: str, name: str) -> Avatar:
    return Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )


def _attach_authorized_sect(world, city):
    sect = Sect(
        id=71,
        name="River Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter("Hall", "", Path()),
        technique_names=[],
        magic_stone=1000,
    )
    patriarch = _avatar(world, avatar_id="river-patriarch", name="Patriarch")
    member = _avatar(world, avatar_id="river-member", name="Member")
    patriarch.join_sect(sect, SectRank.Patriarch)
    member.join_sect(sect, get_rank_from_realm(member.cultivation_progress.realm))
    member.magic_stone = MagicStone(0)
    member.pos_x, member.pos_y = city.cors[0]
    member.tile = world.map.get_tile(member.pos_x, member.pos_y)
    member.tile.region = city
    world.avatar_manager.register_avatar(patriarch)
    world.avatar_manager.register_avatar(member)
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects(world.existed_sects)
    bootstrap_institutional_authority(world)
    return sect, member


def _select_support_member():
    """Inject only an option the organization interpreter really offered."""
    import src.systems.organization_interpreter as interpreter

    original = interpreter.interpret_domain_affordances

    async def choose(*args, **kwargs):
        offered = tuple(kwargs.get("affordances") or ())
        selected = next(
            (item for item in offered if item.action_kind == "support_member"), None
        )
        if selected is None:
            return await original(*args, **kwargs)
        return await original(
            *args,
            **{
                **kwargs,
                "injected_decision": DomainDecision(
                    DomainDecisionKind.ACT,
                    "The sect supports its member.",
                    selected.id,
                ),
            },
        )

    @contextmanager
    def scope():
        with patch.object(interpreter, "interpret_domain_affordances", choose):
            yield

    return scope()


@pytest.mark.asyncio
async def test_failed_prehistory_commit_restores_derived_sect_support(base_map, monkeypatch) -> None:
    world = _world(base_map, pressured=False)
    city = _declare_urban_pressure(world)
    sect, member = _attach_authorized_sect(world, city)

    assert world.mechanical_language.condition_instances == {}
    treasury_before = sect.magic_stone
    member_stones_before = member.magic_stone.value
    receipts_before = dict(world.mechanical_language.reaction_receipts)
    event_count_before = world.event_manager.count()
    month_before = world.month_stamp
    random_before = random.getstate()
    attempted: list = []
    original_commit = world.event_manager.commit_step

    def fail_after_support(events, chapter=None):
        if not any(event.event_type == "sect_member_support_completed" for event in events):
            return original_commit(events, chapter)
        attempted.extend(events)
        assert sect.magic_stone < treasury_before
        assert member.magic_stone.value > member_stones_before
        assert any(
            receipt.domain == f"organization:{sect.id}"
            for receipt in world.mechanical_language.reaction_receipts.values()
        )
        return False

    monkeypatch.setattr(world.event_manager, "commit_step", fail_after_support)

    with _select_support_member():
        with pytest.raises(EventPersistenceError, match="failed to persist causal event"):
            await _run(world)

    activations = [
        event for event in attempted if event.event_type == "semantic_condition_activated"
    ]
    support = next(
        event for event in attempted if event.event_type == "sect_member_support_completed"
    )
    decision_ids = {
        event.id
        for event in attempted
        if event.fact_kind is FactKind.DECISION
    }
    assert activations
    assert decision_ids
    support_causes = {link.cause_event_id for link in support.causal_links}
    assert support_causes.intersection(decision_ids)
    assert support_causes.intersection(event.id for event in activations)
    assert sect.magic_stone == treasury_before
    assert member.magic_stone.value == member_stones_before
    assert world.mechanical_language.condition_instances == {}
    assert world.mechanical_language.reaction_receipts == receipts_before
    assert world.event_manager.count() == event_count_before
    assert world.month_stamp == month_before
    assert random.getstate() == random_before
