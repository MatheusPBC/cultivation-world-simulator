from __future__ import annotations

import math

import pytest

from src.classes.environment.geography import GeographyLayer, WaterBody, WaterBodyKind
from src.classes.environment.map import Map
from src.classes.environment.region import NormalRegion
from src.classes.environment.tile import TileType


def _geography(*, water_bodies=None, terrain_rows=None, elevation_rows=None) -> GeographyLayer:
    if terrain_rows is None:
        terrain_rows = [[TileType.PLAIN] * 5 for _ in range(4)]
        for body in water_bodies or []:
            for x, y in body.cell_refs:
                if 0 <= x < 5 and 0 <= y < 4:
                    terrain_rows[y][x] = (
                        TileType.SEA if body.kind is WaterBodyKind.SEA else TileType.WATER
                    )
    return GeographyLayer(
        width=5,
        height=4,
        terrain_rows=terrain_rows,
        elevation_rows=elevation_rows or [[float(y) for _ in range(5)] for y in range(4)],
        water_bodies=water_bodies or [],
    )


def test_geography_validates_and_normalizes_physical_terrain_and_water() -> None:
    river = WaterBody(
        id="river-1",
        kind="river",
        cell_refs=[(1, 1), (2, 1)],
        navigable=True,
        region_id=10,
        flow_direction=[1, 0],
    )
    geography = _geography(
        water_bodies=[river],
        terrain_rows=[
            ["plain"] * 5,
            ["plain", "water", "water", "plain", "plain"],
            ["plain"] * 5,
            ["plain"] * 5,
        ],
        elevation_rows=[[0, 1, 2, 3, 4]] * 4,
    )

    assert geography.terrain_at(0, 0) is TileType.PLAIN
    assert geography.elevation_at(4, 3) == 4.0
    assert geography.water_bodies[0] == river
    assert geography.water_bodies[0].flow_direction == (1, 0)


@pytest.mark.parametrize("field", ["terrain_rows", "elevation_rows"])
def test_geography_rejects_invalid_matrix_shapes(field: str) -> None:
    kwargs = {field: [[TileType.PLAIN]]}
    with pytest.raises(ValueError):
        _geography(**kwargs)


@pytest.mark.parametrize("value", [TileType.CITY, TileType.CAVE, TileType.RUIN, TileType.SECT, "city"])
def test_geography_rejects_semantic_site_tiles(value: object) -> None:
    terrain_rows = [[TileType.PLAIN] * 5 for _ in range(4)]
    terrain_rows[2][3] = value  # type: ignore[assignment]
    with pytest.raises(ValueError, match="semantic site"):
        _geography(terrain_rows=terrain_rows)


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan, True, "high"])
def test_geography_rejects_non_finite_or_non_numeric_elevation(value: object) -> None:
    elevation_rows = [[0.0] * 5 for _ in range(4)]
    elevation_rows[0][0] = value  # type: ignore[assignment]
    with pytest.raises(ValueError, match="elevation"):
        _geography(elevation_rows=elevation_rows)


@pytest.mark.parametrize("value", [-12000.1, 10000.1])
def test_geography_rejects_elevation_outside_world_bounds(value: float) -> None:
    elevation_rows = [[0.0] * 5 for _ in range(4)]
    elevation_rows[0][0] = value
    with pytest.raises(ValueError, match="between -12000 and 10000"):
        _geography(elevation_rows=elevation_rows)


def test_water_body_rejects_invalid_identity_cells_and_kind_rules() -> None:
    with pytest.raises(ValueError):
        WaterBody("", WaterBodyKind.LAKE, [(0, 0)], False)
    with pytest.raises(ValueError):
        WaterBody("lake", WaterBodyKind.LAKE, [], False)
    with pytest.raises(ValueError):
        WaterBody("lake", WaterBodyKind.LAKE, [(0, 0), (0, 0)], False)
    with pytest.raises(ValueError):
        WaterBody("river", WaterBodyKind.RIVER, [(0, 0)], False)
    with pytest.raises(ValueError):
        WaterBody("river", WaterBodyKind.RIVER, [(0, 0)], False, flow_direction=(0, 0))
    with pytest.raises(ValueError):
        WaterBody("river", WaterBodyKind.RIVER, [(0, 0)], False, flow_direction=(2, 0))
    with pytest.raises(ValueError):
        WaterBody("lake", WaterBodyKind.LAKE, [(0, 0)], False, flow_direction=(1, 0))


def test_geography_rejects_out_of_bounds_water_and_duplicate_ids() -> None:
    outside = WaterBody("outside", WaterBodyKind.SEA, [(5, 0)], False)
    with pytest.raises(ValueError, match="outside"):
        _geography(water_bodies=[outside])

    first = WaterBody("same", WaterBodyKind.LAKE, [(0, 0)], False)
    second = WaterBody("same", WaterBodyKind.SEA, [(1, 0)], False)
    with pytest.raises(ValueError, match="duplicate"):
        _geography(water_bodies=[first, second])

    dry = WaterBody("dry", WaterBodyKind.LAKE, [(0, 0)], False)
    with pytest.raises(ValueError, match="requires water"):
        _geography(
            water_bodies=[dry],
            terrain_rows=[[TileType.PLAIN] * 5 for _ in range(4)],
        )


