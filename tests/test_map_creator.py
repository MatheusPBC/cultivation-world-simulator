import json

import pytest


pytest.importorskip("flask")

from tools.map_creator import main as map_creator


def _write_map(root, map_id, *, width=84, height=60, region_id=101):
    preset_dir = root / map_id
    preset_dir.mkdir(parents=True)
    terrain_rows = [["forest" for _ in range(width)] for _ in range(height)]
    terrain_rows[0][0] = "water"
    payload = {
        "schema_version": 6,
        "id": map_id,
        "version": 7,
        "width": width,
        "height": height,
        "region_rows": [[region_id for _ in range(width)] for _ in range(height)],
        "geography": {
            "terrain_rows": terrain_rows,
            "elevation_rows": [[17 for _ in range(width)] for _ in range(height)],
            "water_bodies": [{
                "id": "river-test",
                "kind": "river",
                "cell_refs": [[0, 0]],
                "navigable": True,
                "flow_direction": [1, 0],
            }],
        },
        "landmarks": {"301": {"x": 1, "y": 2, "asset": "city_301"}},
        "region_overrides": {"101": {"name_id": "region.101.name"}},
        "routes": [],
        "infrastructure_sites": [],
    }
    (preset_dir / "map.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def test_map_creator_save_payload_preserves_existing_size_and_metadata(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    _write_map(maps_dir, "island_seas", width=84, height=60)
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    payload = map_creator.build_map_payload(
        {
            "mapId": "island_seas",
            "grid": [
                {"x": 0, "y": 0, "r": 102},
                {"x": 83, "y": 59, "r": 105},
                {"x": 84, "y": 60, "r": 999},
            ],
            "terrainRows": [["water" if x == 0 and y == 0 else "forest" for x in range(84)] for y in range(60)],
        }
    )

    assert payload["id"] == "island_seas"
    assert payload["version"] == 7
    assert payload["width"] == 84
    assert payload["height"] == 60
    assert len(payload["region_rows"]) == 60
    assert all(len(row) == 84 for row in payload["region_rows"])
    assert payload["region_rows"][0][0] == 102
    assert payload["region_rows"][59][83] == 105
    assert payload["landmarks"] == {"301": {"x": 1, "y": 2, "asset": "city_301"}}
    assert payload["region_overrides"] == {"101": {"name_id": "region.101.name"}}
    assert payload["schema_version"] == 6
    assert payload["geography"]["terrain_rows"][0][0] == "water"
    assert payload["geography"]["terrain_rows"][0][1] == "forest"
    assert payload["geography"]["elevation_rows"][0][0] == 17
    assert payload["geography"]["water_bodies"][0]["id"] == "river-test"
    assert payload["infrastructure_sites"] == []


def test_map_creator_preserves_and_projects_infrastructure_sites(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    payload = _write_map(maps_dir, "classic", width=2, height=2)
    payload["infrastructure_sites"] = [{
        "id": "classic-observatory-test",
        "kind": "weather_observatory",
        "name": "Test Observatory",
        "cell_refs": [[1, 1]],
        "region_ids": [101],
        "route_ids": [],
        "water_body_ids": [],
        "capability_ids": ["food_production"],
        "owner_ref": None,
        "maintainer_ref": None,
        "integrity": 0.91,
        "enabled": True,
        "last_event_id": None,
    }]
    (maps_dir / "classic" / "map.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    loaded = map_creator.load_map_data("classic")
    assert loaded["infrastructureSites"] == payload["infrastructure_sites"]

    saved = map_creator.build_map_payload(
        {"mapId": "classic", "grid": [{"x": x, "y": y, "r": 101} for y in range(2) for x in range(2)]}
    )
    assert saved["infrastructure_sites"] == payload["infrastructure_sites"]


def test_map_creator_persists_explicit_route_site_relation(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    payload = _write_map(maps_dir, "classic", width=2, height=2)
    payload["region_rows"] = [[101, 102], [101, 102]]
    payload["routes"] = [{
        "id": "route:101-102",
        "endpoint_region_ids": [101, 102],
        "mode": "road",
        "capacity": 80,
        "quality": 0.75,
        "enabled": True,
        "allowed_resource_ids": [],
    }]
    (maps_dir / "classic" / "map.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    site = {
        "id": "bridge:101-102",
        "kind": "bridge",
        "name": "Ponte do Vale",
        "cell_refs": [[0, 1]],
        "region_ids": [101, 102],
        "route_ids": ["route:101-102"],
        "water_body_ids": [],
        "capability_ids": [],
        "owner_ref": None,
        "maintainer_ref": None,
        "integrity": 1.0,
        "enabled": True,
        "last_event_id": None,
    }
    saved = map_creator.build_map_payload({
        "mapId": "classic",
        "grid": [
            {"x": x, "y": y, "r": 101 if x == 0 else 102}
            for y in range(2)
            for x in range(2)
        ],
        "infrastructureSites": [site],
    })

    assert saved["routes"] == payload["routes"]
    assert saved["infrastructure_sites"] == [site]


def test_map_creator_accepts_explicit_route_authoring(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    _write_map(maps_dir, "classic", width=2, height=2)
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))
    authored_route = {
        "id": "route:new",
        "endpoint_region_ids": [101, 102],
        "mode": "ferry",
        "capacity": 35,
        "quality": 0.6,
        "enabled": True,
        "allowed_resource_ids": ["medicine"],
    }

    saved = map_creator.build_map_payload({
        "mapId": "classic",
        "grid": [
            {"x": x, "y": y, "r": 101 if x == 0 else 102}
            for y in range(2)
            for x in range(2)
        ],
        "routes": [authored_route],
        "infrastructureSites": [],
    })

    assert saved["routes"] == [{**authored_route, "capacity": 35.0, "quality": 0.6}]


def test_map_creator_rejects_removing_a_route_still_used_by_a_site(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    payload = _write_map(maps_dir, "classic", width=2, height=2)
    payload["region_rows"] = [[101, 102], [101, 102]]
    payload["routes"] = [{
        "id": "route:used",
        "endpoint_region_ids": [101, 102],
        "mode": "road",
        "capacity": 20,
        "quality": 1,
        "enabled": True,
        "allowed_resource_ids": [],
    }]
    payload["infrastructure_sites"] = [{
        "id": "bridge:used",
        "kind": "bridge",
        "name": "Ponte",
        "cell_refs": [[0, 1]],
        "region_ids": [101, 102],
        "route_ids": ["route:used"],
        "water_body_ids": [],
        "capability_ids": [],
        "owner_ref": None,
        "maintainer_ref": None,
        "integrity": 1.0,
        "enabled": True,
        "last_event_id": None,
    }]
    (maps_dir / "classic" / "map.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    with pytest.raises(ValueError, match="unknown route"):
        map_creator.build_map_payload({
            "mapId": "classic",
            "grid": [
                {"x": x, "y": y, "r": 101 if x == 0 else 102}
                for y in range(2)
                for x in range(2)
            ],
            "routes": [],
        })


def test_map_creator_rejects_route_with_unknown_endpoint_region(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    payload = _write_map(maps_dir, "classic", width=2, height=2)
    payload["routes"] = [{
        "id": "route:bad",
        "endpoint_region_ids": [101, 999],
        "mode": "road",
        "capacity": 80,
        "quality": 0.75,
        "enabled": True,
        "allowed_resource_ids": [],
    }]
    (maps_dir / "classic" / "map.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    with pytest.raises(ValueError, match="unknown regions"):
        map_creator.load_map_data("classic")


def test_map_creator_save_payload_uses_request_size_for_known_map(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    _write_map(maps_dir, "classic", width=84, height=60)
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    payload = map_creator.build_map_payload(
        {
            "mapId": "classic",
            "width": 12,
            "height": 8,
            "grid": [{"x": 11, "y": 7, "r": 118}],
            "landmarks": {},
            "regionOverrides": {},
            "terrainRows": [["plain" for _ in range(12)] for _ in range(8)],
        }
    )

    assert payload["width"] == 12
    assert payload["height"] == 8
    assert len(payload["region_rows"]) == 8
    assert all(len(row) == 12 for row in payload["region_rows"])
    assert payload["region_rows"][7][11] == 118


def test_map_creator_rejects_unknown_map_without_explicit_create(tmp_path, monkeypatch):
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(tmp_path / "maps"))

    with pytest.raises(ValueError, match="Unknown map preset"):
        map_creator.build_map_payload({"mapId": "new_world", "grid": []})


def test_map_creator_rejects_schema_four_and_obsolete_wilderness(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    preset_dir = maps_dir / "classic"
    preset_dir.mkdir(parents=True)
    (preset_dir / "map.json").write_text(json.dumps({"schema_version": 4}), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    with pytest.raises(ValueError, match="schema version 6"):
        map_creator.build_map_payload({"mapId": "classic", "grid": []})

    with pytest.raises(ValueError, match="obsolete"):
        map_creator.build_map_payload({"mapId": "new_world", "allowCreate": True, "wildernessTile": "plain"})


def test_map_creator_loads_requested_map_id(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    _write_map(maps_dir, "classic", width=84, height=60, region_id=101)
    _write_map(maps_dir, "mountain_frontier", width=10, height=6, region_id=107)
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))
    loaded = map_creator.load_map_data("mountain_frontier")

    assert loaded["mapId"] == "mountain_frontier"
    assert loaded["width"] == 10
    assert loaded["height"] == 6
    assert loaded["cells"]["0,0"] == {"t": "water", "r": 107}
    assert loaded["terrainRows"][0][0] == "water"
    assert loaded["elevationRows"][0][0] == 17
    assert loaded["waterBodies"][0]["id"] == "river-test"


def test_map_creator_rejects_path_like_map_id():
    with pytest.raises(ValueError, match="Invalid map id"):
        map_creator.normalize_map_id("../classic")


def test_map_creator_rejects_invalid_region_and_river_direction(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    _write_map(maps_dir, "classic", width=2, height=2)
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    with pytest.raises(ValueError, match="Region IDs must be positive"):
        map_creator.build_map_payload(
            {"mapId": "classic", "grid": [{"x": 0, "y": 0, "r": 0}]}
        )

    source = json.loads((maps_dir / "classic" / "map.json").read_text(encoding="utf-8"))
    source["geography"]["water_bodies"][0]["flow_direction"] = [2, 0]
    (maps_dir / "classic" / "map.json").write_text(
        json.dumps(source), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="cardinal or diagonal"):
        map_creator.build_map_payload({"mapId": "classic", "grid": []})


def test_map_creator_rejects_infrastructure_site_with_unknown_reference(tmp_path, monkeypatch):
    maps_dir = tmp_path / "maps"
    payload = _write_map(maps_dir, "classic", width=2, height=2)
    payload["infrastructure_sites"] = [{
        "id": "bad-site",
        "kind": "farm",
        "name": "Bad Site",
        "cell_refs": [[1, 1]],
        "region_ids": [101],
        "route_ids": ["missing-route"],
        "water_body_ids": [],
        "capability_ids": ["food_production"],
        "owner_ref": None,
        "maintainer_ref": None,
        "integrity": 1.0,
        "enabled": True,
        "last_event_id": None,
    }]
    (maps_dir / "classic" / "map.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(map_creator, "MAPS_DIR", str(maps_dir))

    with pytest.raises(ValueError, match="unknown route"):
        map_creator.build_map_payload({"mapId": "classic", "grid": []})
