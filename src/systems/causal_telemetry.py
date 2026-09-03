"""Read-only causal authorship telemetry over persisted events."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind


_MIN_MONTH = -(2**63)
_MAX_MONTH = 2**63 - 1


@dataclass(frozen=True, slots=True)
class CausalTelemetryReport:
    """Deterministic summary of the persisted causal graph."""

    events: int
    by_origin: dict[str, int]
    by_fact_kind: dict[str, int]
    chain_depth_distribution: dict[str, int]
    broken_cause_count: int
    events_with_missing_causes: int
    out_of_window_cause_count: int
    events_with_out_of_window_causes: int
    interpreter_share: float
    actor_share: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": self.events,
            "by_origin": dict(self.by_origin),
            "by_fact_kind": dict(self.by_fact_kind),
            "chain_depth_distribution": dict(self.chain_depth_distribution),
            "broken_cause_count": self.broken_cause_count,
            "events_with_missing_causes": self.events_with_missing_causes,
            "out_of_window_cause_count": self.out_of_window_cause_count,
            "events_with_out_of_window_causes": self.events_with_out_of_window_causes,
            "interpreter_share": self.interpreter_share,
            "actor_share": self.actor_share,
        }


class CausalTelemetryAggregator:
    """Read-only adapter bound to one persisted event manager."""

    def __init__(self, event_manager: Any):
        self._event_manager = event_manager

    def aggregate(
        self,
        *,
        start_month: int | None = None,
        end_month: int | None = None,
    ) -> CausalTelemetryReport:
        return aggregate_causal_telemetry(
            self._event_manager,
            start_month=start_month,
            end_month=end_month,
        )


def _event_window(event_manager: Any, start_month: int | None, end_month: int | None) -> list[Any]:
    start = _MIN_MONTH if start_month is None else int(start_month)
    end = _MAX_MONTH if end_month is None else int(end_month)
    if start > end:
        raise ValueError("start_month must not be after end_month")
    return list(event_manager.get_events_between_months(start, end))


def aggregate_causal_telemetry(
    event_manager: Any,
    *,
    start_month: int | None = None,
    end_month: int | None = None,
) -> CausalTelemetryReport:
    """Aggregate persisted events without mutating the event or world state.

    The event manager is the only read boundary. Causes are resolved by ID;
    an existing cause outside the requested window is retained as a valid
    boundary, while a truly absent cause is reported as broken.
    """
    events = _event_window(event_manager, start_month, end_month)
    events_by_id = {str(event.id): event for event in events}
    cause_events_by_id: dict[str, Any | None] = {}
    links_by_event: dict[str, list[Any]] = {
        str(event.id): list(event_manager.get_causal_links_for_event(event.id) or [])
        for event in events
    }

    origins = Counter(str(getattr(event, "causal_origin", CausalOrigin.DETERMINISTIC)) for event in events)
    fact_kinds = Counter(str(getattr(event, "fact_kind", FactKind.OCCURRENCE)) for event in events)
    broken_cause_count = 0
    events_with_missing_causes = 0
    out_of_window_cause_count = 0
    events_with_out_of_window_causes = 0
    missing_event_ids: set[str] = set()
    out_of_window_event_ids: set[str] = set()

    def cause_event(cause_id: str) -> Any | None:
        if cause_id not in cause_events_by_id:
            cause_events_by_id[cause_id] = event_manager.get_event_by_id(cause_id)
        return cause_events_by_id[cause_id]

    for event in events:
        for link in links_by_event[str(event.id)]:
            cause_id = str(link.cause_event_id)
            if cause_id in events_by_id:
                continue
            if cause_event(cause_id) is None:
                broken_cause_count += 1
                missing_event_ids.add(str(event.id))
            else:
                out_of_window_cause_count += 1
                out_of_window_event_ids.add(str(event.id))
    events_with_missing_causes = len(missing_event_ids)
    events_with_out_of_window_causes = len(out_of_window_event_ids)

    depth_cache: dict[str, int | None] = {}

    def depth(event_id: str, visiting: frozenset[str] = frozenset()) -> int | None:
        if event_id in depth_cache:
            return depth_cache[event_id]
        if event_id in visiting:
            return None
        links = links_by_event.get(event_id, [])
        if not links:
            depth_cache[event_id] = 0
            return 0
        next_visiting = visiting | {event_id}
        cause_depths: list[int] = []
        for link in links:
            cause_id = str(link.cause_event_id)
            if cause_id not in events_by_id:
                # A cause outside the report window is a valid historical
                # boundary. Its own ancestry is intentionally not traversed.
                if cause_event(cause_id) is not None:
                    cause_depths.append(0)
                    continue
                depth_cache[event_id] = None
                return None
            cause_depth = depth(cause_id, next_visiting)
            if cause_depth is None:
                return None
            cause_depths.append(cause_depth)
        result = 1 + max(cause_depths)
        depth_cache[event_id] = result
        return result

    depth_counts = Counter()
    for event in events:
        value = depth(str(event.id))
        depth_counts[str(value) if value is not None else "unknown"] += 1

    total = len(events)
    interpreter_count = origins[str(CausalOrigin.LLM_INTERPRETATION)]
    actor_count = origins[str(CausalOrigin.ACTOR_DECISION)]
    return CausalTelemetryReport(
        events=total,
        by_origin=dict(sorted(origins.items())),
        by_fact_kind=dict(sorted(fact_kinds.items())),
        chain_depth_distribution=dict(sorted(depth_counts.items(), key=lambda item: (item[0] == "unknown", item[0]))),
        broken_cause_count=broken_cause_count,
        events_with_missing_causes=events_with_missing_causes,
        out_of_window_cause_count=out_of_window_cause_count,
        events_with_out_of_window_causes=events_with_out_of_window_causes,
        interpreter_share=interpreter_count / total if total else 0.0,
        actor_share=actor_count / total if total else 0.0,
    )


__all__ = [
    "CausalTelemetryAggregator",
    "CausalTelemetryReport",
    "aggregate_causal_telemetry",
]
