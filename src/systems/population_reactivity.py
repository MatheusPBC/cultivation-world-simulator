from __future__ import annotations

from typing import Any, Awaitable, Callable

from src.classes.domain_proposal import PopulationDecisionKind
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.population_interpreter import interpret_population_transition
from src.systems.population_transfer import resolve_population_transfer
from src.systems.semantic_world.service import evaluate_semantic_world
from src.systems.semantic_world.condition_semantics import is_settlement_pressure
from src.sim.simulator_engine.causal_budget import CausalBudget


def enqueue_population_transitions(
    world: Any,
    events: list[Event],
    invalidations: DomainInvalidationQueue,
) -> None:
    for event in events:
        if event.event_type not in {
            "semantic_condition_activated",
            "semantic_condition_resolved",
        }:
            continue
        params = event.render_params or {}
        definition_id = str(params.get("condition_definition_id", ""))
        region_id = str(params.get("region_id", ""))
        if not region_id or not is_settlement_pressure(world, definition_id):
            continue
        reason = (
            DomainInvalidationReason.CONDITION_ACTIVATED
            if event.event_type == "semantic_condition_activated"
            else DomainInvalidationReason.CONDITION_RESOLVED
        )
        condition_instance_id = next(
            (
                item.id
                for item in world.mechanical_language.get_conditions_for_target(
                    EntityRef("region", region_id)
                )
                if item.cause_event_id == event.id
                or item.resolution_event_id == event.id
            ),
            None,
        )
        invalidations.mark(DomainInvalidation(
            layer=DomainInvalidationLayer.SEMANTIC,
            domain="population",
            target_kind="region",
            target_id=region_id,
            reason=reason,
            source_event_ids=(event.id,),
            condition_instance_id=condition_instance_id,
            revision=event.id,
        ))


def enqueue_unreacted_population_conditions(
    world: Any,
    invalidations: DomainInvalidationQueue,
) -> None:
    month = int(world.month_stamp)
    for region in world.map.regions.values():
        if not isinstance(region, CityRegion):
            continue
        for condition in world.mechanical_language.get_active_conditions(
            EntityRef("region", str(region.id)),
            month,
        ):
            if not is_settlement_pressure(
                world,
                condition.definition_id,
            ):
                continue
            receipt = _reaction_receipt(world, condition)
            if receipt is not None and (
                receipt.completed
                or (
                    receipt.next_eligible_month is not None
                    and month < receipt.next_eligible_month
                )
            ):
                continue
            invalidations.mark(DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="population",
                target_kind="region",
                target_id=str(region.id),
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(condition.cause_event_id,),
                condition_instance_id=condition.id,
                revision=condition.cause_event_id,
            ))


def _event_by_id(world: Any, current_events: list[Event], event_id: str) -> Event | None:
    event = next((item for item in current_events if item.id == event_id), None)
    if event is not None:
        return event
    manager = getattr(world, "event_manager", None)
    return manager.get_event_by_id(event_id) if manager is not None else None


def _active_condition(world: Any, source_event: Event):
    params = source_event.render_params or {}
    try:
        origin = world.map.regions.get(int(params["region_id"]))
    except (KeyError, TypeError, ValueError):
        return None, None, None
    if not isinstance(origin, CityRegion):
        return None, None, None
    definition_id = str(params.get("condition_definition_id", ""))
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(origin.id)),
                int(world.month_stamp),
            )
            if item.definition_id == definition_id and item.cause_event_id == source_event.id
        ),
        None,
    )
    definition = world.mechanical_language.condition_definitions.get(definition_id)
    return origin, condition, definition


def _reaction_receipt(world: Any, condition: Any) -> DomainReactionReceipt | None:
    receipt_id = DomainReactionReceipt.create(
        condition.id,
        "population",
        condition.cause_event_id,
    ).id
    return world.mechanical_language.reaction_receipts.get(receipt_id)


def _reaction_is_not_due(world: Any, condition: Any) -> bool:
    receipt = _reaction_receipt(world, condition)
    if receipt is None:
        return False
    return receipt.completed or (
        receipt.next_eligible_month is not None
        and int(world.month_stamp) < receipt.next_eligible_month
    )


def _mark_condition_reacted(
    world: Any,
    condition: Any,
    decision_event_id: str,
    *,
    next_reaction_month: int | None = None,
    completed: bool = False,
) -> DomainReactionReceipt:
    existing = _reaction_receipt(world, condition)
    updated = DomainReactionReceipt.create(
        condition.id,
        "population",
        condition.cause_event_id,
        decision_event_ids=tuple(dict.fromkeys((
            *(existing.decision_event_ids if existing is not None else ()),
            decision_event_id,
        ))),
        next_eligible_month=next_reaction_month,
        completed=completed,
    )
    world.mechanical_language.reaction_receipts[updated.id] = updated
    return updated


