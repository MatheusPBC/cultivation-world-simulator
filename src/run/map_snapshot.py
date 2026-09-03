from __future__ import annotations

from typing import Any

from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.map import Map
from src.classes.environment.route import Route
from src.run.load_map import build_map_from_source
from src.run.map_presets import DEFAULT_MAP_ID
from src.run.map_source import MapLandmark, MapRegionOverride, MapSource


MAP_SNAPSHOT_SCHEMA_VERSION = 5


def _serialize_geography(game_map: Map) -> dict[str, Any]:
    geography = getattr(game_map, "geography", None)
    if not isinstance(geography, GeographyLayer):
        raise ValueError("Map snapshot requires a physical geography layer")

    return {
        "terrain_rows": [
            [terrain.value for terrain in row]
            for row in geography.terrain_rows
        ],
        "elevation_rows": [list(row) for row in geography.elevation_rows],
        "water_bodies": [
            {
                "id": body.id,
                "kind": body.kind.value,
                "cell_refs": [list(cell) for cell in body.cell_refs],
                "navigable": body.navigable,
                **({"region_id": body.region_id} if body.region_id is not None else {}),
                **({"flow_direction": list(body.flow_direction)} if body.flow_direction is not None else {}),
            }
            for body in geography.water_bodies
        ],
    }


def serialize_map_snapshot(game_map: Map) -> dict[str, Any]:
    region_rows: list[list[int]] = []

    for y in range(game_map.height):
        region_row: list[int] = []
        for x in range(game_map.width):
            tile = game_map.get_tile(x, y)
            region_row.append(int(tile.region.id) if tile.region is not None else -1)
        region_rows.append(region_row)

    return {
        "schema_version": MAP_SNAPSHOT_SCHEMA_VERSION,
        "preset_id": getattr(game_map, "map_id", DEFAULT_MAP_ID),
        "map_name": str(getattr(game_map, "map_name", "") or ""),
        "preset_version": int(getattr(game_map, "preset_version", 1) or 1),
        "width": int(game_map.width),
        "height": int(game_map.height),
        "region_rows": region_rows,
        "geography": _serialize_geography(game_map),
        "landmarks": getattr(game_map, "landmarks", {}) or {},
        "region_overrides": getattr(game_map, "region_overrides", {}) or {},
        "routes": [
            route.to_dict()
            for route in sorted(getattr(game_map, "routes", {}).values(), key=lambda item: item.id)
        ],
        "infrastructure_sites": [
            site.to_dict()
            for site in sorted(
                getattr(game_map, "infrastructure_sites", {}).values(),
                key=lambda item: item.id,
            )
        ],
    }


def _validate_matrix_shape(rows: Any, *, width: int, height: int, field_name: str) -> list[list[Any]]:
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError(f"Invalid {field_name} height")

    normalized: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"Invalid {field_name} width")
        normalized.append(row)
    return normalized


