"""Direct tests for the World Chronicle query API.

These tests intentionally invoke the query builders and route callables
directly. The local FastAPI/Starlette/AnyIO combination hangs when sync
routes are dispatched through a TestClient thread pool.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.classes.causal_link import CausalLink
from src.classes.chronicle import (
    ChronicleChapter,
    ChronicleParagraph,
    ChronicleReference,
    ChronicleSegment,
)
from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.event import Event
from src.server.api.public_v1.query import create_public_query_router
from src.server.services.game_queries import get_chronicle_dossier, get_world_chronicle
from src.server.services.game_query_service import GameQueryService
from src.systems.time import MonthStamp


def _map() -> Map:
    game_map = Map(width=4, height=4)
    for x in range(4):
        for y in range(4):
            game_map.create_tile(x, y, TileType.PLAIN)
    return game_map


def _event(event_id: str, month: int, *, created_at: float | None = None) -> Event:
    return Event(
        MonthStamp(month),
        event_id,
        id=event_id,
        created_at=float(month) if created_at is None else created_at,
    )


def _chapter(chapter_id: str, end_month: int, reference: ChronicleReference) -> ChronicleChapter:
    paragraph = ChronicleParagraph(
        segments=(ChronicleSegment(text="Claim", reference=reference),),
        source_event_ids=reference.source_event_ids,
    )
    return ChronicleChapter(
        id=chapter_id,
        start_month_stamp=end_month,
        end_month_stamp=end_month,
        trigger="major_event",
        title="Chapter",
        paragraphs=(paragraph,),
        source_event_ids=reference.source_event_ids,
        created_at=float(end_month),
    )


def _serialize(events, *, world=None):
    return [event.to_dict() for event in events]


@pytest.fixture
def world(tmp_path: Path):
    game_world = World.create_with_db(
        map=_map(),
        month_stamp=MonthStamp(1200),
        events_db_path=tmp_path / "events.db",
    )
    yield game_world
    game_world.event_manager.close()


@pytest.fixture
def runtime(world):
    return {"world": world}


def _reference(anchor_id: str, event_id: str | None, *source_ids: str, claim_kind="fact"):
    return ChronicleReference(
        anchor_id,
        "event",
        "Event claim",
        event_id,
        claim_kind,
        source_ids,
    )


def _error_code(callable_, *args, **kwargs) -> str:
    with pytest.raises(HTTPException) as caught:
        callable_(*args, **kwargs)
    assert isinstance(caught.value.detail, dict)
    return caught.value.detail["code"]


def test_chronicle_list_is_newest_first_and_cursor_paginated(runtime, world):
    for month in (1, 2, 3):
        source_id = f"event-{month}"
        world.event_manager.add_event(_event(source_id, month))
        world.event_manager.append_chronicle_chapter(
            _chapter(f"chapter-{month}", month, _reference("anchor", source_id, source_id))
        )

    first = get_world_chronicle(runtime, cursor=None, limit=2)
    assert [item["id"] for item in first["chapters"]] == ["chapter-3", "chapter-2"]
    assert first["has_more"] is True
    second = get_world_chronicle(runtime, cursor=first["next_cursor"], limit=2)
    assert [item["id"] for item in second["chapters"]] == ["chapter-1"]


def test_chronicle_list_clamps_limit_and_empty_world(runtime):
    assert get_world_chronicle(runtime, cursor=None, limit=0) == {
        "chapters": [],
        "next_cursor": None,
        "has_more": False,
    }
    assert get_world_chronicle(runtime, cursor=None, limit=999)["chapters"] == []
    assert _error_code(get_world_chronicle, runtime, cursor="not-a-month", limit=20) == "INVALID_CHRONICLE_CURSOR"


def test_dossier_supports_fact_and_returns_chronological_deduplicated_sequence(runtime, world):
    root = _event("root", 1, created_at=3)
    middle = _event("middle", 2, created_at=2)
    focal = _event("focal", 3, created_at=1)
    focal.causal_links = [CausalLink(event_id="focal", cause_event_id="middle")]
    middle.causal_links = [CausalLink(event_id="middle", cause_event_id="root")]
    for item in (root, middle, focal):
        world.event_manager.add_event(item)
    reference = _reference("anchor", "focal", "focal", "middle")
    world.event_manager.append_chronicle_chapter(_chapter("chapter-1", 3, reference))

    data = get_chronicle_dossier(
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="chapter-1",
        anchor_id="anchor",
        depth=3,
        limit=40,
    )
    assert data["chapter_id"] == "chapter-1"
    assert data["anchor"] == reference.to_dict()
    assert data["focal_event"]["id"] == "focal"
    assert [item["id"] for item in data["sequence"]] == ["root", "middle", "focal"]
    assert data["pruned_source_ids"] == []
    assert data["truncated"] is False


def test_dossier_supports_inference_and_explicit_pruning(runtime, world):
    source = _event("source", 1)
    source.causal_links = [CausalLink(event_id="source", cause_event_id="missing-ancestor")]
    world.event_manager.add_event(source)
    reference = _reference("inference", None, "source", "missing", claim_kind="inference")
    world.event_manager.append_chronicle_chapter(_chapter("chapter-1", 1, reference))

    data = get_chronicle_dossier(
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="chapter-1",
        anchor_id="inference",
        depth=3,
        limit=40,
    )
    assert data["focal_event"] is None
    assert [item["id"] for item in data["sequence"]] == ["source"]
    assert data["pruned_source_ids"] == ["missing", "missing-ancestor"]


def test_dossier_rejects_entity_anchor_and_reports_missing_resources(runtime, world):
    entity_ref = ChronicleReference("avatar", "avatar", "Avatar", "avatar-1", None, ("source",))
    world.event_manager.add_event(_event("source", 1))
    world.event_manager.append_chronicle_chapter(_chapter("chapter-1", 1, entity_ref))
    assert _error_code(
        get_chronicle_dossier,
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="chapter-1",
        anchor_id="avatar",
        depth=3,
        limit=40,
    ) == "CHRONICLE_ANCHOR_INVALID"
    assert _error_code(
        get_chronicle_dossier,
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="nope",
        anchor_id="nope",
        depth=3,
        limit=40,
    ) == "CHAPTER_NOT_FOUND"
    assert _error_code(
        get_chronicle_dossier,
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="chapter-1",
        anchor_id="nope",
        depth=3,
        limit=40,
    ) == "ANCHOR_NOT_FOUND"


def test_dossier_is_bounded_and_cycle_safe(runtime, world):
    a = _event("a", 1)
    b = _event("b", 2)
    c = _event("c", 3)
    a.causal_links = [CausalLink(event_id="a", cause_event_id="b")]
    b.causal_links = [
        CausalLink(event_id="b", cause_event_id="a"),
        CausalLink(event_id="b", cause_event_id="c"),
    ]
    for item in (a, b, c):
        world.event_manager.add_event(item)
    world.event_manager.append_chronicle_chapter(
        _chapter("chapter-1", 3, _reference("anchor", "a", "a"))
    )
    data = get_chronicle_dossier(
        runtime,
        serialize_events_for_client=_serialize,
        chapter_id="chapter-1",
        anchor_id="anchor",
        depth=1,
        limit=1,
    )
    assert len(data["sequence"]) == 1
    assert data["truncated"] is True


def test_query_service_wires_chronicle_builders_and_router_callables(runtime):
    calls = []
    deps = SimpleNamespace(
        runtime=runtime,
        serialize_events_for_client=_serialize,
        get_world_chronicle_query=lambda runtime, **kwargs: calls.append(("list", runtime, kwargs)) or {"chapters": []},
        get_chronicle_dossier_query=lambda runtime, **kwargs: calls.append(("dossier", runtime, kwargs)) or {"chapter_id": "c"},
    )
    service = GameQueryService(deps)
    assert service.get_world_chronicle(cursor=None, limit=20) == {"chapters": []}
    assert service.get_chronicle_dossier(chapter_id="c", anchor_id="a", depth=3, limit=40) == {"chapter_id": "c"}
    assert [kind for kind, _, _ in calls] == ["list", "dossier"]

    router = create_public_query_router(query_service=service)
    routes = {route.path: route.endpoint for route in router.routes}
    assert "/api/v1/query/world/chronicle" in routes
    assert "/api/v1/query/world/chronicle/{chapter_id}/anchors/{anchor_id}/dossier" in routes
    assert routes["/api/v1/query/world/chronicle"](cursor="12", limit=7) == {"ok": True, "data": {"chapters": []}}
    assert routes["/api/v1/query/world/chronicle/{chapter_id}/anchors/{anchor_id}/dossier"](
        chapter_id="c", anchor_id="a", depth=2, limit=5
    ) == {"ok": True, "data": {"chapter_id": "c"}}
