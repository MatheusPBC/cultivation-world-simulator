"""
Tests for EventStorage and EventManager.

Covers:
- EventStorage: add_event, get_events, pagination, cursor handling, cleanup
- EventManager: all query methods, get_events_paginated
- Memory fallback mode
"""

import pytest
import tempfile
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

from src.classes.emotions import EmotionType
from src.classes.event import Event, NULL_EVENT
from src.classes.event_appraisal import AppraisalSource, EventAppraisal
from src.classes.event_query import EventQuery
from src.classes.event_storage import EventStorage, EventStorageError
from src.sim.managers.event_manager import EventManager
from src.systems.time import Year, Month, create_month_stamp


# --- Fixtures ---

@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_events.db"


@pytest.fixture
def event_storage(temp_db_path):
    """Create an EventStorage instance with a temporary database."""
    storage = EventStorage(temp_db_path)
    yield storage
    storage.close()


@pytest.fixture
def event_manager(temp_db_path):
    """Create an EventManager with SQLite storage."""
    manager = EventManager.create_with_db(temp_db_path)
    yield manager
    manager.close()


@pytest.fixture
def memory_event_manager():
    """Create an EventManager in memory mode (no SQLite)."""
    return EventManager.create_in_memory()


def make_event(
    year: int,
    month: int,
    content: str,
    avatar_ids: list[str] | None = None,
    is_major: bool = False,
    is_story: bool = False,
    event_id: str | None = None,
) -> Event:
    """Helper to create an Event with the given parameters."""
    month_stamp = create_month_stamp(Year(year), Month(month))
    kwargs = {
        "month_stamp": month_stamp,
        "content": content,
        "related_avatars": avatar_ids,
        "is_major": is_major,
        "is_story": is_story,
    }
    if event_id is not None:
        kwargs["id"] = event_id
    return Event(**kwargs)
    
# --- EventStorage Tests ---

class TestEventStorageBasic:
    """Basic EventStorage functionality tests."""

    def test_init_creates_tables(self, temp_db_path):
        """Test that EventStorage creates necessary tables on init."""
        storage = EventStorage(temp_db_path)
        assert storage._conn is not None

        # Verify tables exist
        cursor = storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('events', 'event_avatars')"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "events" in tables
        assert "event_avatars" in tables

        storage.close()

    def test_add_event_success(self, event_storage):
        """Test adding a single event."""
        event = make_event(100, 5, "Test event content", ["avatar_1", "avatar_2"])

        result = event_storage.add_event(event)

        assert result is True
        assert event_storage.count() == 1

    def test_add_event_duplicate_ignored(self, event_storage):
        """Test that duplicate events (same ID) are ignored."""
        event = make_event(100, 5, "Original content", event_id="fixed-id")
        event_storage.add_event(event)

        # Try to add with same ID but different content
        duplicate = make_event(100, 5, "Different content", event_id="fixed-id")
        result = event_storage.add_event(duplicate)

        assert result is True  # INSERT OR IGNORE doesn't fail
        assert event_storage.count() == 1

    def test_add_event_without_avatars(self, event_storage):
        """Test adding an event without related avatars."""
        event = make_event(100, 5, "World event", avatar_ids=None)

        result = event_storage.add_event(event)

        assert result is True
        assert event_storage.count() == 1

    def test_commit_step_commits_the_whole_batch_and_preserves_causal_links(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 5, "Batch cause", ["avatar_1"])
        effect = make_event(100, 5, "Batch effect", ["avatar_2"])
        effect.causal_links = [
            CausalLink(
                event_id=effect.id,
                cause_event_id=cause.id,
                relation=CausalRelation.ENABLED_BY,
            )
        ]

        assert event_storage.commit_step([cause, effect]) is True
        assert event_storage.count() == 2
        assert event_storage.get_event_by_id(cause.id) is not None
        links = event_storage.get_causal_links_for_event(effect.id)
        assert [(link.event_id, link.cause_event_id, link.relation) for link in links] == [
            (effect.id, cause.id, CausalRelation.ENABLED_BY)
        ]

    def test_commit_step_rolls_back_when_a_later_event_fails(self, event_storage, monkeypatch):
        original_insert = event_storage._insert_event
        insert_count = 0

        def fail_on_second_event(event):
            nonlocal insert_count
            insert_count += 1
            if insert_count == 2:
                raise RuntimeError("injected batch failure")
            original_insert(event)

        monkeypatch.setattr(event_storage, "_insert_event", fail_on_second_event)
        first = make_event(100, 5, "Must roll back", ["avatar_1"])
        second = make_event(100, 5, "Injected failure", ["avatar_2"])

        assert event_storage.commit_step([first, second]) is False
        assert event_storage.count() == 0
        assert event_storage.get_event_by_id(first.id) is None
        assert event_storage.get_event_by_id(second.id) is None

    def test_subject_snapshots_round_trip(self, event_storage):
        event = make_event(100, 5, "Alice acted", ["avatar_1"])
        event.subject_snapshots = {"avatar_1": "Alice"}

        event_storage.add_event(event)
        events, _ = event_storage.get_events()

        assert events[0].subject_snapshots == {"avatar_1": "Alice"}

    def test_count(self, event_storage):
        """Test event counting."""
        assert event_storage.count() == 0

        event_storage.add_event(make_event(100, 1, "Event 1"))
        assert event_storage.count() == 1

        event_storage.add_event(make_event(100, 2, "Event 2"))
        assert event_storage.count() == 2


