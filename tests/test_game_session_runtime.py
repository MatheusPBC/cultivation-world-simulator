import asyncio

import pytest

from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime


def test_reset_to_idle_restores_defaults_and_clears_runtime_state():
    state = dict(DEFAULT_GAME_STATE)
    state.update(
        {
            "world": object(),
            "sim": object(),
            "run_config": {"content_locale": "en-US"},
            "current_save_path": "save.json",
            "is_paused": False,
            "roleplay_auto_paused": True,
            "init_status": "ready",
            "init_phase": 4,
            "init_phase_name": "generating_avatars",
            "init_progress": 80,
            "init_error": "boom",
            "llm_check_failed": True,
            "llm_error_message": "bad key",
            "reset_requested": True,
        }
    )
    runtime = GameSessionRuntime(state)

    runtime.reset_to_idle()

    assert state["world"] is None
    assert state["sim"] is None
    assert state["run_config"] is None
    assert state["current_save_path"] is None
    assert state["is_paused"] is True
    assert state["roleplay_auto_paused"] is False
    assert state["init_status"] == "idle"
    assert state["init_phase"] == 0
    assert state["init_phase_name"] == ""
    assert state["init_progress"] == 0
    assert state["init_error"] is None
    assert state["llm_check_failed"] is False
    assert state["llm_error_message"] == ""
    assert state["reset_requested"] is False
    assert state["roleplay_session"]["controlled_avatar_id"] is None


def test_reset_request_can_be_signaled_before_mutation_lock_is_available():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))

    assert runtime.is_reset_requested() is False

    runtime.request_reset()
    assert runtime.is_reset_requested() is True

    runtime.clear_reset_request()
    assert runtime.is_reset_requested() is False


def test_roleplay_pause_state_is_counted_in_effective_pause():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))

    assert runtime.is_effectively_paused() is True

    runtime.set_paused(False)
    assert runtime.is_effectively_paused() is False

    runtime.set_roleplay_auto_paused(True)
    assert runtime.is_effectively_paused() is True
    assert runtime.get_pause_reason() == "roleplay_waiting"

    runtime.clear_roleplay_session()
    assert runtime.is_effectively_paused() is False


def test_default_roleplay_session_is_not_shared_between_runtimes():
    runtime_a = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime_a.get_roleplay_session()["pending_request"] = {"request_id": "leaked"}
    runtime_a.get_roleplay_session()["interaction_history"].append({"type": "test"})

    runtime_b = GameSessionRuntime(dict(DEFAULT_GAME_STATE))

    assert runtime_b.get_roleplay_session()["pending_request"] is None
    assert runtime_b.get_roleplay_session()["interaction_history"] == []
    assert DEFAULT_GAME_STATE["roleplay_session"]["pending_request"] is None
    assert DEFAULT_GAME_STATE["roleplay_session"]["interaction_history"] == []


def test_roleplay_pause_reason_reflects_choice_waiting():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    session = runtime.get_roleplay_session()
    session["controlled_avatar_id"] = "avatar-1"
    session["status"] = "awaiting_choice"
    session["pending_request"] = {"request_id": "choice-1", "type": "choice"}
    runtime.set_paused(False)
    runtime.set_roleplay_auto_paused(True)

    assert runtime.is_effectively_paused() is True
    assert runtime.get_pause_reason() == "roleplay_waiting_choice"


def test_clear_roleplay_session_cancels_pending_choice_future():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    loop = asyncio.new_event_loop()
    try:
        future = loop.create_future()
        session = runtime.get_roleplay_session()
        session["_choice_future"] = future

        runtime.clear_roleplay_session()

        assert future.cancelled() is True
        assert runtime.get_roleplay_session()["status"] == "inactive"
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_run_mutation_serializes_concurrent_operations():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    execution_order: list[str] = []

    async def _slow(name: str, delay: float):
        execution_order.append(f"{name}:start")
        await asyncio.sleep(delay)
        execution_order.append(f"{name}:end")

    await asyncio.gather(
        runtime.run_mutation(_slow, "first", 0.03),
        runtime.run_mutation(_slow, "second", 0.0),
    )

    assert execution_order == [
        "first:start",
        "first:end",
        "second:start",
        "second:end",
    ]


def test_failure_pause_outranks_roleplay_auto_pause_reason():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_paused(False)
    runtime.set_roleplay_auto_paused(True)
    session = runtime.get_roleplay_session()
    session["status"] = "awaiting_decision"

    assert runtime.get_pause_reason() == "roleplay_waiting_decision"

    runtime.set_failure_pause("required_decision_failed")

    assert runtime.is_effectively_paused() is True
    assert runtime.get_pause_reason() == "required_decision_failed"
    # The roleplay auto-pause flag itself is untouched by the failure pause;
    # only the reported reason is overridden.
    assert runtime.get("roleplay_auto_paused") is True


def test_resuming_from_failure_pause_falls_back_to_a_still_pending_roleplay_wait():
    """A failure pause must not strand or clear a legitimate roleplay
    `pending_request`: resuming (`set_paused(False)`) drops only the
    `required_decision_failed` override, and if roleplay is still waiting on
    a decision the runtime stays paused for that reason instead."""
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_roleplay_auto_paused(True)
    session = runtime.get_roleplay_session()
    session["status"] = "awaiting_decision"
    session["pending_request"] = {"request_id": "roleplay-decision-1"}
    runtime.set_failure_pause("required_decision_failed")

    assert runtime.get_pause_reason() == "required_decision_failed"

    runtime.set_paused(False)

    assert runtime.is_effectively_paused() is True
    assert runtime.get_pause_reason() == "roleplay_waiting_decision"
    # The pending request itself was never touched by the failure pause.
    assert runtime.get_roleplay_session()["pending_request"] == {"request_id": "roleplay-decision-1"}


def test_set_paused_false_clears_failure_pause_reason():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_failure_pause("required_decision_failed")

    runtime.set_paused(False)

    assert runtime.get_pause_reason() == ""
    assert runtime.is_effectively_paused() is False


def test_set_paused_true_also_clears_a_stale_failure_pause_reason():
    """The save-load path pauses a freshly loaded world via
    `set_paused(True)` (not `reset_to_idle`/`mark_pending_initialization`),
    so a `required_decision_failed` override left over from a previous world
    must not leak into it -- an external agent reading
    `/api/v1/query/runtime/status` for the new world must not see a failure
    reason for a decision that never happened in it."""
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_failure_pause("required_decision_failed")

    runtime.set_paused(True)

    assert runtime.get("pause_reason_override") == ""
    assert runtime.get_pause_reason() == "paused"
    assert runtime.is_effectively_paused() is True


def test_reset_to_idle_clears_failure_pause_reason():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_failure_pause("required_decision_failed")

    runtime.reset_to_idle()

    # The runtime is still paused (idle is a paused state), but the specific
    # `required_decision_failed` override must not survive the reset -- it
    # falls back to the generic "paused" reason.
    assert runtime.get("pause_reason_override") == ""
    assert runtime.get_pause_reason() == "paused"


def test_mark_pending_initialization_clears_failure_pause_reason():
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    runtime.set_failure_pause("required_decision_failed")

    runtime.mark_pending_initialization(clear_world=True)

    assert runtime.get("pause_reason_override") == ""
    assert runtime.get_pause_reason() == "paused"
