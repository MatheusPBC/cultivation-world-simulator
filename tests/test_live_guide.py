from types import SimpleNamespace

import pytest

from src.classes.chronicle import ChronicleChapter, ChronicleParagraph, ChronicleSegment
from src.classes.event import Event
from src.server.api.public_v1.query import LiveGuideQuestionRequest, create_public_query_router
from src.server.services.game_query_service import GameQueryService
from src.systems.live_guide_service import answer_live_guide, build_live_guide
from src.systems.time import MonthStamp
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _event(event_id: str, content: str, *, major: bool = True, event_type: str = "") -> Event:
    return Event(
        MonthStamp(24),
        content,
        related_avatars=["avatar-1"],
        is_major=major,
        event_type=event_type,
        id=event_id,
        created_at=1.0,
    )


def _serialize(events, *, world=None):
    return [
        {
            **event.to_dict(),
            "subjects": [{"type": "avatar", "id": "avatar-1", "name": "Lin"}],
        }
        for event in events
    ]


def _world(source: Event, chapter: ChronicleChapter | None = None):
    return SimpleNamespace(
        month_stamp=MonthStamp(24),
        run_config_snapshot={"content_locale": "pt-BR"},
        event_manager=SimpleNamespace(
            get_latest_chronicle_chapter=lambda: chapter,
            get_event_by_id=lambda event_id: source if event_id == source.id else None,
        ),
    )


def test_live_guide_projects_chronicle_sources_people_and_context():
    source = _event("war-1", "Lin iniciou uma guerra entre seitas.", event_type="sect_war")
    chapter = ChronicleChapter(
        id="chapter-1",
        start_month_stamp=24,
        end_month_stamp=24,
        trigger="major_event",
        title="A fronteira rompeu",
        paragraphs=(
            ChronicleParagraph(
                segments=(ChronicleSegment(text="Lin iniciou uma guerra entre seitas."),),
                source_event_ids=(source.id,),
            ),
        ),
        source_event_ids=(source.id,),
        created_at=1.0,
    )
    guide = build_live_guide(
        _world(source, chapter),
        journal={
            "highlights": [],
            "ongoing": [{
                "avatar_id": "avatar-1",
                "avatar_name": "Lin",
                "action": "Marchando",
                "event_count": 4,
                "short_term_objective": "Cruzar a fronteira",
                "long_term_objective": "Unificar as seitas",
            }],
        },
        serialize_events_for_client=_serialize,
    )

    assert guide["headline"] == "A fronteira rompeu"
    assert guide["threads"][0]["severity"] == "critical"
    assert guide["threads"][0]["primary_event_id"] == "war-1"
    assert guide["threads"][0]["subjects"] == [{"kind": "avatar", "id": "avatar-1", "name": "Lin"}]
    assert guide["people"][0]["ambition"] == "Unificar as seitas"
    assert guide["concept"]["term_key"] == "WORLD_INFO_BATTLE"


def test_live_guide_does_not_let_a_stale_chapter_hide_current_highlights():
    stale = Event(MonthStamp(18), "Uma história antiga.", id="old", created_at=1.0)
    current = _event("current", "Lin tomou a fortaleza.", event_type="battle")
    chapter = ChronicleChapter(
        id="old-chapter", start_month_stamp=18, end_month_stamp=18, trigger="max_interval",
        title="Um passado distante",
        paragraphs=(ChronicleParagraph(
            segments=(ChronicleSegment(text=stale.content),), source_event_ids=(stale.id,),
        ),),
        source_event_ids=(stale.id,), created_at=1.0,
    )
    events = {stale.id: stale, current.id: current}
    game_world = SimpleNamespace(
        month_stamp=MonthStamp(24),
        event_manager=SimpleNamespace(
            get_latest_chronicle_chapter=lambda: chapter,
            get_event_by_id=lambda event_id: events.get(event_id),
        ),
    )
    guide = build_live_guide(
        game_world,
        journal={
            "period": {"start_month_stamp": 22},
            "highlights": _serialize([current]),
            "ongoing": [],
        },
        serialize_events_for_client=_serialize,
    )

    assert guide["headline"] == "Lin tomou a fortaleza."
    assert [thread["primary_event_id"] for thread in guide["threads"]] == ["current"]
    assert guide["source_event_ids"] == ["current"]


@pytest.mark.asyncio
async def test_live_guide_question_uses_test_mode_fallback_without_provider():
    source = _event("fact-1", "Lin avançou para a fronteira.")
    guide = {"date": {"year": 2, "month": 1}, "headline": "Avanço", "source_event_ids": [source.id]}

    with llm_test_mode_scope(True):
        answer = await answer_live_guide(_world(source), question="O que mudou?", guide=guide)

    assert answer == {
        "answer": "Lin avançou para a fronteira.",
        "source_event_ids": ["fact-1"],
        "mode": "generated",
    }


@pytest.mark.asyncio
async def test_live_guide_rejects_unknown_model_citation_and_falls_back(monkeypatch):
    source = _event("fact-1", "Lin avançou para a fronteira.")
    guide = {"date": {"year": 2, "month": 1}, "headline": "Avanço", "source_event_ids": [source.id]}

    async def invalid_answer(*_args, **_kwargs):
        return {"answer": "Inventado", "source_event_ids": ["unknown"]}

    monkeypatch.setattr("src.systems.live_guide_service.call_llm_with_task_name", invalid_answer)
    answer = await answer_live_guide(_world(source), question="O que mudou?", guide=guide)

    assert answer["mode"] == "fallback"
    assert answer["answer"] == source.content
    assert answer["source_event_ids"] == [source.id]


@pytest.mark.asyncio
async def test_query_service_and_router_expose_live_guide_as_read_only_query():
    calls = []
    deps = SimpleNamespace(
        runtime={"world": object()},
        serialize_events_for_client=_serialize,
        get_live_guide_query=lambda runtime, **kwargs: calls.append(("get", runtime, kwargs)) or {"threads": []},
        ask_live_guide_query=lambda runtime, **kwargs: _async_result(calls, runtime, kwargs),
    )
    service = GameQueryService(deps)
    router = create_public_query_router(query_service=service)
    routes = {route.path: route.endpoint for route in router.routes}

    assert routes["/api/v1/query/world/live-guide"]() == {"ok": True, "data": {"threads": []}}
    result = await routes["/api/v1/query/world/live-guide/ask"](
        LiveGuideQuestionRequest(question="Quem importa?")
    )

    assert result == {"ok": True, "data": {"answer": "grounded"}}
    assert [item[0] for item in calls] == ["get", "ask"]
    assert calls[1][2]["question"] == "Quem importa?"


async def _async_result(calls, runtime, kwargs):
    calls.append(("ask", runtime, kwargs))
    return {"answer": "grounded"}
