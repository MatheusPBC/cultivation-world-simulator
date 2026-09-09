"""Reactive bridge from regional conditions to existing Sect affordances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.domain_affordance import DomainDecisionKind
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
from src.systems.organization_interpreter import (
    interpret_organization_transition,
    organization_affordance_context,
)
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)
from src.systems.sect_member_support import eligible_member_ids


ORGANIZATION_DOMAIN_PREFIX = "organization:"


def _active_sects(world: Any) -> list[Any]:
    context = getattr(world, "sect_context", None)
    if context is not None:
        return list(context.get_active_sects())
    return [
        sect
        for sect in (getattr(world, "existed_sects", []) or [])
        if getattr(sect, "is_active", True)
    ]


def _region_from_id(world: Any, region_id: str) -> Any | None:
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            return None
    return region


def _condition_for_event(
    world: Any, event: Event
) -> tuple[Any | None, ConditionInstance | None]:
    params = event.render_params or {}
    region_id = str(params.get("region_id", ""))
    definition_id = str(params.get("condition_definition_id", ""))
    region = _region_from_id(world, region_id)
    if region is None or not definition_id:
        return None, None
    if definition_id not in world.mechanical_language.condition_definitions:
        return None, None
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", region_id), int(world.month_stamp)
            )
            if item.definition_id == definition_id and item.cause_event_id == event.id
        ),
        None,
    )
    return region, condition


def _receipt_id(condition: ConditionInstance, sect_id: str) -> str:
    return DomainReactionReceipt.create(
        condition.id,
        f"{ORGANIZATION_DOMAIN_PREFIX}{sect_id}",
        condition.cause_event_id,
        decision="maintain",
        affordance_id=None,
    ).id


def _receipt(
    world: Any, condition: ConditionInstance, sect_id: str
) -> DomainReactionReceipt | None:
    return world.mechanical_language.reaction_receipts.get(
        _receipt_id(condition, sect_id)
    )


def _mark_receipt(
    world: Any,
    condition: ConditionInstance,
    sect_id: str,
    decision_event_id: str,
    *,
    completed: bool,
    next_eligible_month: int | None = None,
    decision: str,
    affordance_id: str | None,
) -> DomainReactionReceipt:
    existing = _receipt(world, condition, sect_id)
    updated = DomainReactionReceipt.create(
        condition.id,
        f"{ORGANIZATION_DOMAIN_PREFIX}{sect_id}",
        condition.cause_event_id,
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
    return updated


def _mark(
    queue: DomainInvalidationQueue,
    *,
    condition: ConditionInstance,
    sect_id: str,
    source_event_id: str,
) -> None:
    queue.mark(
        DomainInvalidation(
            layer=DomainInvalidationLayer.SEMANTIC,
            domain="organization",
            target_kind="sect",
            target_id=str(sect_id),
            reason=DomainInvalidationReason.CONDITION_ACTIVATED,
            source_event_ids=(str(source_event_id),),
            condition_instance_id=condition.id,
            revision=str(condition.cause_event_id),
        )
    )


def enqueue_organization_transitions(
    world: Any,
    events: list[Event],
    invalidations: DomainInvalidationQueue,
) -> None:
    """Enqueue one institutional trigger per eligible Sect, deterministically."""
    for event in events:
        if event.event_type != "semantic_condition_activated" or not isinstance(
            event.render_params, Mapping
        ):
            continue
        region, condition = _condition_for_event(world, event)
        if (
            region is None
            or condition is None
        ):
            continue
        region_id = str(region.id)
        for sect in _active_sects(world):
            if eligible_member_ids(sect, region_id=region_id):
                _mark(
                    invalidations,
                    condition=condition,
                    sect_id=str(sect.id),
                    source_event_id=event.id,
                )


def enqueue_unreacted_organization_conditions(
    world: Any,
    invalidations: DomainInvalidationQueue,
) -> None:
    """Recover active triggers when eligibility appears after the original event."""
    target_month = int(world.month_stamp)
    for region in (getattr(getattr(world, "map", None), "regions", {}) or {}).values():
        region_id = str(getattr(region, "id", ""))
        if not region_id:
            continue
        for condition in world.mechanical_language.get_active_conditions(
            EntityRef("region", region_id), target_month
        ):
            for sect in _active_sects(world):
                if not eligible_member_ids(sect, region_id=region_id):
                    continue
                receipt = _receipt(world, condition, str(sect.id))
                if receipt is not None and (
                    receipt.completed
                    or (
                        receipt.next_eligible_month is not None
                        and target_month < receipt.next_eligible_month
                    )
                ):
                    continue
                _mark(
                    invalidations,
                    condition=condition,
                    sect_id=str(sect.id),
                    source_event_id=condition.cause_event_id,
                )


def _event_by_id(
    world: Any, current_events: list[Event], event_id: str
) -> Event | None:
    event = next((item for item in current_events if item.id == event_id), None)
    if event is not None:
        return event
    manager = getattr(world, "event_manager", None)
    return manager.get_event_by_id(event_id) if manager is not None else None


def _config_value(world: Any, name: str, default: int) -> int:
    try:
        return int((getattr(world, "run_config_snapshot", {}) or {}).get(name, default))
    except (TypeError, ValueError):
        return default


async def process_organization_reactivity(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
) -> list[Event]:
    budget = budget or CausalBudget.from_world(world)
    pending = invalidations.drain(
        layer=DomainInvalidationLayer.SEMANTIC, domain="organization"
    )
    produced: list[Event] = []
    retry: list[DomainInvalidation] = []
    processed: set[tuple[str, str]] = set()
    evaluations = 0
    llm_calls = 0
    evaluation_limit = max(
        0, _config_value(world, "organization_reaction_evaluation_budget_per_month", 8)
    )
    llm_limit = max(
        0, _config_value(world, "organization_interpreter_llm_budget_per_month", 2)
    )

    while pending and evaluations < evaluation_limit:
        trigger = pending.pop(0)
        key = (str(trigger.target_id), str(trigger.condition_instance_id or ""))
        if key in processed:
            continue
        if not budget.consume_propagation_step():
            retry.append(trigger)
            retry.extend(pending)
            pending.clear()
            break
        if not trigger.source_event_ids:
            continue
        source_event = _event_by_id(
            world, [*current_events, *produced], trigger.source_event_ids[0]
        )
        if source_event is None:
            retry.append(trigger)
            continue
        processed.add(key)
        evaluations += 1
        region, condition = _condition_for_event(world, source_event)
        sect = next(
            (
                item
                for item in _active_sects(world)
                if str(item.id) == str(trigger.target_id)
            ),
            None,
        )
        if (
            region is None
            or condition is None
            or sect is None
        ):
            continue
        eligible = eligible_member_ids(sect, region_id=str(region.id))
        receipt = _receipt(world, condition, str(sect.id))
        if not eligible or (
            receipt is not None
            and (
                receipt.completed
                or int(world.month_stamp) < int(receipt.next_eligible_month or 0)
            )
        ):
            continue
        can_use_llm = llm_calls < llm_limit and budget.consume_interpreter_call()
        decision, decision_event = await interpret_organization_transition(
            world,
            sect,
            region,
            condition,
            source_event,
            eligible,
            llm_call=llm_call if can_use_llm else None,
            force_rule=not can_use_llm,
        )
        if can_use_llm:
            llm_calls += 1
        produced.append(decision_event)
        if decision.decision is DomainDecisionKind.MAINTAIN:
            _mark_receipt(
                world,
                condition,
                str(sect.id),
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
                str(sect.id),
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + 1,
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )
            retry.append(trigger)
            continue
        context = organization_affordance_context(
            world, sect, region, condition, source_event
        )
        try:
            action_event = DOMAIN_AFFORDANCES.execute(
                context,
                decision.selected_affordance_id or "",
                decision_event_id=decision_event.id,
                # The decision fact itself, so the executor validates the
                # sect's real authorship instead of trusting an ID.
                decision_event=decision_event,
            )
        except StaleAffordanceError:
            action_event = stale_affordance_blocked_event(
                context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
        produced.append(action_event)
        if action_event.event_type in {
            "sect_member_support_blocked",
            "domain_affordance_blocked",
        }:
            _mark_receipt(
                world,
                condition,
                str(sect.id),
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + 1,
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )
        else:
            _mark_receipt(
                world,
                condition,
                str(sect.id),
                decision_event.id,
                completed=True,
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )

    for item in (*retry, *pending):
        invalidations.mark(item)
    return produced


__all__ = [
    "enqueue_organization_transitions",
    "enqueue_unreacted_organization_conditions",
    "process_organization_reactivity",
]
