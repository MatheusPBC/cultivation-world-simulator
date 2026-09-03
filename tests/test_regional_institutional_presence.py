from types import SimpleNamespace

from src.classes.environment.city_state import CityGovernance
from src.classes.environment.region import CityRegion, NormalRegion
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.server.api.public_v1.query import create_public_query_router
from src.server.services.game_query_service import GameQueryService
from src.systems.government_interpreter import government_affordance_context
from src.systems.regional_institutional_presence import (
    project_regional_institutional_presence,
)


def _map_with_regions() -> tuple[Map, CityRegion, NormalRegion]:
    game_map = Map(width=3, height=1)
    for x in range(3):
        game_map.create_tile(x, 0, TileType.PLAIN)
    city = CityRegion(
        id=301,
        name="Cidade do Rio",
        desc="",
        cors=[(0, 0), (1, 0)],
    )
    wilderness = NormalRegion(
        id=402,
        name="Vale Aberto",
        desc="",
        cors=[(2, 0)],
    )
    game_map.regions = {city.id: city, wilderness.id: wilderness}
    game_map.region_cors = {
        city.id: list(city.cors),
        wilderness.id: list(wilderness.cors),
    }
    return game_map, city, wilderness


def test_projection_aggregates_governance_and_sect_influence_without_ownership():
    game_map, city, wilderness = _map_with_regions()
    sect_a = SimpleNamespace(id=7, name="Seita Azul", color="#00AAFF")
    sect_b = SimpleNamespace(id=8, name="Seita Rubra", color="#FF0000")
    snapshot = SimpleNamespace(
        active_sects=[sect_b, sect_a],
        tile_owners={(0, 0): [8], (1, 0): [7], (2, 0): [7]},
    )
    city.city_state.governance = CityGovernance("dynasty", "dynasty:1", 0.75)

    result = project_regional_institutional_presence(game_map, snapshot)

    assert [item["region_id"] for item in result["regions"]] == [301, 402]
    city_projection = result["regions"][0]
    assert city_projection["governance"] == {
        "controller_kind": "dynasty",
        "controller_id": "dynasty:1",
        "administrative_capacity": 0.75,
    }
    assert city_projection["sect_influences"] == [
        {
            "sect_id": 7,
            "sect_name": "Seita Azul",
            "color": "#00AAFF",
            "owned_tile_count": 1,
            "share": 0.5,
        },
        {
            "sect_id": 8,
            "sect_name": "Seita Rubra",
            "color": "#FF0000",
            "owned_tile_count": 1,
            "share": 0.5,
        },
    ]
    assert city_projection["dominant_sect_id"] == 7
    assert result["regions"][1]["governance"] is None
    assert result["regions"][1]["dominant_sect_id"] == 7


def test_projection_fails_closed_for_invalid_region_footprint():
    game_map, city, _ = _map_with_regions()
    city.cors = [(0, 0), (99, 99)]
    snapshot = SimpleNamespace(active_sects=[], tile_owners={})

    assert project_regional_institutional_presence(game_map, snapshot) == {
        "regions": [
            {
                "region_id": 402,
                "region_name": "Vale Aberto",
                "region_type": "normal",
                "tile_count": 1,
                "governance": None,
                "sect_influences": [],
                "dominant_sect_id": None,
            }
        ]
    }


def test_world_institutional_presence_api_is_empty_without_world():
    query_service = GameQueryService.__new__(GameQueryService)
    query_service._deps = SimpleNamespace(runtime={"world": None})
    router = create_public_query_router(query_service=query_service)
    endpoint = next(
        route.endpoint
        for route in router.routes
        if route.path == "/api/v1/query/world/institutional-presence"
    )

    assert endpoint() == {"ok": True, "data": {"regions": []}}


def test_government_affordance_context_uses_canonical_dynasty_ownership(base_world):
    from tests.domain_reactivity_fixtures import setup_government_condition

    city, trigger, condition = setup_government_condition(base_world)

    context, resolved_city, dynasty = government_affordance_context(
        base_world,
        trigger,
        condition,
    )

    assert resolved_city is city
    assert dynasty is base_world.dynasty
    assert context.actor_ref.kind == "dynasty"
    assert context.actor_ref.id == str(base_world.dynasty.id)
    assert context.condition is condition
