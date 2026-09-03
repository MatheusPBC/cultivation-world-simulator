"""Interpret grounded urban conditions from the current dynasty's view."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_proposal import (
    GovernmentDecision,
    GovernmentDecisionKind,
    GovernmentIntentKind,
    GovernmentUrbanIntentProposal,
)
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.systems.city_interpreter import derive_eligible_capability_ids
from src.systems.semantic_world.condition_semantics import is_settlement_pressure
from src.systems.urban_capacity_project import (
    PROJECT_KIND,
    can_start_urban_capacity_project,
)
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode


GOVERNMENT_INTERPRETER_TASK = "government_interpreter"
GOVERNMENT_INTERPRETER_TEMPLATE = "government_interpreter.txt"

GOVERNMENT_INTERPRETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "oneOf": [
        {
            "required": ["decision", "reason"],
            "properties": {
                "decision": {"const": GovernmentDecisionKind.MAINTAIN.value},
                "reason": {"type": "string"},
            },
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {"const": GovernmentDecisionKind.URBAN_MAINTENANCE.value},
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "capability_id"],
                    "properties": {
                        "action_kind": {
                            "const": GovernmentIntentKind.URBAN_MAINTENANCE.value
                        },
                        "capability_id": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {
                    "const": GovernmentDecisionKind.URBAN_CAPACITY_PROJECT.value
                },
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "project_kind"],
                    "properties": {
                        "action_kind": {
                            "const": GovernmentIntentKind.URBAN_CAPACITY_PROJECT.value
                        },
                        "project_kind": {"const": PROJECT_KIND},
                    },
                },
            },
        },
    ],
}


def _region_for_event(world: Any, trigger_event: Event) -> CityRegion:
    if trigger_event.event_type != "semantic_condition_activated":
        raise ValueError(
            "government interpretation requires semantic_condition_activated"
        )
    if not isinstance(trigger_event.render_params, Mapping):
        raise ValueError(
            "government transition requires region_id and condition_definition_id"
        )
    region_id = str(trigger_event.render_params.get("region_id", "")).strip()
    if not region_id:
        raise ValueError("government transition requires region_id")
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            region = None
    if not isinstance(region, CityRegion):
        raise ValueError("government transition must target a CityRegion")
    return region


def _dynasty(world: Any) -> Any:
    dynasty = getattr(world, "dynasty", None)
    if dynasty is None or not getattr(dynasty, "id", None):
        raise ValueError("government interpretation requires a current dynasty")
    return dynasty


def is_dynasty_governed(world: Any, region: CityRegion) -> bool:
    """Return whether the city's explicit controller is the current dynasty."""
    dynasty = _dynasty(world)
    governance = region.city_state.governance
    return governance.controller_kind == "dynasty" and governance.controller_id == str(
        dynasty.id
    )


def _condition_for_event(world: Any, trigger_event: Event, region: CityRegion) -> Any:
    if not isinstance(trigger_event.render_params, Mapping):
        raise ValueError("government transition requires condition_definition_id")
    definition_id = str(
        trigger_event.render_params.get("condition_definition_id", "")
    ).strip()
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if item.definition_id == definition_id
            and item.target_kind == "region"
            and str(item.target_id) == str(region.id)
            and item.cause_event_id == trigger_event.id
        ),
        None,
    )
    if condition is None:
        raise ValueError("government transition requires a matching active condition")
    return condition


def eligible_project_kinds(
    world: Any, region: CityRegion, condition: Any
) -> tuple[str, ...]:
    definition = world.mechanical_language.condition_definitions.get(
        condition.definition_id
    )
    if (
        definition is not None
        and is_settlement_pressure(world, condition.definition_id)
        and can_start_urban_capacity_project(
            region,
            target_settlement_ratio=definition.resolve_below,
        )
    ):
        return (PROJECT_KIND,)
    return ()


def eligible_capability_ids(
    world: Any, region: CityRegion, condition: Any
) -> tuple[str, ...]:
    return derive_eligible_capability_ids(
        world, region, condition, region.city_state.assets
    )


def build_government_interpreter_context(
    world: Any,
    region: CityRegion,
    condition: Any,
    *,
    trigger_event: Event | None = None,
    capabilities: Sequence[str] = (),
    project_kinds: Sequence[str] = (),
) -> dict[str, Any]:
    dynasty = _dynasty(world)
    emperor_id = getattr(dynasty, "current_emperor_id", None)
    return {
        "trigger": {
            "event_id": str(trigger_event.id)
            if trigger_event is not None
            else str(condition.cause_event_id),
            "event_type": trigger_event.event_type
            if trigger_event is not None
            else "semantic_condition_activated",
        },
        "dynasty": {
            "id": str(dynasty.id),
            "name": str(getattr(dynasty, "name", "")),
            "current_emperor_id": str(emperor_id) if emperor_id else None,
        },
        "city": {
            "id": str(region.id),
            "name": str(region.name),
            "governance": region.city_state.governance.to_dict(),
            "assets": [asset.to_dict() for asset in region.city_state.assets],
            "population": float(region.population),
            "population_capacity": float(region.population_capacity),
        },
        "condition": condition.to_dict(),
        "eligible_capability_ids": sorted(set(str(item) for item in capabilities)),
        "eligible_project_kinds": sorted(set(str(item) for item in project_kinds)),
    }


