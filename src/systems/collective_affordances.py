"""Grounded providers and owner executors for collective domains."""

from __future__ import annotations

import math
from collections.abc import Mapping
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
    StaleAffordanceError,
    validate_actor_decision,
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


def _petition_option(context: AffordanceContext, origin) -> tuple[DomainAffordance, ...]:
    """Addressing the government is an option, never an obligation."""
    from src.systems.civil_petition import PETITION_ACTION, can_file_public_petition

    condition = context.condition
    # The condition that opened this reaction was activated in this very step,
    # so its cause is still only in the phase's own events, not in storage.
    if not can_file_public_petition(
        context.world, origin, condition, overlays=(context.trigger_event,)
    ):
        return ()
    from src.systems.civil_petition import governing_institution_ref

    institution_ref = governing_institution_ref(context.world, origin)
    return (DomainAffordance(
        domain=context.domain,
        actor_ref=context.actor_ref,
        action_kind=PETITION_ACTION,
        target_refs=(EntityRef("region", str(origin.id)), institution_ref),
        parameters={
            "region_id": str(origin.id),
            "condition_instance_id": str(condition.id),
        },
        urgency=_condition_urgency(context),
        motivation_event_ids=(context.trigger_event.id,),
    ),)


def _stoppage_option(context: AffordanceContext, origin) -> tuple[DomainAffordance, ...]:
    """Stopping work is one option, never a required next step."""
    from src.systems.civil_petition import (
        STOPPAGE_ACTION,
        can_declare_work_stoppage,
        labor_bearing_resources,
        prior_local_petition,
        stoppage_participation,
    )

    condition = context.condition
    if not can_declare_work_stoppage(
        context.world, origin, condition, overlays=(context.trigger_event,)
    ):
        return ()
    petition = prior_local_petition(
        context.world, origin, condition=condition,
        current_events=(context.trigger_event,),
    )
    return (DomainAffordance(
        domain=context.domain,
        actor_ref=context.actor_ref,
        action_kind=STOPPAGE_ACTION,
        target_refs=(EntityRef("region", str(origin.id)),),
        parameters={
            "region_id": str(origin.id),
            "condition_instance_id": str(condition.id),
            "petition_event_id": str(petition.id),
            "participation": stoppage_participation(condition),
            "affected_resource_ids": labor_bearing_resources(origin),
        },
        urgency=_condition_urgency(context),
        motivation_event_ids=(context.trigger_event.id,),
    ),)


def _riot_option(context: AffordanceContext, origin) -> tuple[DomainAffordance, ...]:
    """One option per asset a crowd could really damage, or none at all.

    An asset with no declared `UrbanCrowdDamageProfile` is absent from this
    menu because its physical aptitude is unknown, not because it is immune.
    The engine fixes the target's damage; the choice is only which listed
    target, or none.
    """
    from src.systems.civil_riot import (
        RIOT_ACTION,
        aggrieved_crowd_wan,
        projected_service_access,
        riotable_targets,
    )

    condition = context.condition
    if condition is None:
        return ()
    options: list[DomainAffordance] = []
    for asset, capability_id, damage in riotable_targets(
        context.world, origin, condition, overlays=(context.trigger_event,)
    ):
        access_now, access_after = projected_service_access(
            origin, asset, capability_id, damage
        )
        options.append(DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind=RIOT_ACTION,
            target_refs=(EntityRef("region", str(origin.id)),),
            parameters={
                "region_id": str(origin.id),
                "condition_instance_id": str(condition.id),
                "asset_id": str(asset.id),
                "capability_id": str(capability_id),
                "damage": damage,
                # Stated so the choice can be weighed rather than guessed: the
                # crowd this grievance could gather, the declared effort the
                # fabric costs, and what breaking it does to the very service
                # being demanded. Estimates, not measurements.
                "crowd_wan": aggrieved_crowd_wan(origin, asset, capability_id),
                "breach_effort_wan": float(
                    asset.crowd_damage_profile.breach_effort_wan
                ),
                "service_access_now": access_now,
                "service_access_after_damage": access_after,
            },
            urgency=_condition_urgency(context),
            motivation_event_ids=(context.trigger_event.id,),
        ))
    return tuple(options)


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
    # Offered alongside migration, so the population chooses between speaking
    # to its government, leaving, or doing neither.
    petition = _petition_option(context, origin)
    stoppage = _stoppage_option(context, origin)
    riot = _riot_option(context, origin)
    population = float(origin.population)
    capacity = float(origin.population_capacity)
    if population <= 0 or capacity <= 0 or population / capacity <= 0.85:
        # Not crowded enough to migrate, but the grievance can still be voiced.
        return (*petition, *stoppage, *riot)
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
    return (*options, *petition, *stoppage, *riot)


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


