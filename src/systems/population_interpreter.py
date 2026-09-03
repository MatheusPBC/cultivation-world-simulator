"""Interpret grounded city population transitions into auditable intents."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_proposal import (
    PopulationTransferIntentProposal,
    PopulationDecision,
    PopulationDecisionKind,
    PopulationIntentKind,
    PopulationPreference,
)
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.mechanical_language import EntityRef
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


POPULATION_INTERPRETER_TASK = "population_interpreter"
POPULATION_INTERPRETER_TEMPLATE = "population_interpreter.txt"

_PREFERENCES = tuple(item.value for item in PopulationPreference)

POPULATION_INTERPRETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["maintain", "act"]},
        "reason": {"type": "string"},
        "action_intent": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action_kind", "preferences"],
            "properties": {
                "action_kind": {"type": "string", "enum": [PopulationIntentKind.POPULATION_TRANSFER.value]},
                "preferences": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "enum": list(_PREFERENCES)},
                },
            },
        },
    },
    "additionalProperties": False,
    "oneOf": [
        {
            "required": ["decision", "reason"],
            "properties": {
                "decision": {"const": PopulationDecisionKind.MAINTAIN.value},
                "reason": {"type": "string"},
            },
            "additionalProperties": False,
        },
        {
            "required": ["decision", "reason", "action_intent"],
            "properties": {
                "decision": {"const": PopulationDecisionKind.ACT.value},
                "reason": {"type": "string"},
                "action_intent": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action_kind", "preferences"],
                    "properties": {
                        "action_kind": {
                            "type": "string",
                            "enum": [PopulationIntentKind.POPULATION_TRANSFER.value],
                        },
                        "preferences": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"type": "string", "enum": list(_PREFERENCES)},
                        },
                    },
                },
            },
            "additionalProperties": False,
        },
    ],
}


def _validate_transition(world: Any, transition_event: Event) -> tuple[CityRegion, Any]:
    if transition_event.event_type != "semantic_condition_activated":
        raise ValueError("population interpretation requires semantic_condition_activated")
    params = transition_event.render_params
    if not isinstance(params, Mapping):
        raise ValueError("population transition requires region_id and condition_definition_id")
    region_id = str(params.get("region_id", "")).strip()
    definition_id = str(params.get("condition_definition_id", "")).strip()
    if not region_id or not definition_id:
        raise ValueError("population transition requires region_id and condition_definition_id")

    regions = getattr(getattr(world, "map", None), "regions", {}) or {}
    region = regions.get(region_id)
    if region is None:
        try:
            region = regions.get(int(region_id))
        except (TypeError, ValueError):
            region = None
    if not isinstance(region, CityRegion):
        raise ValueError("population transition must target a CityRegion")

    month = int(world.month_stamp)
    condition = next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)),
                month,
            )
            if item.definition_id == definition_id
            and item.target_kind == "region"
            and str(item.target_id) == str(region.id)
        ),
        None,
    )
    if condition is None:
        raise ValueError("population transition requires a matching active condition")
    return region, condition


def _ratio(region: CityRegion) -> float:
    return float(region.population_ratio)


def _context(world: Any, origin: CityRegion, condition: Any) -> dict[str, Any]:
    candidates = []
    for region in sorted(getattr(world.map, "regions", {}).values(), key=lambda item: int(item.id)):
        if not isinstance(region, CityRegion) or region.id == origin.id:
            continue
        candidates.append({
            "id": str(region.id),
            "name": str(region.name),
            "population": float(region.population),
            "capacity": float(region.population_capacity),
            "ratio": _ratio(region),
            "distance": abs(origin.center_loc[0] - region.center_loc[0])
            + abs(origin.center_loc[1] - region.center_loc[1]),
        })

    return {
        "origin": {
            "id": str(origin.id),
            "name": str(origin.name),
            "population": float(origin.population),
            "capacity": float(origin.population_capacity),
            "ratio": _ratio(origin),
            "condition": {
                "id": str(condition.id),
                "definition_id": str(condition.definition_id),
                "label": str(condition.label),
                "intensity": float(condition.intensity),
                "started_month": int(condition.started_month),
                "cause_event_id": str(condition.cause_event_id),
            },
            "source_readings": [dict(reading) for reading in condition.source_readings],
        },
        "candidates": candidates,
    }


def _parse_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("population interpretation must be an object")
    result = dict(raw)
    if set(result) - {"decision", "reason", "action_intent"}:
        raise ValueError("population interpretation contains unsupported fields")
    decision = result.get("decision")
    reason = result.get("reason")
    if decision not in {PopulationDecisionKind.MAINTAIN.value, PopulationDecisionKind.ACT.value}:
        raise ValueError("population interpretation has an invalid decision")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("population interpretation requires a reason")
    intent = result.get("action_intent")
    if decision == PopulationDecisionKind.MAINTAIN.value:
        if "action_intent" in result:
            raise ValueError("maintain cannot carry an action intent")
        return {"decision": decision, "reason": reason.strip()}
    if not isinstance(intent, Mapping) or set(intent) != {"action_kind", "preferences"}:
        raise ValueError("act requires a closed action intent")
    if intent.get("action_kind") != PopulationIntentKind.POPULATION_TRANSFER.value:
        raise ValueError("unsupported population action intent")
    preferences = intent.get("preferences")
    if not isinstance(preferences, list) or any(item not in _PREFERENCES for item in preferences):
        raise ValueError("population action preferences are invalid")
    if len(set(preferences)) != len(preferences):
        raise ValueError("population action preferences must be unique")
    return {"decision": decision, "reason": reason.strip(), "action_intent": {"action_kind": intent["action_kind"], "preferences": list(preferences)}}


def _rule_maintain(reason: str) -> dict[str, Any]:
    return {"decision": PopulationDecisionKind.MAINTAIN.value, "reason": reason}


def _decision_from_result(
    result: Mapping[str, Any],
    *,
    origin: CityRegion,
    transition_event: Event,
) -> PopulationDecision:
    if result["decision"] == PopulationDecisionKind.MAINTAIN.value:
        return PopulationDecision(PopulationDecisionKind.MAINTAIN, str(result["reason"]))
    intent_data = result["action_intent"]
    intent = PopulationTransferIntentProposal(
        action_kind=PopulationIntentKind(intent_data["action_kind"]),
        subject_kind="population",
        subject_id=f"region:{origin.id}",
        motivation_event_ids=(str(transition_event.id),),
        preferences=tuple(PopulationPreference(item) for item in intent_data["preferences"]),
        reason=str(result["reason"]),
    )
    return PopulationDecision(PopulationDecisionKind.ACT, str(result["reason"]), intent)


def _decision_event(
    world: Any,
    origin: CityRegion,
    transition_event: Event,
    decision: PopulationDecision,
    *,
    source: str,
) -> Event:
    intent_dict = decision.action_intent.to_dict() if decision.action_intent is not None else None
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="population",
        subject_id=f"region:{origin.id}",
        source=source,
        considered_count=sum(
            isinstance(region, CityRegion) and region.id != origin.id
            for region in getattr(world.map, "regions", {}).values()
        ),
        chosen_chain=[intent_dict] if intent_dict is not None else [],
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t(
            "{region} interpreted a population transition as {decision}: {reason}",
            region=origin.name,
            decision=decision.decision.value,
            reason=decision.reason,
        ),
        event_type="population_interpretation_decision",
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
                "action_intent": intent_dict,
            },
        },
    )
    event.causal_links.append(CausalLink(
        event_id=event.id,
        cause_event_id=str(transition_event.id),
        relation=CausalRelation.RESPONSE_TO,
    ))
    return event


async def interpret_population_transition(
    world: Any,
    transition_event: Event,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
) -> tuple[PopulationDecision, Event]:
    """Interpret one active semantic population condition without changing state."""
    origin, condition = _validate_transition(world, transition_event)
    infos = _context(world, origin, condition)
    source = "llm"
    try:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            source = "rule"
            raw = resolve_test_mode_task(POPULATION_INTERPRETER_TASK, infos)
        else:
            caller = llm_call or call_llm_with_task_name
            template_path = resolve_locale_template_path(
                POPULATION_INTERPRETER_TEMPLATE,
                current_locale=str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None,
            )
            raw = caller(
                POPULATION_INTERPRETER_TASK,
                template_path,
                infos,
                output_schema=POPULATION_INTERPRETER_SCHEMA,
            )
            if inspect.isawaitable(raw):
                raw = await raw
        result = _parse_result(raw)
    except (LLMError, ParseError, ProviderCallError, ValueError, TypeError, KeyError):
        source = "rule"
        result = _rule_maintain("No population interpretation was available; the transition remains under observation.")

    decision = _decision_from_result(result, origin=origin, transition_event=transition_event)
    return decision, _decision_event(world, origin, transition_event, decision, source=source)
