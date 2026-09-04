"""Read-only projection of persistent world situations for player attention.

Situations are assembled from canonical domain owners.  They are not quests,
do not persist, and never become an input to the simulation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from src.classes.event import FactKind


SEVERITY_ORDER = {"critical": 3, "major": 2, "notable": 1}


def _unique(values: Iterable[str | None]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _event_month(world: Any, event_id: str | None) -> int:
    if not event_id:
        return -1
    event = world.event_manager.get_event_by_id(str(event_id))
    return int(event.month_stamp) if event is not None else -1


def _latest_event_id(world: Any, event_ids: Iterable[str | None]) -> str:
    candidates = _unique(event_ids)
    return max(candidates, key=lambda item: (_event_month(world, item), item), default="")


def _region(world: Any, region_id: str | int):
    try:
        return world.map.regions.get(int(region_id))
    except (TypeError, ValueError):
        return None


def _subject(world: Any, kind: str, subject_id: str | int) -> dict[str, str] | None:
    normalized_id = str(subject_id)
    if kind in {"region", "city"}:
        region = _region(world, normalized_id)
        if region is None:
            return None
        return {"kind": "region", "id": normalized_id, "name": str(region.name)}
    if kind == "avatar":
        avatar = world.avatar_manager.get_avatar(normalized_id)
        if avatar is None:
            return None
        return {"kind": "avatar", "id": normalized_id, "name": str(avatar.name)}
    if kind == "sect":
        sect = next(
            (
                item
                for item in getattr(world, "existed_sects", ()) or ()
                if str(getattr(item, "id", "")) == normalized_id
            ),
            None,
        )
        if sect is None:
            return None
        return {"kind": "sect", "id": normalized_id, "name": str(sect.name)}
    if kind == "infrastructure_site":
        site = world.map.infrastructure_sites.get(normalized_id)
        if site is None:
            return None
        return {"kind": "site", "id": normalized_id, "name": str(site.name)}
    return None


def _subjects(world: Any, refs: Iterable[tuple[str, str | int]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for kind, subject_id in refs:
        item = _subject(world, kind, subject_id)
        if item is None:
            continue
        key = (item["kind"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _age(current_month: int, started_month: int) -> int:
    return max(1, current_month - int(started_month) + 1)


def _severity(value: float, *, critical_at: float = 0.85, major_at: float = 0.6) -> str:
    if value >= critical_at:
        return "critical"
    if value >= major_at:
        return "major"
    return "notable"


def _latest_condition_response(world: Any, condition_ids: set[str]) -> dict[str, Any] | None:
    state = world.mechanical_language
    receipts = [
        receipt
        for receipt in state.reaction_receipts.values()
        if receipt.condition_instance_id in condition_ids and receipt.decision_event_ids
    ]
    decision_ids = _unique(
        event_id
        for receipt in receipts
        for event_id in receipt.decision_event_ids
    )
    events = [world.event_manager.get_event_by_id(event_id) for event_id in decision_ids]
    events = [
        event
        for event in events
        if event is not None and getattr(event, "fact_kind", None) is FactKind.DECISION
    ]
    if not events:
        return None
    event = max(events, key=lambda item: (int(item.month_stamp), item.created_at, item.id))
    payload = getattr(event, "causal_payload", None) or {}
    decision = payload.get("decision") or {}
    interpretation = payload.get("interpretation") or {}
    actor_kind = str(decision.get("subject_kind") or "")
    actor_id = str(decision.get("subject_id") or "")
    actor = _subject(world, actor_kind, actor_id)
    return {
        "event_id": str(event.id),
        "decision": str(interpretation.get("decision") or "maintain"),
        "reason": str(interpretation.get("reason") or decision.get("thinking") or ""),
        "actor": actor,
        "rejected": [
            {
                "action_name": str(item.get("action_name") or ""),
                "reason": str(item.get("reason") or ""),
            }
            for item in decision.get("rejected", ())
            if isinstance(item, dict)
        ],
    }


def _flood_situation(world: Any, current_month: int) -> dict[str, Any] | None:
    occurrences = list(world.regional_flood_state.active_by_region.values())
    if not occurrences:
        return None
    occurrences.sort(key=lambda item: (item.started_month, item.region_id))
    source_ids = _unique(
        source_id
        for occurrence in occurrences
        for source_id in (*occurrence.source_event_ids, occurrence.last_event_id)
    )
    affected_ids = {str(item.region_id) for item in occurrences}
    damaged_sites = [
        site
        for site in world.map.infrastructure_sites.values()
        if site.integrity < 1.0 and affected_ids.intersection(str(item) for item in site.region_ids)
    ]
    max_risk = max(float(item.activation_risk) for item in occurrences)
    started_month = min(item.started_month for item in occurrences)
    return {
        "id": "hazard:regional_flood",
        "kind": "hazard",
        "severity": _severity(max_risk),
        "status": "active",
        "started_month": started_month,
        "age_months": _age(current_month, started_month),
        "title_key": "flood_title",
        "title_params": {"count": len(occurrences)},
        "summary_key": "flood_summary",
        "summary_params": {
            "count": len(occurrences),
            "age": _age(current_month, started_month),
            "risk": round(max_risk * 100),
            "damaged": len(damaged_sites),
        },
        "primary_event_id": _latest_event_id(
            world, (item.last_event_id for item in occurrences)
        ),
        "source_event_ids": source_ids,
        "subjects": _subjects(
            world, (("region", item.region_id) for item in occurrences)
        ),
        "direct_action": None,
        "latest_response": None,
        "_score": max_risk,
    }


def _condition_situations(world: Any, current_month: int) -> list[dict[str, Any]]:
    active = [
        item
        for item in world.mechanical_language.condition_instances.values()
        if item.is_active(current_month)
    ]
    groups: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for item in active:
        groups[(item.definition_id, item.target_kind)].append(item)

    result: list[dict[str, Any]] = []
    for (definition_id, target_kind), items in sorted(groups.items()):
        items.sort(key=lambda item: (item.started_month, item.target_id, item.id))
        intensity = max(float(item.intensity) for item in items)
        started_month = min(item.started_month for item in items)
        source_ids = _unique(item.cause_event_id for item in items)
        result.append(
            {
                "id": f"condition:{target_kind}:{definition_id}",
                "kind": "condition",
                "severity": _severity(intensity),
                "status": "active",
                "started_month": started_month,
                "age_months": _age(current_month, started_month),
                "title": str(items[0].label) if len(items) == 1 else "",
                "title_key": "condition_group_title" if len(items) > 1 else "condition_title",
                "title_params": {"label": str(items[0].label), "count": len(items)},
                "summary_key": "condition_summary",
                "summary_params": {
                    "count": len(items),
                    "age": _age(current_month, started_month),
                    "intensity": round(intensity * 100),
                },
                "primary_event_id": _latest_event_id(world, source_ids),
                "source_event_ids": source_ids,
                "subjects": _subjects(
                    world, ((item.target_kind, item.target_id) for item in items)
                ),
                "direct_action": None,
                "latest_response": _latest_condition_response(
                    world, {str(item.id) for item in items}
                ),
                "_score": intensity,
            }
        )
    return result


def _project_situations(world: Any, current_month: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for region in sorted(world.map.regions.values(), key=lambda item: int(item.id)):
        city_state = getattr(region, "city_state", None)
        if city_state is None:
            continue
        for project in city_state.capacity_projects:
            if project.status.value == "completed":
                continue
            source_ids = _unique((*project.motivation_event_ids, project.last_event_id))
            progress = round(100 * project.completed_months / project.required_months)
            result.append(
                {
                    "id": f"project:{region.id}:{project.id}",
                    "kind": "project",
                    "severity": "major" if project.status.value == "stalled" else "notable",
                    "status": project.status.value,
                    "started_month": project.started_month,
                    "age_months": _age(current_month, project.started_month),
                    "title_key": "project_title",
                    "title_params": {"region": str(region.name)},
                    "summary_key": "project_summary",
                    "summary_params": {
                        "progress": progress,
                        "completed": project.completed_months,
                        "required": project.required_months,
                    },
                    "primary_event_id": project.last_event_id,
                    "source_event_ids": source_ids,
                    "subjects": _subjects(world, (("region", region.id),)),
                    "direct_action": None,
                    "latest_response": None,
                    "_score": 0.65 if project.status.value == "stalled" else 0.35,
                }
            )
    return result


def _infrastructure_situations(world: Any, current_month: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if site.integrity >= 1.0 and site.enabled:
            continue
        severity = _severity(1.0 - float(site.integrity), critical_at=0.65, major_at=0.25)
        source_month = _event_month(world, site.last_event_id)
        started_month = source_month if source_month >= 0 else current_month
        subject_refs = [("infrastructure_site", site.id)]
        subject_refs.extend(("region", region_id) for region_id in site.region_ids)
        result.append(
            {
                "id": f"infrastructure:{site.id}",
                "kind": "infrastructure",
                "severity": severity,
                "status": site.status,
                "started_month": started_month,
                "age_months": _age(current_month, started_month),
                "title_key": "infrastructure_title",
                "title_params": {"site": str(site.name)},
                "summary_key": "infrastructure_summary",
                "summary_params": {
                    "integrity": round(float(site.integrity) * 100),
                    "routes": len(site.route_ids),
                },
                "primary_event_id": str(site.last_event_id or ""),
                "source_event_ids": _unique((site.last_event_id,)),
                "subjects": _subjects(world, subject_refs),
                "direct_action": None,
                "latest_response": None,
                "_score": 1.0 - float(site.integrity),
            }
        )
    return result


def _imperial_crisis_situation(world: Any, current_month: int) -> dict[str, Any] | None:
    dynasty = getattr(world, "dynasty", None)
    crisis = getattr(dynasty, "imperial_crisis", None)
    if crisis is None or crisis.status != "active":
        return None
    claims = [claim for claim in crisis.claims if claim.status == "active"]
    source_ids = _unique(
        event_id for claim in crisis.claims for event_id in claim.evidence_event_ids
    )
    return {
        "id": "crisis:imperial",
        "kind": "crisis",
        "severity": "critical" if crisis.kind == "succession" else "major",
        "status": crisis.kind,
        "started_month": crisis.opened_month,
        "age_months": _age(current_month, crisis.opened_month),
        "title_key": "imperial_crisis_title",
        "title_params": {},
        "summary_key": "imperial_crisis_summary",
        "summary_params": {
            "claims": len(claims),
            "age": _age(current_month, crisis.opened_month),
        },
        "primary_event_id": _latest_event_id(world, source_ids),
        "source_event_ids": source_ids,
        "subjects": _subjects(
            world, (("avatar", claim.candidate_id) for claim in claims)
        ),
        "direct_action": None,
        "latest_response": None,
        "_score": 1.0 if crisis.kind == "succession" else 0.75,
    }


def _petition_situations(world: Any, current_month: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for petition in getattr(world, "dao_petitions", ()) or ():
        if petition.status.value != "pending":
            continue
        source_ids = _unique((*petition.motivated_event_ids, *petition.rite_event_ids))
        subjects = _subjects(world, (("region", petition.region_id),))
        initiator = _subject(world, petition.initiator_kind, petition.initiator_id)
        if initiator is not None:
            subjects.insert(0, initiator)
        result.append(
            {
                "id": f"petition:{petition.id}",
                "kind": "petition",
                "severity": "major",
                "status": "pending",
                "started_month": petition.created_month,
                "age_months": _age(current_month, petition.created_month),
                "title_key": "petition_title",
                "title_params": {
                    "initiator": initiator["name"] if initiator is not None else petition.initiator_kind
                },
                "summary": str(petition.content),
                "summary_key": "petition_summary",
                "summary_params": {"age": _age(current_month, petition.created_month)},
                "primary_event_id": _latest_event_id(world, source_ids),
                "source_event_ids": source_ids,
                "subjects": subjects,
                "direct_action": "dao_petition",
                "latest_response": None,
                "_score": 0.9,
            }
        )
    return result


def build_world_situations(world: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    """Return the current attention queue without persisting presentation state."""
    current_month = int(world.month_stamp)
    result: list[dict[str, Any]] = []
    flood = _flood_situation(world, current_month)
    if flood is not None:
        result.append(flood)
    result.extend(_condition_situations(world, current_month))
    result.extend(_project_situations(world, current_month))
    result.extend(_infrastructure_situations(world, current_month))
    crisis = _imperial_crisis_situation(world, current_month)
    if crisis is not None:
        result.append(crisis)
    result.extend(_petition_situations(world, current_month))
    result.sort(
        key=lambda item: (
            -SEVERITY_ORDER[item["severity"]],
            -int(item["direct_action"] is not None),
            -float(item["_score"]),
            int(item["started_month"]),
            item["id"],
        )
    )
    for item in result:
        item.pop("_score", None)
    return result[:limit]


__all__ = ["build_world_situations"]