def _settlement_target(context: AffordanceContext, condition) -> float:
    """The settlement ratio this expansion should aim at.

    A live condition states its own resolve threshold, which is the most
    grounded answer available. Without one the canonical owner default is
    used, so no new number is introduced for the condition-free path.
    """
    from src.systems.urban_capacity_project import (
        DEFAULT_TARGET_SETTLEMENT_RATIO,
    )

    if condition is None:
        return DEFAULT_TARGET_SETTLEMENT_RATIO
    definition = context.world.mechanical_language.condition_definitions.get(
        condition.definition_id
    )
    return float(
        getattr(definition, "resolve_below", DEFAULT_TARGET_SETTLEMENT_RATIO)
    )


def _city_options(
    context: AffordanceContext, region: CityRegion
) -> tuple[DomainAffordance, ...]:
    condition = context.condition
    urgency = _condition_urgency(context)
    options: list[DomainAffordance] = []
    # The menu is what this city can materially do right now. A live condition
    # enriches it by saying which capabilities are relevant; its absence is not
    # a reason to offer nothing, and a substitute condition is never invented.
    relevant = (
        set(
            derive_eligible_capability_ids(
                context.world,
                region,
                condition,
                region.city_state.assets,
            )
        )
        if condition is not None
        else set()
    )
    # Damage headroom per capability: the real, current shortfall of the worst
    # asset that provides it. Without a condition this is the only honest
    # urgency available, and it is read from the assets, never from the prose
    # or the kind of event that triggered the reaction.
    damage: dict[str, float] = {}
    for asset in region.city_state.assets:
        headroom = max(0.0, 1.0 - float(asset.integrity))
        if headroom <= 0.0:
            continue
        for capability in asset.capability_ids:
            damage[capability] = max(damage.get(capability, 0.0), headroom)
    # Maintenance costs administrative capacity the city may simply not have.
    # Offering it anyway would make the menu a wish list instead of a
    # statement of what this government can do.
    if float(region.city_state.governance.administrative_capacity) > 0:
        for capability_id in sorted(damage):
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
                    urgency=(
                        (urgency if capability_id in relevant else urgency * 0.5)
                        if condition is not None
                        else damage[capability_id]
                    ),
                    motivation_event_ids=(context.trigger_event.id,),
                )
            )
    settlement_ratio = (
        float(region.population) / float(region.population_capacity)
        if float(region.population_capacity) > 0
        else 0.0
    )
    if settlement_ratio > 0.85 and can_start_urban_capacity_project(
        region,
        target_settlement_ratio=_settlement_target(context, condition),
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
                    "target_settlement_ratio": _settlement_target(
                        context, condition
                    ),
                },
                urgency=(
                    urgency
                    if condition is not None
                    else min(1.0, settlement_ratio)
                ),
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
    from src.systems.civil_petition import (
        canonical_stoppage_payload,
        civil_response_is_open,
        petition_payload,
    )

    from src.systems.civil_petition import STOPPAGE_EVENT_TYPE
    from src.systems.civic_endorsement import (
        ENDORSEMENT_EVENT_TYPE,
        canonical_endorsement_payload,
    )
    from src.systems.civil_riot import RIOT_EVENT_TYPE, canonical_riot_payload

    condition = context.condition
    civil_kind = "petition"
    civil = petition_payload(context.trigger_event)
    if civil is None:
        # Read from the stored fact, so composing against a loose object that
        # merely looks like a civil fact offers nothing. The government answers
        # on a later cycle than the fact, so it is genuinely stored by then.
        civil_kind = "stoppage"
        civil = canonical_stoppage_payload(context.world, context.trigger_event)
    if civil is None:
        civil_kind = "riot"
        civil = canonical_riot_payload(context.world, context.trigger_event)
    if civil is None:
        civil_kind = "endorsement"
        civil = canonical_endorsement_payload(
            context.world, context.trigger_event
        )
    if civil is None and context.trigger_event.event_type in (
        STOPPAGE_EVENT_TYPE, RIOT_EVENT_TYPE, ENDORSEMENT_EVENT_TYPE
    ):
        # A trigger claiming to be a civil fact that canonical state does not
        # recognise offers nothing, even alongside a perfectly valid condition:
        # the condition must not launder the unknown fact.
        return ()
    if condition is not None:
        region = _region(context.world, str(condition.target_id))
    elif civil is not None:
        # A civil fact names its own region. Its grievance may already have
        # been resolved; that removes the enrichment, not the government's
        # ability to answer what actually happened.
        region = _region(context.world, str(civil.get("region_id", "")))
    else:
        return ()
    if region is None:
        return ()
    governance = region.city_state.governance
    if governance.controller_kind != "dynasty" or governance.controller_id != context.actor_ref.id:
        return ()
    # Matching the controller id says who governs on paper; it does not say
    # anyone can currently act. An office whose holder is dead or missing
    # authorizes nothing, so the menu is empty and `revalidate` refuses --
    # before any owner mutates the city, not after. The civil branch below
    # asks the same question through its own gate.
    if not _can_administer_now(context, region):
        return ()
    # When the trigger is a civil fact, the institution that was actually
    # addressed must still govern here and still hold the authority to answer.
    # Recomposition runs after the interpreter's await, so losing authority
    # while deciding empties the menu and the reaction is blocked rather than
    # mutating anything.
    if civil is not None and not civil_response_is_open(
        context.world, region, context.trigger_event, civil, civil_kind
    ):
        return ()
    return _city_options(context, region)


