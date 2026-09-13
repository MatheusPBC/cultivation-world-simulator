"""Confined save identifiers and read-only metadata listing."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from src.sim.medieval.persistence import PRODUCT, SCHEMA
from .contracts import SaveView, validate_save_id
from .errors import RuntimeProblem


def resolve_save(root: Path, save_id: str) -> Path:
    try:
        validate_save_id(save_id)
    except ValueError as exc:
        raise RuntimeProblem("INVALID_REQUEST", "Nome de save inválido.", 422) from exc
    root = Path(root).resolve()
    path = root / f"{save_id}.mws"
    if path.is_symlink() or path.resolve().parent != root:
        raise RuntimeProblem("UNSAFE_SAVE_PATH", "O arquivo não pertence ao diretório de saves.", 422)
    return path


def list_save_files(root: Path):
    root = Path(root).resolve()
    if not root.is_dir():
        return []
    result = []
    for entry in sorted(root.glob("*.mws")):
        try:
            path = resolve_save(root, entry.stem)
        except RuntimeProblem:
            continue
        if not path.is_file():
            continue
        compatible, day = False, None
        try:
            conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            try:
                metadata = conn.execute("SELECT product,schema_version FROM metadata WHERE id=1").fetchone()
                compatible = metadata == (PRODUCT, SCHEMA)
                row = conn.execute("SELECT payload FROM world WHERE id=1").fetchone()
                raw_day = json.loads(row[0]).get("clock_day") if row else None
                day = raw_day if type(raw_day) is int and raw_day >= 0 else None
            finally:
                conn.close()
        except (sqlite3.DatabaseError, ValueError, TypeError, AttributeError):
            compatible = False
        stat = path.stat()
        result.append(SaveView(save_id=entry.stem, size_bytes=stat.st_size,
                               modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                               compatible=compatible, day=day))
    return result
