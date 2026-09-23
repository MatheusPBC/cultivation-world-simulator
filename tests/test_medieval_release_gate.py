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


def test_release_gate_rejects_invalid_checkpoint_interval(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["medieval_release_gate", "--output-dir",
                                      str(tmp_path), "--checkpoint-days", "15"])
    with pytest.raises(SystemExit) as exc:
        medieval_release_gate.main()
    assert exc.value.code == 2
