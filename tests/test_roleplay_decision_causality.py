"""An accepted roleplay command is a decision of its own, or it never happened.

The player path used to queue plans without writing any `AgentDecision`, so an
Avatar acting under direct command carried whatever stale audit pointer it
happened to have and had to be fail-closed everywhere downstream.  These tests
pin the replacement: one accepted command produces exactly one canonical
`AgentDecision` with `source="player"`, and a command that is not accepted --
malformed, unavailable, stale, or whose fact could not be recorded -- leaves
nothing at all behind.

They exercise the service and the runtime directly.  The HTTP layer is not
covered here: the two existing public-API roleplay TestClient cases hang in
this environment, so an end-to-end HTTP check remains blocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.classes.action_runtime import ActionOrigin
from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.emotions import EmotionType
from src.classes.environment.sect_region import SectRegion
from src.classes.event import FactKind
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.services import roleplay_service
from src.server.services.roleplay_service import submit_roleplay_decision
from src.server.services.roleplay_state import create_roleplay_session_dict
from src.server.services.roleplay_state_machine import make_pending_decision_request
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint
from src.systems.avatar_aggression import (
    canonical_aggression,
    capture_aggression_snapshot,
    record_deliberate_attack,
)
from src.systems.avatar_decision import (
    DECISION_SOURCE_PLAYER,
    adopt_avatar_decision,
    build_avatar_decision_event,
    offered_actions,
)
from src.systems.cultivation import Realm
from src.systems.domain_affordance_registry import event_lookup
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.time import Month, Year, create_month_stamp


def _roleplay_runtime(world, avatar):
    """A runtime paused at this Avatar's own decision boundary.

    The pending request is built by its real owner, so the request token the
    tests submit is the one the gateway would have issued.
    """

    runtime = GameSessionRuntime(
        {**DEFAULT_GAME_STATE, "roleplay_session": create_roleplay_session_dict()}
    )
    world.runtime = runtime
    runtime.set_world_and_sim(world, None)
    session = runtime.get_roleplay_session()
    session["controlled_avatar_id"] = str(avatar.id)
    session["status"] = "awaiting_decision"
    session["pending_request"] = make_pending_decision_request(avatar=avatar)
    runtime.set_roleplay_auto_paused(True)
    return runtime


def _request_id(runtime) -> str:
    return str(runtime.get_roleplay_session()["pending_request"]["request_id"])


def _interpretation(avatar, pairs, **extra):
    return {
        avatar.name: {
            "action_name_params_pairs": pairs,
            **extra,
        }
    }


def _patch_interpretation(monkeypatch, response):
    call = AsyncMock(return_value=response)
    monkeypatch.setattr(roleplay_service, "call_llm_with_task_name", call)
    return call


def _decision_events(world):
    return [
        event
        for event in world.event_manager.get_recent_events(limit=50, include_decisions=True)
        if event.fact_kind is FactKind.DECISION
    ]


async def _submit(runtime, avatar, command_text="去修炼"):
    return await submit_roleplay_decision(
        runtime,
        avatar_id=str(avatar.id),
        request_id=_request_id(runtime),
        command_text=command_text,
    )


def _assert_nothing_accepted(runtime, world, avatar):
    """No trace of an acceptance: not in the Avatar, session or event store."""

    assert avatar.planned_actions == []
    assert avatar.current_decision_event_id == ""
    assert getattr(avatar, "_current_decision_payload", None) is None
    assert avatar.thinking == ""
    assert avatar.short_term_objective == ""
    assert _decision_events(world) == []
    session = runtime.get_roleplay_session()
    assert session["status"] == "awaiting_decision"
    assert session["pending_request"] is not None
    assert runtime.get("roleplay_auto_paused") is True


@pytest.mark.asyncio
async def test_accepted_command_writes_its_own_canonical_player_decision(
    monkeypatch, base_world, dummy_avatar
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(
        monkeypatch,
        _interpretation(
            dummy_avatar,
            [["Respire", {}]],
            avatar_thinking="调匀气息，先稳住根基。",
            short_term_objective="巩固练气",
            current_emotion=EmotionType.CALM.value,
        ),
    )

    result = await _submit(runtime, dummy_avatar)

    assert result["status"] == "ok"
    assert result["planned_action_count"] == 1
    decisions = _decision_events(base_world)
    assert len(decisions) == 1
    event = decisions[0]
    assert event.id == result["decision_event_id"]
    decision = event.causal_payload["decision"]
    assert decision["source"] == DECISION_SOURCE_PLAYER
    assert decision["subject_kind"] == "avatar"
    assert decision["subject_id"] == str(dummy_avatar.id)
    assert decision["chosen_chain"] == [{"action_name": "Respire", "params": {}}]
    assert decision["thinking"] == "调匀气息，先稳住根基。"
    assert decision["short_term_objective"] == "巩固练气"
    assert decision["considered_count"] == len(offered_actions(dummy_avatar))
    assert decision["rejected"] == []
    assert event.causal_payload["deltas"] == []

    # The audit the Avatar actually carries is this decision, and the queued
    # plan is marked as its own choice rather than a reaction.
    assert dummy_avatar.current_decision_event_id == event.id
    assert dummy_avatar._current_decision_payload is event.causal_payload
    assert [plan.action_name for plan in dummy_avatar.planned_actions] == ["Respire"]
    assert dummy_avatar.planned_actions[0].origin is ActionOrigin.ACTOR_CHOICE
    assert runtime.get_roleplay_session()["status"] == "observing"
    assert runtime.get("roleplay_auto_paused") is False


@pytest.mark.asyncio
async def test_accepted_command_keeps_raw_player_text_out_of_canonical_fields(
    monkeypatch, base_world, dummy_avatar
):
    """The player's keystrokes are chat, not the Avatar's own inner life."""

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(monkeypatch, _interpretation(dummy_avatar, [["Respire", {}]]))

    await _submit(runtime, dummy_avatar, command_text="快去打坐，别磨蹭")

    decision = _decision_events(base_world)[0].causal_payload["decision"]
    assert decision["thinking"] == ""
    assert decision["short_term_objective"] == ""
    assert dummy_avatar.thinking == ""
    assert dummy_avatar.short_term_objective == ""
    history = runtime.get_roleplay_session()["interaction_history"]
    assert [item["text"] for item in history if item["type"] == "command"] == [
        "快去打坐，别磨蹭"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_pairs",
    [
        pytest.param([["NotAnAction", {}]], id="unknown-action"),
        pytest.param([["Attack", {"avatar_name": "TestDummy"}]], id="not-publicly-offered"),
        pytest.param([["Respire", 7]], id="non-mapping-params"),
        pytest.param([["Respire", {"unexpected": 1}]], id="undeclared-parameter"),
        pytest.param([["MoveToDirection", {}]], id="missing-required-argument"),
        pytest.param([], id="empty-chain"),
    ],
)
async def test_malformed_or_unavailable_chain_changes_nothing(
    monkeypatch, base_world, dummy_avatar, raw_pairs
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(monkeypatch, _interpretation(dummy_avatar, raw_pairs))

    with pytest.raises(HTTPException) as excinfo:
        await _submit(runtime, dummy_avatar)

    assert excinfo.value.status_code == 422
    _assert_nothing_accepted(runtime, base_world, dummy_avatar)


@pytest.mark.asyncio
async def test_stale_request_never_applies_an_old_command(
    monkeypatch, base_world, dummy_avatar
):
    """Two boundaries opened at the same instant are still two boundaries.

    The clock is frozen so both request tokens are minted at an identical
    `time.time()`.  A token derived from a millisecond timestamp would be
    identical here and the stale command would be accepted as current, so
    this pins that request identity does not come from the clock.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    monkeypatch.setattr(
        "src.server.services.roleplay_state_machine.time.time", lambda: 1_700_000_000.0
    )
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    stale_request_id = _request_id(runtime)
    _patch_interpretation(monkeypatch, _interpretation(dummy_avatar, [["Respire", {}]]))
    # A new boundary opened while the player was still typing.
    superseding = make_pending_decision_request(avatar=dummy_avatar)
    assert superseding["request_id"] != stale_request_id
    assert superseding["created_at"] == 1_700_000_000.0
    runtime.get_roleplay_session()["pending_request"] = superseding

    with pytest.raises(HTTPException) as excinfo:
        await submit_roleplay_decision(
            runtime,
            avatar_id=str(dummy_avatar.id),
            request_id=stale_request_id,
            command_text="去修炼",
        )

    assert excinfo.value.status_code == 404
    assert avatar_has_no_plan_or_decision(dummy_avatar)
    assert _decision_events(base_world) == []


