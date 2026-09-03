"""Grounded providers and owner executors for collective domains."""

from __future__ import annotations

import math
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef, PrimitiveDimension
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationReason,
)
from src.systems.city_interpreter import derive_eligible_capability_ids
from src.systems.city_maintenance import execute_urban_maintenance
from src.systems.domain_affordance_registry import (
    AffordanceContext,
    DOMAIN_AFFORDANCES,
)
from src.systems.resource_transfer import resolve_resource_transfer
from src.systems.sect_member_support import (
    eligible_member_ids,
    execute_sect_member_support,
)
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    can_start_urban_capacity_project,
    start_urban_capacity_project,
)


MAX_POPULATION_TRANSFER_FRACTION = 0.20
SAFE_DESTINATION_LOAD_RATIO = 0.85


def _region(world: Any, region_id: str) -> CityRegion | None:
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    item = regions.get(region_id)
    if item is None:
        try:
            item = regions.get(int(region_id))
        except (TypeError, ValueError):
            return None
    return item if isinstance(item, CityRegion) else None


def _condition_urgency(context: AffordanceContext) -> float:
    intensity = getattr(context.condition, "intensity", 0.0)
    try:
        return max(0.0, min(1.0, float(intensity)))
    except (TypeError, ValueError):
        return 0.0


def _actor_region_id(actor_ref: EntityRef) -> str:
    return actor_ref.id.split(":", 1)[1] if actor_ref.id.startswith("region:") else actor_ref.id


def population_affordances(context: AffordanceContext):
    origin = _region(context.world, _actor_region_id(context.actor_ref))
    condition = context.condition
    if (
        origin is None
        or condition is None
        or condition.target_kind != "region"
        or str(condition.target_id) != str(origin.id)
        or not condition.is_active(int(context.world.month_stamp))
    ):
        return ()
    population = float(origin.population)
    capacity = float(origin.population_capacity)
    if population <= 0 or capacity <= 0 or population / capacity <= 0.85:
        return ()
    urgency = _condition_urgency(context)
    desired_fraction = min(
        MAX_POPULATION_TRANSFER_FRACTION,
        max(0.02, MAX_POPULATION_TRANSFER_FRACTION * urgency),
    )
    desired = population * desired_fraction
    options: list[DomainAffordance] = []
    for destination in sorted(
        getattr(context.world.map, "regions", {}).values(),
        key=lambda item: str(getattr(item, "id", "")),
    ):
        if not isinstance(destination, CityRegion) or destination.id == origin.id:
            continue
        routes = sorted(
            context.world.map.get_routes_between(origin.id, destination.id),
            key=lambda item: (-float(item.quality), item.id),
        )
        if not routes:
            continue
        route = routes[0]
        route_capacity = float(
            context.world.map.get_route_operational_capacity(route.id)
        )
        safe_headroom = (
            SAFE_DESTINATION_LOAD_RATIO * float(destination.population_capacity)
            - float(destination.population)
        )
        if safe_headroom <= 0 or route_capacity <= 0:
            continue
        amount = min(desired, safe_headroom, route_capacity, population)
        if amount <= 0 or not math.isfinite(amount):
            continue
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind="population_transfer",
                target_refs=(
                    EntityRef("region", str(origin.id)),
                    EntityRef("region", str(destination.id)),
                ),
                parameters={
                    "origin_region_id": str(origin.id),
                    "destination_region_id": str(destination.id),
                    "route_id": str(route.id),
                    "amount": amount,
                    "desired_fraction": desired_fraction,
                    "safe_destination_ratio": SAFE_DESTINATION_LOAD_RATIO,
                },
                urgency=urgency,
                motivation_event_ids=(context.trigger_event.id,),
            )
        )
    return tuple(options)


def economy_affordances(context: AffordanceContext):
    params = context.trigger_event.render_params or {}
    destination = _region(context.world, str(params.get("region_id", "")))
    resource_id = str(params.get("resource_id", "")).strip()
    if (
        destination is None
        or not resource_id
        or resource_id not in destination.economy.stocks
        or resource_id not in destination.economy.capacities
        or resource_id not in destination.economy.access
    ):
        return ()
    demand = float(destination.economy.demand_rates.get(resource_id, 0.0))
    available = destination.economy.available_stock(resource_id)
    need = max(0.0, demand - float(available or 0.0))
    headroom = max(
        0.0,
        float(destination.economy.capacities[resource_id])
        - float(destination.economy.stocks[resource_id]),
    )
    candidates: list[tuple[float, float, str, CityRegion, dict[str, Any]]] = []
    from src.systems.resource_transfer import find_canonical_route

    for source in getattr(context.world.map, "regions", {}).values():
        if not isinstance(source, CityRegion) or source.id == destination.id:
            continue
        route = find_canonical_route(context.world, source, destination, resource_id)
        stock = source.economy.available_stock(resource_id)
        if route is None or stock is None or stock <= 0:
            continue
        candidates.append((-float(stock), -float(route["quality"]), route["route_id"], source, route))
    if not candidates or need <= 0 or headroom <= 0:
        return ()
    _, _, _, source, route = sorted(candidates, key=lambda item: item[:3])[0]
    amount = min(
        float(source.economy.available_stock(resource_id) or 0.0),
        need,
        headroom,
        float(route["effective_capacity"]),
    )
    if amount <= 0:
        return ()
    urgency = max(0.0, min(1.0, need / max(demand, 1e-9)))
    return (
        DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind="resource_transfer",
            target_refs=(
                EntityRef("region", str(source.id)),
                EntityRef("region", str(destination.id)),
            ),
            parameters={
                "resource_id": resource_id,
                "source_region_id": str(source.id),
                "destination_region_id": str(destination.id),
                "route_id": route["route_id"],
                "amount": amount,
            },
            urgency=urgency,
            motivation_event_ids=(context.trigger_event.id,),
        ),
    )


