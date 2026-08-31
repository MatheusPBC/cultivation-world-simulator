from __future__ import annotations

from typing import Any, Dict, List

from src.classes.official_rank import (
    OFFICIAL_NONE,
    OFFICIAL_ORDER,
    get_official_rank_name,
)
from src.server.assemblers.dynasty_overview import build_dynasty_overview
from src.systems.cultivation import REALM_RANK


def _build_empty_dynasty_detail() -> Dict[str, Any]:
    return {
        "overview": build_dynasty_overview(None),
        "summary": {
            "official_count": 0,
            "top_official_rank_name": "",
        },
        "officials": [],
        "imperial_crisis": None,
    }


def _get_avatar_realm_rank(avatar: Any) -> int:
    cultivation_progress = getattr(avatar, "cultivation_progress", None)
    realm = getattr(cultivation_progress, "realm", None)
    return int(REALM_RANK.get(realm, 0))


def _build_dynasty_officials(world: Any) -> List[Dict[str, Any]]:
    avatar_manager = getattr(world, "avatar_manager", None)
    if avatar_manager is None:
        return []

    officials: List[Any] = []
    for avatar in avatar_manager.get_living_avatars():
        rank_key = str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE)
        if rank_key == OFFICIAL_NONE:
            continue
        officials.append(avatar)

    rank_order_map = {key: idx for idx, key in enumerate(OFFICIAL_ORDER)}
    officials.sort(
        key=lambda avatar: (
            -rank_order_map.get(
                str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE),
                0,
            ),
            -int(getattr(avatar, "court_reputation", 0) or 0),
            -_get_avatar_realm_rank(avatar),
            str(getattr(avatar, "name", "") or ""),
            str(getattr(avatar, "id", "") or ""),
        )
    )

    result: List[Dict[str, Any]] = []
    for avatar in officials:
        rank_key = str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE)
        cultivation_progress = getattr(avatar, "cultivation_progress", None)
        result.append(
            {
                "id": str(getattr(avatar, "id", "") or ""),
                "name": str(getattr(avatar, "name", "") or ""),
                "realm": str(
                    getattr(cultivation_progress, "get_info", lambda: "")() or ""
                ),
                "official_rank_key": rank_key,
                "official_rank_name": get_official_rank_name(rank_key),
                "court_reputation": int(getattr(avatar, "court_reputation", 0) or 0),
                "sect_name": str(
                    getattr(getattr(avatar, "sect", None), "name", "") or ""
                ),
            }
        )
    return result


def build_dynasty_detail(world: Any) -> Dict[str, Any]:
    if world is None:
        return _build_empty_dynasty_detail()
    if getattr(world, "dynasty", None) is None:
        return _build_empty_dynasty_detail()

    overview = build_dynasty_overview(world)
    officials = _build_dynasty_officials(world)
    top_official_rank_name = (
        str(officials[0].get("official_rank_name", "") or "") if officials else ""
    )
    crisis = getattr(world.dynasty, "imperial_crisis", None)
    crisis_data = None
    if crisis is not None:
        get_avatar = world.avatar_manager.get_avatar
        emperor = get_avatar(str(crisis.emperor_avatar_id))
        claimant = get_avatar(str(crisis.claimant_avatar_id))
        supporters = []
        for supporter_id in getattr(crisis, "support_avatar_ids", []) or []:
            supporter = get_avatar(str(supporter_id))
            if supporter is None:
                continue
            supporters.append(
                {
                    "id": str(getattr(supporter, "id", "") or ""),
                    "name": str(getattr(supporter, "name", "") or ""),
                }
            )
        crisis_data = {
            "status": str(crisis.status),
            "opened_month": int(crisis.opened_month),
            "emperor": {"id": str(crisis.emperor_avatar_id), "name": str(getattr(emperor, "name", "") or "")},
            "claimant": {"id": str(crisis.claimant_avatar_id), "name": str(getattr(claimant, "name", "") or "")},
            "support_count": len(getattr(crisis, "support_avatar_ids", []) or []),
            "supporters": supporters,
            "evidence_event_ids": list(getattr(crisis, "evidence_event_ids", []) or []),
            "legitimacy_factors": dict(getattr(crisis, "legitimacy_factors", {}) or {}),
        }

    return {
        "overview": overview,
        "summary": {
            "official_count": len(officials),
            "top_official_rank_name": top_official_rank_name,
        },
        "officials": officials,
        "imperial_crisis": crisis_data,
    }
