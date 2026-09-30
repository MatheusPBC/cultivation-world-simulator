from pathlib import Path

import pytest

from tools import medieval_provider_corpus_probe as corpus


def _sources(tmp_path: Path) -> tuple[Path, ...]:
    paths = tuple(tmp_path / f"world-{index}.mws" for index in range(6))
    for index, path in enumerate(paths):
        path.write_bytes(f"synthetic-{index}".encode())
    return paths


@pytest.mark.asyncio
async def test_corpus_without_explicit_egress_only_previews(monkeypatch, tmp_path):
    async def preview(*args):
        return {"consultation_count": 10, "real_provider_calls": 0}

    def forbidden():
        raise AssertionError("provider availability must not be queried in preview mode")

    monkeypatch.setattr(corpus, "preview", preview)
    monkeypatch.setattr(corpus.ai_decider, "provider_available", forbidden)
    result = await corpus.run(*_sources(tmp_path), allow_provider_egress=False)
    assert result == {"consultation_count": 10, "real_provider_calls": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("route_calls, expected_complete", [(2, True), (11, False)])
async def test_corpus_tracks_and_caps_provider_calls(monkeypatch, tmp_path, route_calls, expected_complete):
    paths = _sources(tmp_path)
    actual_calls = []

    async def preview(*args):
        return {"consultation_count": 10}

    async def fake_client(prompt):
        actual_calls.append(prompt)
        return {"selected_id": "NO_ACTION"}

    async def route_probe(path):
        for _ in range(route_calls):
            await corpus.llm_client.call_llm_json("route")
        return {"calls": [{}] * route_calls}

    async def creature_probe(path):
        await corpus.llm_client.call_llm_json("creature")
        return {}

    async def civil_probe(path, polity_id):
        await corpus.llm_client.call_llm_json(f"civil:{polity_id}")
        return {}

    monkeypatch.setattr(corpus, "preview", preview)
    monkeypatch.setattr(corpus, "_civil", lambda *args, **kwargs: {})
    monkeypatch.setattr(corpus.ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr(corpus.llm_client, "call_llm_json", fake_client)
    monkeypatch.setattr(corpus, "route_probe", route_probe)
    monkeypatch.setattr(corpus, "_creature_probe", creature_probe)
    monkeypatch.setattr(corpus, "civil_probe", civil_probe)

    result = await corpus.run(*paths, allow_provider_egress=True)
    assert result["complete"] is expected_complete
    assert result["consultations"] == 10
    assert result["source_saves_unchanged"] is True
    assert len(actual_calls) == 10
    if not expected_complete:
        assert result["failed_case"] == "route_campaign"
        assert result["failure_type"] == "ValueError"


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_egress", [False, True])
async def test_completion_probe_selected_cases_have_no_hidden_retries(monkeypatch, tmp_path, allow_egress):
    from tools import medieval_completion_provider_probe as completion
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.persistence import save_world
    from src.config.settings_service import get_settings_service

    source = tmp_path / "completion-source.mws"
    save_world(create_medieval_world(73, bootstrap_household_income=True), source)
    original = source.read_bytes()
    original_profile = get_settings_service().get_llm_runtime_config()
    calls = []

    async def fake_client(prompt, *args, **kwargs):
        calls.append(kwargs)
        assert kwargs["max_retries"] == 0
        return {"selected_id": "NO_ACTION"}

    monkeypatch.setattr(completion.client, "call_llm_json", fake_client)
    cases = ("elemental", "evocation", "composed")
    result = await completion.run(source, allow_provider_egress=allow_egress, case_names=cases)
    assert result["complete"]
    assert tuple(item["case"] for item in result["cases"]) == cases
    assert len(calls) == (3 if allow_egress else 0)
    assert result["real_attempts"] == len(calls)
    assert result["source_unchanged"] and source.read_bytes() == original
    assert get_settings_service().get_llm_runtime_config() == original_profile
    assert all(not item["receipt_has_deltas"] for item in result["cases"])