def _city_options(
    context: AffordanceContext, region: CityRegion
) -> tuple[DomainAffordance, ...]:
    condition = context.condition
    if condition is None:
        return ()
    urgency = _condition_urgency(context)
    options: list[DomainAffordance] = []
    relevant = set(
        derive_eligible_capability_ids(
            context.world,
            region,
            condition,
            region.city_state.assets,
        )
    )
    damaged_capabilities = {
        capability
        for asset in region.city_state.assets
        if asset.integrity < 1.0
        for capability in asset.capability_ids
    }
    for capability_id in sorted(damaged_capabilities):
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind="urban_maintenance",
                target_refs=(EntityRef("region", str(region.id)),),
                parameters={
                    "region_id": str(region.id),
                    "capability_id": capability_id,
                },
                urgency=(urgency if capability_id in relevant else urgency * 0.5),
                motivation_event_ids=(context.trigger_event.id,),
            )
        )
    if (
        float(region.population_capacity) > 0
        and float(region.population) / float(region.population_capacity) > 0.85
        and can_start_urban_capacity_project(
            region,
            target_settlement_ratio=float(
                getattr(
                    context.world.mechanical_language.condition_definitions.get(
                        condition.definition_id
                    ),
                    "resolve_below",
                    0.75,
                )
            ),
        )
    ):
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind="urban_capacity_project",
                target_refs=(EntityRef("region", str(region.id)),),
                parameters={
                    "region_id": str(region.id),
                    "project_kind": PROJECT_KIND,
                    "target_settlement_ratio": float(
                        context.world.mechanical_language.condition_definitions[
                            condition.definition_id
                        ].resolve_below
                    ),
                },
                urgency=urgency,
                motivation_event_ids=(context.trigger_event.id,),
            )
        )
    return tuple(options)


def city_affordances(context: AffordanceContext):
    region = _region(context.world, _actor_region_id(context.actor_ref))
    if region is None:
        return ()
    governance = region.city_state.governance
    if governance.controller_kind or governance.controller_id:
        return ()
    return _city_options(context, region)


def government_affordances(context: AffordanceContext):
    condition = context.condition
    if condition is None:
        return ()
    region = _region(context.world, str(condition.target_id))
    if region is None:
        return ()
    governance = region.city_state.governance
    if governance.controller_kind != "dynasty" or governance.controller_id != context.actor_ref.id:
        return ()
    return _city_options(context, region)


def _active_sect(world: Any, sect_id: str):
    context = getattr(world, "sect_context", None)
    candidates = context.get_active_sects() if context is not None else getattr(world, "existed_sects", ())
    return next((item for item in candidates if str(item.id) == sect_id and item.is_active), None)


def _is_risk_condition(world: Any, condition: Any) -> bool:
    definition = world.mechanical_language.condition_definitions.get(condition.definition_id)
    metric = (
        world.mechanical_language.derived_definitions.get(definition.metric_definition_id)
        if definition is not None
        else None
    )
    return metric is not None and metric.dimension is PrimitiveDimension.RISK


def organization_affordances(context: AffordanceContext):
    condition = context.condition
    sect = _active_sect(context.world, context.actor_ref.id)
    if condition is None or sect is None or not _is_risk_condition(context.world, condition):
        return ()
    region_id = str(condition.target_id)
    urgency = _condition_urgency(context)
    return tuple(
        DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind="support_member",
            target_refs=(EntityRef("avatar", member_id), EntityRef("region", region_id)),
            parameters={"member_id": member_id, "region_id": region_id},
            urgency=urgency,
            motivation_event_ids=(context.trigger_event.id,),
        )
        for member_id in eligible_member_ids(sect, region_id=region_id)
    )


