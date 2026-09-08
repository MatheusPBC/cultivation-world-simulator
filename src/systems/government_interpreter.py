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
    from src.systems.civil_petition import PETITION_EVENT_TYPE, STOPPAGE_EVENT_TYPE

    # A government answers either a condition it noticed itself or a civil fact
    # its people produced. All of them name the region they concern, and the
    # condition is passed in as evidence when one is still live.
    if (
        trigger_event.event_type
        not in ("semantic_condition_activated", PETITION_EVENT_TYPE,
                STOPPAGE_EVENT_TYPE)
        or not isinstance(trigger_event.render_params, Mapping)
    ):
        raise ValueError(
            "government interpretation requires a condition or a civil fact"
        )
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None:
        raise ValueError("government interpretation requires a current dynasty")
    try:
        region = world.map.regions.get(int(trigger_event.render_params.get("region_id")))
    except (TypeError, ValueError):
        region = None
    if not isinstance(region, CityRegion) or not is_dynasty_governed(world, region):
        raise ValueError("government interpretation requires a dynasty-governed city")
    # A condition is evidence, not a precondition. When one is supplied it must
    # really be active; a civil fact whose pressure has since been resolved is
    # answered without one rather than with an invented substitute.
    if condition is not None:
        active = world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)), int(world.month_stamp)
        )
        if not any(item.id == condition.id for item in active):
            raise ValueError("government condition is not active in canonical state")
    elif trigger_event.event_type == "semantic_condition_activated":
        raise ValueError("government condition interpretation requires its condition")
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


def _civil_fact_context(
    world: Any, trigger_event: Event, region: CityRegion
) -> dict[str, Any]:
    """State the work stoppage as it stands now, from the owner's own record.

    Its dates come from the fact, and whether it is still interrupting anything
    comes from the region's economy, so an expired stoppage is never presented
    as an ongoing one. Nothing here is inferred from the absence of a
    condition.
    """
    from src.systems.civil_petition import stoppage_payload

    payload = stoppage_payload(trigger_event)
    if payload is None:
        return {}
    month = int(world.month_stamp)
    record = getattr(getattr(region, "economy", None), "work_stoppage", None)
    is_this_one = (
        record is not None
        and str(record.start_event_id) == str(trigger_event.id)
    )
    return {
        "work_stoppage": {
            "start_event_id": str(trigger_event.id),
            "region_id": str(payload["region_id"]),
            "participation": float(payload["participation"]),
            "starts_month": int(payload["starts_month"]),
            "ends_month": int(payload["ends_month"]),
            "current_month": month,
            "affected_resource_ids": list(
                payload.get("affected_resource_ids") or ()
            ),
            "interrupting_now": bool(is_this_one and record.is_active(month)),
            "recorded_on_region": bool(is_this_one),
        }
    }


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
        extra_context={
            # The resolved-pressure case says so factually, by carrying no
            # condition, instead of restating the grievance as a second truth.
            "condition": condition.to_dict() if condition is not None else None,
            "region_id": str(region.id),
            **_civil_fact_context(world, trigger_event, region),
        },
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=injected_decision,
    )


__all__ = [
    "government_affordance_context",
    "interpret_government_transition",
    "is_dynasty_governed",
]
