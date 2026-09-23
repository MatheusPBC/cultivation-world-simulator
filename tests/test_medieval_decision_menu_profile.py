import json
import os
import subprocess
import sys

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.persistence import save_world
from tools.medieval_decision_menu_profile import main


def test_profile_cli_reports_checkpoint_and_monthly_menu_measurements(tmp_path, capsys):
    checkpoint = tmp_path / "small-world.mws"
    save_world(create_medieval_world(73, character_count=1), checkpoint)

    main([str(checkpoint), "--profile-limit", "3"])

    report = json.loads(capsys.readouterr().out)
    assert report["checkpoint"] == str(checkpoint.resolve())
    assert report["event_count"] >= 0
    assert report["measurements"]["snapshot_event_count"] == report["event_count"]
    assert report["measurements"]["monthly_decision_menu_seconds"] >= 0
    assert report["measurements"]["actor_count"] >= 0
    assert report["measurements"]["option_count"] >= 0
    assert len(report["menu_profile_top_cumulative"]) <= 3
    assert all({"function", "calls", "cumulative_seconds"} <= row.keys()
               for row in report["menu_profile_top_cumulative"])


def test_profile_script_stdout_is_json(tmp_path):
    checkpoint = tmp_path / "small-world.mws"
    save_world(create_medieval_world(73, character_count=1), checkpoint)
    script = os.path.join(os.path.dirname(__file__), "..", "tools", "medieval_decision_menu_profile.py")

    result = subprocess.run(
        [sys.executable, script, str(checkpoint), "--profile-limit", "1"],
        capture_output=True,
        text=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["checkpoint"] == str(checkpoint.resolve())
