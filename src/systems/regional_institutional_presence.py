"""Pure projection of administrative and sect presence by map region.

This module deliberately does not own state.  ``Map.regions`` owns the
semantic region records, ``CityState.governance`` owns urban administration,
and ``SectTerritorySnapshot`` owns the current spatial influence calculation.
The projection only joins those sources for read-only consumers.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from src.classes.environment.region import CityRegion


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _valid_cells(game_map: Any, region: Any, region_id: int) -> tuple[tuple[int, int], ...] | None:
    """Return a region footprint only when both map indexes agree exactly."""
    raw_cells = getattr(region, "cors", None)
    if not isinstance(raw_cells, (list, tuple)) or not raw_cells:
        return None

    width = getattr(game_map, "width", None)
    height = getattr(game_map, "height", None)
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or isinstance(height, bool)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        return None

    cells: list[tuple[int, int]] = []
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, (list, tuple)) or len(raw_cell) != 2:
            return None
        x, y = raw_cell
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
            or not (0 <= x < width and 0 <= y < height)
        ):
            return None
        cell = (x, y)
        if cell in cells:
            return None
        cells.append(cell)

    tiles = getattr(game_map, "tiles", None)
    if isinstance(tiles, Mapping) and any(cell not in tiles for cell in cells):
        return None

    indexed_regions = getattr(game_map, "region_cors", None)
    if not isinstance(indexed_regions, Mapping) or region_id not in indexed_regions:
        return None
    indexed_cells = indexed_regions[region_id]
    if not isinstance(indexed_cells, (list, tuple)):
        return None
    try:
        normalized_index = tuple(tuple(cell) for cell in indexed_cells)
    except TypeError:
        return None
    if set(normalized_index) != set(cells) or len(normalized_index) != len(cells):
        return None

    return tuple(cells)


def _active_sects(snapshot: Any) -> dict[int, Any] | None:
    raw_sects = getattr(snapshot, "active_sects", None)
    if not isinstance(raw_sects, Iterable) or isinstance(raw_sects, (str, bytes, Mapping)):
        return None

    by_id: dict[int, Any] = {}
    for sect in raw_sects:
        sect_id = _positive_int(getattr(sect, "id", None))
        name = getattr(sect, "name", None)
        color = getattr(sect, "color", None)
        if (
            sect_id is None
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(color, str)
            or len(color) != 7
            or not color.startswith("#")
            or any(char not in "0123456789abcdefABCDEF" for char in color[1:])
            or sect_id in by_id
        ):
            return None
        by_id[sect_id] = sect
    return by_id


def _valid_tile_owners(snapshot: Any, active_sects: Mapping[int, Any]) -> dict[tuple[int, int], int]:
    raw_owners = getattr(snapshot, "tile_owners", None)
    if not isinstance(raw_owners, Mapping):
        return {}

    owners: dict[tuple[int, int], int] = {}
    for raw_cell, raw_owner_ids in raw_owners.items():
        if not isinstance(raw_cell, (list, tuple)) or len(raw_cell) != 2:
            continue
        x, y = raw_cell
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
        ):
            continue
        if not isinstance(raw_owner_ids, (list, tuple)) or len(raw_owner_ids) != 1:
            continue
        owner_id = _positive_int(raw_owner_ids[0])
        if owner_id is None or owner_id not in active_sects:
            continue
        owners[(x, y)] = owner_id
    return owners


def _city_governance(region: CityRegion) -> dict[str, Any] | None:
    governance = getattr(getattr(region, "city_state", None), "governance", None)
    if governance is None:
        return None
    controller_kind = getattr(governance, "controller_kind", None)
    controller_id = getattr(governance, "controller_id", None)
    administrative_capacity = getattr(governance, "administrative_capacity", None)
    if controller_kind == "" and controller_id == "":
        return None
    if (
        not isinstance(controller_kind, str)
        or not controller_kind.strip()
        or not isinstance(controller_id, str)
        or not controller_id.strip()
        or isinstance(administrative_capacity, bool)
        or not isinstance(administrative_capacity, (int, float))
        or not math.isfinite(float(administrative_capacity))
        or administrative_capacity < 0
    ):
        return None
    return {
        "controller_kind": controller_kind,
        "controller_id": controller_id,
        "administrative_capacity": float(administrative_capacity),
    }


def project_regional_institutional_presence(
    game_map: Any,
    territory_snapshot: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Build a deterministic, read-only institutional presence projection.

    Invalid region footprints and malformed territory claims are ignored.  No
    fallback ownership or narrative value is invented when canonical inputs
    disagree.
    """
    regions = getattr(game_map, "regions", None)
    if not isinstance(regions, Mapping):
        return {"regions": []}

    active_sects = _active_sects(territory_snapshot)
    if active_sects is None:
        return {"regions": []}
    tile_owners = _valid_tile_owners(territory_snapshot, active_sects)
    projections: list[dict[str, Any]] = []

    for raw_region_key, region in sorted(regions.items(), key=lambda item: str(item[0])):
        region_id = _positive_int(raw_region_key)
        object_region_id = _positive_int(getattr(region, "id", None))
        if region_id is None or object_region_id != region_id:
            continue
        name = getattr(region, "name", None)
        get_region_type = getattr(region, "get_region_type", None)
        if not isinstance(name, str) or not name.strip() or not callable(get_region_type):
            continue
        try:
            region_type = get_region_type()
        except Exception:
            continue
        if not isinstance(region_type, str) or not region_type.strip():
            continue
        cells = _valid_cells(game_map, region, region_id)
        if cells is None:
            continue

        tile_counts: dict[int, int] = {}
        for cell in cells:
            sect_id = tile_owners.get(cell)
            if sect_id is not None:
                tile_counts[sect_id] = tile_counts.get(sect_id, 0) + 1

        tile_count = len(cells)
        sect_influences = [
            {
                "sect_id": sect_id,
                "sect_name": str(getattr(active_sects[sect_id], "name")),
                "color": str(getattr(active_sects[sect_id], "color")),
                "owned_tile_count": owned_tile_count,
                "share": float(owned_tile_count / tile_count),
            }
            for sect_id, owned_tile_count in sorted(
                tile_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        projection: dict[str, Any] = {
            "region_id": region_id,
            "region_name": name,
            "region_type": region_type,
            "tile_count": tile_count,
            "governance": None,
            "sect_influences": sect_influences,
            "dominant_sect_id": sect_influences[0]["sect_id"] if sect_influences else None,
        }
        if isinstance(region, CityRegion):
            projection["governance"] = _city_governance(region)
        projections.append(projection)

    projections.sort(key=lambda item: int(item["region_id"]))
    return {"regions": projections}


__all__ = ["project_regional_institutional_presence"]
