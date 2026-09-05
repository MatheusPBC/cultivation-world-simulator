"""Transactional runtime witnesses for grounded institutional war.

The assertions are intentionally end-to-end: the aggression must originate in
the normal Avatar ``Attack`` lifecycle, not from a hand-assembled casus event.
"""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.action_runtime import ActionOrigin
from src.classes.causal_link import CausalRelation
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.institution import KnowledgeChannel
from src.classes.environment.sect_region import SectRegion
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.sim.simulator_engine.phases.actions import phase_decide_actions
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.systems.avatar_aggression import DELIBERATE_ATTACK_EVENT_TYPE
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    are_sects_at_war,
    sect_institution_id,
)
from src.systems.time import Month, Year, create_month_stamp
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _avatar(world, *, avatar_id: str, name: str, coordinate: tuple[int, int]) -> Avatar:
    avatar = Avatar(
        world=world,
        id=avatar_id,
        name=name,
        birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=coordinate[0],
        pos_y=coordinate[1],
        root=Root.GOLD,
        alignment=Alignment.NEUTRAL,
        personas=[],
    )
    avatar.personas = []
    avatar.weapon = None
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _war_world(world) -> dict[str, Avatar | Sect]:
    """Two sects, with only the victim sect's force office witnessing it."""

    headquarters = SectHeadQuarter(name="War HQ", desc="", image=Path(""))
    sect_one = Sect(
        id=1,
        name="Azure Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.NEUTRAL,
        headquarter=headquarters,
        technique_names=[],
    )
    sect_two = Sect(
        id=2,
        name="Crimson Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.NEUTRAL,
        headquarter=headquarters,
        technique_names=[],
    )
    for sect, region_id, coordinate in (
        (sect_one, 5101, (0, 0)),
        (sect_two, 5102, (8, 8)),
    ):
        region = SectRegion(
            id=region_id,
            name=f"{sect.name} headquarters",
            desc="",
            sect_id=sect.id,
            sect_name=sect.name,
            cors=[coordinate],
        )
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = [coordinate]

    patriarch_one = _avatar(
        world,
        avatar_id="war-patriarch-1",
        name="Patriarch Azure",
        coordinate=(8, 8),
    )
    aggressor = _avatar(
        world,
        avatar_id="war-aggressor",
        name="Azure Disciple",
        coordinate=(0, 0),
    )
    victim = _avatar(
        world,
        avatar_id="war-victim",
        name="Crimson Disciple",
        coordinate=(0, 1),
    )
    patriarch_two = _avatar(
        world,
        avatar_id="war-patriarch-2",
        name="Patriarch Crimson",
        coordinate=(1, 1),
    )
    patriarch_one.join_sect(sect_one, SectRank.Patriarch)
    aggressor.join_sect(sect_one, SectRank.OuterDisciple)
    victim.join_sect(sect_two, SectRank.OuterDisciple)
    patriarch_two.join_sect(sect_two, SectRank.Patriarch)

    world.map.update_sect_regions()
    world.existed_sects = [sect_one, sect_two]
    world.sect_context.from_existed_sects(world.existed_sects)
    world.run_config_snapshot = {
        "test_mode": True,
        "provider": "test",
        "npc_awakening_rate_per_month": 0.0,
    }
    bootstrap_institutional_authority(world)
    return {
        "sect_one": sect_one,
        "sect_two": sect_two,
        "patriarch_one": patriarch_one,
        "patriarch_two": patriarch_two,
        "aggressor": aggressor,
        "victim": victim,
    }


def _enable_annual_war(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.sim.simulator_engine.phases.annual._should_run_sect_decision_cycle",
        lambda _world: True,
    )


