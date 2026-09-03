from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.server.loop import GameLoopRunner, TickPayloadBuilder
from src.server.runtime import GameSessionRuntime
from src.server.runtime.session import create_default_game_state


def _runner(*, broadcast: AsyncMock, acknowledge: Mock) -> GameLoopRunner:
    state = create_default_game_state()
    state["init_status"] = "ready"
    runtime = GameSessionRuntime(state)
    runtime.set_paused(False)

    async def step():
        return []

    world = SimpleNamespace(
        run_config_snapshot={"test_mode": True},
        map=SimpleNamespace(acknowledge_infrastructure_site_updates=acknowledge),
    )
    runtime.set_world_and_sim(world, SimpleNamespace(step=step))
    return GameLoopRunner(
        game_instance={},
        runtime=runtime,
        manager=SimpleNamespace(broadcast=broadcast),
        tick_payload_builder=TickPayloadBuilder(
            build_avatar_updates=lambda: [],
            build_tick_state=lambda _avatars, _events, _world: {"type": "tick"},
        ),
        should_trigger_auto_save=lambda _world: (False, 0, 0),
        trigger_auto_save=lambda _world, _sim: None,
        build_auto_save_toast=lambda: {},
        get_logger=lambda: SimpleNamespace(logger=SimpleNamespace(error=lambda *_a, **_kw: None)),
    )


@pytest.mark.asyncio
async def test_site_updates_are_acknowledged_only_after_successful_broadcast():
    acknowledge = Mock()
    runner = _runner(broadcast=AsyncMock(), acknowledge=acknowledge)

    await runner.run_once()

    acknowledge.assert_called_once_with()


@pytest.mark.asyncio
async def test_site_updates_remain_pending_when_broadcast_fails():
    acknowledge = Mock()
    runner = _runner(
        broadcast=AsyncMock(side_effect=RuntimeError("network unavailable")),
        acknowledge=acknowledge,
    )

    await runner.run_once()

    acknowledge.assert_not_called()
