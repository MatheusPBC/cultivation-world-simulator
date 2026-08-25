from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = PROJECT_ROOT / "static" / "game_configs" / "maps"


def migrate_save_data(
    save_data: dict[str, Any],
    *,
    maps_dir: Path = MAPS_DIR,
    refresh_unmodified_lore: bool = False,
) -> dict[str, Any]:
    """Return a migrated copy of a save without modifying the input object."""
    migrated = copy.deepcopy(save_data)
    snapshot = migrated.get("world", {}).get("map_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("Save does not contain world.map_snapshot")
    if int(snapshot.get("schema_version", 0) or 0) != 2:
        raise ValueError("Expected map snapshot schema version 2")

    preset_id = str(snapshot.get("preset_id") or "classic")
    map_path = maps_dir / preset_id / "map.json"
    if not map_path.exists():
        raise ValueError(f"Unknown map preset: {preset_id}")

    map_source = json.loads(map_path.read_text(encoding="utf-8"))
    if int(map_source.get("schema_version", 0) or 0) != 3:
        raise ValueError(f"Map preset {preset_id} is not schema version 3")

    source_overrides = map_source.get("region_overrides")
    if not isinstance(source_overrides, dict):
        raise ValueError(f"Map preset {preset_id} has invalid region_overrides")

    old_overrides = snapshot.get("region_overrides") or {}
    if not isinstance(old_overrides, dict):
        raise ValueError("Map snapshot has invalid region_overrides")
    unknown_region_ids = sorted(set(old_overrides) - set(source_overrides))
    if unknown_region_ids:
        raise ValueError(f"Map snapshot contains unknown override regions: {', '.join(unknown_region_ids)}")

    snapshot["schema_version"] = 3
    snapshot["region_overrides"] = {
        region_id: copy.deepcopy(source_overrides[region_id])
        for region_id in old_overrides
    }

    if refresh_unmodified_lore:
        lore_snapshot = migrated.get("world", {}).get("world_lore_snapshot") or {}
        if str(lore_snapshot.get("lore_text") or "").strip():
            raise ValueError("Cannot refresh a customized world_lore_snapshot")
        if lore_snapshot.get("stats") or lore_snapshot.get("rewrite_config"):
            raise ValueError("Cannot refresh a world_lore_snapshot with rewrite metadata")
        migrated["world"]["world_lore_snapshot"] = {}
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a copied save map snapshot from schema v2 to v3.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--refresh-unmodified-lore",
        action="store_true",
        help="drop a non-customized locale snapshot so it is rebuilt in the selected content locale",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        parser.error("input and output must be different files; in-place migration is not allowed")
    if output_path.exists():
        parser.error(f"output already exists: {output_path}")

    save_data = json.loads(input_path.read_text(encoding="utf-8"))
    migrated = migrate_save_data(save_data, refresh_unmodified_lore=args.refresh_unmodified_lore)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(migrated, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
