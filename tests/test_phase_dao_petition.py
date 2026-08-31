from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.event import Event, FactKind
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.phase_registry import create_dao_petition
from src.utils.llm.runtime_mode import llm_test_mode_scope


@pytest.mark.asyncio
async def test_monthly_dao_petition_phase_uses_test_mode_fallback_and_adds_causal_event(base_world, dummy_avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.BALANCE)
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.map.regions[region.id] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
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

    assert len(base_world.dao_petitions) == 1
    petition = base_world.dao_petitions[0]
    assert petition.motivated_event_ids == [cause.id]
    assert cause.content in petition.content
    phase_event = next(event for event in ctx.events if event is not cause)
    assert phase_event.fact_kind is FactKind.STATE_TRANSITION
    assert phase_event.causal_links[0].cause_event_id == cause.id
