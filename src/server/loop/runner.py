from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from .tick_payload import TickPayloadBuilder
from src.sim.simulator_engine.phases.actions import RequiredDecisionFailed
from src.utils.llm.runtime_mode import is_world_test_mode, llm_test_mode_scope


@dataclass(slots=True)
class GameLoopRunner:
    game_instance: dict[str, Any]
    runtime: Any
    manager: Any
    tick_payload_builder: TickPayloadBuilder
    should_trigger_auto_save: Callable[[Any], tuple[bool, int, int]]
    trigger_auto_save: Callable[[Any, Any], None]
    build_auto_save_toast: Callable[[], dict[str, Any]]
    get_logger: Callable[[], Any]
    sleep: Callable[[float], Any] = asyncio.sleep

    async def wait_for_initialization(self) -> bool:
        print("Background game loop started, waiting for initialization...")
        while self.game_instance.get("init_status") not in ("ready", "error"):
            await self.sleep(0.5)

        if self.game_instance.get("init_status") == "error":
            print("[game_loop] Initialization failed, game loop exiting.")
            return False

        print("[game_loop] Initialization completed, starting game loop.")
        return True

    async def run_forever(self) -> None:
        if not await self.wait_for_initialization():
            return

        while True:
            await self.sleep(1.0)
            await self.run_once()

    async def run_once(self) -> None:
        try:
            if self.runtime.is_effectively_paused():
                return
            if self.runtime.get("init_status") != "ready":
                return

            sim = self.runtime.get("sim")
            world = self.runtime.get("world")
            if not sim or not world:
                return

            async def _step_in_run_scope():
                with llm_test_mode_scope(is_world_test_mode(world)):
                    return await sim.step()

            events = await self.runtime.run_mutation(_step_in_run_scope)
            if getattr(self.runtime, "is_reset_requested", lambda: False)():
                return
            await self.manager.broadcast(self.tick_payload_builder.build(events=events, world=world))
            acknowledge_site_updates = getattr(
                getattr(world, "map", None),
                "acknowledge_infrastructure_site_updates",
                None,
            )
            if callable(acknowledge_site_updates):
                acknowledge_site_updates()

            should_auto_save, year, _month = self.should_trigger_auto_save(world)
            if should_auto_save:
                print(f"[Auto-Save] Triggering auto save for year {year}...")
                await asyncio.to_thread(self.trigger_auto_save, world, sim)
                await self.manager.broadcast(self.build_auto_save_toast())
                print("[Auto-Save] Auto save completed.")
        except RequiredDecisionFailed as exc:
            # A required `action_decision` LLM call failed after its own
            # retries. `finalize_step` never ran for this tick, so no events
            # were persisted and `world.month_stamp` was not advanced —
            # abort-before-mutate already held. What was missing is this
            # pause: without it the loop would silently retry the same month
            # forever. Resuming re-runs the month from phase 1.
            print(f"Game loop required decision failed: {exc}")
            self.get_logger().logger.error(f"Game loop required decision failed: {exc}", exc_info=True)
            self.runtime.set_failure_pause("required_decision_failed")
        except Exception as exc:
            print(f"Game loop error: {exc}")
            self.get_logger().logger.error(f"Game loop error: {exc}", exc_info=True)
