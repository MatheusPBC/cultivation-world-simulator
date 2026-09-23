"""Focused contract tests for the bounded technology material probe."""

import asyncio
import json

import pytest

from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.persistence import load_world
import tools.medieval_technology_material_probe as probe
from tools.medieval_technology_material_probe import OWNER, _research_for_probe, run
from src.run.medieval_world import create_medieval_world


def _provider(monkeypatch, selected):
    prompts = []

    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        return {"selected_id": selected(payload) if callable(selected) else selected}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    return prompts


def test_probe_discovers_then_applies_existing_technology_and_round_trips(monkeypatch, tmp_path):
    prompts = _provider(monkeypatch, lambda payload: payload["choices"][0]["id"])
    result = asyncio.run(run(output=tmp_path / "technology.mws"))

    assert len(prompts) == 2
    # Research choice IDs are deliberately redacted in the provider prompt;
    # validate the persisted resolved ID against the canonical menu instead.
    assert result["research_selected_id"] in {item.id for item in _research_for_probe(create_medieval_world(73), OWNER)}
    assert result["application_selected_id"] in {item["id"] for item in prompts[1]["choices"]}
    assert result["knowledge_discovered"] is True
    assert result["application_stage"] == "completed"
    assert result["production_delta"]
    assert result["real_ai_calls"] == 2
    assert result["audit"]["ok"] is True
    restored = load_world(tmp_path / "technology.mws")
    assert any(event.event_type == "technology_discovered" for event in restored.events)
    assert any(event.event_type == "expansion_started" for event in restored.events)
    assert not [event for event in restored.events
                if event.event_type == ai_decider.INTERPRETED_EVENT and event.deltas]


def test_probe_research_no_action_is_safe_and_does_not_open_projects(monkeypatch, tmp_path):
    prompts = _provider(monkeypatch, ai_decider.NO_ACTION)
    result = asyncio.run(run(output=tmp_path / "declined.mws"))

    assert len(prompts) == 1
    assert result["research_no_action"] is True
    assert result["knowledge_discovered"] is False
    assert result["application_selected_id"] is None
    assert result["real_ai_calls"] == 1
    restored = load_world(tmp_path / "declined.mws")
    assert not restored.research.projects
    assert not restored.economy.expansions


def test_probe_rejects_invented_provider_id_without_opening_a_project(monkeypatch, tmp_path):
    _provider(monkeypatch, "research:invented")
    with pytest.raises(ProviderDecisionRequired, match="unknown"):
        asyncio.run(run(output=tmp_path / "stale.mws"))
    assert not (tmp_path / "stale.mws").exists()


def test_probe_fails_closed_when_selected_research_affordance_becomes_stale(monkeypatch, tmp_path):
    _provider(monkeypatch, lambda payload: payload["choices"][0]["id"])
    original = probe._research_for_probe
    calls = 0

    def stale_after_prompt(world, actor):
        nonlocal calls
        calls += 1
        # ``run`` inventories once, then the turn composes the prompt.  The
        # fresh owner revalidation must see that same choice disappear.
        return original(world, actor) if calls < 3 else ()

    monkeypatch.setattr(probe, "_research_for_probe", stale_after_prompt)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        asyncio.run(run(output=tmp_path / "stale-selected.mws"))
    assert not (tmp_path / "stale-selected.mws").exists()