def _can_administer_now(context: AffordanceContext, region: CityRegion) -> bool:
    """Whether this actor can really administer this region right now.

    Asked of the institution, under the scope urban work actually needs, with
    material control over this very region. Unclaimed cities go through
    `city_affordances` and keep their existing semantics; this is the
    government path only.
    """
    from src.classes.institution import AuthorityScope
    from src.systems.institution_authority import can_actor_act_for

    return can_actor_act_for(
        context.world,
        context.actor_ref,
        context.actor_ref,
        AuthorityScope.URBAN_ADMINISTRATION,
        current_month=int(context.world.month_stamp),
        require_material_control=True,
        material_target_ref=EntityRef("region", str(region.id)),
    ).allowed


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
    if (
        condition is None
        or sect is None
        or context.domain != "organization"
        or context.actor_ref.kind != "sect"
        or not _is_risk_condition(context.world, condition)
    ):
        return ()
    # The grievance must still be live in canonical state, and be the very
    # same instance: a context built earlier can carry a condition that has
    # since resolved, and recomposition is where that has to be caught.
    if not any(
        str(item.id) == str(condition.id)
        and str(item.cause_event_id) == str(condition.cause_event_id)
        for item in context.world.mechanical_language.get_active_conditions(
            EntityRef("region", str(condition.target_id)),
            int(context.world.month_stamp),
        )
    ):
        return ()
    # Supporting a member spends the sect's own treasury, so the office that
    # could authorize that has to have a living holder right now. Asked here,
    # in the provider, so an unauthorized sect has an empty menu and
    # `revalidate` refuses before any owner moves money. No material control
    # is required: a treasury is not territorial, and the region only says
    # where the member is.
    if not _can_dispose_treasury(context):
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


def _require_urban_authorship(
    context, option, decision_event, decision_event_id: str, *, label: str
) -> None:
    """The acting body's own decision, as a fact, authorizes an urban action.

    The same shared validator every other collective domain uses. An ID alone
    proves nothing, and validating one decision while citing another would
    leave the authorship broken.
    """
    validate_actor_decision(decision_event, context, option, label=label)
    if str(getattr(decision_event, "id", "")) != str(decision_event_id):
        raise StaleAffordanceError(f"{label} decision id does not match")


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


def _execute_maintenance(
    context, option, *, decision_event_id: str, decision_event=None,
    invalidations=None, **_,
):
    _require_urban_authorship(
        context, option, decision_event, decision_event_id, label="urban maintenance"
    )
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
    _remember_completed_maintenance(context, region, event)
    return event


