"""Focused contract tests for the bounded campaign-supply probe."""

import asyncio
import json

from src.sim.medieval import ai_decider
from src.sim.medieval.persistence import load_world
from tools.medieval_campaign_supply_probe import run


def _provider(monkeypatch, selected_id):
    calls = []

    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        calls.append(payload)
        return {"selected_id": selected_id(payload) if callable(selected_id) else selected_id}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    return calls


def test_supply_probe_dispatches_then_fulfills_without_second_provider_call(monkeypatch, tmp_path):
    calls = _provider(monkeypatch, lambda payload: payload["choices"][0]["id"])
    result = asyncio.run(run(output=tmp_path / "fulfilled.mws"))

    assert len(calls) == 1
    assert result["no_action"] is False
    assert result["notice_state"] == "fulfilled"
    assert result["freight_count"] >= 1
    assert result["real_ai_calls"] == 1
    assert result["audit"] == {"ok": True, "save_load_equivalent": True}
    restored = load_world(tmp_path / "fulfilled.mws")
    assert any(event.event_type == "campaign_supply_dispatched" for event in restored.events)
    assert any(event.event_type == "campaign_provisions_loaded" for event in restored.events)


def test_supply_probe_no_action_leads_to_lapse_without_freight(monkeypatch, tmp_path):
    _provider(monkeypatch, ai_decider.NO_ACTION)
    result = asyncio.run(run(output=tmp_path / "lapsed.mws"))

    assert result["no_action"] is True
    assert result["notice_state"] == "lapsed"
    assert result["freight_count"] == 0
    assert result["real_ai_calls"] == 1
    restored = load_world(tmp_path / "lapsed.mws")
    assert any(event.event_type == "campaign_supply_lapsed" for event in restored.events)
    assert not any(event.event_type == "freight_opened" for event in restored.events)
