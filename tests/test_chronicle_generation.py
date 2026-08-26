from types import SimpleNamespace

import pytest

from src.classes.event import Event
from src.classes.causal_link import CausalLink
from src.classes.chronicle import ChronicleChapter, ChronicleParagraph, ChronicleSegment
from src.systems.chronicle_service import ChronicleService
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import llm_test_mode_scope
from src.utils.llm.exceptions import ProviderCallError, ProviderFailureKind


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
    async def call(*_args, **_kwargs):
        return {"title": "bad", "paragraphs": []}
    monkeypatch.setattr(service, "_call_model", call)
    assert await service.maybe_generate_chapter(world(3), [event(3, "known")]) is None


@pytest.mark.asyncio
async def test_bootstrap_window_is_current_and_two_preceding_months(monkeypatch):
    captured = {}
    service = ChronicleService()

    async def call(_world, infos):
        captured.update(infos)
        event_id = infos["events"][0]["id"]
        return {"title": "Bootstrap", "paragraphs": [{"source_event_ids": [event_id], "segments": [{"text": "fact"}]}]}

    monkeypatch.setattr(service, "_call_model", call)
    existing = [event(1, "one"), event(2, "two")]
    result = await service.maybe_generate_chapter(world(3, existing), [event(3, "three")])

    assert result is not None
    assert captured["start_month_stamp"] == 1
    assert [item["id"] for item in captured["events"]] == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_persisted_causal_links_are_available_to_prompt(monkeypatch):
    effect = event(3, "effect", major=True)
    cause = event(2, "cause")
    link = CausalLink(id="link", event_id="effect", cause_event_id="cause")
    manager = SimpleNamespace(
        get_latest_chronicle_chapter=lambda: None,
        get_events_between_months=lambda _start, _end: [cause, effect],
        get_causal_links_for_event=lambda event_id: [link] if event_id == "effect" else [],
    )
    captured = {}
    service = ChronicleService()

    async def call(_world, infos):
        captured.update(infos)
        return {"title": "Causal", "paragraphs": [{"source_event_ids": ["effect"], "segments": [{"text": "fact"}]}]}

    monkeypatch.setattr(service, "_call_model", call)
    await service.maybe_generate_chapter(SimpleNamespace(month_stamp=MonthStamp(3), event_manager=manager), [effect])

    effect_info = next(item for item in captured["events"] if item["id"] == "effect")
    assert effect_info["causal_source_event_ids"] == ["cause"]


@pytest.mark.asyncio
async def test_all_major_events_and_transitive_ancestors_survive_candidate_bound(monkeypatch):
    majors = [event(1, f"major-{idx}", major=True) for idx in range(65)]
    ancestor = event(1, "ancestor")
    majors[0].causal_links = [CausalLink(cause_event_id="ancestor")]
    captured = {}
    service = ChronicleService()

    async def call(_world, infos):
        captured.update(infos)
        return {"title": "Bounded", "paragraphs": [{"source_event_ids": ["major-0"], "segments": [{"text": "fact"}]}]}

    monkeypatch.setattr(service, "_call_model", call)
    result = await service.maybe_generate_chapter(world(3, majors + [ancestor]), [])

    assert result is not None
    supplied = {item["id"] for item in captured["events"]}
    assert {item.id for item in majors} | {"ancestor"} <= supplied


@pytest.mark.asyncio
async def test_entity_reference_target_is_validated(monkeypatch):
    source = event(3, "source", major=True)
    game_world = SimpleNamespace(
        month_stamp=MonthStamp(3),
        event_manager=SimpleNamespace(
            get_latest_chronicle_chapter=lambda: None,
            get_events_between_months=lambda _start, _end: [],
        ),
        avatar_manager=SimpleNamespace(avatars={"avatar-1": SimpleNamespace(id="avatar-1", name="A")}),
        map=SimpleNamespace(regions={}),
    )
    draft = {"title": "Entity", "paragraphs": [{
        "source_event_ids": ["source"],
        "segments": [{"text": "A acted", "reference": {
            "id": "avatar-anchor", "kind": "avatar", "label": "A", "target_id": "avatar-1",
            "claim_kind": None, "source_event_ids": ["source"],
        }}],
    }]}
    service = ChronicleService()
    async def call(_world, _infos):
        return draft
    monkeypatch.setattr(service, "_call_model", call)
    assert await service.maybe_generate_chapter(game_world, [source])


@pytest.mark.asyncio
async def test_unexpected_programming_error_propagates(monkeypatch):
    service = ChronicleService()
    async def fail(*_args):
        raise RuntimeError("bug")
    monkeypatch.setattr(service, "_call_model", fail)
    with pytest.raises(RuntimeError, match="bug"):
        await service.maybe_generate_chapter(world(3), [event(3, "major", major=True)])


@pytest.mark.asyncio
async def test_provider_failure_leaves_latest_window_unchanged_for_retry(monkeypatch):
    pending = event(5, "pending")
    old_chapter = ChronicleChapter(
        id="chapter-2", start_month_stamp=1, end_month_stamp=2, trigger="max_interval", title="Old",
        paragraphs=(ChronicleParagraph(segments=(ChronicleSegment(text="old"),), source_event_ids=("old",)),),
        source_event_ids=("old",), created_at=1.0,
    )
    manager = SimpleNamespace(
        get_latest_chronicle_chapter=lambda: old_chapter,
        get_events_between_months=lambda _start, _end: [pending],
    )
    service = ChronicleService()
    async def fail(*_args):
        raise ProviderCallError(ProviderFailureKind.NETWORK, "offline")
    monkeypatch.setattr(service, "_call_model", fail)
    assert await service.maybe_generate_chapter(SimpleNamespace(month_stamp=MonthStamp(5), event_manager=manager), []) is None
    assert manager.get_latest_chronicle_chapter().end_month_stamp == 2
