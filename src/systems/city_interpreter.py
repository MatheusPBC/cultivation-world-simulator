"""Interpret grounded urban risk transitions into typed maintenance intents."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.domain_proposal import (
    CityCapacityProjectIntentProposal,
    CityDecision,
    CityDecisionKind,
    CityIntentKind,
    CityMaintenanceIntentProposal,
)
from src.classes.environment.city_state import CityGovernance, UrbanAsset
from src.classes.environment.region import CityRegion
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import PrimitiveDimension
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.systems.semantic_world.condition_semantics import metric_leaves
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


CITY_INTERPRETER_TASK = "city_interpreter"
CITY_INTERPRETER_TEMPLATE = "city_interpreter.txt"


CITY_INTERPRETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "oneOf": [
        {
            "required": ["decision", "reason"],
            "properties": {
                "decision": {"const": CityDecisionKind.MAINTAIN.value},
                "reason": {"type": "string"},
            },
            "additionalProperties": False,
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {"const": CityDecisionKind.URBAN_MAINTENANCE.value},
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "capability_id"],
                    "properties": {
                        "action_kind": {
                            "const": CityIntentKind.URBAN_MAINTENANCE.value,
                        },
                        "capability_id": {"type": "string", "minLength": 1},
                    },
                },
            },
            "additionalProperties": False,
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {"const": CityDecisionKind.URBAN_CAPACITY_PROJECT.value},
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "project_kind"],
                    "properties": {
                        "action_kind": {"const": CityIntentKind.URBAN_CAPACITY_PROJECT.value},
                        "project_kind": {"const": "settlement_capacity_expansion"},
                    },
                },
            },
            "additionalProperties": False,
        },
    ],
}


def _region_for_event(world: Any, event: Event) -> CityRegion:
    if event.event_type != "semantic_condition_activated":
        raise ValueError("city interpretation requires semantic_condition_activated")
    if not isinstance(event.render_params, Mapping):
        raise ValueError("city transition requires region_id and condition_definition_id")
    region_id = str(event.render_params.get("region_id", "")).strip()
    if not region_id:
        raise ValueError("city transition requires region_id")
    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            region = None
    if not isinstance(region, CityRegion):
        raise ValueError("city transition must target a CityRegion")
    return region


def _asset_payload(asset: UrbanAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "district_id": asset.district_id,
        "capability_ids": list(asset.capability_ids),
        "capacity": float(asset.capacity),
        "quality": float(asset.quality),
        "integrity": float(asset.integrity),
        "effective_quality": float(asset.quality * asset.integrity),
    }


def derive_eligible_capability_ids(
    world: Any,
    region: CityRegion,
    condition: Any,
    assets: Sequence[UrbanAsset],
) -> tuple[str, ...]:
    """Return only grounded capabilities supported by an urban risk metric.

    Legacy quality-based city conditions remain eligible.  The V1 urban
    service path additionally accepts access, load, or capacity leaves only
    when they explicitly carry the urban-service qualifier and name a
    declared service demand.
    """
    state = getattr(world, "mechanical_language", None)
    if state is None:
        return ()
    condition_definition = state.condition_definitions.get(condition.definition_id)
    if condition_definition is None or condition_definition.target_kind != "region":
        return ()
    metric_definition = state.derived_definitions.get(condition_definition.metric_definition_id)
    if (
        metric_definition is None
        or metric_definition.target_kind != "region"
        or metric_definition.dimension is not PrimitiveDimension.RISK
    ):
        return ()
    declared_services = {
        item.capability_id for item in region.city_state.service_demands
    }
    quality_capabilities = {
        str(leaf.get("concept_id", "")).strip()
        for leaf in metric_leaves(
            metric_definition.expression,
            state.derived_definitions,
        )
        if leaf.get("dimension") == PrimitiveDimension.QUALITY.value
        and str(leaf.get("concept_id", "")).strip()
    }
    urban_service_capabilities = {
        str(leaf.get("concept_id", "")).strip()
        for leaf in metric_leaves(
            metric_definition.expression,
            state.derived_definitions,
        )
        if leaf.get("dimension")
        in {
            PrimitiveDimension.ACCESS.value,
            PrimitiveDimension.LOAD.value,
            PrimitiveDimension.CAPACITY.value,
        }
        and dict(leaf.get("qualifiers", {}) or {}).get("kind") == "urban_service"
        and str(leaf.get("concept_id", "")).strip() in declared_services
    }
    grounded = {
        capability
        for asset in assets
        for capability in asset.capability_ids
    }
    return tuple(
        sorted((quality_capabilities | urban_service_capabilities).intersection(grounded))
    )


def build_city_interpreter_context(
    region: CityRegion,
    condition: Any,
    assets: Sequence[UrbanAsset],
    governance: CityGovernance,
    trigger_event: Event | None = None,
    eligible_capability_ids: Sequence[str] = (),
    eligible_project_kinds: Sequence[str] = (),
) -> dict[str, Any]:
    """Build only grounded facts exposed to the interpreter."""
    return {
        "trigger": {
            "event_id": str(trigger_event.id) if trigger_event is not None else str(condition.cause_event_id),
            "event_type": trigger_event.event_type if trigger_event is not None else "semantic_condition_activated",
        },
        "city": {
            "id": str(region.id),
            "name": str(region.name),
            "governance": governance.to_dict(),
        },
        "condition": condition.to_dict(),
        "assets": [_asset_payload(asset) for asset in assets],
        "eligible_capability_ids": sorted(set(str(item) for item in eligible_capability_ids)),
        "eligible_project_kinds": sorted(set(str(item) for item in eligible_project_kinds)),
    }


def _parse_result(
    raw: Any,
    valid_capabilities: set[str],
    valid_project_kinds: set[str],
) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("city interpretation must be an object")
    result = dict(raw)
    if set(result) - {"decision", "reason", "action_intent"}:
        raise ValueError("city interpretation contains unsupported fields")
    decision = result.get("decision")
    reason = result.get("reason")
    if decision not in {item.value for item in CityDecisionKind}:
        raise ValueError("city interpretation has an invalid decision")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("city interpretation requires a reason")
    if decision == CityDecisionKind.MAINTAIN.value:
        if "action_intent" in result:
            raise ValueError("maintain cannot carry an action intent")
        return {"decision": decision, "reason": reason.strip()}
    intent = result.get("action_intent")
    if not isinstance(intent, Mapping):
        raise ValueError("acting city decisions require an action intent")
    if decision == CityDecisionKind.URBAN_MAINTENANCE.value:
        if set(intent) != {"action_kind", "capability_id"}:
            raise ValueError("urban maintenance requires a closed action intent")
        capability_id = str(intent.get("capability_id", "")).strip()
        if intent.get("action_kind") != CityIntentKind.URBAN_MAINTENANCE.value:
            raise ValueError("unsupported city action intent")
        if capability_id not in valid_capabilities:
            raise ValueError("urban maintenance capability is not present in the city")
        return {
            "decision": decision,
            "reason": reason.strip(),
            "action_intent": {
                "action_kind": intent["action_kind"],
                "capability_id": capability_id,
            },
        }
    if set(intent) != {"action_kind", "project_kind"}:
        raise ValueError("urban capacity project requires a closed action intent")
    project_kind = str(intent.get("project_kind", "")).strip()
    if intent.get("action_kind") != CityIntentKind.URBAN_CAPACITY_PROJECT.value:
        raise ValueError("unsupported city action intent")
    if project_kind not in valid_project_kinds:
        raise ValueError("urban capacity project is not currently afforded")
    return {
        "decision": decision,
        "reason": reason.strip(),
        "action_intent": {
            "action_kind": intent["action_kind"],
            "project_kind": project_kind,
        },
    }


def _decision_from_result(
    result: Mapping[str, Any],
    *,
    region: CityRegion,
    trigger_event: Event,
) -> CityDecision:
    if result["decision"] == CityDecisionKind.MAINTAIN.value:
        return CityDecision(CityDecisionKind.MAINTAIN, str(result["reason"]))
    intent_data = result["action_intent"]
    decision_kind = CityDecisionKind(result["decision"])
    if decision_kind is CityDecisionKind.URBAN_MAINTENANCE:
        intent = CityMaintenanceIntentProposal(
            action_kind=CityIntentKind(intent_data["action_kind"]),
            subject_kind="city",
            subject_id=f"region:{region.id}",
            capability_id=str(intent_data["capability_id"]),
            motivation_event_ids=(str(trigger_event.id),),
            reason=str(result["reason"]),
        )
    else:
        intent = CityCapacityProjectIntentProposal(
            action_kind=CityIntentKind(intent_data["action_kind"]),
            subject_kind="city",
            subject_id=f"region:{region.id}",
            project_kind=str(intent_data["project_kind"]),
            motivation_event_ids=(str(trigger_event.id),),
            reason=str(result["reason"]),
        )
    return CityDecision(decision_kind, str(result["reason"]), intent)


def _decision_event(
    world: Any,
    region: CityRegion,
    trigger_event: Event,
    condition: Any,
    decision: CityDecision,
    *,
    source: str,
) -> Event:
    intent = decision.action_intent.to_dict() if decision.action_intent else None
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="city",
        subject_id=f"region:{region.id}",
        source=source,
        considered_count=len(region.city_state.assets),
        chosen_chain=[intent] if intent else [],
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t(
            "{region} interpreted an urban risk as {decision}: {reason}",
            region=region.name,
            decision=decision.decision.value,
            reason=decision.reason,
        ),
        event_type="city_interpretation_decision",
        render_key="city_interpretation_decision",
        render_params={
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
                "source_readings": [dict(item) for item in condition.source_readings],
                "action_intent": intent,
            },
        },
    )
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=str(trigger_event.id),
        relation=CausalRelation.RESPONSE_TO,
    ))
    return event


async def interpret_city_transition(
    world: Any,
    trigger_event: Event,
    condition: Any,
    assets: Sequence[UrbanAsset],
    governance: CityGovernance,
    *,
    eligible_capability_ids: Sequence[str] | None = None,
    eligible_project_kinds: Sequence[str] = (),
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
) -> tuple[CityDecision, Event]:
    """Interpret one eligible condition without changing canonical city state."""
    region = _region_for_event(world, trigger_event)
    if str(condition.target_id) != str(region.id) or condition.target_kind != "region":
        raise ValueError("city condition target does not match the transition city")
    assets = tuple(assets)
    valid_capabilities = set(
        derive_eligible_capability_ids(world, region, condition, assets)
        if eligible_capability_ids is None
        else (str(item) for item in eligible_capability_ids)
    )
    valid_project_kinds = {str(item) for item in eligible_project_kinds}
    infos = build_city_interpreter_context(
        region,
        condition,
        assets,
        governance,
        trigger_event,
        tuple(sorted(valid_capabilities)),
        tuple(sorted(valid_project_kinds)),
    )
    source = "llm"
    try:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            source = "rule"
            raw = resolve_test_mode_task(CITY_INTERPRETER_TASK, infos)
        else:
            caller = llm_call or call_llm_with_task_name
            template_path = resolve_locale_template_path(
                CITY_INTERPRETER_TEMPLATE,
                current_locale=str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None,
            )
            raw = caller(
                CITY_INTERPRETER_TASK,
                template_path,
                infos,
                output_schema=CITY_INTERPRETER_SCHEMA,
            )
            if inspect.isawaitable(raw):
                raw = await raw
        result = _parse_result(raw, valid_capabilities, valid_project_kinds)
    except (LLMError, ParseError, ProviderCallError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        source = "rule"
        result = {"decision": CityDecisionKind.MAINTAIN.value, "reason": "The urban risk remains under observation."}
    decision = _decision_from_result(result, region=region, trigger_event=trigger_event)
    return decision, _decision_event(world, region, trigger_event, condition, decision, source=source)


__all__ = [
    "CITY_INTERPRETER_SCHEMA",
    "CITY_INTERPRETER_TASK",
    "build_city_interpreter_context",
    "derive_eligible_capability_ids",
    "interpret_city_transition",
]
