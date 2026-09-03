"""Deterministic structured LLM results used by rule-based test runs."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any


class TestModeLLMError(RuntimeError):
    """Base error for an LLM operation intentionally unavailable in test mode."""

    __test__ = False


class TestModeUnsupportedLLMTask(TestModeLLMError):
    __test__ = False
    def __init__(self, task_name: str):
        super().__init__(f"No rule fallback is registered for LLM task: {task_name}")
        self.task_name = task_name


class TestModeLLMUnavailable(TestModeLLMError):
    __test__ = False
    def __init__(self, feature: str):
        super().__init__(f"LLM feature is unavailable in rule-based test mode: {feature}")
        self.feature = feature


def _semantic_discovery(infos: Mapping[str, Any]) -> dict[str, Any]:
    metrics = [
        dict(item)
        for item in infos.get("available_metrics", []) or []
        if isinstance(item, Mapping)
    ]
    settlement = {
        (item.get("dimension"), item.get("concept_id"))
        for item in metrics
    }
    urban_service_metrics = [
        item
        for item in metrics
        if dict(item.get("qualifiers", {}) or {}).get("kind") == "urban_service"
    ]
    for load in urban_service_metrics:
        if load.get("dimension") != "load":
            continue
        capacity = next(
            (
                item
                for item in urban_service_metrics
                if item.get("dimension") == "capacity"
                and item.get("concept_id") == load.get("concept_id")
                and item.get("group_id") == load.get("group_id")
                and dict(item.get("qualifiers", {}) or {})
                == dict(load.get("qualifiers", {}) or {})
                and item.get("unit") == load.get("unit")
            ),
            None,
        )
        if capacity is not None:
            strain = dict(load)
            strain["dimension"] = "risk"
            strain["unit"] = "ratio"
            strain["_expression"] = {
                "op": "divide",
                "left": {
                    "op": "metric",
                    "dimension": "load",
                    "concept_id": str(load["concept_id"]),
                },
                "right": {
                    "op": "metric",
                    "dimension": "capacity",
                    "concept_id": str(capacity["concept_id"]),
                },
            }
            if load.get("group_id") is not None:
                strain["_expression"]["left"]["group_id"] = str(load["group_id"])
                strain["_expression"]["right"]["group_id"] = str(load["group_id"])
            if load.get("qualifiers"):
                strain["_expression"]["left"]["qualifiers"] = dict(load["qualifiers"])
                strain["_expression"]["right"]["qualifiers"] = dict(load["qualifiers"])
            metrics.append(strain)
    if not metrics or {
        ("load", "settlement"),
        ("capacity", "settlement"),
    }.issubset(settlement):
        return {
            "concepts": [
                {
                    "id": "settlement_density_pressure",
                    "label": "settlement density pressure",
                    "concept_kind": "derived_metric",
                },
                {
                    "id": "overcrowded_settlement",
                    "label": "overcrowded settlement",
                    "concept_kind": "condition",
                },
            ],
            "derived_metrics": [{
                "id": "settlement_density_pressure",
                "concept_id": "settlement_density_pressure",
                "dimension": "risk",
                "target_kind": "region",
                "expression": {
                    "op": "divide",
                    "left": {"op": "metric", "dimension": "load", "concept_id": "settlement"},
                    "right": {"op": "metric", "dimension": "capacity", "concept_id": "settlement"},
                },
                "unit": "ratio",
            }],
            "conditions": [{
                "id": "overcrowded_settlement",
                "concept_id": "overcrowded_settlement",
                "target_kind": "region",
                "metric_definition_id": "settlement_density_pressure",
                "activate_above": 0.85,
                "resolve_below": 0.75,
                "activate_after_months": 2,
                "resolve_after_months": 2,
            }],
            "mechanic_proposals": [],
        }

    injury_burden = next(
        (
            item
            for item in metrics
            if item.get("dimension") == "risk"
            and item.get("concept_id") == "injury_burden"
            and dict(item.get("qualifiers", {}) or {}).get("kind")
            == "collective_health"
            and item.get("unit") == "ratio"
        ),
        None,
    )
    healing_access = next(
        (
            item
            for item in urban_service_metrics
            if item.get("dimension") == "access"
            and item.get("concept_id") == "healing"
            and item.get("group_id") is None
            and item.get("unit") == "ratio"
        ),
        None,
    )
    if injury_burden is not None and healing_access is not None:
        return {
            "concepts": [
                {
                    "id": "health_recovery_strain",
                    "label": "health recovery strain",
                    "concept_kind": "derived_metric",
                },
                {
                    "id": "strained_health_recovery",
                    "label": "strained health recovery",
                    "concept_kind": "condition",
                },
            ],
            "derived_metrics": [{
                "id": "health_recovery_strain",
                "concept_id": "health_recovery_strain",
                "dimension": "risk",
                "target_kind": "region",
                "expression": {
                    "op": "clamp",
                    "min": 0.0,
                    "max": 1.0,
                    "value": {
                        "op": "multiply",
                        "left": {
                            "op": "metric",
                            "dimension": "risk",
                            "concept_id": "injury_burden",
                            "qualifiers": dict(injury_burden["qualifiers"]),
                        },
                        "right": {
                            "op": "subtract",
                            "left": {
                                "op": "constant",
                                "value": 1.0,
                                "unit": "ratio",
                            },
                            "right": {
                                "op": "metric",
                                "dimension": "access",
                                "concept_id": "healing",
                                "qualifiers": dict(healing_access["qualifiers"]),
                            },
                        },
                    },
                },
                "unit": "ratio",
            }],
            "conditions": [{
                "id": "strained_health_recovery",
                "concept_id": "strained_health_recovery",
                "target_kind": "region",
                "metric_definition_id": "health_recovery_strain",
                "activate_above": 0.20,
                "resolve_below": 0.05,
                "activate_after_months": 2,
                "resolve_after_months": 2,
            }],
            "mechanic_proposals": [],
        }

    for item in metrics:
        if item.get("dimension") not in {
            "access",
            "quality",
            "risk",
            "influence",
            "dependency",
        } or item.get("unit") != "ratio":
            continue
        concept_id = str(item.get("concept_id", "")).strip()
        if not concept_id:
            continue
        is_quality = item["dimension"] == "quality"
        group_id = item.get("group_id")
        is_urban_service = dict(item.get("qualifiers", {}) or {}).get("kind") == "urban_service"
        metric_stem = (
            f"observed_{concept_id}_{item['dimension']}_deficit"
            if is_urban_service and item["dimension"] == "access"
            else f"observed_{concept_id}_deficit"
            if is_quality
            else f"observed_{concept_id}_{item['dimension']}"
        )
        if group_id is not None:
            group_text = str(group_id).strip()
            group_slug = re.sub(r"[^a-z0-9]+", "_", group_text.lower()).strip("_") or "group"
            group_digest = hashlib.sha256(group_text.encode("utf-8")).hexdigest()[:10]
            metric_stem = f"{metric_stem}_group_{group_slug}_{group_digest}"
        metric_id = _fit_semantic_id(metric_stem, f"metric:{concept_id}:{item['dimension']}:{group_id}")
        condition_id = _fit_semantic_id(
            f"sustained_{metric_id.removeprefix('observed_')}",
            f"condition:{metric_id}",
        )
        expression = item.get("_expression") or {
            "op": "metric",
            "dimension": item["dimension"],
            "concept_id": concept_id,
        }
        if item.get("_expression") is None:
            if group_id is not None:
                expression["group_id"] = str(group_id)
            if item.get("qualifiers"):
                expression["qualifiers"] = dict(item["qualifiers"])
        if is_quality or (is_urban_service and item["dimension"] == "access"):
            expression = {
                "op": "subtract",
                "left": {"op": "constant", "value": 1.0, "unit": "ratio"},
                "right": expression,
            }
        return {
            "concepts": [
                {
                    "id": metric_id,
                    "label": metric_id.replace("_", " "),
                    "concept_kind": "derived_metric",
                },
                {
                    "id": condition_id,
                    "label": condition_id.replace("_", " "),
                    "concept_kind": "condition",
                },
            ],
            "derived_metrics": [{
                "id": metric_id,
                "concept_id": metric_id,
                "dimension": "risk" if is_quality or is_urban_service else item["dimension"],
                "target_kind": "region",
                "expression": expression,
                "unit": "ratio",
            }],
            "conditions": [{
                "id": condition_id,
                "concept_id": condition_id,
                "target_kind": "region",
                "metric_definition_id": metric_id,
                "activate_above": 0.75,
                "resolve_below": 0.6,
                "activate_after_months": 2,
                "resolve_after_months": 2,
            }],
            "mechanic_proposals": [],
        }

    return {
        "concepts": [],
        "derived_metrics": [],
        "conditions": [],
        "mechanic_proposals": [],
    }


def _fit_semantic_id(stem: str, discriminator: str) -> str:
    """Keep deterministic fallback IDs valid and distinct after truncation."""
    normalized = re.sub(r"[^a-z0-9_]+", "_", stem.lower()).strip("_")
    if len(normalized) <= 63:
        return normalized
    digest = hashlib.sha256(discriminator.encode("utf-8")).hexdigest()[:10]
    return f"{normalized[:52]}_{digest}"


def _action_decision(infos: Mapping[str, Any]) -> dict[str, Any]:
    avatar_name = str(infos.get("avatar_name", ""))
    return {
        avatar_name: {
            "action_name_params_pairs": [],
            "avatar_thinking": "",
            "short_term_objective": "",
            "current_emotion": "emotion_calm",
        }
    }


def _city_interpreter(infos: Mapping[str, Any]) -> dict[str, Any]:
    city = dict(infos.get("city", {}) or {})
    governance = dict(city.get("governance", {}) or {})
    try:
        administrative_capacity = float(governance.get("administrative_capacity", 0))
    except (TypeError, ValueError):
        administrative_capacity = 0.0
    project_kinds = {
        str(item)
        for item in infos.get("eligible_project_kinds", []) or []
        if str(item).strip()
    }
    if administrative_capacity > 0 and "settlement_capacity_expansion" in project_kinds:
        return {
            "decision": "urban_capacity_project",
            "reason": "Persistent settlement pressure can be answered by grounded urban expansion.",
            "action_intent": {
                "action_kind": "urban_capacity_project",
                "project_kind": "settlement_capacity_expansion",
            },
        }
    candidates = [
        dict(asset)
        for asset in infos.get("assets", []) or []
        if isinstance(asset, Mapping)
    ]
    eligible = {
        str(capability)
        for capability in infos.get("eligible_capability_ids", []) or []
        if str(capability).strip()
    }
    candidates = [
        asset
        for asset in candidates
        if eligible.intersection(str(item) for item in asset.get("capability_ids", []) or [])
    ]
    candidates.sort(key=lambda asset: (
        float(asset.get("effective_quality", 1.0)),
        str(asset.get("id", "")),
    ))
    if administrative_capacity > 0 and candidates:
        capability_ids = sorted({
            str(capability)
            for capability in candidates[0].get("capability_ids", []) or []
            if str(capability).strip() and str(capability) in eligible
        })
        if capability_ids:
            return {
                "decision": "urban_maintenance",
                "reason": "Administrative capacity can maintain the weakest grounded urban capability.",
                "action_intent": {
                    "action_kind": "urban_maintenance",
                    "capability_id": capability_ids[0],
                },
            }
    return {
        "decision": "maintain",
        "reason": "No grounded urban maintenance affordance is available.",
    }


def resolve_test_mode_task(task_name: str, infos: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, parser-safe result without loading prompts or networking."""
    if task_name == "action_decision":
        return _action_decision(infos)
    if task_name == "backstory":
        return {"backstory": ""}
    if task_name == "long_term_objective":
        return {"long_term_objective": ""}
    if task_name == "nickname":
        return {"nickname": "", "thinking": "", "reason": ""}
    if task_name == "story_teller":
        return {"story": ""}
    if task_name == "relation_resolver":
        return {"changed": False}
    if task_name == "relation_delta":
        return {"delta_a_to_b": 0, "delta_b_to_a": 0}
    if task_name == "single_choice":
        # The domain resolver turns an invalid choice into its configured legal fallback.
        return {"choice": "", "thinking": ""}
    if task_name == "sect_thinker":
        return {"sect_thinking": ""}
    if task_name == "event_appraisal":
        # No AI appraisals: every candidate falls back to its deterministic
        # per-candidate rule profile in event_appraisal_service.
        return {"appraisals": []}
    if task_name == "chronicle_chapter":
        events = list(infos.get("events", []))
        if not events:
            return {"title": "", "source_event_ids": [], "paragraphs": []}
        # Keep the rule-based chapter useful for the same read path as a
        # provider chapter: expose one factual event anchor so the Chronicle
        # dossier (and the existing Why query) can be exercised in test mode.
        first = next((item for item in events if item.get("is_major")), events[0])
        event_id = str(first["id"])
        return {
            "title": "World Chronicle",
            "source_event_ids": [event_id],
            "paragraphs": [{
                "source_event_ids": [event_id],
                "segments": [{
                    "text": str(first.get("content", "")),
                    "reference": {
                        "id": f"event-{event_id}",
                        "kind": "event",
                        "label": f"Event {event_id}",
                        "target_id": event_id,
                        "claim_kind": "fact",
                        "source_event_ids": [event_id],
                    },
                }],
            }],
        }
    if task_name == "live_guide_ask":
        facts = list(infos.get("facts", []))
        if not facts:
            return {"answer": "", "source_event_ids": []}
        fact = facts[-1]
        return {
            "answer": str(fact.get("content", "")),
            "source_event_ids": [str(fact.get("id", ""))],
        }
    if task_name == "dao_petition":
        initiator = dict(infos.get("initiator", {}) or {})
        cause = dict(infos.get("cause", {}) or {})
        tradition = str(infos.get("tradition", ""))
        return {
            "content": f"{initiator.get('name', 'An institution')} seeks a rare audience after sustained {tradition} rites: {cause.get('content', '')}",
        }
    if task_name == "semantic_discovery":
        return _semantic_discovery(infos)
    if task_name == "population_interpreter":
        origin = dict(infos.get("origin", {}) or {})
        try:
            origin_ratio = float(origin["ratio"])
        except (KeyError, TypeError, ValueError):
            origin_ratio = 1.0
        for candidate in infos.get("candidates", []) or []:
            try:
                has_capacity = float(candidate["capacity"]) > float(candidate["population"])
                lower_load = float(candidate["ratio"]) < origin_ratio
            except (KeyError, TypeError, ValueError):
                continue
            if lower_load and has_capacity:
                return {
                    "decision": "act",
                    "reason": "A lower-load city has available capacity.",
                    "action_intent": {
                        "action_kind": "population_transfer",
                        "preferences": ["lower_settlement_load", "available_capacity"],
                    },
                }
        return {
            "decision": "maintain",
            "reason": "No lower-load city with available capacity was found.",
        }
    if task_name == "economy_interpreter":
        destination = dict(infos.get("destination", {}) or {})
        for candidate in infos.get("candidates", []) or []:
            route = dict(candidate.get("route", {}) or {})
            if (
                route.get("available") is True
                and float(candidate.get("stock", 0)) > 0
                and float(candidate.get("source_access", 0)) > 0
                and float(destination.get("access", 0)) > 0
            ):
                return {
                    "decision": "act",
                    "reason": "A grounded route connects a stocked source to the shortage.",
                    "action_intent": {
                        "action_kind": "resource_transfer",
                        "preferences": ["available_supply", "higher_route_quality"],
                    },
                }
        return {
            "decision": "maintain",
            "reason": "No grounded route can carry the resource this month.",
        }
    if task_name == "city_interpreter":
        return _city_interpreter(infos)
    if task_name in {"sect_decider", "interaction_feedback", "fate_revelation", "random_minor_event"}:
        return {}
    if task_name.startswith("world_lore_"):
        raise TestModeLLMUnavailable("world_lore_rewrite")
    if task_name in {"custom_content_generation", "roleplay_conversation_turn", "roleplay_conversation_summary"}:
        raise TestModeLLMUnavailable(task_name)
    raise TestModeUnsupportedLLMTask(task_name)


def registered_test_mode_tasks() -> frozenset[str]:
    return frozenset({
        "action_decision", "backstory", "long_term_objective", "nickname", "story_teller",
        "relation_resolver", "relation_delta", "single_choice", "sect_thinker", "sect_decider",
        "interaction_feedback", "fate_revelation", "random_minor_event", "event_appraisal",
        "custom_content_generation", "roleplay_conversation_turn", "roleplay_conversation_summary", "chronicle_chapter",
        "live_guide_ask", "dao_petition", "semantic_discovery", "population_interpreter", "economy_interpreter", "city_interpreter",
    })
