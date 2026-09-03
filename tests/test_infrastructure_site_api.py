from types import SimpleNamespace

import pytest

from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.server.services.game_queries import get_detail, get_world_map


def _site() -> InfrastructureSite:
    return InfrastructureSite(
        id="mine:black-iron",
        kind="mine",
        name="Mina de Ferro Negro",
        cell_refs=((2, 1),),
        region_ids=(301,),
        route_ids=(),
        water_body_ids=(),
        capability_ids=("iron_extraction",),
        integrity=0.7,
        enabled=True,
        last_event_id="damage:event",
    )


def _runtime_with_site():
    game_map = Map(4, 3)
    game_map.infrastructure_sites = {_site().id: _site()}
    world = SimpleNamespace(
        map=game_map,
        month_stamp=0,
        poi_manager=None,
    )
    return {"world": world}, world


def test_world_map_exposes_canonical_infrastructure_site_projection():
    runtime, _world = _runtime_with_site()

    payload = get_world_map(runtime, sects_by_id={}, render_config={})

    assert payload["infrastructure_sites"] == [
        {
            "id": "mine:black-iron",
            "kind": "mine",
            "name": "Mina de Ferro Negro",
            "cell_refs": [[2, 1]],
            "region_ids": [301],
            "route_ids": [],
            "water_body_ids": [],
            "capability_ids": ["iron_extraction"],
            "owner_ref": None,
            "maintainer_ref": None,
            "integrity": 0.7,
            "enabled": True,
            "last_event_id": "damage:event",
            "status": "impaired",
            "x": 2,
            "y": 1,
            "clickable": True,
        }
    ]


def test_world_map_projects_route_capacity_from_explicit_site_dependency():
    game_map = Map(4, 3)
    site = InfrastructureSite(
        id="bridge:black-iron",
        kind="bridge",
        name="Ponte de Ferro Negro",
        cell_refs=((2, 1),),
        region_ids=(301, 302),
        route_ids=("route:black-iron",),
        water_body_ids=(),
        capability_ids=("land_transport",),
        integrity=0.5,
        enabled=True,
        last_event_id="damage:event",
    )
    game_map.routes = {
        "route:black-iron": Route(
            id="route:black-iron",
            endpoint_region_ids=(301, 302),
            mode="road",
            capacity=100,
            quality=0.8,
            enabled=True,
        )
    }
    game_map.infrastructure_sites = {site.id: site}
    world = SimpleNamespace(map=game_map, month_stamp=0, poi_manager=None)

    payload = get_world_map({"world": world}, sects_by_id={}, render_config={})

    assert payload["routes"] == [{
        "id": "route:black-iron",
        "endpoint_region_ids": [301, 302],
        "mode": "road",
        "capacity": 100.0,
        "quality": 0.8,
        "enabled": True,
        "allowed_resource_ids": [],
        "operational_capacity": 40.0,
        "dependency_site_ids": ["bridge:black-iron"],
    }]


def test_detail_query_supports_infrastructure_site_as_its_own_entity_type():
    runtime, _world = _runtime_with_site()

    payload = get_detail(
        runtime,
        target_type="site",
        target_id="mine:black-iron",
        sects_by_id={},
        build_sect_detail=lambda *_args: {},
        language_manager=None,
        resolve_avatar_pic_id=lambda _avatar: 0,
    )

    assert payload["id"] == "mine:black-iron"
    assert payload["status"] == "impaired"
    assert payload["last_event_id"] == "damage:event"
    assert payload["source_event_ids"] == ["damage:event"]
    assert payload["capability_ids"] == ["iron_extraction"]


def test_detail_query_projects_route_dependencies_and_causal_sources():
    game_map = Map(4, 3)
    route = Route("route:black-iron", (301, 302), "road", 100, 0.8, True)
    site = InfrastructureSite(
        id="bridge:black-iron",
        kind="bridge",
        name="Ponte de Ferro Negro",
        cell_refs=((2, 1),),
        region_ids=(301, 302),
        route_ids=(route.id,),
        integrity=0.5,
        last_event_id="damage:event",
    )
    game_map.routes = {route.id: route}
    game_map.infrastructure_sites = {site.id: site}
    world = SimpleNamespace(map=game_map, month_stamp=0, poi_manager=None)

    payload = get_detail(
        {"world": world},
        target_type="route",
        target_id=route.id,
        sects_by_id={},
        build_sect_detail=lambda *_args: {},
        language_manager=None,
        resolve_avatar_pic_id=lambda _avatar: 0,
    )

    assert payload == {
        "id": "route:black-iron",
        "name": "route:black-iron",
        "endpoint_region_ids": [301, 302],
        "mode": "road",
        "capacity": 100.0,
        "quality": 0.8,
        "enabled": True,
        "allowed_resource_ids": [],
        "operational_capacity": 40.0,
        "dependency_site_ids": ["bridge:black-iron"],
        "source_event_ids": ["damage:event"],
    }


def test_detail_query_returns_not_found_for_unknown_site():
    runtime, _world = _runtime_with_site()

    with pytest.raises(Exception) as exc_info:
        get_detail(
            runtime,
            target_type="site",
            target_id="missing",
            sects_by_id={},
            build_sect_detail=lambda *_args: {},
            language_manager=None,
            resolve_avatar_pic_id=lambda _avatar: 0,
        )

    assert getattr(exc_info.value, "status_code", None) == 404
