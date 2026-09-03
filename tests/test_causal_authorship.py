from __future__ import annotations

from pathlib import Path

from src.classes.event import Event, FactKind
from src.classes.event_storage import EventStorage
from src.classes.causal_origin import CausalOrigin
from src.systems.time import Month, Year, create_month_stamp


def _event(event_id: str, *, origin: CausalOrigin) -> Event:
    return Event(
        month_stamp=create_month_stamp(Year(100), Month(1)),
        content=event_id,
        id=event_id,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=origin,
    )


def test_causal_origin_is_orthogonal_and_round_trips_in_event_dict() -> None:
    event = _event("llm-event", origin=CausalOrigin.LLM_INTERPRETATION)

    restored = Event.from_dict(event.to_dict())

    assert event.to_dict()["causal_origin"] == "llm_interpretation"
    assert restored.causal_origin is CausalOrigin.LLM_INTERPRETATION
    assert restored.fact_kind is FactKind.STATE_TRANSITION


def test_causal_origin_round_trips_through_sqlite(tmp_path: Path) -> None:
    storage = EventStorage(tmp_path / "events.db")
    event = _event("external-event", origin=CausalOrigin.EXTERNAL_EVENT)

    assert storage.add_event(event) is True

    restored = storage.get_event_by_id(event.id)

    assert restored is not None
    assert restored.causal_origin is CausalOrigin.EXTERNAL_EVENT
    storage.close()


def test_material_action_origin_is_explicit() -> None:
    from types import SimpleNamespace

    from src.systems.population_transfer import _blocked_event

    event = _blocked_event(
        SimpleNamespace(month_stamp=1),
        origin=SimpleNamespace(id=1, name="City"),
        condition=SimpleNamespace(id="condition"),
        condition_definition=SimpleNamespace(id="definition"),
        decision_event_id="decision",
        reason="no destination",
        measurements=[],
    )

    assert event.causal_origin is CausalOrigin.ACTOR_DECISION


def test_public_event_dto_exposes_causal_origin() -> None:
    from src.server.serialization import serialize_events_for_client

    event = _event("actor-event", origin=CausalOrigin.ACTOR_DECISION)

    payload = serialize_events_for_client([event])[0]

    assert payload["causal_origin"] == "actor_decision"
