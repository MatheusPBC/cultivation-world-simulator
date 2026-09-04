import json

import pytest

from src.sim.load.load_game import check_save_compatibility, load_game


@pytest.mark.parametrize("schema_version", [None, 0, "1"])
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
