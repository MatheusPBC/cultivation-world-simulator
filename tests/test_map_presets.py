from pathlib import Path

import polib

from src.run.load_map import load_cultivation_world_map
from src.run.map_presets import list_map_presets
from src.run.map_snapshot import load_map_from_snapshot, serialize_map_snapshot
from src.run.map_source import read_map_source
from tools.map_presets.quality_audit import audit_landmarks
from src.classes.core.world import World
from src.server.runtime.session import GameSessionRuntime, create_default_game_state
from src.server.services.game_queries import get_world_map
from src.systems.time import Month, Year, create_month_stamp
from src.classes.language import language_manager
from src.i18n import reload_translations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_preset_tile_rows(map_id: str) -> list[list[str]]:
    source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
    return [[tile.value for tile in row] for row in source.geography.terrain_rows]


def _count_pair_edges(tile_rows: list[list[str]], pair: set[str]) -> int:
    height = len(tile_rows)
    width = len(tile_rows[0]) if height else 0
    count = 0
    for y, row in enumerate(tile_rows):
        for x, tile_name in enumerate(row):
            if x + 1 < width and {tile_name, row[x + 1]} == pair:
                count += 1
            if y + 1 < height and {tile_name, tile_rows[y + 1][x]} == pair:
                count += 1
    return count


def _count_checkerboards(tile_rows: list[list[str]], pair: set[str]) -> int:
    height = len(tile_rows)
    width = len(tile_rows[0]) if height else 0
    count = 0
    for y in range(height - 1):
        for x in range(width - 1):
            top_left = tile_rows[y][x]
            top_right = tile_rows[y][x + 1]
            bottom_left = tile_rows[y + 1][x]
            bottom_right = tile_rows[y + 1][x + 1]
            if (
                {top_left, top_right, bottom_left, bottom_right} == pair
                and top_left == bottom_right
                and top_right == bottom_left
            ):
                count += 1
    return count


def _max_edge_run(tile_rows: list[list[str]], x: int = 0) -> int:
    max_run = 0
    current_tile = None
    current_run = 0
    for row in tile_rows:
        tile_name = row[x]
        if tile_name == current_tile:
            current_run += 1
        else:
            max_run = max(max_run, current_run)
            current_tile = tile_name
            current_run = 1
    return max(max_run, current_run)


def test_official_map_presets_load_with_uniform_size():
    presets = list_map_presets()
    assert [preset.id for preset in presets] == ["classic", "island_seas", "mountain_frontier"]

    region_sets = []
    for preset in presets:
        game_map = load_cultivation_world_map(preset.id)
        assert game_map.width == 84
        assert game_map.height == 60
        assert game_map.map_id == preset.id
        assert game_map.map_name == preset.name
        assert game_map.preset_version == preset.version
        assert game_map.regions
        region_sets.append(set(game_map.regions))

    assert all(region_set == region_sets[0] for region_set in region_sets)


def test_physical_geography_covers_region_terrain_and_landmarks():
    game_map = load_cultivation_world_map("classic")

    assert game_map.geography is not None
    source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / "classic" / "map.json")
    for region_id, expected_terrain in ((112, "farm"), (201, "mountain")):
        coordinate = next(
            (x, y)
            for y, row in enumerate(source.region_rows)
            for x, value in enumerate(row)
            if value == region_id
        )
        assert game_map.get_terrain(*coordinate).value == expected_terrain
    assert game_map.landmarks[201]["asset"] == "cave"
    assert game_map.landmarks[301]["asset"] == "city_301"
    assert game_map.landmarks[401]["asset"] == "sect_1"


def test_official_map_visual_shape_guards():
    island_rows = _read_preset_tile_rows("island_seas")
    assert _count_pair_edges(island_rows, {"island", "plain"}) <= 200
    assert _count_checkerboards(island_rows, {"island", "plain"}) == 0

    mountain_rows = _read_preset_tile_rows("mountain_frontier")
    assert _max_edge_run(mountain_rows, x=0) <= 20


def test_official_map_core_quality_guards():
    for map_id in ["classic", "mountain_frontier"]:
        source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
        water_bodies = source.geography.water_bodies
        assert any(body.kind == "river" and body.region_id == 106 for body in water_bodies)
        assert any(body.kind == "sea" and body.region_id == 105 for body in water_bodies)

    mountain_source = read_map_source(
        PROJECT_ROOT / "static" / "game_configs" / "maps" / "mountain_frontier" / "map.json"
    )
    landmark_issues = [
        issue
        for issue in audit_landmarks("mountain_frontier", mountain_source.region_rows, mountain_source.landmarks)
        if issue.region_id == 406
    ]
    assert "landmark_poor_fit" not in {issue.code for issue in landmark_issues}


