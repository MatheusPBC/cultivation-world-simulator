from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.classes.environment.tile import TileType
from src.classes.mechanical_language import EntityRef
from src.run.map_source import MAP_SOURCE_SCHEMA_VERSION, map_source_to_dict, read_map_source
from src.run.load_map import build_map_from_rows
from src.run.map_snapshot import load_map_from_snapshot, serialize_map_snapshot


def _map_with_regions() -> Map:
    game_map = Map(4, 2)
    for y in range(2):
        for x in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)

    game_map.regions = {
        101: SimpleNamespace(id=101, cors=[(0, 0), (0, 1)]),
        102: SimpleNamespace(id=102, cors=[(1, 0), (1, 1)]),
    }
    game_map.region_cors = {
        101: [(0, 0), (0, 1)],
        102: [(1, 0), (1, 1)],
    }
    game_map.set_routes(
        [
            Route(
                id="route:bridge",
                endpoint_region_ids=(101, 102),
                mode="land",
                capacity=100,
                quality=1.0,
                enabled=True,
            )
        ]
    )
    game_map.set_geography(
        GeographyLayer(
            width=4,
            height=2,
            terrain_rows=[
                [TileType.PLAIN, TileType.PLAIN, TileType.WATER, TileType.PLAIN],
                [TileType.PLAIN, TileType.PLAIN, TileType.WATER, TileType.PLAIN],
            ],
            elevation_rows=[[0.0] * 4 for _ in range(2)],
            water_bodies=[
                WaterBody(
                    id="water:river",
                    kind="river",
                    cell_refs=((2, 0), (2, 1)),
                    navigable=True,
                    flow_direction=(0, 1),
                )
            ],
        )
    )
    return game_map


def _site() -> InfrastructureSite:
    return InfrastructureSite(
        id="site:bridge",
        kind="bridge",
        name="Ponte de Jade",
        cell_refs=((1, 0),),
        region_ids=(101, 102),
        route_ids=("route:bridge",),
        water_body_ids=("water:river",),
        capability_ids=("land_transport",),
        owner_ref=EntityRef("sect", "1"),
        maintainer_ref=EntityRef("city", "101"),
        integrity=0.8,
        enabled=True,
    )


def test_infrastructure_site_round_trip_and_derived_status() -> None:
    site = _site()

    assert site.status == "impaired"
    assert InfrastructureSite.from_dict(site.to_dict()) == site
    assert json.loads(json.dumps(site.to_dict())) == site.to_dict()

    site.update_runtime(integrity=0.0)
    assert site.status == "destroyed"
    site.update_runtime(integrity=1.0, enabled=False)
    assert site.status == "impaired"

    with pytest.raises(ValueError, match="unknown fields"):
        InfrastructureSite.from_dict({**site.to_dict(), "narrative_effect": "prosperity"})


def test_map_validates_spatial_references_and_does_not_queue_initial_updates() -> None:
    game_map = _map_with_regions()

    game_map.set_infrastructure_sites([_site()])

    assert game_map.infrastructure_sites["site:bridge"] == _site()
    assert game_map.get_infrastructure_site_updates() == []


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda site: InfrastructureSite.from_dict({**site.to_dict(), "cell_refs": [[3, 3]]}), "outside map"),
        (lambda site: InfrastructureSite.from_dict({**site.to_dict(), "region_ids": [999]}), "unknown region"),
        (lambda site: InfrastructureSite.from_dict({**site.to_dict(), "route_ids": ["missing"]}), "unknown route"),
        (lambda site: InfrastructureSite.from_dict({**site.to_dict(), "water_body_ids": ["missing"]}), "unknown water body"),
        (lambda site: InfrastructureSite.from_dict({**site.to_dict(), "cell_refs": [[0, 0]]}), "does not touch its cells"),
    ],
)
def test_map_rejects_invalid_infrastructure_references(mutator, message) -> None:
    game_map = _map_with_regions()
    invalid_site = mutator(_site())

    with pytest.raises(ValueError, match=message):
        game_map.set_infrastructure_sites([invalid_site])


def test_map_rejects_route_when_only_one_endpoint_belongs_to_site_regions() -> None:
    game_map = _map_with_regions()
    game_map.set_routes([
        Route(
            id="route:mismatch",
            endpoint_region_ids=(101, 999),
            mode="land",
            capacity=10,
            quality=1,
            enabled=True,
        )
    ])
    site = InfrastructureSite.from_dict({
        **_site().to_dict(),
        "route_ids": ["route:mismatch"],
        "water_body_ids": [],
    })

    with pytest.raises(ValueError, match="not connected to its regions"):
        game_map.set_infrastructure_sites([site])


def test_runtime_update_enqueues_canonical_upsert_and_pop_resets_queue() -> None:
    game_map = _map_with_regions()
    game_map.set_infrastructure_sites([_site()])

    changed = game_map.update_infrastructure_site_runtime(
        "site:bridge",
        integrity=0.4,
        enabled=False,
        last_event_id="event:bridge-damaged",
    )

    assert changed is True
    site = game_map.infrastructure_sites["site:bridge"]
    assert site.integrity == 0.4
    assert site.enabled is False
    assert site.last_event_id == "event:bridge-damaged"
    assert game_map.get_infrastructure_site_updates() == [
        {"op": "upsert", "id": "site:bridge", "site": site.to_dict()}
    ]
    assert game_map.get_infrastructure_site_updates() != []
    game_map.acknowledge_infrastructure_site_updates()
    assert game_map.get_infrastructure_site_updates() == []


