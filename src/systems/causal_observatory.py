"""Read-only, headless observatory for long causal simulation runs.

The observatory deliberately does not own simulation state.  It consumes the
public event manager, mechanical-language registry and canonical map after a
run (or between two months), and returns deterministic measurements useful for
finding causal chains that terminate, break, or become repetitive.
"""

from __future__ import annotations

import asyncio
import inspect
import random
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Iterable

from src.classes.regional_economy import QUANTITY_EPSILON
from src.systems.causal_telemetry import aggregate_causal_telemetry
from src.utils.llm.runtime_mode import llm_test_mode_scope


class TestModeRequired(ValueError):
    """Raised when the torture harness is configured without test mode."""


class RealProviderBlocked(ValueError):
    """Raised when a run attempts to opt into a real LLM provider."""


class PersistentStorageBlocked(ValueError):
    """Raised when a harness run is given a persistent event store."""


_TEST_PROVIDERS = frozenset({"test", "fallback", "deterministic"})
_MATERIAL_EVENT_TOKENS = {
    "migration": ("population_transfer", "migration"),
    "economic_transfer": ("resource_transfer", "economic_transfer"),
    "maintenance": ("maintenance",),
    "capacity_project": ("urban_capacity_project",),
    "institutional_support": ("sect_member_support",),
}


@dataclass(frozen=True, slots=True)
class CausalTortureConfig:
    """Configurable run guardrails; none of these are world rules."""

    worlds: int = 10
    months: int = 1000
    seed: int = 0
    test_mode: bool = True
    provider: str = "test"
    map_id: str = "classic"
    probe_profile: str = "baseline"
    severe_overcrowding_ratio: float = 1.25
    near_capacity_ratio: float = 0.85
    underused_ratio: float = 0.25

    def __post_init__(self) -> None:
        if self.worlds < 1 or self.months < 1:
            raise ValueError("worlds and months must be positive")
        if not self.test_mode:
            raise TestModeRequired("causal torture tests require test_mode=True")
        provider = str(self.provider).strip().lower()
        if provider not in _TEST_PROVIDERS:
            raise RealProviderBlocked(
                "causal torture tests block real providers; use provider='test'"
            )
        if not self.map_id.strip():
            raise ValueError("map_id must not be empty")
        from src.systems.causal_probe import CAUSAL_PROBE_PROFILES

        if self.probe_profile not in CAUSAL_PROBE_PROFILES:
            raise ValueError(f"Unknown causal probe profile: {self.probe_profile}")
        if not (
            0.0 <= self.underused_ratio < self.near_capacity_ratio
            <= self.severe_overcrowding_ratio
        ):
            raise ValueError("urban observation thresholds must be ordered")


