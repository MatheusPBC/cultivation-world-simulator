from pathlib import Path

import pytest

from src.classes.chronicle import (
    ChronicleChapter,
    ChronicleParagraph,
    ChronicleReference,
    ChronicleSegment,
)
from src.classes.event import Event
from src.classes.event_storage import EventStorage
from src.systems.time import MonthStamp


def make_chapter(end_month: int, chapter_id: str | None = None) -> ChronicleChapter:
    reference = ChronicleReference(
        id="anchor-1",
        kind="event",
        label="A factual event",
        target_id="event-1",
        claim_kind="fact",
        source_event_ids=("event-1",),
    )
    paragraph = ChronicleParagraph(
        segments=(ChronicleSegment(text="An event occurred. "), ChronicleSegment(text="Claim", reference=reference)),
        source_event_ids=("event-1",),
    )
    return ChronicleChapter(
        id=chapter_id or f"chapter-{end_month}",
        start_month_stamp=end_month - 1,
        end_month_stamp=end_month,
        trigger="major_event",
        title="A chapter",
        paragraphs=(paragraph,),
        source_event_ids=("event-1",),
        created_at=1234.5,
    )


def test_chronicle_json_round_trip_is_immutable():
    chapter = make_chapter(10)
    restored = ChronicleChapter.from_dict(chapter.to_dict())

    assert restored == chapter
    with pytest.raises((AttributeError, TypeError)):
        chapter.title = "changed"


def test_chronicle_rejects_structurally_empty_chapter():
    with pytest.raises(ValueError):
        ChronicleChapter(
            id="empty",
            start_month_stamp=1,
            end_month_stamp=1,
            trigger="major_event",
            title="",
            paragraphs=(),
            source_event_ids=(),
            created_at=1.0,
        )


def test_chronicle_rejects_invalid_enum_values():
    with pytest.raises(ValueError):
        ChronicleReference(
            id="bad",
            kind="unknown",  # type: ignore[arg-type]
            label="Bad",
            target_id=None,
            claim_kind=None,
            source_event_ids=("event-1",),
        )


def test_storage_append_is_append_only_and_duplicate_end_month_does_not_overwrite(tmp_path: Path):
    storage = EventStorage(tmp_path / "events.db")
    original = make_chapter(10, "original")
    replacement = make_chapter(10, "replacement")

    assert storage.append_chronicle_chapter(original) is True
    assert storage.append_chronicle_chapter(replacement) is False
    assert storage.get_latest_chronicle_chapter() == original
    storage.close()


def test_storage_step_commit_rolls_back_events_when_chapter_insert_fails(
    tmp_path: Path,
    monkeypatch,
):
    storage = EventStorage(tmp_path / "events.db")
    event = Event(MonthStamp(1), "fact", id="event-1")
    chapter = make_chapter(1)

    def fail_chapter(_chapter):
        raise RuntimeError("chapter write failed")

    monkeypatch.setattr(storage, "_insert_chronicle_chapter", fail_chapter, raising=False)

    assert storage.commit_step([event], chapter) is False
    assert storage.get_event_by_id(event.id) is None
    assert storage.get_latest_chronicle_chapter() is None
    storage.close()


def test_storage_step_commit_persists_events_and_chapter_together(tmp_path: Path):
    storage = EventStorage(tmp_path / "events.db")
    event = Event(MonthStamp(1), "fact", id="event-1")
    chapter = make_chapter(1)

    assert storage.commit_step([event], chapter) is True
    restored_event = storage.get_event_by_id(event.id)
    assert restored_event is not None
    assert restored_event.id == event.id
    assert restored_event.content == event.content
    assert storage.get_latest_chronicle_chapter() == chapter
    storage.close()


def test_storage_paginates_newest_first_and_survives_reopen_and_event_cleanup(tmp_path: Path):
    db_path = tmp_path / "events.db"
    storage = EventStorage(db_path)
    for month in (1, 2, 3):
        storage.append_chronicle_chapter(make_chapter(month))
    storage.add_event(Event(MonthStamp(1), "old", id="event-1"))
    assert storage.get_chronicle_chapters_page(None, 2) == (
        [make_chapter(3), make_chapter(2)],
        "2",
        True,
    )
    page, cursor, has_more = storage.get_chronicle_chapters_page(cursor="2", limit=2)
    assert [chapter.end_month_stamp for chapter in page] == [1]
    assert cursor is None and has_more is False
    storage.cleanup(keep_major=False, before_month_stamp=2)
    storage.close()

    reopened = EventStorage(db_path)
    assert reopened.get_latest_chronicle_chapter() == make_chapter(3)
    assert reopened.get_chronicle_chapters_page(None, 20)[0]
    reopened.close()


def test_event_manager_delegates_chronicle_and_month_queries(tmp_path: Path):
    from src.sim.managers.event_manager import EventManager

    manager = EventManager.create_with_db(tmp_path / "events.db")
    manager.add_event(Event(MonthStamp(2), "current", id="event-2"))
    manager.add_event(Event(MonthStamp(3), "later", id="event-3"))
    chapter = make_chapter(3)
    assert manager.append_chronicle_chapter(chapter) is True
    assert manager.get_latest_chronicle_chapter() == chapter
    assert [event.id for event in manager.get_events_between_months(2, 3)] == ["event-2", "event-3"]
    manager.close()


def test_in_memory_step_commit_rejects_missing_chapter_source_without_partial_event():
    from src.sim.managers.event_manager import EventManager

    manager = EventManager.create_in_memory()
    event = Event(MonthStamp(1), "different fact", id="event-2")
    chapter = make_chapter(1)

    assert manager.commit_step([event], chapter) is False
    assert manager.get_event_by_id(event.id) is None
    assert manager.get_latest_chronicle_chapter() is None


def test_finalizer_does_not_publish_when_a_chapter_source_failed_to_persist():
    from types import SimpleNamespace
    from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
    from src.sim.simulator_engine.context import SimulationStepContext

    chapter = make_chapter(1)
    event_manager = SimpleNamespace(
        commit_step=lambda _events, _chapter: False,
    )
    fake_world = SimpleNamespace(
        avatar_manager=SimpleNamespace(avatars={}),
        event_manager=event_manager,
        month_stamp=MonthStamp(1),
    )
    ctx = SimulationStepContext.__new__(SimulationStepContext)
    ctx.world = fake_world
    ctx.events = [Event(MonthStamp(1), "fact", id="event-1")]
    ctx.causal = SimpleNamespace(attach_to=lambda _events: None)
    ctx.pending_chronicle_chapter = chapter

    with pytest.raises(EventPersistenceError):
        finalize_step(ctx)
    assert ctx.pending_chronicle_chapter is chapter
    assert fake_world.month_stamp == MonthStamp(1)