class TestEventStorageQueries:
    """EventStorage query functionality tests."""

    def test_get_events_empty_db(self, event_storage):
        """Test querying an empty database."""
        events, cursor = event_storage.get_events()

        assert events == []
        assert cursor is None

    def test_get_events_raises_distinct_error_when_sqlite_read_fails(self, event_storage):
        """A broken store must not be indistinguishable from an empty result."""
        class BrokenConnection:
            def execute(self, *_args, **_kwargs):
                raise Exception("broken sqlite")

        connection = event_storage._conn
        event_storage._conn = BrokenConnection()
        try:
            with pytest.raises(EventStorageError, match="Failed to query events"):
                event_storage.get_events()
        finally:
            event_storage._conn = connection

    def test_get_events_all(self, event_storage):
        """Test getting all events (no filter)."""
        event_storage.add_event(make_event(100, 1, "Event 1", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event 2", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event 3", ["a1", "a2"]))

        events, cursor = event_storage.get_events()

        assert len(events) == 3
        # Events returned in descending order (newest first)
        assert events[0].content == "Event 3"
        assert events[1].content == "Event 2"
        assert events[2].content == "Event 1"

    def test_get_events_by_avatar(self, event_storage):
        """Test filtering events by single avatar."""
        event_storage.add_event(make_event(100, 1, "Event A1 only", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event A2 only", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event both", ["a1", "a2"]))

        events, _ = event_storage.get_events(avatar_id="a1")

        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Event A1 only" in contents
        assert "Event both" in contents
        assert "Event A2 only" not in contents

    def test_get_events_by_sect(self, event_storage):
        """Test filtering events by sect_id."""
        # 事件1：仅关联宗门1
        e1 = make_event(100, 1, "Sect 1 only")
        e1.related_sects = [1]
        event_storage.add_event(e1)

        # 事件2：仅关联宗门2
        e2 = make_event(100, 2, "Sect 2 only")
        e2.related_sects = [2]
        event_storage.add_event(e2)

        # 事件3：无宗门关联
        e3 = make_event(100, 3, "No sect")
        e3.related_sects = None
        event_storage.add_event(e3)

        events, _ = event_storage.get_events(sect_id=1)

        assert len(events) == 1
        assert events[0].content == "Sect 1 only"

    def test_get_events_by_avatar_pair(self, event_storage):
        """Test filtering events by avatar pair."""
        event_storage.add_event(make_event(100, 1, "Event A1 only", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event A2 only", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event A1+A2", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 4, "Event A1+A3", ["a1", "a3"]))

        events, _ = event_storage.get_events(avatar_id_pair=("a1", "a2"))

        assert len(events) == 1
        assert events[0].content == "Event A1+A2"

    def test_get_events_by_avatar_returns_related_avatars(self, event_storage):
        """Test that related_avatars are correctly returned."""
        event_storage.add_event(make_event(100, 1, "Multi avatar", ["a1", "a2", "a3"]))

        events, _ = event_storage.get_events(avatar_id="a1")

        assert len(events) == 1
        assert set(events[0].related_avatars) == {"a1", "a2", "a3"}

    def test_get_events_batches_related_avatar_and_sect_lookups_per_page(self, event_storage):
        """Test get_events batches related avatar/sect lookups instead of querying per row."""
        for idx in range(3):
            event = make_event(100, idx + 1, f"Event {idx}", [f"a{idx}", f"b{idx}"])
            event.related_sects = [idx + 1, idx + 10]
            event_storage.add_event(event)

        related_query_counts = {
            "event_avatars": 0,
            "event_sects": 0,
        }

        def tracer(sql: str) -> None:
            normalized = " ".join(sql.split()).lower()
            if " from event_avatars " in normalized:
                related_query_counts["event_avatars"] += 1
            if " from event_sects " in normalized:
                related_query_counts["event_sects"] += 1

        event_storage._conn.set_trace_callback(tracer)
        try:
            events, _ = event_storage.get_events(limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert related_query_counts["event_avatars"] == 1
        assert related_query_counts["event_sects"] == 1
        assert set(events[0].related_sects) == {3, 12}


class TestEventStoragePagination:
    """EventStorage pagination tests."""

    def test_pagination_limit(self, event_storage):
        """Test that limit parameter works."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor = event_storage.get_events(limit=5)

        assert len(events) == 5
        assert cursor is not None  # Has more

    def test_pagination_cursor_format(self, event_storage):
        """Test cursor format is {month_stamp}_{rowid}."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        _, cursor = event_storage.get_events(limit=5)

        assert cursor is not None
        parts = cursor.split("_")
        assert len(parts) == 2
        # Both parts should be integers
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    def test_pagination_cursor_continues(self, event_storage):
        """Test that using cursor returns next page."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        # First page
        page1, cursor1 = event_storage.get_events(limit=5)
        assert len(page1) == 5
        assert cursor1 is not None  # More events exist

        # Second page
        page2, cursor2 = event_storage.get_events(limit=5, cursor=cursor1)
        assert len(page2) == 5

        # No overlap between pages
        page1_ids = {e.id for e in page1}
        page2_ids = {e.id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

        # cursor2 is None because all 10 events have been returned
        assert cursor2 is None

        # All 10 unique events were returned across both pages
        all_ids = page1_ids | page2_ids
        assert len(all_ids) == 10

    def test_pagination_no_more_events(self, event_storage):
        """Test that cursor is None when no more events."""
        for i in range(3):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor = event_storage.get_events(limit=10)

        assert len(events) == 3
        assert cursor is None  # No more

    def test_pagination_with_filter(self, event_storage):
        """Test pagination combined with avatar filter."""
        for i in range(10):
            avatar_id = "a1" if i % 2 == 0 else "a2"
            event_storage.add_event(make_event(100, i + 1, f"Event {i}", [avatar_id]))

        # Get a1's events (5 total)
        page1, cursor = event_storage.get_events(avatar_id="a1", limit=3)
        assert len(page1) == 3

        page2, _ = event_storage.get_events(avatar_id="a1", limit=3, cursor=cursor)
        assert len(page2) == 2  # Only 2 remaining


class TestEventStorageHelperMethods:
    """Tests for helper query methods."""

    def test_get_events_by_avatar_method(self, event_storage):
        """Test get_events_by_avatar returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First", ["a1"]))
        event_storage.add_event(make_event(100, 6, "Second", ["a1"]))
        event_storage.add_event(make_event(101, 1, "Third", ["a1"]))

        events = event_storage.get_events_by_avatar("a1")

        # Should be in chronological order (oldest first)
        assert events[0].content == "First"
        assert events[1].content == "Second"
        assert events[2].content == "Third"

    def test_get_events_between_method(self, event_storage):
        """Test get_events_between returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First pair", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 6, "Second pair", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 3, "A1 only", ["a1"]))

        events = event_storage.get_events_between("a1", "a2")

        assert len(events) == 2
        # Chronological order
        assert events[0].content == "First pair"
        assert events[1].content == "Second pair"

    def test_get_major_events_by_avatar(self, event_storage):
        """Test getting only major events for an avatar."""
        event_storage.add_event(make_event(100, 1, "Minor 1", ["a1"], is_major=False))
        event_storage.add_event(make_event(100, 2, "Major 1", ["a1"], is_major=True))
        event_storage.add_event(make_event(100, 3, "Story", ["a1"], is_major=True, is_story=True))
        event_storage.add_event(make_event(100, 4, "Major 2", ["a1"], is_major=True))

        events = event_storage.get_major_events_by_avatar("a1")

        # Should only include major non-story events
        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Major 1" in contents
        assert "Major 2" in contents
        assert "Story" not in contents
        assert "Minor 1" not in contents

    def test_get_major_events_by_avatar_batches_related_avatar_and_sect_lookups(self, event_storage):
        """Test get_major_events_by_avatar batches related avatar/sect lookups for the page."""
        for idx in range(3):
            event = make_event(100, idx + 1, f"Major {idx}", [f"a{idx}", "a1"], is_major=True)
            event.related_sects = [idx + 1, idx + 10]
            event_storage.add_event(event)

        related_query_counts = {
            "event_avatars": 0,
            "event_sects": 0,
        }

        def tracer(sql: str) -> None:
            normalized = " ".join(sql.split()).lower()
            if " from event_avatars " in normalized:
                related_query_counts["event_avatars"] += 1
            if " from event_sects " in normalized:
                related_query_counts["event_sects"] += 1

        event_storage._conn.set_trace_callback(tracer)
        try:
            events = event_storage.get_major_events_by_avatar("a1", limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert related_query_counts["event_avatars"] == 1
        assert related_query_counts["event_sects"] == 1
        assert set(events[-1].related_sects) == {3, 12}

    def test_get_minor_events_by_avatar(self, event_storage):
        """Test getting minor events (including stories) for an avatar."""
        event_storage.add_event(make_event(100, 1, "Minor 1", ["a1"], is_major=False))
        event_storage.add_event(make_event(100, 2, "Major 1", ["a1"], is_major=True))
        event_storage.add_event(make_event(100, 3, "Story", ["a1"], is_major=True, is_story=True))

        events = event_storage.get_minor_events_by_avatar("a1")

        # Should include minor and story events
        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Minor 1" in contents
        assert "Story" in contents
        assert "Major 1" not in contents

    def test_get_recent_events(self, event_storage):
        """Test get_recent_events returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First"))
        event_storage.add_event(make_event(100, 6, "Second"))
        event_storage.add_event(make_event(101, 1, "Third"))

        events = event_storage.get_recent_events()

        # Should be chronological (oldest first)
        assert events[0].content == "First"
        assert events[1].content == "Second"
        assert events[2].content == "Third"


class TestEventStorageQueryEfficiency:
    """Tests for query counts in SQLite-backed read paths."""

    def test_get_events_uses_batched_association_queries(self, event_storage):
        """get_events should not issue per-row association lookups."""
        for i in range(4):
            event = make_event(100, i + 1, f"Event {i}", [f"a{i}", f"b{i}"])
            event.related_sects = [1, 2]
            event_storage.add_event(event)

        sql_statements: list[str] = []

        def tracer(sql: str) -> None:
            sql_statements.append(sql)

        event_storage._conn.set_trace_callback(tracer)
        try:
            events, cursor = event_storage.get_events(limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert cursor is not None
        assert len(sql_statements) <= 3

    def test_get_major_events_by_avatar_uses_batched_association_queries(self, event_storage):
        """Major-event queries should not reload associations row by row."""
        for i in range(3):
            event = make_event(100, i + 1, f"Major {i}", ["a1", f"other{i}"], is_major=True)
            event.related_sects = [1]
            event_storage.add_event(event)

        sql_statements: list[str] = []

        def tracer(sql: str) -> None:
            sql_statements.append(sql)

        event_storage._conn.set_trace_callback(tracer)
        try:
            events = event_storage.get_major_events_by_avatar("a1")
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert len(sql_statements) <= 3


class TestEventStorageCleanup:
    """Tests for event cleanup functionality."""

    def test_cleanup_keeps_major_by_default(self, event_storage):
        """Test that cleanup keeps major events by default."""
        event_storage.add_event(make_event(100, 1, "Minor", is_major=False))
        event_storage.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_storage.cleanup()

        assert deleted == 1
        assert event_storage.count() == 1
        events = event_storage.get_recent_events()
        assert events[0].content == "Major"

    def test_cleanup_deletes_all_when_keep_major_false(self, event_storage):
        """Test cleanup with keep_major=False."""
        event_storage.add_event(make_event(100, 1, "Minor", is_major=False))
        event_storage.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_storage.cleanup(keep_major=False)

        assert deleted == 2
        assert event_storage.count() == 0

    def test_cleanup_before_month_stamp(self, event_storage):
        """Test cleanup with before_month_stamp filter."""
        event_storage.add_event(make_event(100, 1, "Old", is_major=False))
        event_storage.add_event(make_event(200, 1, "New", is_major=False))

        # Delete events before year 150
        before_stamp = int(create_month_stamp(Year(150), Month.JANUARY))
        deleted = event_storage.cleanup(keep_major=False, before_month_stamp=before_stamp)

        assert deleted == 1
        assert event_storage.count() == 1
        events = event_storage.get_recent_events()
        assert events[0].content == "New"


class TestEventStorageCausalMetadata:
    """Task 2: fact_kind / causal_payload columns and the event_causal_links side table."""

    def test_init_creates_causal_links_table(self, temp_db_path):
        storage = EventStorage(temp_db_path)

        cursor = storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = 'event_causal_links'"
        )
        assert cursor.fetchone() is not None

        columns = {row["name"] for row in storage._conn.execute("PRAGMA table_info(events)").fetchall()}
        assert "fact_kind" in columns
        assert "causal_payload" in columns

        storage.close()

    def test_upgrades_a_pre_existing_database_missing_the_new_columns(self, temp_db_path):
        import sqlite3

        legacy_conn = sqlite3.connect(str(temp_db_path))
        legacy_conn.executescript(
            """
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                month_stamp INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_major BOOLEAN DEFAULT FALSE,
                is_story BOOLEAN DEFAULT FALSE,
                event_type TEXT DEFAULT '',
                render_key TEXT,
                render_params TEXT,
                subject_snapshots TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        legacy_conn.commit()
        legacy_conn.close()

        storage = EventStorage(temp_db_path)
        columns = {row["name"] for row in storage._conn.execute("PRAGMA table_info(events)").fetchall()}
        assert "fact_kind" in columns
        assert "causal_payload" in columns

        event = make_event(100, 5, "Upgraded db still writes fine")
        assert storage.add_event(event) is True
        storage.close()

    def test_add_event_persists_fact_kind_and_causal_payload(self, event_storage):
        from src.classes.event import FactKind

        event = make_event(100, 5, "Population fell")
        event.fact_kind = FactKind.STATE_TRANSITION
        event.causal_payload = {"deltas": [{"aspect": "population"}], "decision": None}

        event_storage.add_event(event)
        events, _ = event_storage.get_events()

        assert events[0].fact_kind == FactKind.STATE_TRANSITION
        assert events[0].causal_payload == {"deltas": [{"aspect": "population"}], "decision": None}

    def test_read_defaults_fact_kind_to_occurrence_when_null(self, event_storage):
        from src.classes.event import FactKind

        event = make_event(100, 5, "Plain event")
        event_storage.add_event(event)
        events, _ = event_storage.get_events()

        assert events[0].fact_kind == FactKind.OCCURRENCE
        assert events[0].causal_payload is None

    def test_row_to_event_does_not_eagerly_load_causal_links(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        ]
        event_storage.add_event(cause)
        event_storage.add_event(effect)

        events, _ = event_storage.get_events()

        assert all(event.causal_links == [] for event in events)


class TestEventStorageCausalLinks:
    """Write/read/cleanup behaviour for the event_causal_links side table."""

    def test_links_write_and_read_back(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(
                event_id=effect.id,
                cause_event_id=cause.id,
                relation=CausalRelation.TRIGGERED_BY,
                weight=0.8,
            )
        ]
        event_storage.add_event(cause)
        event_storage.add_event(effect)

        links = event_storage.get_causal_links_for_event(effect.id)

        assert len(links) == 1
        assert links[0].cause_event_id == cause.id
        assert links[0].relation == CausalRelation.TRIGGERED_BY
        assert links[0].weight == 0.8

    def test_multifactor_links_on_one_effect(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause1 = make_event(100, 1, "cause1")
        cause2 = make_event(100, 1, "cause2")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause1.id, relation=CausalRelation.TRIGGERED_BY, weight=0.6),
            CausalLink(event_id=effect.id, cause_event_id=cause2.id, relation=CausalRelation.ENABLED_BY, weight=0.4),
        ]
        event_storage.add_event(cause1)
        event_storage.add_event(cause2)
        event_storage.add_event(effect)

        links = event_storage.get_causal_links_for_event(effect.id)

        assert {link.cause_event_id for link in links} == {cause1.id, cause2.id}

    def test_unique_constraint_deduplicates_identical_links(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        link = CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        effect.causal_links = [link, link]
        event_storage.add_event(cause)
        event_storage.add_event(effect)

        links = event_storage.get_causal_links_for_event(effect.id)

        assert len(links) == 1

    def test_links_are_capped_per_event(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation, MAX_CAUSAL_LINKS_PER_EVENT

        effect = make_event(100, 2, "effect")
        causes = [make_event(100, 1, f"cause{i}") for i in range(MAX_CAUSAL_LINKS_PER_EVENT + 5)]
        for cause in causes:
            event_storage.add_event(cause)
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
            for cause in causes
        ]
        event_storage.add_event(effect)

        links = event_storage.get_causal_links_for_event(effect.id)

        assert len(links) == MAX_CAUSAL_LINKS_PER_EVENT

    def test_cleanup_cascades_links_of_the_deleted_event(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 1, "cause", is_major=True)
        effect = make_event(100, 2, "effect", is_major=False)
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        ]
        event_storage.add_event(cause)
        event_storage.add_event(effect)

        event_storage.cleanup(keep_major=True)

        assert event_storage.get_causal_links_for_event(effect.id) == []
        row = event_storage._conn.execute("SELECT COUNT(*) FROM event_causal_links").fetchone()
        assert row[0] == 0

    def test_cleanup_leaves_a_dangling_cause_event_id_readable(self, event_storage):
        from src.classes.causal_link import CausalLink, CausalRelation

        cause = make_event(100, 1, "cause", is_major=False)
        effect = make_event(100, 2, "effect", is_major=True)
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        ]
        event_storage.add_event(cause)
        event_storage.add_event(effect)

        deleted = event_storage.cleanup(keep_major=True)

        assert deleted == 1
        links = event_storage.get_causal_links_for_event(effect.id)
        assert len(links) == 1
        assert links[0].cause_event_id == cause.id
        # The cause row itself is gone; the link is still readable as a pruned reference.
        assert all(event.id != cause.id for event in event_storage.get_recent_events())


class TestEventStorageUpdateCausalPayloadSqlite:
    """Permanent SQLite-backed regression for EventStorage.update_causal_payload
    (task-4-review.md finding: verified ad hoc, not previously checked in).

    Exercises a real on-disk database across a close/reopen cycle -- an
    in-memory EventManager or a single long-lived connection could not catch
    a write that only looked persisted because the same process/connection
    was still holding it in a cache.
    """

    def test_update_causal_payload_persists_across_close_and_reopen(self, temp_db_path):
        from src.classes.event import FactKind

        storage = EventStorage(temp_db_path)
        decision_event = make_event(100, 1, "decision", ["a1"])
        decision_event.fact_kind = FactKind.DECISION
        decision_event.causal_payload = {
            "deltas": [],
            "decision": {"chosen_chain": [{"action_name": "Breakthrough", "params": {}}], "rejected": []},
        }
        storage.add_event(decision_event)
        storage.close()

        # Reopen a brand-new EventStorage instance on the same file -- this
        # is the cross-month scenario: the decision event was flushed in an
        # earlier process/step, and the rejection is captured later.
        storage = EventStorage(temp_db_path)
        updated_payload = {
            "deltas": [],
            "decision": {
                "chosen_chain": [{"action_name": "Breakthrough", "params": {}}],
                "rejected": [{"action_name": "Breakthrough", "params": {}, "reason": "Not at bottleneck"}],
            },
        }
        result = storage.update_causal_payload(decision_event.id, updated_payload)
        assert result is True
        storage.close()

        # Reopen again, with a fresh connection, and read it back through the
        # normal query path with include_decisions=True (the opt-in causal
        # query path), not a raw SELECT.
        storage = EventStorage(temp_db_path)
        page = storage.query_page(EventQuery(limit=100, include_decisions=True))
        storage.close()

        matching = [e for e in page.events if e.id == decision_event.id]
        assert len(matching) == 1
        assert matching[0].causal_payload["decision"]["rejected"] == [
            {"action_name": "Breakthrough", "params": {}, "reason": "Not at bottleneck"}
        ]

    def test_update_causal_payload_to_none_persists_across_reopen(self, temp_db_path):
        storage = EventStorage(temp_db_path)
        event = make_event(100, 1, "occurrence", ["a1"])
        event.causal_payload = {"deltas": [{"aspect": "population"}], "decision": None}
        storage.add_event(event)
        storage.close()

        storage = EventStorage(temp_db_path)
        assert storage.update_causal_payload(event.id, None) is True
        storage.close()

        storage = EventStorage(temp_db_path)
        events, _ = storage.get_events()
        storage.close()

        assert events[0].causal_payload is None

    def test_update_causal_payload_returns_false_when_storage_closed(self, temp_db_path):
        storage = EventStorage(temp_db_path)
        storage.close()

        assert storage.update_causal_payload("does-not-matter", {"deltas": []}) is False


class TestEventStorageCursorParsing:
    """Tests for cursor parsing edge cases."""

    def test_parse_cursor_valid(self, event_storage):
        """Test parsing a valid cursor."""
        month_stamp, rowid = event_storage._parse_cursor("1200_42")

        assert month_stamp == 1200
        assert rowid == 42

    def test_parse_cursor_invalid_format(self, event_storage):
        """Test parsing an invalid cursor raises ValueError."""
        with pytest.raises(ValueError):
            event_storage._parse_cursor("invalid")

    def test_make_cursor(self, event_storage):
        """Test cursor generation."""
        cursor = event_storage._make_cursor(1200, 42)

        assert cursor == "1200_42"


# --- EventManager Tests ---

class TestEventManagerWithStorage:
    """EventManager tests with SQLite storage."""

    def test_add_event(self, event_manager):
        """Test adding events through EventManager."""
        event = make_event(100, 5, "Test event", ["a1"])

        event_manager.add_event(event)

        assert event_manager.count() == 1

    def test_add_event_captures_subject_name_from_world_resolver(self, event_manager):
        event_manager.set_subject_resolver(
            lambda avatar_id: SimpleNamespace(name="Alice") if avatar_id == "a1" else None
        )
        event = make_event(100, 5, "Alice acted", ["a1"])

        event_manager.add_event(event)
        events = event_manager.get_recent_events()

        assert events[0].subject_snapshots == {"a1": "Alice"}

    def test_add_null_event_ignored(self, event_manager):
        """Test that NULL_EVENT is ignored."""
        event_manager.add_event(NULL_EVENT)

        assert event_manager.count() == 0

    def test_get_recent_events(self, event_manager):
        """Test getting recent events."""
        event_manager.add_event(make_event(100, 1, "First", ["a1"]))
        event_manager.add_event(make_event(100, 6, "Second", ["a1"]))

        events = event_manager.get_recent_events()

        assert len(events) == 2
        # Chronological order
        assert events[0].content == "First"
        assert events[1].content == "Second"

    def test_get_events_by_avatar(self, event_manager):
        """Test getting events by avatar."""
        event_manager.add_event(make_event(100, 1, "A1 event", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A2 event", ["a2"]))

        events = event_manager.get_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "A1 event"

    def test_get_events_between(self, event_manager):
        """Test getting events between two avatars."""
        event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))

        events = event_manager.get_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_major_events_by_avatar(self, event_manager):
        """Test getting major events for an avatar."""
        event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = event_manager.get_major_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Major"

    def test_get_minor_events_by_avatar(self, event_manager):
        """Test getting minor events for an avatar."""
        event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = event_manager.get_minor_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Minor"

    def test_get_major_events_between(self, event_manager):
        """Test getting major events between two avatars."""
        event_manager.add_event(make_event(100, 1, "Minor pair", ["a1", "a2"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major pair", ["a1", "a2"], is_major=True))

        events = event_manager.get_major_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "Major pair"

    def test_get_minor_events_between(self, event_manager):
        """Test getting minor events between two avatars."""
        event_manager.add_event(make_event(100, 1, "Minor pair", ["a1", "a2"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major pair", ["a1", "a2"], is_major=True))

        events = event_manager.get_minor_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "Minor pair"

    def test_get_event_appraisals_delegates_to_storage(self, event_manager):
        """Test that EventManager.get_event_appraisals delegates to EventStorage."""
        from src.classes.emotions import EmotionType
        from src.classes.event_appraisal import AppraisalSource, EventAppraisal

        event = make_event(100, 5, "An ambush occurred", ["avatar_1", "avatar_2"])
        event_manager.add_event(event)
        appraisal = EventAppraisal(
            event_id=event.id,
            appraiser_avatar_id="avatar_1",
            focus_avatar_id="avatar_2",
            personal_importance=0.8,
            valence=-0.5,
            persistence=0.4,
            primary_emotion=EmotionType.ANGRY,
            summary="Betrayed during the ambush.",
            source=AppraisalSource.LLM,
        )
        event_manager._storage.add_event_appraisal(appraisal)

        loaded = event_manager.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(event.month_stamp),
        )

        assert [a.id for a in loaded] == [appraisal.id]


class TestEventManagerPagination:
    """EventManager pagination tests."""

    def test_get_events_paginated_basic(self, event_manager):
        """Test basic pagination through EventManager."""
        for i in range(10):
            event_manager.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor, has_more = event_manager.get_events_paginated(limit=5)

        assert len(events) == 5
        assert cursor is not None
        assert has_more is True

    def test_get_events_paginated_with_filter(self, event_manager):
        """Test paginated query with avatar filter."""
        for i in range(10):
            avatar = "a1" if i % 2 == 0 else "a2"
            event_manager.add_event(make_event(100, i + 1, f"Event {i}", [avatar]))

        events, cursor, has_more = event_manager.get_events_paginated(avatar_id="a1", limit=3)

        assert len(events) == 3
        assert has_more is True
        for e in events:
            assert "a1" in e.related_avatars

    def test_get_events_paginated_with_pair_filter(self, event_manager):
        """Test paginated query with avatar pair filter."""
        event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))
        event_manager.add_event(make_event(100, 3, "A2 only", ["a2"]))

        events, _, _ = event_manager.get_events_paginated(avatar_id_pair=("a1", "a2"))

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_events_paginated_no_more(self, event_manager):
        """Test pagination when there are no more events."""
        event_manager.add_event(make_event(100, 1, "Event 1"))
        event_manager.add_event(make_event(100, 2, "Event 2"))

        events, cursor, has_more = event_manager.get_events_paginated(limit=10)

        assert len(events) == 2
        assert cursor is None
        assert has_more is False


class TestEventManagerMemoryMode:
    """EventManager tests in memory fallback mode."""

    def test_add_and_get_events(self, memory_event_manager):
        """Test basic operations in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Event 1", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "Event 2", ["a2"]))

        events = memory_event_manager.get_recent_events()

        assert len(events) == 2

    def test_get_events_by_avatar_memory(self, memory_event_manager):
        """Test avatar filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "A1 event", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "A2 event", ["a2"]))

        events = memory_event_manager.get_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "A1 event"

    def test_get_events_between_memory(self, memory_event_manager):
        """Test pair filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))

        events = memory_event_manager.get_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_major_events_memory(self, memory_event_manager):
        """Test major event filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        memory_event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = memory_event_manager.get_major_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Major"

    def test_get_event_appraisals_returns_empty_in_memory_mode(self, memory_event_manager):
        """Memory mode has no event_appraisals table; it must return [] rather than error."""
        memory_event_manager.add_event(make_event(100, 1, "An ambush occurred", ["a1", "a2"]))

        loaded = memory_event_manager.get_event_appraisals(
            appraiser_avatar_id="a1",
            current_month_stamp=100,
        )

        assert loaded == []

    def test_get_minor_events_memory(self, memory_event_manager):
        """Test minor event filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        memory_event_manager.add_event(make_event(100, 2, "Story", ["a1"], is_major=True, is_story=True))
        memory_event_manager.add_event(make_event(100, 3, "Major", ["a1"], is_major=True))

        events = memory_event_manager.get_minor_events_by_avatar("a1")

        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Minor" in contents
        assert "Story" in contents

    def test_pagination_memory_mode(self, memory_event_manager):
        """Memory mode follows the same opaque-cursor pagination contract as SQLite."""
        for i in range(10):
            memory_event_manager.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor, has_more = memory_event_manager.get_events_paginated(limit=5)

        assert len(events) == 5
        assert cursor is not None
        assert has_more is True

        next_events, next_cursor, next_has_more = memory_event_manager.get_events_paginated(
            limit=5,
            cursor=cursor,
        )
        assert len(next_events) == 5
        assert next_cursor is None
        assert next_has_more is False
        assert {event.id for event in events}.isdisjoint(event.id for event in next_events)

    def test_cleanup_memory_mode(self, memory_event_manager):
        """Test cleanup in memory mode clears all events."""
        memory_event_manager.add_event(make_event(100, 1, "Event 1"))
        memory_event_manager.add_event(make_event(100, 2, "Event 2"))

        deleted = memory_event_manager.cleanup()

        assert deleted == 2
        assert memory_event_manager.count() == 0


