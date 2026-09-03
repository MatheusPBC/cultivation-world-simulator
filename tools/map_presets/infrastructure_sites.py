"""Validation helpers for the schema-v6 spatial infrastructure catalog.

The catalog is deliberately declarative.  It identifies spatial assets that
other runtime owners may later use; it does not contain stock, production,
route throughput, or generated outcomes.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Iterable


INFRASTRUCTURE_SITE_FIELDS = frozenset(
    {
        "id",
        "kind",
        "name",
        "cell_refs",
        "region_ids",
        "route_ids",
        "water_body_ids",
        "capability_ids",
        "owner_ref",
        "maintainer_ref",
        "integrity",
        "enabled",
        "last_event_id",
    }
)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Infrastructure site {field_name} must be a non-empty string")
    return value


def _validate_ref(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Infrastructure site {field_name} must be null or an ID reference")
    if set(value) != {"kind", "id"}:
        raise ValueError(f"Infrastructure site {field_name} must contain only kind and id")
    _require_non_empty_string(value["kind"], f"{field_name}.kind")
    _require_non_empty_string(value["id"], f"{field_name}.id")
    return deepcopy(value)


def _validate_id_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Infrastructure site {field_name} must be a list")
    result: list[str] = []
    for item in value:
        item = _require_non_empty_string(item, f"{field_name} item")
        if item in result:
            raise ValueError(f"Infrastructure site {field_name} contains duplicate ID: {item}")
        result.append(item)
    return result


def _validate_int_list(value: Any, field_name: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Infrastructure site {field_name} must be a non-empty list")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f"Infrastructure site {field_name} must contain positive integers")
        if item in result:
            raise ValueError(f"Infrastructure site {field_name} contains duplicate ID: {item}")
        result.append(item)
    return result


def _validate_cell_refs(value: Any, *, width: int, height: int, site_id: str) -> list[list[int]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Infrastructure site {site_id} cell_refs must be a non-empty list")
    result: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for cell in value:
        if (
            not isinstance(cell, list)
            or len(cell) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in cell)
        ):
            raise ValueError(f"Infrastructure site {site_id} cell_refs must contain [x, y] integer pairs")
        x, y = cell
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"Infrastructure site {site_id} cell is out of bounds: {(x, y)}")
        if (x, y) in seen:
            raise ValueError(f"Infrastructure site {site_id} contains duplicate cell: {(x, y)}")
        seen.add((x, y))
        result.append([x, y])
    return result


def _as_site_dict(site: Any) -> dict[str, Any]:
    if isinstance(site, dict):
        return site
    to_dict = getattr(site, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, dict):
            return value
    raise ValueError("Infrastructure site must be an object")


def validate_infrastructure_sites(
    sites: Iterable[Any],
    *,
    width: int,
    height: int,
    region_rows: list[list[int]],
    routes: Iterable[Any],
    water_bodies: Iterable[Any],
) -> list[dict[str, Any]]:
    """Validate and return a detached, canonical JSON-ready site list."""

    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("Infrastructure site validation requires a positive map size")
    if len(region_rows) != height or any(len(row) != width for row in region_rows):
        raise ValueError("Infrastructure site validation requires a valid region_rows matrix")

    route_by_id: dict[str, Any] = {}
    for route in routes:
        route_id = route.get("id") if isinstance(route, dict) else getattr(route, "id", None)
        if isinstance(route_id, str):
            route_by_id[route_id] = route

    water_by_id: dict[str, Any] = {}
    for body in water_bodies:
        body_id = body.get("id") if isinstance(body, dict) else getattr(body, "id", None)
        if isinstance(body_id, str):
            water_by_id[body_id] = body

    result: list[dict[str, Any]] = []
    seen_site_ids: set[str] = set()
    for raw_site in sites:
        site = _as_site_dict(raw_site)
        missing = INFRASTRUCTURE_SITE_FIELDS - set(site)
        if missing:
            raise ValueError(
                f"Infrastructure site is missing fields: {', '.join(sorted(missing))}"
            )
        unknown = set(site) - INFRASTRUCTURE_SITE_FIELDS
        if unknown:
            raise ValueError(
                f"Infrastructure site has unknown fields: {', '.join(sorted(unknown))}"
            )

        site_id = _require_non_empty_string(site["id"], "id")
        if site_id in seen_site_ids:
            raise ValueError(f"Duplicate infrastructure site id: {site_id}")
        seen_site_ids.add(site_id)

        kind = _require_non_empty_string(site["kind"], f"{site_id}.kind")
        name = _require_non_empty_string(site["name"], f"{site_id}.name")
        cells = _validate_cell_refs(site["cell_refs"], width=width, height=height, site_id=site_id)
        region_ids = _validate_int_list(site["region_ids"], f"{site_id}.region_ids")
        route_ids = _validate_id_list(site["route_ids"], f"{site_id}.route_ids")
        water_body_ids = _validate_id_list(site["water_body_ids"], f"{site_id}.water_body_ids")
        capability_ids = _validate_id_list(site["capability_ids"], f"{site_id}.capability_ids")

        for route_id in route_ids:
            if route_id not in route_by_id:
                raise ValueError(f"Infrastructure site {site_id} references unknown route: {route_id}")
        for body_id in water_body_ids:
            if body_id not in water_by_id:
                raise ValueError(f"Infrastructure site {site_id} references unknown water body: {body_id}")
            body = water_by_id[body_id]
            raw_body_cells = body.get("cell_refs", []) if isinstance(body, dict) else getattr(body, "cell_refs", ())
            body_cells = {tuple(cell) for cell in raw_body_cells}
            site_cells = {tuple(cell) for cell in cells}
            if not any(
                cell in site_cells
                or any(
                    (cell[0] + dx, cell[1] + dy) in site_cells
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                )
                for cell in body_cells
            ):
                raise ValueError(
                    f"Infrastructure site {site_id} water body {body_id} does not touch its cells"
                )

        for x, y in cells:
            region_id = int(region_rows[y][x])
            if region_id not in region_ids:
                raise ValueError(
                    f"Infrastructure site {site_id} cell {(x, y)} is outside its region_ids"
                )
        for route_id in route_ids:
            if not set(_route_endpoints(route_by_id[route_id])).issubset(set(region_ids)):
                raise ValueError(
                    f"Infrastructure site {site_id} route {route_id} is not connected to its regions"
                )

        integrity = site["integrity"]
        if isinstance(integrity, bool) or not isinstance(integrity, (int, float)):
            raise ValueError(f"Infrastructure site {site_id} integrity must be a finite number")
        if not math.isfinite(float(integrity)) or not 0 <= float(integrity) <= 1:
            raise ValueError(f"Infrastructure site {site_id} integrity must be between 0 and 1")
        if not isinstance(site["enabled"], bool):
            raise ValueError(f"Infrastructure site {site_id} enabled must be a boolean")
        last_event_id = site["last_event_id"]
        if last_event_id is not None:
            _require_non_empty_string(last_event_id, f"{site_id}.last_event_id")

        result.append(
            {
                "id": site_id,
                "kind": kind,
                "name": name,
                "cell_refs": deepcopy(cells),
                "region_ids": list(region_ids),
                "route_ids": list(route_ids),
                "water_body_ids": list(water_body_ids),
                "capability_ids": list(capability_ids),
                "owner_ref": _validate_ref(site["owner_ref"], f"{site_id}.owner_ref"),
                "maintainer_ref": _validate_ref(site["maintainer_ref"], f"{site_id}.maintainer_ref"),
                "integrity": float(integrity),
                "enabled": site["enabled"],
                "last_event_id": last_event_id,
            }
        )
    return result


def _route_endpoints(route: Any) -> list[int]:
    endpoints = route.get("endpoint_region_ids") if isinstance(route, dict) else getattr(route, "endpoint_region_ids", ())
    return [int(region_id) for region_id in endpoints]
