"""Runtime witnesses for a public player-authored Rest decision."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.event import FactKind
from src.classes.hp import HP
from src.server.runtime import GameSessionRuntime, create_default_game_state
from src.server.services.roleplay_service import start_roleplay, submit_roleplay_decision
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.sim.simulator_engine.phase_registry import get_simulation_phases


async def _accept_player_rest(runtime, avatar, monkeypatch) -> str:
    start_roleplay(runtime, avatar_id=avatar.id)
    request_id = runtime.get_roleplay_session()["pending_request"]["request_id"]
    response = {
        avatar.name: {
            "action_name_params_pairs": [["Rest", {}]],
            "avatar_thinking": "I need to recover before continuing.",
            "short_term_objective": "Recover from my injuries.",
            "current_emotion": "emotion_calm",
        }
    }
    provider = AsyncMock(return_value=response)
    monkeypatch.setattr("src.server.services.roleplay_service.call_llm_with_task_name", provider)
    result = await submit_roleplay_decision(
        runtime, avatar_id=avatar.id, request_id=request_id, command_text="Rest and recover."
    )
    assert result["status"] == "ok"
    provider.assert_awaited_once()
    return avatar.current_decision_event_id


def _limit_month_to_rest_lifecycle(monkeypatch) -> None:
    """Keep this witness on the real Simulator.step transaction, narrowly.

    The player plan is already accepted, so unrelated world generation and
    collective reactions are not evidence for this contract.
    """
    phases = tuple(
        phase for phase in get_simulation_phases()
        if phase.name in {"commit_next_plans", "execute_actions", "finalize_step"}
    )
    monkeypatch.setattr(
        "src.sim.simulator_engine.phase_runner.get_simulation_phases",
        lambda: phases,
    )


def _hp_recovery_event(events, avatar_id: str):
    return next(
        event
        for event in events
        if any(
            delta.get("owner_id") == avatar_id and delta.get("aspect") == "hp"
            for delta in (event.causal_payload or {}).get("deltas", [])
            if isinstance(delta, dict)
        )
    )
@pytest.mark.asyncio
async def test_player_roleplay_rest_persists_decision_and_recovers_hp(
    base_world, dummy_avatar, monkeypatch
):
    avatar = dummy_avatar
    avatar.hp = HP(100, 50)
    base_world.avatar_manager.register_avatar(avatar)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, Simulator(base_world))

    decision_id = await _accept_player_rest(runtime, avatar, monkeypatch)
    _limit_month_to_rest_lifecycle(monkeypatch)
    decision = base_world.event_manager.get_event_by_id(decision_id)
    assert decision is not None
    assert decision.fact_kind is FactKind.DECISION
    assert decision.causal_payload["deltas"] == []
    assert decision.causal_payload["decision"]["source"] == "player"

    await runtime.get_simulator().step()
    await runtime.get_simulator().step()
    hp_before_recovery = avatar.hp.cur
    events = await runtime.get_simulator().step()
    recovery = _hp_recovery_event(events, avatar.id)
    assert any(
        link.cause_event_id == decision_id and link.relation is CausalRelation.MOTIVATED_BY
        for link in recovery.causal_links
    )
    assert avatar.hp.cur > hp_before_recovery
    assert any(
        delta["owner_id"] == avatar.id
        and delta["aspect"] == "hp"
        and delta["before"] == str(hp_before_recovery)
        for delta in recovery.causal_payload["deltas"]
    )


@pytest.mark.asyncio
async def test_player_rest_final_month_rollback_preserves_acceptance_without_duplicate(
    base_world, dummy_avatar, monkeypatch
):
    avatar = dummy_avatar
    avatar.hp = HP(100, 50)
    base_world.avatar_manager.register_avatar(avatar)
    simulator = Simulator(base_world)
    runtime = GameSessionRuntime(create_default_game_state())
    runtime.set_world_and_sim(base_world, simulator)
    decision_id = await _accept_player_rest(runtime, avatar, monkeypatch)
    _limit_month_to_rest_lifecycle(monkeypatch)

    await simulator.step()
    await simulator.step()
    hp_before_final_month = avatar.hp.cur
    elapsed_before_final_month = avatar.current_action.action.start_monthstamp

    original_commit = base_world.event_manager.commit_step
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda *_args, **_kwargs: False)
    with pytest.raises(EventPersistenceError):
        await simulator.step()

    assert avatar.hp.cur == hp_before_final_month
    assert avatar.current_action.action.start_monthstamp == elapsed_before_final_month
    assert base_world.event_manager.get_event_by_id(decision_id) is not None
    assert [
        event for event in base_world.event_manager.get_recent_events(limit=100, include_decisions=True)
        if event.id == decision_id
    ]

    monkeypatch.setattr(base_world.event_manager, "commit_step", original_commit)
    events = await simulator.step()
    recovery = _hp_recovery_event(events, avatar.id)
    assert any(
        link.cause_event_id == decision_id and link.relation is CausalRelation.MOTIVATED_BY
        for link in recovery.causal_links
    )
    assert avatar.hp.cur > hp_before_final_month
    decisions = [
        event for event in base_world.event_manager.get_recent_events(limit=100, include_decisions=True)
        if event.fact_kind is FactKind.DECISION and event.id == decision_id
    ]
    assert len(decisions) == 1
