"""Operational boundary checks for the real-provider probe."""

import importlib.util
from pathlib import Path

import pytest


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
