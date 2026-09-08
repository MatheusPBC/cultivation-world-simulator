from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.systems.institutional_diplomacy import get_sect_diplomacy_state

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


def _build_court_crisis_context(avatar: "Avatar") -> dict:
    """Expose a public legitimacy crisis to its contenders and court officials.

    This is observation-only prompt material.  Eligibility and any resulting
    action remain validated by the imperial crisis service.
    """
    from src.classes.official_rank import OFFICIAL_NONE

    world = avatar.world
    dynasty = getattr(world, "dynasty", None)
    crisis = getattr(dynasty, "imperial_crisis", None)
    if crisis is None or str(getattr(crisis, "status", "")) != "active":
        return {"active_imperial_crisis": None}

    avatar_id = str(getattr(avatar, "id", ""))
    contender_ids = {
        str(value)
        for value in (
            crisis.incumbent_id,
            *(claim.candidate_id for claim in crisis.claims),
        )
        if value is not None
    }
    is_official = str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE) != OFFICIAL_NONE
    if not is_official and avatar_id not in contender_ids:
        return {"active_imperial_crisis": None}

    get_avatar = world.avatar_manager.get_avatar
    incumbent = get_avatar(str(crisis.incumbent_id)) if crisis.incumbent_id else None
    claims = []
    for claim in crisis.claims:
        candidate = get_avatar(str(claim.candidate_id))
        claims.append(
            {
                "candidate_id": str(claim.candidate_id),
                "candidate_name": str(getattr(candidate, "name", "") or ""),
                "status": str(claim.status),
                "positions": dict(claim.political_positions),
            }
        )
    role = "court_official"
    if avatar_id == str(crisis.incumbent_id):
        role = "incumbent"
    elif avatar_id in {str(claim.candidate_id) for claim in crisis.claims}:
        role = "candidate"
    return {
        "active_imperial_crisis": {
            "role": role,
            "kind": str(crisis.kind),
            "incumbent": (
                {
                    "id": str(crisis.incumbent_id),
                    "name": str(getattr(incumbent, "name", "") or ""),
                }
                if crisis.incumbent_id
                else None
            ),
            "claims": claims,
            "opened_month": int(getattr(crisis, "opened_month", 0) or 0),
        }
    }


