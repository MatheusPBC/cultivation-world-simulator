"""Focused contract tests for the bounded material campaign probe."""

import asyncio
import json

from src.sim.medieval import ai_decider
from src.sim.medieval.persistence import load_world
from tools.medieval_campaign_material_probe import run


def _choose_first(monkeypatch):
    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)


def test_material_probe_adopts_then_raises_and_round_trips(monkeypatch, tmp_path):
    _choose_first(monkeypatch)
    result = asyncio.run(run(output=tmp_path / "campaign.mws"))

    assert result["adopted"] is True
    assert result["advanced_day"] is True
    assert result["material_changed"] is True
    assert result["force_decision_count"] == 1
    assert result["detachment_count"] == 1
    assert result["real_ai_calls"] == 2
    assert result["audit"]["ok"] is True
    restored = load_world(tmp_path / "campaign.mws")
    adoption = next(event for event in restored.events
                    if event.event_type == "strategy_defense_adopted")
    force_decision = next(event for event in restored.events
                          if event.event_type == "strategy_defense_force_decided")
    material = next(event for event in restored.events
                    if event.event_type == "detachment_raised")
    assert adoption.causal_links
    assert force_decision.id in {link.cause_event_id for link in material.causal_links}


def test_material_probe_no_action_does_not_create_force(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def decline(prompt, *args, **kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", decline)
    result = asyncio.run(run(output=tmp_path / "declined.mws"))

    assert result["no_action"] is True
    assert result["advanced_day"] is False
    assert result["force_decision_count"] == 0
    assert result["detachment_count"] == 0
    assert result["real_ai_calls"] == 1
    assert any(event.event_type == ai_decider.DECLINED_EVENT
               for event in load_world(tmp_path / "declined.mws").events)
