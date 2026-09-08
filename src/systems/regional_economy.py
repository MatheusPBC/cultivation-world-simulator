from __future__ import annotations

from typing import Any

from src.classes.environment.region import CityRegion
from src.classes.regional_economy import QUANTITY_EPSILON
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
    from src.systems.civil_petition import expire_work_stoppages

    # A stoppage lasts exactly one cycle, and its duration alone ends it.
    # Retiring it here, before any output is computed, means production really
    # resumes this month and does not depend on any other phase running.
    events: list[Event] = list(expire_work_stoppages(world))
    for region in world.map.regions.values():
        if not isinstance(region, CityRegion):
            continue
        economy = region.economy
        resource_ids = sorted(
            set(economy.production_rates) | set(economy.demand_rates)
        )
        for resource_id in resource_ids:
            if resource_id not in economy.stocks:
                continue
            before = float(economy.stocks[resource_id])
            # One headroom, read before anything is produced or consumed, so
            # the counterfactual below compares like with like.
            headroom_before = _headroom(economy, resource_id)
            produced = min(
                # The owner's own effective rate, so a stoppage is felt here
                # and in every FLOW reading identically.
                economy.effective_production_rate(
                    resource_id, int(world.month_stamp)
                ),
                headroom_before,
            )
            reserved = sum(
                resources.get(resource_id, 0.0)
                for resources in economy.reservations.values()
            )
            available_after_production = max(0.0, before + produced - reserved)
            demand = float(economy.demand_rates.get(resource_id, 0.0))
            consumed = min(demand, available_after_production)
            after = before + produced - consumed
            economy.set_stock(resource_id, after)
            # Float arithmetic leaves noise far below any real quantity; the
            # owner's own epsilon decides whether stock actually moved.
            net_changed = abs(after - before) > QUANTITY_EPSILON

            # What the stoppage really cost, at the warehouse: output that
            # would have been stored but was not. A full warehouse loses
            # nothing, and nothing is claimed to have been lost.
            stoppage = economy.work_stoppage
            forgone = 0.0
            if stoppage is not None and stoppage.is_active(int(world.month_stamp)):
                forgone = max(
                    0.0,
                    min(
                        float(economy.production_rates.get(resource_id, 0.0)),
                        headroom_before,
                    )
                    - produced,
                )
            if forgone > 0.0 and not net_changed:
                # A real flow fact with no net stock change: stated as flow,
                # never as an invented before/after delta.
                events.append(_build_stoppage_flow_event(
                    world, region, resource_id,
                    produced=produced, consumed=consumed, forgone=forgone,
                    start_event_id=str(stoppage.start_event_id),
                ))
            if net_changed:
                balance = _build_balance_event(
                    world,
                    region,
                    resource_id,
                    before=before,
                    after=after,
                    produced=produced,
                    consumed=consumed,
                    causal=causal,
                    invalidations=invalidations,
                )
                # Only when this resource really lost output to the stoppage:
                # a non-labour concept and a full warehouse forgo nothing and
                # are never attributed to it.
                if forgone > 0.0:
                    balance.render_params["forgone"] = forgone
                    balance.causal_links.append(CausalLink(
                        event_id=balance.id,
                        cause_event_id=str(stoppage.start_event_id),
                        relation=CausalRelation.CONTRIBUTED_TO,
                    ))
                events.append(balance)
            if consumed < demand:
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
                        "demand": demand,
                        "available": available_after_production,
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
                # The stoppage is a real cause of this shortage only where it
                # really cost output.
                if forgone > 0.0:
                    shortage.render_params["forgone"] = forgone
                    shortage.causal_links.append(CausalLink(
                        event_id=shortage.id,
                        cause_event_id=str(stoppage.start_event_id),
                        relation=CausalRelation.CONTRIBUTED_TO,
                    ))
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
            and str(delta.get("aspect")) in {
                "enabled",
                "capacity",
                "quality",
                "operational_capacity",
            }
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


def _build_stoppage_flow_event(
    world: Any,
    region: CityRegion,
    resource_id: str,
    *,
    produced: float,
    consumed: float,
    forgone: float,
    start_event_id: str,
) -> Event:
    """Output really forgone to a stoppage, when stock did not move.

    An OCCURRENCE with no delta: nothing transitioned, so nothing is claimed
    to have. The flow figures and the stoppage that caused them are the fact.
    """
    event = Event(
        world.month_stamp,
        t(
            "{region} produced less {resource} during the work stoppage.",
            region=region.name,
            resource=resource_id,
        ),
        event_type="regional_production_forgone",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        render_params={
            "region_id": str(region.id),
            "resource_id": resource_id,
            "produced": produced,
            "consumed": consumed,
            "forgone": forgone,
        },
        causal_payload={"deltas": []},
    )
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=start_event_id,
        relation=CausalRelation.TRIGGERED_BY,
    ))
    return event


def _build_balance_event(
    world: Any,
    region: CityRegion,
    resource_id: str,
    *,
    before: float,
    after: float,
    produced: float,
    consumed: float,
    causal: Any | None,
    invalidations: Any | None,
) -> Event:
    delta = after - before
    event = Event(
        world.month_stamp,
        t(
            "{region} monthly {resource} balance changed stock by {amount}.",
            region=region.name,
            resource=resource_id,
            amount=f"{delta:+.2f}",
        ),
        event_type="regional_resource_balance",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        render_params={
            "region_id": str(region.id),
            "resource_id": resource_id,
            "produced": produced,
            "consumed": consumed,
            "net_amount": delta,
        },
    )
    state_delta = StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(region.id),
        aspect=f"resource_stock:{resource_id}",
        before=str(before),
        after=str(after),
        magnitude=delta,
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
