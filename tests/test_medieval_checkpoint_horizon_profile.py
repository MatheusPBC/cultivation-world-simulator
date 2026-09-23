import json

import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.persistence import save_world
from tools.medieval_checkpoint_horizon_profile import main, profile_checkpoint_horizon


@pytest.mark.asyncio
async def test_checkpoint_horizon_profile_advances_only_the_in_memory_world(tmp_path):
    checkpoint = tmp_path / "small-world.mws"
    save_world(create_medieval_world(73, character_count=1), checkpoint)
    source_bytes = checkpoint.read_bytes()

    report = await profile_checkpoint_horizon(checkpoint, days=30, profile_limit=3)

    assert report["source_checkpoint"] == str(checkpoint.resolve())
    assert report["source_save_overwritten"] is False
    assert report["source_save_unchanged"] is True
    assert report["in_memory_only"] is True
    assert report["start"] == {"day": 0, "event_count": 0}
    assert report["target"]["day"] == 30
    assert report["target"]["event_count"] >= report["start"]["event_count"]
    assert report["advanced_days"] == 30
    assert report["jumps"] >= 1
    assert report["elapsed_seconds"] >= 0
    assert len(report["profile_top_cumulative"]) <= 3
    assert checkpoint.read_bytes() == source_bytes


def test_checkpoint_horizon_profile_cli_writes_json_only(tmp_path, capsys):
    checkpoint = tmp_path / "small-world.mws"
    save_world(create_medieval_world(73, character_count=1), checkpoint)

    main([str(checkpoint), "--days", "30", "--profile-limit", "1"])

    report = json.loads(capsys.readouterr().out)
    assert report["source_checkpoint"] == str(checkpoint.resolve())
    assert report["target"]["day"] == 30
    assert len(report["profile_top_cumulative"]) <= 1
