from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.classes.domain_affordance import DomainDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import DomainReactionReceipt
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.economy_interpreter import (
    economy_affordance_context,
    interpret_resource_shortage,
)
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)


def _config_value(world: Any, name: str, default: float) -> float:
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    try:
        return float(snapshot.get(name, default))
    except (TypeError, ValueError):
        return default


def _receipt(world: Any, shortage: Event) -> DomainReactionReceipt | None:
    receipt_id = DomainReactionReceipt.create(
        shortage.id,
        "economy",
        shortage.id,
        decision="maintain",
        affordance_id=None,
    ).id
    return world.mechanical_language.reaction_receipts.get(receipt_id)


def _mark_receipt(
    world: Any,
    shortage: Event,
    decision_event_id: str,
    *,
    decision: str,
    affordance_id: str | None,
    completed: bool,
) -> None:
    receipt = DomainReactionReceipt.create(
        shortage.id,
        "economy",
        shortage.id,
        decision=decision,
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,),
        completed=completed,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


async def process_economy_reactivity(
    world: Any,
    *,
    current_events: list[Event],
    invalidations: DomainInvalidationQueue,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
) -> list[Event]:
    """Interpret grounded shortages and execute only validated shipments."""
    budget = budget or CausalBudget.from_world(world)
    llm_budget = max(0, int(_config_value(
        world,
        "economy_interpreter_llm_budget_per_month",
        2,
    )))
    evaluation_budget = max(0, int(_config_value(
        world,
        "economy_reaction_evaluation_budget_per_month",
        8,
    )))
    produced: list[Event] = []
    llm_calls = 0
    evaluations = 0
    processed: set[str] = set()

    for shortage in current_events:
        if shortage.event_type != "regional_resource_shortage" or shortage.id in processed:
            continue
        if evaluations >= evaluation_budget or not budget.consume_propagation_step():
            break
        processed.add(shortage.id)
        evaluations += 1
        if _receipt(world, shortage) is not None:
            continue
        can_use_interpreter = (
            llm_calls < llm_budget
            and budget.consume_interpreter_call()
        )
        decision, decision_event = await interpret_resource_shortage(
            world,
            shortage,
            llm_call=llm_call if can_use_interpreter else None,
            force_rule=not can_use_interpreter,
        )
        if can_use_interpreter:
            llm_calls += 1
        produced.append(decision_event)
        if decision.decision is not DomainDecisionKind.ACT:
            _mark_receipt(
                world,
                shortage,
                decision_event.id,
                decision="maintain",
                affordance_id=None,
                completed=True,
            )
            continue
        if not budget.consume_domain_mutation():
            _mark_receipt(
                world,
                shortage,
                decision_event.id,
                decision="act",
                affordance_id=decision.selected_affordance_id,
                completed=False,
            )
            continue
        context, _, _ = economy_affordance_context(world, shortage)
        try:
            transfer_event = DOMAIN_AFFORDANCES.execute(
                context,
                decision.selected_affordance_id or "",
                decision_event_id=decision_event.id,
                invalidations=invalidations,
            )
        except StaleAffordanceError:
            transfer_event = stale_affordance_blocked_event(
                context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
        produced.append(transfer_event)
        _mark_receipt(
            world,
            shortage,
            decision_event.id,
            decision="act",
            affordance_id=decision.selected_affordance_id,
            completed=(
                transfer_event.event_type == "regional_resource_transfer_completed"
            ),
        )
    return produced


__all__ = ["process_economy_reactivity"]
