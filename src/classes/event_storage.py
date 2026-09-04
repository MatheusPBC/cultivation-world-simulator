"""
SQLite 事件存储层。

提供事件的持久化存储、分页查询和清理功能。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from contextlib import contextmanager
from datetime import datetime, timezone

from src.run.log import get_logger
from src.classes.causal_link import CausalLink, CausalRelation, MAX_CAUSAL_LINKS_PER_EVENT
from src.classes.event_query import EventAudience, EventMemoryScope, EventPage, EventQuery


class EventStorageError(RuntimeError):
    """A persistent event-store operation failed.

    An empty result means that no event matched a query; it must never hide a
    SQLite failure.  Callers can now distinguish these two cases reliably.
    """

if TYPE_CHECKING:
    from src.classes.chronicle import ChronicleChapter
    from src.classes.event import Event
    from src.classes.event_appraisal import EventAppraisal, ScoredEventAppraisal
    from src.classes.event_observation import EventObservation

def _format_time(ts: float) -> str:
    """将 timestamp float 转换为 SQLite 兼容的 UTC 字符串"""
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')

def _parse_time(ts_str: str) -> float:
    """将 SQLite 时间字符串解析为 timestamp float"""
    if not ts_str:
        return 0.0
    try:
        # 尝试带微秒的格式
        dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        try:
            # 尝试不带微秒的格式
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return 0.0
    # 假设数据库存的是 UTC (naive time string from sqlite usually treated as such)
    return dt.replace(tzinfo=timezone.utc).timestamp()

class EventStorage:
    """
    SQLite 事件存储层。

    提供：
    - 实时写入事件
    - 分页查询（cursor-based）
    - 按角色/角色对查询
    - 历史清理
    """

    def __init__(self, db_path: Path):
        """
        初始化数据库连接，创建表（如不存在）。

        Args:
            db_path: 数据库文件路径。
        """
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        # 单连接模型下，用可重入锁串行化所有 SQL 操作，避免读写交错污染连接状态。
        self._db_lock = threading.RLock()
        self._logger = get_logger().logger
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库连接和表结构。"""
        try:
            with self._db_lock:
                # 确保目录存在。
                self._db_path.parent.mkdir(parents=True, exist_ok=True)

                self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
                self._conn.row_factory = sqlite3.Row

                # 启用外键约束。
                self._conn.execute("PRAGMA foreign_keys = ON")

                # 创建表。
                self._conn.executescript("""
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        month_stamp INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        is_major BOOLEAN DEFAULT FALSE,
                        is_story BOOLEAN DEFAULT FALSE,
                        event_type TEXT DEFAULT '',
                        render_key TEXT,
                        render_params TEXT,
                        subject_snapshots TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        fact_kind TEXT,
                        causal_payload TEXT,
                        causal_origin TEXT
                    );

                    CREATE TABLE IF NOT EXISTS event_avatars (
                        event_id TEXT NOT NULL,
                        avatar_id TEXT NOT NULL,
                        PRIMARY KEY (event_id, avatar_id),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_events_month_stamp
                        ON events(month_stamp DESC);
                    CREATE INDEX IF NOT EXISTS idx_events_is_major
                        ON events(is_major);
                    CREATE INDEX IF NOT EXISTS idx_event_avatars_avatar_id
                        ON event_avatars(avatar_id);
                    CREATE INDEX IF NOT EXISTS idx_event_avatars_event_id
                        ON event_avatars(event_id);

                    CREATE TABLE IF NOT EXISTS event_sects (
                        event_id TEXT NOT NULL,
                        sect_id INTEGER NOT NULL,
                        PRIMARY KEY (event_id, sect_id),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_sects_sect_id
                        ON event_sects(sect_id);
                    CREATE INDEX IF NOT EXISTS idx_event_sects_event_id
                        ON event_sects(event_id);

                    CREATE TABLE IF NOT EXISTS event_observations (
                        id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        observer_avatar_id TEXT NOT NULL,
                        subject_avatar_id TEXT,
                        propagation_kind TEXT NOT NULL,
                        relation_type TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(event_id, observer_avatar_id, propagation_kind),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_observations_observer_avatar_id
                        ON event_observations(observer_avatar_id);
                    CREATE INDEX IF NOT EXISTS idx_event_observations_event_id
                        ON event_observations(event_id);
                    CREATE INDEX IF NOT EXISTS idx_event_observations_subject_avatar_id
                        ON event_observations(subject_avatar_id);

                    CREATE TABLE IF NOT EXISTS event_causal_links (
                        id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        cause_event_id TEXT NOT NULL,
                        relation TEXT NOT NULL,
                        weight REAL DEFAULT 1.0,
                        note_key TEXT,
                        note_params TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(event_id, cause_event_id, relation),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_causal_links_event_id
                        ON event_causal_links(event_id);
                    CREATE INDEX IF NOT EXISTS idx_event_causal_links_cause_event_id
                        ON event_causal_links(cause_event_id);

                    CREATE TABLE IF NOT EXISTS event_appraisals (
                        id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        appraiser_avatar_id TEXT NOT NULL,
                        focus_avatar_id TEXT NOT NULL,
                        personal_importance REAL NOT NULL,
                        valence REAL NOT NULL,
                        persistence REAL NOT NULL,
                        primary_emotion TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        source TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(event_id, appraiser_avatar_id, focus_avatar_id),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_appraisals_appraiser_avatar_id
                        ON event_appraisals(appraiser_avatar_id);
                    CREATE INDEX IF NOT EXISTS idx_event_appraisals_focus_avatar_id
                        ON event_appraisals(focus_avatar_id);

                    CREATE TABLE IF NOT EXISTS chronicle_chapters (
                        id TEXT PRIMARY KEY,
                        start_month_stamp INTEGER NOT NULL,
                        end_month_stamp INTEGER NOT NULL UNIQUE,
                        trigger TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_chronicle_chapters_end
                        ON chronicle_chapters(end_month_stamp DESC, id DESC);
                """)
                columns = {
                    row["name"]
                    for row in self._conn.execute("PRAGMA table_info(events)").fetchall()
                }
                if "subject_snapshots" not in columns:
                    self._conn.execute("ALTER TABLE events ADD COLUMN subject_snapshots TEXT")
                if "fact_kind" not in columns:
                    self._conn.execute("ALTER TABLE events ADD COLUMN fact_kind TEXT")
                if "causal_payload" not in columns:
                    self._conn.execute("ALTER TABLE events ADD COLUMN causal_payload TEXT")
                if "causal_origin" not in columns:
                    self._conn.execute("ALTER TABLE events ADD COLUMN causal_origin TEXT")
                self._conn.commit()
            self._logger.info(f"EventStorage initialized: {self._db_path}")
        except Exception as e:
            self._logger.error(f"Failed to initialize EventStorage: {e}")
            raise

    @contextmanager
    def _transaction(self):
        """事务上下文管理器。"""
        with self._db_lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def add_event(self, event: "Event") -> bool:
        """
        写入单个事件。

        失败时记录日志并返回 False，不抛异常。

        Args:
            event: 要写入的事件对象。

        Returns:
            写入是否成功。
        """
        if self._conn is None:
            self._logger.error("EventStorage not initialized")
            return False

        try:
            with self._transaction():
                self._insert_event(event)
            return True
        except Exception as e:
            self._logger.error(f"Failed to write event {event.id}: {e}")
            return False

    def commit_step(
        self,
        events: list["Event"],
        chapter: "ChronicleChapter | None" = None,
    ) -> bool:
        """Commit all durable outputs of one simulation step atomically."""
        if self._conn is None:
            self._logger.error("EventStorage not initialized")
            return False

        try:
            with self._transaction():
                for event in events:
                    self._insert_event(event)
                if chapter is not None:
                    missing_sources = [
                        event_id
                        for event_id in chapter.source_event_ids
                        if self._conn.execute(
                            "SELECT 1 FROM events WHERE id = ? LIMIT 1",
                            (str(event_id),),
                        ).fetchone()
                        is None
                    ]
                    if missing_sources:
                        raise EventStorageError(
                            "chronicle chapter references missing events: "
                            + ", ".join(missing_sources)
                        )
                    self._insert_chronicle_chapter(chapter)
            return True
        except Exception as exc:
            self._logger.error("Failed to commit simulation step: %s", exc)
            return False

    def backup_to(self, destination: Path) -> None:
        """Write a consistent SQLite snapshot without copying a live database file."""
        if self._conn is None:
            raise EventStorageError("Event storage is not initialized")

        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(destination))
        try:
            with self._db_lock:
                self._conn.backup(target)
        finally:
            target.close()

    def _insert_event(self, event: "Event") -> None:
        """Insert one event and its dependent rows without managing a transaction."""
        # 插入事件主表。
        self._conn.execute(
            """
            INSERT OR IGNORE INTO events (
                id, month_stamp, content, is_major, is_story, event_type, render_key, render_params, subject_snapshots, created_at, fact_kind, causal_payload, causal_origin
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                int(event.month_stamp),
                event.content,
                event.is_major,
                event.is_story,
                event.event_type,
                event.render_key,
                json.dumps(event.render_params, ensure_ascii=False) if event.render_params is not None else None,
                json.dumps(getattr(event, "subject_snapshots", {}), ensure_ascii=False),
                _format_time(event.created_at),
                str(getattr(event, "fact_kind", None)) if getattr(event, "fact_kind", None) is not None else None,
                json.dumps(event.causal_payload, ensure_ascii=False) if getattr(event, "causal_payload", None) is not None else None,
                str(getattr(event, "causal_origin", "deterministic")),
            )
        )

        # 插入关联表。
        if event.related_avatars:
            for avatar_id in event.related_avatars:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO event_avatars (event_id, avatar_id)
                    VALUES (?, ?)
                    """,
                    (event.id, str(avatar_id))
                )

        # 插入宗门关联表。
        if getattr(event, "related_sects", None):
            for sect_id in event.related_sects:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO event_sects (event_id, sect_id)
                    VALUES (?, ?)
                    """,
                    (event.id, int(sect_id))
                )

        for observation in self._build_observations_for_event(event):
            self._conn.execute(
                """
                INSERT OR IGNORE INTO event_observations (
                    id, event_id, observer_avatar_id, subject_avatar_id,
                    propagation_kind, relation_type, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.id,
                    event.id,
                    str(observation.observer_avatar_id),
                    str(observation.subject_avatar_id) if observation.subject_avatar_id is not None else None,
                    str(observation.propagation_kind),
                    observation.relation_type,
                    _format_time(observation.created_at),
                )
            )

        causal_links = getattr(event, "causal_links", None) or []
        if len(causal_links) > MAX_CAUSAL_LINKS_PER_EVENT:
            self._logger.warning(
                f"Event {event.id} has {len(causal_links)} causal links; "
                f"truncating to {MAX_CAUSAL_LINKS_PER_EVENT}"
            )
            causal_links = causal_links[:MAX_CAUSAL_LINKS_PER_EVENT]

        for link in causal_links:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO event_causal_links (
                    id, event_id, cause_event_id, relation, weight, note_key, note_params, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link.id,
                    event.id,
                    link.cause_event_id,
                    str(link.relation),
                    link.weight,
                    link.note_key,
                    json.dumps(link.note_params, ensure_ascii=False) if link.note_params is not None else None,
                    _format_time(link.created_at),
                )
            )

        # 插入运行时挂载的 appraisal，与事件主表同一事务，失败时整体回滚。
        for appraisal in getattr(event, "appraisals", None) or []:
            self._insert_event_appraisal_row(appraisal)

    def _build_observations_for_event(self, event: "Event") -> list["EventObservation"]:
        from src.classes.event_observation import EventObservation

        observations: list[EventObservation] = []
        seen: set[tuple[str, str, str]] = set()

        for avatar_id in event.related_avatars or []:
            key = (event.id, str(avatar_id), "self_direct")
            if key in seen:
                continue
            seen.add(key)
            observations.append(
                EventObservation(
                    event_id=event.id,
                    observer_avatar_id=str(avatar_id),
                    subject_avatar_id=str(avatar_id),
                    propagation_kind="self_direct",
                )
            )

        for observation in getattr(event, "observations", []) or []:
            observation.event_id = event.id
            key = (event.id, str(observation.observer_avatar_id), str(observation.propagation_kind))
            if key in seen:
                continue
            seen.add(key)
            observations.append(observation)

        return observations

    def _load_avatar_map_for_events(self, event_ids: list[str]) -> dict[str, list[str]]:
        if not event_ids:
            return {}

        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT event_id, avatar_id
                FROM event_avatars
                WHERE event_id IN ({placeholders})
                ORDER BY rowid ASC
                """,
                event_ids,
            ).fetchall()

        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row["avatar_id"])
        return grouped

    def _load_sect_map_for_events(self, event_ids: list[str]) -> dict[str, list[int]]:
        if not event_ids:
            return {}

        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT event_id, sect_id
                FROM event_sects
                WHERE event_id IN ({placeholders})
                ORDER BY rowid ASC
                """,
                event_ids,
            ).fetchall()

        grouped: dict[str, list[int]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row["sect_id"])
        return grouped

    def _row_to_event(
        self,
        row,
        *,
        avatar_map: Optional[dict[str, list[str]]] = None,
        sect_map: Optional[dict[str, list[int]]] = None,
    ) -> "Event":
        from src.classes.causal_origin import CausalOrigin
        from src.classes.event import Event, FactKind
        from src.systems.time import MonthStamp

        if avatar_map is None:
            with self._db_lock:
                avatar_rows = self._conn.execute(
                    "SELECT avatar_id FROM event_avatars WHERE event_id = ?",
                    (row["id"],)
                ).fetchall()
            related_avatars = [r["avatar_id"] for r in avatar_rows]
        else:
            related_avatars = avatar_map.get(row["id"], [])

        if sect_map is None:
            with self._db_lock:
                sect_rows = self._conn.execute(
                    "SELECT sect_id FROM event_sects WHERE event_id = ?",
                    (row["id"],)
                ).fetchall()
            related_sects = [r["sect_id"] for r in sect_rows]
        else:
            related_sects = sect_map.get(row["id"], [])

        snapshot_json = row["subject_snapshots"] if "subject_snapshots" in row.keys() else None
        row_keys = row.keys()
        fact_kind_value = row["fact_kind"] if "fact_kind" in row_keys else None
        causal_payload_json = row["causal_payload"] if "causal_payload" in row_keys else None
        causal_origin_value = row["causal_origin"] if "causal_origin" in row_keys else None
        event = Event(
            month_stamp=MonthStamp(row["month_stamp"]),
            content=row["content"],
            related_avatars=related_avatars if related_avatars else None,
            related_sects=related_sects if related_sects else None,
            is_major=bool(row["is_major"]),
            is_story=bool(row["is_story"]),
            event_type=row["event_type"] or "",
            render_key=row["render_key"],
            render_params=json.loads(row["render_params"]) if row["render_params"] else None,
            subject_snapshots=json.loads(snapshot_json) if snapshot_json else {},
            id=row["id"],
            created_at=_parse_time(row["created_at"]),
            fact_kind=FactKind(fact_kind_value) if fact_kind_value else FactKind.OCCURRENCE,
            causal_payload=json.loads(causal_payload_json) if causal_payload_json else None,
            causal_origin=CausalOrigin(causal_origin_value) if causal_origin_value else CausalOrigin.DETERMINISTIC,
        )
        return event

    def _build_events_from_rows(self, rows) -> list["Event"]:
        event_ids = [row["id"] for row in rows]
        avatar_map = self._load_avatar_map_for_events(event_ids)
        sect_map = self._load_sect_map_for_events(event_ids)
        return [
            self._row_to_event(row, avatar_map=avatar_map, sect_map=sect_map)
            for row in rows
        ]

    def _load_observation_map_for_events(self, event_ids: list[str]) -> dict[str, list[sqlite3.Row]]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT id, event_id, observer_avatar_id, subject_avatar_id, propagation_kind, relation_type, created_at
                FROM event_observations
                WHERE event_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                event_ids,
            ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row)
        return grouped

    def _parse_cursor(self, cursor: str) -> tuple[int, int]:
        """
        解析复合 cursor。

        格式: {month_stamp}_{rowid}

        Returns:
            (month_stamp, rowid)
        """
        parts = cursor.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid cursor format: {cursor}")
        return int(parts[0]), int(parts[1])

    def _make_cursor(self, month_stamp: int, rowid: int) -> str:
        """生成复合 cursor。"""
        return f"{month_stamp}_{rowid}"

    def _query_direct_page(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        stable_cursor: tuple[int, str] | None = None,
        stable_order: bool = False,
        limit: int = 100,
        include_decisions: bool = False,
    ) -> EventPage["Event"]:
        """
        分页查询事件。

        Args:
            avatar_id: 按单个角色筛选。
            avatar_id_pair: Pair 查询（两个角色之间的事件）。
            sect_id: 按单个宗门筛选。
            cursor: 分页 cursor，获取该位置之前的事件。
            limit: 每页数量。

        Returns:
            (events, next_cursor)，next_cursor 为 None 表示没有更多。
        """
        if self._conn is None:
            return EventPage([])

        base_query = ""
        params: list = []
        try:
            with self._db_lock:
                # 构建查询。
                if avatar_id_pair:
                    # Pair 查询：两个角色都相关的事件。
                    id1, id2 = avatar_id_pair
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at, e.fact_kind, e.causal_payload, e.causal_origin
                        FROM events e
                        JOIN event_avatars ea1 ON e.id = ea1.event_id AND ea1.avatar_id = ?
                        JOIN event_avatars ea2 ON e.id = ea2.event_id AND ea2.avatar_id = ?
                    """
                    params.extend([id1, id2])
                elif avatar_id:
                    # 单角色查询。
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at, e.fact_kind, e.causal_payload, e.causal_origin
                        FROM events e
                        JOIN event_avatars ea ON e.id = ea.event_id AND ea.avatar_id = ?
                    """
                    params.append(avatar_id)
                elif sect_id is not None:
                    # 宗门查询。
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at, e.fact_kind, e.causal_payload, e.causal_origin
                        FROM events e
                        JOIN event_sects es ON e.id = es.event_id AND es.sect_id = ?
                    """
                    params.append(sect_id)
                else:
                    # 全部事件。
                    base_query = """
                        SELECT
                            rowid, id, month_stamp, content, is_major, is_story,
                            event_type, render_key, render_params, e.subject_snapshots, e.created_at, e.fact_kind, e.causal_payload, e.causal_origin
                        FROM events e
                    """

                # Cursor 条件（获取更旧的事件）。
                # 使用 rowid 保证同一 month_stamp 内的确定性顺序。
                where_clauses = []
                if major_scope == "major":
                    where_clauses.append("e.is_major = TRUE AND e.is_story = FALSE")
                elif major_scope == "minor":
                    where_clauses.append("(e.is_major = FALSE OR e.is_story = TRUE)")

                if not include_decisions:
                    where_clauses.append("(e.fact_kind IS NULL OR e.fact_kind != 'decision')")

                if stable_cursor is not None:
                    cursor_month, cursor_event_id = stable_cursor
                    if (
                        isinstance(cursor_month, bool)
                        or not isinstance(cursor_month, int)
                        or cursor_month < 0
                        or not isinstance(cursor_event_id, str)
                        or not cursor_event_id
                    ):
                        raise ValueError("invalid stable event cursor")
                    where_clauses.append(
                        "(e.month_stamp < ? OR (e.month_stamp = ? AND e.id < ?))"
                    )
                    params.extend([cursor_month, cursor_month, cursor_event_id])
                elif cursor:
                    cursor_month, cursor_rowid = self._parse_cursor(cursor)
                    where_clauses.append(
                        "(e.month_stamp < ? OR (e.month_stamp = ? AND e.rowid < ?))"
                    )
                    params.extend([cursor_month, cursor_month, cursor_rowid])

                # 组装 WHERE。
                if where_clauses:
                    base_query += " WHERE " + " AND ".join(where_clauses)

                # 排序和分页（最新的在前，向上加载更旧的）。
                # 使用 rowid 保证同一 month_stamp 内的插入顺序。
                if stable_order:
                    base_query += " ORDER BY e.month_stamp DESC, e.id DESC LIMIT ?"
                else:
                    base_query += " ORDER BY e.month_stamp DESC, e.rowid DESC LIMIT ?"
                params.append(limit + 1)  # 多取一条判断是否有更多。

                rows = self._conn.execute(base_query, params).fetchall()

                # 判断是否有更多。
                has_more = len(rows) > limit
                if has_more:
                    rows = rows[:limit]

                # 构建事件对象。
                events = self._build_events_from_rows(rows)
                last_rowid = rows[-1]["rowid"] if rows else None
                last_month_stamp = rows[-1]["month_stamp"] if rows else None

                # 生成 next_cursor。
                next_cursor = None
                if has_more and last_rowid is not None:
                    next_cursor = self._make_cursor(last_month_stamp, last_rowid)

                return EventPage(events, next_cursor)

        except Exception as e:
            self._logger.exception(
                "Failed to query events: %s | avatar_id=%r avatar_id_pair=%r sect_id=%r "
                "major_scope=%r cursor=%r limit=%r sql=%r params=%r",
                e,
                avatar_id,
                avatar_id_pair,
                sect_id,
                major_scope,
                cursor,
                limit,
                base_query,
                params,
            )
            raise EventStorageError("Failed to query events") from e

    def query_page(self, query: EventQuery) -> EventPage["Event"]:
        """Execute an EventQuery and preserve its pagination information."""
        if self._conn is None:
            return EventPage([])
        if query.audience is EventAudience.DIRECT:
            avatar_ids = query.avatar_ids
            if len(avatar_ids) > 2:
                raise ValueError("Direct event queries support at most two avatars")
            return self._query_direct_page(
                avatar_id=avatar_ids[0] if len(avatar_ids) == 1 else None,
                avatar_id_pair=(avatar_ids[0], avatar_ids[1]) if len(avatar_ids) == 2 else None,
                sect_id=query.sect_id,
                major_scope=None if query.memory_scope is EventMemoryScope.ALL else query.memory_scope.value,
                cursor=query.cursor,
                stable_cursor=query.stable_cursor,
                stable_order=query.stable_order,
                limit=query.limit,
                include_decisions=query.include_decisions,
            )

        if len(query.avatar_ids) != 1:
            raise ValueError("Observed event queries require exactly one avatar")
        scope_sql = {
            EventMemoryScope.ALL: "1=1",
            EventMemoryScope.MAJOR: "e.is_major = TRUE AND e.is_story = FALSE",
            EventMemoryScope.MINOR: "e.is_major = FALSE OR e.is_story = TRUE",
        }[query.memory_scope]
        params: list[object] = [query.avatar_ids[0]]
        where_clauses = [scope_sql]
        if not query.include_decisions:
            where_clauses.append("(e.fact_kind IS NULL OR e.fact_kind != 'decision')")
        if query.sect_id is not None:
            where_clauses.append("EXISTS (SELECT 1 FROM event_sects es WHERE es.event_id = e.id AND es.sect_id = ?)")
            params.append(query.sect_id)
        if query.cursor:
            cursor_month, cursor_rowid = self._parse_cursor(query.cursor)
            where_clauses.append("(e.month_stamp < ? OR (e.month_stamp = ? AND e.rowid < ?))")
            params.extend([cursor_month, cursor_month, cursor_rowid])
        sql = f"""
            SELECT DISTINCT e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at, e.fact_kind, e.causal_payload, e.causal_origin,
                eo.propagation_kind, eo.observer_avatar_id, eo.subject_avatar_id, eo.relation_type
            FROM events e JOIN event_observations eo
                ON e.id = eo.event_id AND eo.observer_avatar_id = ?
            WHERE {' AND '.join(where_clauses)}
            ORDER BY e.month_stamp DESC, e.rowid DESC LIMIT ?
        """
        params.append(query.limit + 1)
        try:
            with self._db_lock:
                rows = self._conn.execute(sql, params).fetchall()
            has_more = len(rows) > query.limit
            rows = rows[:query.limit]
            events = self._build_events_from_rows(rows)
            from src.classes.event_renderer import render_observed_event
            for event, row in zip(events, rows):
                event.content = render_observed_event(event, row)
            next_cursor = None
            if has_more and rows:
                next_cursor = self._make_cursor(rows[-1]["month_stamp"], rows[-1]["rowid"])
            return EventPage(events, next_cursor)
        except Exception as exc:
            self._logger.exception("Failed to execute observed event query: %s", exc)
            raise EventStorageError("Failed to query events") from exc

    def get_events(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[list["Event"], Optional[str]]:
        """Legacy paginated adapter; use :meth:`query_page` in new code."""
        avatar_ids = avatar_id_pair or ((avatar_id,) if avatar_id else ())
        page = self.query_page(EventQuery(
            avatar_ids=tuple(str(item) for item in avatar_ids),
            sect_id=sect_id,
            memory_scope=EventMemoryScope(major_scope) if major_scope in {"major", "minor"} else EventMemoryScope.ALL,
            cursor=cursor,
            limit=limit,
        ))
        return page.events, page.next_cursor

    def get_events_by_avatar(self, avatar_id: str, limit: int = 50) -> list["Event"]:
        """
        后端用：获取角色相关事件（供 LLM prompt 使用）。

        返回最新的 N 条，按时间正序排列。
        """
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), limit=limit, chronological=True))

    def get_events_between(self, id1: str, id2: str, limit: int = 50) -> list["Event"]:
        """
        后端用：获取两角色之间的事件。

        返回最新的 N 条，按时间正序排列。
        """
        return self.query_events(EventQuery(avatar_ids=(str(id1), str(id2)), limit=limit, chronological=True))

    def get_major_events_by_avatar(self, avatar_id: str, limit: int = 10) -> list["Event"]:
        """获取角色的大事（长期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True,
        ))

    def get_minor_events_by_avatar(self, avatar_id: str, limit: int = 10) -> list["Event"]:
        """获取角色的小事（短期记忆，包括故事）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True,
        ))

    def get_major_events_between(self, id1: str, id2: str, limit: int = 10) -> list["Event"]:
        """获取两个角色之间的大事（长期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(id1), str(id2)), memory_scope=EventMemoryScope.MAJOR,
            limit=limit, chronological=True,
        ))

    def get_minor_events_between(self, id1: str, id2: str, limit: int = 10) -> list["Event"]:
        """获取两个角色之间的小事（短期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(id1), str(id2)), memory_scope=EventMemoryScope.MINOR,
            limit=limit, chronological=True,
        ))

    def query_events(self, query: EventQuery) -> list["Event"]:
        """Execute the shared event query contract for the SQLite backend."""
        events = self.query_page(query).events
        return list(reversed(events)) if query.chronological else events

    def get_recent_events(self, limit: int = 100, include_decisions: bool = False) -> list["Event"]:
        """获取最近的事件（供初始状态 API 使用）。"""
        events = self.query_page(EventQuery(limit=limit, include_decisions=include_decisions)).events
        return list(reversed(events))  # 时间正序。

    def append_chronicle_chapter(self, chapter: "ChronicleChapter") -> bool:
        """Append one immutable Chronicle chapter.

        The end month is the publication-window idempotency key.  A duplicate
        end month is deliberately a no-op; no existing payload is replaced.
        """
        if self._conn is None:
            return False
        from src.classes.chronicle import ChronicleChapter

        if not isinstance(chapter, ChronicleChapter):
            raise TypeError("chapter must be a ChronicleChapter")
        try:
            with self._transaction():
                self._insert_chronicle_chapter(chapter)
            return True
        except sqlite3.IntegrityError as exc:
            if "chronicle_chapters.end_month_stamp" in str(exc) or "UNIQUE constraint failed: chronicle_chapters.end_month_stamp" in str(exc):
                return False
            raise

    def _insert_chronicle_chapter(self, chapter: "ChronicleChapter") -> None:
        """Insert a Chronicle chapter inside the caller's transaction."""
        self._conn.execute(
            """
            INSERT INTO chronicle_chapters (
                id, start_month_stamp, end_month_stamp, trigger, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chapter.id,
                chapter.start_month_stamp,
                chapter.end_month_stamp,
                chapter.trigger,
                json.dumps(chapter.to_dict(), ensure_ascii=False, separators=(",", ":")),
                float(chapter.created_at),
            ),
        )

    @staticmethod
    def _chronicle_row_to_chapter(row) -> "ChronicleChapter":
        from src.classes.chronicle import ChronicleChapter

        return ChronicleChapter.from_dict(json.loads(row["payload_json"]))

    def get_latest_chronicle_chapter(self) -> "ChronicleChapter | None":
        if self._conn is None:
            return None
        with self._db_lock:
            row = self._conn.execute(
                "SELECT payload_json FROM chronicle_chapters ORDER BY end_month_stamp DESC, id DESC LIMIT 1"
            ).fetchone()
        return self._chronicle_row_to_chapter(row) if row else None

    def get_chronicle_chapter(self, chapter_id: str) -> "ChronicleChapter | None":
        """Read one Chronicle chapter by its immutable id."""
        if self._conn is None:
            return None
        with self._db_lock:
            row = self._conn.execute(
                "SELECT payload_json FROM chronicle_chapters WHERE id = ?",
                (chapter_id,),
            ).fetchone()
        return self._chronicle_row_to_chapter(row) if row else None

    def get_chronicle_chapters_page(
        self, cursor: str | None, limit: int
    ) -> tuple[list["ChronicleChapter"], str | None, bool]:
        if self._conn is None:
            return [], None, False
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        try:
            cursor_value = int(cursor) if cursor is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Chronicle cursor") from exc

        where = "WHERE end_month_stamp < ?" if cursor_value is not None else ""
        params: tuple[object, ...] = (cursor_value, limit + 1) if cursor_value is not None else (limit + 1,)
        with self._db_lock:
            rows = self._conn.execute(
                f"SELECT payload_json, end_month_stamp FROM chronicle_chapters {where} "
                "ORDER BY end_month_stamp DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        chapters = [self._chronicle_row_to_chapter(row) for row in rows]
        next_cursor = str(rows[-1]["end_month_stamp"]) if has_more and rows else None
        return chapters, next_cursor, has_more

    def get_events_between_months(self, start: int, end: int) -> list["Event"]:
        """Return all events in an inclusive, deterministic month window."""
        if self._conn is None:
            return []
        if int(start) > int(end):
            return []
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT rowid, id, month_stamp, content, is_major, is_story,
                    event_type, render_key, render_params, subject_snapshots,
                    created_at, fact_kind, causal_payload, causal_origin
                FROM events
                WHERE month_stamp BETWEEN ? AND ?
                ORDER BY month_stamp ASC, created_at ASC, id ASC
                """,
                (int(start), int(end)),
            ).fetchall()
        return self._build_events_from_rows(rows)

    def cleanup(
        self,
        keep_major: bool = True,
        before_month_stamp: Optional[int] = None,
        protected_event_ids: set[str] | None = None,
        preserve_factual: bool = False,
    ) -> int:
        """
        清理事件。

        Args:
            keep_major: 是否保留大事。
            before_month_stamp: 删除此时间之前的事件。

        Returns:
            删除的事件数量。
        """
        if self._conn is None:
            return 0

        try:
            conditions = []
            params: list = []

            if keep_major:
                conditions.append("is_major = FALSE")

            if before_month_stamp is not None:
                conditions.append("month_stamp < ?")
                params.append(before_month_stamp)

            # A world-level cleanup may discard presentation-only story text,
            # but never canonical facts.  State references add an extra guard
            # for their full causal ancestry below.
            if preserve_factual:
                conditions.append("is_story = TRUE")

            # 如果没有条件且要保留大事，则无需删除任何内容
            if not conditions and keep_major:
                return 0

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            with self._transaction():
                before_count = self._conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE {where_clause}", params
                ).fetchone()[0]
                self._conn.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS event_cleanup_protected ("
                    "id TEXT PRIMARY KEY)"
                )
                self._conn.execute("DELETE FROM event_cleanup_protected")
                self._conn.executemany(
                    "INSERT OR IGNORE INTO event_cleanup_protected (id) VALUES (?)",
                    [(str(event_id),) for event_id in protected_event_ids or ()],
                )
                if preserve_factual:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO event_cleanup_protected (id) "
                        "SELECT id FROM events WHERE is_story = FALSE"
                    )
                self._conn.execute(
                    f"""
                    WITH RECURSIVE protected(id) AS (
                        SELECT id FROM event_cleanup_protected
                        UNION
                        SELECT links.cause_event_id
                        FROM event_causal_links AS links
                        JOIN protected ON links.event_id = protected.id
                    )
                    DELETE FROM events
                    WHERE {where_clause}
                      AND id NOT IN (SELECT id FROM protected)
                    """,
                    params
                )
                after_count = self._conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE {where_clause}", params
                ).fetchone()[0]
                deleted = before_count - after_count

            self._logger.info(f"Cleaned up {deleted} events")
            return deleted

        except Exception as e:
            self._logger.error(f"Failed to cleanup events: {e}")
            return 0

    def update_causal_payload(self, event_id: str, causal_payload: Optional[dict]) -> bool:
        """
        重写单个事件的 causal_payload（就地更新，不新增行）。

        用于跨月消费的决策链：`AgentDecision.rejected` 可能在决策事件已经
        持久化之后的月份才产生，需要通过 UPDATE 回填，而不是重新 INSERT
        （`add_event` 使用 INSERT OR IGNORE，对已存在的行是无操作的）。
        若事件尚未持久化（本月仍在 ctx.events 中），本次 UPDATE 影响 0 行，
        属于正常情况——随后的 `add_event` 会写入包含最终 payload 的完整行。
        """
        if self._conn is None:
            return False
        try:
            with self._transaction():
                self._conn.execute(
                    "UPDATE events SET causal_payload = ? WHERE id = ?",
                    (
                        json.dumps(causal_payload, ensure_ascii=False) if causal_payload is not None else None,
                        event_id,
                    ),
                )
            return True
        except Exception as e:
            self._logger.error(f"Failed to update causal payload for event {event_id}: {e}")
            return False

    def _insert_event_appraisal_row(self, appraisal: "EventAppraisal") -> None:
        """执行单条 event_appraisals INSERT；不管理事务，供 add_event 与
        add_event_appraisal 在各自的事务边界内复用。"""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO event_appraisals (
                id, event_id, appraiser_avatar_id, focus_avatar_id,
                personal_importance, valence, persistence,
                primary_emotion, summary, source, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                appraisal.id,
                appraisal.event_id,
                str(appraisal.appraiser_avatar_id),
                str(appraisal.focus_avatar_id),
                appraisal.personal_importance,
                appraisal.valence,
                appraisal.persistence,
                appraisal.primary_emotion.value,
                appraisal.summary,
                appraisal.source.value,
                _format_time(appraisal.created_at),
            ),
        )

    def add_event_appraisal(self, appraisal: "EventAppraisal") -> bool:
        """
        写入单条 EventAppraisal。

        appraisal 是不可变的历史个人解读；重复的
        (event_id, appraiser_avatar_id, focus_avatar_id) 组合会被静默忽略，
        而不是覆盖已有记录。失败时记录日志并返回 False，不抛异常。
        """
        if self._conn is None:
            self._logger.error("EventStorage not initialized")
            return False
        try:
            with self._transaction():
                self._insert_event_appraisal_row(appraisal)
            return True
        except sqlite3.IntegrityError as e:
            self._logger.error(
                f"Event appraisal {appraisal.id} references a missing or invalid "
                f"event {appraisal.event_id!r}: {e}"
            )
            return False
        except Exception as e:
            self._logger.error(f"Failed to write event appraisal {appraisal.id}: {e}")
            return False

    def get_event_appraisals(
        self,
        appraiser_avatar_id: str,
        current_month_stamp: int,
        focus_avatar_id: Optional[str] = None,
        min_effective_weight: float = 0.0,
        limit: int = 100,
    ) -> list["EventAppraisal"]:
        """查询某个 appraiser 对（可选）某个 focus 的个人解读，按当前有效权重降序排列。"""
        return [
            scored.appraisal
            for scored in self.get_scored_event_appraisals(
                appraiser_avatar_id,
                current_month_stamp,
                focus_avatar_id=focus_avatar_id,
                min_effective_weight=min_effective_weight,
                limit=limit,
            )
        ]

    def get_scored_event_appraisals(
        self,
        appraiser_avatar_id: str,
        current_month_stamp: int,
        focus_avatar_id: Optional[str] = None,
        min_effective_weight: float = 0.0,
        limit: int = 100,
    ) -> list["ScoredEventAppraisal"]:
        """
        与 `get_event_appraisals` 相同的查询，但额外带回读取时派生的
        来源事件 month_stamp 与当前有效权重。

        有效权重依赖来源事件的 month_stamp 与 current_month_stamp 计算的
        年龄（月），不持久化在 event_appraisals 表中；`current_month_stamp`
        为必填参数，调用方必须显式给出评估所用的当前时间，避免默认值
        悄悄产生错误的年龄（进而错误地绕过 min_effective_weight 过滤）。
        """
        from src.classes.event_appraisal import ScoredEventAppraisal

        if self._conn is None:
            return []

        sql = """
            SELECT ea.id, ea.event_id, ea.appraiser_avatar_id, ea.focus_avatar_id,
                ea.personal_importance, ea.valence, ea.persistence,
                ea.primary_emotion, ea.summary, ea.source, ea.created_at,
                ea.rowid AS appraisal_rowid, e.month_stamp AS event_month_stamp
            FROM event_appraisals ea
            JOIN events e ON e.id = ea.event_id
            WHERE ea.appraiser_avatar_id = ?
        """
        params: list = [str(appraiser_avatar_id)]
        if focus_avatar_id is not None:
            sql += " AND ea.focus_avatar_id = ?"
            params.append(str(focus_avatar_id))

        try:
            with self._db_lock:
                rows = self._conn.execute(sql, params).fetchall()
        except Exception as e:
            self._logger.exception(f"Failed to query event appraisals: {e}")
            raise EventStorageError("Failed to query event appraisals") from e

        scored: list[tuple[float, int, int, "EventAppraisal"]] = []
        for row in rows:
            appraisal = self._row_to_event_appraisal(row)
            event_month_stamp = int(row["event_month_stamp"])
            age_months = int(current_month_stamp) - event_month_stamp
            weight = appraisal.effective_weight(age_months)
            if weight >= min_effective_weight:
                scored.append((weight, event_month_stamp, int(row["appraisal_rowid"]), appraisal))

        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [
            ScoredEventAppraisal(
                appraisal=appraisal,
                source_event_month_stamp=event_month_stamp,
                effective_weight=weight,
            )
            for weight, event_month_stamp, _, appraisal in scored[:limit]
        ]

    def _row_to_event_appraisal(self, row) -> "EventAppraisal":
        from src.classes.event_appraisal import AppraisalSource, EventAppraisal
        from src.classes.emotions import EmotionType

        return EventAppraisal(
            id=row["id"],
            event_id=row["event_id"],
            appraiser_avatar_id=row["appraiser_avatar_id"],
            focus_avatar_id=row["focus_avatar_id"],
            personal_importance=row["personal_importance"],
            valence=row["valence"],
            persistence=row["persistence"],
            primary_emotion=EmotionType(row["primary_emotion"]),
            summary=row["summary"],
            source=AppraisalSource(row["source"]),
            created_at=_parse_time(row["created_at"]),
        )

    def get_event_appraisals_by_ids(self, appraisal_ids: list[str]) -> list["EventAppraisal"]:
        """按 id 批量读取 EventAppraisal，用于解析决策 chosen_chain 中引用的证据。

        与 `get_event_appraisals`（按 appraiser 查询）不同，这里按精确 id
        查找，不涉及有效权重计算；结果顺序不保证与输入顺序一致，调用方
        自行按需要重新排序。
        """
        if self._conn is None or not appraisal_ids:
            return []
        placeholders = ",".join("?" for _ in appraisal_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT id, event_id, appraiser_avatar_id, focus_avatar_id,
                    personal_importance, valence, persistence,
                    primary_emotion, summary, source, created_at
                FROM event_appraisals
                WHERE id IN ({placeholders})
                """,
                list(appraisal_ids),
            ).fetchall()
        return [self._row_to_event_appraisal(row) for row in rows]

    def get_event_by_id(self, event_id: str) -> Optional["Event"]:
        """按 id 直接读取单个事件，不受默认时间线的 decision 过滤限制。"""
        if self._conn is None:
            return None
        with self._db_lock:
            row = self._conn.execute(
                """
                SELECT id, month_stamp, content, is_major, is_story, event_type, render_key,
                    render_params, subject_snapshots, created_at, fact_kind, causal_payload, causal_origin
                FROM events WHERE id = ?
                """,
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        event = self._row_to_event(row)
        event.causal_links = self.get_causal_links_for_event(event.id)
        return event

    def get_causal_links_for_event(self, event_id: str) -> list["CausalLink"]:
        """
        返回以 event_id 为结果（效果）的所有因果边，即该事件的直接原因。

        不会因为 cause_event_id 指向的原始事件已被 cleanup 清理而报错或漏读——
        因果边本身没有对 cause_event_id 的外键约束，允许其指向一个已被裁剪的事件。
        """
        if self._conn is None:
            return []
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT id, event_id, cause_event_id, relation, weight, note_key, note_params, created_at
                FROM event_causal_links
                WHERE event_id = ?
                ORDER BY created_at ASC
                """,
                (event_id,),
            ).fetchall()
        return [self._row_to_causal_link(row) for row in rows]

    def get_causal_links_caused_by(self, cause_event_id: str) -> list["CausalLink"]:
        """返回以 cause_event_id 为原因的所有因果边，即该事件触发的下游效果。"""
        if self._conn is None:
            return []
        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT id, event_id, cause_event_id, relation, weight, note_key, note_params, created_at
                FROM event_causal_links
                WHERE cause_event_id = ?
                ORDER BY created_at ASC
                """,
                (cause_event_id,),
            ).fetchall()
        return [self._row_to_causal_link(row) for row in rows]

    def _row_to_causal_link(self, row) -> "CausalLink":
        return CausalLink(
            id=row["id"],
            event_id=row["event_id"],
            cause_event_id=row["cause_event_id"],
            relation=CausalRelation(row["relation"]),
            weight=row["weight"],
            note_key=row["note_key"],
            note_params=json.loads(row["note_params"]) if row["note_params"] else None,
            created_at=_parse_time(row["created_at"]),
        )

    def count(self) -> int:
        """获取事件总数。"""
        if self._conn is None:
            return 0
        try:
            with self._db_lock:
                row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            try:
                with self._db_lock:
                    self._conn.close()
                    self._logger.info("EventStorage closed")
            except Exception as e:
                self._logger.error(f"Failed to close EventStorage: {e}")
            finally:
                self._conn = None
