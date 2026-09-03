from __future__ import annotations

import json
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.tile import TileType
from src.classes.environment.route import Route


MAP_SOURCE_SCHEMA_VERSION = 6
SEMANTIC_TILE_TYPES = frozenset({"city", "cave", "ruin", "sect"})
WATER_TERRAIN_TYPES = frozenset({"water", "sea", "marsh"})


@dataclass(frozen=True)
class MapLandmark:
    x: int
    y: int
    asset: str

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "asset": self.asset}


@dataclass(frozen=True)
class MapRegionOverride:
    name_id: str | None = None
    desc_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.name_id is not None:
            data["name_id"] = self.name_id
        if self.desc_id is not None:
            data["desc_id"] = self.desc_id
        return data


@dataclass(frozen=True)
class MapSource:
    map_id: str
    version: int
    width: int
    height: int
    region_rows: list[list[int]]
    geography: GeographyLayer
    landmarks: dict[int, MapLandmark]
    region_overrides: dict[int, MapRegionOverride]
    infrastructure_sites: tuple[InfrastructureSite, ...]
    routes: tuple[Route, ...] = ()


def _validate_region_rows(rows: Any, *, width: int, height: int) -> list[list[int]]:
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError("Invalid region_rows height")

    normalized: list[list[int]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("Invalid region_rows width")
        normalized_row: list[int] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("region_rows values must be integer region IDs or -1")
            if value != -1 and value <= 0:
                raise ValueError("region_rows values must be positive region IDs or -1")
            normalized_row.append(value)
        normalized.append(normalized_row)
    return normalized


def _validate_terrain_rows(rows: Any, *, width: int, height: int) -> list[list[str]]:
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError("Invalid geography.terrain_rows height")

    normalized: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("Invalid geography.terrain_rows width")
        normalized_row: list[str] = []
        for value in row:
            if not isinstance(value, str) or value != value.strip():
                raise ValueError("geography.terrain_rows values must be canonical tile names")
            tile_name = value.strip()
            try:
                TileType(tile_name)
            except ValueError as exc:
                raise ValueError(f"Unknown geography terrain tile: {value}") from exc
            if tile_name in SEMANTIC_TILE_TYPES:
                raise ValueError(f"Semantic tile is forbidden in geography.terrain_rows: {value}")
            normalized_row.append(tile_name)
        normalized.append(normalized_row)
    return normalized


def _validate_elevation_rows(rows: Any, *, width: int, height: int) -> list[list[float | int]]:
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError("Invalid geography.elevation_rows height")

    normalized: list[list[float | int]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("Invalid geography.elevation_rows width")
        normalized_row: list[float | int] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError("geography.elevation_rows values must be finite numbers")
            elevation = float(value)
            if not math.isfinite(elevation) or elevation < -12000 or elevation > 10000:
                raise ValueError("geography.elevation_rows values must be between -12000 and 10000")
            normalized_row.append(value)
        normalized.append(normalized_row)
    return normalized


def _parse_water_bodies(
    raw: Any,
    *,
    width: int,
    height: int,
    region_rows: list[list[int]],
    terrain_rows: list[list[str]],
) -> tuple[WaterBody, ...]:
    if not isinstance(raw, list):
        raise ValueError("geography.water_bodies must be a list")

    bodies: list[WaterBody] = []
    body_ids: set[str] = set()
    for value in raw:
        if not isinstance(value, dict):
            raise ValueError("Water body must be an object")
        required = ("id", "kind", "cell_refs", "navigable")
        missing = [field_name for field_name in required if field_name not in value]
        if missing:
            raise ValueError(f"Water body missing fields: {', '.join(missing)}")

        body_id = value["id"]
        if not isinstance(body_id, str) or not body_id.strip() or body_id != body_id.strip():
            raise ValueError("Water body id must be a non-empty string")
        if body_id in body_ids:
            raise ValueError(f"Duplicate water body id: {body_id}")

        kind = value["kind"]
        if kind not in {"river", "lake", "sea"}:
            raise ValueError(f"Unknown water body kind: {kind}")
        if not isinstance(value["navigable"], bool):
            raise ValueError(f"Water body {body_id} navigable must be a boolean")

        raw_cells = value["cell_refs"]
        if not isinstance(raw_cells, list) or not raw_cells:
            raise ValueError(f"Water body {body_id} cell_refs must be a non-empty list")
        cell_refs: list[tuple[int, int]] = []
        seen_cells: set[tuple[int, int]] = set()
        for raw_cell in raw_cells:
            if (
                not isinstance(raw_cell, (list, tuple))
                or len(raw_cell) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in raw_cell)
            ):
                raise ValueError(f"Water body {body_id} cell_refs must contain [x, y] integer pairs")
            x, y = int(raw_cell[0]), int(raw_cell[1])
            if x < 0 or y < 0 or x >= width or y >= height:
                raise ValueError(f"Water body {body_id} cell is out of bounds: {(x, y)}")
            if (x, y) in seen_cells:
                raise ValueError(f"Water body {body_id} contains duplicate cell: {(x, y)}")
            if terrain_rows[y][x] not in WATER_TERRAIN_TYPES:
                raise ValueError(
                    f"Water body {body_id} cell {(x, y)} is incompatible with terrain {terrain_rows[y][x]}"
                )
            seen_cells.add((x, y))
            cell_refs.append((x, y))

        region_id = value.get("region_id")
        if region_id is not None:
            if isinstance(region_id, bool) or not isinstance(region_id, int) or region_id <= 0:
                raise ValueError(f"Water body {body_id} region_id must be a positive integer")
            if region_id not in collect_region_coords(region_rows):
                raise ValueError(f"Water body {body_id} references unknown region id: {region_id}")
            if not any(region_rows[y][x] == region_id for x, y in cell_refs):
                raise ValueError(
                    f"Water body {body_id} does not intersect its region id: {region_id}"
                )

        flow_direction = value.get("flow_direction")
        if kind == "river" and flow_direction is None:
            raise ValueError(f"River water body {body_id} requires flow_direction")
        normalized_flow: tuple[int, int] | None = None
        if flow_direction is not None:
            if (
                not isinstance(flow_direction, (list, tuple))
                or len(flow_direction) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in flow_direction)
            ):
                raise ValueError(
                    f"Water body {body_id} flow_direction must contain two integers"
                )
            if any(item not in (-1, 0, 1) for item in flow_direction):
                raise ValueError(
                    f"Water body {body_id} flow_direction must be cardinal or diagonal"
                )
            if not any(item != 0 for item in flow_direction):
                raise ValueError(f"Water body {body_id} flow_direction cannot be zero")
            normalized_flow = (flow_direction[0], flow_direction[1])

        body_ids.add(body_id)
        bodies.append(
            WaterBody(
                id=body_id,
                kind=kind,
                cell_refs=tuple(cell_refs),
                navigable=value["navigable"],
                region_id=region_id,
                flow_direction=normalized_flow,
            )
        )
    return tuple(bodies)


