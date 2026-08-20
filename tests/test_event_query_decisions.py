"""
Decision events (fact_kind=DECISION) must be excluded from the default event
page, memory queries, and get_recent_events, in both storage backends -- and
included only when a caller explicitly opts in via EventQuery.include_decisions.

See docs/specs/causal-world-kernel.md section 5.4 "Consequence for the
timeline" and finding N2 (task-1-rereview.md) about get_recent_events.
"""
import tempfile
from pathlib import Path

import pytest

from src.classes.event import Event, FactKind
from src.classes.event_query import EventAudience, EventQuery
from src.classes.event_storage import EventStorage
from src.sim.managers.event_manager import EventManager
from src.systems.time import Year, Month, create_month_stamp


def make_event(
    year: int,
    month: int,
    content: str,
    avatar_ids: list[str] | None = None,
    fact_kind: FactKind = FactKind.OCCURRENCE,
) -> Event:
    return Event(
        month_stamp=create_month_stamp(Year(year), Month(month)),
        content=content,
        related_avatars=avatar_ids,
        fact_kind=fact_kind,
    )


@pytest.fixture
def event_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = EventStorage(Path(tmpdir) / "events.db")
        yield storage
        storage.close()


@pytest.fixture
def event_manager(event_storage):
    return EventManager(storage=event_storage)


@pytest.fixture
def memory_event_manager():
    return EventManager.create_in_memory()


class TestEventStorageDecisionFilter:
    def test_default_page_excludes_decision_events(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        page = event_storage.query_page(EventQuery(limit=100))

        assert len(page.events) == 1
        assert page.events[0].fact_kind == FactKind.OCCURRENCE

    def test_include_decisions_opts_in(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        page = event_storage.query_page(EventQuery(limit=100, include_decisions=True))

        assert len(page.events) == 2

    def test_avatar_scoped_page_excludes_decision_events(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        page = event_storage.query_page(EventQuery(avatar_ids=("a1",), limit=100))

        assert len(page.events) == 1

    def test_observed_page_excludes_decision_events(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        page = event_storage.query_page(
            EventQuery(avatar_ids=("a1",), audience=EventAudience.OBSERVED, limit=100)
        )

        assert len(page.events) == 1

    def test_get_recent_events_excludes_decision_events_by_default(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = event_storage.get_recent_events(limit=100)

        assert len(events) == 1
        assert events[0].fact_kind == FactKind.OCCURRENCE

    def test_get_recent_events_include_decisions_opts_in(self, event_storage):
        event_storage.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_storage.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = event_storage.get_recent_events(limit=100, include_decisions=True)

        assert len(events) == 2


class TestEventManagerDecisionFilterStorage:
    def test_get_recent_events_excludes_decisions(self, event_manager):
        event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = event_manager.get_recent_events(limit=100)

        assert len(events) == 1

    def test_get_events_paginated_excludes_decisions_by_default(self, event_manager):
        event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events, _, _ = event_manager.get_events_paginated(limit=100)

        assert len(events) == 1

    def test_get_events_by_avatar_excludes_decisions(self, event_manager):
        event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = event_manager.get_events_by_avatar("a1")

        assert len(events) == 1


class TestEventManagerDecisionFilterMemory:
    def test_get_recent_events_excludes_decisions_in_memory(self, memory_event_manager):
        memory_event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = memory_event_manager.get_recent_events(limit=100)

        assert len(events) == 1

    def test_get_recent_events_include_decisions_in_memory(self, memory_event_manager):
        memory_event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = memory_event_manager.get_recent_events(limit=100, include_decisions=True)

        assert len(events) == 2

    def test_query_page_excludes_decisions_in_memory(self, memory_event_manager):
        memory_event_manager.add_event(make_event(100, 1, "occurrence", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "decision", ["a1"], fact_kind=FactKind.DECISION))

        events = memory_event_manager.get_events_by_avatar("a1")

        assert len(events) == 1
