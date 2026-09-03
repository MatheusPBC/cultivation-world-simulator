from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Mapping, Optional

from src.classes.environment.tile import Tile, TileType
from src.classes.environment.route import Route
from src.classes.environment.sect_region import SectRegion
from src.classes.environment.geography import GeographyLayer, WaterBody
from src.classes.environment.infrastructure import InfrastructureSite

if TYPE_CHECKING:
    from src.classes.environment.region import Region


class Map():
    """
    通过dict记录position 到 tile。
    """
    def __init__(
        self,
        width: int,
        height: int,
        map_id: str = "classic",
        map_name: str = "",
        preset_version: int = 1,
    ):
        self.tiles = {}
        self.width = width
        self.height = height
        self.map_id = map_id
        self.map_name = map_name
        self.preset_version = preset_version
        self.landmarks: dict[int, dict[str, object]] = {}
        self.region_overrides: dict[int, dict[str, object]] = {}
        self.region_formations: dict[int, dict[str, object]] = {}
        # 维护“最终归属”的每个 region 的坐标集合（由分配流程写入）
        # key: region.id, value: list[(x, y)]
        self.region_cors: dict[int, list[tuple[int, int]]] = {}
        
        # 区域字典，由外部加载器 (load_map.py) 填充
        # 只维护 regions[id] 作为唯一的 source of truth，按名称查找通过遍历实现
        self.regions = {}
        self.sect_regions = {}
        
        # 分类索引由加载器按需填充；regions 仍是唯一语义真源。
        self.normal_regions = {}
        self.cultivate_regions = {}
        self.city_regions = {}
        self.routes: dict[str, Route] = {}
        self.infrastructure_sites: dict[str, InfrastructureSite] = {}
        self._infrastructure_site_updates: list[dict[str, Any]] = []
        self.geography = GeographyLayer(
            width=width,
            height=height,
            terrain_rows=[[TileType.PLAIN for _ in range(width)] for _ in range(height)],
            elevation_rows=[[0.0 for _ in range(width)] for _ in range(height)],
            water_bodies=[],
        )

    def set_geography(self, geography: GeographyLayer) -> None:
        """Install the map-owned physical geography layer."""
        if not isinstance(geography, GeographyLayer):
            raise TypeError("geography must be a GeographyLayer")
        if geography.width != self.width or geography.height != self.height:
            raise ValueError("geography dimensions must match the map")
        self.geography = geography

    def get_terrain(self, x: int, y: int) -> TileType | None:
        return self.geography.terrain_at(x, y)

    def get_elevation(self, x: int, y: int) -> float | None:
        return self.geography.elevation_at(x, y)

    def get_water_bodies_at(self, x: int, y: int) -> list[WaterBody]:
        if not self.geography.is_in_bounds(x, y):
            return []
        return [body for body in self.geography.water_bodies if (x, y) in body.cell_refs]

    def _region_coordinates(self, region_id: int) -> set[tuple[int, int]]:
        if isinstance(region_id, bool) or not isinstance(region_id, int):
            return set()

        coordinates = self.region_cors.get(region_id)
        if coordinates:
            return {
                normalized
                for coordinate in coordinates
                if (normalized := self._normalize_map_coordinate(coordinate)) is not None
            }

        region = self.regions.get(region_id)
        if region is not None:
            coordinates = getattr(region, "cors", None) or []
            return {
                normalized
                for coordinate in coordinates
                if (normalized := self._normalize_map_coordinate(coordinate)) is not None
            }

        return set()

    def get_region_coordinates(self, region_id: int) -> set[tuple[int, int]]:
        """Return the validated physical footprint of a semantic region."""
        return self._region_coordinates(region_id)

    def get_water_bodies_touching_region(self, region_id: int) -> list[WaterBody]:
        """Return bodies overlapping or cardinally adjacent to a region."""
        region_cells = self._region_coordinates(region_id)
        touching: list[WaterBody] = []
        for body in self.geography.water_bodies:
            if self._water_body_touches_region(body, region_id, region_cells):
                touching.append(body)
        return touching

    @staticmethod
    def _water_body_touches_region(
        body: WaterBody,
        region_id: int,
        region_cells: set[tuple[int, int]],
    ) -> bool:
        if body.region_id == region_id:
            return True
        return any(
            cell in region_cells
            or any(
                (cell[0] + dx, cell[1] + dy) in region_cells
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            for cell in body.cell_refs
        )

    def get_neighboring_region_ids(self, region_id: int) -> list[int]:
        """Return region IDs sharing an orthogonal map edge with a region."""
        region_cells = self._region_coordinates(region_id)
        if not region_cells:
            return []

        coordinate_to_region: dict[tuple[int, int], int] = {}
        for candidate_id, coordinates in self.region_cors.items():
            for coordinate in coordinates:
                if normalized := self._normalize_map_coordinate(coordinate):
                    coordinate_to_region[normalized] = candidate_id
        for candidate_id, region in self.regions.items():
            for coordinate in getattr(region, "cors", []) or []:
                if normalized := self._normalize_map_coordinate(coordinate):
                    coordinate_to_region.setdefault(normalized, candidate_id)
        for coordinate, tile in self.tiles.items():
            if tile.region is not None:
                coordinate_to_region.setdefault(coordinate, tile.region.id)

        neighboring_ids: set[int] = set()
        for x, y in region_cells:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                candidate_id = coordinate_to_region.get((x + dx, y + dy))
                if candidate_id is not None and candidate_id != region_id:
                    neighboring_ids.add(candidate_id)
        return sorted(neighboring_ids)

    def _normalize_map_coordinate(self, coordinate: object) -> tuple[int, int] | None:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            return None
        x, y = coordinate
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
            or not self.is_in_bounds(x, y)
        ):
            return None
        return (x, y)

    @staticmethod
    def _river_cells_for_region(
        body: WaterBody,
        region_cells: set[tuple[int, int]],
    ) -> set[tuple[int, int]]:
        intersections = set(body.cell_refs).intersection(region_cells)
        if intersections:
            return intersections
        return {
            cell
            for cell in body.cell_refs
            if any(
                (cell[0] + dx, cell[1] + dy) in region_cells
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
        }

    def get_river_relation(self, region_a: int, region_b: int) -> str | None:
        """Return ``upstream`` or ``downstream`` for two regions on one river.

        Flow is represented as a grid vector. The relation is accepted only
        when the explicit river cells occupied by or adjacent to each region
        form non-overlapping ranges along that vector. Multiple rivers must
        agree; ambiguous evidence returns ``None``.
        """
        if region_a == region_b:
            return None
        region_a_cells = self._region_coordinates(region_a)
        region_b_cells = self._region_coordinates(region_b)
        if not region_a_cells or not region_b_cells:
            return None
        relations: set[str] = set()
        for body in self.geography.water_bodies:
            if body.kind.value != "river" or body.flow_direction is None:
                continue
            river_cells_a = self._river_cells_for_region(body, region_a_cells)
            river_cells_b = self._river_cells_for_region(body, region_b_cells)
            if not river_cells_a or not river_cells_b:
                continue
            dx, dy = body.flow_direction
            projections_a = {x * dx + y * dy for x, y in river_cells_a}
            projections_b = {x * dx + y * dy for x, y in river_cells_b}
            if max(projections_a) < min(projections_b):
                relations.add("upstream")
            elif max(projections_b) < min(projections_a):
                relations.add("downstream")
            else:
                return None

        if len(relations) == 1:
            return relations.pop()
        return None

    def update_sect_regions(self) -> None:
        """根据当前 self.regions 动态刷新宗门总部区域字典。"""
        self.sect_regions = {rid: r for rid, r in self.regions.items() if isinstance(r, SectRegion)}

    def set_routes(self, routes: Iterable[Route]) -> None:
        """Replace the explicit route registry after validating stable IDs."""
        route_registry: dict[str, Route] = {}
        for route in routes:
            if not isinstance(route, Route):
                raise TypeError("routes must contain Route instances")
            if route.id in route_registry:
                raise ValueError(f"Duplicate route id: {route.id}")
            route_registry[route.id] = route
        self.routes = route_registry

    def set_infrastructure_sites(self, sites: Iterable[InfrastructureSite]) -> None:
        """Replace the map-owned site registry after validating spatial references."""
        site_registry: dict[str, InfrastructureSite] = {}
        water_bodies = {body.id: body for body in self.geography.water_bodies}
        for site in sites:
            if not isinstance(site, InfrastructureSite):
                raise TypeError("infrastructure_sites must contain InfrastructureSite instances")
            if site.id in site_registry:
                raise ValueError(f"Duplicate infrastructure site id: {site.id}")
            if any(not self.is_in_bounds(*cell) for cell in site.cell_refs):
                raise ValueError(f"Infrastructure site {site.id} has a cell outside map bounds")
            missing_regions = set(site.region_ids) - set(self.regions)
            if missing_regions:
                missing = ", ".join(str(region_id) for region_id in sorted(missing_regions))
                raise ValueError(
                    f"Infrastructure site {site.id} references unknown region ids: {missing}"
                )
            site_region_ids = set(site.region_ids)
            for cell in site.cell_refs:
                tile = self.tiles.get(cell)
                cell_region_id = tile.region.id if tile is not None and tile.region is not None else None
                if cell_region_id is None:
                    cell_region_id = next(
                        (
                            region_id
                            for region_id in site_region_ids
                            if cell in self._region_coordinates(region_id)
                        ),
                        None,
                    )
                if cell_region_id not in site_region_ids:
                    raise ValueError(
                        f"Infrastructure site {site.id} cell {cell} does not belong to one of its regions"
                    )

            for route_id in site.route_ids:
                route = self.routes.get(route_id)
                if route is None:
                    raise ValueError(
                        f"Infrastructure site {site.id} references unknown route: {route_id}"
                    )
                if not set(route.endpoint_region_ids).issubset(site_region_ids):
                    raise ValueError(
                        f"Infrastructure site {site.id} route {route_id} is not connected to its regions"
                    )

            site_cells = set(site.cell_refs)
            for water_body_id in site.water_body_ids:
                body = water_bodies.get(water_body_id)
                if body is None:
                    raise ValueError(
                        f"Infrastructure site {site.id} references unknown water body: {water_body_id}"
                    )
                if not any(
                    cell in site_cells
                    or any(
                        (cell[0] + dx, cell[1] + dy) in site_cells
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                    )
                    for cell in body.cell_refs
                ):
                    raise ValueError(
                        f"Infrastructure site {site.id} water body {water_body_id} does not touch its cells"
                    )
            site_registry[site.id] = site

        self.infrastructure_sites = site_registry
        self._infrastructure_site_updates.clear()

    def update_infrastructure_site_runtime(
        self,
        site_id: str,
        *,
        integrity: float | None = None,
        enabled: bool | None = None,
        last_event_id: str | None = None,
        track_update: bool = True,
    ) -> bool:
        """Update site runtime state and optionally queue its canonical upsert."""
        site = self.infrastructure_sites.get(site_id)
        if site is None:
            raise KeyError(f"unknown infrastructure site: {site_id}")
        changed = site.update_runtime(
            integrity=integrity,
            enabled=enabled,
            last_event_id=last_event_id,
        )
        if changed and track_update:
            self._infrastructure_site_updates.append(
                {"op": "upsert", "id": site.id, "site": site.to_dict()}
            )
        return changed

    def get_infrastructure_site_updates(self) -> list[dict[str, Any]]:
        """Return pending projection updates without acknowledging delivery."""
        return list(self._infrastructure_site_updates)

    def acknowledge_infrastructure_site_updates(self) -> None:
        """Clear updates only after the websocket broadcast succeeds."""
        self._infrastructure_site_updates.clear()

    def get_routes_between(
        self,
        region_a: int,
        region_b: int,
        *,
        resource_id: str | None = None,
    ) -> list[Route]:
        """Return enabled explicit routes between two regions in stable order."""
        if region_a == region_b:
            return []
        routes = [
            route
            for route in self.routes.values()
            if route.enabled
            and route.connects(region_a, region_b)
            and route.allows_resource(resource_id)
        ]
        return sorted(routes, key=lambda route: route.id)

    def get_route_dependency_sites(self, route_id: str) -> list[InfrastructureSite]:
        """Return the explicit infrastructure dependencies of one route."""
        if route_id not in self.routes:
            raise KeyError(f"unknown route: {route_id}")
        return sorted(
            (
                site
                for site in self.infrastructure_sites.values()
                if route_id in site.route_ids
            ),
            key=lambda site: site.id,
        )

    def get_route_operational_capacity(
        self,
        route_id: str,
        *,
        site_runtime_overrides: Mapping[str, tuple[float, bool]] | None = None,
    ) -> float:
        """Derive usable capacity from the route and its declared sites.

        ``Route.capacity`` remains the route-owned nominal capacity. Sites do
        not copy or mutate it: every site that names the route is an explicit
        serial dependency, so the least available dependency is the current
        bottleneck. Overrides support before/after projections without
        mutating canonical state.
        """
        route = self.routes.get(route_id)
        if route is None:
            raise KeyError(f"unknown route: {route_id}")
        if not route.enabled:
            return 0.0

        dependency_factor = 1.0
        for site in self.get_route_dependency_sites(route_id):
            integrity, enabled = (
                site_runtime_overrides[site.id]
                if site_runtime_overrides is not None
                and site.id in site_runtime_overrides
                else (float(site.integrity), bool(site.enabled))
            )
            site.validate_runtime(integrity=integrity, enabled=enabled)
            dependency_factor = min(
                dependency_factor,
                float(integrity) if enabled else 0.0,
            )

        return float(route.capacity) * float(route.quality) * dependency_factor

    def is_in_bounds(self, x: int, y: int) -> bool:
        """
        判断坐标是否在地图边界内。
        """
        return 0 <= x < self.width and 0 <= y < self.height

    def create_tile(self, x: int, y: int, tile_type: TileType):
        self.tiles[(x, y)] = Tile(tile_type, x, y, region=None)

    def get_tile(self, x: int, y: int) -> Tile:
        return self.tiles[(x, y)]

    def get_center_locs(self, locs: list[tuple[int, int]]) -> tuple[int, int]:
        """
        获取locs的中心位置。
        如果几何中心恰好在位置列表中，返回几何中心；
        否则返回距离几何中心最近的实际位置。
        """
        if not locs:
            return (0, 0)
        
        # 分别计算x和y坐标的平均值
        avg_x = sum(loc[0] for loc in locs) // len(locs)
        avg_y = sum(loc[1] for loc in locs) // len(locs)
        center = (avg_x, avg_y)

        # 如果几何中心恰好在位置列表中，直接返回
        if center in locs:
            return center
        
        # 否则找到距离几何中心最近的实际位置
        def distance_squared(loc: tuple[int, int]) -> int:
            """计算到中心点的距离平方（避免开方运算）"""
            return (loc[0] - avg_x) ** 2 + (loc[1] - avg_y) ** 2
        
        return min(locs, key=distance_squared)

    def get_region(self, x: int, y: int) -> Optional['Region']:
        """
        获取一个region。
        """
        return self.tiles[(x, y)].region

    def get_info(self, detailed: bool = False, avatar: object = None) -> dict:
        """
        返回地图信息（dict）。
        avatar: 如果提供，将用于：
               1. 过滤仅返回 avatar.known_regions 中的区域
               2. 计算并在描述中追加从 avatar 当前位置到各区域的距离
        """
        from src.classes.environment.region import NormalRegion, CultivateRegion, CityRegion
        
        known_region_ids = avatar.known_regions if avatar else None
        current_loc = (avatar.pos_x, avatar.pos_y) if avatar else None
        
        def filter_regions(cls):
            return {
                rid: r for rid, r in self.regions.items() 
                if isinstance(r, cls) and (known_region_ids is None or rid in known_region_ids)
            }

        from src.i18n import t

        def build_regions_info(regions_dict) -> list[str]:
            infos = []
            step_len = avatar.move_step_length if avatar else 1
            for r in regions_dict.values():
                base_info = r.get_detailed_info(current_loc, step_len) if detailed else r.get_info(current_loc, step_len)
                infos.append(base_info)
            return infos

        return {
            t("Cultivate Region (can respire to increase cultivation)"): build_regions_info(filter_regions(CultivateRegion)),
            t("Normal Region (can hunt, gather, mine)"): build_regions_info(filter_regions(NormalRegion)),
            t("City Region (can trade)"): build_regions_info(filter_regions(CityRegion)),
            t("Sect Headquarters (sect disciples heal faster here)"): build_regions_info(filter_regions(SectRegion)),
        }
