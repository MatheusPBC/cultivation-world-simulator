"""Interpret grounded government affordances by ID only."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.domain_affordance import DomainDecision
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.systems.domain_affordance_registry import AffordanceContext, DOMAIN_AFFORDANCES
from src.systems.domain_decision_interpreter import interpret_domain_affordances


GOVERNMENT_INTERPRETER_TASK = "government_interpreter"
GOVERNMENT_INTERPRETER_TEMPLATE = "government_interpreter.txt"


def is_dynasty_governed(world: Any, region: CityRegion) -> bool:
    dynasty = getattr(world, "dynasty", None)
    return (
        dynasty is not None
        and region.city_state.governance.controller_kind == "dynasty"
        and region.city_state.governance.controller_id == str(dynasty.id)
    )


def government_affordance_context(
    world: Any, trigger_event: Event, condition: Any
) -> tuple[AffordanceContext, CityRegion, Any]:
    if (
        trigger_event.event_type != "semantic_condition_activated"
        or not isinstance(trigger_event.render_params, Mapping)
    ):
        raise ValueError("government interpretation requires semantic_condition_activated")
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        raise ValueError("government interpretation requires a current dynasty")
    try:
        region = world.map.regions.get(int(trigger_event.render_params.get("region_id")))
    except (TypeError, ValueError):
        region = None
    if not isinstance(region, CityRegion) or not is_dynasty_governed(world, region):
        raise ValueError("government interpretation requires a dynasty-governed city")
    active = world.mechanical_language.get_active_conditions(
        EntityRef("region", str(region.id)), int(world.month_stamp)
    )
    if not any(item.id == condition.id for item in active):
        raise ValueError("government condition is not active in canonical state")
    return (
        AffordanceContext(
            world,
            "government",
            EntityRef("dynasty", str(dynasty.id)),
            trigger_event,
            condition,
        ),
        region,
        dynasty,
    )


async def interpret_government_transition(
    world: Any,
    trigger_event: Event,
    condition: Any,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
    **_unused: Any,
):
    from src.systems import collective_affordances as _registered  # noqa: F401

    context, region, dynasty = government_affordance_context(
        world, trigger_event, condition
    )
    options = DOMAIN_AFFORDANCES.compose(context)
    return await interpret_domain_affordances(
        world,
        domain="government",
        actor_ref=context.actor_ref,
        actor_label=getattr(dynasty, "name", str(dynasty.id)),
        trigger_event=trigger_event,
        affordances=options,
        task_name=GOVERNMENT_INTERPRETER_TASK,
        template_name=GOVERNMENT_INTERPRETER_TEMPLATE,
        extra_context={"condition": condition.to_dict(), "region_id": str(region.id)},
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = [
    "government_affordance_context",
    "interpret_government_transition",
    "is_dynasty_governed",
]
