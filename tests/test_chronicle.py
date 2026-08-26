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
