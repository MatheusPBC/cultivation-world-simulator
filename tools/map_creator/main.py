import os
import csv
import json
import glob
import sys
import math
from copy import deepcopy
from numbers import Real
from flask import Flask, render_template, jsonify, request, send_from_directory

if os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")) not in sys.path:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.classes.environment.tile import TileType
from src.classes.environment.route import Route
from tools.map_presets.infrastructure_sites import validate_infrastructure_sites

app = Flask(__name__)

# --- 配置路径 ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CONFIG_DIR = os.path.join(BASE_DIR, "static", "game_configs")
OUTPUT_DIR = os.path.dirname(__file__)
DEFAULT_MAP_ID = "classic"
MAPS_DIR = os.path.join(CONFIG_DIR, "maps")

# 新建地图的兜底尺寸；已有地图保存时必须使用 map.json 或请求里的真实尺寸。
MAP_WIDTH = 84
MAP_HEIGHT = 60
MAP_SCHEMA_VERSION = 6
SEMANTIC_TILE_TYPES = {"city", "cave", "ruin", "sect"}
WATER_TERRAIN_TYPES = {"water", "sea", "marsh"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tiles/<path:filename>')
def serve_tile_image(filename):
    return send_from_directory(os.path.join(ASSETS_DIR, "tiles"), filename)

@app.route('/sects/<path:filename>')
def serve_sect_image(filename):
    return send_from_directory(os.path.join(ASSETS_DIR, "sects"), filename)

@app.route('/cities/<path:filename>')
def serve_city_image(filename):
    return send_from_directory(os.path.join(ASSETS_DIR, "cities"), filename)

def get_region_preview(region_id, type_tag, saved_map, sect_id=None, sub_type=None):
    landmarks = saved_map.get("landmarks") or {}
    landmark = landmarks.get(str(region_id), landmarks.get(region_id, {}))
    asset = landmark.get("asset") if isinstance(landmark, dict) else None

    if asset and asset.startswith("city_"):
        return {"asset": asset, "type": "city"}
    if asset and asset.startswith("sect_"):
        return {"asset": asset, "type": "sect"}
    if asset:
        return {"asset": asset, "type": "tile"}
    if type_tag == "sect" and sect_id is not None:
        return {"asset": f"sect_{sect_id}", "type": "sect"}
    if type_tag == "city":
        return {"asset": f"city_{region_id}", "type": "city"}
    if type_tag == "cultivate":
        return {
            "asset": sub_type if sub_type in {"cave", "ruin"} else "cave",
            "type": "tile",
        }

    for cell in (saved_map.get("cells") or {}).values():
        if cell.get("r") == region_id:
            return {"asset": cell.get("t") or "plain", "type": "tile"}
    return {"asset": "plain", "type": "tile"}


def normalize_map_id(raw_map_id=None):
    map_id = str(raw_map_id or DEFAULT_MAP_ID).strip()
    if not map_id:
        return DEFAULT_MAP_ID
    if map_id in {".", ".."} or "/" in map_id or "\\" in map_id:
        raise ValueError(f"Invalid map id: {map_id}")
    return map_id


def get_map_json_path(map_id):
    safe_map_id = normalize_map_id(map_id)
    return os.path.join(MAPS_DIR, safe_map_id, "map.json")


def read_map_json(map_id):
    map_json_path = get_map_json_path(map_id)
    if not os.path.exists(map_json_path):
        return None
    with open(map_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_save_dimensions(data, existing_data=None):
    width = data.get("width") if isinstance(data, dict) else None
    height = data.get("height") if isinstance(data, dict) else None
    if existing_data:
        width = width or existing_data.get("width")
        height = height or existing_data.get("height")
    width = int(width or MAP_WIDTH)
    height = int(height or MAP_HEIGHT)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid map size")
    if existing_data and (width != int(existing_data.get("width", 0)) or height != int(existing_data.get("height", 0))):
        raise ValueError("Existing map dimensions cannot change while preserving physical geography")
    return width, height


def _validate_matrix(rows, *, width, height, field_name):
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError(f"Invalid {field_name} height")
    if any(not isinstance(row, list) or len(row) != width for row in rows):
        raise ValueError(f"Invalid {field_name} width")
    return rows


def _physical_terrain_rows(rows, *, width, height):
    rows = _validate_matrix(rows, width=width, height=height, field_name="geography.terrain_rows")
    normalized = []
    for row in rows:
        normalized_row = []
        for value in row:
            if not isinstance(value, str) or value != value.strip():
                raise ValueError("geography.terrain_rows values must be canonical tile names")
            tile_name = value.strip().lower()
            try:
                TileType(tile_name)
            except ValueError as exc:
                raise ValueError(f"Unknown physical terrain tile: {value}") from exc
            if tile_name in SEMANTIC_TILE_TYPES:
                raise ValueError(f"Semantic tile is forbidden in geography.terrain_rows: {value}")
            normalized_row.append(tile_name)
        normalized.append(normalized_row)
    return normalized


def _validate_elevation_rows(rows, *, width, height):
    rows = _validate_matrix(rows, width=width, height=height, field_name="geography.elevation_rows")
    for row in rows:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError("geography.elevation_rows values must be finite numbers")
            if not math.isfinite(float(value)) or not -12000 <= float(value) <= 10000:
                raise ValueError("geography.elevation_rows values must be between -12000 and 10000")
    return rows


def _validate_water_bodies(bodies, *, width, height, terrain_rows):
    if not isinstance(bodies, list):
        raise ValueError("geography.water_bodies must be a list")
    seen_ids = set()
    for body in bodies:
        if not isinstance(body, dict):
            raise ValueError("Water body must be an object")
        for field_name in ("id", "kind", "cell_refs", "navigable"):
            if field_name not in body:
                raise ValueError(f"Water body missing field: {field_name}")
        body_id = body["id"]
        if not isinstance(body_id, str) or not body_id.strip() or body_id != body_id.strip():
            raise ValueError("Water body id must be a non-empty string")
        if body_id in seen_ids:
            raise ValueError(f"Duplicate water body id: {body_id}")
        if body["kind"] not in {"river", "lake", "sea"}:
            raise ValueError(f"Unknown water body kind: {body['kind']}")
        if not isinstance(body["navigable"], bool):
            raise ValueError(f"Water body {body_id} navigable must be a boolean")
        cells = body["cell_refs"]
        if not isinstance(cells, list) or not cells:
            raise ValueError(f"Water body {body_id} cell_refs must be a non-empty list")
        seen_cells = set()
        for cell in cells:
            if (
                not isinstance(cell, list)
                or len(cell) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in cell)
            ):
                raise ValueError(f"Water body {body_id} cell_refs must contain [x, y] integer pairs")
            x, y = cell
            if not 0 <= x < width or not 0 <= y < height:
                raise ValueError(f"Water body {body_id} cell is out of bounds: {(x, y)}")
            if (x, y) in seen_cells:
                raise ValueError(f"Water body {body_id} contains duplicate cell: {(x, y)}")
            if terrain_rows[y][x] not in WATER_TERRAIN_TYPES:
                raise ValueError(
                    f"Water body {body_id} cell {(x, y)} is incompatible with terrain {terrain_rows[y][x]}"
                )
            seen_cells.add((x, y))
        has_flow = "flow_direction" in body and body["flow_direction"] is not None
        if body["kind"] == "river" and not has_flow:
            raise ValueError(f"River water body {body_id} requires flow_direction")
        if body["kind"] != "river" and has_flow:
            raise ValueError(f"Water body {body_id} cannot declare flow_direction")
        if has_flow:
            flow = body["flow_direction"]
            if (
                not isinstance(flow, list)
                or len(flow) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in flow)
                or any(item not in (-1, 0, 1) for item in flow)
                or not any(item != 0 for item in flow)
            ):
                raise ValueError(
                    f"Water body {body_id} flow_direction must be cardinal or diagonal"
                )
        seen_ids.add(body_id)
    return bodies