def test_official_presets_have_grounded_infrastructure_sites():
    expected_kinds = {"classic": "farm", "island_seas": "irrigation", "mountain_frontier": "mine"}
    for map_id, expected_kind in expected_kinds.items():
        source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
        sites = getattr(source, "infrastructure_sites", ())
        assert sites, map_id
        assert any(getattr(site, "kind", None) == expected_kind for site in sites)

    classic = read_map_source(
        PROJECT_ROOT / "static" / "game_configs" / "maps" / "classic" / "map.json"
    )
    bridge = next(
        site
        for site in classic.infrastructure_sites
        if site.id == "classic-tianhe-bridge-301-405"
    )
    assert bridge.route_ids == ("classic-301-405",)
    assert bridge.water_body_ids == ("classic-tianhe",)
    assert bridge.cell_refs == ((45, 24),)

    loaded_classic = load_cultivation_world_map("classic")
    assert loaded_classic.get_route_operational_capacity("classic-301-405") == 110.4
    loaded_classic.update_infrastructure_site_runtime(
        bridge.id,
        integrity=0.5,
        last_event_id="test:bridge-damage",
    )
    assert loaded_classic.get_route_operational_capacity("classic-301-405") == 55.2


def test_map_snapshot_round_trip_restores_tiles_and_regions():
    game_map = load_cultivation_world_map("island_seas")
    snapshot = serialize_map_snapshot(game_map)

    assert snapshot["schema_version"] == 5
    assert snapshot["preset_id"] == "island_seas"
    assert snapshot["map_name"] == game_map.map_name
    assert snapshot["width"] == 84
    assert snapshot["height"] == 60
    assert "wilderness_tile" not in snapshot
    assert "region_tile_overrides" not in snapshot
    assert snapshot["geography"]["terrain_rows"] == [
        [tile.value for tile in row]
        for row in game_map.geography.terrain_rows
    ]
    assert snapshot["geography"]["elevation_rows"] == game_map.geography.elevation_rows
    assert len(snapshot["region_rows"]) == 60
    assert snapshot["landmarks"]
    assert snapshot["infrastructure_sites"]

    restored = load_map_from_snapshot(snapshot)
    assert restored.map_id == "island_seas"
    assert restored.map_name == game_map.map_name
    assert restored.width == game_map.width
    assert restored.height == game_map.height
    assert set(restored.regions) == set(game_map.regions)
    assert restored.geography is not None
    assert restored.geography.terrain_rows == game_map.geography.terrain_rows
    assert restored.geography.elevation_rows == game_map.geography.elevation_rows
    assert restored.geography.water_bodies == game_map.geography.water_bodies

    for y in range(game_map.height):
        for x in range(game_map.width):
            original_tile = game_map.get_tile(x, y)
            restored_tile = restored.get_tile(x, y)
            assert restored_tile.type == original_tile.type
            assert (restored_tile.region.id if restored_tile.region else -1) == (
                original_tile.region.id if original_tile.region else -1
            )

    assert restored.get_water_bodies_at(1, 0) == game_map.get_water_bodies_at(1, 0)
    assert restored.get_water_bodies_touching_region(106) == game_map.get_water_bodies_touching_region(106)
    assert restored.get_neighboring_region_ids(101) == game_map.get_neighboring_region_ids(101)
    assert restored.get_river_relation(106, 107) == game_map.get_river_relation(106, 107)
    assert [site.to_dict() for site in restored.infrastructure_sites.values()] == snapshot["infrastructure_sites"]


def test_region_first_map_loads_wilderness_and_landmarks():
    game_map = load_cultivation_world_map("island_seas")
    source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / "island_seas" / "map.json")

    wilderness_coord = None
    for y, row in enumerate(source.region_rows):
        for x, region_id in enumerate(row):
            if region_id == -1:
                wilderness_coord = (x, y)
                break
        if wilderness_coord:
            break

    assert wilderness_coord is not None
    unclaimed_tile = game_map.get_tile(*wilderness_coord)
    assert unclaimed_tile.region is None
    assert unclaimed_tile.type.value == source.geography.terrain_rows[wilderness_coord[1]][wilderness_coord[0]].value

    assert game_map.landmarks[301]["asset"] == "city_301"
    assert "x" in game_map.landmarks[301]
    assert "y" in game_map.landmarks[301]