class TestEventManagerCleanup:
    """EventManager cleanup tests with SQLite storage."""

    def test_cleanup_delegates_to_storage(self, event_manager):
        """Test that cleanup delegates to storage."""
        event_manager.add_event(make_event(100, 1, "Minor", is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_manager.cleanup()

        assert deleted == 1
        assert event_manager.count() == 1


# --- Edge Cases ---

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_storage_closed_operations_fail_gracefully(self, temp_db_path):
        """Test that operations on closed storage fail gracefully."""
        storage = EventStorage(temp_db_path)
        storage.close()

        # Mock logger to suppress expected errors
        storage._logger = MagicMock()

        # Should return False/empty rather than throwing
        assert storage.add_event(make_event(100, 1, "Test")) is False
        events, cursor = storage.get_events()
        assert events == []
        assert storage.count() == 0

    def test_event_with_many_avatars(self, event_storage):
        """Test event with many related avatars."""
        avatar_ids = [f"avatar_{i}" for i in range(20)]
        event = make_event(100, 1, "Large group event", avatar_ids)

        event_storage.add_event(event)

        events, _ = event_storage.get_events()
        assert len(events) == 1
        assert set(events[0].related_avatars) == set(avatar_ids)

    def test_empty_content(self, event_storage):
        """Test event with empty content."""
        event = make_event(100, 1, "", ["a1"])

        result = event_storage.add_event(event)

        assert result is True
        events, _ = event_storage.get_events()
        assert events[0].content == ""

    def test_special_characters_in_content(self, event_storage):
        """Test event with special characters in content."""
        content = "测试中文 & 'quotes' \"double\" <tag> END"
        event = make_event(100, 1, content, ["a1"])

        event_storage.add_event(event)

        events, _ = event_storage.get_events()
        assert events[0].content == content

    def test_same_month_stamp_ordering(self, event_storage):
        """Test that events with same month_stamp maintain insertion order."""
        # Add multiple events in the same month
        for i in range(5):
            event_storage.add_event(make_event(100, 6, f"Event {i}"))

        events, _ = event_storage.get_events()

        # Should be in reverse insertion order (newest first)
        assert events[0].content == "Event 4"
        assert events[4].content == "Event 0"


class TestEventStorageThreadSafety:
    """Tests for thread-safe access around the shared SQLite connection."""

    def test_concurrent_add_event_calls_do_not_corrupt_storage(self, event_storage):
        """Concurrent writes should serialize cleanly and preserve all events."""
        total_events = 40

        def write_event(index: int) -> bool:
            return event_storage.add_event(
                make_event(
                    100 + (index % 3),
                    (index % 12) + 1,
                    f"Concurrent event {index}",
                    [f"avatar_{index % 5}"],
                    event_id=f"concurrent-{index}",
                )
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write_event, range(total_events)))

        assert all(results)
        assert event_storage.count() == total_events

        events, _ = event_storage.get_events(limit=total_events + 5)
        assert len(events) == total_events
        assert {event.id for event in events} == {f"concurrent-{i}" for i in range(total_events)}

    def test_concurrent_reads_and_writes_remain_usable(self, event_storage):
        """Mixed readers and writers should not throw or leave the store unusable."""
        preload_events = 12
        added_during_test = 18

        for i in range(preload_events):
            event_storage.add_event(
                make_event(
                    99,
                    (i % 12) + 1,
                    f"Seed event {i}",
                    [f"seed_avatar_{i % 3}"],
                    event_id=f"seed-{i}",
                )
            )

        def writer(index: int) -> bool:
            return event_storage.add_event(
                make_event(
                    101,
                    (index % 12) + 1,
                    f"Live event {index}",
                    [f"live_avatar_{index % 4}"],
                    is_major=(index % 2 == 0),
                    event_id=f"live-{index}",
                )
            )

        def reader(index: int) -> tuple[int, int, int]:
            all_events, _ = event_storage.get_events(limit=64)
            recent_for_avatar = event_storage.get_events_by_avatar(f"seed_avatar_{index % 3}", limit=10)
            major_for_avatar = event_storage.get_major_events_by_avatar(f"live_avatar_{index % 4}", limit=10)
            return len(all_events), len(recent_for_avatar), len(major_for_avatar)

        futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for i in range(added_during_test):
                futures.append(executor.submit(writer, i))
                futures.append(executor.submit(reader, i))

        results = [future.result() for future in futures]

        writer_results = results[0::2]
        reader_results = results[1::2]

        assert all(writer_results)
        assert all(isinstance(snapshot, tuple) and len(snapshot) == 3 for snapshot in reader_results)

        expected_total = preload_events + added_during_test
        assert event_storage.count() == expected_total

        final_events, _ = event_storage.get_events(limit=expected_total + 5)
        assert len(final_events) == expected_total


# --- EventAppraisal persistence tests ---

def make_appraisal(event_id: str, **overrides) -> EventAppraisal:
    defaults = dict(
        event_id=event_id,
        appraiser_avatar_id="avatar_1",
        focus_avatar_id="avatar_2",
        personal_importance=0.8,
        valence=-0.5,
        persistence=0.4,
        primary_emotion=EmotionType.ANGRY,
        summary="Betrayed during the ambush.",
        source=AppraisalSource.LLM,
    )
    defaults.update(overrides)
    return EventAppraisal(**defaults)


class TestEventAppraisalPersistence:
    """Tests for EventStorage's event_appraisals table."""

    def test_init_creates_event_appraisals_table_and_indexes(self, temp_db_path):
        storage = EventStorage(temp_db_path)

        tables = [
            row[0]
            for row in storage._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='event_appraisals'"
            ).fetchall()
        ]
        assert "event_appraisals" in tables

        indexes = {
            row[0]
            for row in storage._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='event_appraisals'"
            ).fetchall()
        }
        assert any("appraiser" in name for name in indexes)
        assert any("focus" in name for name in indexes)

        storage.close()

    def test_add_event_appraisal_round_trips(self, event_storage):
        event = make_event(100, 5, "An ambush occurred", ["avatar_1", "avatar_2"])
        event_storage.add_event(event)
        appraisal = make_appraisal(event.id)

        result = event_storage.add_event_appraisal(appraisal)
        assert result is True

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(event.month_stamp),
        )

        assert len(loaded) == 1
        restored = loaded[0]
        assert restored.id == appraisal.id
        assert restored.event_id == event.id
        assert restored.appraiser_avatar_id == "avatar_1"
        assert restored.focus_avatar_id == "avatar_2"
        assert restored.personal_importance == pytest.approx(0.8)
        assert restored.valence == pytest.approx(-0.5)
        assert restored.persistence == pytest.approx(0.4)
        assert restored.primary_emotion is EmotionType.ANGRY
        assert restored.summary == "Betrayed during the ambush."
        assert restored.source is AppraisalSource.LLM

    def test_add_event_appraisal_enforces_uniqueness(self, event_storage):
        event = make_event(100, 5, "An ambush occurred", ["avatar_1", "avatar_2"])
        event_storage.add_event(event)
        first = make_appraisal(event.id, summary="First take.")
        second = make_appraisal(event.id, summary="Second take.")

        event_storage.add_event_appraisal(first)
        event_storage.add_event_appraisal(second)

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(event.month_stamp),
        )
        assert len(loaded) == 1
        assert loaded[0].summary == "First take."

    def test_event_appraisal_cascades_on_event_delete(self, event_storage):
        event = make_event(100, 5, "An ambush occurred", ["avatar_1", "avatar_2"], event_id="doomed-event")
        event_storage.add_event(event)
        event_storage.add_event_appraisal(make_appraisal(event.id))

        with event_storage._transaction() as conn:
            conn.execute("DELETE FROM events WHERE id = ?", (event.id,))

        remaining = event_storage._conn.execute(
            "SELECT COUNT(*) FROM event_appraisals WHERE event_id = ?", (event.id,)
        ).fetchone()[0]
        assert remaining == 0

    def test_get_event_appraisals_filters_by_focus_avatar(self, event_storage):
        event = make_event(100, 5, "Two encounters", ["avatar_1", "avatar_2", "avatar_3"])
        event_storage.add_event(event)
        event_storage.add_event_appraisal(
            make_appraisal(event.id, focus_avatar_id="avatar_2")
        )
        event_storage.add_event_appraisal(
            make_appraisal(event.id, focus_avatar_id="avatar_3")
        )

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            focus_avatar_id="avatar_2",
            current_month_stamp=int(event.month_stamp),
        )

        assert len(loaded) == 1
        assert loaded[0].focus_avatar_id == "avatar_2"

    def test_get_event_appraisals_filters_by_minimum_effective_weight(self, event_storage):
        old_event = make_event(0, 1, "Long ago", ["avatar_1", "avatar_2"], event_id="old-event")
        recent_event = make_event(100, 1, "Recently", ["avatar_1", "avatar_2"], event_id="recent-event")
        event_storage.add_event(old_event)
        event_storage.add_event(recent_event)

        # Fully decayed (persistence=0, ~100 years old) -> low effective weight.
        event_storage.add_event_appraisal(
            make_appraisal(
                old_event.id,
                personal_importance=0.9,
                persistence=0.0,
            )
        )
        # Fresh appraisal -> high effective weight.
        event_storage.add_event_appraisal(
            make_appraisal(
                recent_event.id,
                personal_importance=0.9,
                persistence=0.0,
            )
        )

        current_month_stamp = int(recent_event.month_stamp)
        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=current_month_stamp,
            min_effective_weight=0.5,
        )

        assert len(loaded) == 1
        assert loaded[0].event_id == recent_event.id

    def test_get_event_appraisals_sorts_by_effective_weight_descending(self, event_storage):
        weak_event = make_event(0, 1, "Weak memory", ["avatar_1", "avatar_2"], event_id="weak-event")
        strong_event = make_event(100, 1, "Strong memory", ["avatar_1", "avatar_2"], event_id="strong-event")
        event_storage.add_event(weak_event)
        event_storage.add_event(strong_event)

        event_storage.add_event_appraisal(
            make_appraisal(weak_event.id, personal_importance=0.9, persistence=0.0)
        )
        event_storage.add_event_appraisal(
            make_appraisal(strong_event.id, personal_importance=0.9, persistence=0.0)
        )

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(strong_event.month_stamp),
        )

        assert [a.event_id for a in loaded] == [strong_event.id, weak_event.id]

    def test_get_event_appraisals_respects_limit_with_deterministic_tie_order(self, event_storage):
        event = make_event(100, 1, "Many focuses", ["avatar_1"])
        event_storage.add_event(event)
        for i in range(5):
            event_storage.add_event_appraisal(
                make_appraisal(event.id, focus_avatar_id=f"avatar_focus_{i}")
            )

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(event.month_stamp),
            limit=2,
        )

        # All five appraisals share the same event and the same weight, so the
        # tie must break deterministically (most-recently-inserted first)
        # rather than depend on unspecified SQLite row order.
        assert [a.focus_avatar_id for a in loaded] == ["avatar_focus_4", "avatar_focus_3"]

    def test_get_event_appraisals_returns_empty_for_unknown_appraiser(self, event_storage):
        event = make_event(100, 1, "Something happened", ["avatar_1", "avatar_2"])
        event_storage.add_event(event)
        event_storage.add_event_appraisal(make_appraisal(event.id))

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="unknown-avatar",
            current_month_stamp=int(event.month_stamp),
        )

        assert loaded == []

    def test_get_event_appraisals_preserves_positive_and_negative_across_events(self, event_storage):
        good_event = make_event(100, 1, "A reconciliation", ["avatar_1", "avatar_2"], event_id="good-event")
        bad_event = make_event(100, 2, "A betrayal", ["avatar_1", "avatar_2"], event_id="bad-event")
        event_storage.add_event(good_event)
        event_storage.add_event(bad_event)

        event_storage.add_event_appraisal(
            make_appraisal(good_event.id, valence=0.9, summary="Reconciled.")
        )
        event_storage.add_event_appraisal(
            make_appraisal(bad_event.id, valence=-0.9, summary="Betrayed.")
        )

        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1",
            current_month_stamp=int(bad_event.month_stamp),
        )

        valence_by_event = {a.event_id: a.valence for a in loaded}
        assert len(loaded) == 2
        assert valence_by_event[good_event.id] == pytest.approx(0.9)
        assert valence_by_event[bad_event.id] == pytest.approx(-0.9)

    def test_add_event_appraisal_rejects_orphan_event_id(self, event_storage):
        orphan = make_appraisal("does-not-exist")

        result = event_storage.add_event_appraisal(orphan)

        assert result is False
        count = event_storage._conn.execute(
            "SELECT COUNT(*) FROM event_appraisals"
        ).fetchone()[0]
        assert count == 0

    def test_add_event_persists_runtime_appraisals_atomically(self, event_storage):
        event = make_event(100, 5, "Something happened", ["avatar_1", "avatar_2"], event_id="atomic-event")
        appraisal = make_appraisal(event.id)
        event.appraisals.append(appraisal)

        result = event_storage.add_event(event)

        assert result is True
        loaded = event_storage.get_event_appraisals(
            appraiser_avatar_id=appraisal.appraiser_avatar_id,
            current_month_stamp=int(event.month_stamp),
        )
        assert [a.id for a in loaded] == [appraisal.id]

    def test_add_event_rolls_back_entirely_when_runtime_appraisal_is_invalid(self, event_storage):
        event = make_event(100, 5, "Something happened", ["avatar_1", "avatar_2"], event_id="broken-event")
        bad_appraisal = make_appraisal("some-other-nonexistent-event-id")
        event.appraisals.append(bad_appraisal)

        result = event_storage.add_event(event)

        assert result is False
        assert event_storage.count() == 0
        assert event_storage.get_event_by_id(event.id) is None

    def test_old_database_gets_empty_event_appraisals_table_without_backfill(self, temp_db_path):
        import sqlite3

        legacy_conn = sqlite3.connect(str(temp_db_path))
        legacy_conn.executescript(
            """
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                month_stamp INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_major BOOLEAN DEFAULT FALSE,
                is_story BOOLEAN DEFAULT FALSE,
                event_type TEXT DEFAULT '',
                render_key TEXT,
                render_params TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        legacy_conn.execute(
            "INSERT INTO events (id, month_stamp, content) VALUES ('legacy-1', 5, 'Old content')"
        )
        legacy_conn.commit()
        legacy_conn.close()

        storage = EventStorage(temp_db_path)

        loaded = storage.get_event_appraisals(
            appraiser_avatar_id="avatar_1", current_month_stamp=5
        )
        assert loaded == []

        count = storage._conn.execute("SELECT COUNT(*) FROM event_appraisals").fetchone()[0]
        assert count == 0

        storage.close()
