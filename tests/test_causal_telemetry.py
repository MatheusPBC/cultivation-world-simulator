from __future__ import annotations

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.sim.managers.event_manager import EventManager
from src.systems.causal_telemetry import aggregate_causal_telemetry
from src.systems.time import Month, MonthStamp, Year, create_month_stamp


def _event(
    event_id: str,
    *,
    origin: CausalOrigin,
    fact_kind: FactKind,
    month_stamp: int | None = None,
) -> Event:
    return Event(
        month_stamp=MonthStamp(
            month_stamp
            if month_stamp is not None
            else create_month_stamp(Year(100), Month(1))
        ),
        content=event_id,
        id=event_id,
        causal_origin=origin,
        fact_kind=fact_kind,
    )


def test_telemetry_reports_origins_fact_kinds_depth_and_missing_causes() -> None:
    manager = EventManager.create_in_memory()
    root = _event("root", origin=CausalOrigin.EXTERNAL_EVENT, fact_kind=FactKind.OCCURRENCE)
    decision = _event("decision", origin=CausalOrigin.LLM_INTERPRETATION, fact_kind=FactKind.DECISION)
    decision.causal_links = [CausalLink(event_id=decision.id, cause_event_id=root.id)]
    effect = _event("effect", origin=CausalOrigin.ACTOR_DECISION, fact_kind=FactKind.STATE_TRANSITION)
    effect.causal_links = [CausalLink(event_id=effect.id, cause_event_id=decision.id, relation=CausalRelation.RESPONSE_TO)]
    broken = _event("broken", origin=CausalOrigin.DETERMINISTIC, fact_kind=FactKind.OCCURRENCE)
    broken.causal_links = [CausalLink(event_id=broken.id, cause_event_id="missing-cause")]
    for event in (root, decision, effect, broken):
        assert manager.add_event(event)

    report = aggregate_causal_telemetry(manager)

    assert report.events == 4
    assert report.by_origin["external_event"] == 1
    assert report.by_origin["llm_interpretation"] == 1
    assert report.by_origin["actor_decision"] == 1
    assert report.by_fact_kind["decision"] == 1
    assert report.chain_depth_distribution == {"0": 1, "1": 1, "2": 1, "unknown": 1}
    assert report.broken_cause_count == 1
    assert report.events_with_missing_causes == 1
    assert report.out_of_window_cause_count == 0
    assert report.events_with_out_of_window_causes == 0
    assert report.interpreter_share == 0.25
    assert report.actor_share == 0.25
    assert manager.get_causal_telemetry().to_dict() == report.to_dict()


def test_telemetry_keeps_existing_causes_outside_window_as_valid_boundaries() -> None:
    manager = EventManager.create_in_memory()
    outside = _event(
        "outside",
        origin=CausalOrigin.EXTERNAL_EVENT,
        fact_kind=FactKind.OCCURRENCE,
        month_stamp=1199,
    )
    outside.causal_links = [CausalLink(event_id=outside.id, cause_event_id="not-traversed")]
    boundary_child = _event(
        "boundary-child",
        origin=CausalOrigin.DETERMINISTIC,
        fact_kind=FactKind.STATE_TRANSITION,
    )
    boundary_child.causal_links = [CausalLink(event_id=boundary_child.id, cause_event_id=outside.id)]
    descendant = _event(
        "descendant",
        origin=CausalOrigin.ACTOR_DECISION,
        fact_kind=FactKind.STATE_TRANSITION,
    )
    descendant.causal_links = [CausalLink(event_id=descendant.id, cause_event_id=boundary_child.id)]
    missing = _event(
        "missing",
        origin=CausalOrigin.DETERMINISTIC,
        fact_kind=FactKind.OCCURRENCE,
    )
    missing.causal_links = [CausalLink(event_id=missing.id, cause_event_id="actually-missing")]
    for event in (outside, boundary_child, descendant, missing):
        assert manager.add_event(event)

    report = aggregate_causal_telemetry(manager, start_month=1200, end_month=1200)

    assert report.events == 3
    assert report.broken_cause_count == 1
    assert report.events_with_missing_causes == 1
    assert report.out_of_window_cause_count == 1
    assert report.events_with_out_of_window_causes == 1
    assert report.chain_depth_distribution == {"1": 1, "2": 1, "unknown": 1}
    payload = report.to_dict()
    assert payload["out_of_window_cause_count"] == 1
    assert payload["events_with_out_of_window_causes"] == 1


def test_telemetry_keeps_cycles_unknown_without_marking_them_broken() -> None:
    manager = EventManager.create_in_memory()
    first = _event("cycle-first", origin=CausalOrigin.DETERMINISTIC, fact_kind=FactKind.OCCURRENCE)
    second = _event("cycle-second", origin=CausalOrigin.DETERMINISTIC, fact_kind=FactKind.OCCURRENCE)
    first.causal_links = [CausalLink(event_id=first.id, cause_event_id=second.id)]
    second.causal_links = [CausalLink(event_id=second.id, cause_event_id=first.id)]
    assert manager.add_event(first)
    assert manager.add_event(second)

    report = aggregate_causal_telemetry(manager)

    assert report.broken_cause_count == 0
    assert report.events_with_missing_causes == 0
    assert report.out_of_window_cause_count == 0
    assert report.events_with_out_of_window_causes == 0
    assert report.chain_depth_distribution == {"unknown": 2}


def test_telemetry_reads_decision_events_from_sqlite(tmp_path) -> None:
    from src.classes.event_storage import EventStorage

    storage = EventStorage(tmp_path / "events.db")
    manager = EventManager(storage)
    decision = _event("decision", origin=CausalOrigin.LLM_INTERPRETATION, fact_kind=FactKind.DECISION)
    assert manager.add_event(decision)

    report = aggregate_causal_telemetry(manager)

    assert report.events == 1
    assert report.by_origin["llm_interpretation"] == 1
    storage.close()


def test_telemetry_resolves_out_of_window_cause_from_sqlite(tmp_path) -> None:
    from src.classes.event_storage import EventStorage

    storage = EventStorage(tmp_path / "window.db")
    manager = EventManager(storage)
    outside = _event(
        "sqlite-outside",
        origin=CausalOrigin.EXTERNAL_EVENT,
        fact_kind=FactKind.OCCURRENCE,
        month_stamp=1199,
    )
    effect = _event(
        "sqlite-effect",
        origin=CausalOrigin.DETERMINISTIC,
        fact_kind=FactKind.STATE_TRANSITION,
    )
    effect.causal_links = [CausalLink(event_id=effect.id, cause_event_id=outside.id)]
    assert manager.add_event(outside)
    assert manager.add_event(effect)

    report = aggregate_causal_telemetry(manager, start_month=1200, end_month=1200)

    assert report.events == 1
    assert report.broken_cause_count == 0
    assert report.out_of_window_cause_count == 1
    assert report.events_with_out_of_window_causes == 1
    assert report.chain_depth_distribution == {"1": 1}
    storage.close()
