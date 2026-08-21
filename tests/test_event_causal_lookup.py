"""
Tests for the id-addressed causal lookups used by the `why` query (Task 5):

- EventStorage.get_event_by_id / EventManager.get_event_by_id
- EventStorage.get_causal_links_for_event / get_causal_links_caused_by (SQLite)
- EventManager.get_causal_links_for_event / get_causal_links_caused_by (in-memory backend)

These reads must bypass the default decision-event timeline filter (§5.4):
a `fact_kind=DECISION` event is a normal Event and the causal traversal reads
it by id regardless of the default page filter.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.event_storage import EventStorage
from src.sim.managers.event_manager import EventManager
from src.systems.time import Month, Year, create_month_stamp


def make_event(year: int, month: int, content: str, **kwargs) -> Event:
    return Event(month_stamp=create_month_stamp(Year(year), Month(month)), content=content, **kwargs)


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "events.db"


@pytest.fixture
def storage(temp_db_path):
    s = EventStorage(temp_db_path)
    yield s
    s.close()


class TestEventStorageGetEventById:
    def test_returns_none_for_unknown_id(self, storage):
        assert storage.get_event_by_id("does-not-exist") is None

    def test_returns_the_event_with_its_causal_fields(self, storage):
        event = make_event(100, 1, "cause")
        event.fact_kind = FactKind.DECISION
        event.causal_payload = {"deltas": [], "decision": {"id": "d1"}}
        storage.add_event(event)

        found = storage.get_event_by_id(event.id)

        assert found is not None
        assert found.id == event.id
        assert found.fact_kind == FactKind.DECISION
        assert found.causal_payload == {"deltas": [], "decision": {"id": "d1"}}

    def test_finds_a_decision_event_bypassing_the_default_timeline_filter(self, storage):
        decision = make_event(100, 1, "decision", fact_kind=FactKind.DECISION)
        storage.add_event(decision)

        # The default page hides decision events...
        page = storage.get_recent_events(limit=10)
        assert decision.id not in {e.id for e in page}

        # ...but a direct id lookup still finds it.
        assert storage.get_event_by_id(decision.id) is not None


class TestEventStorageCausalLinkLookups:
    def test_get_causal_links_for_event_and_caused_by(self, storage):
        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        ]
        storage.add_event(cause)
        storage.add_event(effect)

        as_effect = storage.get_causal_links_for_event(effect.id)
        as_cause = storage.get_causal_links_caused_by(cause.id)

        assert len(as_effect) == 1
        assert as_effect[0].cause_event_id == cause.id
        assert len(as_cause) == 1
        assert as_cause[0].event_id == effect.id

    def test_pruned_cause_still_returns_the_link_but_lookup_of_the_event_is_none(self, storage):
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id="ghost-id", relation=CausalRelation.TRIGGERED_BY)
        ]
        storage.add_event(effect)

        links = storage.get_causal_links_for_event(effect.id)
        assert len(links) == 1
        assert storage.get_event_by_id(links[0].cause_event_id) is None


class TestEventManagerInMemoryCausalLookups:
    """Mirror the SQLite behaviour for the in-memory fallback backend."""

    def test_get_event_by_id(self):
        manager = EventManager.create_in_memory()
        event = make_event(100, 1, "an event")
        manager.add_event(event)

        assert manager.get_event_by_id(event.id) is event
        assert manager.get_event_by_id("missing") is None

    def test_get_causal_links_for_event_and_caused_by(self):
        manager = EventManager.create_in_memory()
        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.ENABLED_BY)
        ]
        manager.add_event(cause)
        manager.add_event(effect)

        assert len(manager.get_causal_links_for_event(effect.id)) == 1
        assert len(manager.get_causal_links_caused_by(cause.id)) == 1
        assert manager.get_causal_links_for_event("missing") == []

    def test_get_event_by_id_finds_decision_event_bypassing_default_filter(self):
        manager = EventManager.create_in_memory()
        decision = make_event(100, 1, "decision", fact_kind=FactKind.DECISION)
        manager.add_event(decision)

        assert decision.id not in {e.id for e in manager.get_recent_events(limit=10)}
        assert manager.get_event_by_id(decision.id) is decision
