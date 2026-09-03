import copy

import pytest

from src.run.load_map import load_cultivation_world_map
from src.run.map_snapshot import load_map_from_snapshot, serialize_map_snapshot


def test_snapshot_round_trip_preserves_physical_geography_and_spatial_queries() -> None:
    original = load_cultivation_world_map("mountain_frontier")
    snapshot = serialize_map_snapshot(original)
    restored = load_map_from_snapshot(snapshot)

    assert restored.geography is not None
    assert restored.map_source["schema_version"] == 6
    assert restored.map_source["geography"] == snapshot["geography"]
    assert restored.get_terrain(0, 0) == original.get_terrain(0, 0)
    assert restored.get_elevation(10, 10) == original.get_elevation(10, 10)
    assert restored.get_water_bodies_at(1, 0) == original.get_water_bodies_at(1, 0)
    assert restored.get_water_bodies_touching_region(106) == original.get_water_bodies_touching_region(106)
    assert restored.get_neighboring_region_ids(106) == original.get_neighboring_region_ids(106)
    assert restored.get_river_relation(106, 107) == original.get_river_relation(106, 107)


def test_snapshot_does_not_alias_geography_mutable_rows() -> None:
    original = load_cultivation_world_map("classic")
    restored = load_map_from_snapshot(serialize_map_snapshot(original))

    restored.geography.elevation_rows[0][0] += 1

    assert restored.get_elevation(0, 0) != original.get_elevation(0, 0)


def test_snapshot_rejects_missing_or_malformed_geography() -> None:
    snapshot = serialize_map_snapshot(load_cultivation_world_map("classic"))

    missing = copy.deepcopy(snapshot)
    del missing["geography"]
    with pytest.raises(ValueError, match="geography is required"):
        load_map_from_snapshot(missing)

    malformed = copy.deepcopy(snapshot)
    malformed["geography"]["terrain_rows"] = []
    with pytest.raises(ValueError, match="Invalid geography.terrain_rows height"):
        load_map_from_snapshot(malformed)


def test_snapshot_rejects_invalid_region_ids_and_ungrounded_water_region() -> None:
    snapshot = serialize_map_snapshot(load_cultivation_world_map("classic"))

    invalid_region = copy.deepcopy(snapshot)
    invalid_region["region_rows"][0][0] = 0
    with pytest.raises(ValueError, match="positive region IDs or -1"):
        load_map_from_snapshot(invalid_region)

    invalid_water = copy.deepcopy(snapshot)
    invalid_water["geography"]["water_bodies"][0]["region_id"] = 9999
    with pytest.raises(ValueError, match="unknown region id"):
        load_map_from_snapshot(invalid_water)
