"""Interpret grounded population affordances without proposing mechanics."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.domain_affordance import DomainDecision
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.systems.domain_affordance_registry import AffordanceContext, DOMAIN_AFFORDANCES
from src.systems.domain_decision_interpreter import interpret_domain_affordances


POPULATION_INTERPRETER_TASK = "population_interpreter"
POPULATION_INTERPRETER_TEMPLATE = "population_interpreter.txt"


def population_affordance_context(
    world: Any, transition_event: Event
) -> tuple[AffordanceContext, CityRegion, Any]:
    if transition_event.event_type != "semantic_condition_activated":
        raise ValueError("population interpretation requires semantic_condition_activated")
    params = transition_event.render_params
    if not isinstance(params, Mapping):
        raise ValueError("population transition requires region_id and condition_definition_id")
    region_id = str(params.get("region_id", "")).strip()
    definition_id = str(params.get("condition_definition_id", "")).strip()
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    try:
        region = regions.get(int(region_id))
    except (TypeError, ValueError):
        region = regions.get(region_id)
    if not isinstance(region, CityRegion):
        raise ValueError("population transition must target a CityRegion")
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if item.definition_id == definition_id
            and item.cause_event_id == transition_event.id
        ),
        None,
    )
    if condition is None:
        raise ValueError("population transition requires a matching active condition")
    context = AffordanceContext(
        world=world,
        domain="population",
        actor_ref=EntityRef("population", f"region:{region.id}"),
        trigger_event=transition_event,
        condition=condition,
    )
    return context, region, condition


async def interpret_population_transition(
    world: Any,
    transition_event: Event,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
):
    from src.systems import collective_affordances as _registered  # noqa: F401

    context, region, condition = population_affordance_context(world, transition_event)
    affordances = DOMAIN_AFFORDANCES.compose(context)
    return await interpret_domain_affordances(
        world,
        domain=context.domain,
        actor_ref=context.actor_ref,
        actor_label=region.name,
        trigger_event=transition_event,
        affordances=affordances,
        task_name=POPULATION_INTERPRETER_TASK,
        template_name=POPULATION_INTERPRETER_TEMPLATE,
        extra_context={
            "condition": condition.to_dict(),
            "origin": {
                "id": str(region.id),
                "population": float(region.population),
                "capacity": float(region.population_capacity),
            },
        },
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = [
    "POPULATION_INTERPRETER_TASK",
    "interpret_population_transition",
    "population_affordance_context",
]