@dataclass(frozen=True, slots=True)
class CausalRunObservation:
    """Deterministic measurements for one world/window."""

    seed: int
    start_month: int
    end_month: int
    months_completed: int
    event_count: int
    event_types: dict[str, int]
    condition_activated: int
    condition_resolved: int
    condition_durations: dict[str, int]
    reactions: dict[str, Any]
    material_events: dict[str, int]
    event_quality: dict[str, Any]
    causal_graph: dict[str, Any]
    urban_projects: dict[str, float | int]
    urban_extremes: dict[str, float | int]
    derived_metric_reuse: dict[str, int]
    causal_telemetry: dict[str, Any]
    causal_chains: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CausalTortureReport:
    """Result of a complete configured run."""

    config: CausalTortureConfig
    runs: tuple[CausalRunObservation, ...]

    @property
    def totals(self) -> dict[str, int]:
        return {
            "worlds": len(self.runs),
            "months": sum(run.months_completed for run in self.runs),
            "events": sum(run.event_count for run in self.runs),
            "conditions_activated": sum(run.condition_activated for run in self.runs),
            "conditions_resolved": sum(run.condition_resolved for run in self.runs),
            "migrations": sum(run.material_events["migration"] for run in self.runs),
            "economic_transfers": sum(
                run.material_events["economic_transfer"] for run in self.runs
            ),
            "maintenance": sum(run.material_events["maintenance"] for run in self.runs),
            "institutional_support": sum(
                run.material_events["institutional_support"] for run in self.runs
            ),
            "capacity_projects_completed": sum(
                int(run.urban_projects["completed"]) for run in self.runs
            ),
            "failed_affordances": sum(
                int(run.reactions["failed_affordance"]) for run in self.runs
            ),
            "untyped_events": sum(
                int(run.event_quality["untyped_events"]) for run in self.runs
            ),
            "story_mutations": sum(
                int(run.event_quality["story_mutations"]) for run in self.runs
            ),
            "max_chain_depth": max(
                (
                    int(depth)
                    for run in self.runs
                    for depth in run.causal_telemetry[
                        "chain_depth_distribution"
                    ]
                    if str(depth).isdigit()
                ),
                default=0,
            ),
            "broken_causes": sum(
                int(run.causal_telemetry["broken_cause_count"])
                for run in self.runs
            ),
            "out_of_window_causes": sum(
                int(run.causal_telemetry.get("out_of_window_cause_count", 0))
                for run in self.runs
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "runs": [run.to_dict() for run in self.runs],
            "totals": self.totals,
        }


def _event_window(world: Any, start_month: int | None, end_month: int | None) -> tuple[int, int, list[Any]]:
    manager = world.event_manager
    if start_month is None or end_month is None:
        current = int(world.month_stamp)
        events = manager.get_events_between_months(-(2**63), 2**63 - 1)
        if events:
            start_month = int(start_month if start_month is not None else events[0].month_stamp)
            end_month = int(end_month if end_month is not None else events[-1].month_stamp)
        else:
            start_month = int(start_month if start_month is not None else current)
            end_month = int(end_month if end_month is not None else current)
    start = int(start_month)
    end = int(end_month)
    if start > end:
        raise ValueError("start_month must not be after end_month")
    return start, end, list(manager.get_events_between_months(start, end))


def _condition_instances(world: Any) -> Iterable[Any]:
    state = getattr(world, "mechanical_language", None)
    return (getattr(state, "condition_instances", {}) or {}).values()


def _condition_counts_and_durations(world: Any, events: list[Any], start: int, end: int) -> tuple[int, int, dict[str, int]]:
    activated_events = [event for event in events if event.event_type == "semantic_condition_activated"]
    resolved_events = [event for event in events if event.event_type == "semantic_condition_resolved"]
    instances = [
        instance
        for instance in _condition_instances(world)
        if int(instance.started_month) <= end
        and (instance.resolved_month is None or int(instance.resolved_month) >= start)
    ]
    activated_ids = {
        str(instance.id)
        for instance in instances
        if start <= int(instance.started_month) <= end
    }
    resolved_ids = {
        str(instance.id)
        for instance in instances
        if instance.resolved_month is not None and start <= int(instance.resolved_month) <= end
    }
    # Current condition events predate an instance-id render parameter.  The
    # cause/resolution event IDs are the durable join available in that case.
    for event in activated_events:
        if not any(str(instance.cause_event_id) == str(event.id) for instance in instances):
            activated_ids.add(f"event:{event.id}")
    for event in resolved_events:
        if not any(str(instance.resolution_event_id) == str(event.id) for instance in instances):
            resolved_ids.add(f"event:{event.id}")

    durations: dict[str, int] = {}
    for instance in instances:
        started = int(instance.started_month)
        observed_end = int(instance.resolved_month) if instance.resolved_month is not None else end
        if observed_end < start or started > end:
            continue
        stable_key = ":".join((
            str(instance.definition_id),
            str(instance.target_kind),
            str(instance.target_id),
            str(started),
            str(observed_end),
        ))
        durations[stable_key] = max(0, observed_end - started + 1)
    return len(activated_ids), len(resolved_ids), dict(sorted(durations.items()))


def _decision_value(event: Any) -> str | None:
    payload = getattr(event, "causal_payload", None) or {}
    for container_key in ("interpretation", "decision"):
        value = payload.get(container_key)
        if isinstance(value, dict) and value.get("decision") is not None:
            return str(value["decision"])
    return None


def _is_decision_event(event: Any) -> bool:
    return str(getattr(event, "event_type", "")).endswith("_interpretation_decision")


def _material_kind(event_type: str) -> str | None:
    for kind, tokens in _MATERIAL_EVENT_TOKENS.items():
        if any(token in event_type for token in tokens):
            return kind
    return None


def _reaction_counts(world: Any, events: list[Any]) -> dict[str, Any]:
    decisions = [event for event in events if _is_decision_event(event)]
    no_action = sum(_decision_value(event) in {"maintain", "no_action"} for event in decisions)
    material = [event for event in events if _material_kind(str(event.event_type)) is not None]
    attempts = [event for event in material if _is_affordance_attempt(event)]
    successful = sum(
        _affordance_outcome(event) in {"completed", "success", "succeeded", "started"}
        for event in attempts
    )
    failed = sum(
        "blocked" in str(event.event_type)
        or _affordance_outcome(event) in {"blocked", "failed", "failure"}
        for event in attempts
    )
    terminal_reasons = Counter(
        str((getattr(event, "causal_payload", None) or {}).get("reason", "unknown"))
        for event in attempts
        if (
            "blocked" in str(event.event_type)
            or _affordance_outcome(event) in {"blocked", "failed", "failure"}
        )
    )
    return {
        "decisions": len(decisions),
        "no_action": no_action,
        "successful": successful,
        "failed_affordance": failed,
        "affordance_attempts": len(attempts),
        "post_attempt_lifecycle_events": len(material) - len(attempts),
        "terminal_reasons": dict(sorted(terminal_reasons.items())),
    }


def _affordance_outcome(event: Any) -> str:
    payload = getattr(event, "causal_payload", None) or {}
    outcome = str(payload.get("outcome", "")).strip().lower()
    if outcome in {
        "started",
        "completed",
        "success",
        "succeeded",
        "blocked",
        "failed",
        "failure",
    }:
        return outcome
    event_type = str(getattr(event, "event_type", ""))
    if event_type.endswith("_started"):
        return "started"
    if event_type.endswith("_completed"):
        return "completed"
    if event_type.endswith("_blocked"):
        return "blocked"
    return ""


def _is_affordance_attempt(event: Any) -> bool:
    """Count actor requests once, not every later lifecycle transition."""
    payload = getattr(event, "causal_payload", None) or {}
    event_type = str(getattr(event, "event_type", ""))
    if any(token in event_type for token in ("_progressed", "_resumed", "_stalled")):
        return False
    if event_type == "urban_capacity_project_completed":
        return False
    single_step_affordance = event_type.startswith((
        "population_transfer_",
        "regional_resource_transfer_",
        "city_maintenance_",
        "sect_member_support_",
    ))
    single_step_affordance = (
        single_step_affordance
        or event_type == "urban_capacity_project_blocked"
    )
    if not single_step_affordance and not isinstance(payload.get("execution"), Mapping):
        return False
    return _affordance_outcome(event) in {
        "started",
        "completed",
        "success",
        "succeeded",
        "blocked",
        "failed",
        "failure",
    }


def _material_counts(events: list[Any]) -> dict[str, int]:
    counts = {kind: 0 for kind in _MATERIAL_EVENT_TOKENS}
    for event in events:
        event_type = str(getattr(event, "event_type", ""))
        outcome = str(
            (getattr(event, "causal_payload", None) or {}).get("outcome", "")
        )
        if "blocked" in event_type or outcome in {
            "blocked",
            "failed",
            "failure",
            "stalled",
        }:
            continue
        kind = _material_kind(event_type)
        if kind is not None:
            counts[kind] += 1
    return counts


def _payload_float(event: Any, key: str) -> float:
    value = (getattr(event, "causal_payload", None) or {}).get(key)
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _project_id(event: Any) -> str | None:
    payload = getattr(event, "causal_payload", None) or {}
    project_id = payload.get("project_id")
    if project_id:
        return str(project_id)
    render_params = getattr(event, "render_params", None) or {}
    project_id = render_params.get("project_id")
    return str(project_id) if project_id else None


def _urban_project_history(world: Any, end_month: int) -> list[Any]:
    manager = getattr(world, "event_manager", None)
    if manager is None:
        return []
    return list(manager.get_events_between_months(-(2**63), end_month))


def _causal_reservation_snapshot(
    world: Any,
    *,
    start_month: int,
    end_month: int,
) -> tuple[float, set[str], int]:
    """Rebuild construction reservations from the project event stream.

    The canonical economy may have moved on since a historical observation,
    and it also contains reservations owned by other systems.  Only a
    lifecycle that starts with an UrbanCapacityProject event is eligible here.
    """
    balances: dict[str, float] = {}
    completed: set[str] = set()
    leaks = 0
    for event in _urban_project_history(world, end_month):
        event_type = str(getattr(event, "event_type", ""))
        project_id = _project_id(event)
        if project_id is None:
            continue
        if event_type == "urban_capacity_project_started":
            required = _payload_float(event, "material_required")
            if required > QUANTITY_EPSILON:
                balances[project_id] = required
                completed.discard(project_id)
        elif (
            event_type == "urban_capacity_project_progressed"
            and project_id in balances
            and project_id not in completed
        ):
            balances[project_id] = max(
                0.0,
                balances[project_id] - _payload_float(event, "material_delta"),
            )
        elif (
            event_type == "urban_capacity_project_completed"
            and project_id in balances
            and project_id not in completed
        ):
            if (
                balances[project_id] > QUANTITY_EPSILON
                and start_month <= int(event.month_stamp) <= end_month
            ):
                leaks += 1
            completed.add(project_id)

    active = {
        project_id
        for project_id, balance in balances.items()
        if balance > QUANTITY_EPSILON
    }
    return sum(balances[project_id] for project_id in active), active, leaks


def _urban_project_counts(
    world: Any,
    events: list[Any],
    *,
    start_month: int,
    end_month: int,
) -> dict[str, float | int]:
    event_types = Counter(str(getattr(event, "event_type", "")) for event in events)
    capacity_delta_total = 0.0
    material_reserved_total = 0.0
    material_consumed_total = 0.0
    for event in events:
        event_type = str(getattr(event, "event_type", ""))
        if event_type == "urban_capacity_project_started":
            material_reserved_total += _payload_float(event, "material_required")
        elif event_type == "urban_capacity_project_progressed":
            material_consumed_total += _payload_float(event, "material_delta")
        elif event_type == "urban_capacity_project_completed":
            for delta in (getattr(event, "causal_payload", None) or {}).get("deltas", []) or []:
                if isinstance(delta, dict) and delta.get("aspect") == "population_capacity":
                    try:
                        capacity_delta_total += float(delta.get("magnitude", 0.0))
                    except (TypeError, ValueError):
                        continue
    active_reserved_material, active_project_ids, completed_with_reservation_leak = (
        _causal_reservation_snapshot(
            world,
            start_month=start_month,
            end_month=end_month,
        )
    )
    return {
        "started": event_types["urban_capacity_project_started"],
        "progressed": event_types["urban_capacity_project_progressed"],
        "stalled": event_types["urban_capacity_project_stalled"],
        "resumed": event_types["urban_capacity_project_resumed"],
        "blocked": event_types["urban_capacity_project_blocked"],
        "completed": event_types["urban_capacity_project_completed"],
        "capacity_delta_total": capacity_delta_total,
        "material_reserved_total": material_reserved_total,
        "material_consumed_total": material_consumed_total,
        "active_reserved_material": active_reserved_material,
        "projects_with_active_reservations": len(active_project_ids),
        "completed_with_reservation_leak": completed_with_reservation_leak,
    }


def _urban_snapshot(world: Any, config: CausalTortureConfig) -> dict[str, float | int]:
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    ratios: list[float] = []
    for region in regions.values():
        population = getattr(region, "population", None)
        capacity = getattr(region, "population_capacity", None)
        if isinstance(population, (int, float)) and isinstance(capacity, (int, float)) and capacity > 0:
            ratios.append(float(population) / float(capacity))
    if not ratios:
        return {
            "city_months_observed": 0,
            "city_months_near_capacity": 0,
            "city_months_over_capacity": 0,
            "city_months_severe_overcrowding": 0,
            "city_months_underused": 0,
            "peak_load_ratio": 0.0,
        }
    return {
        "city_months_observed": len(ratios),
        "city_months_near_capacity": sum(value >= config.near_capacity_ratio for value in ratios),
        "city_months_over_capacity": sum(value > 1.0 for value in ratios),
        "city_months_severe_overcrowding": sum(value >= config.severe_overcrowding_ratio for value in ratios),
        "city_months_underused": sum(value <= config.underused_ratio for value in ratios),
        "peak_load_ratio": round(max(ratios), 6),
    }


def _urban_extremes(world: Any, config: CausalTortureConfig, samples: Iterable[dict[str, float | int]] = ()) -> dict[str, float | int]:
    snapshots = list(samples)
    if not snapshots:
        snapshots = [_urban_snapshot(world, config)]
    return {
        "city_months_observed": sum(int(item["city_months_observed"]) for item in snapshots),
        "city_months_near_capacity": sum(int(item["city_months_near_capacity"]) for item in snapshots),
        "city_months_over_capacity": sum(int(item["city_months_over_capacity"]) for item in snapshots),
        "city_months_severe_overcrowding": sum(int(item["city_months_severe_overcrowding"]) for item in snapshots),
        "city_months_underused": sum(int(item["city_months_underused"]) for item in snapshots),
        "peak_load_ratio": max(float(item["peak_load_ratio"]) for item in snapshots),
    }


def _causal_chains(world: Any, events: list[Any]) -> dict[str, int]:
    """Classify graph roots and leaves within the observed event window.

    A root has no direct causes.  A terminal event is a leaf with no children;
    it includes an unrelated singleton event and is intentionally not named a
    "terminal causal chain" because it may have no causal edges at all.
    """
    ids = {str(event.id) for event in events}
    links_by_effect = {
        str(event.id): list(world.event_manager.get_causal_links_for_event(event.id) or [])
        for event in events
    }
    has_cause = {event_id for event_id, links in links_by_effect.items() if links}
    has_child = {
        str(link.cause_event_id)
        for links in links_by_effect.values()
        for link in links
        if str(link.cause_event_id) in ids
    }
    cause_presence: dict[str, bool] = {}

    def cause_exists(cause_id: str) -> bool:
        if cause_id in ids:
            return True
        if cause_id not in cause_presence:
            cause_presence[cause_id] = (
                world.event_manager.get_event_by_id(cause_id) is not None
            )
        return cause_presence[cause_id]

    broken = {
        event_id
        for event_id, links in links_by_effect.items()
        if any(not cause_exists(str(link.cause_event_id)) for link in links)
    }
    out_of_window = {
        event_id
        for event_id, links in links_by_effect.items()
        if any(
            str(link.cause_event_id) not in ids
            and cause_exists(str(link.cause_event_id))
            for link in links
        )
    }
    return {
        "root_events": len(ids - has_cause),
        "terminal_events": len(ids - has_child),
        "broken_events": len(broken),
        "out_of_window_events": len(out_of_window),
    }


def _event_quality(events: list[Any]) -> dict[str, Any]:
    event_types = Counter(str(getattr(event, "event_type", "") or "") for event in events)
    untyped = [event for event in events if not str(getattr(event, "event_type", "") or "").strip()]
    typed_counts = Counter({key: value for key, value in event_types.items() if key})
    dominant_type = ""
    dominant_count = 0
    if typed_counts:
        dominant_type, dominant_count = min(
            typed_counts.items(), key=lambda item: (-item[1], item[0])
        )

    monthly = Counter(
        (int(getattr(event, "month_stamp", 0)), event_type)
        for event in events
        if (event_type := str(getattr(event, "event_type", "") or "").strip())
    )
    repeated_pairs = [count for count in monthly.values() if count > 1]
    story_mutations = sum(
        1
        for event in events
        if bool(getattr(event, "is_story", False))
        and bool((getattr(event, "causal_payload", None) or {}).get("deltas") or [])
    )
    return {
        "typed_events": len(events) - len(untyped),
        "untyped_events": len(untyped),
        "untyped_by_fact_kind": dict(sorted(Counter(
            str(getattr(event, "fact_kind", "")) for event in untyped
        ).items())),
        "untyped_by_origin": dict(sorted(Counter(
            str(getattr(event, "causal_origin", "")) for event in untyped
        ).items())),
        "dominant_event_type": dominant_type,
        "dominant_event_share": dominant_count / len(events) if events else 0.0,
        "repeated_type_month_pairs": len(repeated_pairs),
        "max_same_type_in_month": max(repeated_pairs, default=0),
        "story_mutations": story_mutations,
    }


def _causal_graph(world: Any, events: list[Any]) -> dict[str, Any]:
    event_ids = {str(event.id) for event in events}
    links = [
        link
        for event in events
        for link in (world.event_manager.get_causal_links_for_event(event.id) or [])
    ]
    relation_counts = Counter(str(getattr(link, "relation", "")) for link in links)
    fan_out = Counter(str(link.cause_event_id) for link in links)
    observed_fan_out = [count for cause_id, count in fan_out.items() if cause_id in event_ids]
    linked_effect_ids = {str(link.event_id) for link in links}
    return {
        "links": len(links),
        "linked_events": len(linked_effect_ids),
        "by_relation": dict(sorted(relation_counts.items())),
        "causes_with_children": len(observed_fan_out),
        "max_fan_out": max(observed_fan_out, default=0),
        "average_fan_out": (
            sum(observed_fan_out) / len(observed_fan_out)
            if observed_fan_out
            else 0.0
        ),
    }


def _derived_metric_reuse(world: Any) -> dict[str, int]:
    definitions = getattr(getattr(world, "mechanical_language", None), "derived_definitions", {}) or {}
    reused = [definition for definition in definitions.values() if len(getattr(definition, "reuse_contexts", ())) >= 2]
    return {
        "definitions_reused": len(reused),
        "contexts": sum(len(getattr(definition, "reuse_contexts", ())) for definition in reused),
    }


class CausalObservatory:
    """Read-only adapter over one world's public causal state."""

    def __init__(self, config: CausalTortureConfig | None = None):
        self.config = config or CausalTortureConfig()

    def observe(
        self,
        world: Any,
        *,
        start_month: int | None = None,
        end_month: int | None = None,
        urban_samples: Iterable[dict[str, float | int]] = (),
    ) -> CausalRunObservation:
        start, end, events = _event_window(world, start_month, end_month)
        activated, resolved, durations = _condition_counts_and_durations(world, events, start, end)
        telemetry = aggregate_causal_telemetry(
            world.event_manager,
            start_month=start,
            end_month=end,
        ).to_dict()
        return CausalRunObservation(
            seed=0,
            start_month=start,
            end_month=end,
            months_completed=max(0, end - start + 1),
            event_count=len(events),
            event_types=dict(sorted(Counter(str(event.event_type) for event in events).items())),
            condition_activated=activated,
            condition_resolved=resolved,
            condition_durations=durations,
            reactions=_reaction_counts(world, events),
            material_events=_material_counts(events),
            event_quality=_event_quality(events),
            causal_graph=_causal_graph(world, events),
            urban_projects=_urban_project_counts(
                world,
                events,
                start_month=start,
                end_month=end,
            ),
            urban_extremes=_urban_extremes(world, self.config, urban_samples),
            derived_metric_reuse=_derived_metric_reuse(world),
            causal_telemetry=telemetry,
            causal_chains=_causal_chains(world, events),
        )


WorldFactory = Callable[[int, int], Any]
StepFunction = Callable[[Any], Awaitable[Iterable[Any]] | Iterable[Any] | None]


def _default_world_factory(map_id: str, world_index: int, seed: int) -> Any:
    from src.classes.core.world import World
    from src.run.load_map import load_cultivation_world_map
    from src.systems.time import Month, Year, create_month_stamp

    world = World(
        map=load_cultivation_world_map(map_id),
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    )
    world.run_config_snapshot = {
        "map_id": map_id,
        "test_mode": True,
        "causal_torture_world_index": world_index,
        "causal_torture_seed": seed,
    }
    return world


def _assert_isolated_world(world: Any) -> None:
    manager = getattr(world, "event_manager", None)
    if getattr(manager, "_storage", None) is not None:
        raise PersistentStorageBlocked(
            "causal torture tests require an in-memory EventManager"
        )
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    if snapshot.get("allow_real_provider"):
        raise RealProviderBlocked("world configuration explicitly allows a real provider")
    provider = snapshot.get("provider") or snapshot.get("llm_provider")
    if provider is not None and str(provider).strip().lower() not in _TEST_PROVIDERS:
        raise RealProviderBlocked("world configuration selects a real provider")


def _memory_event_state(manager: Any) -> tuple[list[Any] | None, list[Any] | None]:
    events = getattr(manager, "_memory_events", None)
    chapters = getattr(manager, "_memory_chronicle_chapters", None)
    return (
        list(events) if isinstance(events, list) else None,
        list(chapters) if isinstance(chapters, list) else None,
    )


def _restore_memory_event_state(
    manager: Any,
    state: tuple[list[Any] | None, list[Any] | None],
) -> None:
    events, chapters = state
    if events is not None and isinstance(getattr(manager, "_memory_events", None), list):
        manager._memory_events[:] = events
    if chapters is not None and isinstance(getattr(manager, "_memory_chronicle_chapters", None), list):
        manager._memory_chronicle_chapters[:] = chapters


def _restore_external_handles(world: Any, event_manager: Any) -> None:
    """Reconnect handles intentionally excluded from the canonical snapshot."""
    world.event_manager = event_manager
    if hasattr(event_manager, "set_subject_resolver") and hasattr(world, "avatar_manager"):
        event_manager.set_subject_resolver(
            lambda avatar_id: world.avatar_manager.get_avatar(str(avatar_id))
        )
    mechanical_language = getattr(world, "mechanical_language", None)
    if mechanical_language is not None and hasattr(mechanical_language, "bind_world"):
        mechanical_language.bind_world(world)
    sect_context = getattr(world, "_sect_context", None)
    if sect_context is not None and hasattr(sect_context, "_world"):
        sect_context._world = world


class CausalTortureRunner:
    """Run isolated worlds under deterministic, provider-free conditions."""

    def __init__(self, config: CausalTortureConfig | None = None):
        self.config = config or CausalTortureConfig()

    async def run(
        self,
        *,
        world_factory: WorldFactory | None = None,
        step: StepFunction | None = None,
    ) -> CausalTortureReport:
        factory = world_factory or (
            lambda world_index, world_seed: _default_world_factory(
                self.config.map_id, world_index, world_seed
            )
        )
        observations: list[CausalRunObservation] = []
        random_state = random.getstate()
        try:
            for world_index in range(self.config.worlds):
                world_seed = self.config.seed + world_index
                random.seed(world_seed)
                world = factory(world_index, world_seed)
                if inspect.isawaitable(world):
                    world = await world
                _assert_isolated_world(world)
                from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

                checkpoint = SimulationMonthCheckpoint.capture(world)
                event_manager = world.event_manager
                memory_event_state = _memory_event_state(event_manager)
                snapshot = dict(getattr(world, "run_config_snapshot", {}) or {})
                snapshot["test_mode"] = True
                world.run_config_snapshot = snapshot
                try:
                    from src.systems.causal_probe import (
                        apply_causal_probe,
                        build_causal_probe_schedule,
                        prepare_health_recovery_strain_world,
                        prepare_institutional_urban_strain_world,
                    )

                    if self.config.probe_profile == "institutional_urban_strain":
                        prepare_institutional_urban_strain_world(world)
                        from src.systems.institution_bootstrap import (
                            bootstrap_institutional_authority,
                            synchronize_institutional_authority,
                        )

                        bootstrap_institutional_authority(world)
                        synchronize_institutional_authority(world)
                    elif self.config.probe_profile == "health_recovery_strain":
                        prepare_health_recovery_strain_world(world)
                    probe_schedule = build_causal_probe_schedule(
                        world,
                        self.config.probe_profile,
                    )
                    start_month = int(world.month_stamp)
                    urban_samples: list[dict[str, float | int]] = []
                    completed_months = 0
                    if step is None:
                        from src.sim.simulator import Simulator

                        simulator = Simulator(world)

                        async def default_step(current_world: Any) -> Any:
                            return await simulator.step()

                        current_step = default_step
                    else:
                        current_step = step
                    with llm_test_mode_scope(True):
                        for month_offset in range(self.config.months):
                            for probe in probe_schedule:
                                if probe.month_offset == month_offset:
                                    apply_causal_probe(world, probe)
                            result = current_step(world)
                            if inspect.isawaitable(result):
                                await result
                            completed_months += 1
                            urban_samples.append(_urban_snapshot(world, self.config))
                    end_month = start_month + completed_months - 1
                    observation = CausalObservatory(self.config).observe(
                        world,
                        start_month=start_month,
                        end_month=max(start_month, end_month),
                        urban_samples=urban_samples,
                    )
                    observations.append(
                        CausalRunObservation(
                            seed=world_seed,
                            start_month=observation.start_month,
                            end_month=observation.end_month,
                            months_completed=completed_months,
                            event_count=observation.event_count,
                            event_types=observation.event_types,
                            condition_activated=observation.condition_activated,
                            condition_resolved=observation.condition_resolved,
                            condition_durations=observation.condition_durations,
                            reactions=observation.reactions,
                            material_events=observation.material_events,
                            event_quality=observation.event_quality,
                            causal_graph=observation.causal_graph,
                            urban_projects=observation.urban_projects,
                            urban_extremes=observation.urban_extremes,
                            derived_metric_reuse=observation.derived_metric_reuse,
                            causal_telemetry=observation.causal_telemetry,
                            causal_chains=observation.causal_chains,
                        )
                    )
                finally:
                    checkpoint.restore()
                    _restore_external_handles(world, event_manager)
                    _restore_memory_event_state(event_manager, memory_event_state)
        finally:
            random.setstate(random_state)
        return CausalTortureReport(self.config, tuple(observations))

    def run_sync(
        self,
        *,
        world_factory: WorldFactory | None = None,
        step: StepFunction | None = None,
    ) -> CausalTortureReport:
        return asyncio.run(self.run(world_factory=world_factory, step=step))


async def run_causal_torture_test(
    config: CausalTortureConfig | None = None,
    *,
    world_factory: WorldFactory | None = None,
    step: StepFunction | None = None,
) -> CausalTortureReport:
    return await CausalTortureRunner(config).run(world_factory=world_factory, step=step)


__all__ = [
    "CausalObservatory",
    "CausalRunObservation",
    "CausalTortureConfig",
    "CausalTortureReport",
    "CausalTortureRunner",
    "PersistentStorageBlocked",
    "RealProviderBlocked",
    "TestModeRequired",
    "run_causal_torture_test",
]