def test_map_owns_default_geography_and_accepts_authored_geography() -> None:
    game_map = Map(width=5, height=4)
    assert game_map.get_terrain(0, 0) is TileType.PLAIN
    assert game_map.get_elevation(0, 0) == 0.0
    assert game_map.get_water_bodies_at(0, 0) == []

    geography = _geography()
    game_map.set_geography(geography)
    assert game_map.geography is geography
    assert game_map.get_terrain(0, 0) is TileType.PLAIN
    assert game_map.get_elevation(4, 3) == 3.0
    assert game_map.get_elevation(-1, 0) is None

    with pytest.raises(ValueError):
        game_map.set_geography(GeographyLayer(1, 1, [[TileType.PLAIN]], [[0]], []))


def _set_region(game_map: Map, region_id: int, cells: list[tuple[int, int]]) -> None:
    region = NormalRegion(id=region_id, name=f"region-{region_id}", desc="", cors=cells)
    game_map.regions[region_id] = region
    game_map.region_cors[region_id] = cells


def test_map_queries_water_touching_regions_and_mesh_neighbors_deterministically() -> None:
    game_map = Map(width=5, height=4)
    _set_region(game_map, 1, [(0, 0), (0, 1)])
    _set_region(game_map, 2, [(1, 0), (1, 1)])
    _set_region(game_map, 3, [(4, 3)])
    river = WaterBody("river", WaterBodyKind.RIVER, [(1, 0), (2, 0)], False, flow_direction=(1, 0))
    lake = WaterBody("lake", WaterBodyKind.LAKE, [(4, 2)], False)
    game_map.set_geography(_geography(water_bodies=[river, lake]))

    assert [body.id for body in game_map.get_water_bodies_at(2, 0)] == ["river"]
    assert [body.id for body in game_map.get_water_bodies_touching_region(1)] == ["river"]
    assert [body.id for body in game_map.get_water_bodies_touching_region(3)] == ["lake"]
    assert game_map.get_water_bodies_touching_region(999) == []
    assert game_map.get_neighboring_region_ids(1) == [2]
    assert game_map.get_neighboring_region_ids(2) == [1]
    assert game_map.get_neighboring_region_ids(999) == []


def test_map_projects_region_centers_for_upstream_and_downstream() -> None:
    game_map = Map(width=5, height=4)
    _set_region(game_map, 10, [(0, 1), (1, 1)])
    _set_region(game_map, 20, [(2, 1), (3, 1)])
    river = WaterBody("river", WaterBodyKind.RIVER, [(1, 1), (2, 1)], False, flow_direction=(1, 0))
    game_map.set_geography(_geography(water_bodies=[river]))

    assert game_map.get_river_relation(10, 20) == "upstream"
    assert game_map.get_river_relation(20, 10) == "downstream"
    assert game_map.get_river_relation(10, 30) is None


def test_river_relation_requires_shared_river_and_is_ambiguous_when_rivers_disagree() -> None:
    game_map = Map(width=5, height=4)
    _set_region(game_map, 10, [(0, 1), (1, 1)])
    _set_region(game_map, 20, [(2, 1), (3, 1)])
    north = WaterBody("north", WaterBodyKind.RIVER, [(1, 1), (2, 1)], False, flow_direction=(1, 0))
    south = WaterBody("south", WaterBodyKind.RIVER, [(1, 1), (2, 1)], False, flow_direction=(-1, 0))
    game_map.set_geography(_geography(water_bodies=[north, south]))

    assert game_map.get_river_relation(10, 20) is None


def test_river_relation_uses_touched_segments_not_region_centers() -> None:
    game_map = Map(width=5, height=4)
    _set_region(game_map, 10, [(0, 1), (4, 3)])
    _set_region(game_map, 20, [(3, 1), (0, 3)])
    river = WaterBody(
        "river",
        WaterBodyKind.RIVER,
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        False,
        flow_direction=(1, 0),
    )
    game_map.set_geography(_geography(water_bodies=[river]))

    assert game_map.get_river_relation(10, 20) == "upstream"


def test_river_relation_is_unknown_when_touched_segments_overlap() -> None:
    game_map = Map(width=5, height=4)
    _set_region(game_map, 10, [(0, 0)])
    _set_region(game_map, 20, [(0, 2)])
    river = WaterBody(
        "river",
        WaterBodyKind.RIVER,
        [(0, 1), (1, 1)],
        False,
        flow_direction=(1, 0),
    )
    game_map.set_geography(_geography(water_bodies=[river]))

    assert game_map.get_river_relation(10, 20) is None
