"""
End-to-end check that a decision made during Simulator.step() actually
reaches storage as a fact_kind=DECISION event, is hidden from the default
event page, and is addressable when a caller opts in.
"""
from unittest.mock import AsyncMock

import pytest

from src.classes.event import FactKind, NULL_EVENT
from src.sim.simulator import Simulator


@pytest.mark.asyncio
async def test_step_persists_decision_event_and_hides_it_by_default(
    base_world, dummy_avatar, mock_llm_managers
):
    base_world.avatar_manager.avatars[dummy_avatar.id] = dummy_avatar
    pairs = [("Respire", {})]
    mock_llm_managers["ai"].decide = AsyncMock(
        return_value={dummy_avatar: (pairs, "thinking", "objective", NULL_EVENT)}
    )

    sim = Simulator(base_world)
    await sim.step()

    assert dummy_avatar.current_decision_event_id != ""

    default_events = base_world.event_manager.get_recent_events(limit=200)
    assert all(e.fact_kind != FactKind.DECISION for e in default_events)

    all_events = base_world.event_manager.get_recent_events(limit=200, include_decisions=True)
    decision_events = [e for e in all_events if e.fact_kind == FactKind.DECISION]
    assert len(decision_events) == 1
    assert decision_events[0].id == dummy_avatar.current_decision_event_id
    assert decision_events[0].causal_payload["decision"]["chosen_chain"] == [
        {"action_name": "Respire", "params": {}}
    ]