def test_runtime_noop_does_not_enqueue_update_and_identity_is_immutable() -> None:
    game_map = _map_with_regions()
    site = _site()
    game_map.set_infrastructure_sites([site])

    assert game_map.update_infrastructure_site_runtime("site:bridge", integrity=0.8) is False
    assert game_map.get_infrastructure_site_updates() == []

    with pytest.raises(AttributeError):
        site.kind = "mine"


def test_map_source_schema_six_requires_and_round_trips_sites(tmp_path) -> None:
    payload = {
        "schema_version": MAP_SOURCE_SCHEMA_VERSION,
        "id": "test-map",
        "version": 1,
        "width": 2,
        "height": 1,
        "region_rows": [[101, 101]],
        "geography": {
            "terrain_rows": [["plain", "plain"]],
            "elevation_rows": [[0, 0]],
            "water_bodies": [],
        },
        "landmarks": {},
        "region_overrides": {},
        "routes": [],
        "infrastructure_sites": [
            {
                "id": "site:well",
                "kind": "well",
                "name": "Poço",
                "cell_refs": [[0, 0]],
                "region_ids": [101],
                "route_ids": [],
                "water_body_ids": [],
                "capability_ids": ["water_access"],
                "owner_ref": None,
                "maintainer_ref": None,
                "integrity": 1.0,
                "enabled": True,
                "last_event_id": None,
            }
        ],
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    source = read_map_source(path)

    assert source.infrastructure_sites[0].id == "site:well"
    assert map_source_to_dict(source)["infrastructure_sites"] == payload["infrastructure_sites"]


def test_map_source_rejects_missing_infrastructure_sites(tmp_path) -> None:
    payload = {
        "schema_version": MAP_SOURCE_SCHEMA_VERSION,
        "id": "test-map",
        "version": 1,
        "width": 1,
        "height": 1,
        "region_rows": [[101]],
        "geography": {
            "terrain_rows": [["plain"]],
            "elevation_rows": [[0]],
            "water_bodies": [],
        },
        "landmarks": {},
        "region_overrides": {},
        "routes": [],
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="infrastructure_sites is required"):
        read_map_source(path)


def test_map_source_rejects_route_with_an_endpoint_outside_site_regions(tmp_path) -> None:
    payload = {
        "schema_version": MAP_SOURCE_SCHEMA_VERSION,
        "id": "invalid-route-site",
        "version": 1,
        "width": 3,
        "height": 1,
        "region_rows": [[101, 102, 103]],
        "geography": {
            "terrain_rows": [["plain", "plain", "plain"]],
            "elevation_rows": [[0, 0, 0]],
            "water_bodies": [],
        },
        "landmarks": {},
        "region_overrides": {},
        "routes": [{
            "id": "route:mismatch",
            "endpoint_region_ids": [101, 103],
            "mode": "road",
            "capacity": 10,
            "quality": 1,
            "enabled": True,
            "allowed_resource_ids": [],
        }],
        "infrastructure_sites": [{
            **_site().to_dict(),
            "cell_refs": [[0, 0]],
            "region_ids": [101, 102],
            "route_ids": ["route:mismatch"],
            "water_body_ids": [],
        }],
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="not connected to its regions"):
        read_map_source(path)


def test_map_source_rejects_water_body_far_from_site_cells(tmp_path) -> None:
    payload = {
        "schema_version": MAP_SOURCE_SCHEMA_VERSION,
        "id": "invalid-water-site",
        "version": 1,
        "width": 3,
        "height": 1,
        "region_rows": [[101, 101, 101]],
        "geography": {
            "terrain_rows": [["plain", "plain", "water"]],
            "elevation_rows": [[0, 0, 0]],
            "water_bodies": [{
                "id": "water:far",
                "kind": "lake",
                "cell_refs": [[2, 0]],
                "navigable": False,
            }],
        },
        "landmarks": {},
        "region_overrides": {},
        "routes": [],
        "infrastructure_sites": [{
            **_site().to_dict(),
            "cell_refs": [[0, 0]],
            "region_ids": [101],
            "route_ids": [],
            "water_body_ids": ["water:far"],
        }],
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="does not touch its cells"):
        read_map_source(path)


def test_snapshot_v5_persists_sites_and_routes_without_initial_updates() -> None:
    game_map = build_map_from_rows(
        [["plain", "plain"]],
        [[101, 102]],
        map_id="test-map",
    )
    game_map.set_routes(
        [
            Route(
                id="route:bridge",
                endpoint_region_ids=(101, 102),
                mode="land",
                capacity=100,
                quality=1.0,
                enabled=True,
            )
        ]
    )
    snapshot_site = InfrastructureSite(
        id="site:bridge",
        kind="bridge",
        name="Ponte de Jade",
        cell_refs=((0, 0),),
        region_ids=(101, 102),
        route_ids=("route:bridge",),
        integrity=0.4,
    )
    game_map.set_infrastructure_sites([snapshot_site])

    snapshot = serialize_map_snapshot(game_map)
    restored = load_map_from_snapshot(snapshot)

    assert snapshot["schema_version"] == 5
    assert snapshot["infrastructure_sites"] == [snapshot_site.to_dict()]
    assert restored.infrastructure_sites["site:bridge"] == snapshot_site
    assert restored.routes["route:bridge"].to_dict() == game_map.routes["route:bridge"].to_dict()
    assert restored.get_route_operational_capacity("route:bridge") == 40.0
    assert restored.get_infrastructure_site_updates() == []