def _terrain_rows_from_grid(grid, *, width, height):
    rows = [["plain" for _ in range(width)] for _ in range(height)]
    for cell in grid or []:
        x, y = int(cell["x"]), int(cell["y"])
        if 0 <= x < width and 0 <= y < height and cell.get("t") is not None:
            rows[y][x] = cell["t"]
    return rows


def _existing_schema6(data):
    if not isinstance(data, dict) or int(data.get("schema_version", 0) or 0) != MAP_SCHEMA_VERSION:
        raise ValueError("Map editor requires schema version 6")
    if "wilderness_tile" in data:
        raise ValueError("wilderness_tile is obsolete; use geography.terrain_rows")
    geography = data.get("geography")
    if not isinstance(geography, dict):
        raise ValueError("geography is required")
    if "infrastructure_sites" not in data:
        raise ValueError("infrastructure_sites is required for schema version 6")
    if "routes" not in data:
        raise ValueError("routes is required for schema version 6")
    return geography


def _validate_routes(routes, *, region_rows):
    if not isinstance(routes, list):
        raise ValueError("routes must be a list")
    region_ids = {
        int(region_id)
        for row in region_rows
        for region_id in row
        if isinstance(region_id, int) and not isinstance(region_id, bool) and region_id > 0
    }
    validated = []
    seen_ids = set()
    route_fields = {
        "id", "endpoint_region_ids", "mode", "capacity", "quality",
        "enabled", "allowed_resource_ids",
    }
    for raw_route in routes:
        if not isinstance(raw_route, dict):
            raise ValueError("Route must be an object")
        unknown_fields = set(raw_route) - route_fields
        if unknown_fields:
            raise ValueError(f"Route has unknown fields: {', '.join(sorted(unknown_fields))}")
        route = Route.from_dict(raw_route)
        if route.id in seen_ids:
            raise ValueError(f"Duplicate route id: {route.id}")
        missing_regions = set(route.endpoint_region_ids) - region_ids
        if missing_regions:
            raise ValueError(
                f"Route {route.id} references unknown regions: {sorted(missing_regions)}"
            )
        seen_ids.add(route.id)
        validated.append(route.to_dict())
    return validated