def _execute_population(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    invalidations: Any = None,
    **_: Any,
) -> Event:
    params = option.parameters
    origin = _region(context.world, str(params["origin_region_id"]))
    destination = _region(context.world, str(params["destination_region_id"]))
    if origin is None or destination is None:
        raise ValueError("population affordance target disappeared")
    amount = float(params["amount"])
    origin_before = float(origin.population)
    destination_before = float(destination.population)
    origin.change_population(-amount)
    destination.change_population(amount)
    event = Event(
        context.world.month_stamp,
        t(
            "population_transfer.completed",
            origin=origin.name,
            destination=destination.name,
            amount=f"{amount:.6g}",
        ),
        event_type="population_transfer_completed",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "origin_region_id": str(origin.id),
            "destination_region_id": str(destination.id),
            "amount": amount,
            "affordance_id": option.id,
        },
    )
    deltas = [
        StateDelta(
            event_id=event.id,
            owner_kind="region",
            owner_id=str(origin.id),
            aspect="population",
            before=str(origin_before),
            after=str(origin.population),
            magnitude=-amount,
        ),
        StateDelta(
            event_id=event.id,
            owner_kind="region",
            owner_id=str(destination.id),
            aspect="population",
            before=str(destination_before),
            after=str(destination.population),
            magnitude=amount,
        ),
    ]
    event.causal_payload = {
        "outcome": "completed",
        "affordance_id": option.id,
        "amount": amount,
        "measurements": list(getattr(context.condition, "source_readings", ()) or ()),
        "deltas": [item.to_dict() for item in deltas],
    }
    event.causal_links.extend(
        [
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            ),
            CausalLink(
                event_id=event.id,
                cause_event_id=context.trigger_event.id,
                relation=CausalRelation.TRIGGERED_BY,
            ),
        ]
    )
    if invalidations is not None:
        for changed in (origin, destination):
            invalidations.mark(
                DomainInvalidation(
                    layer=DomainInvalidationLayer.MECHANICAL,
                    domain="population",
                    target_kind="region",
                    target_id=str(changed.id),
                    reason=DomainInvalidationReason.POPULATION_CHANGED,
                    source_event_ids=(event.id,),
                    revision=event.id,
                )
            )
    return event


def _execute_resource(context, option, *, decision_event_id: str, invalidations=None, **_):
    destination = _region(context.world, str(option.parameters["destination_region_id"]))
    if destination is None:
        raise ValueError("resource affordance target disappeared")
    event = resolve_resource_transfer(
        context.world,
        destination=destination,
        resource_id=str(option.parameters["resource_id"]),
        decision_event_id=decision_event_id,
        preferences=("available_supply", "higher_route_quality"),
        invalidations=invalidations,
    )
    if event.causal_payload is not None:
        event.causal_payload["affordance_id"] = option.id
    return event


def _execute_maintenance(context, option, *, decision_event_id: str, invalidations=None, **_):
    region = _region(context.world, str(option.parameters["region_id"]))
    if region is None:
        raise ValueError("city affordance target disappeared")
    event = execute_urban_maintenance(
        context.world,
        region,
        capability_id=str(option.parameters["capability_id"]),
        decision_event_id=decision_event_id,
        trigger_event_id=context.trigger_event.id,
        invalidations=invalidations,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


def _execute_project(context, option, *, decision_event_id: str, invalidations=None, **_):
    region = _region(context.world, str(option.parameters["region_id"]))
    if region is None:
        raise ValueError("city affordance target disappeared")
    event = start_urban_capacity_project(
        context.world,
        region,
        decision_event_id=decision_event_id,
        trigger_event_id=context.trigger_event.id,
        target_settlement_ratio=float(option.parameters["target_settlement_ratio"]),
        invalidations=invalidations,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


def _execute_support(context, option, *, decision_event_id: str, **_):
    sect = _active_sect(context.world, context.actor_ref.id)
    if sect is None:
        raise ValueError("organization affordance actor disappeared")
    event = execute_sect_member_support(
        context.world,
        sect,
        member_id=str(option.parameters["member_id"]),
        region_id=str(option.parameters["region_id"]),
        decision_event_id=decision_event_id,
        condition_event_id=context.trigger_event.id,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


for _domain, _provider in (
    ("population", population_affordances),
    ("economy", economy_affordances),
    ("city", city_affordances),
    ("government", government_affordances),
    ("organization", organization_affordances),
):
    DOMAIN_AFFORDANCES.register_provider(_domain, _provider)

for _action, _executor in (
    ("population_transfer", _execute_population),
    ("resource_transfer", _execute_resource),
    ("urban_maintenance", _execute_maintenance),
    ("urban_capacity_project", _execute_project),
    ("support_member", _execute_support),
):
    DOMAIN_AFFORDANCES.register_executor(_action, _executor)


__all__ = [
    "MAX_POPULATION_TRANSFER_FRACTION",
    "SAFE_DESTINATION_LOAD_RATIO",
    "city_affordances",
    "economy_affordances",
    "government_affordances",
    "organization_affordances",
    "population_affordances",
]
