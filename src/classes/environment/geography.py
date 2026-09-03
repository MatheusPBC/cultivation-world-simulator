"""Map-owned physical geography primitives.

Physical geography deliberately does not know about ``Region`` instances.  A
region footprint and a physical terrain cell are different layers and may
overlap without changing one another.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Any

from src.classes.environment.tile import TileType


CellRef = tuple[int, int]
FlowDirection = tuple[int, int]

_SEMANTIC_TILE_TYPES = frozenset(
    {
        TileType.CITY,
        TileType.CAVE,
        TileType.RUIN,
        TileType.SECT,
    }
)
_WATER_TERRAIN_TYPES = frozenset(
    {
        TileType.WATER,
        TileType.SEA,
        TileType.MARSH,
    }
)
MIN_ELEVATION_METERS = -12_000.0
MAX_ELEVATION_METERS = 10_000.0


class WaterBodyKind(str, Enum):
    RIVER = "river"
    LAKE = "lake"
    SEA = "sea"


def _normalize_kind(value: Any) -> WaterBodyKind:
    if isinstance(value, WaterBodyKind):
        return value
    if isinstance(value, str):
        try:
            return WaterBodyKind(value.lower())
        except ValueError:
            pass
    raise ValueError("kind must be river, lake, or sea")


def _normalize_cell_ref(value: Any, field_name: str) -> CellRef:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field_name} must contain exactly two coordinates")
    x, y = value
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"{field_name}[0] must be an integer")
    if isinstance(y, bool) or not isinstance(y, int):
        raise ValueError(f"{field_name}[1] must be an integer")
    return (x, y)


def _normalize_flow_direction(value: Any) -> FlowDirection:
    direction = _normalize_cell_ref(value, "flow_direction")
    if any(component not in (-1, 0, 1) for component in direction):
        raise ValueError("flow_direction must be cardinal or diagonal")
    if direction == (0, 0):
        raise ValueError("flow_direction must be non-zero")
    return direction


def _normalize_region_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("region_id must be a positive integer")
    return value


def _normalize_id(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("id must be a non-empty string")
    return value


@dataclass(frozen=True)
class WaterBody:
    """A stable, explicitly authored body of water on geography cells."""

    id: str
    kind: WaterBodyKind
    cell_refs: tuple[CellRef, ...]
    navigable: bool
    region_id: int | None = None
    flow_direction: FlowDirection | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _normalize_id(self.id))
        object.__setattr__(self, "kind", _normalize_kind(self.kind))

        if not isinstance(self.cell_refs, (list, tuple)) or not self.cell_refs:
            raise ValueError("cell_refs must be non-empty")
        normalized_cells = tuple(
            _normalize_cell_ref(cell_ref, "cell_refs") for cell_ref in self.cell_refs
        )
        if len(set(normalized_cells)) != len(normalized_cells):
            raise ValueError("cell_refs must not contain duplicates")
        object.__setattr__(self, "cell_refs", normalized_cells)

        if not isinstance(self.navigable, bool):
            raise ValueError("navigable must be a boolean")

        if self.region_id is not None:
            object.__setattr__(self, "region_id", _normalize_region_id(self.region_id))

        if self.kind is WaterBodyKind.RIVER:
            if self.flow_direction is None:
                raise ValueError("river requires flow_direction")
            object.__setattr__(self, "flow_direction", _normalize_flow_direction(self.flow_direction))
        elif self.flow_direction is not None:
            raise ValueError("lake and sea cannot declare flow_direction")


def _normalize_dimension(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _normalize_matrix(value: Any, *, width: int, height: int, field_name: str) -> list[list[Any]]:
    if not isinstance(value, (list, tuple)) or len(value) != height:
        raise ValueError(f"{field_name} must have {height} rows")
    rows: list[list[Any]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != width:
            raise ValueError(f"{field_name} rows must have width {width}")
        rows.append(list(row))
    return rows


def _normalize_terrain(value: Any) -> TileType:
    if isinstance(value, TileType):
        terrain = value
    elif isinstance(value, str):
        try:
            terrain = TileType(value.lower())
        except ValueError:
            try:
                terrain = TileType[value.upper()]
            except KeyError as exc:
                raise ValueError(f"invalid terrain TileType: {value}") from exc
    else:
        raise ValueError("terrain must contain TileType values")

    if terrain in _SEMANTIC_TILE_TYPES:
        raise ValueError(f"{terrain.value} is a semantic site, not physical terrain")
    return terrain


def _normalize_elevation(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("elevation must be a finite number")
    normalized = float(value)
    if (
        not math.isfinite(normalized)
        or normalized < MIN_ELEVATION_METERS
        or normalized > MAX_ELEVATION_METERS
    ):
        raise ValueError(
            "elevation must be a finite number between -12000 and 10000 metres"
        )
    return normalized


@dataclass
class GeographyLayer:
    """Validated physical terrain, elevation, and water for one map grid."""

    width: int
    height: int
    terrain_rows: list[list[TileType]]
    elevation_rows: list[list[float]]
    water_bodies: list[WaterBody]

    def __post_init__(self) -> None:
        self.width = _normalize_dimension(self.width, "width")
        self.height = _normalize_dimension(self.height, "height")

        terrain_rows = _normalize_matrix(
            self.terrain_rows,
            width=self.width,
            height=self.height,
            field_name="terrain_rows",
        )
        self.terrain_rows = [
            [_normalize_terrain(value) for value in row] for row in terrain_rows
        ]

        elevation_rows = _normalize_matrix(
            self.elevation_rows,
            width=self.width,
            height=self.height,
            field_name="elevation_rows",
        )
        self.elevation_rows = [
            [_normalize_elevation(value) for value in row] for row in elevation_rows
        ]

        if not isinstance(self.water_bodies, (list, tuple)):
            raise ValueError("water_bodies must be a list")
        normalized_bodies: list[WaterBody] = []
        seen_ids: set[str] = set()
        for body in self.water_bodies:
            if not isinstance(body, WaterBody):
                raise ValueError("water_bodies must contain WaterBody instances")
            if body.id in seen_ids:
                raise ValueError(f"duplicate water body id: {body.id}")
            seen_ids.add(body.id)
            for cell_ref in body.cell_refs:
                if not self.is_in_bounds(*cell_ref):
                    raise ValueError(f"water body cell is outside the geography layer: {cell_ref}")
                terrain = self.terrain_at(*cell_ref)
                if terrain not in _WATER_TERRAIN_TYPES:
                    raise ValueError(
                        f"water body cell {cell_ref} requires water, sea, or marsh terrain"
                    )
            normalized_bodies.append(body)
        self.water_bodies = sorted(normalized_bodies, key=lambda body: body.id)

    def is_in_bounds(self, x: int, y: int) -> bool:
        return (
            isinstance(x, int)
            and not isinstance(x, bool)
            and isinstance(y, int)
            and not isinstance(y, bool)
            and 0 <= x < self.width
            and 0 <= y < self.height
        )

    def terrain_at(self, x: int, y: int) -> TileType | None:
        if not self.is_in_bounds(x, y):
            return None
        return self.terrain_rows[y][x]

    def elevation_at(self, x: int, y: int) -> float | None:
        if not self.is_in_bounds(x, y):
            return None
        return self.elevation_rows[y][x]
