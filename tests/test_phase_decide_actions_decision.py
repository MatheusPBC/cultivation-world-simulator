"""
`phase_decide_actions` emits an audit fact_kind=DECISION Event carrying the
AgentDecision at the point an LLM decision is committed to a chain, and sets
a runtime-only identity on the Avatar so later months can relate their events
back to it. See docs/specs/causal-world-kernel.md section 5.4.
"""
from unittest.mock import AsyncMock

import pytest

from src.classes.actions import get_action_infos
from src.classes.event import FactKind, NULL_EVENT
from src.sim.simulator_engine.phases.actions import phase_decide_actions


@pytest.mark.asyncio
async def test_phase_decide_actions_emits_decision_event(dummy_avatar, base_world, mock_llm_managers):
    pairs = [("Respire", {})]
    mock_llm_managers["ai"].decide = AsyncMock(
        return_value={dummy_avatar: (pairs, "I should cultivate.", "Reach the next realm", NULL_EVENT)}
    )

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert len(events) == 1
    event = events[0]
    assert event.fact_kind == FactKind.DECISION
    assert event.related_avatars == [dummy_avatar.id]
    assert event.is_major is False
    assert event.is_story is False

    decision = event.causal_payload["decision"]
    assert decision["subject_kind"] == "avatar"
    assert decision["subject_id"] == str(dummy_avatar.id)
    assert decision["source"] == "llm"
    assert decision["chosen_chain"] == [{"action_name": "Respire", "params": {}}]
    assert decision["thinking"] == "I should cultivate."
    assert decision["short_term_objective"] == "Reach the next realm"
    assert decision["rejected"] == []


@pytest.mark.asyncio
async def test_phase_decide_actions_sets_runtime_decision_identity_on_avatar(
    dummy_avatar, base_world, mock_llm_managers
):
    pairs = [("Respire", {})]
    mock_llm_managers["ai"].decide = AsyncMock(
        return_value={dummy_avatar: (pairs, "thinking", "objective", NULL_EVENT)}
    )

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert dummy_avatar.current_decision_event_id == events[0].id


@pytest.mark.asyncio
async def test_phase_decide_actions_considered_count_matches_offered_action_catalog(
    dummy_avatar, base_world, mock_llm_managers
):
    pairs = [("Respire", {})]
    mock_llm_managers["ai"].decide = AsyncMock(
        return_value={dummy_avatar: (pairs, "thinking", "objective", NULL_EVENT)}
    )
    expected_considered = len(get_action_infos(dummy_avatar))

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert events[0].causal_payload["decision"]["considered_count"] == expected_considered


@pytest.mark.asyncio
async def test_phase_decide_actions_multi_plan_chain_lands_in_chosen_chain(
    dummy_avatar, base_world, mock_llm_managers
):
    pairs = [("Respire", {}), ("Meditate", {"duration": 3})]
    mock_llm_managers["ai"].decide = AsyncMock(
        return_value={dummy_avatar: (pairs, "thinking", "objective", NULL_EVENT)}
    )

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert events[0].causal_payload["decision"]["chosen_chain"] == [
        {"action_name": "Respire", "params": {}},
        {"action_name": "Meditate", "params": {"duration": 3}},
    ]


@pytest.mark.asyncio
async def test_phase_decide_actions_returns_no_events_when_nobody_needs_deciding(
    dummy_avatar, base_world, mock_llm_managers
):
    events = await phase_decide_actions(base_world, [])

    assert events == []


@pytest.mark.asyncio
async def test_phase_decide_actions_returns_no_events_when_llm_skips_avatar(
    dummy_avatar, base_world, mock_llm_managers
):
    mock_llm_managers["ai"].decide = AsyncMock(return_value={})

    events = await phase_decide_actions(base_world, [dummy_avatar])

    assert events == []
    assert dummy_avatar.current_decision_event_id == ""
