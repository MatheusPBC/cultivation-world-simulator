"""Deterministic population transfer in response to a regional condition."""

from __future__ import annotations

import math
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.core.world import World
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import ConditionDefinition, ConditionInstance
from src.classes.mechanical_language import (
    MeasurementAvailability,
    MetricKey,
    MetricReading,
    PrimitiveDimension,
    ReadingKind,
)
from src.classes.state_delta import StateDelta
from src.i18n import t


def _strict_required_amount(population: float, threshold_population: float) -> float:
    """Find a representable amount whose domain mutation crosses the threshold."""
    amount = math.nextafter(population - threshold_population, math.inf)
    for _ in range(64):
        if population - amount < threshold_population:
            return amount
        amount = math.nextafter(amount, math.inf)
    return math.inf


def _settlement_readings(region: CityRegion, month: int) -> list[dict[str, Any]]:
    return [
        MetricReading(
            key=MetricKey(PrimitiveDimension.LOAD, "region", str(region.id), "settlement"),
            value=float(region.population),
            unit="ten_thousand_people",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.EXACT,
            calculated_month=month,
            state_refs=[f"region:{region.id}:population"],
        ).to_dict(),
        MetricReading(
            key=MetricKey(PrimitiveDimension.CAPACITY, "region", str(region.id), "settlement"),
            value=float(region.population_capacity),
            unit="ten_thousand_people",
            availability=MeasurementAvailability.MEASURABLE,
            reading_kind=ReadingKind.EXACT,
            calculated_month=month,
            state_refs=[f"region:{region.id}:population_capacity"],
        ).to_dict(),
    ]


def _blocked_event(
    world: World,
    *,
    origin: CityRegion,
    condition: ConditionInstance,
    condition_definition: ConditionDefinition,
    decision_event_id: str,
    reason: str,
    measurements: list[dict[str, Any]],
) -> Event:
    event = Event(
        world.month_stamp,
        t("population_transfer.blocked", origin=origin.name),
        event_type="population_transfer_blocked",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
    )
    event.causal_payload = {
        "outcome": "blocked",
        "reason": reason,
        "execution": {
            "kind": "population_transfer",
            "condition_id": condition.id,
            "condition_definition_id": condition_definition.id,
            "origin_region_id": str(origin.id),
            "decision_event_id": decision_event_id,
        },
        "measurements": measurements,
    }
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    )
    return event


