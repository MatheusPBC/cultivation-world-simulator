import json

import pytest

from src.sim.load.load_game import check_save_compatibility, load_game
from src.sim.save.sections.base import SAVE_SCHEMA_VERSION


# Version 3 serialized regional flood windows without their per-month drainage
# evidence, and version 4 predates the economy's labour dependence and work
# stoppage; neither body loads, so both are rejected at the version gate.
@pytest.mark.parametrize("schema_version", [None, 0, 1, 2, "2", 3, "3", 4, "4"])
def test_old_or_invalid_save_schema_is_rejected_without_mutating_file(
    tmp_path, schema_version
):
    meta = {} if schema_version is None else {"schema_version": schema_version}
    save_path = tmp_path / "old-save.json"
    original = json.dumps({"meta": meta, "world": {}})
    save_path.write_text(original, encoding="utf-8")

    compatible, reason = check_save_compatibility(save_path)
    assert compatible is False
    assert "Unsupported save schema version" in reason
    with pytest.raises(ValueError, match="Unsupported save schema version"):
        load_game(save_path)
    assert save_path.read_text(encoding="utf-8") == original


def test_current_schema_without_required_events_sidecar_is_rejected(tmp_path):
    save_path = tmp_path / "missing-sidecar.json"
    original = json.dumps(
        {
            "meta": {
                "schema_version": SAVE_SCHEMA_VERSION,
                "events_db": "missing-sidecar_events.deadbeef.db",
                "event_count": 0,
            }
        }
    )
    save_path.write_text(original, encoding="utf-8")

    compatible, reason = check_save_compatibility(save_path)
    assert compatible is False
    assert "events database does not exist" in reason
    with pytest.raises(FileNotFoundError, match="events database does not exist"):
        load_game(save_path)
    assert save_path.read_text(encoding="utf-8") == original