def _config_value(world: Any, name: str, default: float) -> float:
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    try:
        return float(snapshot.get(name, default))
    except (TypeError, ValueError):
        return default


async def process_population_reactivity(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
) -> list[Event]:
    budget = budget or CausalBudget.from_world(world)
    produced: list[Event] = []
    llm_budget = max(0, int(_config_value(
        world,
        "population_interpreter_llm_budget_per_month",
        2,
    )))
    processed_source_ids: set[str] = set()
    llm_calls = 0
    evaluation_budget = max(0, int(_config_value(
        world,
        "population_reaction_evaluation_budget_per_month",
        8,
    )))
    evaluations = 0

    pending = invalidations.drain(
        layer=DomainInvalidationLayer.SEMANTIC,
        domain="population",
    )
    retry: list[DomainInvalidation] = []
    while pending and evaluations < evaluation_budget:
        invalidation = pending.pop(0)
        if not budget.consume_propagation_step():
            retry.append(invalidation)
            retry.extend(pending)
            pending.clear()
            break
        if (
            invalidation.reason is not DomainInvalidationReason.CONDITION_ACTIVATED
            or not invalidation.source_event_ids
            or invalidation.source_event_ids[0] in processed_source_ids
        ):
            continue
        source_event = _event_by_id(
            world,
            [*current_events, *produced],
            invalidation.source_event_ids[0],
        )
        if source_event is None:
            retry.append(invalidation)
            continue
        evaluations += 1
        processed_source_ids.add(source_event.id)
        origin, condition, definition = _active_condition(world, source_event)
        if (
            origin is None
            or condition is None
            or definition is None
            or _reaction_is_not_due(world, condition)
        ):
            continue
        can_use_interpreter = (
            llm_calls < llm_budget
            and budget.consume_interpreter_call()
        )
        decision, decision_event = await interpret_population_transition(
            world,
            source_event,
            llm_call=llm_call if can_use_interpreter else None,
            force_rule=not can_use_interpreter,
        )
        if can_use_interpreter:
            llm_calls += 1
        produced.append(decision_event)
        if decision.decision is not PopulationDecisionKind.ACT:
            _mark_condition_reacted(
                world,
                condition,
                decision_event.id,
                completed=True,
            )
            continue

        if not budget.consume_domain_mutation():
            retry.append(invalidation)
            continue
        transfer_event = resolve_population_transfer(
            world,
            origin=origin,
            condition=condition,
            condition_definition=definition,
            decision_event_id=decision_event.id,
            max_fraction=_config_value(
                world,
                "population_transfer_max_fraction_per_reaction",
                0.20,
            ),
            preferences=decision.action_intent.preferences,
        )
        produced.append(transfer_event)
        if transfer_event.event_type != "population_transfer_completed":
            retry_after_months = max(1, int(_config_value(
                world,
                "population_failed_transfer_retry_after_months",
                12,
            )))
            _mark_condition_reacted(
                world,
                condition,
                decision_event.id,
                next_reaction_month=(
                    int(world.month_stamp) + retry_after_months
                ),
            )
            continue

        affordance = transfer_event.causal_payload["affordance"]
        _mark_condition_reacted(
            world,
            condition,
            decision_event.id,
            next_reaction_month=(
                None
                if affordance["relief_complete"]
                else int(world.month_stamp) + 1
            ),
            completed=bool(affordance["relief_complete"]),
        )
        for region_id in (
            affordance["origin_region_id"],
            affordance["destination_region_id"],
        ):
            invalidations.mark(DomainInvalidation(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="population",
                target_kind="region",
                target_id=str(region_id),
                reason=DomainInvalidationReason.POPULATION_CHANGED,
                source_event_ids=(transfer_event.id,),
                revision=transfer_event.id,
            ))
        mechanical = invalidations.drain(layer=DomainInvalidationLayer.MECHANICAL)
        sources_by_target: dict[str, list[str]] = {}
        for item in mechanical:
            for source_event_id in item.source_event_ids:
                sources_by_target.setdefault(
                    f"{item.target_kind}:{item.target_id}",
                    [],
                ).append(source_event_id)
        semantic_events = await evaluate_semantic_world(
            world,
            source_event_ids_by_target=sources_by_target,
            budget=budget,
        )
        produced.extend(semantic_events)
        enqueue_population_transitions(world, semantic_events, invalidations)
        pending.extend(invalidations.drain(
            layer=DomainInvalidationLayer.SEMANTIC,
            domain="population",
        ))

    for item in (*retry, *pending):
        invalidations.mark(item)
    return produced


__all__ = [
    "enqueue_population_transitions",
    "enqueue_unreacted_population_conditions",
    "process_population_reactivity",
]
