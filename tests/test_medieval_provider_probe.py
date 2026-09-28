"""Operational boundary checks for the real-provider probe."""

import importlib.util
from pathlib import Path

import pytest

from src.run.medieval_world import create_medieval_world


def _probe_module():
    path = Path(__file__).parents[1] / "tools" / "medieval_provider_probe.py"
    spec = importlib.util.spec_from_file_location("medieval_provider_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_real_provider_probe_fails_before_world_creation_when_unconfigured(monkeypatch):
    probe = _probe_module()
    monkeypatch.setattr(probe.ai_decider, "provider_available", lambda: False)

    with pytest.raises(RuntimeError, match="real provider is not configured"):
        await probe.run(73)


@pytest.mark.asyncio
async def test_real_provider_probe_rejects_non_positive_budget_without_provider_call(monkeypatch):
    probe = _probe_module()
    monkeypatch.setattr(probe.ai_decider, "provider_available", lambda: True)

    with pytest.raises(ValueError, match="calls_per_step"):
        await probe.run(73, calls_per_step=0)


def test_real_provider_probe_uses_full_monthly_menu_with_competing_economic_choices():
    probe = _probe_module()
    world = create_medieval_world(73, bootstrap_household_income=True)
    actor, by_id, target_options = probe._actor_and_options(world)

    situation, choices = probe._provider_request(world, actor, by_id)

    assert {choice["id"] for choice in choices} == set(by_id)
    assert situation["production_priority"]["payroll_competition"]
    assert situation["production"]["site_construction_opportunities"]
    assert len(target_options) >= 2
    assert all(choice["label"] != choice["id"] for choice in choices)
    assert all("Selecionar " not in choice["label"] for choice in choices)
    assert situation["actor"] == actor.to_dict()
