"""
存档功能模块。

顶层函数只负责路径、事件数据库复制、section 编排和文件 IO。具体 payload
由 `src.sim.save.sections` 中的 section 负责，避免新增系统继续膨胀本文件。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import src.utils.config as app_config
from src.classes.event_storage import EventStorage
from src.sim.save.sections.base import SaveContext
from src.sim.save.sections.registry import dump_save_data

if TYPE_CHECKING:
    from src.classes.core.sect import Sect
    from src.classes.core.world import World
    from src.sim.simulator import Simulator


def sanitize_save_name(name: str) -> str:
    """清理存档名称，只保留安全字符。"""
    safe_name = re.sub(r'[\\/:*?"<>|]', "", name)
    safe_name = re.sub(r"[^\w\u4e00-\u9fff]", "_", safe_name)
    return safe_name[:50] if safe_name else "save"


def _get_current_saves_dir() -> Path:
    return Path(app_config.CONFIG.paths.saves)


def _resolve_save_path(
    *,
    world: "World",
    save_path: Optional[Path],
    custom_name: Optional[str],
) -> Path:
    if save_path is not None:
        resolved = Path(save_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    saves_dir = _get_current_saves_dir()
    saves_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    time_str = now.strftime("%Y%m%d_%H%M%S")
    year = world.month_stamp.get_year()
    month = world.month_stamp.get_month().value
    game_time_str = f"Y{year}M{month}"
    if custom_name:
        filename = f"{sanitize_save_name(custom_name)}_{time_str}.json"
    else:
        filename = f"{time_str}_{game_time_str}.json"
    return saves_dir / filename


def _snapshot_events_database(world: "World", events_db_path: Path) -> None:
    """Materialize the authoritative event history into a SQLite sidecar."""
    storage = getattr(getattr(world, "event_manager", None), "_storage", None)
    if storage is not None:
        storage.backup_to(events_db_path)
        return

    snapshot = EventStorage(events_db_path)
    try:
        events = world.event_manager.get_events_between_months(-2**63, 2**63 - 1)
        if not snapshot.commit_step(events):
            raise RuntimeError("Failed to materialize in-memory event history")
        chapters = []
        cursor = None
        while True:
            page, cursor, has_more = world.event_manager.get_chronicle_chapters_page(
                cursor, limit=100
            )
            chapters.extend(page)
            if not has_more:
                break
        for chapter in reversed(chapters):
            if not snapshot.append_chronicle_chapter(chapter):
                raise RuntimeError("Failed to materialize in-memory chronicle history")
    finally:
        snapshot.close()


def _temporary_path(destination: Path, suffix: str) -> Path:
    handle, raw_path = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=suffix,
        dir=destination.parent,
    )
    os.close(handle)
    return Path(raw_path)


def _validate_institutional_evidence(world: "World", events_db_path: Path) -> None:
    references = world.event_manager.collect_event_reference_ids(
        [
            world.institutional_authority.to_dict(),
            world.institutional_knowledge.to_dict(),
            world.institutional_relations.to_dict(),
        ]
    )
    if not references:
        return
    storage = EventStorage(events_db_path)
    try:
        missing = sorted(
            event_id for event_id in references if storage.get_event_by_id(event_id) is None
        )
    finally:
        storage.close()
    if missing:
        raise ValueError(
            "Save would lose canonical causal evidence: " + ", ".join(missing)
        )


def save_game(
    world: "World",
    simulator: "Simulator",
    existed_sects: List["Sect"],
    save_path: Optional[Path] = None,
    custom_name: Optional[str] = None,
    is_auto_save: bool = False,
) -> tuple[bool, Optional[str]]:
    """保存游戏状态到 JSON + SQLite 事件库。"""
    try:
        resolved_save_path = _resolve_save_path(
            world=world,
            save_path=save_path,
            custom_name=custom_name,
        )
        events_db_path = resolved_save_path.with_name(
            f"{resolved_save_path.stem}_events.{uuid.uuid4().hex}.db"
        )
        temporary_events_db_path = _temporary_path(events_db_path, ".db")
        temporary_save_path = _temporary_path(resolved_save_path, ".json")
        try:
            _snapshot_events_database(world, temporary_events_db_path)
            _validate_institutional_evidence(world, temporary_events_db_path)

            context = SaveContext(
                world=world,
                simulator=simulator,
                existed_sects=list(existed_sects),
                save_path=resolved_save_path,
                events_db_path=events_db_path,
                custom_name=custom_name,
                is_auto_save=is_auto_save,
            )
            save_data = dump_save_data(context)

            with open(temporary_save_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            os.replace(temporary_events_db_path, events_db_path)
            try:
                os.replace(temporary_save_path, resolved_save_path)
            except Exception:
                events_db_path.unlink(missing_ok=True)
                raise
        finally:
            temporary_events_db_path.unlink(missing_ok=True)
            temporary_save_path.unlink(missing_ok=True)

        print(f"Game saved to: {resolved_save_path}")
        return True, resolved_save_path.name
    except Exception as exc:
        print(f"Failed to save game: {exc}")
        import traceback

        traceback.print_exc()
        return False, None


def get_save_info(save_path: Path) -> Optional[dict]:
    """读取存档文件的元信息。"""
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("meta", {})
    except Exception:
        return None


def list_saves(saves_dir: Optional[Path] = None) -> List[tuple[Path, dict]]:
    """列出所有存档文件及其元信息。"""
    if saves_dir is None:
        saves_dir = _get_current_saves_dir()

    if not saves_dir.exists():
        return []

    saves = []
    for save_file in saves_dir.glob("*.json"):
        info = get_save_info(save_file)
        if info is not None:
            saves.append((save_file, info))

    saves.sort(key=lambda x: x[1].get("save_time", ""), reverse=True)
    return saves
