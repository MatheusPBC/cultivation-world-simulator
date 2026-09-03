"""Interpret engine-composed resource-transfer affordances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.domain_affordance import DomainDecision
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.systems.domain_affordance_registry import AffordanceContext, DOMAIN_AFFORDANCES
from src.systems.domain_decision_interpreter import interpret_domain_affordances


ECONOMY_INTERPRETER_TASK = "economy_interpreter"
ECONOMY_INTERPRETER_TEMPLATE = "economy_interpreter.txt"


def economy_affordance_context(
    world: Any, event: Event
) -> tuple[AffordanceContext, CityRegion, str]:
    if (
        event.event_type != "regional_resource_shortage"
        or not isinstance(event.render_params, Mapping)
    ):
        raise ValueError("economy interpretation requires a resource shortage event")
    region_id = str(event.render_params.get("region_id", ""))
    resource_id = str(event.render_params.get("resource_id", "")).strip()
    try:
        destination = world.map.regions.get(int(region_id))
    except (TypeError, ValueError):
        destination = None
    if not isinstance(destination, CityRegion) or not resource_id:
        raise ValueError("resource shortage must identify a city and resource")
    return (
        AffordanceContext(
            world,
            "economy",
            EntityRef("regional_economy", f"region:{destination.id}"),
            event,
        ),
        destination,
        resource_id,
    )


async def interpret_resource_shortage(
    world: Any,
    shortage_event: Event,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
):
    from src.systems import collective_affordances as _registered  # noqa: F401

    context, destination, resource_id = economy_affordance_context(
        world, shortage_event
    )
    options = DOMAIN_AFFORDANCES.compose(context)
    return await interpret_domain_affordances(
        world,
        domain="economy",
        actor_ref=context.actor_ref,
        actor_label=destination.name,
        trigger_event=shortage_event,
        affordances=options,
        task_name=ECONOMY_INTERPRETER_TASK,
        template_name=ECONOMY_INTERPRETER_TEMPLATE,
        extra_context={
            "resource_id": resource_id,
            "destination_region_id": str(destination.id),
        },
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = ["interpret_resource_shortage", "economy_affordance_context"]