def load_map_from_snapshot(snapshot: dict[str, Any]) -> Map:
    if not isinstance(snapshot, dict):
        raise ValueError("Map snapshot must be an object")

    schema_version = int(snapshot.get("schema_version", 0) or 0)
    if schema_version != MAP_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported map snapshot schema version: {schema_version}")

    obsolete_fields = {"wilderness_tile", "region_tile_overrides"}.intersection(snapshot)
    if obsolete_fields:
        fields = ", ".join(sorted(obsolete_fields))
        raise ValueError(f"Obsolete map snapshot fields: {fields}")

    width = int(snapshot.get("width", 0) or 0)
    height = int(snapshot.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid map snapshot size")

    region_rows = _validate_matrix_shape(
        snapshot.get("region_rows"),
        width=width,
        height=height,
        field_name="region_rows",
    )

    normalized_region_rows: list[list[int]] = []
    for region_row in region_rows:
        normalized_region_row: list[int] = []
        for region_id in region_row:
            if isinstance(region_id, bool) or not isinstance(region_id, int):
                raise ValueError("region_rows values must be integer region IDs or -1")
            if region_id != -1 and region_id <= 0:
                raise ValueError("region_rows values must be positive region IDs or -1")
            normalized_region_row.append(region_id)
        normalized_region_rows.append(normalized_region_row)

    geography_data = snapshot.get("geography")
    if not isinstance(geography_data, dict):
        raise ValueError("geography is required in map snapshot")
    terrain_rows = _validate_matrix_shape(
        geography_data.get("terrain_rows"),
        width=width,
        height=height,
        field_name="geography.terrain_rows",
    )
    elevation_rows = _validate_matrix_shape(
        geography_data.get("elevation_rows"),
        width=width,
        height=height,
        field_name="geography.elevation_rows",
    )
    raw_water_bodies = geography_data.get("water_bodies")
    if not isinstance(raw_water_bodies, list):
        raise ValueError("geography.water_bodies must be a list")
    water_bodies: list[WaterBody] = []
    for raw_body in raw_water_bodies:
        if not isinstance(raw_body, dict):
            raise ValueError("geography.water_bodies must contain objects")
        required = ("id", "kind", "cell_refs", "navigable")
        missing = [field for field in required if field not in raw_body]
        if missing:
            raise ValueError(f"Water body missing fields: {', '.join(missing)}")
        try:
            water_bodies.append(
                WaterBody(
                    id=raw_body["id"],
                    kind=raw_body["kind"],
                    cell_refs=tuple(tuple(cell) for cell in raw_body["cell_refs"]),
                    navigable=raw_body["navigable"],
                    region_id=raw_body.get("region_id"),
                    flow_direction=(
                        tuple(raw_body["flow_direction"])
                        if raw_body.get("flow_direction") is not None
                        else None
                    ),
                )
            )
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid water body in map snapshot: {exc}") from exc

    region_ids = {
        region_id
        for row in normalized_region_rows
        for region_id in row
        if region_id != -1
    }
    for body in water_bodies:
        if body.region_id is None:
            continue
        if body.region_id not in region_ids:
            raise ValueError(
                f"Water body {body.id} references unknown region id: {body.region_id}"
            )
        if not any(
            normalized_region_rows[y][x] == body.region_id
            for x, y in body.cell_refs
        ):
            raise ValueError(
                f"Water body {body.id} does not intersect its region id: {body.region_id}"
            )

    raw_routes = snapshot.get("routes")
    if not isinstance(raw_routes, list):
        raise ValueError("routes is required in map snapshot")
    routes: list[Route] = []
    route_ids: set[str] = set()
    for raw_route in raw_routes:
        try:
            route = Route.from_dict(raw_route)
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid route in map snapshot: {exc}") from exc
        if route.id in route_ids:
            raise ValueError(f"Duplicate route id: {route.id}")
        missing_regions = set(route.endpoint_region_ids) - region_ids
        if missing_regions:
            raise ValueError(
                f"Route {route.id} references unknown region ids: "
                + ", ".join(str(region_id) for region_id in sorted(missing_regions))
            )
        route_ids.add(route.id)
        routes.append(route)

    raw_sites = snapshot.get("infrastructure_sites")
    if not isinstance(raw_sites, list):
        raise ValueError("infrastructure_sites is required in map snapshot")
    infrastructure_sites: list[InfrastructureSite] = []
    for raw_site in raw_sites:
        try:
            infrastructure_sites.append(InfrastructureSite.from_dict(raw_site))
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid infrastructure site in map snapshot: {exc}") from exc

    preset_id = str(snapshot.get("preset_id") or DEFAULT_MAP_ID)
    landmarks: dict[int, MapLandmark] = {}
    raw_landmarks = snapshot.get("landmarks") or {}
    if isinstance(raw_landmarks, dict):
        for raw_region_id, value in raw_landmarks.items():
            if not isinstance(value, dict):
                continue
            landmarks[int(raw_region_id)] = MapLandmark(
                x=int(value.get("x", 0)),
                y=int(value.get("y", 0)),
                asset=str(value.get("asset") or ""),
            )

    region_overrides: dict[int, dict[str, Any]] = {}
    raw_region_overrides = snapshot.get("region_overrides") or {}
    if isinstance(raw_region_overrides, dict):
        for raw_region_id, value in raw_region_overrides.items():
            if not isinstance(value, dict):
                continue
            override: dict[str, Any] = {}
            if value.get("name_id") is not None:
                override["name_id"] = str(value.get("name_id") or "")
            if value.get("desc_id") is not None:
                override["desc_id"] = str(value.get("desc_id") or "")
            if override:
                region_overrides[int(raw_region_id)] = override

    source = MapSource(
        map_id=preset_id,
        version=int(snapshot.get("preset_version", 1) or 1),
        width=width,
        height=height,
        region_rows=normalized_region_rows,
        geography=GeographyLayer(
            width=width,
            height=height,
            terrain_rows=terrain_rows,
            elevation_rows=elevation_rows,
            water_bodies=water_bodies,
        ),
        landmarks=landmarks,
        region_overrides={
            rid: MapRegionOverride(
                name_id=str(value.get("name_id")) if value.get("name_id") is not None else None,
                desc_id=str(value.get("desc_id")) if value.get("desc_id") is not None else None,
            )
            for rid, value in region_overrides.items()
        },
        infrastructure_sites=tuple(infrastructure_sites),
        routes=tuple(routes),
    )
    return build_map_from_source(
        source,
        map_id=preset_id,
        map_name=str(snapshot.get("map_name") or ""),
        preset_version=int(snapshot.get("preset_version", 1) or 1),
    )
