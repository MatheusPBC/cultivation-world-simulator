"""Provider choices for the bounded civic-demand vertical."""

import pytest

from src.classes.event import FactKind
from src.sim.medieval import ai_decider
from src.sim.medieval.civic_protest import civic_protest_options
from src.sim.medieval.civic_protest_policy import review_civic_protests_with_provider
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.run.medieval_world import create_medieval_world


def _pressured(world):
    settlement_id = "pedraclara"
    need = world.economy.needs[settlement_id]
    world.economy.needs[settlement_id] = need.model_copy(update={"missing_food": 8, "unrest": 350})
    refresh_settlement_reports(world)
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == settlement_id and item.count >= 5)
    option = civic_protest_options(world, group.id)[0]
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 10, "ai_max_calls": 20})
    return group, option


@pytest.mark.asyncio
async def test_provider_selects_an_existing_civic_affordance(monkeypatch):
    world = create_medieval_world(73)
    group, option = _pressured(world)

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def call_llm_json(prompt, *args, **kwargs):
        assert option.id in prompt
        return {"selected_id": option.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    assert await review_civic_protests_with_provider(world)
    protest = next(item for item in world.society.civic_protests.values() if item.group_id == group.id)
    decision = next(event for event in world.events
                    if event.fact_kind == FactKind.DECISION
                    and event.decision is not None
                    and event.decision.get("selected_affordance_id") == option.id)
    assert protest.decision_event_id == decision.id
    assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [{"selected_id": "forged:civic"}, {"selected_id": "NO_ACTION"}])
async def test_provider_invalid_or_no_action_does_not_open_protest(monkeypatch, answer):
    world = create_medieval_world(73)
    _group, _option = _pressured(world)
    before = len(world.events)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def call_llm_json(prompt, *args, **kwargs):
        return answer

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    assert not await review_civic_protests_with_provider(world)
    assert not world.society.civic_protests
    receipts = [event for event in world.events[before:]
                if event.event_type in {ai_decider.INTERPRETED_EVENT, ai_decider.FAILED_EVENT}]
    assert receipts and all(event.deltas == () for event in receipts)
    assert not any(event.fact_kind == FactKind.DECISION for event in world.events[before:])
