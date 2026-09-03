"""Affordance and owner executor for explicit infrastructure maintainers."""

from __future__ import annotations

import math
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance, DomainDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.domain_affordance_registry import (
    AffordanceContext,
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.infrastructure_site_condition import (
    change_infrastructure_site_condition,
)


MAX_SITE_RESTORATION = 0.10
SPIRIT_STONE_PER_INTEGRITY = 100.0


def _city_maintenance_owner(world: Any, maintainer_ref: EntityRef, site: Any):
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    if maintainer_ref.kind == "city":
        try:
            region = regions.get(int(maintainer_ref.id))
        except (TypeError, ValueError):
            return None
        return region if isinstance(region, CityRegion) else None
    if maintainer_ref.kind not in {"dynasty", "sect"}:
        return None
    return next(
        (
            region
            for region in regions.values()
            if isinstance(region, CityRegion)
            and int(region.id) in site.region_ids
            and region.city_state.governance.controller_kind == maintainer_ref.kind
            and region.city_state.governance.controller_id == maintainer_ref.id
        ),
        None,
    )


def restore_infrastructure_site_affordances(context: AffordanceContext):
    options: list[DomainAffordance] = []
    for site in sorted(context.world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if site.maintainer_ref != context.actor_ref or site.integrity >= 1.0:
            continue
        owner = _city_maintenance_owner(context.world, context.actor_ref, site)
        if owner is None:
            continue
        administrative_capacity = float(
            owner.city_state.governance.administrative_capacity
        )
        stock = owner.economy.available_stock("spirit_stone")
        improvement = min(
            MAX_SITE_RESTORATION,
            1.0 - float(site.integrity),
            max(0.0, administrative_capacity) * MAX_SITE_RESTORATION,
        )
        cost = float(math.ceil(improvement * SPIRIT_STONE_PER_INTEGRITY))
        if improvement <= 0 or stock is None or stock < cost:
            continue
        urgency = min(
            1.0,
            max(0.70 if site.route_ids else 0.0, 1.0 - float(site.integrity)),
        )
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind="restore_infrastructure_site",
                target_refs=(EntityRef("infrastructure_site", site.id),),
                parameters={
                    "site_id": site.id,
                    "resource_owner_region_id": str(owner.id),
                    "resource_id": "spirit_stone",
                    "spirit_stone_cost": cost,
                    "integrity_improvement": improvement,
                },
                urgency=urgency,
                motivation_event_ids=(context.trigger_event.id,),
            )
        )
    return tuple(options)


def _execute_restoration(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    invalidations: DomainInvalidationQueue,
    **_: Any,
) -> Event:
    params = option.parameters
    site = context.world.map.infrastructure_sites.get(str(params["site_id"]))
    try:
        owner = context.world.map.regions.get(int(params["resource_owner_region_id"]))
    except (TypeError, ValueError):
        owner = None
    if site is None or not isinstance(owner, CityRegion):
        raise ValueError("restoration affordance target disappeared")
    if site.maintainer_ref != context.actor_ref:
        raise ValueError("site maintainer changed")
    cost = float(params["spirit_stone_cost"])
    improvement = float(params["integrity_improvement"])
    before_stock = float(owner.economy.stocks["spirit_stone"])
    owner.economy.change_stock("spirit_stone", -cost)
    event = change_infrastructure_site_condition(
        context.world,
        site_id=site.id,
        source_event_id=decision_event_id,
        invalidations=invalidations,
        integrity=min(1.0, float(site.integrity) + improvement),
        enabled=True,
    )
    event.causal_origin = CausalOrigin.ACTOR_DECISION
    event.event_type = "infrastructure_site_restored"
    event.render_key = "infrastructure_site_restored"
    event.render_params.update(
        {
            "maintainer_kind": context.actor_ref.kind,
            "maintainer_id": context.actor_ref.id,
            "spirit_stone_cost": cost,
            "affordance_id": option.id,
        }
    )
    stock_delta = StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(owner.id),
        aspect="resource_stock:spirit_stone",
        before=str(before_stock),
        after=str(owner.economy.stocks["spirit_stone"]),
        magnitude=-cost,
    )
    event.causal_payload.update(
        {
            "affordance_id": option.id,
            "spirit_stone_cost": cost,
            "integrity_improvement": improvement,
            "resource_owner_region_id": str(owner.id),
        }
    )
    event.causal_payload["deltas"].append(stock_delta.to_dict())
    if context.trigger_event.id != decision_event_id:
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=context.trigger_event.id,
                relation=CausalRelation.TRIGGERED_BY,
            )
        )
    return event


DOMAIN_AFFORDANCES.register_provider(
    "infrastructure_maintenance", restore_infrastructure_site_affordances
)
DOMAIN_AFFORDANCES.register_executor(
    "restore_infrastructure_site", _execute_restoration
)


def _event_by_id(world: Any, current_events: list[Event], event_id: str):
    event = next((item for item in current_events if item.id == event_id), None)
    if event is not None:
        return event
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    return getter(event_id) if callable(getter) else None


async def process_infrastructure_restoration(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
    budget: CausalBudget | None = None,
    llm_call: Any = None,
) -> list[Event]:
    budget = budget or CausalBudget.from_world(world)
    produced: list[Event] = []
    actors = sorted(
        {
            site.maintainer_ref
            for site in world.map.infrastructure_sites.values()
            if site.maintainer_ref is not None and site.integrity < 1.0
        },
        key=lambda item: (item.kind, item.id),
    )
    for actor_ref in actors:
        damaged = [
            site
            for site in world.map.infrastructure_sites.values()
            if site.maintainer_ref == actor_ref and site.integrity < 1.0
        ]
        source_ids = [site.last_event_id for site in damaged if site.last_event_id]
        source_event = next(
            (
                event
                for source_id in source_ids
                if (event := _event_by_id(world, current_events, source_id)) is not None
            ),
            None,
        )
        if source_event is None or not budget.consume_propagation_step():
            continue
        context = AffordanceContext(
            world,
            "infrastructure_maintenance",
            actor_ref,
            source_event,
        )
        options = DOMAIN_AFFORDANCES.compose(context)
        can_use_llm = budget.consume_interpreter_call()
        decision, decision_event = await interpret_domain_affordances(
            world,
            domain=context.domain,
            actor_ref=actor_ref,
            actor_label=f"{actor_ref.kind}:{actor_ref.id}",
            trigger_event=source_event,
            affordances=options,
            task_name="infrastructure_maintenance_interpreter",
            template_name="infrastructure_maintenance_interpreter.txt",
            llm_call=llm_call if can_use_llm else None,
            force_rule=not can_use_llm,
        )
        produced.append(decision_event)
        if (
            decision.decision is DomainDecisionKind.MAINTAIN
            or not budget.consume_domain_mutation()
        ):
            continue
        try:
            produced.append(
                DOMAIN_AFFORDANCES.execute(
                    context,
                    decision.selected_affordance_id or "",
                    decision_event_id=decision_event.id,
                    invalidations=invalidations,
                )
            )
        except StaleAffordanceError:
            produced.append(
                stale_affordance_blocked_event(
                    context,
                    decision_event_id=decision_event.id,
                    selected_affordance_id=decision.selected_affordance_id or "",
                )
            )
    return produced


__all__ = [
    "MAX_SITE_RESTORATION",
    "process_infrastructure_restoration",
    "restore_infrastructure_site_affordances",
]