def _parse_result(
    raw: Any, valid_capabilities: set[str], valid_projects: set[str]
) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("government interpretation must be an object")
    result = dict(raw)
    if set(result) - {"decision", "reason", "action_intent"}:
        raise ValueError("government interpretation contains unsupported fields")
    decision = result.get("decision")
    reason = result.get("reason")
    if decision not in {item.value for item in GovernmentDecisionKind}:
        raise ValueError("government interpretation has an invalid decision")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("government interpretation requires a reason")
    if decision == GovernmentDecisionKind.MAINTAIN.value:
        if "action_intent" in result:
            raise ValueError("maintain cannot carry an action intent")
        return {"decision": decision, "reason": reason.strip()}
    intent = result.get("action_intent")
    if not isinstance(intent, Mapping):
        raise ValueError("acting government decisions require an action intent")
    if decision == GovernmentDecisionKind.URBAN_MAINTENANCE.value:
        if set(intent) != {"action_kind", "capability_id"}:
            raise ValueError("government maintenance requires a closed action intent")
        capability_id = str(intent.get("capability_id", "")).strip()
        if intent.get("action_kind") != GovernmentIntentKind.URBAN_MAINTENANCE.value:
            raise ValueError("unsupported government action intent")
        if capability_id not in valid_capabilities:
            raise ValueError("government maintenance capability is not eligible")
        return {
            "decision": decision,
            "reason": reason.strip(),
            "action_intent": {
                "action_kind": intent["action_kind"],
                "capability_id": capability_id,
            },
        }
    if set(intent) != {"action_kind", "project_kind"}:
        raise ValueError("government capacity project requires a closed action intent")
    project_kind = str(intent.get("project_kind", "")).strip()
    if (
        intent.get("action_kind") != GovernmentIntentKind.URBAN_CAPACITY_PROJECT.value
        or project_kind not in valid_projects
    ):
        raise ValueError("government capacity project is not currently afforded")
    return {
        "decision": decision,
        "reason": reason.strip(),
        "action_intent": {
            "action_kind": intent["action_kind"],
            "project_kind": project_kind,
        },
    }


def _decision_from_result(
    result: Mapping[str, Any], *, world: Any, region: CityRegion, trigger_event: Event
) -> GovernmentDecision:
    if result["decision"] == GovernmentDecisionKind.MAINTAIN.value:
        return GovernmentDecision(
            GovernmentDecisionKind.MAINTAIN, str(result["reason"])
        )
    dynasty = _dynasty(world)
    intent_data = result["action_intent"]
    if result["decision"] == GovernmentDecisionKind.URBAN_MAINTENANCE.value:
        intent = GovernmentUrbanIntentProposal(
            action_kind=GovernmentIntentKind.URBAN_MAINTENANCE,
            subject_kind="dynasty",
            subject_id=f"dynasty:{dynasty.id}",
            region_id=str(region.id),
            capability_id=str(intent_data["capability_id"]),
            motivation_event_ids=(str(trigger_event.id),),
            reason=str(result["reason"]),
        )
    else:
        intent = GovernmentUrbanIntentProposal(
            action_kind=GovernmentIntentKind.URBAN_CAPACITY_PROJECT,
            subject_kind="dynasty",
            subject_id=f"dynasty:{dynasty.id}",
            region_id=str(region.id),
            project_kind=str(intent_data["project_kind"]),
            motivation_event_ids=(str(trigger_event.id),),
            reason=str(result["reason"]),
        )
    return GovernmentDecision(
        GovernmentDecisionKind(result["decision"]), str(result["reason"]), intent
    )


