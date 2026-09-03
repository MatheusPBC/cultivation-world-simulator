import json
from dataclasses import replace

from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.environment.region import NormalRegion, CultivateRegion, CityRegion
from src.classes.environment.city_state import (
    CityState,
    UrbanPopulationGroup,
    UrbanServiceDemand,
)
from src.classes.regional_economy import RegionalEconomyState
from src.classes.environment.sect_region import SectRegion
from src.utils.df import game_configs, get_str, get_int, get_float
from src.classes.essence import EssenceType
from src.classes.core.sect import sects_by_id  # 直接导入已加载的宗门数据
from src.run.map_presets import resolve_map_source_file
from src.run.map_source import (
    MapSource,
    collect_region_coords,
    map_source_to_dict,
    read_map_source,
)
from src.i18n import t

def load_cultivation_world_map(map_id: str | None = None) -> Map:
    """
    从 region-first 地图源加载修仙世界地图。
    读取: maps/<map_id>/map.json
    以及: normal/city/cultivate/sect_region.csv
    """
    preset, source_path = resolve_map_source_file(map_id)
    source = read_map_source(source_path)
    return build_map_from_source(
        source,
        map_id=preset.id,
        map_name=preset.localized_name,
        preset_version=preset.version,
    )


def build_map_from_source(
    source: MapSource,
    *,
    map_id: str | None = None,
    map_name: str = "",
    preset_version: int | None = None,
) -> Map:
    tile_rows = [
        [terrain.value for terrain in row]
        for row in source.geography.terrain_rows
    ]
    game_map = build_map_from_rows(
        tile_rows,
        source.region_rows,
        map_id=map_id or source.map_id,
        map_name=map_name,
        preset_version=preset_version if preset_version is not None else source.version,
        region_overrides={
            region_id: override.to_dict()
            for region_id, override in source.region_overrides.items()
        },
    )
    game_map.set_geography(source.geography)
    game_map.landmarks = {
        region_id: landmark.to_dict()
        for region_id, landmark in source.landmarks.items()
    }
    game_map.region_overrides = {
        region_id: override.to_dict()
        for region_id, override in source.region_overrides.items()
    }
    game_map.set_routes(source.routes)
    game_map.set_infrastructure_sites(source.infrastructure_sites)
    game_map.map_source = map_source_to_dict(source)
    return game_map


def build_map_from_rows(
    tile_rows: list[list[str]],
    region_rows: list[list[str | int]],
    *,
    map_id: str = "classic",
    map_name: str = "",
    preset_version: int = 1,
    region_overrides: dict[int, dict[str, object]] | None = None,
) -> Map:
    """Build a Map from already parsed tile and region matrices."""
    height = len(tile_rows)
    width = len(tile_rows[0]) if height > 0 else 0
    if height <= 0 or width <= 0:
        raise ValueError("Map terrain matrix must not be empty")
    if any(len(row) != width for row in tile_rows):
        raise ValueError("Map terrain rows must have a uniform width")
    if len(region_rows) != height or any(len(row) != width for row in region_rows):
        raise ValueError("Region matrix dimensions must match terrain")
    
    game_map = Map(width=width, height=height, map_id=map_id, map_name=map_name, preset_version=preset_version)
    game_map.region_overrides = region_overrides or {}
    
    # 2. 填充 Tile Type
    for y, row in enumerate(tile_rows):
        for x, tile_name in enumerate(row):
            try:
                t_type = TileType(str(tile_name).lower())
            except ValueError as exc:
                raise ValueError(
                    f"Invalid physical terrain at ({x}, {y}): {tile_name}"
                ) from exc
            if t_type in {TileType.CITY, TileType.CAVE, TileType.RUIN, TileType.SECT}:
                raise ValueError(
                    f"Semantic site cannot be physical terrain at ({x}, {y}): {tile_name}"
                )
            game_map.create_tile(x, y, t_type)
    
    normalized_region_rows: list[list[int]] = []
    for row in region_rows:
        normalized_region_row: list[int] = []
        for val in row:
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError("Region matrix values must be integer region IDs or -1")
            if val != -1 and val <= 0:
                raise ValueError("Region matrix values must be positive region IDs or -1")
            normalized_region_row.append(val)
        normalized_region_rows.append(normalized_region_row)

    region_coords = collect_region_coords(normalized_region_rows)

    # 4. 加载 Region 元数据并创建对象
    _load_and_assign_regions(game_map, region_coords)
    
    # 5. 更新缓存
    game_map.update_sect_regions()
    
    return game_map

