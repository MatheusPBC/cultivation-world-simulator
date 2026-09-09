"""Shared interpreter boundary for collective-domain affordance selection."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import (
    DomainAffordance,
    DomainDecision,
    DomainDecisionKind,
)
from src.classes.event import Event, FactKind
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode


DEFAULT_ACTION_URGENCY_THRESHOLD = 0.65


def decision_schema(affordances: Sequence[DomainAffordance]) -> dict[str, Any]:
    ids = [item.id for item in affordances]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "enum": ["maintain", "act"]},
            "reason": {"type": "string", "minLength": 1},
            "selected_affordance_id": {"type": "string", "enum": ids},
        },
        "required": ["decision", "reason"],
        "oneOf": [
            {
                "properties": {"decision": {"const": "maintain"}},
                "not": {"required": ["selected_affordance_id"]},
            },
            {
                "properties": {"decision": {"const": "act"}},
                "required": ["selected_affordance_id"],
            },
        ],
    }


def _parse(raw: Any, affordances: Sequence[DomainAffordance]) -> DomainDecision:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("domain decision must be an object")
    allowed = {"decision", "reason", "selected_affordance_id"}
    if set(raw) - allowed:
        raise ValueError("domain decision contains unsupported fields")
    try:
        kind = DomainDecisionKind(str(raw["decision"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("domain decision must be maintain or act") from exc
    reason = raw.get("reason")
    selected = raw.get("selected_affordance_id")
    decision = DomainDecision(kind, str(reason or ""), selected)
    offered_ids = {item.id for item in affordances}
    if decision.selected_affordance_id is not None and decision.selected_affordance_id not in offered_ids:
        raise ValueError("selected_affordance_id was not offered")
    return decision


def conservative_decision(
    world: Any, affordances: Sequence[DomainAffordance]
) -> DomainDecision:
    if not affordances:
        return DomainDecision(
            DomainDecisionKind.MAINTAIN,
            "No material affordance is currently grounded.",
        )
    snapshot = getattr(world, "run_config_snapshot", {}) or {}
    try:
        threshold = float(
            snapshot.get(
                "domain_affordance_action_urgency_threshold",
                DEFAULT_ACTION_URGENCY_THRESHOLD,
            )
        )
    except (TypeError, ValueError):
        threshold = DEFAULT_ACTION_URGENCY_THRESHOLD
    selected = sorted(
        affordances,
        key=lambda item: (-item.urgency, item.action_kind, item.id),
    )[0]
    if selected.urgency < max(0.0, min(1.0, threshold)):
        return DomainDecision(
            DomainDecisionKind.MAINTAIN,
            "Available actions remain below the conservative urgency threshold.",
        )
    return DomainDecision(
        DomainDecisionKind.ACT,
        "The highest-urgency grounded option is actionable.",
        selected.id,
    )


def _context(
    actor_label: str,
    trigger_event: Event,
    affordances: Sequence[DomainAffordance],
    extra_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "actor": actor_label,
        "trigger": {
            "event_id": trigger_event.id,
            "event_type": trigger_event.event_type,
            "content": trigger_event.content,
        },
        "affordances": [item.to_dict() for item in affordances],
        "context": dict(extra_context or {}),
    }


def _event(
    world: Any,
    *,
    domain: str,
    actor_ref: Any,
    actor_label: str,
    trigger_event: Event,
    affordances: Sequence[DomainAffordance],
    decision: DomainDecision,
    source: str,
) -> Event:
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind=actor_ref.kind,
        subject_id=actor_ref.id,
        source=source,
        considered_count=len(affordances),
        chosen_chain=(
            [{"selected_affordance_id": decision.selected_affordance_id}]
            if decision.selected_affordance_id
            else []
        ),
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t(
            "{actor} made a domain decision: {decision}.",
            actor=actor_label,
            decision=decision.decision.value,
        ),
        event_type=f"{domain.split(':', 1)[0]}_interpretation_decision",
        render_key="domain_interpretation_decision",
        render_params={
            "domain": domain,
            "actor_kind": actor_ref.kind,
            "actor_id": actor_ref.id,
            "decision": decision.decision.value,
            "selected_affordance_id": decision.selected_affordance_id,
        },
        fact_kind=FactKind.DECISION,
        causal_origin=(
            CausalOrigin.LLM_INTERPRETATION
            if source == "llm"
            else CausalOrigin.DETERMINISTIC
        ),
        causal_payload={
            "deltas": [],
            "decision": audit.to_dict(),
            "interpretation": {**decision.to_dict(), "source": source},
        },
    )
    causes = tuple(
        dict.fromkeys(
            (
                trigger_event.id,
                *(
                    event_id
                    for option in affordances
                    for event_id in option.motivation_event_ids
                ),
            )
        )
    )
    event.causal_links.extend(
        CausalLink(
            event_id=event.id,
            cause_event_id=cause_id,
            relation=CausalRelation.RESPONSE_TO,
        )
        for cause_id in causes
    )
    return event


async def interpret_domain_affordances(
    world: Any,
    *,
    domain: str,
    actor_ref: Any,
    actor_label: str,
    trigger_event: Event,
    affordances: Sequence[DomainAffordance],
    task_name: str,
    template_name: str,
    extra_context: Mapping[str, Any] | None = None,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    injected_decision: DomainDecision | None = None,
) -> tuple[DomainDecision, Event]:
    """Interpret only offered IDs; all mechanics stay inside the engine."""
    options = tuple(affordances)
    if any(item.domain != domain or item.actor_ref != actor_ref for item in options):
        raise ValueError("interpreter received an affordance for another actor")
    source = "injected" if injected_decision is not None else "llm"
    if injected_decision is not None:
        decision = _parse(injected_decision.to_dict(), options)
    elif not options:
        source = "rule"
        decision = conservative_decision(world, options)
    else:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            source = "rule"
            decision = conservative_decision(world, options)
        else:
            try:
                caller = llm_call or call_llm_with_task_name
                template = resolve_locale_template_path(
                    template_name,
                    current_locale=str(
                        (getattr(world, "run_config_snapshot", {}) or {}).get(
                            "content_locale", ""
                        )
                    )
                    or None,
                )
                raw = caller(
                    task_name,
                    template,
                    _context(actor_label, trigger_event, options, extra_context),
                    output_schema=decision_schema(options),
                )
                if inspect.isawaitable(raw):
                    raw = await raw
                decision = _parse(raw, options)
            except (LLMError, ParseError, ProviderCallError):
                source = "rule"
                decision = DomainDecision(
                    DomainDecisionKind.MAINTAIN,
                    "The domain provider was unavailable, so no action was selected.",
                )
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                # Invalid structured output is an explicit blocked decision.
                # Selecting another option here would let malformed LLM output
                # cause a mutation the actor never chose.
                source = "llm_rejected"
                decision = DomainDecision(
                    DomainDecisionKind.MAINTAIN,
                    "The proposed affordance identifier was invalid or unsupported.",
                )
    return decision, _event(
        world,
        domain=domain,
        actor_ref=actor_ref,
        actor_label=actor_label,
        trigger_event=trigger_event,
        affordances=options,
        decision=decision,
        source=source,
    )


__all__ = [
    "DEFAULT_ACTION_URGENCY_THRESHOLD",
    "conservative_decision",
    "decision_schema",
    "interpret_domain_affordances",
]