def _maintenance_memory_factors(event, region) -> dict[str, float]:
    """The factors a completed repair really supports, and nothing more.

    `relative_scale` is the **observed improvement**, read from the canonical
    `urban_asset_integrity` delta on the asset's own 0..1 scale. It is not
    divided by `MAX_MAINTENANCE_IMPROVEMENT`: an execution cap limits what one
    repair may do, it is not a scale for how large the improvement was.

    The other three are frozen at zero because nothing supports them. No
    office, institution or control changed; no commitment exists; and a
    generic urban asset is not an identity anchor.

    This only reads the transition the maintenance owner already applied. A
    refusal writes no memory rather than rolling anything back.
    """
    import math

    payload = event.causal_payload if isinstance(event.causal_payload, dict) else {}
    deltas = [
        item
        for item in (payload.get("deltas") or [])
        if isinstance(item, Mapping)
        and str(item.get("aspect")) == "urban_asset_integrity"
        and str(item.get("event_id")) == str(event.id)
        and str(item.get("owner_kind")) == "region"
        and str(item.get("owner_id")) == str(region.id)
    ]
    if len(deltas) != 1:
        raise ValueError("maintenance memory requires exactly one integrity delta")
    delta = deltas[0]
    before = float(delta["before"])
    after = float(delta["after"])
    if not all(
        math.isfinite(value) and 0.0 <= value <= 1.0 for value in (before, after)
    ):
        raise ValueError("maintenance memory requires integrity endpoints in 0..1")
    observed = after - before
    if not 0.0 < observed <= 1.0:
        raise ValueError("maintenance memory requires a real, bounded improvement")
    # Endpoints, recorded magnitude and the payload figure must agree, with the
    # finiteness test first: `abs(NaN) > tol` is False and would pass silently.
    for claimed in (float(delta["magnitude"]), float(payload["improvement"])):
        if not math.isfinite(claimed) or abs(claimed - observed) > 1e-9:
            raise ValueError("maintenance memory found an incoherent delta")
    return {
        "relative_scale": observed,
        "institutional_change": 0.0,
        "commitment_breach": 0.0,
        "identity_anchor_impact": 0.0,
    }


def _remember_completed_maintenance(context, region, event) -> None:
    """Let the institution that really repaired the city remember doing it.

    This is a **knowledge and memory** gate only, and runs after the owner has
    already acted. It authorizes nothing: whether the material work was
    permitted is decided before execution, by `_can_administer_now` emptying
    the government menu so `revalidate` refuses. What is asked here is the
    narrower question of who may be said to know this happened.

    Only a completed repair, and only the institution this actor speaks for. A
    blocked attempt improved nothing and is remembered as nothing. Nothing
    here reads what prompted the repair: a riot, a condition and a petition
    all leave the same record, because the memory is of the improvement, not
    of its cause.

    Fail-closed: no institution, or no current authority, and the fact still
    stands with nobody remembering it.
    """
    from src.classes.institution import AuthorityScope, KnowledgeChannel
    from src.systems.institution_authority import can_actor_act_for
    from src.systems.institutional_memory import record_known_fact

    if str(getattr(event, "event_type", "")) != "city_maintenance_completed":
        return
    authority = getattr(context.world, "institutional_authority", None)
    if authority is None:
        return
    institution = authority.get_institution_for_owner(context.actor_ref)
    if institution is None:
        return
    verdict = can_actor_act_for(
        context.world,
        context.actor_ref,
        context.actor_ref,
        AuthorityScope.URBAN_ADMINISTRATION,
        current_month=int(context.world.month_stamp),
        require_material_control=True,
        material_target_ref=EntityRef("region", str(region.id)),
    )
    if not verdict.allowed:
        return
    record_known_fact(
        context.world,
        event,
        (institution.id,),
        factors=_maintenance_memory_factors(event, region),
        # The institution did the work; it was not told and did not witness.
        channel=KnowledgeChannel.OWN_ACTION,
    )


def _execute_project(
    context, option, *, decision_event_id: str, decision_event=None,
    invalidations=None, **_,
):
    _require_urban_authorship(
        context, option, decision_event, decision_event_id,
        label="urban capacity project",
    )
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