def _load_and_assign_regions(game_map: Map, region_coords: dict[int, list[tuple[int, int]]]):
    """
    读取各 region.csv，创建 Region 对象，并分配给 Map 和 Tile
    """
    economy_by_region = _load_city_economy()
    services_by_region = _load_city_services()
    groups_by_region = _load_city_population_groups()

    # 辅助函数：处理 Region 数据
    def process_region_config(df, cls, type_tag):
        for row in df:
            rid = get_int(row, "id")
            
            if rid not in region_coords:
                continue
            
            cors = region_coords[rid]
            
            override = (getattr(game_map, "region_overrides", {}) or {}).get(rid, {})
            name_id = str(override.get("name_id") or "")
            desc_id = str(override.get("desc_id") or "")
            # 构建参数
            params = {
                "id": rid,
                "name": t(name_id) if name_id else get_str(row, "name"),
                "desc": t(desc_id) if desc_id else get_str(row, "desc"),
                "cors": cors,
            }
            
            # 特有字段处理
            if type_tag == "normal":
                params["animal_ids"] = _parse_list(get_str(row, "animal_ids"))
                params["plant_ids"] = _parse_list(get_str(row, "plant_ids"))
                params["lode_ids"] = _parse_list(get_str(row, "lode_ids"))
            elif type_tag == "cultivate":
                params["essence_type"] = EssenceType.from_str(get_str(row, "root_type"))
                params["essence_density"] = get_int(row, "root_density")
                params["sub_type"] = get_str(row, "sub_type") or "cave"
            elif type_tag == "city":
                sell_ids_str = get_str(row, "sell_item_ids")
                if sell_ids_str:
                    try:
                        import ast
                        ids = ast.literal_eval(sell_ids_str)
                        if isinstance(ids, list):
                            params["sell_item_ids"] = ids
                    except Exception as e:
                        print(f"Error parsing sell_item_ids for city {rid}: {e}")
                params["population"] = get_float(row, "initial_population", 80.0)
                params["population_capacity"] = get_float(row, "population_capacity", 120.0)
                params["economy"] = economy_by_region.get(rid, RegionalEconomyState())
                urban_profile = get_str(row, "urban_profile")
                if urban_profile:
                    city_state = CityState.from_profile_dict(
                        json.loads(urban_profile),
                        city_tiles=cors,
                    )
                else:
                    city_state = CityState.default_for_region(cors)
                params["city_state"] = replace(
                    city_state,
                    service_demands=services_by_region.get(rid, ()),
                    population_groups=groups_by_region.get(rid, ()),
                )

            elif type_tag == "sect":
                sect_id = get_int(row, "sect_id")
                params["sect_id"] = sect_id
                
                # 直接从已加载的 sects_by_id 中获取宗门对象
                # 如果找不到对应的 sect_id，默认使用驻地名称作为兜底（防止崩溃），但正常情况下应该能找到
                sect_obj = sects_by_id.get(sect_id)
                if sect_obj:
                    params["sect_name"] = sect_obj.name
                else:
                    params["sect_name"] = get_str(row, "name")
            
            try:
                region_obj = cls(**params)
            except Exception as exc:
                raise ValueError(f"Failed to create region {rid}: {exc}") from exc

            game_map.regions[rid] = region_obj
            game_map.region_cors[rid] = cors
            for rx, ry in cors:
                game_map.tiles[(rx, ry)].region = region_obj

    # 执行加载
    process_region_config(game_configs["normal_region"], NormalRegion, "normal")
    process_region_config(game_configs["city_region"], CityRegion, "city")
    process_region_config(game_configs["cultivate_region"], CultivateRegion, "cultivate")
    process_region_config(game_configs["sect_region"], SectRegion, "sect")

    missing_region_ids = sorted(set(region_coords) - set(game_map.regions))
    if missing_region_ids:
        raise ValueError(
            "Map references regions missing from canonical configuration: "
            + ", ".join(str(region_id) for region_id in missing_region_ids)
        )


def _load_city_economy() -> dict[int, RegionalEconomyState]:
    economy_by_region: dict[int, RegionalEconomyState] = {}
    for row in game_configs.get("city_economy", []):
        region_id = get_int(row, "region_id")
        concept_id = get_str(row, "concept_id")
        if region_id <= 0 or not concept_id:
            continue
        economy = economy_by_region.setdefault(region_id, RegionalEconomyState())
        economy.set_capacity(concept_id, get_float(row, "capacity"))
        economy.set_stock(concept_id, get_float(row, "stock"))
        economy.set_production_rate(concept_id, get_float(row, "production_rate"))
        economy.set_demand_rate(concept_id, get_float(row, "demand_rate"))
        economy.set_access(concept_id, get_float(row, "access"))
        economy.set_dependency(concept_id, get_float(row, "dependency"))
        project_kind = get_str(row, "project_kind")
        if project_kind:
            previous_resource_id = economy.project_resources.get(project_kind)
            if previous_resource_id is not None and previous_resource_id != concept_id:
                raise ValueError(
                    "conflicting project resource mapping "
                    f"for region {region_id} and project kind {project_kind}"
                )
            economy.project_resources[project_kind] = concept_id
    return economy_by_region


def _load_city_services() -> dict[int, tuple[UrbanServiceDemand, ...]]:
    services: dict[int, list[UrbanServiceDemand]] = {}
    for row in game_configs.get("city_service", []):
        region_id = get_int(row, "region_id")
        capability_id = get_str(row, "capability_id")
        if region_id <= 0 or not capability_id:
            continue
        services.setdefault(region_id, []).append(
            UrbanServiceDemand(
                capability_id=capability_id,
                demand_per_population=get_float(row, "demand_per_population"),
            )
        )
    return {
        region_id: tuple(sorted(items, key=lambda item: item.capability_id))
        for region_id, items in services.items()
    }


def _load_city_population_groups() -> dict[int, tuple[UrbanPopulationGroup, ...]]:
    groups: dict[int, list[UrbanPopulationGroup]] = {}
    for row in game_configs.get("city_population_group", []):
        region_id = get_int(row, "region_id")
        group_id = get_str(row, "group_id")
        if region_id <= 0 or not group_id:
            continue
        raw_priorities = get_str(row, "service_priority_weights") or "{}"
        priorities = json.loads(raw_priorities)
        if not isinstance(priorities, dict):
            raise ValueError("city population group priorities must be an object")
        groups.setdefault(region_id, []).append(
            UrbanPopulationGroup(
                id=group_id,
                population_weight=get_float(row, "population_weight"),
                service_priority_weights=tuple(priorities.items()),
            )
        )
    return {
        region_id: tuple(sorted(items, key=lambda item: item.id))
        for region_id, items in groups.items()
    }

def _parse_list(s: str) -> list[int]:
    if not s:
        return []
    res = []
    for x in s.split(","):
        x = x.strip()
        if x:
            try:
                res.append(int(float(x)))
            except (ValueError, TypeError):
                pass
    return res