def build_map_payload(data):
    data = data or {}
    if "wildernessTile" in data or "wilderness_tile" in data:
        raise ValueError("wilderness_tile is obsolete; use geography.terrain_rows")
    map_id = normalize_map_id(data.get("mapId"))
    map_dir = os.path.join(MAPS_DIR, map_id)
    existing_data = read_map_json(map_id)
    if existing_data is None and not data.get("allowCreate"):
        raise ValueError(f"Unknown map preset: {map_id}")
    existing_geography = _existing_schema6(existing_data) if existing_data is not None else None
    os.makedirs(map_dir, exist_ok=True)

    width, height = resolve_save_dimensions(data, existing_data)
    region_matrix = [[-1 for _ in range(width)] for _ in range(height)]

    for cell in data.get('grid', []) or []:
        x, y = int(cell['x']), int(cell['y'])
        if 0 <= x < width and 0 <= y < height and cell.get('r') is not None:
            region_id = int(cell['r'])
            if region_id <= 0:
                raise ValueError("Region IDs must be positive integers")
            region_matrix[y][x] = region_id

    requested_geography = data.get("geography") or {}
    terrain_rows = data.get("terrainRows")
    if terrain_rows is None and existing_geography is not None:
        terrain_rows = existing_geography["terrain_rows"]
    elif terrain_rows is None:
        terrain_rows = _terrain_rows_from_grid(data.get("grid"), width=width, height=height)
    terrain_rows = _physical_terrain_rows(terrain_rows, width=width, height=height)

    if existing_geography is not None:
        elevation_rows = deepcopy(existing_geography["elevation_rows"])
        water_bodies = deepcopy(existing_geography["water_bodies"])
    else:
        elevation_rows = deepcopy(requested_geography.get("elevation_rows"))
        water_bodies = deepcopy(requested_geography.get("water_bodies", []))
        if elevation_rows is None:
            elevation_rows = [[0 for _ in range(width)] for _ in range(height)]
    elevation_rows = _validate_elevation_rows(elevation_rows, width=width, height=height)
    water_bodies = _validate_water_bodies(
        water_bodies,
        width=width,
        height=height,
        terrain_rows=terrain_rows,
    )
    routes = _validate_routes(
        deepcopy(data.get("routes", (existing_data or {}).get("routes", []))),
        region_rows=region_matrix,
    )
    infrastructure_sites = data.get(
        "infrastructureSites",
        (existing_data or {}).get("infrastructure_sites", []),
    ) or []
    infrastructure_sites = validate_infrastructure_sites(
        infrastructure_sites,
        width=width,
        height=height,
        region_rows=region_matrix,
        routes=routes,
        water_bodies=water_bodies,
    )

    return {
        "schema_version": MAP_SCHEMA_VERSION,
        "id": map_id,
        "version": int((existing_data or {}).get("version", data.get("version", 1)) or 1),
        "width": width,
        "height": height,
        "region_rows": region_matrix,
        "geography": {
            "terrain_rows": terrain_rows,
            "elevation_rows": elevation_rows,
            "water_bodies": water_bodies,
        },
        "landmarks": data.get("landmarks", (existing_data or {}).get("landmarks", {})) or {},
        "region_overrides": data.get(
            "regionOverrides",
            (existing_data or {}).get("region_overrides", {}),
        ) or {},
        "routes": routes,
        "infrastructure_sites": infrastructure_sites,
    }

