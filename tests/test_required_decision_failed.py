"""Task 6: required-decision failure semantics.

Covers the three-way classification from docs/specs/causal-world-kernel.md
section 6.3:

- a provider/parse failure that escapes `llm_ai.decide` after the client's
  own retries must raise `RequiredDecisionFailed` from `phase_decide_actions`
  and propagate untouched through `SimulationPhaseRunner.run` and
  `Simulator.step()` into `GameLoopRunner.run_once`, which pauses the
  runtime with reason `required_decision_failed`;
- a response that parses but yields no avatar entry or an empty pairs list
  is a *valid empty decision* and must not raise or pause;
- rule-based test mode (`resolve_test_mode_task`) must never raise or pause
  either.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.classes.ai import LLMAI
from src.server.loop.runner import GameLoopRunner
from src.server.loop.tick_payload import TickPayloadBuilder
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.sim.simulator_engine.phases.actions import (
    RequiredDecisionFailed,
    phase_decide_actions,
)
from src.utils.llm.exceptions import LLMError, ProviderCallError, ProviderFailureKind
from src.utils.llm.runtime_mode import llm_test_mode_scope


@pytest.mark.asyncio
async def test_phase_decide_actions_raises_required_decision_failed_on_llm_error(
    base_world, dummy_avatar, mock_llm_managers
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(side_effect=LLMError("解析失败（重试 3 次后）"))

    with pytest.raises(RequiredDecisionFailed) as exc_info:
        await phase_decide_actions(base_world, [dummy_avatar])

    assert str(dummy_avatar.id) in exc_info.value.avatar_ids


@pytest.mark.asyncio
async def test_phase_decide_actions_raises_required_decision_failed_on_provider_call_error(
    base_world, dummy_avatar, mock_llm_managers
):
    """`ProviderCallError` is not an `LLMError` subclass (see
    src/utils/llm/exceptions.py), so it must be caught explicitly -- this is
    the transport-failure half of the required-failure set from §6.3."""
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(
        side_effect=ProviderCallError(ProviderFailureKind.NETWORK, "connection refused")
    )

    with pytest.raises(RequiredDecisionFailed) as exc_info:
        await phase_decide_actions(base_world, [dummy_avatar])

    assert str(dummy_avatar.id) in exc_info.value.avatar_ids


@pytest.mark.asyncio
async def test_phase_decide_actions_does_not_convert_a_non_llm_exception(
    base_world, dummy_avatar, mock_llm_managers
):
    """The classification must be strict: a bug inside `llm_ai.decide` (a
    programming error, not a provider/parse failure) must propagate as
    itself, so it is visible through `GameLoopRunner.run_once`'s generic
    `except Exception` instead of being misfiled as
    `required_decision_failed`. This is the actual boundary the diff
    creates -- raising something other than `LLMError`/`ProviderCallError`
    from *inside* the wrapped call must NOT be caught here."""
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(
        side_effect=AttributeError("'Avatar' object has no attribute 'foo'")
    )

    with pytest.raises(AttributeError):
        await phase_decide_actions(base_world, [dummy_avatar])


@pytest.mark.asyncio
async def test_phase_decide_actions_does_not_raise_on_valid_empty_decision(
    base_world, dummy_avatar, mock_llm_managers
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(return_value={})

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert events == []


@pytest.mark.asyncio
async def test_llm_ai_decide_in_rule_based_test_mode_returns_empty_without_raising(
    base_world, dummy_avatar
):
    base_world.avatar_manager.register_avatar(dummy_avatar)

    with llm_test_mode_scope(True):
        results = await LLMAI().decide(base_world, [dummy_avatar])

    assert results == {}


@pytest.mark.asyncio
async def test_simulation_phase_runner_propagates_required_decision_failed(
    base_world, dummy_avatar, mock_llm_managers
):
    """`RequiredDecisionFailed` must NOT be caught by `SimulationPhaseRunner.run`
    the way `SimulationStepAborted` is -- it must escape `run()` untouched."""
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(side_effect=LLMError("boom"))

    simulator = Simulator(base_world)
    runner = SimulationPhaseRunner(simulator)

    with pytest.raises(RequiredDecisionFailed):
        await runner.run()

    # The recorder cleanup in `finally` must still run even on this failure path.
    assert base_world.step_causal_recorder is None


@pytest.mark.asyncio
async def test_simulator_step_raises_and_does_not_advance_month_on_required_decision_failed(
    base_world, dummy_avatar, mock_llm_managers
):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    mock_llm_managers["ai"].decide = AsyncMock(side_effect=LLMError("boom"))

    sim = Simulator(base_world)
    month_before = int(base_world.month_stamp)

    with pytest.raises(RequiredDecisionFailed):
        await sim.step()

    assert int(base_world.month_stamp) == month_before


@pytest.mark.asyncio
async def test_simulator_step_still_aborts_cleanly_on_reset_request(base_world, mock_llm_managers):
    """A lifecycle reset must still resolve as an empty step, not a failure
    pause -- `SimulationStepAborted` and `RequiredDecisionFailed` must stay
    on separate, non-overlapping paths."""
    runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
    base_world.runtime = runtime
    sim = Simulator(base_world)
    runtime.request_reset()

    events = await sim.step()

    assert events == []


@pytest.mark.asyncio
async def test_run_once_pauses_runtime_with_required_decision_failed_reason():
    state = dict(DEFAULT_GAME_STATE)
    state["init_status"] = "ready"
    runtime = GameSessionRuntime(state)
    runtime.set_paused(False)

    async def _raise_step():
        raise RequiredDecisionFailed(["avatar-1"], "boom")

    sim = SimpleNamespace(step=_raise_step)
    world = SimpleNamespace(run_config_snapshot={})
    runtime.set_world_and_sim(world, sim)

    runner = GameLoopRunner(
        game_instance={},
        runtime=runtime,
        manager=SimpleNamespace(broadcast=AsyncMock()),
        tick_payload_builder=TickPayloadBuilder(
            build_avatar_updates=lambda: [],
            build_tick_state=lambda avatar_updates, events, world: {},
        ),
        should_trigger_auto_save=lambda world: (False, 0, 0),
        trigger_auto_save=lambda world, sim: None,
        build_auto_save_toast=lambda: {},
        get_logger=lambda: SimpleNamespace(logger=SimpleNamespace(error=lambda *a, **k: None)),
    )

    await runner.run_once()

    assert runtime.is_effectively_paused() is True
    assert runtime.get_pause_reason() == "required_decision_failed"
    # Resuming must clear the failure pause, not leave it stuck.
    runtime.set_paused(False)
    assert runtime.get_pause_reason() == ""


@pytest.mark.asyncio
async def test_run_once_does_not_pause_on_unrelated_exception():
    """The generic `except Exception` path must stay untouched: an unrelated
    bug must not be mistaken for a required-decision failure."""
    state = dict(DEFAULT_GAME_STATE)
    state["init_status"] = "ready"
    runtime = GameSessionRuntime(state)
    runtime.set_paused(False)

    async def _raise_step():
        raise ValueError("unrelated bug")

    sim = SimpleNamespace(step=_raise_step)
    world = SimpleNamespace(run_config_snapshot={})
    runtime.set_world_and_sim(world, sim)

    runner = GameLoopRunner(
        game_instance={},
        runtime=runtime,
        manager=SimpleNamespace(broadcast=AsyncMock()),
        tick_payload_builder=TickPayloadBuilder(
            build_avatar_updates=lambda: [],
            build_tick_state=lambda avatar_updates, events, world: {},
        ),
        should_trigger_auto_save=lambda world: (False, 0, 0),
        trigger_auto_save=lambda world, sim: None,
        build_auto_save_toast=lambda: {},
        get_logger=lambda: SimpleNamespace(logger=SimpleNamespace(error=lambda *a, **k: None)),
    )

    await runner.run_once()

    assert runtime.is_effectively_paused() is False
    assert runtime.get_pause_reason() == ""
