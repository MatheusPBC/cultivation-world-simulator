from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.classes.domain_proposal import EconomyDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import (
    DomainInvalidation,
    DomainInvalidationLayer,
    DomainInvalidationQueue,
    DomainInvalidationReason,
)
from src.systems.economy_interpreter import interpret_resource_shortage
from src.systems.resource_transfer import resolve_resource_transfer


def _config_value(world: Any, name: str, default: float) -> float:
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    try:
        return float(snapshot.get(name, default))
    except (TypeError, ValueError):
        return default


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
        if decision.decision is not EconomyDecisionKind.ACT:
            continue
        if not budget.consume_domain_mutation():
            continue
        params = shortage.render_params or {}
        destination = world.map.regions.get(int(params["region_id"]))
        if not isinstance(destination, CityRegion):
            continue
        transfer_event = resolve_resource_transfer(
            world,
            destination=destination,
            resource_id=str(params["resource_id"]),
            decision_event_id=decision_event.id,
            preferences=decision.action_intent.preferences,
        )
        produced.append(transfer_event)
        if transfer_event.event_type != "regional_resource_transfer_completed":
            continue
        affordance = transfer_event.causal_payload["affordance"]
        for region_id in (
            affordance["source_region_id"],
            affordance["destination_region_id"],
        ):
            invalidations.mark(DomainInvalidation(
                layer=DomainInvalidationLayer.MECHANICAL,
                domain="economy",
                target_kind="region",
                target_id=str(region_id),
                reason=DomainInvalidationReason.RESOURCE_STOCK_CHANGED,
                source_event_ids=(transfer_event.id,),
                revision=transfer_event.id,
            ))
    return produced


__all__ = ["process_economy_reactivity"]
