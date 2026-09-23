from types import SimpleNamespace

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.sim.medieval.events import WorldEvent
from tools import medieval_causal_audit


def _event(sequence, *, fact_kind=FactKind.OCCURRENCE,
           causal_origin=CausalOrigin.DETERMINISTIC, decision=None,
           causal_payload=None, deltas=(), causes=()):
    event_id = f"event:{sequence}"
    links = tuple(
        CausalLink(id=f"{event_id}:cause:{index}", event_id=event_id,
                   cause_event_id=cause_id, relation=CausalRelation.TRIGGERED_BY)
        for index, cause_id in enumerate(causes)
    )
    return WorldEvent(
        id=event_id, day=1, sequence=sequence, event_type="audit_fixture",
        content="Audit fixture", fact_kind=fact_kind, causal_origin=causal_origin,
        decision=decision, causal_payload=causal_payload, deltas=tuple(deltas),
        causal_links=links,
    )


def test_audit_uses_index_and_preserves_broken_cause_and_decision_findings(
        monkeypatch, tmp_path):
    actor_ref = {"kind": "polity", "id": "auren"}
    decision = _event(
        1, fact_kind=FactKind.DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "aid:1"},
    )
    valid_transition = _event(
        2, fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision.id, "actor_ref": actor_ref,
                        "selected_affordance_id": "aid:1"},
        deltas=(StateDelta(id="event:2:delta:0", event_id="event:2", owner_kind="polity",
                           owner_id="auren", aspect="aid", before="0", after="1"),),
        causes=(decision.id,),
    )
    broken = _event(3, causes=("event:999",))
    invalid_actor_transition = _event(
        4, fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": broken.id, "actor_ref": actor_ref,
                        "selected_affordance_id": "aid:1"},
        deltas=(StateDelta(id="event:4:delta:0", event_id="event:4", owner_kind="polity",
                           owner_id="auren", aspect="aid", before="1", after="2"),),
        causes=(broken.id,),
    )
    world = SimpleNamespace(events=[decision, valid_transition, broken, invalid_actor_transition],
                            clock=SimpleNamespace(absolute_day=1))
    monkeypatch.setattr(medieval_causal_audit, "load_world", lambda _path: world)
    save = tmp_path / "audit-input.mws"
    save.write_bytes(b"unchanged fixture bytes")
    before = save.read_bytes()

    report = medieval_causal_audit.audit(save)

    assert report["broken_cause_ids"] == ["event:999"]
    assert report["decision_origin_without_source"] == [invalid_actor_transition.id]
    assert report["decision_authorship_errors"] == [invalid_actor_transition.id]
    assert save.read_bytes() == before
