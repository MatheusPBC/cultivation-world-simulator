"""Reactive dispatch for institutional dynasty responses to city conditions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.domain_affordance import DomainDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import (
    ConditionInstance,
    DomainReactionReceipt,
    EntityRef,
)
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.government_interpreter import (
    government_affordance_context,
    interpret_government_transition,
    is_dynasty_governed,
)
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)


def _region_from_id(world: Any, region_id: str) -> CityRegion | None:
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            region = None
    return region if isinstance(region, CityRegion) else None


def _dynasty_id(world: Any) -> str | None:
    dynasty = getattr(world, "dynasty", None)
    value = getattr(dynasty, "id", None)
    return str(value) if value is not None else None


def _condition_for_event(
    world: Any, event: Event
) -> tuple[CityRegion | None, ConditionInstance | None]:
    if not isinstance(event.render_params, Mapping):
        return None, None
    region = _region_from_id(world, str(event.render_params.get("region_id", "")))
    definition_id = str(event.render_params.get("condition_definition_id", ""))
    if region is None or not definition_id:
        return None, None
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if item.definition_id == definition_id
            and item.cause_event_id == event.id
            and str(item.target_id) == str(region.id)
        ),
        None,
    )
    return region, condition


def _event_by_id(
    world: Any, current_events: list[Event], event_id: str
) -> Event | None:
    event = next((item for item in current_events if item.id == event_id), None)
    if event is not None:
        return event
    manager = getattr(world, "event_manager", None)
    return manager.get_event_by_id(event_id) if manager is not None else None


def _receipt(
    world: Any, condition: ConditionInstance, revision: str
) -> DomainReactionReceipt | None:
    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return None
    receipt_id = DomainReactionReceipt.create(
        condition.id,
        f"government:{dynasty_id}",
        revision,
        decision="maintain",
        affordance_id=None,
    ).id
    return world.mechanical_language.reaction_receipts.get(receipt_id)


def _mark_receipt(
    world: Any,
    condition: ConditionInstance,
    revision: str,
    decision_event_id: str,
    *,
    completed: bool,
    next_eligible_month: int | None = None,
    decision: str,
    affordance_id: str | None,
) -> None:
    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    existing = _receipt(world, condition, revision)
    updated = DomainReactionReceipt.create(
        condition.id,
        f"government:{dynasty_id}",
        revision,
        decision=decision,
        affordance_id=affordance_id,
        decision_event_ids=tuple(
            dict.fromkeys(
                (*(existing.decision_event_ids if existing else ()), decision_event_id)
            )
        ),
        completed=completed,
        next_eligible_month=next_eligible_month,
    )
    world.mechanical_language.reaction_receipts[updated.id] = updated


def enqueue_government_transitions(
    world: Any, events: list[Event], invalidations: DomainInvalidationQueue
) -> None:
    """Mark newly activated, grounded conditions for the current dynasty."""
    if _dynasty_id(world) is None:
        return
    for event in events:
        if event.event_type != "semantic_condition_activated" or not isinstance(
            event.render_params, Mapping
        ):
            continue
        region, condition = _condition_for_event(world, event)
        if (
            region is None
            or condition is None
            or not is_dynasty_governed(world, region)
        ):
            continue
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="government",
                target_kind="dynasty",
                target_id=_dynasty_id(world) or "",
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(event.id,),
                condition_instance_id=condition.id,
                revision=event.id,
            )
        )


def enqueue_unreacted_government_conditions(
    world: Any, invalidations: DomainInvalidationQueue
) -> None:
    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    month = int(world.month_stamp)
    for region in getattr(getattr(world, "map", None), "regions", {}).values():
        if not isinstance(region, CityRegion) or not is_dynasty_governed(world, region):
            continue
        for condition in world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)), month
        ):
            revision = str(condition.cause_event_id)
            receipt = _receipt(world, condition, revision)
            if receipt is not None and (
                receipt.completed
                or (
                    receipt.next_eligible_month is not None
                    and month < receipt.next_eligible_month
                )
            ):
                continue
            invalidations.mark(
                DomainInvalidation(
                    layer=DomainInvalidationLayer.SEMANTIC,
                    domain="government",
                    target_kind="dynasty",
                    target_id=dynasty_id,
                    reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                    source_event_ids=(condition.cause_event_id,),
                    condition_instance_id=condition.id,
                    revision=revision,
                )
            )


def _config_value(world: Any, name: str, default: float) -> float:
    try:
        return float(
            (getattr(world, "run_config_snapshot", {}) or {}).get(name, default)
        )
    except (TypeError, ValueError):
        return default


async def process_government_reactivity(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
) -> list[Event]:
    """Process institutional triggers once and preserve budgeted retries."""
    budget = budget or CausalBudget.from_world(world)
    pending = invalidations.drain(
        layer=DomainInvalidationLayer.SEMANTIC, domain="government"
    )
    produced: list[Event] = []
    retry: list[DomainInvalidation] = []
    evaluations = 0
    evaluation_budget = max(
        0,
        int(_config_value(world, "government_reaction_evaluation_budget_per_month", 8)),
    )
    llm_budget = max(
        0, int(_config_value(world, "government_interpreter_llm_budget_per_month", 2))
    )
    llm_calls = 0
    processed_sources: set[str] = set()

    while pending and evaluations < evaluation_budget:
        trigger = pending.pop(0)
        if (
            not trigger.source_event_ids
            or trigger.source_event_ids[0] in processed_sources
        ):
            continue
        if not budget.consume_propagation_step():
            retry.append(trigger)
            retry.extend(pending)
            pending.clear()
            break
        source_event = _event_by_id(
            world, [*current_events, *produced], trigger.source_event_ids[0]
        )
        if source_event is None:
            retry.append(trigger)
            continue
        processed_sources.add(source_event.id)
        evaluations += 1
        region, condition = _condition_for_event(world, source_event)
        if (
            region is None
            or condition is None
            or not is_dynasty_governed(world, region)
        ):
            continue
        revision = str(trigger.revision or source_event.id)
        receipt = _receipt(world, condition, revision)
        if receipt is not None and (
            receipt.completed
            or (
                receipt.next_eligible_month is not None
                and int(world.month_stamp) < receipt.next_eligible_month
            )
        ):
            continue
        can_use_interpreter = (
            llm_calls < llm_budget and budget.consume_interpreter_call()
        )
        decision, decision_event = await interpret_government_transition(
            world,
            source_event,
            condition,
            llm_call=llm_call if can_use_interpreter else None,
            force_rule=not can_use_interpreter,
        )
        if can_use_interpreter:
            llm_calls += 1
        produced.append(decision_event)
        if decision.decision is DomainDecisionKind.MAINTAIN:
            _mark_receipt(
                world,
                condition,
                revision,
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + 1,
                decision="maintain",
                affordance_id=None,
            )
            continue
        if not budget.consume_domain_mutation():
            _mark_receipt(
                world,
                condition,
                revision,
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + 1,
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )
            retry.append(trigger)
            continue
        context, _, _ = government_affordance_context(
            world, source_event, condition
        )
        try:
            selected = DOMAIN_AFFORDANCES.revalidate(
                context, decision.selected_affordance_id or ""
            )
            if selected.action_kind == "urban_capacity_project":
                blocked_type = "urban_capacity_project_blocked"
                retry_months = int(
                    _config_value(
                        world, "government_blocked_project_retry_months", 12
                    )
                )
            else:
                blocked_type = "city_maintenance_blocked"
                retry_months = int(
                    _config_value(
                        world, "government_blocked_maintenance_retry_months", 1
                    )
                )
            action_event = DOMAIN_AFFORDANCES.execute(
                context,
                decision.selected_affordance_id or "",
                decision_event_id=decision_event.id,
                invalidations=invalidations,
            )
        except StaleAffordanceError:
            action_event = stale_affordance_blocked_event(
                context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
            blocked_type = "domain_affordance_blocked"
            retry_months = 1
        produced.append(action_event)
        if action_event.event_type == blocked_type:
            _mark_receipt(
                world,
                condition,
                revision,
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + retry_months,
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )
        else:
            _mark_receipt(
                world,
                condition,
                revision,
                decision_event.id,
                completed=(selected.action_kind == "urban_capacity_project"),
                next_eligible_month=(
                    None
                    if selected.action_kind == "urban_capacity_project"
                    else int(world.month_stamp) + 1
                ),
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )

    for item in (*retry, *pending):
        invalidations.mark(item)
    return produced


__all__ = [
    "enqueue_government_transitions",
    "enqueue_unreacted_government_conditions",
    "process_government_reactivity",
]