def _can_dispose_treasury(context: AffordanceContext) -> bool:
    """Whether this sect can really spend its treasury right now."""
    from src.classes.institution import AuthorityScope
    from src.systems.institution_authority import can_actor_act_for

    return can_actor_act_for(
        context.world,
        context.actor_ref,
        context.actor_ref,
        AuthorityScope.TREASURY_DISPOSITION,
        current_month=int(context.world.month_stamp),
    ).allowed


def _execute_support(
    context, option, *, decision_event_id: str, decision_event=None, **_
):
    """Delegate wholly to the support owner.

    The owner revalidates authorship, the option and current treasury
    authority itself, so this registry path and a direct call are the same
    single operation. No validation is duplicated here.
    """
    event = execute_sect_member_support(
        context,
        option,
        decision_event_id=decision_event_id,
        decision_event=decision_event,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


def _execute_petition(
    context, option, *, decision_event_id: str, decision_event=None, **_
):
    """Revalidate at the boundary, then let the petition owner record it.

    The population's own canonical decision is validated by the shared
    collective validator before anything is written; an ID alone authorizes
    nothing, and no actor decision is ever fabricated here.
    """
    from src.systems.civil_petition import (
        can_file_public_petition,
        record_public_petition,
    )

    validate_actor_decision(decision_event, context, option, label="public petition")
    # Validating one fact while citing another id would leave the authorship
    # broken; the object and the citation must be the same decision.
    if str(getattr(decision_event, "id", "")) != str(decision_event_id):
        raise StaleAffordanceError("public petition decision id does not match")
    region = _region(context.world, str(option.parameters["region_id"]))
    condition = context.condition
    if (
        region is None
        or condition is None
        or str(condition.id) != str(option.parameters["condition_instance_id"])
        or not can_file_public_petition(
            context.world, region, condition, overlays=(context.trigger_event,)
        )
    ):
        raise StaleAffordanceError("public petition is absent or stale")
    event = record_public_petition(
        context.world,
        region=region,
        condition=condition,
        decision_event_id=decision_event_id,
        affordance_id=option.id,
        source_event=context.trigger_event,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


def _execute_stoppage(
    context, option, *, decision_event_id: str, decision_event=None, **_
):
    """Revalidate at the boundary, then let the civil owner record it."""
    from src.systems.civil_petition import (
        can_declare_work_stoppage,
        prior_local_petition,
        record_work_stoppage,
    )

    validate_actor_decision(decision_event, context, option, label="work stoppage")
    if str(getattr(decision_event, "id", "")) != str(decision_event_id):
        raise StaleAffordanceError("work stoppage decision id does not match")
    region = _region(context.world, str(option.parameters["region_id"]))
    condition = context.condition
    if (
        region is None
        or condition is None
        or str(condition.id) != str(option.parameters["condition_instance_id"])
        or not can_declare_work_stoppage(
            context.world, region, condition, overlays=(context.trigger_event,)
        )
    ):
        raise StaleAffordanceError("work stoppage is absent or stale")
    petition = prior_local_petition(
        context.world, region, condition=condition,
        current_events=(context.trigger_event,),
    )
    if petition is None or petition.id != str(option.parameters["petition_event_id"]):
        raise StaleAffordanceError("work stoppage cites a stale petition")
    event = record_work_stoppage(
        context.world,
        region=region,
        condition=condition,
        petition_event=petition,
        decision_event_id=decision_event_id,
        affordance_id=option.id,
    )
    event.causal_payload["affordance_id"] = option.id
    return event


def _execute_riot(
    context, option, *, decision_event_id: str, decision_event=None,
    invalidations=None, **_,
):
    """Delegate wholly to the damage owner.

    The owner revalidates authorship, re-derives the magnitude from current
    state and the asset's declared profile, and records the aftermath itself,
    so this registry path and a direct call are the same single operation.
    """
    from src.systems.city_damage import execute_crowd_damage

    return execute_crowd_damage(
        context,
        option,
        decision_event_id=decision_event_id,
        decision_event=decision_event,
        invalidations=invalidations,
    )


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
    ("file_public_petition", _execute_petition),
    ("declare_work_stoppage", _execute_stoppage),
    ("join_public_riot", _execute_riot),
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
