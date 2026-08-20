"""
`world.step_causal_recorder` must be cleared on every exit from
`SimulationPhaseRunner.run` -- success, `SimulationStepAborted` (reset), and
any other exception escaping a phase handler -- not only on the success path
through `finalize_step`.

Fixes the Minor finding in
.superpowers/sdd/2026-08-20-causal-world-kernel/task-3-review.md.
"""
from types import SimpleNamespace

import pytest

from src.sim.simulator_engine.causal_recorder import CausalRecorder
from src.sim.simulator_engine.phase_registry import SimulationPhase
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner, SimulationStepAborted


def _runner_with_single_phase(base_world, handler, *, reset_check_after=True):
    simulator = SimpleNamespace(world=base_world)
    phase = SimulationPhase(
        name="fake_phase",
        index=1,
        handler_name="fake_phase",
        handler=handler,
        reset_check_after=reset_check_after,
    )
    return SimulationPhaseRunner(simulator, phases=(phase,))


class TestCausalRecorderClearedOnAbort:
    @pytest.mark.asyncio
    async def test_recorder_is_cleared_when_a_reset_aborts_the_step(self, base_world):
        seen_recorder_during_phase = []

        def handler(_simulator, ctx):
            seen_recorder_during_phase.append(getattr(ctx.world, "step_causal_recorder", None))
            raise SimulationStepAborted()

        runner = _runner_with_single_phase(base_world, handler)

        result = await runner.run()

        assert result == []
        # sanity: the recorder really was attached while the phase ran
        assert isinstance(seen_recorder_during_phase[0], CausalRecorder)
        # the Task 3 review finding: it must not survive the abort
        assert base_world.step_causal_recorder is None

    @pytest.mark.asyncio
    async def test_recorder_is_cleared_when_reset_is_requested_before_any_phase_runs(self, base_world):
        runtime = SimpleNamespace(is_reset_requested=lambda: True)
        base_world.runtime = runtime
        try:
            runner = _runner_with_single_phase(base_world, handler=lambda s, c: None)
            result = await runner.run()
            assert result == []
            assert base_world.step_causal_recorder is None
        finally:
            base_world.runtime = None


class TestCausalRecorderClearedOnException:
    @pytest.mark.asyncio
    async def test_recorder_is_cleared_and_exception_still_propagates(self, base_world):
        seen_recorder_during_phase = []

        def handler(_simulator, ctx):
            seen_recorder_during_phase.append(getattr(ctx.world, "step_causal_recorder", None))
            raise RuntimeError("boom")

        runner = _runner_with_single_phase(base_world, handler)

        with pytest.raises(RuntimeError, match="boom"):
            await runner.run()

        # the exception was not swallowed (proven by pytest.raises above);
        # the recorder must still be cleared despite finalize_step never running
        assert isinstance(seen_recorder_during_phase[0], CausalRecorder)
        assert base_world.step_causal_recorder is None

    @pytest.mark.asyncio
    async def test_recorder_is_cleared_when_an_async_phase_handler_raises(self, base_world):
        async def handler(_simulator, _ctx):
            raise ValueError("async boom")

        runner = _runner_with_single_phase(base_world, handler)

        with pytest.raises(ValueError, match="async boom"):
            await runner.run()

        assert base_world.step_causal_recorder is None


class TestCausalRecorderClearedOnSuccess:
    @pytest.mark.asyncio
    async def test_recorder_is_still_cleared_on_normal_finalize_step_completion(self, base_world):
        from src.sim.simulator_engine.phase_registry import finalize_step_phase

        finalize_phase = SimulationPhase(
            name="finalize_step",
            index=1,
            handler_name="finalize_step",
            handler=finalize_step_phase,
            reset_check_after=False,
        )
        simulator = SimpleNamespace(world=base_world)
        runner = SimulationPhaseRunner(simulator, phases=(finalize_phase,))

        events = await runner.run()

        assert events == []
        assert base_world.step_causal_recorder is None