def test_public_map_data_uses_renderable_tile_types():
    for preset in list_map_presets():
        runtime = GameSessionRuntime(create_default_game_state())
        world = World(
            map=load_cultivation_world_map(preset.id),
            month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        )
        runtime.set_world_and_sim(world, None)

        response = get_world_map(runtime, sects_by_id={}, render_config={})
        tile_types = {tile_type for row in response["data"] for tile_type in row}

        assert "CAVE" not in tile_types
        assert "RUIN" not in tile_types
        assert "SECT" not in tile_types


def test_public_map_region_coordinates_use_landmarks():
    runtime = GameSessionRuntime(create_default_game_state())
    game_map = load_cultivation_world_map("island_seas")
    world = World(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    )
    runtime.set_world_and_sim(world, None)

    response = get_world_map(runtime, sects_by_id={}, render_config={})
    city = next(region for region in response["regions"] if region["id"] == 301)

    assert city["x"] == game_map.landmarks[301]["x"]
    assert city["y"] == game_map.landmarks[301]["y"]


def test_official_map_region_overrides_use_stable_locale_ids():
    expected_ids: set[str] = set()
    for map_id in ("classic", "island_seas", "mountain_frontier"):
        source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
        for region_id, override in source.region_overrides.items():
            prefix = f"MAP_REGION_{map_id.upper()}_{region_id}"
            assert override.name_id == f"{prefix}_NAME"
            assert override.desc_id == f"{prefix}_DESC"
            expected_ids.update((override.name_id, override.desc_id))

    assert len(expected_ids) == 132
    for locale in ("en-US", "pt-BR"):
        po = polib.pofile(str(PROJECT_ROOT / "static" / "locales" / locale / "modules" / "map_regions.po"))
        translations = {entry.msgid: entry.msgstr for entry in po if not entry.obsolete}
        assert set(translations) == expected_ids
        assert all(value.strip() for value in translations.values())


def test_public_map_preserves_world_lore_rewrite_after_localized_snapshot_load(tmp_path, monkeypatch):
    from src import i18n
    from src.classes.world_lore_snapshot import apply_world_lore_snapshot

    po = polib.pofile(
        str(PROJECT_ROOT / "static" / "locales" / "pt-BR" / "modules" / "map_regions.po")
    )
    mo_path = tmp_path / "pt-BR" / "LC_MESSAGES" / "messages.mo"
    mo_path.parent.mkdir(parents=True)
    po.save_as_mofile(str(mo_path))

    original_language = str(language_manager)
    monkeypatch.setattr(i18n, "_get_locale_dir", lambda: tmp_path)
    try:
        language_manager.set_language("pt-BR")
        reload_translations()
        original_map = load_cultivation_world_map("classic")
        game_map = load_map_from_snapshot(serialize_map_snapshot(original_map))
        assert game_map.regions[101].name == "Planícies do Sudeste"

        world = World(map=game_map, month_stamp=create_month_stamp(Year(1), Month.JANUARY))
        apply_world_lore_snapshot(
            world,
            {
                "schema_version": 2,
                "regions": {
                    "101": {
                        "name": "Vale das Cinzas Renascidas",
                        "desc": "A antiga planície foi reescrita pela história deste mundo.",
                    }
                },
            },
        )
        runtime = GameSessionRuntime(create_default_game_state())
        runtime.set_world_and_sim(world, None)
        response = get_world_map(runtime, sects_by_id={}, render_config={})
    finally:
        language_manager.set_language(original_language)
        reload_translations()

    region = next(region for region in response["regions"] if region["id"] == 101)
    assert region["name"] == "Vale das Cinzas Renascidas"
    assert region["desc"] == "A antiga planície foi reescrita pela história deste mundo."


def test_map_presets_are_localized():
    original_language = str(language_manager)
    try:
        language_manager.set_language("en-US")
        reload_translations()
        presets = {preset.id: preset.to_dict() for preset in list_map_presets()}
        assert presets["classic"]["name"] == "Central Nine Provinces"
        assert presets["island_seas"]["name"] == "Azure Isles"
        assert presets["mountain_frontier"]["size_label"] == "Medium"
    finally:
        language_manager.set_language(original_language)
        reload_translations()


def test_map_presets_can_be_localized_for_specific_locale_without_switching_global_language():
    original_language = str(language_manager)
    try:
        language_manager.set_language("zh-CN")
        reload_translations()

        presets = {preset.id: preset.to_dict(locale="fr-FR") for preset in list_map_presets()}

        assert str(language_manager) == "zh-CN"
        assert presets["classic"]["name"] == "Les Neuf Provinces Centrales"
        assert presets["island_seas"]["desc"] == (
            "Les mers ouvertes divisent les îles, donnant au monde un sentiment d'espace plus large."
        )
        assert presets["mountain_frontier"]["size_label"] == "Moyen"
    finally:
        language_manager.set_language(original_language)
        reload_translations()
