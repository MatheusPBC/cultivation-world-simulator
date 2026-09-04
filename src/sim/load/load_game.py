"""
读档功能模块。

顶层函数只负责路径解析、文件 IO、section registry 编排和错误处理。具体恢复
顺序集中在 save/load section registry 中维护。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

import src.utils.config as app_config
from src.sim.save.sections.base import SAVE_SCHEMA_VERSION, LoadContext
from src.sim.save.sections.registry import restore_loaded_game

if TYPE_CHECKING:
    from src.classes.core.sect import Sect
    from src.classes.core.world import World
    from src.sim.simulator import Simulator


def get_events_db_path(save_path: Path, events_db_name: str | None = None) -> Path:
    """
    根据存档路径计算事件数据库路径。

    例如：save_20260105_1423.json -> save_20260105_1423_events.db
    """
    if events_db_name is None and save_path.is_file():
        with open(save_path, "r", encoding="utf-8") as f:
            metadata_name = json.load(f).get("meta", {}).get("events_db")
        if not isinstance(metadata_name, str):
            raise ValueError("Save metadata must name its events database")
        events_db_name = metadata_name
    if events_db_name is None:
        return save_path.with_suffix("").with_name(save_path.stem + "_events.db")
    candidate = Path(events_db_name)
    if candidate.name != events_db_name or candidate.suffix != ".db":
        raise ValueError("Invalid events database name in save metadata")
    events_db_path = save_path.parent / candidate
    if events_db_path.is_symlink():
        raise ValueError("Save events database must not be a symlink")
    return events_db_path


def _get_current_saves_dir() -> Path:
    return Path(app_config.CONFIG.paths.saves)


def _resolve_load_path(save_path: Optional[Path]) -> Path:
    if save_path is None:
        return _get_current_saves_dir() / "save.json"
    return Path(save_path)


def _validate_save_schema(save_data: object) -> dict:
    if not isinstance(save_data, dict):
        raise ValueError("Save root must be an object")
    meta = save_data.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("Save metadata must be an object")
    version = meta.get("schema_version")
    if type(version) is not int or version != SAVE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported save schema version: {version!r}; "
            f"expected {SAVE_SCHEMA_VERSION}"
        )
    return save_data


def _events_db_path_from_save(save_path: Path, save_data: dict) -> Path:
    meta = save_data["meta"]
    events_db_name = meta.get("events_db")
    if not isinstance(events_db_name, str):
        raise ValueError("Save metadata must name its events database")
    events_db_path = get_events_db_path(save_path, events_db_name)
    if not events_db_path.is_file():
        raise FileNotFoundError(f"Save events database does not exist: {events_db_path}")
    expected_count = meta.get("event_count")
    if type(expected_count) is not int:
        raise ValueError("Save metadata must include an integer event count")
    with sqlite3.connect(events_db_path) as conn:
        actual_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if actual_count != expected_count:
        raise ValueError(
            f"Save events database count mismatch: expected {expected_count}, got {actual_count}"
        )
    return events_db_path


def _validate_loaded_institutional_evidence(world: "World") -> None:
    references = world.event_manager.collect_event_reference_ids(
        [
            world.institutional_authority.to_dict(),
            world.institutional_knowledge.to_dict(),
            world.institutional_relations.to_dict(),
        ]
    )
    missing = sorted(
        event_id
        for event_id in references
        if world.event_manager.get_event_by_id(event_id) is None
    )
    if missing:
        raise ValueError(
            "Save is missing canonical institutional causal evidence: "
            + ", ".join(missing)
        )


def load_game(save_path: Optional[Path] = None) -> Tuple["World", "Simulator", List["Sect"]]:
    """从文件加载游戏状态。"""
    resolved_save_path = _resolve_load_path(save_path)
    if not resolved_save_path.exists():
        raise FileNotFoundError(f"存档文件不存在: {resolved_save_path}")

    try:
        with open(resolved_save_path, "r", encoding="utf-8") as f:
            save_data = _validate_save_schema(json.load(f))
        _events_db_path_from_save(resolved_save_path, save_data)

        meta = save_data.get("meta", {})
        print(
            f"Loading save (Version: {meta.get('version', 'unknown')}, "
            f"游戏时间: {meta.get('game_time', 'unknown')})"
        )

        context = LoadContext(save_path=resolved_save_path, save_data=save_data)
        world, simulator, existed_sects = restore_loaded_game(context)
        _validate_loaded_institutional_evidence(world)
        loaded_count = len(context.all_avatars or {})
        print(f"Save loaded successfully! Loaded {loaded_count} avatars")
        return world, simulator, existed_sects
    except Exception as exc:
        print(f"Failed to load game: {exc}")
        import traceback

        traceback.print_exc()
        raise


def check_save_compatibility(save_path: Path) -> Tuple[bool, str]:
    """Return whether a save uses the current explicit schema."""
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            save_data = _validate_save_schema(json.load(f))
        _events_db_path_from_save(save_path, save_data)
        return True, ""
    except Exception as exc:
        return False, f"无法读取存档文件: {exc}"
