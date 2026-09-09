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
from src.systems.civil_petition import civil_response_is_open
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
    condition: ConditionInstance | None,
    revision: str,
    decision_event_id: str,
    *,
    completed: bool,
    next_eligible_month: int | None = None,
    decision: str,
    affordance_id: str | None,
) -> None:
    dynasty_id = _dynasty_id(world)
    # A civil fact whose grievance is already resolved has no condition receipt
    # to write; its own response receipt is the record of the answer.
    if dynasty_id is None or condition is None:
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


def _close_civil_response(
    world: Any, source_event: Event, payload: dict, kind: str, decision_event, decision
) -> None:
    """Record that this civil fact has now been answered, once."""
    from src.systems.civil_petition import (
        mark_petition_responded,
        mark_stoppage_answered,
    )

    outcome = (
        "maintain" if decision.decision is DomainDecisionKind.MAINTAIN else "act"
    )
    if kind == "petition":
        mark_petition_responded(
            world,
            source_event.id,
            decision_event_id=decision_event.id,
            decision=outcome,
            affordance_id=decision.selected_affordance_id,
        )
        return
    if kind == "endorsement":
        from src.systems.civic_endorsement import mark_endorsement_answered

        mark_endorsement_answered(
            world,
            source_event.id,
            str(payload.get("addressed_institution_id", "")),
            decision_event_id=decision_event.id,
            decision=outcome,
            affordance_id=decision.selected_affordance_id,
        )
        return
    if kind == "riot":
        from src.systems.civil_riot import mark_riot_answered

        mark_riot_answered(
            world,
            source_event.id,
            str(payload.get("addressed_institution_id", "")),
            decision_event_id=decision_event.id,
            decision=outcome,
            affordance_id=decision.selected_affordance_id,
        )
        return
    mark_stoppage_answered(
        world,
        source_event.id,
        str(payload.get("addressed_institution_id", "")),
        decision_event_id=decision_event.id,
        decision=outcome,
        affordance_id=decision.selected_affordance_id,
    )


def _civil_trigger(world: Any, event: Event) -> tuple[str, dict] | None:
    """The civil fact this event is, read from canonical state if it is one."""
    from src.systems.civil_petition import (
        canonical_stoppage_payload,
        petition_payload,
    )

    from src.systems.civic_endorsement import canonical_endorsement_payload
    from src.systems.civil_riot import canonical_riot_payload

    payload = petition_payload(event)
    if payload is not None:
        return "petition", payload
    payload = canonical_stoppage_payload(world, event)
    if payload is not None:
        return "stoppage", payload
    payload = canonical_riot_payload(world, event)
    if payload is not None:
        return "riot", payload
    payload = canonical_endorsement_payload(world, event)
    return ("endorsement", payload) if payload is not None else None


def _condition_for_petition(
    world: Any, payload: dict
) -> tuple[CityRegion | None, ConditionInstance | None]:
    """The grievance's own condition, still active and still this region's."""
    region = _region_from_id(world, str(payload.get("region_id", "")))
    instance_id = str(payload.get("condition_instance_id", ""))
    if region is None or not instance_id:
        return None, None
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if str(item.id) == instance_id
        ),
        None,
    )
    return (region, condition) if condition is not None else (None, None)


def _region_and_optional_condition(
    world: Any, payload: dict
) -> tuple[CityRegion | None, ConditionInstance | None]:
    """The civil fact's region, and its grievance only if still live.

    A resolved pressure leaves the region and returns no condition: the
    government answers the fact that really happened, with no substitute
    condition invented to stand in for the one that is gone.
    """
    from src.systems.civil_petition import active_condition_for

    region = _region_from_id(world, str(payload.get("region_id", "")))
    if region is None:
        return None, None
    # Both civil facts name their grievance the same way, so one reader serves.
    return region, active_condition_for(world, region, payload)


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


def enqueue_pending_petitions(
    world: Any,
    invalidations: DomainInvalidationQueue,
    current_events: list[Event] | None = None,
) -> None:
    """Let an unanswered public petition ask the government for an answer.

    The government phase runs before the population phase, so a petition
    filed this month is legitimately answered on the next cycle. It is found
    by its persisted fact rather than by re-reading the original condition, so
    the grievance the people actually raised is what the government responds
    to; the condition stays attached as evidence.
    """
    from src.systems.civil_petition import pending_petitions

    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    for event, payload in pending_petitions(world, current_events=current_events):
        region = _region_from_id(world, str(payload.get("region_id", "")))
        if region is None or not is_dynasty_governed(world, region):
            continue
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="government",
                target_kind="dynasty",
                target_id=dynasty_id,
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(event.id,),
                condition_instance_id=str(payload.get("condition_instance_id", "")),
                revision=event.id,
            )
        )


def enqueue_pending_stoppages(
    world: Any,
    invalidations: DomainInvalidationQueue,
) -> None:
    """Let a public work stoppage the government knows about ask for an answer.

    The stoppage fact itself is the trigger, so a grievance that has since been
    resolved still gets an answer to what really happened; the condition is
    attached only while it is genuinely live.
    """
    from src.systems.civil_petition import pending_stoppages

    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    for event, payload in pending_stoppages(world):
        region = _region_from_id(world, str(payload.get("region_id", "")))
        if region is None or not is_dynasty_governed(world, region):
            continue
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="government",
                target_kind="dynasty",
                target_id=dynasty_id,
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(event.id,),
                condition_instance_id=str(payload.get("condition_instance_id", "")),
                revision=event.id,
            )
        )


