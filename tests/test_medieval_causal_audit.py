from types import SimpleNamespace

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.sim.medieval.events import WorldEvent
from tools import medieval_causal_audit


def _event(sequence, *, day=1, fact_kind=FactKind.OCCURRENCE,
           causal_origin=CausalOrigin.DETERMINISTIC, decision=None,
           causal_payload=None, deltas=(), causes=(), event_type="audit_fixture"):
    event_id = f"event:{sequence}"
    links = tuple(
        CausalLink(id=f"{event_id}:cause:{index}", event_id=event_id,
                   cause_event_id=cause_id, relation=CausalRelation.TRIGGERED_BY)
        for index, cause_id in enumerate(causes)
    )
    return WorldEvent(
        id=event_id, day=day, sequence=sequence, event_type=event_type,
        content="Audit fixture", fact_kind=fact_kind, causal_origin=causal_origin,
        decision=decision, causal_payload=causal_payload, deltas=tuple(deltas),
        causal_links=links,
    )


def test_audit_uses_index_and_preserves_broken_cause_and_decision_findings(
        monkeypatch, tmp_path):
    actor_ref = {"kind": "polity", "id": "auren"}
    decision = _event(
        1, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
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
    unauthored_decision = _event(
        5, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "build:1"},
    )
    unnamed_fallback = _event(
        6, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "build:2"},
        causal_payload={"decision_source": {"kind": "fallback", "policy": "routine-rules"}},
    )
    provider_receipt = _event(
        7, event_type="ai_decision_interpreted",
        causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"selection": {"actor_ref": actor_ref,
                                       "selected_affordance_id": "aid:2"}},
    )
    provider_decision = _event(
        8, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "aid:2"},
        causal_payload={"decision_source": {"kind": "provider", "receipt_event_id": provider_receipt.id}},
        causes=(provider_receipt.id,),
    )
    stale_provider_decision = _event(
        14, day=2, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "aid:2"},
        causal_payload={"decision_source": {"kind": "provider",
                                             "receipt_event_id": provider_receipt.id}},
        causes=(provider_receipt.id,),
    )
    named_fallback_decision = _event(
        11, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "build:3"},
        causal_payload={"decision_source": {"kind": "fallback", "policy": "routine-rules",
                                             "rule": "investment"}},
    )
    owner_authorization = _event(
        9, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.DETERMINISTIC,
        decision={"actor_ref": actor_ref, "selected_affordance_id": "aid:3"},
    )
    misattributed_transition = _event(
        10, fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": owner_authorization.id,
                        "actor_ref": actor_ref, "selected_affordance_id": "aid:3"},
        deltas=(StateDelta(id="event:10:delta:0", event_id="event:10", owner_kind="polity",
                           owner_id="auren", aspect="aid", before="2", after="3"),),
        causes=(owner_authorization.id,),
    )
    stale_decision_transition = _event(
        12, day=2, fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision.id, "actor_ref": actor_ref,
                        "selected_affordance_id": "aid:1"},
        deltas=(StateDelta(id="event:12:delta:0", event_id="event:12", owner_kind="polity",
                           owner_id="auren", aspect="aid", before="3", after="4"),),
        causes=(decision.id,),
    )
    unauthored_nonmaterial_transition = _event(
        13, causal_origin=CausalOrigin.ACTOR_DECISION,
    )
    world = SimpleNamespace(events=[decision, valid_transition, broken, invalid_actor_transition,
                                    unauthored_decision, unnamed_fallback, provider_receipt,
                                    provider_decision, owner_authorization, misattributed_transition,
                                    named_fallback_decision, stale_decision_transition,
                                    unauthored_nonmaterial_transition, stale_provider_decision],
                            clock=SimpleNamespace(absolute_day=1))
    monkeypatch.setattr(medieval_causal_audit, "load_world", lambda _path: world)
    save = tmp_path / "audit-input.mws"
    save.write_bytes(b"unchanged fixture bytes")
    before = save.read_bytes()

    report = medieval_causal_audit.audit(save)

    assert report["broken_cause_ids"] == ["event:999"]
    assert report["decision_origin_without_source"] == [misattributed_transition.id,
                                                          stale_decision_transition.id,
                                                          unauthored_nonmaterial_transition.id,
                                                          invalid_actor_transition.id]
    assert report["decision_authorship_errors"] == [misattributed_transition.id,
                                                     stale_decision_transition.id,
                                                     invalid_actor_transition.id]
    assert report["decision_source_errors"] == [stale_provider_decision.id,
                                                unauthored_decision.id, unnamed_fallback.id]
    assert report["material_delta_inventory"] == [{
        "event_type": "audit_fixture",
        "owner_kind": "polity",
        "aspect": "aid",
        "causal_origin": "actor_decision",
        "event_count": 4,
        "delta_count": 4,
        "owner_id_count": 1,
        "owner_id_samples": ["auren"],
        "events_without_causal_links": 0,
        "events_with_root_premise": 0,
        "example_event_ids": ["event:2", "event:4", "event:10"],
    }]
    assert save.read_bytes() == before


