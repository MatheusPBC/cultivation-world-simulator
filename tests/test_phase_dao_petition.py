from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event, FactKind
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phase_registry import process_dao_rites


@pytest.mark.asyncio
async def test_monthly_dao_phase_does_not_synthesize_an_institutional_rite(
    base_world, dummy_avatar
):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.BALANCE)
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.map.regions[region.id] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )
    ctx = SimulationStepContext.create(base_world)
    cause = Event(
        base_world.month_stamp,
        "A consequential court decision becomes public.",
        related_avatars=[dummy_avatar.id],
        fact_kind=FactKind.DECISION,
        is_major=True,
    )
    ctx.add_events([cause])

    await process_dao_rites(SimpleNamespace(world=base_world), ctx)

    assert base_world.dao_petitions == []
    assert ctx.events == [cause]
