"""The local provider probe preserves its source save and causal receipt."""

import json

import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.persistence import save_world
from tools.medieval_provider_civil_probe import probe


@pytest.mark.asyncio
async def test_civil_probe_uses_current_menu_without_persisting(monkeypatch, tmp_path):
    save_path = tmp_path / "probe-source.mws"
    save_world(create_medieval_world(73), save_path)
    original = save_path.read_bytes()

    async def decline(_prompt):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", decline)
    result = await probe(save_path, "auren")

    assert result["offered_count"] > 0
    assert result["menu_scope"] == "full_monthly_institutional_menu"
    assert result["selected_id"] == ai_decider.NO_ACTION
    assert result["receipt_type"] == ai_decider.DECLINED_EVENT
    assert result["receipt_has_deltas"] is False
    assert result["selection_valid"] is True
    assert result["material_event_count"] == 0
    assert result["state_delta_count"] == 0
    assert result["persisted"] is False
    assert save_path.read_bytes() == original


@pytest.mark.asyncio
async def test_civil_probe_executes_only_an_offered_id_on_its_fork(monkeypatch, tmp_path):
    save_path = tmp_path / "probe-source.mws"
    save_world(create_medieval_world(73), save_path)
    original = save_path.read_bytes()

    async def select_first(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", select_first)
    result = await probe(save_path, "auren")

    assert result["selected_id"] != ai_decider.NO_ACTION
    assert result["receipt_type"] == ai_decider.INTERPRETED_EVENT
    assert result["receipt_has_deltas"] is False
    assert result["selection_valid"] is True
    assert result["persisted"] is False
    assert save_path.read_bytes() == original


@pytest.mark.asyncio
async def test_civil_probe_rejects_unknown_id_without_touching_save(monkeypatch, tmp_path):
    save_path = tmp_path / "probe-source.mws"
    save_world(create_medieval_world(73), save_path)
    original = save_path.read_bytes()

    async def invent_option(_prompt):
        return {"selected_id": "invented-affordance"}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", invent_option)
    with pytest.raises(ProviderDecisionRequired, match="unknown"):
        await probe(save_path, "auren")
    assert save_path.read_bytes() == original