def test_audit_accepts_provider_sourced_no_action_decision(monkeypatch, tmp_path):
    actor_ref = {"kind": "polity", "id": "auren"}
    receipt = _event(
        1, event_type="ai_decision_declined", causal_origin=CausalOrigin.LLM_INTERPRETATION,
        causal_payload={"selection": {"actor_ref": actor_ref, "selected_affordance_id": "NO_ACTION"}},
    )
    decision = _event(
        2, fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"action": "no_action", "actor_ref": actor_ref,
                  "selected_affordance_id": "NO_ACTION", "declined_option_ids": ["research:one"]},
        causal_payload={"decision_source": {"kind": "provider", "receipt_event_id": receipt.id}},
        causes=(receipt.id,),
    )
    world = SimpleNamespace(events=[receipt, decision], clock=SimpleNamespace(absolute_day=1))
    monkeypatch.setattr(medieval_causal_audit, "load_world", lambda _path: world)
    save = tmp_path / "audit-no-action.mws"
    save.write_bytes(b"fixture")

    report = medieval_causal_audit.audit(save)

    assert report["decision_source_errors"] == []
    assert report["material_delta_inventory"] == []
    assert report["ok"] is True


def test_audit_distinguishes_explicit_root_premise_from_unrooted_material(monkeypatch, tmp_path):
    rooted = _event(
        1, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(id="event:1:delta:0", event_id="event:1", owner_kind="stock",
                           owner_id="stock:one", aspect="grain", before="0", after="1"),),
        causal_payload={"root_premise": {
            "kind": "world_generation", "domain": "production",
            "source_refs": [{"kind": "stock", "id": "stock:one"}],
            "observed_day": 1,
        }},
    )
    unrooted = _event(
        2, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(id="event:2:delta:0", event_id="event:2", owner_kind="stock",
                           owner_id="stock:two", aspect="grain", before="0", after="1"),),
    )
    forged_root = _event(
        3, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(id="event:3:delta:0", event_id="event:3", owner_kind="stock",
                           owner_id="stock:missing", aspect="grain", before="0", after="1"),),
        causal_payload={"root_premise": {
            "kind": "world_generation", "domain": "production",
            "source_refs": [{"kind": "stock", "id": "stock:missing"}],
            "observed_day": 1,
        }},
    )
    world = SimpleNamespace(
        events=[rooted, unrooted, forged_root], clock=SimpleNamespace(absolute_day=1),
        economy=SimpleNamespace(stocks={"stock:one": object()}),
        society=SimpleNamespace(), map=SimpleNamespace(), creatures=SimpleNamespace(),
    )
    monkeypatch.setattr(medieval_causal_audit, "load_world", lambda _path: world)
    save = tmp_path / "audit-root-premise.mws"
    save.write_bytes(b"fixture")

    report = medieval_causal_audit.audit(save)

    assert report["root_premise_events"] == [rooted.id]
    assert report["root_premise_errors"] == [forged_root.id]
    assert report["unrooted_material_events"] == [unrooted.id]
    assert report["ok"] is False
