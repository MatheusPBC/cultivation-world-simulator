"""Interpret a regional condition as a typed Sect organization decision."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_proposal import (
    OrganizationDecision,
    OrganizationDecisionKind,
    OrganizationIntentKind,
    SectMemberSupportIntentProposal,
)
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.systems.sect_member_support import eligible_member_ids, support_amount
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode


ORGANIZATION_INTERPRETER_TASK = "organization_interpreter"
ORGANIZATION_INTERPRETER_TEMPLATE = "organization_interpreter.txt"
ORGANIZATION_INTERPRETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "oneOf": [
        {
            "required": ["decision", "reason"],
            "properties": {
                "decision": {"const": OrganizationDecisionKind.MAINTAIN.value},
                "reason": {"type": "string"},
            },
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {"const": OrganizationDecisionKind.SUPPORT_MEMBER.value},
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "member_id"],
                    "properties": {
                        "action_kind": {
                            "const": OrganizationIntentKind.SUPPORT_MEMBER.value
                        },
                        "member_id": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    ],
}


def _validate_transition(
    world: Any,
    sect: Any,
    region: Any,
    condition: Any,
    trigger_event: Event,
    eligible_ids: Sequence[str],
) -> tuple[str, ...]:
    if trigger_event.event_type != "semantic_condition_activated":
        raise ValueError("organization interpretation requires an activated condition")
    if not isinstance(trigger_event.render_params, Mapping):
        raise ValueError("organization transition requires grounded render parameters")
    region_id = str(trigger_event.render_params.get("region_id", "")).strip()
    definition_id = str(
        trigger_event.render_params.get("condition_definition_id", "")
    ).strip()
    if (
        not region_id
        or region_id != str(getattr(region, "id", ""))
        or definition_id != str(condition.definition_id)
        or condition.target_kind != "region"
        or str(condition.target_id) != region_id
        or condition.cause_event_id != trigger_event.id
        or not condition.is_active(int(world.month_stamp))
    ):
        raise ValueError("organization transition requires a matching active condition")
    active = world.mechanical_language.get_active_conditions(
        EntityRef("region", region_id), int(world.month_stamp)
    )
    if not any(item.id == condition.id for item in active):
        raise ValueError("organization condition is not registered in canonical state")
    if not getattr(sect, "is_active", False):
        raise ValueError("organization transition requires an active sect")
    grounded = set(eligible_member_ids(sect, region_id=region_id))
    supplied = tuple(
        sorted(set(str(item).strip() for item in eligible_ids if str(item).strip()))
    )
    if not set(supplied).issubset(grounded):
        raise ValueError("organization transition contains an ineligible member")
    return supplied


def build_organization_interpreter_context(
    sect: Any,
    region: Any,
    condition: Any,
    eligible_ids: Sequence[str],
    trigger_event: Event,
) -> dict[str, Any]:
    return {
        "trigger": {
            "event_id": trigger_event.id,
            "event_type": trigger_event.event_type,
        },
        "organization": {
            "kind": "sect",
            "id": str(sect.id),
            "name": str(sect.name),
            "active": bool(sect.is_active),
        },
        "region": {"id": str(region.id), "name": str(region.name)},
        "condition": condition.to_dict(),
        "treasury": int(getattr(sect, "magic_stone", 0)),
        "eligible_member_ids": sorted(str(item) for item in eligible_ids),
        "support_amount": support_amount(),
    }


def _parse(raw: Any, eligible_ids: set[str]) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping) or set(raw) - {
        "decision",
        "reason",
        "action_intent",
    }:
        raise ValueError("organization interpretation must be a closed object")
    decision = raw.get("decision")
    reason = raw.get("reason")
    if (
        decision not in {item.value for item in OrganizationDecisionKind}
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        raise ValueError("invalid organization decision")
    if decision == OrganizationDecisionKind.MAINTAIN.value:
        if "action_intent" in raw:
            raise ValueError("maintain cannot carry an action intent")
        return {"decision": decision, "reason": reason.strip()}
    intent = raw.get("action_intent")
    if not isinstance(intent, Mapping) or set(intent) != {"action_kind", "member_id"}:
        raise ValueError("support requires a closed member intent")
    member_id = str(intent.get("member_id", "")).strip()
    if (
        intent.get("action_kind") != OrganizationIntentKind.SUPPORT_MEMBER.value
        or member_id not in eligible_ids
    ):
        raise ValueError("support member is not eligible")
    return {
        "decision": decision,
        "reason": reason.strip(),
        "action_intent": {"action_kind": intent["action_kind"], "member_id": member_id},
    }


def _rule(eligible_ids: Sequence[str]) -> dict[str, Any]:
    if eligible_ids:
        return {
            "decision": OrganizationDecisionKind.SUPPORT_MEMBER.value,
            "reason": "A present member needs support and the sect can afford it.",
            "action_intent": {
                "action_kind": OrganizationIntentKind.SUPPORT_MEMBER.value,
                "member_id": sorted(eligible_ids)[0],
            },
        }
    return {
        "decision": OrganizationDecisionKind.MAINTAIN.value,
        "reason": "No eligible member support is grounded in this region.",
    }


def _decision_event(
    world: Any,
    sect: Any,
    region: Any,
    condition: Any,
    trigger: Event,
    decision: OrganizationDecision,
    source: str,
) -> Event:
    intent = decision.action_intent.to_dict() if decision.action_intent else None
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="sect",
        subject_id=str(sect.id),
        source=source,
        considered_count=1,
        chosen_chain=[intent] if intent else [],
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t(
            "{sect_name} considered a response to a regional condition.",
            sect_name=sect.name,
        ),
        related_sects=[int(sect.id)],
        related_avatars=(
            [str(decision.action_intent.member_id)] if decision.action_intent else []
        ),
        event_type="organization_interpretation_decision",
        render_key="organization_interpretation_decision",
        render_params={
            "sect_id": str(sect.id),
            "region_id": str(region.id),
            "condition_instance_id": str(condition.id),
            "decision": decision.decision.value,
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
            "interpretation": {
                "decision": decision.decision.value,
                "reason": decision.reason,
                "source": source,
                "condition_instance_id": str(condition.id),
                "action_intent": intent,
            },
        },
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=str(trigger.id),
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    return event


async def interpret_organization_transition(
    world: Any,
    sect: Any,
    region: Any,
    condition: Any,
    trigger_event: Event,
    eligible_ids: Sequence[str],
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
) -> tuple[OrganizationDecision, Event]:
    eligible_ids = _validate_transition(
        world, sect, region, condition, trigger_event, eligible_ids
    )
    infos = build_organization_interpreter_context(
        sect, region, condition, eligible_ids, trigger_event
    )
    source = "llm"
    try:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            source = "rule"
            raw = _rule(eligible_ids)
        else:
            caller = llm_call or call_llm_with_task_name
            template = resolve_locale_template_path(
                ORGANIZATION_INTERPRETER_TEMPLATE,
                current_locale=str(
                    (getattr(world, "run_config_snapshot", {}) or {}).get(
                        "content_locale", ""
                    )
                )
                or None,
            )
            raw = caller(
                ORGANIZATION_INTERPRETER_TASK,
                template,
                infos,
                output_schema=ORGANIZATION_INTERPRETER_SCHEMA,
            )
            if inspect.isawaitable(raw):
                raw = await raw
        parsed = _parse(raw, set(str(item) for item in eligible_ids))
    except (
        LLMError,
        ParseError,
        ProviderCallError,
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):
        source = "rule"
        parsed = _rule(eligible_ids)
    if parsed["decision"] == OrganizationDecisionKind.MAINTAIN.value:
        decision = OrganizationDecision(
            OrganizationDecisionKind.MAINTAIN, parsed["reason"]
        )
    else:
        intent = SectMemberSupportIntentProposal(
            action_kind=OrganizationIntentKind.SUPPORT_MEMBER,
            subject_kind="sect",
            subject_id=str(sect.id),
            member_id=parsed["action_intent"]["member_id"],
            region_id=str(region.id),
            motivation_event_ids=(str(trigger_event.id),),
            reason=parsed["reason"],
        )
        decision = OrganizationDecision(
            OrganizationDecisionKind.SUPPORT_MEMBER, parsed["reason"], intent
        )
    return decision, _decision_event(
        world, sect, region, condition, trigger_event, decision, source
    )


__all__ = [
    "ORGANIZATION_INTERPRETER_SCHEMA",
    "ORGANIZATION_INTERPRETER_TASK",
    "build_organization_interpreter_context",
    "interpret_organization_transition",
]