def _water_body_to_dict(body: WaterBody) -> dict[str, Any]:
    return {
        "id": body.id,
        "kind": body.kind.value,
        "cell_refs": [list(cell) for cell in body.cell_refs],
        "navigable": body.navigable,
        **({"region_id": body.region_id} if body.region_id is not None else {}),
        **({"flow_direction": list(body.flow_direction)} if body.flow_direction is not None else {}),
    }


def _parse_landmarks(raw: Any, *, width: int, height: int) -> dict[int, MapLandmark]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Invalid landmarks")

    landmarks: dict[int, MapLandmark] = {}
    for raw_region_id, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f"Invalid landmark for region {raw_region_id}")
        region_id = int(raw_region_id)
        x = int(value.get("x"))
        y = int(value.get("y"))
        asset = str(value.get("asset") or "").strip()
        if not asset:
            raise ValueError(f"Missing landmark asset for region {region_id}")
        if x < 0 or y < 0 or x >= width or y >= height:
            raise ValueError(f"Landmark out of bounds for region {region_id}: {(x, y)}")
        landmarks[region_id] = MapLandmark(x=x, y=y, asset=asset)
    return landmarks


def _parse_region_overrides(raw: Any) -> dict[int, MapRegionOverride]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Invalid region_overrides")

    overrides: dict[int, MapRegionOverride] = {}
    for raw_region_id, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f"Invalid region override for region {raw_region_id}")
        region_id = int(raw_region_id)
        name_id = str(value.get("name_id") or "").strip() or None
        desc_id = str(value.get("desc_id") or "").strip() or None
        if not name_id and not desc_id:
            continue
        overrides[region_id] = MapRegionOverride(name_id=name_id, desc_id=desc_id)
    return overrides


