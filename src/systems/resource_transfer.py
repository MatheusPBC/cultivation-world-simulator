from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)


def find_canonical_route(
    world: Any,
    source: CityRegion,
    destination: CityRegion,
    resource_id: str,
) -> dict[str, Any] | None:
    """Return one explicitly stored route, never a geometric inference.

    Routes are bidirectional canonical Map entities. Quality reduces effective
    throughput; it never creates or removes connectivity on its own.
    """
    game_map = getattr(world, "map", None)
    if game_map is None or not hasattr(game_map, "get_routes_between"):
        return None
    routes = game_map.get_routes_between(
        int(source.id),
        int(destination.id),
        resource_id=resource_id,
    )
    for route in sorted(
        routes,
        key=lambda item: (-float(item.quality), -float(item.capacity), item.id),
    ):
        effective_capacity = float(route.capacity) * float(route.quality)
        if effective_capacity <= 0:
            continue
        return {
            "route_id": str(route.id),
            "source_region_id": str(source.id),
            "destination_region_id": str(destination.id),
            "capacity": float(route.capacity),
            "quality": float(route.quality),
            "effective_capacity": effective_capacity,
            "mode": str(route.mode),
        }
    return None


def resolve_resource_transfer(
    world: Any,
    *,
    destination: CityRegion,
    resource_id: str,
    decision_event_id: str,
    preferences: Iterable[Any] = (),
    invalidations: DomainInvalidationQueue | None = None,
) -> Event:
    """Apply one grounded shipment using only declared city facts and a route."""
    if resource_id not in destination.economy.stocks:
        return _blocked(world, destination, resource_id, decision_event_id, "destination_stock_unknown")
    if resource_id not in destination.economy.capacities:
        return _blocked(world, destination, resource_id, decision_event_id, "destination_capacity_unknown")
    if resource_id not in destination.economy.access:
        return _blocked(world, destination, resource_id, decision_event_id, "destination_access_unknown")
    demand = float(destination.economy.demand_rates.get(resource_id, 0.0))
    current = float(destination.economy.stocks[resource_id])
    available_destination = destination.economy.available_stock(resource_id)
    capacity = destination.economy.capacities[resource_id]
    headroom = max(0.0, float(capacity) - current)
    needed = max(0.0, demand - (available_destination if available_destination is not None else 0.0))
    candidates: list[tuple[CityRegion, dict[str, Any], float]] = []
    route_seen = False
    source_stock_unknown = False
    for region in world.map.regions.values():
        if not isinstance(region, CityRegion) or region.id == destination.id:
            continue
        route = find_canonical_route(world, region, destination, resource_id)
        if route is None:
            continue
        route_seen = True
        source_stock = region.economy.available_stock(resource_id)
        if source_stock is None:
            source_stock_unknown = True
            continue
        source_access = float(region.economy.access.get(resource_id, 0.0))
        destination_access = float(destination.economy.access[resource_id])
        if source_stock <= 0 or source_access <= 0 or destination_access <= 0:
            continue
        candidates.append((region, route, route["effective_capacity"]))
    preference_values = {str(getattr(item, "value", item)) for item in preferences}
    candidates.sort(key=lambda item: (
        -float(item[0].economy.available_stock(resource_id) or 0.0)
        if "available_supply" in preference_values
        else 0.0,
        -float(item[1]["quality"])
        if "higher_route_quality" in preference_values
        else 0.0,
        item[1]["route_id"],
        int(item[0].id),
    ))
    if not candidates or headroom <= 0 or needed <= 0:
        if not candidates and source_stock_unknown:
            reason = "source_stock_unknown"
        else:
            reason = "no_transferable_quantity" if route_seen else "route_unknown"
        return _blocked(
            world,
            destination,
            resource_id,
            decision_event_id,
            reason,
        )

    source, route, transport_capacity = candidates[0]
    source_available = source.economy.available_stock(resource_id)
    assert source_available is not None
    amount = min(source_available, headroom, needed, transport_capacity)
    if amount <= 0:
        return _blocked(world, destination, resource_id, decision_event_id, "no_transferable_quantity")

    source_before = float(source.economy.stocks[resource_id])
    destination_before = current
    source.economy.change_stock(resource_id, -amount)
    destination.economy.change_stock(resource_id, amount)
    source_after = float(source.economy.stocks[resource_id])
    destination_after = float(destination.economy.stocks[resource_id])
    event = Event(
        world.month_stamp,
        t(
            "{resource} moved from {source} to {destination}.",
            resource=resource_id,
            source=source.name,
            destination=destination.name,
        ),
        event_type="regional_resource_transfer_completed",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
    )
    event.causal_payload = {
        "outcome": "completed",
        "affordance": {
            "kind": "resource_transfer",
            "resource_id": resource_id,
            "source_region_id": str(source.id),
            "destination_region_id": str(destination.id),
            "route_id": route["route_id"],
            "amount": amount,
            "transport_capacity": transport_capacity,
            "route_capacity": route["capacity"],
            "route_quality": route["quality"],
            "route_mode": route["mode"],
            "access_source": source.economy.access[resource_id],
            "access_destination": destination.economy.access[resource_id],
        },
        "deltas": [
            StateDelta(owner_kind="region", owner_id=str(source.id), aspect=f"resource_stock:{resource_id}", before=str(source_before), after=str(source_after), magnitude=-amount).to_dict(),
            StateDelta(owner_kind="region", owner_id=str(destination.id), aspect=f"resource_stock:{resource_id}", before=str(destination_before), after=str(destination_after), magnitude=amount).to_dict(),
        ],
    }
    for delta in event.causal_payload["deltas"]:
        delta["event_id"] = event.id
    if invalidations is not None:
        for changed_region in (source, destination):
            invalidations.mark(DomainInvalidation(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="economy",
                target_kind="region",
                target_id=str(changed_region.id),
                reason=DomainInvalidationReason.RESOURCE_STOCK_CHANGED,
                source_event_ids=(event.id,),
                revision=event.id,
            ))
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=decision_event_id,
        relation=CausalRelation.MOTIVATED_BY,
    ))
    return event


def _blocked(world: Any, destination: CityRegion, resource_id: str, decision_event_id: str, reason: str) -> Event:
    event = Event(
        world.month_stamp,
        t(
            "{destination} could not receive {resource}.",
            destination=destination.name,
            resource=resource_id,
        ),
        event_type="regional_resource_transfer_blocked",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={"region_id": str(destination.id), "resource_id": resource_id, "reason": reason},
        causal_payload={
            "outcome": "blocked",
            "reason": reason,
            "affordance": {
                "kind": "resource_transfer",
                "resource_id": resource_id,
                "destination_region_id": str(destination.id),
            },
        },
    )
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=decision_event_id,
        relation=CausalRelation.MOTIVATED_BY,
    ))
    return event
