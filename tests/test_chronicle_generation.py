from types import SimpleNamespace

import pytest

from src.classes.event import Event
from src.classes.chronicle import ChronicleChapter
from src.systems.chronicle_service import ChronicleService
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import llm_test_mode_scope


def event(month: int, event_id: str, *, major: bool = False, story: bool = False) -> Event:
    return Event(MonthStamp(month), event_id, is_major=major, is_story=story, id=event_id, created_at=float(month))


def world(month: int, events: list[Event] | None = None):
    return SimpleNamespace(
        month_stamp=MonthStamp(month),
        event_manager=SimpleNamespace(
            get_latest_chronicle_chapter=lambda: None,
            get_events_between_months=lambda _start, _end: list(events or []),
        ),
    )


@pytest.mark.asyncio
async def test_generation_returns_none_before_three_month_interval():
    service = ChronicleService()
    assert await service.maybe_generate_chapter(world(1), [event(1, "minor")]) is None
    assert await service.maybe_generate_chapter(world(2), [event(2, "minor")]) is None


@pytest.mark.asyncio
async def test_generation_uses_major_event_immediately_and_excludes_story():
    with llm_test_mode_scope(True):
        result = await ChronicleService().maybe_generate_chapter(
            world(2), [event(2, "story", major=True, story=True), event(2, "major", major=True)]
        )

    assert isinstance(result, ChronicleChapter)
    assert result.trigger == "major_event"
    assert result.source_event_ids == ("major",)


@pytest.mark.asyncio
async def test_generation_rejects_unknown_and_duplicate_sources(monkeypatch):
    service = ChronicleService()
    monkeypatch.setattr(service, "_call_model", lambda *_args, **_kwargs: {"title": "bad", "paragraphs": []})
    assert await service.maybe_generate_chapter(world(3), [event(3, "known")]) is None
