from __future__ import annotations

from pathlib import Path

import pytest

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.classes.event_storage import EventStorage
from src.classes.causal_origin import CausalOrigin
from src.sim.simulator_engine.context import SimulationStepContext
from src.sim.simulator_engine.finalizer import (
    CausalIntegrityError,
    validate_causal_integrity,
)
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


def test_decision_fact_requires_complete_agent_decision(base_world) -> None:
    event = Event(
        base_world.month_stamp,
        "invalid decision",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": []},
    )
    ctx = SimulationStepContext.create(base_world)

    with pytest.raises(CausalIntegrityError, match="must contain AgentDecision"):
        validate_causal_integrity(ctx, [event])


def test_llm_and_story_events_cannot_carry_state_deltas(base_world) -> None:
    fact = Event(base_world.month_stamp, "real source")
    interpretation = Event(
        base_world.month_stamp,
        "interpretation",
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"deltas": [{"aspect": "population"}]},
    )
    story = Event(
        base_world.month_stamp,
        "story",
        is_story=True,
        causal_payload={"deltas": [{"aspect": "population"}]},
        causal_links=[
            CausalLink(
                cause_event_id=fact.id,
                relation=CausalRelation.CONTRIBUTED_TO,
            )
        ],
    )
    ctx = SimulationStepContext.create(base_world)

    with pytest.raises(CausalIntegrityError, match="LLM interpretation"):
        validate_causal_integrity(ctx, [fact, interpretation])
    with pytest.raises(CausalIntegrityError, match="story event"):
        validate_causal_integrity(ctx, [fact, story])


def test_actor_transition_requires_real_decision_cause(base_world) -> None:
    non_decision = Event(base_world.month_stamp, "rumor")
    transition = Event(
        base_world.month_stamp,
        "mutated from rumor",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": [{"aspect": "population"}]},
        causal_links=[
            CausalLink(
                cause_event_id=non_decision.id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        ],
    )
    ctx = SimulationStepContext.create(base_world)

    with pytest.raises(CausalIntegrityError, match="real decision cause"):
        validate_causal_integrity(ctx, [non_decision, transition])


def test_audited_decision_can_author_actor_transition(base_world) -> None:
    decision = AgentDecision(
        month_stamp=int(base_world.month_stamp),
        subject_kind="population",
        subject_id="301",
        source="test",
        considered_count=1,
        chosen_chain=[{"action_name": "migrate", "params": {}}],
    )
    decision_event = Event(
        base_world.month_stamp,
        "population chose",
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": [], "decision": decision.to_dict()},
    )
    transition = Event(
        base_world.month_stamp,
        "population moved",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"deltas": [{"aspect": "population"}]},
        causal_links=[
            CausalLink(
                cause_event_id=decision_event.id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        ],
    )
    ctx = SimulationStepContext.create(base_world)

    validate_causal_integrity(ctx, [decision_event, transition])