def avatar_has_no_plan_or_decision(avatar) -> bool:
    return (
        avatar.planned_actions == []
        and avatar.current_decision_event_id == ""
        and getattr(avatar, "_current_decision_payload", None) is None
    )


@pytest.mark.asyncio
async def test_replaced_world_never_applies_an_old_command(
    monkeypatch, base_world, base_map, dummy_avatar
):
    """A reset or load between interpretation and acceptance voids the command."""

    from src.classes.core.world import World

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    replacement = World(
        map=base_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY)
    )
    replacement.avatar_manager.register_avatar(dummy_avatar)

    async def _swap_world_then_answer(*_args, **_kwargs):
        runtime.set_world_and_sim(replacement, None)
        return _interpretation(dummy_avatar, [["Respire", {}]])

    monkeypatch.setattr(
        roleplay_service, "call_llm_with_task_name", _swap_world_then_answer
    )

    with pytest.raises(HTTPException) as excinfo:
        await _submit(runtime, dummy_avatar)

    assert excinfo.value.status_code == 409
    assert avatar_has_no_plan_or_decision(dummy_avatar)
    assert _decision_events(replacement) == []


@pytest.mark.asyncio
async def test_persistence_failure_leaves_no_accepted_command(
    monkeypatch, base_world, dummy_avatar
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(
        monkeypatch,
        _interpretation(
            dummy_avatar,
            [["Respire", {}]],
            avatar_thinking="想法",
            short_term_objective="目标",
            current_emotion=EmotionType.ANGRY.value,
        ),
    )
    monkeypatch.setattr(
        base_world.event_manager, "commit_step", lambda *_args, **_kwargs: False
    )
    emotion_before = dummy_avatar.emotion

    with pytest.raises(RuntimeError):
        await _submit(runtime, dummy_avatar)

    _assert_nothing_accepted(runtime, base_world, dummy_avatar)
    assert dummy_avatar.emotion == emotion_before
    session = runtime.get_roleplay_session()
    assert [item["type"] for item in session["interaction_history"]] == ["command"]


@pytest.mark.asyncio
async def test_failure_while_finishing_acceptance_leaves_no_partial_acceptance(
    monkeypatch, base_world, dummy_avatar
):
    """A fault after the plans are queued but before the fact is written.

    This is the ordering the acceptance depends on: the durable write happens
    last, so a failure anywhere in the in-memory work undoes the queue instead
    of leaving a half-accepted command -- and no decision fact exists to
    describe a chain nobody is going to run.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(monkeypatch, _interpretation(dummy_avatar, [["Respire", {}]]))

    def _boom(*_args, **_kwargs):
        raise RuntimeError("observing state could not be written")

    monkeypatch.setattr(roleplay_service, "_set_observing", _boom)

    with pytest.raises(RuntimeError):
        await _submit(runtime, dummy_avatar)

    _assert_nothing_accepted(runtime, base_world, dummy_avatar)


@pytest.mark.asyncio
async def test_monthly_rollback_keeps_the_accepted_command_and_adds_no_duplicate(
    monkeypatch, base_world, dummy_avatar
):
    """The command was accepted; a later failed month does not unaccept it.

    The submit lands between steps, so the next month's checkpoint already
    contains the queued plan and the audit pointer, and the decision fact lives
    in the event store's own transaction, which the checkpoint never touches.
    A rolled-back month therefore replays from the same accepted command and
    writes no second decision.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(
        monkeypatch,
        _interpretation(dummy_avatar, [["Respire", {}]], avatar_thinking="想法"),
    )
    result = await _submit(runtime, dummy_avatar)

    checkpoint = SimulationMonthCheckpoint.capture(base_world)
    dummy_avatar.clear_plans()
    dummy_avatar.current_decision_event_id = ""
    checkpoint.restore()

    restored = base_world.avatar_manager.get_avatar(str(dummy_avatar.id))
    assert [plan.action_name for plan in restored.planned_actions] == ["Respire"]
    assert restored.current_decision_event_id == result["decision_event_id"]
    assert restored.thinking == "想法"
    surviving = _decision_events(base_world)
    assert [event.id for event in surviving] == [result["decision_event_id"]]
    assert surviving[0].causal_payload["decision"]["source"] == DECISION_SOURCE_PLAYER


@pytest.mark.asyncio
async def test_session_reset_clears_runtime_state_but_keeps_the_canonical_decision(
    monkeypatch, base_world, dummy_avatar
):
    """The pending UI is runtime; the accepted decision is a fact.

    This exercises `clear_roleplay_session` directly -- the call `load`,
    `reset` and `reinit` all make -- not a real save/load round trip, which
    this slice does not cover.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)
    _patch_interpretation(monkeypatch, _interpretation(dummy_avatar, [["Respire", {}]]))
    result = await _submit(runtime, dummy_avatar)

    # The session reset that `load`/`reset`/`reinit` each perform.
    runtime.clear_roleplay_session()

    session = runtime.get_roleplay_session()
    assert session["status"] == "inactive"
    assert session["pending_request"] is None
    assert session["interaction_history"] == []
    persisted = base_world.event_manager.get_event_by_id(result["decision_event_id"])
    assert persisted is not None
    assert persisted.causal_payload["decision"]["source"] == DECISION_SOURCE_PLAYER


@pytest.mark.asyncio
async def test_test_mode_submit_never_reaches_a_provider_and_fails_closed(
    monkeypatch, base_world, dummy_avatar
):
    """A rule-based run refuses the command instead of calling out.

    The submit runs on a request task, so it does not inherit the game loop's
    LLM mode; entering the run's own scope is what keeps it off the network.
    The registered `action_decision` fallback returns an empty chain, which the
    acceptance boundary refuses -- fail closed, no invented command.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.run_config_snapshot = {"test_mode": True, "provider": "test"}
    runtime = _roleplay_runtime(base_world, dummy_avatar)

    def _provider_reached(*_args, **_kwargs):
        raise AssertionError("a rule-based run must not call a provider")

    monkeypatch.setattr(
        "src.utils.llm.client.call_llm_with_template", _provider_reached
    )

    with pytest.raises(HTTPException) as excinfo:
        await _submit(runtime, dummy_avatar)

    assert excinfo.value.status_code == 422
    _assert_nothing_accepted(runtime, base_world, dummy_avatar)


@pytest.mark.asyncio
async def test_prompt_assembly_failure_keeps_the_boundary_waiting(
    monkeypatch, base_world, dummy_avatar
):
    """Building the prompt is expensive and fallible; it must not strand the request.

    It walks the Avatar's expanded info, the semantic context and the world
    info, none of which is guaranteed to succeed.  That work therefore runs
    before the session moves to `submitting` and before the command is logged,
    so a fault leaves the same boundary open and unlogged rather than a request
    stuck mid-submission.
    """

    base_world.avatar_manager.register_avatar(dummy_avatar)
    runtime = _roleplay_runtime(base_world, dummy_avatar)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("world info could not be assembled")

    monkeypatch.setattr(base_world, "get_info", _boom)

    with pytest.raises(RuntimeError):
        await _submit(runtime, dummy_avatar, command_text="去修炼")

    _assert_nothing_accepted(runtime, base_world, dummy_avatar)
    assert runtime.get_roleplay_session()["interaction_history"] == []


def _two_sect_world(world):
    """Two authorized sects, each with a patriarch standing on the other."""

    headquarter = SectHeadQuarter(name="HQ", desc="", image=Path(""))
    sects = []
    for sect_id in (1, 2):
        region = SectRegion(
            id=7000 + sect_id,
            name=f"Sect {sect_id} HQ",
            desc="",
            sect_id=sect_id,
            sect_name=f"Sect {sect_id}",
            cors=[(0, 0)],
        )
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = [(0, 0)]
        sect = Sect(
            id=sect_id,
            name=f"Sect {sect_id}",
            desc="",
            member_act_style="",
            alignment=Alignment.NEUTRAL,
            headquarter=headquarter,
            technique_names=[],
        )
        patriarch = Avatar(
            world=world,
            name=f"Patriarch {sect_id}",
            id=f"decision-patriarch-{sect_id}",
            birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
            age=Age(30, Realm.Qi_Refinement),
            gender=Gender.MALE,
            pos_x=0,
            pos_y=0,
            root=Root.GOLD,
            alignment=Alignment.NEUTRAL,
            personas=[],
        )
        patriarch.weapon = None
        patriarch.technique = None
        patriarch.join_sect(sect, SectRank.Patriarch)
        world.avatar_manager.register_avatar(patriarch)
        sects.append(sect)
    world.map.update_sect_regions()
    world.existed_sects = sects
    world.sect_context.from_existed_sects(sects)
    world.run_config_snapshot = {"test_mode": True, "provider": "test"}
    bootstrap_institutional_authority(world)
    return sects


def test_a_player_authored_decision_can_ground_an_aggression_fact(base_world):
    """`source="player"` is now audited evidence, on the same strict terms.

    Nothing is relaxed for the player: the aggression still has to cite a real
    decision fact that names this exact attack and belongs to this attacker.
    What changes is only that a decision the player authored is no longer
    disqualified by its authorship alone.

    The audited step is `MutualAttack` with a `target_avatar` selector -- the
    one publicly offered action by which an Avatar opens hostilities, and one
    a player command may legitimately choose.  This test pins the audit
    contract only; the full public lifecycle is covered by the MutualAttack
    contracts and runtime witnesses.
    """

    _two_sect_world(base_world)
    initiator = base_world.avatar_manager.get_avatar("decision-patriarch-2")
    target = base_world.avatar_manager.get_avatar("decision-patriarch-1")
    params = {"target_avatar": target.name}

    decision_event = build_avatar_decision_event(
        base_world,
        initiator,
        [("MutualAttack", params)],
        "",
        "",
        source=DECISION_SOURCE_PLAYER,
        offered=offered_actions(initiator),
    )
    adopt_avatar_decision(initiator, decision_event)
    assert base_world.event_manager.commit_step([decision_event])

    snapshot = capture_aggression_snapshot(
        base_world,
        initiator,
        target,
        params=params,
        action_origin=ActionOrigin.ACTOR_CHOICE,
    )
    assert snapshot is not None
    assert snapshot.decision_event_id == decision_event.id

    aggression_event = record_deliberate_attack(
        base_world, snapshot, initiator=initiator, target=target
    )
    grounded = canonical_aggression(
        aggression_event, lookup=event_lookup(base_world, [aggression_event])
    )
    assert grounded is not None
    _event, aggression = grounded
    assert aggression["decision_event_id"] == decision_event.id
