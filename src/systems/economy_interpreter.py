from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.agent_decision import AgentDecision
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_proposal import (
    EconomyDecision,
    EconomyDecisionKind,
    EconomyIntentKind,
    EconomyPreference,
    ResourceTransferIntentProposal,
)
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ParseError, ProviderCallError
from src.utils.llm.runtime_mode import is_test_mode_enabled, is_world_test_mode
from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task
from src.systems.resource_transfer import find_canonical_route


ECONOMY_INTERPRETER_TASK = "economy_interpreter"
ECONOMY_INTERPRETER_TEMPLATE = "economy_interpreter.txt"
_PREFERENCES = tuple(item.value for item in EconomyPreference)


async def interpret_resource_shortage(
    world: Any,
    shortage_event: Event,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    force_rule: bool = False,
) -> tuple[EconomyDecision, Event]:
    destination, resource_id = _validate_shortage(world, shortage_event)
    infos = _context(world, destination, resource_id, shortage_event)
    source = "rule"
    try:
        if force_rule or is_world_test_mode(world) or is_test_mode_enabled():
            raw = resolve_test_mode_task(ECONOMY_INTERPRETER_TASK, infos)
        else:
            source = "llm"
            caller = llm_call or call_llm_with_task_name
            template = resolve_locale_template_path(
                ECONOMY_INTERPRETER_TEMPLATE,
                current_locale=str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None,
            )
            raw = caller(ECONOMY_INTERPRETER_TASK, template, infos, output_schema=ECONOMY_INTERPRETER_SCHEMA)
            if inspect.isawaitable(raw):
                raw = await raw
        result = _parse_result(raw)
    except (LLMError, ParseError, ProviderCallError, ValueError, TypeError, KeyError):
        result = {"decision": "maintain", "reason": "The shortage has no grounded transfer affordance yet."}
    decision = _decision_from_result(result, destination, resource_id, shortage_event)
    return decision, _decision_event(world, destination, shortage_event, decision, source=source)


def _validate_shortage(world: Any, event: Event) -> tuple[CityRegion, str]:
    if event.event_type != "regional_resource_shortage" or not isinstance(event.render_params, Mapping):
        raise ValueError("economy interpretation requires a regional resource shortage")
    region_id = str(event.render_params.get("region_id", ""))
    resource_id = str(event.render_params.get("resource_id", ""))
    region = world.map.regions.get(int(region_id))
    if not isinstance(region, CityRegion) or not resource_id:
        raise ValueError("shortage must identify a city and resource")
    return region, resource_id


def _context(world: Any, destination: CityRegion, resource_id: str, event: Event) -> dict[str, Any]:
    candidates = []
    for region in sorted(world.map.regions.values(), key=lambda item: int(item.id)):
        if not isinstance(region, CityRegion) or region.id == destination.id:
            continue
        route = find_canonical_route(world, region, destination, resource_id)
        candidates.append({
            "id": str(region.id),
            "name": str(region.name),
            "stock": region.economy.available_stock(resource_id),
            "source_access": float(region.economy.access.get(resource_id, 0.0)),
            "transport_capacity": float(region.infrastructure.capacities.get("transport", 0.0)),
            "route": {
                "available": route is not None,
                "id": route["route_id"] if route is not None else None,
                "capacity": route["capacity"] if route is not None else None,
            },
        })
    return {
        "shortage": dict(event.render_params),
        "destination": {
            "id": str(destination.id),
            "name": str(destination.name),
            "stock": destination.economy.available_stock(resource_id),
            "capacity": float(destination.economy.capacities.get(resource_id, 0.0)),
            "demand": float(destination.economy.demand_rates.get(resource_id, 0.0)),
            "access": float(destination.economy.access.get(resource_id, 0.0)),
            "transport_capacity": float(destination.infrastructure.capacities.get("transport", 0.0)),
            "route_required": True,
        },
        "resource_id": resource_id,
        "candidates": candidates,
    }


def _parse_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, Mapping):
        raise ValueError("economy interpretation must be an object")
    result = dict(raw)
    if result.get("decision") not in {"act", "maintain"} or not isinstance(result.get("reason"), str) or not result["reason"].strip():
        raise ValueError("economy interpretation requires decision and reason")
    if result["decision"] == "maintain":
        if "action_intent" in result:
            raise ValueError("maintain cannot carry an action intent")
        return {"decision": "maintain", "reason": result["reason"].strip()}
    intent = result.get("action_intent")
    if not isinstance(intent, Mapping) or set(intent) != {"action_kind", "preferences"}:
        raise ValueError("act requires a closed resource transfer intent")
    if intent.get("action_kind") != EconomyIntentKind.RESOURCE_TRANSFER.value:
        raise ValueError("unsupported economy action intent")
    preferences = intent.get("preferences")
    if not isinstance(preferences, list) or len(set(preferences)) != len(preferences) or any(item not in _PREFERENCES for item in preferences):
        raise ValueError("economy action preferences are invalid")
    return {"decision": "act", "reason": result["reason"].strip(), "action_intent": {"action_kind": intent["action_kind"], "preferences": preferences}}


def _decision_from_result(result: Mapping[str, Any], destination: CityRegion, resource_id: str, event: Event) -> EconomyDecision:
    if result["decision"] == "maintain":
        return EconomyDecision(EconomyDecisionKind.MAINTAIN, result["reason"])
    intent_data = result["action_intent"]
    intent = ResourceTransferIntentProposal(
        action_kind=EconomyIntentKind(intent_data["action_kind"]),
        subject_kind="region",
        subject_id=f"region:{destination.id}",
        resource_id=resource_id,
        motivation_event_ids=(event.id,),
        preferences=tuple(EconomyPreference(item) for item in intent_data["preferences"]),
        reason=result["reason"],
    )
    return EconomyDecision(EconomyDecisionKind.ACT, result["reason"], intent)


def _decision_event(world: Any, destination: CityRegion, shortage_event: Event, decision: EconomyDecision, *, source: str) -> Event:
    intent = decision.action_intent.to_dict() if decision.action_intent else None
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="economy",
        subject_id=f"region:{destination.id}",
        source=source,
        considered_count=sum(isinstance(region, CityRegion) and region.id != destination.id for region in world.map.regions.values()),
        chosen_chain=[intent] if intent else [],
        thinking=decision.reason,
    )
    event = Event(
        world.month_stamp,
        t("{region} interpreted a resource shortage as {decision}: {reason}", region=destination.name, decision=decision.decision.value, reason=decision.reason),
        event_type="economy_interpretation_decision",
        fact_kind=FactKind.DECISION,
        causal_origin=(
            CausalOrigin.LLM_INTERPRETATION
            if source == "llm"
            else CausalOrigin.DETERMINISTIC
        ),
        causal_payload={"deltas": [], "decision": audit.to_dict(), "interpretation": decision.to_dict()},
    )
    event.causal_links.append(CausalLink(event_id=event.id, cause_event_id=shortage_event.id, relation=CausalRelation.RESPONSE_TO))
    return event


ECONOMY_INTERPRETER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "reason"],
    "properties": {
        "decision": {"type": "string", "enum": ["maintain", "act"]},
        "reason": {"type": "string"},
        "action_intent": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action_kind", "preferences"],
            "properties": {
                "action_kind": {"type": "string", "enum": ["resource_transfer"]},
                "preferences": {"type": "array", "uniqueItems": True, "items": {"type": "string", "enum": list(_PREFERENCES)}},
            },
        },
    },
}
