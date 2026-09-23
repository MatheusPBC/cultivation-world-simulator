"""Contract tests for the bounded medieval campaign provider probe."""

import asyncio
import json

import pytest

from src.classes.causal_origin import CausalOrigin
from src.sim.medieval import ai_decider
from src.sim.medieval.persistence import world_snapshot
from src.sim.medieval.strategy_response import defense_adoption_options
from tools.medieval_campaign_provider_probe import (
    OWNER,
    _occupied_campaign_world,
    run,
)


def test_campaign_probe_requires_configured_provider(monkeypatch):
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    with pytest.raises(RuntimeError, match="real provider is not configured"):
        asyncio.run(run())


def test_campaign_probe_uses_one_bounded_call_and_only_interprets(monkeypatch):
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    calls = []

    async def choose_first(prompt, *args, **kwargs):
        calls.append(json.loads(prompt[prompt.index("{"):]))
        return {"selected_id": calls[-1]["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_first)
    result = asyncio.run(run())

    assert len(calls) == 1
    assert result["selected_id"] != ai_decider.NO_ACTION
    assert result["receipt_type"] == ai_decider.INTERPRETED_EVENT
    assert result["receipt_causal_origin"] == CausalOrigin.LLM_INTERPRETATION.value
    assert result["receipt_has_delta"] is False
    assert result["real_ai_calls"] == 1


def test_campaign_probe_can_record_no_action_without_material_owner(monkeypatch):
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def decline(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", decline)
    result = asyncio.run(run())

    assert result["selected_id"] == ai_decider.NO_ACTION
    assert result["receipt_type"] == ai_decider.DECLINED_EVENT
    assert result["receipt_causal_origin"] == CausalOrigin.LLM_INTERPRETATION.value
    assert result["receipt_has_delta"] is False


def test_campaign_fixture_is_unchanged_by_direct_probe_call(monkeypatch):
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    world, _, report = _occupied_campaign_world(73)
    world.config = world.config.model_copy(update={
        "ai_enabled": True,
        "ai_calls_per_step": 1,
        "ai_max_calls": 1,
    })
    before = world_snapshot(world)
    options = [{"id": item.id, "label": "Adotar a resposta defensiva observada."}
               for item in defense_adoption_options(world, OWNER)]

    async def choose_first(prompt, *args, **kwargs):
        return {"selected_id": options[0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_first)
    selected = asyncio.run(ai_decider.select_option(
        world, OWNER, {"campaign_probe": True, "report_event_id": report.event_id}, options,
    ))

    assert selected == options[0]["id"]
    after = world_snapshot(world)
    assert after["society"] == before["society"]
    assert after["economy"] == before["economy"]
    assert after["strategy"] == before["strategy"]
