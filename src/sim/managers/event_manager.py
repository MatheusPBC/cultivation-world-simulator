"""
事件管理器。

提供事件写入和查询 facade，底层优先使用 SQLite storage。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING
from src.classes.event_query import EventAudience, EventMemoryScope, EventPage, EventQuery, matches_memory_scope

if TYPE_CHECKING:
    from src.classes.causal_link import CausalLink
    from src.classes.event import Event
    from src.classes.event_appraisal import EventAppraisal, ScoredEventAppraisal
    from src.classes.event_storage import EventStorage


class EventManager:
    """
    事件管理器：使用 SQLite 持久化存储。

    对外提供统一事件接口：
    - add_event: 添加事件
    - get_recent_events: 获取最近事件
    - get_events_by_avatar: 按角色查询
    - get_events_between: 按角色对查询
    - get_major_events_by_avatar: 获取角色大事
    - get_minor_events_by_avatar: 获取角色小事
    - get_major_events_between: 获取角色对大事
    - get_minor_events_between: 获取角色对小事
    """

    def __init__(self, storage: Optional["EventStorage"] = None):
        """
        初始化事件管理器。

        Args:
            storage: SQLite 存储层。如果为 None，则使用内存模式（仅用于测试）。
        """
        self._storage = storage
        self._subject_resolver: Callable[[str], object | None] | None = None
        self._protected_event_ids_resolver: Callable[[], set[str]] | None = None
        # 内存后备，仅当 storage 为 None 时使用，主要用于测试。
        self._memory_events: List["Event"] = []
        self._memory_chronicle_chapters: list[object] = []

    @classmethod
    def create_with_db(cls, db_path: Path) -> "EventManager":
        """
        工厂方法：创建使用 SQLite 的事件管理器。

        Args:
            db_path: 数据库文件路径。

        Returns:
            配置好的 EventManager 实例。
        """
        from src.classes.event_storage import EventStorage
        storage = EventStorage(db_path)
        return cls(storage)

    @classmethod
    def create_in_memory(cls) -> "EventManager":
        """
        工厂方法：创建内存模式的事件管理器（仅用于测试）。

        Returns:
            内存模式的 EventManager 实例。
        """
        return cls(storage=None)

    def set_subject_resolver(self, resolver: Callable[[str], object | None]) -> None:
        self._subject_resolver = resolver

    def set_protected_event_ids_resolver(self, resolver: Callable[[], set[str]]) -> None:
        """Keep canonical-state evidence out of maintenance cleanup."""
        self._protected_event_ids_resolver = resolver

    @staticmethod
    def collect_event_reference_ids(payload: object) -> set[str]:
        """Collect conventionally named event references from JSON-safe state."""
        event_ids: set[str] = set()

        def visit(value: object, key: str | None = None) -> None:
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    visit(child_value, str(child_key))
                return
            if isinstance(value, (list, tuple)):
                for item in value:
                    visit(item, key)
                return
            if (
                isinstance(value, str)
                and key is not None
                and (key == "event_id" or key.endswith("_event_id") or key.endswith("_event_ids"))
            ):
                event_ids.add(value)

        visit(payload)
        return event_ids

    def _capture_subject_snapshots(self, event: "Event") -> None:
        if self._subject_resolver is None:
            return
        snapshots = dict(getattr(event, "subject_snapshots", {}) or {})
        for avatar_id in getattr(event, "related_avatars", None) or []:
            avatar_id_str = str(avatar_id)
            if avatar_id_str in snapshots:
                continue
            avatar = self._subject_resolver(avatar_id_str)
            name = getattr(avatar, "name", None) if avatar is not None else None
            if name:
                snapshots[avatar_id_str] = str(name)
        event.subject_snapshots = snapshots

    def add_event(self, event: "Event") -> bool:
        """
        添加事件。

        如果有 SQLite 存储，实时写入数据库。
        否则存入内存后备列表。
        """
        # 过滤空事件。
        from src.classes.event import is_null_event
        if is_null_event(event):
            return True

        self._capture_subject_snapshots(event)

        if self._storage:
            return self._storage.add_event(event)
        else:
            # 内存后备模式。
            self._memory_events.append(event)
            return True

    def commit_step(self, events: list["Event"], chapter=None) -> bool:
        """Persist all durable outputs of one simulation step atomically."""
        from src.classes.event import is_null_event

        persistable_events = [event for event in events if not is_null_event(event)]
        for event in persistable_events:
            self._capture_subject_snapshots(event)

        if self._storage:
            return self._storage.commit_step(persistable_events, chapter)

        event_count = len(self._memory_events)
        chapter_count = len(self._memory_chronicle_chapters)
        try:
            self._memory_events.extend(persistable_events)
            if chapter is not None:
                persisted_ids = {str(event.id) for event in self._memory_events}
                if any(str(event_id) not in persisted_ids for event_id in chapter.source_event_ids):
                    raise ValueError("chronicle chapter references missing events")
                if any(
                    getattr(item, "end_month_stamp", None) == chapter.end_month_stamp
                    for item in self._memory_chronicle_chapters
                ):
                    raise ValueError("chronicle end month already exists")
                self._memory_chronicle_chapters.append(chapter)
            return True
        except Exception:
            del self._memory_events[event_count:]
            del self._memory_chronicle_chapters[chapter_count:]
            return False

    @staticmethod
    def _is_observed_by(event: "Event", avatar_id: str) -> bool:
        avatar_id = str(avatar_id)
        if event.related_avatars and avatar_id in {str(item) for item in event.related_avatars}:
            return True
        for observation in getattr(event, "observations", []) or []:
            if str(getattr(observation, "observer_avatar_id", "")) == avatar_id:
                return True
        return False

    @staticmethod
    def _render_for_observer(event: "Event", avatar_id: str) -> "Event":
        from src.classes.event import Event
        from src.classes.event_renderer import render_observed_event

        avatar_id = str(avatar_id)
        matched_observation = None
        for observation in getattr(event, "observations", []) or []:
            if str(getattr(observation, "observer_avatar_id", "")) == avatar_id:
                matched_observation = {
                    "propagation_kind": getattr(observation, "propagation_kind", "self_direct"),
                    "subject_avatar_id": getattr(observation, "subject_avatar_id", None),
                }
                break

        if matched_observation is None and event.related_avatars and avatar_id in {str(item) for item in event.related_avatars}:
            matched_observation = {
                "propagation_kind": "self_direct",
                "subject_avatar_id": avatar_id,
            }

        if matched_observation is None:
            return event

        rendered = Event.from_dict(event.to_dict())
        rendered.content = render_observed_event(rendered, matched_observation)
        return rendered

    def get_recent_events(self, limit: int = 100, include_decisions: bool = False) -> List["Event"]:
        """获取最近的事件（时间正序）。"""
        if self._storage:
            return self._storage.get_recent_events(limit=limit, include_decisions=include_decisions)

        from src.classes.event import FactKind
        events = self._memory_events
        if not include_decisions:
            events = [e for e in events if getattr(e, "fact_kind", FactKind.OCCURRENCE) != FactKind.DECISION]
        return events[-limit:]

    def append_chronicle_chapter(self, chapter) -> bool:
        if self._storage:
            return self._storage.append_chronicle_chapter(chapter)
        if any(getattr(item, "end_month_stamp", None) == chapter.end_month_stamp for item in self._memory_chronicle_chapters):
            return False
        self._memory_chronicle_chapters.append(chapter)
        return True

    def get_latest_chronicle_chapter(self):
        if self._storage:
            return self._storage.get_latest_chronicle_chapter()
        return max(self._memory_chronicle_chapters, key=lambda item: (item.end_month_stamp, item.id), default=None)

    def get_chronicle_chapter(self, chapter_id: str):
        if self._storage:
            return self._storage.get_chronicle_chapter(chapter_id)
        return next(
            (item for item in self._memory_chronicle_chapters if item.id == chapter_id),
            None,
        )

    def get_chronicle_chapters_page(self, cursor: str | None, limit: int):
        if self._storage:
            return self._storage.get_chronicle_chapters_page(cursor, limit)
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        cursor_value = int(cursor) if cursor is not None else None
        chapters = sorted(self._memory_chronicle_chapters, key=lambda item: (item.end_month_stamp, item.id), reverse=True)
        if cursor_value is not None:
            chapters = [item for item in chapters if item.end_month_stamp < cursor_value]
        page = chapters[:limit]
        has_more = len(chapters) > limit
        return page, str(page[-1].end_month_stamp) if has_more else None, has_more

    def get_events_between_months(self, start: int, end: int) -> list["Event"]:
        if self._storage:
            return self._storage.get_events_between_months(start, end)
        return sorted(
            [event for event in self._memory_events if int(start) <= int(event.month_stamp) <= int(end)],
            key=lambda event: (int(event.month_stamp), event.created_at, event.id),
        )

    def get_events_by_avatar(self, avatar_id: str, *, limit: int = 50) -> List["Event"]:
        """获取角色相关的事件（时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), limit=limit, chronological=True))

    def get_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 50) -> List["Event"]:
        """获取两个角色之间的事件（时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)), limit=limit, chronological=True))

    def get_major_events_by_avatar(self, avatar_id: str, *, limit: int = 10) -> List["Event"]:
        """获取角色的大事（长期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
                                            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True))

    def get_minor_events_by_avatar(self, avatar_id: str, *, limit: int = 10) -> List["Event"]:
        """获取角色的小事（短期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
                                            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True))

    def get_major_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 10) -> List["Event"]:
        """获取两个角色之间的大事（长期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)),
                                            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True))

    def get_minor_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 10) -> List["Event"]:
        """获取两个角色之间的小事（短期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)),
                                            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True))

    def query_events(self, query: EventQuery) -> List["Event"]:
        """Execute the same semantic query contract in either storage backend."""
        events = self.query_page(query).events
        return list(reversed(events)) if query.chronological else events

    def query_page(self, query: EventQuery) -> EventPage["Event"]:
        """Return one page using the same EventQuery semantics in both backends."""
        if self._storage:
            return self._storage.query_page(query)

        if query.audience is EventAudience.OBSERVED and len(query.avatar_ids) != 1:
            raise ValueError("Observed event queries require exactly one avatar")
        from src.classes.event import FactKind
        if query.stable_cursor is not None:
            month, event_id = query.stable_cursor
            if (
                isinstance(month, bool)
                or not isinstance(month, int)
                or month < 0
                or not isinstance(event_id, str)
                or not event_id
            ):
                raise ValueError("invalid stable event cursor")
        result: list["Event"] = []
        start_index = int(query.cursor or "0")
        matched_index = 0
        memory_events = reversed(self._memory_events)
        if query.stable_order:
            memory_events = iter(sorted(
                self._memory_events,
                key=lambda event: (int(event.month_stamp), str(event.id)),
                reverse=True,
            ))
        for event in memory_events:
            related = {str(item) for item in (event.related_avatars or [])}
            if query.audience is EventAudience.OBSERVED:
                matched = self._is_observed_by(event, query.avatar_ids[0])
            else:
                matched = all(avatar_id in related for avatar_id in query.avatar_ids)
            if not matched or not matches_memory_scope(event, query.memory_scope):
                continue
            if not query.include_decisions and getattr(event, "fact_kind", FactKind.OCCURRENCE) == FactKind.DECISION:
                continue
            if query.sect_id is not None and query.sect_id not in (getattr(event, "related_sects", None) or []):
                continue
            if query.stable_cursor is not None and (
                int(event.month_stamp), str(event.id)
            ) >= query.stable_cursor:
                continue
            if matched_index < start_index:
                matched_index += 1
                continue
            result.append(self._render_for_observer(event, query.avatar_ids[0]) if query.audience is EventAudience.OBSERVED else event)
            matched_index += 1
            if len(result) > query.limit:
                break
        has_more = len(result) > query.limit
        result = result[:query.limit]
        return EventPage(result, str(start_index + len(result)) if has_more else None)

    # --- 分页查询接口（新增）---

    def get_events_paginated(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[List["Event"], Optional[str], bool]:
        """
        分页查询事件。

        Args:
            avatar_id: 按单个角色筛选。
            avatar_id_pair: Pair 查询（两个角色之间的事件）。
            sect_id: 按单个宗门筛选。
            cursor: 分页 cursor，获取该位置之前的事件。
            limit: 每页数量。

        Returns:
            (events, next_cursor, has_more)
            - events: 事件列表（时间倒序，最新在前）。
            - next_cursor: 下一页的 cursor，None 表示没有更多。
            - has_more: 是否有更多数据。
        """
        avatar_ids = avatar_id_pair or ((avatar_id,) if avatar_id else ())
        page = self.query_page(EventQuery(
            avatar_ids=tuple(str(item) for item in avatar_ids),
            sect_id=sect_id,
            memory_scope=EventMemoryScope(major_scope) if major_scope in {"major", "minor"} else EventMemoryScope.ALL,
            cursor=cursor,
            limit=limit,
        ))
        return page.events, page.next_cursor, page.next_cursor is not None

    # --- 清理接口 ---

    def get_event_by_id(self, event_id: str) -> Optional["Event"]:
        """按 id 直接读取单个事件，不受默认时间线的 decision 过滤限制。"""
        if self._storage:
            return self._storage.get_event_by_id(event_id)
        for event in self._memory_events:
            if event.id == event_id:
                return event
        return None

    def get_causal_links_for_event(self, event_id: str) -> List["CausalLink"]:
        """返回以 event_id 为结果（效果）的所有因果边，即该事件的直接原因。"""
        if self._storage:
            return self._storage.get_causal_links_for_event(event_id)
        event = self.get_event_by_id(event_id)
        return list(getattr(event, "causal_links", None) or []) if event is not None else []

    def get_causal_links_caused_by(self, cause_event_id: str) -> List["CausalLink"]:
        """返回以 cause_event_id 为原因的所有因果边，即该事件触发的下游效果。"""
        if self._storage:
            return self._storage.get_causal_links_caused_by(cause_event_id)
        result: List["CausalLink"] = []
        for event in self._memory_events:
            for link in getattr(event, "causal_links", None) or []:
                if link.cause_event_id == cause_event_id:
                    result.append(link)
        return result

    def get_causal_telemetry(
        self,
        *,
        start_month: int | None = None,
        end_month: int | None = None,
    ):
        """Return a read-only authorship summary over persisted events."""
        from src.systems.causal_telemetry import aggregate_causal_telemetry

        return aggregate_causal_telemetry(
            self,
            start_month=start_month,
            end_month=end_month,
        )

    def get_event_appraisals(
        self,
        appraiser_avatar_id: str,
        current_month_stamp: int,
        focus_avatar_id: Optional[str] = None,
        min_effective_weight: float = 0.0,
        limit: int = 100,
    ) -> List["EventAppraisal"]:
        """返回某个 appraiser 对（可选）某个 focus 的个人解读；内存模式下返回空列表。"""
        if self._storage:
            return self._storage.get_event_appraisals(
                appraiser_avatar_id,
                current_month_stamp,
                focus_avatar_id=focus_avatar_id,
                min_effective_weight=min_effective_weight,
                limit=limit,
            )
        return []

    def get_scored_event_appraisals(
        self,
        appraiser_avatar_id: str,
        current_month_stamp: int,
        focus_avatar_id: Optional[str] = None,
        min_effective_weight: float = 0.0,
        limit: int = 100,
    ) -> List["ScoredEventAppraisal"]:
        """同 get_event_appraisals，但带回来源事件 month_stamp 与当前有效权重；内存模式下返回空列表。"""
        if self._storage:
            return self._storage.get_scored_event_appraisals(
                appraiser_avatar_id,
                current_month_stamp,
                focus_avatar_id=focus_avatar_id,
                min_effective_weight=min_effective_weight,
                limit=limit,
            )
        return []

    def get_event_appraisals_by_ids(self, appraisal_ids: List[str]) -> List["EventAppraisal"]:
        """按 id 批量读取 EventAppraisal；内存模式下返回空列表。"""
        if self._storage:
            return self._storage.get_event_appraisals_by_ids(appraisal_ids)
        return []

    def update_decision_payload(self, event_id: str, causal_payload: Optional[dict]) -> None:
        """Rewrite a decision event's causal_payload in place (see EventStorage.update_causal_payload)."""
        if self._storage:
            self._storage.update_causal_payload(event_id, causal_payload)
            return
        for event in self._memory_events:
            if event.id == event_id:
                event.causal_payload = causal_payload
                break

    def cleanup(self, keep_major: bool = True, before_month_stamp: Optional[int] = None) -> int:
        """
        清理事件。

        Args:
            keep_major: 是否保留大事。
            before_month_stamp: 删除此时间之前的事件。

        Returns:
            删除的事件数量。
        """
        protected_event_ids = (
            self._protected_event_ids_resolver()
            if self._protected_event_ids_resolver is not None
            else set()
        )
        preserve_factual = self._protected_event_ids_resolver is not None
        if self._storage:
            return self._storage.cleanup(
                keep_major=keep_major,
                before_month_stamp=before_month_stamp,
                protected_event_ids=protected_event_ids,
                preserve_factual=preserve_factual,
            )
        protected = set(protected_event_ids)
        by_id = {event.id: event for event in self._memory_events}
        frontier = list(protected)
        while frontier:
            event = by_id.get(frontier.pop())
            if event is None:
                continue
            for link in getattr(event, "causal_links", ()) or ():
                cause_id = str(link.cause_event_id)
                if cause_id not in protected:
                    protected.add(cause_id)
                    frontier.append(cause_id)

        def should_delete(event: "Event") -> bool:
            if (
                (preserve_factual and not getattr(event, "is_story", False))
                or event.id in protected
            ):
                return False
            if keep_major and getattr(event, "is_major", False):
                return False
            return before_month_stamp is None or int(event.month_stamp) < before_month_stamp

        before_count = len(self._memory_events)
        self._memory_events[:] = [
            event for event in self._memory_events if not should_delete(event)
        ]
        return before_count - len(self._memory_events)

    def count(self) -> int:
        """获取事件总数。"""
        if self._storage:
            return self._storage.count()
        else:
            return len(self._memory_events)

    def close(self) -> None:
        """关闭资源。"""
        if self._storage:
            self._storage.close()
