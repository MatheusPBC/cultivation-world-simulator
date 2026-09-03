from __future__ import annotations

import inspect
from typing import Any

from .context import SimulationStepContext
from .month_transaction import SimulationMonthCheckpoint
from .phase_registry import SimulationPhase, get_simulation_phases


class SimulationStepAborted(Exception):
    """Raised internally when a lifecycle command supersedes the current step."""


class SimulationPhaseRunner:
    def __init__(self, simulator: Any, phases: tuple[SimulationPhase, ...] | None = None):
        self.simulator = simulator
        self.world = simulator.world
        self.phases = phases or get_simulation_phases()
        self.handlers = {
            phase.handler_name: phase.handler
            for phase in self.phases
        }

    def raise_if_reset_requested(self) -> None:
        runtime = getattr(self.world, "runtime", None)
        if runtime is not None and getattr(runtime, "is_reset_requested", lambda: False)():
            raise SimulationStepAborted()

    async def run(self) -> list[Any]:
        checkpoint = SimulationMonthCheckpoint.capture(self.world)
        ctx = SimulationStepContext.create(self.world)
        try:
            self.raise_if_reset_requested()
            for phase in self.phases:
                result = phase.handler(self.simulator, ctx)
                if inspect.isawaitable(result):
                    result = await result
                if phase.reset_check_after:
                    self.raise_if_reset_requested()
                if phase.name == "finalize_step":
                    return result or []
            return []
        except SimulationStepAborted:
            checkpoint.restore()
            return []
        except BaseException:
            checkpoint.restore()
            raise
        finally:
            # 因果记录器只在本轮 step 内有效：无论成功收尾、reset 中止还是
            # 任意异常向外传播，都要在这里统一清理，不依赖只在成功路径上
            # 才会执行的 finalize_step。不吞异常——这里不 except，只清理。
            self.world.step_causal_recorder = None
            self.world.step_invalidations = None