def build_avatar_prompt_context(
    avatar: "Avatar",
    co_region_avatars: Optional[list["Avatar"]] = None,
) -> dict:
    """Build the focused LLM prompt context for avatar decisions."""
    from src.classes.core.avatar.info_presenter import (
        _get_goldfinger_structured_payload,
        _get_race_behavior_desc,
        _get_race_info,
        _get_world_secret_knowledge_payload,
    )
    from src.i18n import t
    from src.systems.cultivation_display import build_avatar_cultivation_display
    from src.systems.opportunity import get_opportunity_context_text

    world = avatar.world
    current_month = int(getattr(world, "month_stamp", 0))
    region = avatar.tile.region if avatar.tile is not None else None
    from src.systems.celestial_dao_service import (
        get_dao_context,
        get_sponsor_institution_memory,
    )
    observed = []
    for other in (co_region_avatars or [])[:8]:
        observed.append(
            {
                "id": str(getattr(other, "id", "")),
                "name": str(getattr(other, "name", "") or ""),
                "realm": str(getattr(getattr(other, "cultivation_progress", None), "get_info", lambda: "")()),
                "sect": str(getattr(getattr(other, "sect", None), "name", "") or t("Rogue Cultivator")),
            }
        )

    major_events = world.event_manager.get_major_events_by_avatar(avatar.id, limit=4)
    minor_events = world.event_manager.get_minor_events_by_avatar(avatar.id, limit=4)

    sect_context = {
        "has_sect": False,
        "sect_name": "",
        "sect_rank": "",
        "sect_alignment": "",
        "sect_rule_desc": "",
        "sect_is_at_war": False,
        "active_wars": [],
        "hostile_sects_summary": "",
        "can_seek_support_from_sect": False,
    }
    if avatar.sect is not None:
        world_sect_context = getattr(world, "sect_context", None)
        active_sects = world_sect_context.get_active_sects() if world_sect_context is not None else []
        active_wars = []
        hostile_names = []
        for other in active_sects:
            if other is None or int(getattr(other, "id", 0)) == int(getattr(avatar.sect, "id", 0)):
                continue
            state = get_sect_diplomacy_state(
                world,
                int(avatar.sect.id),
                int(other.id),
                current_month=current_month,
            )
            if str(state.get("status", "peace") or "peace") != "war":
                continue
            hostile_names.append(str(getattr(other, "name", "") or ""))
            active_wars.append(
                {
                    "other_sect_id": int(other.id),
                    "other_sect_name": str(getattr(other, "name", "") or ""),
                    "war_months": int(state.get("war_months", 0) or 0),
                    "war_reason": str(state.get("reason", "") or ""),
                }
            )
        sect_context = {
            "has_sect": True,
            "sect_name": avatar.sect.name,
            "sect_rank": avatar.get_sect_rank_name(),
            "sect_alignment": str(avatar.sect.alignment),
            "sect_rule_desc": str(getattr(avatar.sect, "rule_desc", "") or ""),
            "sect_is_at_war": bool(active_wars),
            "active_wars": active_wars,
            "hostile_sects_summary": "、".join(hostile_names[:4]),
            "can_seek_support_from_sect": bool(active_wars),
        }

    return {
        "self_profile": {
            "name": avatar.name,
            "race": _get_race_info(avatar, detailed=True),
            "race_behavior_priority": _get_race_behavior_desc(avatar),
            "realm": avatar.cultivation_progress.get_info(),
            "cultivation": build_avatar_cultivation_display(avatar),
            "hp": {"cur": avatar.hp.cur, "max": avatar.hp.max},
            "magic_stone": int(getattr(getattr(avatar, "magic_stone", None), "value", 0)),
            "current_action": avatar.current_action_name,
            "emotion": t(avatar.emotion.value),
            "long_term_objective": avatar.long_term_objective.content if avatar.long_term_objective else "",
            "short_term_objective": avatar.short_term_objective,
            "individual_consequences": avatar.individual_consequences.to_dict(),
            "derived_priority": avatar.individual_consequences.derived_priority,
            "goldfinger": _get_goldfinger_structured_payload(avatar),
            "active_opportunity": get_opportunity_context_text(avatar),
            "world_secret_knowledge": _get_world_secret_knowledge_payload(avatar),
        },
        "sect_context": sect_context,
        "court_context": _build_court_crisis_context(avatar),
        "local_world": {
            "region": region.get_info() if region is not None else t("None"),
            "nearby_avatars": observed,
            "celestial_dao": get_dao_context(world, region_id=getattr(region, "id", None), initiator_id=str(avatar.id)),
            # Only an avatar who may currently speak for its institution sees
            # that institution's own bounded memory; an ordinary member gets
            # nothing, and nothing about other institutions is projected here.
            "own_institution_memory": get_sponsor_institution_memory(world, avatar),
        },
        "recent_memory": {
            "major_events": [str(getattr(ev, "content", "")) for ev in major_events],
            "recent_events": [str(getattr(ev, "content", "")) for ev in minor_events],
        },
        "decision_hints": {
            "should_prioritize_safety": avatar.hp.cur < max(1, avatar.hp.max // 2),
            "restricted_actions": (
                ["Attack", "Assassinate", "Spar", "MutualAttack", "Occupy", "DriveAway", "SectMission", "DigGrave", "TakeTreasure"]
                if avatar.individual_consequences.active_injury else []
            ),
            "should_prioritize_sect_duty": bool(sect_context["sect_is_at_war"]),
            "can_seek_support_from_sect": bool(sect_context["can_seek_support_from_sect"]),
        },
    }
