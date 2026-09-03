"""Interpret all currently grounded organization affordances by ID."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from src.classes.domain_affordance import DomainDecision
from src.classes.event import Event
from src.classes.mechanical_language import EntityRef
from src.systems.domain_affordance_registry import AffordanceContext, DOMAIN_AFFORDANCES
from src.systems.domain_decision_interpreter import interpret_domain_affordances


ORGANIZATION_INTERPRETER_TASK = "organization_interpreter"
ORGANIZATION_INTERPRETER_TEMPLATE = "organization_interpreter.txt"


def organization_affordance_context(
    world: Any,
    sect: Any,
    region: Any,
    condition: Any,
    trigger_event: Event,
) -> AffordanceContext:
    if trigger_event.event_type != "semantic_condition_activated":
        raise ValueError("organization interpretation requires a condition activation")
    if not getattr(sect, "is_active", False):
        raise ValueError("organization interpretation requires an active sect")
    active = world.mechanical_language.get_active_conditions(
        EntityRef("region", str(region.id)), int(world.month_stamp)
    )
    if not any(item.id == condition.id for item in active):
        raise ValueError("organization condition is not active in canonical state")
    return AffordanceContext(
        world,
        "organization",
        EntityRef("sect", str(sect.id)),
        trigger_event,
        condition,
    )


async def interpret_organization_transition(
    world: Any,
    sect: Any,
    region: Any,
    condition: Any,
    trigger_event: Event,
    eligible_ids: Sequence[str] = (),
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
):
    from src.systems import collective_affordances as _registered  # noqa: F401

    context = organization_affordance_context(
        world, sect, region, condition, trigger_event
    )
    options = DOMAIN_AFFORDANCES.compose(context)
    if eligible_ids:
        supplied = {str(item) for item in eligible_ids}
        options = tuple(
            option
            for option in options
            if str(option.parameters.get("member_id")) in supplied
        )
    return await interpret_domain_affordances(
        world,
        domain="organization",
        actor_ref=context.actor_ref,
        actor_label=sect.name,
        trigger_event=trigger_event,
        affordances=options,
        task_name=ORGANIZATION_INTERPRETER_TASK,
        template_name=ORGANIZATION_INTERPRETER_TEMPLATE,
        extra_context={"condition": condition.to_dict(), "region_id": str(region.id)},
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = [
    "interpret_organization_transition",
    "organization_affordance_context",
]
