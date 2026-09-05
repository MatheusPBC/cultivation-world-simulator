"""Runtime witnesses for the public ``MutualAttack`` aggression path.

These deliberately use the public roleplay catalogue and the normal action
lifecycle.  They must not manufacture an internal ``Attack`` plan: an escape
is already a witnessed hostile initiative, while any responsive Attack remains
a response rather than a second casus belli.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalRelation
from src.classes.core.avatar import Avatar, Gender
from src.classes.event import FactKind
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.sect_region import SectRegion
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.server.runtime import GameSessionRuntime, create_default_game_state
from src.server.services.roleplay_service import (
    start_roleplay,
    submit_roleplay_choice,
    submit_roleplay_decision,
)
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.systems.avatar_aggression import DELIBERATE_ATTACK_EVENT_TYPE, canonical_aggression
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_diplomacy import WAR_DECLARED_EVENT_TYPE, sect_institution_id
from src.systems.institutional_war import DECLARATION_DOMAIN, process_institutional_war_declaration
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, *, avatar_id: str, name: str, position: tuple[int, int]) -> Avatar:
    avatar = Avatar(
        world=world, id=avatar_id, name=name,
        birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement), gender=Gender.MALE,
        pos_x=position[0], pos_y=position[1], root=Root.GOLD,
        alignment=Alignment.NEUTRAL, personas=[],
    )
    avatar.personas = []
    avatar.weapon = None
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _two_sect_witness_world(world):
    headquarters = SectHeadQuarter(name="Mutual attack HQ", desc="", image=Path(""))
    sects = [
        Sect(id=1, name="Azure Sect", desc="", member_act_style="", alignment=Alignment.NEUTRAL, headquarter=headquarters, technique_names=[]),
        Sect(id=2, name="Crimson Sect", desc="", member_act_style="", alignment=Alignment.NEUTRAL, headquarter=headquarters, technique_names=[]),
    ]
    for sect, region_id, coordinate in ((sects[0], 8101, (0, 0)), (sects[1], 8102, (8, 8))):
        region = SectRegion(id=region_id, name=f"{sect.name} HQ", desc="", sect_id=sect.id, sect_name=sect.name, cors=[coordinate])
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = [coordinate]

    initiator = _avatar(world, avatar_id="mutual-initiator", name="Azure Disciple", position=(0, 0))
    target = _avatar(world, avatar_id="mutual-target", name="Crimson Disciple", position=(0, 1))
    # Each force holder sees/participates in the hostility, making both sides
    # eligible to know it; only the victim side may later use it as a casus.
    azure_head = _avatar(world, avatar_id="azure-head", name="Patriarch Azure", position=(0, 0))
    crimson_head = _avatar(world, avatar_id="crimson-head", name="Patriarch Crimson", position=(0, 1))
    initiator.join_sect(sects[0], SectRank.OuterDisciple)
    azure_head.join_sect(sects[0], SectRank.Patriarch)
    target.join_sect(sects[1], SectRank.OuterDisciple)
    crimson_head.join_sect(sects[1], SectRank.Patriarch)
    world.map.update_sect_regions()
    world.existed_sects = sects
    world.sect_context.from_existed_sects(sects)
    world.run_config_snapshot = {"test_mode": True, "provider": "test", "npc_awakening_rate_per_month": 0.0}
    bootstrap_institutional_authority(world)
    return initiator, target, sects


def _only_mutual_action_lifecycle(monkeypatch) -> None:
    phases = tuple(phase for phase in get_simulation_phases() if phase.name in {"commit_next_plans", "execute_actions", "finalize_step"})
    monkeypatch.setattr("src.sim.simulator_engine.phase_runner.get_simulation_phases", lambda: phases)


async def _accept_public_mutual_attack(runtime, initiator, target, monkeypatch) -> str:
    start_roleplay(runtime, avatar_id=initiator.id)
    request_id = runtime.get_roleplay_session()["pending_request"]["request_id"]
    provider = AsyncMock(return_value={
        initiator.name: {
            "action_name_params_pairs": [["MutualAttack", {"target_avatar": target.name}]],
            "avatar_thinking": "I openly threaten the rival.",
            "short_term_objective": "Confront the rival.",
            "current_emotion": "emotion_calm",
        }
    })
    monkeypatch.setattr("src.server.services.roleplay_service.call_llm_with_task_name", provider)
    accepted = await submit_roleplay_decision(runtime, avatar_id=initiator.id, request_id=request_id, command_text="Confront the nearby rival.")
    assert accepted["status"] == "ok"
    provider.assert_awaited_once()
    return initiator.current_decision_event_id


async def _complete_escape_response(simulator, monkeypatch):
    # The response is independently selected by the target.  Escape settles
    # no battle, which makes the aggression's initiating attribution visible.
    response = AsyncMock(return_value={"choice": "Escape", "thinking": "Withdraw."})
    monkeypatch.setattr("src.systems.single_choice.engine.call_llm_with_task_name", response)
    # Escape itself owns the no-battle outcome.  Keep this deterministic: a
    # selected but failed escape is still hostility, but it is not this
    # witness's claim.
    monkeypatch.setattr("src.classes.action.escape.get_escape_success_rate", lambda *_args: 1.0)
    initiative_events = await simulator.step()
    await asyncio.sleep(0)
    return [*initiative_events, *(await simulator.step())]


def _aggression(events):
    return next(event for event in events if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE)


@pytest.mark.asyncio
async def test_public_mutual_attack_escape_records_initiator_decision_not_reactive_battle(base_world, monkeypatch):
    initiator, target, sects = _two_sect_witness_world(base_world)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    decision_id = await _accept_public_mutual_attack(runtime, initiator, target, monkeypatch)
    _only_mutual_action_lifecycle(monkeypatch)

    events = await _complete_escape_response(simulator, monkeypatch)
    aggression = _aggression(events)
    grounded = canonical_aggression(aggression, lookup=base_world.event_manager.get_event_by_id)

    assert grounded is not None
    assert aggression.related_avatars == [initiator.id, target.id]
    payload = aggression.causal_payload["avatar_aggression"]
    assert payload["initiator_avatar_id"] == initiator.id
    assert payload["target_avatar_id"] == target.id
    assert payload["decision_event_id"] == decision_id
    assert any(link.cause_event_id == decision_id and link.relation is CausalRelation.MOTIVATED_BY for link in aggression.causal_links)
    assert base_world.institutional_knowledge.contains(sect_institution_id(sects[1].id), aggression.id)
    assert not any(event.event_type in {"battle_result", "battle_kill"} for event in events)


@pytest.mark.asyncio
async def test_victim_institution_can_maintain_after_public_mutual_attack_without_forced_war(base_world, monkeypatch):
    initiator, target, sects = _two_sect_witness_world(base_world)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    await _accept_public_mutual_attack(runtime, initiator, target, monkeypatch)
    _only_mutual_action_lifecycle(monkeypatch)
    events = await _complete_escape_response(simulator, monkeypatch)
    aggression = _aggression(events)

    maintained = await process_institutional_war_declaration(
        base_world,
        event_overlays=(aggression,),
        injected_decisions={f"{DECLARATION_DOMAIN}:{sects[1].id}": DomainDecision(DomainDecisionKind.MAINTAIN, "Do not escalate.", None)},
    )
    assert any(event.fact_kind.value == "decision" for event in maintained)
    assert not any(event.event_type == WAR_DECLARED_EVENT_TYPE for event in maintained)


@pytest.mark.asyncio
async def test_defensive_attack_response_does_not_reverse_or_duplicate_public_aggression(base_world, monkeypatch):
    initiator, target, _sects = _two_sect_witness_world(base_world)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    decision_id = await _accept_public_mutual_attack(runtime, initiator, target, monkeypatch)
    _only_mutual_action_lifecycle(monkeypatch)

    monkeypatch.setattr(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        AsyncMock(return_value={"choice": "Attack", "thinking": "Defend myself."}),
    )
    events = [*(await simulator.step())]
    await asyncio.sleep(0)
    # The response installs a real internal Attack through its usual action
    # lifecycle; its consequences may point back to the initiative, but it
    # must never become a second (or reversed) public casus.
    events.extend(await simulator.step())
    aggressions = [event for event in events if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE]
    assert len(aggressions) == 1
    payload = aggressions[0].causal_payload["avatar_aggression"]
    assert payload["initiator_avatar_id"] == initiator.id
    assert payload["target_avatar_id"] == target.id
    assert payload["decision_event_id"] == decision_id
    battle_responses = [event for event in events if event.event_type in {"battle_result", "battle_kill"}]
    assert battle_responses
    assert all(
        any(link.cause_event_id == aggressions[0].id and link.relation is CausalRelation.RESPONSE_TO for link in event.causal_links)
        for event in battle_responses
    )


@pytest.mark.asyncio
async def test_player_escape_response_is_a_separate_decision_and_motivates_its_transition(base_world, monkeypatch):
    initiator, target, _sects = _two_sect_witness_world(base_world)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    base_world.runtime = runtime
    await _accept_public_mutual_attack(runtime, initiator, target, monkeypatch)
    _only_mutual_action_lifecycle(monkeypatch)
    monkeypatch.setattr("src.classes.action.escape.get_escape_success_rate", lambda *_args: 1.0)

    # The initiator's public command is already accepted.  The independently
    # controlled target now answers through the real unified choice resolver,
    # rather than an LLM stub or a hand-built response decision.
    session = runtime.get_roleplay_session()
    session.clear()
    session.update({"controlled_avatar_id": target.id, "status": "observing", "pending_request": None, "last_prompt_context": None})
    await simulator.step()
    await asyncio.sleep(0)
    pending = runtime.get_roleplay_session()["pending_request"]
    assert pending is not None
    assert [option["key"] for option in pending["options"]] == ["Escape", "Attack"]
    await submit_roleplay_choice(runtime, avatar_id=target.id, request_id=pending["request_id"], selected_key="Escape")
    await asyncio.sleep(0)
    response_events = await simulator.step()

    decision = next(
        event for event in response_events
        if event.fact_kind is FactKind.DECISION
        and event.causal_payload["decision"]["subject_id"] == target.id
    )
    transition = next(event for event in response_events if event.fact_kind is FactKind.STATE_TRANSITION)
    assert decision.causal_payload["decision"]["source"] == "player"
    assert decision.causal_payload["decision"]["chosen_chain"] == [{"action_name": "Escape", "params": {"avatar_name": initiator.id}}]
    assert decision.causal_payload["deltas"] == []
    assert any(link.cause_event_id == decision.id and link.relation is CausalRelation.MOTIVATED_BY for link in transition.causal_links)


@pytest.mark.asyncio
async def test_mutual_attack_response_rollback_retries_one_aggression_without_duplicate(base_world, monkeypatch):
    initiator, target, _sects = _two_sect_witness_world(base_world)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    decision_id = await _accept_public_mutual_attack(runtime, initiator, target, monkeypatch)
    _only_mutual_action_lifecycle(monkeypatch)

    response = AsyncMock(return_value={"choice": "Escape", "thinking": "Withdraw."})
    monkeypatch.setattr("src.systems.single_choice.engine.call_llm_with_task_name", response)
    monkeypatch.setattr("src.classes.action.escape.get_escape_success_rate", lambda *_args: 1.0)
    initiative_events = await simulator.step()
    initiative_aggression = _aggression(initiative_events)
    await asyncio.sleep(0)
    original_commit = base_world.event_manager.commit_step
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda *_args, **_kwargs: False)
    with pytest.raises(EventPersistenceError):
        await simulator.step()
    assert base_world.event_manager.get_event_by_id(decision_id) is not None
    assert base_world.event_manager.get_event_by_id(initiative_aggression.id) is not None

    monkeypatch.setattr(base_world.event_manager, "commit_step", original_commit)
    await simulator.step()
    stored = [event for event in base_world.event_manager.get_recent_events(limit=100, include_decisions=True) if event.event_type == DELIBERATE_ATTACK_EVENT_TYPE]
    assert [event.id for event in stored] == [initiative_aggression.id]
    assert initiative_aggression.causal_payload["avatar_aggression"]["decision_event_id"] == decision_id
