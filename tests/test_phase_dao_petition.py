from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.event import Event, FactKind
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phase_registry import create_dao_petition
from src.utils.llm.runtime_mode import llm_test_mode_scope


@pytest.mark.asyncio
async def test_monthly_dao_phase_records_a_contested_rite_before_any_audience(
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

    with llm_test_mode_scope(True):
        await create_dao_petition(SimpleNamespace(world=base_world), ctx)

    assert base_world.dao_petitions == []
    phase_event = next(event for event in ctx.events if event is not cause)
    assert phase_event.event_type == "dao_rite"
    assert phase_event.fact_kind is FactKind.DECISION
    assert phase_event.causal_links[0].cause_event_id == cause.id