def _parse_routes(raw: Any, *, region_ids: set[int]) -> tuple[Route, ...]:
    if not isinstance(raw, list):
        raise ValueError("routes must be a list")

    routes: list[Route] = []
    route_ids: set[str] = set()
    for value in raw:
        route = Route.from_dict(value)
        if route.id in route_ids:
            raise ValueError(f"Duplicate route id: {route.id}")
        missing_regions = set(route.endpoint_region_ids) - region_ids
        if missing_regions:
            missing = ", ".join(str(region_id) for region_id in sorted(missing_regions))
            raise ValueError(f"Route {route.id} references unknown region ids: {missing}")
        route_ids.add(route.id)
        routes.append(route)
    return tuple(routes)


def _parse_infrastructure_sites(
    raw: Any,
    *,
    width: int,
    height: int,
    region_rows: list[list[int]],
    water_bodies: tuple[WaterBody, ...],
    routes: tuple[Route, ...],
) -> tuple[InfrastructureSite, ...]:
    if not isinstance(raw, list):
        raise ValueError("infrastructure_sites is required and must be a list")

    region_ids = set(collect_region_coords(region_rows))
    route_by_id = {route.id: route for route in routes}
    water_body_by_id = {body.id: body for body in water_bodies}
    sites: list[InfrastructureSite] = []
    site_ids: set[str] = set()
    for value in raw:
        site = InfrastructureSite.from_dict(value)
        if site.id in site_ids:
            raise ValueError(f"Duplicate infrastructure site id: {site.id}")
        if any(x < 0 or y < 0 or x >= width or y >= height for x, y in site.cell_refs):
            raise ValueError(f"Infrastructure site {site.id} has a cell outside map bounds")
        missing_regions = set(site.region_ids) - region_ids
        if missing_regions:
            missing = ", ".join(str(region_id) for region_id in sorted(missing_regions))
            raise ValueError(
                f"Infrastructure site {site.id} references unknown region ids: {missing}"
            )
        if any(region_rows[y][x] not in site.region_ids for x, y in site.cell_refs):
            raise ValueError(
                f"Infrastructure site {site.id} cell does not belong to one of its regions"
            )
        for route_id in site.route_ids:
            route = route_by_id.get(route_id)
            if route is None:
                raise ValueError(
                    f"Infrastructure site {site.id} references unknown route: {route_id}"
                )
            if not set(route.endpoint_region_ids).issubset(set(site.region_ids)):
                raise ValueError(
                    f"Infrastructure site {site.id} route {route_id} is not connected to its regions"
                )
        site_cells = set(site.cell_refs)
        for water_body_id in site.water_body_ids:
            body = water_body_by_id.get(water_body_id)
            if body is None:
                raise ValueError(
                    f"Infrastructure site {site.id} references unknown water body: {water_body_id}"
                )
            if not _water_body_touches_cells(body, site_cells):
                raise ValueError(
                    f"Infrastructure site {site.id} water body {water_body_id} does not touch its cells"
                )
        site_ids.add(site.id)
        sites.append(site)
    return tuple(sites)