def enqueue_pending_riots(
    world: Any,
    invalidations: DomainInvalidationQueue,
) -> None:
    """Let a riot the government knows about ask for an answer.

    Same shape as the stoppage: the fact itself is the trigger, so a grievance
    that has since been resolved still gets an answer to the damage that
    really happened.
    """
    from src.systems.civil_riot import pending_riots

    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    for event, payload in pending_riots(world):
        region = _region_from_id(world, str(payload.get("region_id", "")))
        if region is None or not is_dynasty_governed(world, region):
            continue
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="government",
                target_kind="dynasty",
                target_id=dynasty_id,
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(event.id,),
                condition_instance_id=str(payload.get("condition_instance_id", "")),
                revision=event.id,
            )
        )


def enqueue_pending_endorsements(
    world: Any,
    invalidations: DomainInvalidationQueue,
) -> None:
    """Let an endorsement the government knows about ask for an answer.

    Its own trigger, because institutional knowledge alone would not reach the
    decision context: `decision_context` projects only memories, and a fact
    recorded without memory factors has none.
    """
    from src.systems.civic_endorsement import pending_endorsements

    dynasty_id = _dynasty_id(world)
    if dynasty_id is None:
        return
    for event, payload in pending_endorsements(world):
        region = _region_from_id(world, str(payload.get("region_id", "")))
        if region is None or not is_dynasty_governed(world, region):
            continue
        invalidations.mark(
            DomainInvalidation(
                layer=DomainInvalidationLayer.SEMANTIC,
                domain="government",
                target_kind="dynasty",
                target_id=dynasty_id,
                reason=DomainInvalidationReason.CONDITION_ACTIVATED,
                source_event_ids=(event.id,),
                condition_instance_id=str(payload.get("condition_instance_id", "")),
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
        civil = _civil_trigger(world, source_event)
        if civil is None:
            civil_kind, civil_payload = "", None
            region, condition = _condition_for_event(world, source_event)
        else:
            civil_kind, civil_payload = civil
            if civil_kind == "petition":
                # A petition is an appeal about a live grievance; without it
                # there is nothing being appealed.
                region, condition = _condition_for_petition(world, civil_payload)
            else:
                region, condition = _region_and_optional_condition(
                    world, civil_payload
                )
        if region is None or not is_dynasty_governed(world, region):
            continue
        if civil_payload is None and condition is None:
            continue
        if civil_payload is not None:
            # One answer per civil fact, and only from the institution that was
            # actually addressed and still governs here with the authority to.
            if not civil_response_is_open(
                world, region, source_event, civil_payload, civil_kind
            ):
                continue
        revision = str(trigger.revision or source_event.id)
        receipt = _receipt(world, condition, revision) if condition is not None else None
        if civil_payload is None and receipt is not None and (
            receipt.completed
            or (
                receipt.next_eligible_month is not None
                and int(world.month_stamp) < receipt.next_eligible_month
            )
        ):
            continue
        # Captured while the world is still known to be valid, so a blocked
        # attempt after the await still has a legitimate context to audit on.
        try:
            pre_context, _, _ = government_affordance_context(
                world, source_event, condition
            )
        except ValueError:
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
        # The civil fact is closed only by an answer that really happened. A
        # maintain is such an answer; an act is not closed until it has been
        # attempted, so exhausting the budget leaves the grievance pending for
        # the next cycle instead of silently burying it. The RESPONSE_TO link
        # is already written by the interpreter and is not duplicated here.
        # A maintain is an institutional answer, so it too needs the authority
        # and the knowledge to still be there when it is recorded. Losing them
        # during the await leaves the fact unanswered rather than closed by a
        # body that can no longer speak for this city.
        if (
            civil_payload is not None
            and decision.decision is DomainDecisionKind.MAINTAIN
            and civil_response_is_open(
                world, region, source_event, civil_payload, civil_kind
            )
        ):
            _close_civil_response(
                world, source_event, civil_payload, civil_kind,
                decision_event, decision,
            )
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
        # Rebuilding the context is itself a revalidation: authority, the
        # controller and the condition can all have changed while the
        # interpreter awaited. A world that moved on is a blocked attempt --
        # audited as the act it really was, on the context captured before the
        # await -- not a ValueError that takes the whole month down.
        try:
            context, _, _ = government_affordance_context(
                world, source_event, condition
            )
            # Knowledge and authority are asked again on the far side of the
            # await, exactly as they were asked before it.
            if civil_payload is not None and not civil_response_is_open(
                world, region, source_event, civil_payload, civil_kind
            ):
                raise ValueError("civil response is no longer open")
        except ValueError:
            blocked = stale_affordance_blocked_event(
                pre_context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
            produced.append(blocked)
            if civil_payload is not None:
                _close_civil_response(
                    world, source_event, civil_payload, civil_kind,
                    decision_event, decision,
                )
            _mark_receipt(
                world,
                condition,
                revision,
                decision_event.id,
                completed=False,
                next_eligible_month=int(world.month_stamp) + 1,
                # The actor really chose to act; a blocked attempt does not
                # rewrite that choice into a maintain.
                decision="act",
                affordance_id=decision.selected_affordance_id,
            )
            continue
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
                # The decision fact itself, so the executor validates the
                # government's real authorship instead of trusting an ID.
                decision_event=decision_event,
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
        # The attempt happened, blocked or not, so the civil fact has now been
        # answered and is closed exactly once.
        if civil_payload is not None:
            _close_civil_response(
                world, source_event, civil_payload, civil_kind,
                decision_event, decision,
            )
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
    "enqueue_pending_petitions",
    "enqueue_pending_endorsements",
    "enqueue_pending_riots",
    "enqueue_pending_stoppages",
    "enqueue_unreacted_government_conditions",
    "process_government_reactivity",
]
