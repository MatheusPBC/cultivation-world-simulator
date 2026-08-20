import copy

import pytest

from tools.migrate_map_snapshot_v2_to_v3 import migrate_save_data


def _save_data() -> dict:
    return {
        "world": {
            "map_snapshot": {
                "schema_version": 2,
                "preset_id": "classic",
                "region_overrides": {
                    "101": {"name": "old name", "desc": "old description"},
                },
            },
            "world_lore_snapshot": {
                "schema_version": 2,
                "regions": {"101": {"name": "Custom Lore Name", "desc": "Custom lore description"}},
            },
        }
    }


def test_migration_replaces_base_map_text_with_ids_and_preserves_world_lore():
    original = _save_data()
    original_copy = copy.deepcopy(original)

    migrated = migrate_save_data(original)

    assert original == original_copy
    assert migrated["world"]["map_snapshot"]["schema_version"] == 3
    assert migrated["world"]["map_snapshot"]["region_overrides"]["101"] == {
        "name_id": "MAP_REGION_CLASSIC_101_NAME",
        "desc_id": "MAP_REGION_CLASSIC_101_DESC",
    }
    assert migrated["world"]["world_lore_snapshot"] == original["world"]["world_lore_snapshot"]


def test_migration_rejects_unknown_custom_override_instead_of_losing_data():
    save_data = _save_data()
    save_data["world"]["map_snapshot"]["region_overrides"]["999"] = {
        "name": "Custom",
        "desc": "Must not be discarded",
    }

    with pytest.raises(ValueError, match="unknown override regions: 999"):
        migrate_save_data(save_data)


def test_migration_can_refresh_only_a_non_customized_locale_snapshot():
    migrated = migrate_save_data(_save_data(), refresh_unmodified_lore=True)

    assert migrated["world"]["world_lore_snapshot"] == {}

    customized = _save_data()
    customized["world"]["world_lore_snapshot"]["lore_text"] = "A custom cosmology"
    with pytest.raises(ValueError, match="customized world_lore_snapshot"):
        migrate_save_data(customized, refresh_unmodified_lore=True)
