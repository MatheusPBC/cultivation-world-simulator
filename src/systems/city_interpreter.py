"""Interpret the full current set of engine-owned city affordances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from src.classes.domain_affordance import DomainDecision
from src.classes.environment.city_state import UrbanAsset
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef, PrimitiveDimension
from src.systems.domain_affordance_registry import AffordanceContext, DOMAIN_AFFORDANCES
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.semantic_world.condition_semantics import metric_leaves


CITY_INTERPRETER_TASK = "city_interpreter"
CITY_INTERPRETER_TEMPLATE = "city_interpreter.txt"


def derive_eligible_capability_ids(
    world: Any,
    region: CityRegion,
    condition: Any,
    assets: Sequence[UrbanAsset],
) -> tuple[str, ...]:
    """Resolve capabilities from metric evidence, never labels or event names."""
    state = getattr(world, "mechanical_language", None)
    if state is None:
        return ()
    condition_definition = state.condition_definitions.get(condition.definition_id)
    metric_definition = (
        state.derived_definitions.get(condition_definition.metric_definition_id)
        if condition_definition is not None
        else None
    )
    if (
        condition_definition is None
        or condition_definition.target_kind != "region"
        or metric_definition is None
        or metric_definition.target_kind != "region"
        or metric_definition.dimension is not PrimitiveDimension.RISK
    ):
        return ()
    declared_services = {
        item.capability_id for item in region.city_state.service_demands
    }
    leaves = metric_leaves(metric_definition.expression, state.derived_definitions)
    quality_capabilities = {
        str(leaf.get("concept_id", "")).strip()
        for leaf in leaves
        if leaf.get("dimension") == PrimitiveDimension.QUALITY.value
        and str(leaf.get("concept_id", "")).strip()
    }
    service_capabilities = {
        str(leaf.get("concept_id", "")).strip()
        for leaf in leaves
        if leaf.get("dimension")
        in {
            PrimitiveDimension.ACCESS.value,
            PrimitiveDimension.LOAD.value,
            PrimitiveDimension.CAPACITY.value,
        }
        and dict(leaf.get("qualifiers", {}) or {}).get("kind") == "urban_service"
        and str(leaf.get("concept_id", "")).strip() in declared_services
    }
    grounded = {
        capability for asset in assets for capability in asset.capability_ids
    }
    return tuple(sorted((quality_capabilities | service_capabilities) & grounded))


def city_affordance_context(
    world: Any, trigger_event: Event, condition: Any
) -> tuple[AffordanceContext, CityRegion]:
    if (
        trigger_event.event_type != "semantic_condition_activated"
        or not isinstance(trigger_event.render_params, Mapping)
    ):
        raise ValueError("city interpretation requires semantic_condition_activated")
    region_id = str(trigger_event.render_params.get("region_id", ""))
    try:
        region = world.map.regions.get(int(region_id))
    except (TypeError, ValueError):
        region = None
    if not isinstance(region, CityRegion):
        raise ValueError("city interpretation requires a CityRegion")
    active = world.mechanical_language.get_active_conditions(
        EntityRef("region", str(region.id)), int(world.month_stamp)
    )
    if not any(item.id == condition.id for item in active):
        raise ValueError("city condition is not active in canonical state")
    return (
        AffordanceContext(
            world,
            "city",
            EntityRef("city", f"region:{region.id}"),
            trigger_event,
            condition,
        ),
        region,
    )


async def interpret_city_transition(
    world: Any,
    trigger_event: Event,
    condition: Any,
    *_unused: Any,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
    **_unused_kwargs: Any,
):
    from src.systems import collective_affordances as _registered  # noqa: F401

    context, region = city_affordance_context(world, trigger_event, condition)
    options = DOMAIN_AFFORDANCES.compose(context)
    return await interpret_domain_affordances(
        world,
        domain="city",
        actor_ref=context.actor_ref,
        actor_label=region.name,
        trigger_event=trigger_event,
        affordances=options,
        task_name=CITY_INTERPRETER_TASK,
        template_name=CITY_INTERPRETER_TEMPLATE,
        extra_context={"condition": condition.to_dict(), "region_id": str(region.id)},
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = [
    "CITY_INTERPRETER_TASK",
    "city_affordance_context",
    "derive_eligible_capability_ids",
    "interpret_city_transition",
]