def resolve_population_transfer(
    world: World,
    *,
    origin: CityRegion,
    condition: ConditionInstance,
    condition_definition: ConditionDefinition,
    decision_event_id: str,
    max_fraction: float = 0.20,
    preferences: tuple[str, ...] = (
        "lower_settlement_load",
        "available_capacity",
    ),
) -> Event:
    """Resolve an overcrowding condition by moving population deterministically.

    The function only uses state owned by ``CityRegion`` and explicit routes
    owned by the map.  Geometry never implies reachability.
    """
    try:
        population = float(origin.population)
        capacity = float(origin.population_capacity)
        resolve_below = float(condition_definition.resolve_below)
        fraction = float(max_fraction)
    except (TypeError, ValueError):
        return _blocked_event(
            world,
            origin=origin,
            condition=condition,
            condition_definition=condition_definition,
            decision_event_id=decision_event_id,
            reason="invalid_transfer_measurements",
            measurements=[],
        )

    base_measurements = [
        *(dict(item) for item in condition.source_readings),
        *_settlement_readings(origin, int(world.month_stamp)),
    ]

    if (
        not math.isfinite(population)
        or not math.isfinite(capacity)
        or not math.isfinite(resolve_below)
        or not math.isfinite(fraction)
        or population <= 0
        or capacity <= 0
        or fraction <= 0
        or fraction > 1
        or not decision_event_id
        or condition.definition_id != condition_definition.id
        or condition.target_kind != "region"
        or condition.target_id != str(origin.id)
        or not condition.is_active(int(world.month_stamp))
    ):
        return _blocked_event(
            world,
            origin=origin,
            condition=condition,
            condition_definition=condition_definition,
            decision_event_id=decision_event_id,
            reason="invalid_transfer_measurements",
            measurements=base_measurements,
        )

    threshold_population = resolve_below * capacity
    required = population - threshold_population
    if not math.isfinite(required) or required <= 0:
        return _blocked_event(
            world,
            origin=origin,
            condition=condition,
            condition_definition=condition_definition,
            decision_event_id=decision_event_id,
            reason="origin_already_below_threshold",
            measurements=base_measurements,
        )
    required = _strict_required_amount(population, threshold_population)

    candidates: list[
        tuple[
            tuple[float, float, str, object],
            CityRegion,
            float,
            float,
            float,
            Any,
        ]
    ] = []
    for candidate in world.map.regions.values():
        if not isinstance(candidate, CityRegion) or candidate is origin or candidate.id == origin.id:
            continue
        routes = world.map.get_routes_between(origin.id, candidate.id)
        if not routes:
            continue
        route = max(routes, key=lambda item: (item.quality, item.id))
        try:
            candidate_population = float(candidate.population)
            candidate_capacity = float(candidate.population_capacity)
        except (TypeError, ValueError):
            continue
        headroom = candidate_capacity - candidate_population
        safe_headroom = (
            float(condition_definition.activate_above) * candidate_capacity
            - candidate_population
        )
        if (
            not math.isfinite(candidate_population)
            or not math.isfinite(candidate_capacity)
            or not math.isfinite(headroom)
            or candidate_population < 0
            or candidate_capacity <= 0
            or headroom <= 0
            or safe_headroom <= 0
        ):
            continue
        ratio = candidate_population / candidate_capacity
        if not math.isfinite(ratio):
            continue
        if (
            "lower_settlement_load"
            in {str(getattr(item, "value", item)) for item in preferences}
            and ratio >= population / capacity
        ):
            continue
        candidates.append((
            (ratio, -float(route.quality), route.id, candidate.id),
            candidate,
            candidate_population,
            headroom,
            safe_headroom,
            route,
        ))

    candidates.sort(key=lambda item: item[0])
    maximum_by_fraction = fraction * population
    destination: CityRegion | None = None
    destination_before = 0.0
    destination_headroom = 0.0
    destination_safe_headroom = 0.0
    amount = 0.0
    selected_route = None
    for (
        _,
        candidate,
        candidate_population,
        headroom,
        safe_headroom,
        route,
    ) in candidates:
        candidate_amount = min(
            required,
            maximum_by_fraction,
            population,
            headroom,
            safe_headroom,
        )
        if math.isfinite(candidate_amount) and candidate_amount > 0:
            destination = candidate
            destination_before = candidate_population
            destination_headroom = headroom
            destination_safe_headroom = safe_headroom
            amount = candidate_amount
            selected_route = route
            break

    if destination is None:
        return _blocked_event(
            world,
            origin=origin,
            condition=condition,
            condition_definition=condition_definition,
            decision_event_id=decision_event_id,
            reason="no_reachable_destination_or_quantity",
            measurements=base_measurements,
        )

    origin_before = population
    destination.change_population(amount)
    origin.change_population(-amount)
    origin_after = float(origin.population)
    destination_after = float(destination.population)

    deltas = [
        StateDelta(
            event_id="",
            owner_kind="region",
            owner_id=str(origin.id),
            aspect="population",
            before=str(origin_before),
            after=str(origin_after),
            magnitude=origin_after - origin_before,
        ).to_dict(),
        StateDelta(
            event_id="",
            owner_kind="region",
            owner_id=str(destination.id),
            aspect="population",
            before=str(destination_before),
            after=str(destination_after),
            magnitude=destination_after - destination_before,
        ).to_dict(),
    ]
    event = Event(
        world.month_stamp,
        t(
            "population_transfer.completed",
            origin=origin.name,
            destination=destination.name,
            amount=f"{amount:.6g}",
        ),
        event_type="population_transfer_completed",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
    )
    for delta in deltas:
        delta["event_id"] = event.id
    event.causal_payload = {
        "outcome": "completed",
        "reason": "transfer_applied",
        "execution": {
            "kind": "population_transfer",
            "condition_id": condition.id,
            "condition_definition_id": condition_definition.id,
            "origin_region_id": str(origin.id),
            "destination_region_id": str(destination.id),
            "route_id": selected_route.id,
            "route_mode": selected_route.mode,
            "route_quality": selected_route.quality,
            "decision_event_id": decision_event_id,
            "preferences": [str(getattr(item, "value", item)) for item in preferences],
            "amount": amount,
            "required_amount": required,
            "max_fraction": fraction,
            "destination_headroom_before": destination_headroom,
            "destination_safe_headroom_before": destination_safe_headroom,
            "origin_ratio_before": origin_before / capacity,
            "origin_ratio_after": origin_after / capacity,
            "relief_complete": origin_after / capacity < resolve_below,
        },
        "measurements": [
            *base_measurements,
            *_settlement_readings(destination, int(world.month_stamp)),
        ],
        "deltas": deltas,
    }
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    )
    return event


__all__ = ["resolve_population_transfer"]