def _decision_event(
    world: Any,
    region: CityRegion,
    trigger_event: Event,
    condition: Any,
    decision: GovernmentDecision,
    *,
    source: str,
) -> Event:
    dynasty = _dynasty(world)
    intent = decision.action_intent.to_dict() if decision.action_intent else None
    emperor_id = getattr(dynasty, "current_emperor_id", None)
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="dynasty",
        subject_id=f"dynasty:{dynasty.id}",
        source=source,
        considered_count=1 + len(region.city_state.assets),
        chosen_chain=[intent] if intent else [],
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t(
            "The dynasty responded to {region}'s condition with {decision}: {reason}",
            region=region.name,
            decision=decision.decision.value,
            reason=decision.reason,
        ),
        related_avatars=[str(emperor_id)] if emperor_id else None,
        event_type="government_interpretation_decision",
        render_key="government_interpretation_decision",
        render_params={
            "dynasty_id": str(dynasty.id),
            "region_id": str(region.id),
            "condition_instance_id": str(condition.id),
            "decision": decision.decision.value,
        },
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.LLM_INTERPRETATION
        if source == "llm"
        else CausalOrigin.DETERMINISTIC,
        causal_payload={
            "deltas": [],
            "decision": audit.to_dict(),
            "interpretation": {
                "decision": decision.decision.value,
                "reason": decision.reason,
                "source": source,
                "dynasty_id": str(dynasty.id),
                "region_id": str(region.id),
                "condition_instance_id": str(condition.id),
                "source_readings": [dict(item) for item in condition.source_readings],
                "action_intent": intent,
            },
        },
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=str(trigger_event.id),
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    return event


def _rule_result(
    capabilities: Sequence[str], projects: Sequence[str]
) -> dict[str, Any]:
    if capabilities:
        return {
            "decision": GovernmentDecisionKind.URBAN_MAINTENANCE.value,
            "reason": "The dynasty maintains the first grounded urban capability.",
            "action_intent": {
                "action_kind": GovernmentIntentKind.URBAN_MAINTENANCE.value,
                "capability_id": str(sorted(capabilities)[0]),
            },
        }
    if projects:
        return {
            "decision": GovernmentDecisionKind.URBAN_CAPACITY_PROJECT.value,
            "reason": "The dynasty authorizes the available settlement capacity project.",
            "action_intent": {
                "action_kind": GovernmentIntentKind.URBAN_CAPACITY_PROJECT.value,
                "project_kind": str(sorted(projects)[0]),
            },
        }
    return {
        "decision": GovernmentDecisionKind.MAINTAIN.value,
        "reason": "The dynasty keeps the condition under observation.",
    }


def _maintain_result() -> dict[str, Any]:
    return {
        "decision": GovernmentDecisionKind.MAINTAIN.value,
        "reason": "The dynasty keeps the condition under observation.",
    }


async def interpret_government_transition(
    world: Any,
    trigger_event: Event,
    condition: Any,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
    capabilities: Sequence[str] | None = None,
    project_kinds: Sequence[str] | None = None,
) -> tuple[GovernmentDecision, Event]:
    """Return a grounded institutional decision without mutating canonical state."""
    region = _region_for_event(world, trigger_event)
    _dynasty(world)
    if not is_dynasty_governed(world, region):
        raise ValueError("government transition requires explicit dynasty control")
    if (
        str(condition.target_id) != str(region.id)
        or condition.target_kind != "region"
        or not condition.is_active(int(world.month_stamp))
    ):
        raise ValueError("government transition requires an active matching condition")
    valid_capabilities = (
        tuple(capabilities)
        if capabilities is not None
        else eligible_capability_ids(world, region, condition)
    )
    valid_projects = (
        tuple(project_kinds)
        if project_kinds is not None
        else eligible_project_kinds(world, region, condition)
    )
    infos = build_government_interpreter_context(
        world,
        region,
        condition,
        trigger_event=trigger_event,
        capabilities=valid_capabilities,
        project_kinds=valid_projects,
    )
    source = "rule"
    try:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            raw = _rule_result(valid_capabilities, valid_projects)
        else:
            source = "llm"
            caller = llm_call or call_llm_with_task_name
            template = resolve_locale_template_path(
                GOVERNMENT_INTERPRETER_TEMPLATE,
                current_locale=str(
                    (getattr(world, "run_config_snapshot", {}) or {}).get(
                        "content_locale", ""
                    )
                )
                or None,
            )
            raw = caller(
                GOVERNMENT_INTERPRETER_TASK,
                template,
                infos,
                output_schema=GOVERNMENT_INTERPRETER_SCHEMA,
            )
            if inspect.isawaitable(raw):
                raw = await raw
        result = _parse_result(
            raw,
            set(str(item) for item in valid_capabilities),
            set(str(item) for item in valid_projects),
        )
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
        result = _maintain_result()
    decision = _decision_from_result(
        result, world=world, region=region, trigger_event=trigger_event
    )
    return decision, _decision_event(
        world, region, trigger_event, condition, decision, source=source
    )


__all__ = [
    "GOVERNMENT_INTERPRETER_SCHEMA",
    "GOVERNMENT_INTERPRETER_TASK",
    "build_government_interpreter_context",
    "eligible_capability_ids",
    "eligible_project_kinds",
    "interpret_government_transition",
    "is_dynasty_governed",
]