def _control_war_interpreter(monkeypatch) -> None:
    import src.systems.institutional_war as institutional_war

    original = institutional_war.interpret_domain_affordances

    async def controlled(*args, **kwargs):
        option = kwargs["affordances"][0]
        decision = DomainDecision(
            DomainDecisionKind.ACT,
            "Controlled declaration grounded in the witnessed attack.",
            option.id,
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    monkeypatch.setattr(institutional_war, "interpret_domain_affordances", controlled)


def _advance_to_next_january(world) -> None:
    world.month_stamp = create_month_stamp(
        Year(world.month_stamp.get_year() + 1), Month.JANUARY
    )


@pytest.mark.asyncio
async def test_real_avatar_choice_attack_records_only_witnessed_aggression(
    base_world, monkeypatch
):
    """A real decision/commit/MutualAttack lifecycle is the sole casus producer.

    ``MutualAttack`` is the initiative: it states that hostility began and
    resolves no battle, so the aggression lands in this month while the
    target's answer -- and any damage -- belongs to a later one.  The full
    public lifecycle is covered by the MutualAttack runtime witnesses; what is
    pinned here is who learns of the initiative.
    """

    actors = _war_world(base_world)
    aggressor = actors["aggressor"]
    victim = actors["victim"]

    import src.sim.simulator_engine.phases.actions as action_phase

    monkeypatch.setattr(
        action_phase.llm_ai,
        "decide",
        AsyncMock(
            return_value={
                aggressor: (
                    [("MutualAttack", {"target_avatar": victim.name})],
                    "I will attack the nearby rival.",
                    "Attack the rival.",
                    None,
                )
            }
        ),
    )

    events = await Simulator(base_world).step()
    aggression = next(
        event
        for event in events
        if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    )

    assert aggression.related_avatars == [aggressor.id, victim.id]
    assert base_world.institutional_knowledge.contains(
        sect_institution_id(actors["sect_two"].id), aggression.id
    )
    assert not base_world.institutional_knowledge.contains(
        sect_institution_id(actors["sect_one"].id), aggression.id
    )
    knowledge = base_world.institutional_knowledge.get_fact(
        sect_institution_id(actors["sect_two"].id), aggression.id
    )
    assert knowledge is not None
    assert knowledge.channel is KnowledgeChannel.MEMBER_WITNESS
    assert any(
        link.relation is CausalRelation.MOTIVATED_BY
        for link in aggression.causal_links
    )
    # The initiative alone: no battle was invented in this month, and exactly
    # one aggression exists for it.
    assert not [
        event
        for event in events
        if event.event_type in {"battle_result", "battle_kill"}
    ]
    assert (
        len([e for e in events if e.event_type == DELIBERATE_ATTACK_EVENT_TYPE]) == 1
    )


@pytest.mark.asyncio
async def test_reactive_counterattack_cannot_reuse_an_old_attack_decision_as_casus(
    base_world, monkeypatch
):
    """An old matching decision is insufficient without actor-choice origin."""

    actors = _war_world(base_world)
    aggressor = actors["aggressor"]
    victim = actors["victim"]

    import src.sim.simulator_engine.phases.actions as action_phase

    monkeypatch.setattr(
        action_phase.llm_ai,
        "decide",
        AsyncMock(
            return_value={
                victim: (
                    [("MutualAttack", {"target_avatar": aggressor.name})],
                    "An earlier attack decision.",
                    "Attack the rival.",
                    None,
                )
            }
        ),
    )
    await phase_decide_actions(base_world, [victim])
    victim.clear_plans()
    victim.load_decide_result_chain(
        [("MutualAttack", {"target_avatar": aggressor.name})],
        victim.thinking,
        "Reactive counterattack.",
        origin=ActionOrigin.REACTIVE_RESPONSE,
    )
    victim.commit_next_plan()
    # MutualAttack now waits for a real single-choice response.  This direct
    # lifecycle witness is outside Simulator.step(), so it must scope test
    # mode and consume the task instead of leaking it into pytest teardown.
    with llm_test_mode_scope(True):
        events = await victim.tick_action()
        response_task = victim.current_action.action._response_task
        assert response_task is not None
        await response_task
        events.extend(await victim.tick_action())

    assert not [
        event for event in events if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    ]


@pytest.mark.asyncio
async def test_save_load_preserves_grounded_evidence_knowledge_and_war(
    base_world, monkeypatch, tmp_path
):
    """The casus evidence remains canonical across the normal save boundary."""

    # The pending response is deliberately settled before the later annual
    # institutional reading.  A random failed Escape may legitimately cause
    # its defensive battle and alter material eligibility, which is outside
    # this save/load witness.
    monkeypatch.setattr("src.classes.action.escape.get_escape_success_rate", lambda *_args: 1.0)
    actors = _war_world(base_world)
    aggressor = actors["aggressor"]
    victim = actors["victim"]
    import src.sim.simulator_engine.phases.actions as action_phase

    monkeypatch.setattr(
        action_phase.llm_ai,
        "decide",
        AsyncMock(
            return_value={
                aggressor: (
                    [("MutualAttack", {"target_avatar": victim.name})],
                    "I will attack the nearby rival.",
                    "Attack the rival.",
                    None,
                )
            }
        ),
    )
    attack_cycle = await Simulator(base_world).step()
    aggression = next(
        event
        for event in attack_cycle
        if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    )
    _enable_annual_war(monkeypatch)
    _control_war_interpreter(monkeypatch)
    _advance_to_next_january(base_world)
    monkeypatch.setattr(action_phase.llm_ai, "decide", AsyncMock(return_value={}))
    declaration_cycle = await Simulator(base_world).step()
    declaration = next(
        event for event in declaration_cycle if event.event_type == WAR_DECLARED_EVENT_TYPE
    )
    assert are_sects_at_war(base_world, actors["sect_one"].id, actors["sect_two"].id)
    assert not [
        event
        for event in declaration_cycle
        if event.event_type in {"battle_result", "battle_kill"}
    ]
    assert not [
        event
        for event in declaration_cycle
        if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    ]
    save_path = tmp_path / "grounded-war-evidence.json"
    success, message = save_game(
        base_world, Simulator(base_world), base_world.existed_sects, save_path
    )
    assert success, message

    loaded, _simulator, _sects = load_game(save_path)
    institution_id = sect_institution_id(actors["sect_two"].id)
    loaded_aggression = loaded.event_manager.get_event_by_id(aggression.id)

    assert loaded_aggression is not None
    assert loaded_aggression.event_type == DELIBERATE_ATTACK_EVENT_TYPE
    assert loaded.institutional_knowledge.contains(institution_id, aggression.id)
    loaded_knowledge = loaded.institutional_knowledge.get_fact(
        institution_id, aggression.id
    )
    assert loaded_knowledge is not None
    assert loaded_knowledge.channel is KnowledgeChannel.MEMBER_WITNESS
    assert loaded.event_manager.get_event_by_id(declaration.id) is not None
    assert are_sects_at_war(loaded, actors["sect_one"].id, actors["sect_two"].id)


@pytest.mark.asyncio
async def test_failed_finalizer_reverts_attack_evidence_knowledge_and_war(
    base_world, monkeypatch
):
    """No attack, fact, knowledge or war relation escapes a failed commit."""

    actors = _war_world(base_world)
    aggressor = actors["aggressor"]
    victim = actors["victim"]
    import src.sim.simulator_engine.phases.actions as action_phase

    _enable_annual_war(monkeypatch)
    _control_war_interpreter(monkeypatch)
    monkeypatch.setattr(
        action_phase.llm_ai,
        "decide",
        AsyncMock(
            return_value={
                aggressor: (
                    [("MutualAttack", {"target_avatar": victim.name})],
                    "I will attack the nearby rival.",
                    "Attack the rival.",
                    None,
                )
            }
        ),
    )
    before_hp = (aggressor.hp.cur, victim.hp.cur)
    before_knowledge = base_world.institutional_knowledge.to_dict()
    before_relations = base_world.institutional_relations.to_dict()
    before_month = base_world.month_stamp
    before_events = base_world.event_manager.count()
    before_rng = random.getstate()
    attempted = []
    monkeypatch.setattr(
        base_world.event_manager,
        "commit_step",
        lambda events, _chapter: attempted.extend(events) or False,
    )

    with pytest.raises(EventPersistenceError):
        await Simulator(base_world).step()

    assert any(
        event.event_type == DELIBERATE_ATTACK_EVENT_TYPE for event in attempted
    )
    assert any(event.event_type == WAR_DECLARED_EVENT_TYPE for event in attempted)
    assert (aggressor.hp.cur, victim.hp.cur) == before_hp
    assert base_world.institutional_knowledge.to_dict() == before_knowledge
    assert base_world.institutional_relations.to_dict() == before_relations
    assert base_world.month_stamp == before_month
    assert base_world.event_manager.count() == before_events
    assert random.getstate() == before_rng