@app.route('/api/init')
def init_data():
    """初始化数据：读取Tiles列表和Region配置"""
    try:
        map_id = normalize_map_id(request.args.get("mapId"))
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    
    # 1. 获取所有 Tile 图片名称
    tile_files = glob.glob(os.path.join(ASSETS_DIR, "tiles", "*.png"))
    # 过滤切片 (name_0.png)
    tiles = [
        os.path.splitext(os.path.basename(f))[0]
        for f in tile_files
        if os.path.splitext(os.path.basename(f))[0][-2:] not in ['_0', '_1', '_2', '_3']
        and os.path.splitext(os.path.basename(f))[0] not in SEMANTIC_TILE_TYPES
    ]
    tiles.sort()

    # 2. 获取所有 Sect 图片名称 (sect_1, sect_2, ...)
    sect_files = glob.glob(os.path.join(ASSETS_DIR, "sects", "*.png"))
    sect_tiles_set = set()
    for f in sect_files:
        name = os.path.splitext(os.path.basename(f))[0]
        # Extract base name from slices: sect_1_0 -> sect_1
        if name.startswith('sect_') and '_' in name[5:]:
            # Split by underscore and take first two parts
            parts = name.split('_')
            if len(parts) >= 3:  # sect_1_0
                base_name = f"{parts[0]}_{parts[1]}"  # sect_1
                sect_tiles_set.add(base_name)
    sect_tiles = sorted(list(sect_tiles_set))

    # 3. 获取所有 City 图片名称 (city_301, city_302, ...)
    city_files = glob.glob(os.path.join(ASSETS_DIR, "cities", "*.*"))
    # 过滤非图片
    city_files = [f for f in city_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    city_tiles_map = {} # base_name -> extension (for first slice)
    city_tiles_set = set()
    for f in city_files:
        basename = os.path.basename(f)
        name = os.path.splitext(basename)[0]
        ext = os.path.splitext(basename)[1]
        
        # Extract base name from slices: city_301_0 -> city_301
        if name.startswith('city_') and '_' in name[5:]:
            parts = name.split('_')
            if len(parts) >= 3:  # city_301_0
                base_name = f"{parts[0]}_{parts[1]}"  # city_301
                city_tiles_set.add(base_name)
                # Store extension for the first slice
                if base_name not in city_tiles_map:
                    city_tiles_map[base_name] = f"{base_name}_0{ext}"
    
    city_tiles = sorted(list(city_tiles_set))

    # 4. 读取 sect.csv 建立 sect_id -> sect_name 映射
    sect_id_to_name = {}
    sect_csv_path = os.path.join(CONFIG_DIR, "sect.csv")
    if os.path.exists(sect_csv_path):
        with open(sect_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            data_rows = rows[2:] if len(rows) > 2 else []
            for row in data_rows:
                if len(row) >= 2:
                    try:
                        sid = int(row[0])
                        sname = row[1]
                        sect_id_to_name[sid] = sname
                    except ValueError:
                        continue

    saved_map = load_map_data(map_id)
    region_overrides = saved_map["regionOverrides"] or {}

    # 5. 读取 Region 配置
    regions = []
    
    def parse_csv(filename, id_col, name_col, type_tag, sect_id_col=None, sub_type_col=None):
        path = os.path.join(CONFIG_DIR, filename)
        if not os.path.exists(path):
            print(f"Warning: {path} not found")
            return
        
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
            # 跳过前两行 (header 和 description)
            data_rows = rows[2:] if len(rows) > 2 else []
            
            for row in data_rows:
                if len(row) <= max(id_col, name_col):
                    continue
                try:
                    r_id = int(row[id_col])
                    name = row[name_col]
                    # 简单的 hash 颜色生成
                    color_hash = hash(f"{type_tag}_{r_id}") & 0xFFFFFF
                    color = f"#{color_hash:06x}"
                    
                    # 获取 sect_id (用于宗门)
                    sect_id = None
                    if type_tag == 'sect' and sect_id_col is not None and len(row) > sect_id_col:
                        try:
                            sect_id = int(row[sect_id_col])
                        except ValueError:
                            pass
                    
                    # 获取 sub_type (用于修炼区域)
                    sub_type = None
                    if type_tag == 'cultivate' and sub_type_col is not None and len(row) > sub_type_col:
                        sub_type = row[sub_type_col].strip()
                    
                    preview = get_region_preview(
                        r_id,
                        type_tag,
                        saved_map,
                        sect_id=sect_id,
                        sub_type=sub_type,
                    )
                    override = region_overrides.get(str(r_id), {}) if isinstance(region_overrides, dict) else {}

                    regions.append({
                        "id": r_id,
                        "name": (override.get("name") or name),
                        "desc": override.get("desc") or "",
                        "type": type_tag,
                        "color": color,
                        "previewAsset": preview["asset"],
                        "previewType": preview["type"],
                    })
                except ValueError:
                    continue


    # 读取四种配置
    # normal_region.csv: id=0, name=1
    parse_csv("normal_region.csv", 0, 1, "normal")
    # sect_region.csv: id=0, name=1, sect_id=3
    parse_csv("sect_region.csv", 0, 1, "sect", sect_id_col=3)
    # cultivate_region.csv: id=0, name=1, sub_type=3 (在 desc 后面)
    parse_csv("cultivate_region.csv", 0, 1, "cultivate", sub_type_col=3)
    # city_region.csv: id=0, name=1
    parse_csv("city_region.csv", 0, 1, "city")
    
    # 排序优先级：normal > sect > cultivate > city > 其他
    def sort_priority(r):
        if r['type'] == 'normal':
            return 0
        if r['type'] == 'sect':
            return 1
        if r['type'] == 'cultivate':
            return 2
        if r['type'] == 'city':
            return 3
        return 4
        
    regions.sort(key=lambda x: (sort_priority(x), x['id']))

    return jsonify({
        "width": saved_map["width"],
        "height": saved_map["height"],
        "mapId": saved_map["mapId"],
        "tiles": tiles,
        "sectTiles": sect_tiles,
        "cityTiles": city_tiles,
        "cityTilesMap": city_tiles_map,
        "regions": regions,
        "savedMap": saved_map["cells"],
        "terrainRows": saved_map["terrainRows"],
        "elevationRows": saved_map["elevationRows"],
        "waterBodies": saved_map["waterBodies"],
        "routes": saved_map["routes"],
        "infrastructureSites": saved_map["infrastructureSites"],
        "landmarks": saved_map["landmarks"],
        "regionOverrides": saved_map["regionOverrides"],
    })

@app.route('/api/save', methods=['POST'])
def save_map():
    data = request.json
    try:
        payload = build_map_payload(data or {})
        map_json_path = get_map_json_path(payload["id"])
        with open(map_json_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        
        return jsonify({"status": "success", "message": "Map saved successfully (region-first map.json)"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def load_map_data(map_id=DEFAULT_MAP_ID):
    """Read schema 6 physical geography and rebuild editor grid state."""
    map_id = normalize_map_id(map_id)
    map_json_path = get_map_json_path(map_id)
    
    loaded_data = {} # key: "x,y", value: {t: ..., r: ...}
    landmarks = {}
    region_overrides = {}
    terrain_rows = []
    elevation_rows = []
    water_bodies = []
    routes = []
    infrastructure_sites = []
    width = MAP_WIDTH
    height = MAP_HEIGHT

    if os.path.exists(map_json_path):
        with open(map_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        geography = _existing_schema6(data)
        width = data.get("width", MAP_WIDTH)
        height = data.get("height", MAP_HEIGHT)
        region_rows = data.get("region_rows", [])
        terrain_rows = _physical_terrain_rows(
            geography.get("terrain_rows"), width=int(width), height=int(height)
        )
        elevation_rows = _validate_elevation_rows(
            geography.get("elevation_rows"), width=int(width), height=int(height)
        )
        water_bodies = _validate_water_bodies(
            geography.get("water_bodies"),
            width=int(width),
            height=int(height),
            terrain_rows=terrain_rows,
        )
        routes = _validate_routes(
            deepcopy(data.get("routes", [])),
            region_rows=region_rows,
        )
        infrastructure_sites = validate_infrastructure_sites(
            data.get("infrastructure_sites", []),
            width=int(width),
            height=int(height),
            region_rows=region_rows,
            routes=routes,
            water_bodies=water_bodies,
        )
        region_overrides = data.get("region_overrides", {})
        for y, row in enumerate(region_rows):
            for x, rid in enumerate(row):
                key = f"{x},{y}"
                loaded_data[key] = {"t": terrain_rows[y][x], "r": rid if rid != -1 else None}
        landmarks = data.get("landmarks", {})

    return {
        "mapId": map_id,
        "cells": loaded_data,
        "landmarks": landmarks,
        "regionOverrides": region_overrides,
        "terrainRows": terrain_rows,
        "elevationRows": elevation_rows,
        "waterBodies": water_bodies,
        "routes": routes if os.path.exists(map_json_path) else [],
        "infrastructureSites": infrastructure_sites if os.path.exists(map_json_path) else [],
        "width": width,
        "height": height,
    }

if __name__ == '__main__':
    print("Starting Map Creator at http://127.0.0.1:5000")
    print(f"Assets Dir: {ASSETS_DIR}")
    app.run(debug=True, port=5000)
