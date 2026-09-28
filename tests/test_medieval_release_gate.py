import pytest

from tools import medieval_release_gate


@pytest.mark.asyncio
async def test_release_gate_audits_natural_checkpoint_artifacts(tmp_path):
    report = await medieval_release_gate.run_gate(
        (73,), 60, tmp_path, pressured=False, checkpoint_days=30)

    assert report["ok"] is True
    natural = report["natural"][0]
    assert len(natural["checkpoint_audits"]) == 2
    assert all(item["ok"] for item in natural["checkpoint_audits"])
    assert all(item["conservation"] and item["save_load_equivalent"]
               for item in natural["result"]["checkpoints"])
    months = natural["result"]["monthly_advance_seconds"]
    assert len(months) == 2 and all(value > 0 for value in months)
    assert natural["result"]["monthly_p95_seconds"] == max(months)


def test_release_gate_rejects_invalid_checkpoint_interval(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["medieval_release_gate", "--output-dir",
                                      str(tmp_path), "--checkpoint-days", "15"])
    with pytest.raises(SystemExit) as exc:
        medieval_release_gate.main()
    assert exc.value.code == 2


def test_final_v1_budget_rejects_a_slow_month_and_incomplete_samples():
    result = {
        "elapsed_s": 2400, "memory_high_water_bytes": 2 * 1024**3,
        "save_bytes": 200 * 1024**2, "save_elapsed_s": 20,
        "load_elapsed_s": 18, "monthly_p95_seconds": 30,
        "monthly_advance_seconds": [20.0] * 120,
    }
    why = {"queries": 20, "p95_s": 0.5, "links_verified": True}
    assert medieval_release_gate._v1_budget_result(result, why)["ok"]

    why["links_verified"] = False
    assert medieval_release_gate._v1_budget_result(result, why)["checks"]["why_links"] is False
    why["links_verified"] = True

    result["monthly_p95_seconds"] = 36
    result["monthly_advance_seconds"] = [20.0] * 119
    checks = medieval_release_gate._v1_budget_result(result, why)["checks"]
    assert checks["monthly_p95_s"] is False
    assert checks["monthly_samples"] is False


@pytest.mark.asyncio
async def test_final_v1_requires_intermediate_checkpoints_before_running(tmp_path):
    with pytest.raises(ValueError, match="annual-or-finer checkpoints"):
        await medieval_release_gate.run_gate(
            (73, 101, 137), 3600, tmp_path, pressured=False, final_v1=True)
    assert not (tmp_path / "natural-73.mws").exists()
