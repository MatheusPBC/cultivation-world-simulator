from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.classes.domain_affordance import DomainDecisionKind
from src.classes.event import Event
from src.classes.mechanical_language import DomainReactionReceipt
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)
from src.systems.economy_interpreter import (
    economy_affordance_context,
    interpret_resource_shortage,
)
from src.systems.institutional_aid import (
    has_institutional_aid_request_option,
    has_institutional_aid_requester,
    process_institutional_aid_deadlines,
    process_institutional_aid_fulfillment,
    process_institutional_aid_remediation,
    process_institutional_aid_shortage,
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
    llm_budget = max(
        0,
        int(
            _config_value(
                world,
                "economy_interpreter_llm_budget_per_month",
                2,
            )
        ),
    )
    evaluation_budget = max(
        0,
        int(
            _config_value(
                world,
                "economy_reaction_evaluation_budget_per_month",
                8,
            )
        ),
    )
    produced: list[Event] = []
    llm_calls = 0
    evaluations = 0
    processed: set[str] = set()

    produced.extend(
        await process_institutional_aid_fulfillment(
            world,
            invalidations=invalidations,
            llm_call=llm_call,
            budget=budget,
            evaluation_budget=max(
                0,
                int(
                    _config_value(
                        world,
                        "institutional_aid_fulfillment_evaluation_budget_per_month",
                        8,
                    )
                ),
            ),
            llm_budget=max(
                0,
                int(
                    _config_value(
                        world,
                        "institutional_aid_fulfillment_llm_budget_per_month",
                        2,
                    )
                ),
            ),
        )
    )
    produced.extend(
        await process_institutional_aid_remediation(
            world,
            llm_call=llm_call,
            budget=budget,
            evaluation_budget=max(
                0,
                int(
                    _config_value(
                        world,
                        "institutional_aid_fulfillment_evaluation_budget_per_month",
                        8,
                    )
                ),
            ),
            llm_budget=max(
                0,
                int(
                    _config_value(
                        world,
                        "institutional_aid_fulfillment_llm_budget_per_month",
                        2,
                    )
                ),
            ),
        )
    )

    for shortage in current_events:
        if (
            shortage.event_type != "regional_resource_shortage"
            or shortage.id in processed
        ):
            continue
        if evaluations >= evaluation_budget or not budget.consume_propagation_step():
            break
        processed.add(shortage.id)
        evaluations += 1
        if _receipt(world, shortage) is not None:
            continue
        params = shortage.render_params or {}
        destination_id = str(params.get("region_id", ""))
        if has_institutional_aid_requester(world, destination_id):
            has_request_option = has_institutional_aid_request_option(world, shortage)
            request_uses_llm = has_request_option and (
                llm_calls < llm_budget and budget.consume_interpreter_call()
            )
            if request_uses_llm:
                llm_calls += 1
            response_uses_llm = has_request_option and (
                llm_calls < llm_budget and budget.consume_interpreter_call()
            )
            if response_uses_llm:
                llm_calls += 1
            aid_events = await process_institutional_aid_shortage(
                world,
                shortage,
                llm_call=llm_call,
                request_force_rule=not request_uses_llm,
                response_force_rule=not response_uses_llm,
                budget=budget,
            )
            produced.extend(aid_events)
            decision_event = aid_events[0] if aid_events else None
            if decision_event is not None:
                interpretation = (decision_event.causal_payload or {}).get(
                    "interpretation", {}
                )
                _mark_receipt(
                    world,
                    shortage,
                    decision_event.id,
                    decision=str(interpretation.get("decision", "maintain")),
                    affordance_id=interpretation.get("selected_affordance_id"),
                    completed=any(
                        event.event_type
                        in {
                            "institutional_aid_accepted",
                            "institutional_aid_refused",
                        }
                        for event in aid_events
                    )
                    or str(interpretation.get("decision")) == "maintain",
                )
            continue
        can_use_interpreter = (
            llm_calls < llm_budget and budget.consume_interpreter_call()
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
    produced.extend(
        process_institutional_aid_deadlines(
            world,
            budget=budget,
            evaluation_budget=min(
                4,
                max(
                    0,
                    int(
                        _config_value(
                            world,
                            "institutional_aid_fulfillment_evaluation_budget_per_month",
                            8,
                        )
                    ),
                ),
            ),
        )
    )
    from src.systems.institutional_relationship_impact import (
        process_institutional_relationship_impacts,
    )

    produced.extend(
        await process_institutional_relationship_impacts(
            world,
            current_events=[*current_events, *produced],
            llm_call=llm_call,
            budget=budget,
            evaluation_budget=max(
                0,
                int(_config_value(
                    world,
                    "institutional_relationship_impact_evaluation_budget_per_month",
                    8,
                )),
            ),
            llm_budget=max(
                0,
                int(_config_value(
                    world,
                    "institutional_relationship_impact_llm_budget_per_month",
                    2,
                )),
            ),
        )
    )
    return produced


__all__ = ["process_economy_reactivity"]
