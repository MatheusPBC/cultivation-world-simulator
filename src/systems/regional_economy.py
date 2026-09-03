from __future__ import annotations

from typing import Any

from src.classes.environment.region import CityRegion
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import MetricKey, PrimitiveDimension
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationReason,
)


def phase_update_regional_economy(
    world: Any,
    causal: Any | None = None,
    invalidations: Any | None = None,
) -> list[Event]:
    """Apply explicit local production and demand for each city.

    This is deliberately deterministic.  No route is inferred here: a city
    only gets a flow when its own canonical production/demand rates declare
    one.  Transport and inter-city flow can be added later when the map owns
    an actual route graph.
    """
    events: list[Event] = []
    for region in world.map.regions.values():
        if not isinstance(region, CityRegion):
            continue
        economy = region.economy
        for resource_id, rate in sorted(economy.production_rates.items()):
            if resource_id not in economy.stocks:
                continue
            amount = min(float(rate), _headroom(economy, resource_id))
            if amount <= 0:
                continue
            events.append(_apply_flow(
                world,
                region,
                resource_id,
                amount,
                flow_kind="production",
                causal=causal,
                invalidations=invalidations,
            ))

        for resource_id, demand in sorted(economy.demand_rates.items()):
            available = economy.available_stock(resource_id)
            consumed = 0.0 if available is None else min(float(demand), available)
            if consumed > 0:
                events.append(_apply_flow(
                    world,
                    region,
                    resource_id,
                    -consumed,
                    flow_kind="consumption",
                    causal=causal,
                    invalidations=invalidations,
                ))
            if consumed < float(demand):
                from src.systems.semantic_world.resolvers import resolve_metric

                stock_reading = resolve_metric(
                    world,
                    MetricKey(PrimitiveDimension.STOCK, "region", str(region.id), resource_id),
                    target=region,
                    calculated_month=int(world.month_stamp),
                )
                demand_reading = resolve_metric(
                    world,
                    MetricKey(
                        PrimitiveDimension.FLOW,
                        "region",
                        str(region.id),
                        resource_id,
                        qualifiers=(("kind", "demand"),),
                    ),
                    target=region,
                    calculated_month=int(world.month_stamp),
                )
                shortage = Event(
                    world.month_stamp,
                    t(
                        "{region} could not satisfy demand for {resource}.",
                        region=region.name,
                        resource=resource_id,
                    ),
                    event_type="regional_resource_shortage",
                    fact_kind=FactKind.OCCURRENCE,
                    causal_origin=CausalOrigin.DETERMINISTIC,
                    causal_payload={
                        "measurements": [stock_reading.to_dict(), demand_reading.to_dict()],
                    },
                    render_params={
                        "region_id": str(region.id),
                        "resource_id": resource_id,
                        "demand": float(demand),
                            "available": available,
                    },
                )
                shortage.causal_links.extend(
                    CausalLink(
                        event_id=shortage.id,
                        cause_event_id=source_event_id,
                        relation=CausalRelation.CONTRIBUTED_TO,
                    )
                    for source_event_id in _resource_source_event_ids(
                        world,
                        region,
                        resource_id,
                    )
                )
                events.append(shortage)
    return events


def _resource_source_event_ids(
    world: Any,
    region: CityRegion,
    resource_id: str,
) -> tuple[str, ...]:
    pending = world.mechanical_language.pending_target_source_event_ids.get(
        f"region:{region.id}",
        (),
    )
    matching: list[str] = []
    for source_event_id in pending:
        event = world.event_manager.get_event_by_id(source_event_id)
        if event is None:
            continue
        deltas = (event.causal_payload or {}).get("deltas") or []
        region_resource_change = any(
            str(delta.get("owner_kind")) == "region"
            and str(delta.get("owner_id")) == str(region.id)
            and str(delta.get("aspect")) in {
                f"resource_stock:{resource_id}",
                f"resource_production_rate:{resource_id}",
                f"resource_demand_rate:{resource_id}",
            }
            for delta in deltas
        )
        route_change = any(
            str(delta.get("owner_kind")) == "route"
            and str(delta.get("aspect")) in {"enabled", "capacity", "quality"}
            for delta in deltas
        )
        params = event.render_params or {}
        affected_regions = {
            str(item) for item in (params.get("endpoint_region_ids") or ())
        }
        allowed_resources = {
            str(item) for item in (params.get("allowed_resource_ids") or ())
        }
        relevant_route_change = (
            route_change
            and str(region.id) in affected_regions
            and (not allowed_resources or resource_id in allowed_resources)
        )
        if region_resource_change or relevant_route_change:
            matching.append(str(source_event_id))
    return tuple(dict.fromkeys(matching))


def _headroom(economy: Any, resource_id: str) -> float:
    capacity = economy.capacities.get(resource_id)
    if capacity is None:
        return float("inf")
    return max(0.0, float(capacity) - float(economy.stocks.get(resource_id, 0.0)))


def _apply_flow(
    world: Any,
    region: CityRegion,
    resource_id: str,
    delta: float,
    *,
    flow_kind: str,
    causal: Any | None,
    invalidations: Any | None,
) -> Event:
    economy = region.economy
    before = float(economy.stocks.get(resource_id, 0.0))
    after = economy.change_stock(resource_id, delta)
    event = Event(
        world.month_stamp,
        t(
            "{region} {flow_kind} changed {resource} stock by {amount}.",
            region=region.name,
            flow_kind=flow_kind,
            resource=resource_id,
            amount=f"{abs(delta):.2f}",
        ),
        event_type=f"regional_{flow_kind}",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        render_params={
            "region_id": str(region.id),
            "resource_id": resource_id,
            "flow_kind": flow_kind,
            "amount": abs(delta),
        },
    )
    state_delta = StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(region.id),
        aspect=f"resource_stock:{resource_id}",
        before=str(before),
        after=str(after),
        magnitude=after - before,
    )
    if causal is not None:
        causal.record_delta(event.id, state_delta)
    else:
        event.causal_payload = {"deltas": [state_delta.to_dict()]}
    if invalidations is not None and after != before:
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.MECHANICAL,
            domain="economy",
            target_kind="region",
            target_id=str(region.id),
            reason=DomainInvalidationReason.RESOURCE_STOCK_CHANGED,
            source_event_ids=(event.id,),
            revision=event.id,
        ))
    return event