def _water_body_touches_cells(body: WaterBody, cells: set[tuple[int, int]]) -> bool:
    return any(
        cell in cells
        or any(
            (cell[0] + dx, cell[1] + dy) in cells
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
        for cell in body.cell_refs
    )


def read_map_source(path: Path) -> MapSource:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schema_version = int(data.get("schema_version", 0) or 0)
    if schema_version != MAP_SOURCE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported map source schema version: {schema_version}")

    width = int(data.get("width", 0) or 0)
    height = int(data.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid map source size")

    if "wilderness_tile" in data:
        raise ValueError("wilderness_tile is obsolete; use geography.terrain_rows")
    region_rows = _validate_region_rows(data.get("region_rows"), width=width, height=height)
    geography_data = data.get("geography")
    if not isinstance(geography_data, dict):
        raise ValueError("geography is required")
    terrain_rows = _validate_terrain_rows(
        geography_data.get("terrain_rows"), width=width, height=height
    )
    elevation_rows = _validate_elevation_rows(
        geography_data.get("elevation_rows"), width=width, height=height
    )
    water_bodies = _parse_water_bodies(
        geography_data.get("water_bodies"),
        width=width,
        height=height,
        region_rows=region_rows,
        terrain_rows=terrain_rows,
    )
    routes = _parse_routes(
        data.get("routes"), region_ids=set(collect_region_coords(region_rows))
    )
    infrastructure_sites = _parse_infrastructure_sites(
        data.get("infrastructure_sites"),
        width=width,
        height=height,
        region_rows=region_rows,
        water_bodies=water_bodies,
        routes=routes,
    )

    return MapSource(
        map_id=str(data.get("id") or path.parent.name),
        version=int(data.get("version", 1) or 1),
        width=width,
        height=height,
        region_rows=region_rows,
        geography=GeographyLayer(
            width=width,
            height=height,
            terrain_rows=terrain_rows,
            elevation_rows=elevation_rows,
            water_bodies=list(water_bodies),
        ),
        landmarks=_parse_landmarks(data.get("landmarks"), width=width, height=height),
        region_overrides=_parse_region_overrides(data.get("region_overrides")),
        infrastructure_sites=infrastructure_sites,
        routes=routes,
    )


def map_source_to_dict(source: MapSource) -> dict[str, Any]:
    return {
        "schema_version": MAP_SOURCE_SCHEMA_VERSION,
        "id": source.map_id,
        "version": source.version,
        "width": source.width,
        "height": source.height,
        "region_rows": source.region_rows,
        "geography": {
            "terrain_rows": [
                [tile.value if isinstance(tile, TileType) else str(tile) for tile in row]
                for row in source.geography.terrain_rows
            ],
            "elevation_rows": source.geography.elevation_rows,
            "water_bodies": [_water_body_to_dict(body) for body in source.geography.water_bodies],
        },
        "landmarks": {
            str(region_id): landmark.to_dict()
            for region_id, landmark in sorted(source.landmarks.items())
        },
        "region_overrides": {
            str(region_id): override.to_dict()
            for region_id, override in sorted(source.region_overrides.items())
        },
        "infrastructure_sites": [
            site.to_dict() for site in sorted(source.infrastructure_sites, key=lambda item: item.id)
        ],
        "routes": [
            route.to_dict()
            for route in sorted(source.routes, key=lambda item: item.id)
        ],
    }

def collect_region_coords(region_rows: list[list[int]]) -> dict[int, list[tuple[int, int]]]:
    region_coords: dict[int, list[tuple[int, int]]] = {}
    for y, row in enumerate(region_rows):
        for x, value in enumerate(row):
            region_id = int(value)
            if region_id == -1:
                continue
            region_coords.setdefault(region_id, []).append((x, y))
    return region_coords
