"""Causal rites, contested claims, and rare audiences with the Celestial Dao."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.celestial_dao import DaoPetition, DaoPetitionStatus, DaoTradition
from src.classes.event import Event, FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.systems.sect_decision_context import find_living_patriarch
from src.systems.semantic_world.context import region_semantic_relevance
from src.utils.llm import call_llm_with_task_name
from src.utils.llm.exceptions import LLMError, ProviderCallError

DAO_PETITION_TASK_NAME = "dao_petition"
DAO_PETITION_TEMPLATE_FILENAME = "dao_petition.txt"
DAO_PETITION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["content"],
    "properties": {"content": {"type": "string"}},
}
RITE_WINDOW_MONTHS = 12
RITES_REQUIRED_FOR_AUDIENCE = 3
AUDIENCE_COOLDOWN_MONTHS = 12


class DaoPetitionDraftError(ValueError):
    """The rare-audience narration was missing or unusable."""


def assign_region_traditions(world: Any) -> None:
    traditions = tuple(DaoTradition)
    for region in world.map.regions.values():
        digest = hashlib.sha256(f"{world.playthrough_id}:{region.id}".encode()).digest()
        region.dao_tradition = traditions[digest[0] % len(traditions)]


def interpret_sign(tradition: DaoTradition, sign: str) -> str:
    readings = {
        DaoTradition.MANDATE_AND_ORDER: "a call to restore rightful order",
        DaoTradition.BALANCE: "a warning against excess and imbalance",
        DaoTradition.MERCY: "a charge to protect those bearing the cost",
        DaoTradition.TRANSCENDENCE: "a reminder that worldly claims are temporary",
    }
    return t("{sign}: {reading}", sign=sign, reading=t(readings[tradition]))


def _recent_rite_events(
    world: Any, *, current_events: list[Event] | None = None
) -> list[Event]:
    current_month = int(world.month_stamp)
    stored = world.event_manager.get_events_between_months(
        current_month - RITE_WINDOW_MONTHS + 1, current_month
    )
    return [
        event
        for event in [*stored, *(current_events or [])]
        if str(getattr(event, "event_type", "")) == "dao_rite"
    ]


def get_dao_context(
    world: Any, *, region_id: int | None = None, initiator_id: str | None = None
) -> list[dict[str, Any]]:
    """Actual answers and explicitly unconfirmed public claims, never commands."""
    current_month = int(world.month_stamp)
    observer_region = (
        (getattr(getattr(world, "map", None), "regions", {}) or {}).get(int(region_id))
        if region_id is not None
        else None
    )
    observer_tradition = getattr(observer_region, "dao_tradition", None)
    context: list[dict[str, Any]] = []
    for petition in getattr(world, "dao_petitions", []):
        if petition.status == DaoPetitionStatus.SIGNED:
            reading_tradition = observer_tradition or petition.tradition
            context.append(
                {
                    "kind": "omen",
                    "tradition": reading_tradition.value,
                    "source_tradition": petition.tradition.value,
                    "interpretation": interpret_sign(
                        reading_tradition, t("A public omen")
                    ),
                    "initiator_id": str(petition.initiator_id),
                    "source_event_id": petition.response_event_id,
                    "target_avatar_id": petition.target_avatar_id,
                    "target_evidence_event_ids": list(petition.target_evidence_event_ids),
                }
            )
        elif (
            petition.status == DaoPetitionStatus.FAVORED
            and petition.favor_expires_month
            and current_month <= petition.favor_expires_month
        ):
            if region_id is not None and petition.region_id != int(region_id):
                continue
            if initiator_id is None or petition.initiator_id == str(initiator_id):
                context.append(
                    {
                        "kind": "limited_favor",
                        "tradition": petition.tradition.value,
                        "initiator_id": str(petition.initiator_id),
                        "expires_month": petition.favor_expires_month,
                        "source_event_id": petition.response_event_id,
                        "target_avatar_id": petition.target_avatar_id,
                        "target_evidence_event_ids": list(petition.target_evidence_event_ids),
                    }
                )
    for rite in _recent_rite_events(world)[-6:]:
        claim = dict(
            (getattr(rite, "causal_payload", {}) or {}).get("dao_rite", {}) or {}
        )
        if region_id is not None and claim.get("region_id") != int(region_id):
            continue
        context.append(
            {
                "kind": "unconfirmed_rite",
                "tradition": claim.get("tradition", ""),
                "initiator_id": str(claim.get("initiator_id", "")),
                "source_event_id": rite.id,
                "interpretation": t(
                    "A mortal rite claims the Dao favors its cause; this is not a Dao response."
                ),
                "claim": str(getattr(rite, "content", "")),
            }
        )
    return context


def create_petition(
    world: Any,
    *,
    initiator_kind: str,
    initiator_id: str,
    region_id: int,
    motivated_event_ids: list[str],
    rite_event_ids: list[str] | None = None,
    content: str = "",
) -> DaoPetition:
    resolved_target, resolved_evidence = _resolve_imperial_target(
        world,
        motivated_event_ids,
    )
    return _append_petition(
        world,
        initiator_kind=initiator_kind,
        initiator_id=initiator_id,
        region_id=region_id,
        motivated_event_ids=motivated_event_ids,
        rite_event_ids=rite_event_ids,
        content=content,
        target_avatar_id=resolved_target,
        target_evidence_event_ids=resolved_evidence,
    )


def _append_petition(
    world: Any,
    *,
    initiator_kind: str,
    initiator_id: str,
    region_id: int,
    motivated_event_ids: list[str],
    rite_event_ids: list[str] | None,
    content: str,
    target_avatar_id: str | None,
    target_evidence_event_ids: list[str],
) -> DaoPetition:
    """Append a petition after its target was resolved by this module."""
    if initiator_kind not in {"sect", "court"}:
        raise ValueError(
            t(
                "Only a sect patriarch or the imperial court may seek a Celestial Audience"
            )
        )
    if any(p.status == DaoPetitionStatus.PENDING for p in world.dao_petitions):
        raise ValueError(t("A Celestial Audience is already awaiting an answer"))
    region = world.map.regions[int(region_id)]
    petition = DaoPetition(
        initiator_kind=initiator_kind,
        initiator_id=str(initiator_id),
        region_id=int(region_id),
        tradition=region.dao_tradition,
        motivated_event_ids=list(motivated_event_ids),
        rite_event_ids=list(rite_event_ids or []),
        content=content or t("An institution seeks a rare Celestial Audience."),
        created_month=int(world.month_stamp),
        target_avatar_id=target_avatar_id,
        target_evidence_event_ids=list(target_evidence_event_ids),
    )
    world.dao_petitions.append(petition)
    return petition


def _resolve_imperial_target(
    world: Any,
    event_ids: list[str],
) -> tuple[str | None, list[str]]:
    """Resolve a crisis target only from an unambiguous source fact.

    A fact related to both contenders, to neither contender, or to different
    contenders is intentionally ambiguous.  It remains usable as public Dao
    context but cannot become imperial legitimacy evidence.
    """
    crisis = getattr(getattr(world, "dynasty", None), "imperial_crisis", None)
    if crisis is None:
        return None, []
    events: list[Event] = []
    for event_id in event_ids:
        event = world.event_manager.get_event_by_id(str(event_id))
        if event is None:
            return None, []
        events.append(event)
    return _resolve_imperial_target_from_events(world, events)


def _resolve_imperial_target_from_events(
    world: Any,
    events: list[Event],
) -> tuple[str | None, list[str]]:
    crisis = getattr(getattr(world, "dynasty", None), "imperial_crisis", None)
    if crisis is None:
        return None, []
    contender_ids = {
        str(crisis.emperor_avatar_id),
        str(crisis.claimant_avatar_id),
    }
    targets: set[str] = set()
    evidence_ids: list[str] = []
    for event in events:
        related_ids = {
            str(avatar_id) for avatar_id in getattr(event, "related_avatars", None) or []
        }
        matched = related_ids & contender_ids
        if len(matched) != 1:
            return None, []
        targets.update(matched)
        evidence_ids.append(str(event.id))
    if len(targets) != 1:
        return None, []
    return next(iter(targets)), list(dict.fromkeys(evidence_ids))


def _create_petition_from_events(
    world: Any,
    *,
    initiator_kind: str,
    initiator_id: str,
    region_id: int,
    motivated_event_ids: list[str],
    rite_event_ids: list[str],
    content: str,
    source_events: list[Event],
) -> DaoPetition:
    """Create a petition whose source events are still in the current step."""
    target_avatar_id, target_evidence_event_ids = _resolve_imperial_target_from_events(
        world, source_events
    )
    return _append_petition(
        world,
        initiator_kind=initiator_kind,
        initiator_id=initiator_id,
        region_id=region_id,
        motivated_event_ids=motivated_event_ids,
        rite_event_ids=rite_event_ids,
        content=content,
        target_avatar_id=target_avatar_id,
        target_evidence_event_ids=target_evidence_event_ids,
    )


def _region_for_avatar(avatar: Any) -> Any | None:
    return getattr(getattr(avatar, "tile", None), "region", None)


def _institution_candidates(
    world: Any, cause: Event
) -> list[tuple[str, str, str, Any]]:
    candidates: list[tuple[str, str, str, Any]] = []
    related_avatar_ids = {
        str(item) for item in getattr(cause, "related_avatars", None) or []
    }
    dynasty = getattr(world, "dynasty", None)
    emperor = (
        world.avatar_manager.get_avatar(
            str(getattr(dynasty, "current_emperor_id", "") or "")
        )
        if dynasty
        else None
    )
    crisis = getattr(dynasty, "imperial_crisis", None) if dynasty else None
    court_ids = {str(getattr(emperor, "id", "") or "")}
    if crisis is not None:
        court_ids.add(str(getattr(crisis, "claimant_avatar_id", "") or ""))
    court_region = _region_for_avatar(emperor)
    if (
        dynasty is not None
        and court_region is not None
        and related_avatar_ids & court_ids
    ):
        candidates.append(
            (
                "court",
                str(dynasty.id),
                str(getattr(dynasty, "title", "") or getattr(dynasty, "name", "")),
                court_region,
            )
        )
    sects_by_id = {
        int(getattr(sect, "id", 0)): sect
        for sect in getattr(world, "existed_sects", []) or []
    }
    for sect_id in getattr(cause, "related_sects", None) or []:
        sect = sects_by_id.get(int(sect_id))
        patriarch = find_living_patriarch(sect) if sect is not None else None
        region = _region_for_avatar(patriarch)
        if sect is not None and patriarch is not None and region is not None:
            candidates.append(
                ("sect", str(sect.id), str(getattr(sect, "name", "")), region)
            )
    return candidates


def _rite_matches(event: Event, initiator_kind: str, initiator_id: str) -> bool:
    payload = dict(
        (getattr(event, "causal_payload", {}) or {}).get("dao_rite", {}) or {}
    )
    return (
        str(payload.get("initiator_kind", "")) == initiator_kind
        and str(payload.get("initiator_id", "")) == initiator_id
    )


def _is_institutional_rite(event: Event) -> bool:
    payload = dict(
        (getattr(event, "causal_payload", {}) or {}).get("dao_rite", {}) or {}
    )
    return (
        str(payload.get("initiator_kind", "")) in {"sect", "court"}
        and not bool(payload.get("is_popular", False))
    )


def _build_rite(
    world: Any, cause: Event, candidate: tuple[str, str, str, Any]
) -> Event:
    initiator_kind, initiator_id, initiator_name, region = candidate
    rite = Event(
        world.month_stamp,
        t(
            "{institution} holds a public rite and claims the Dao witnesses its cause: {cause}",
            institution=initiator_name,
            cause=cause.content,
        ),
        related_sects=[int(initiator_id)] if initiator_kind == "sect" else None,
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        event_type="dao_rite",
        causal_payload={
            "dao_rite": {
                "initiator_kind": initiator_kind,
                "initiator_id": initiator_id,
                "region_id": int(region.id),
                "tradition": region.dao_tradition.value,
                "is_confirmed": False,
            }
        },
    )
    rite.causal_links = [
        CausalLink(
            event_id=rite.id,
            cause_event_id=cause.id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    ]
    return rite


def _build_popular_rite(world: Any, cause: Event | None, region: Any) -> Event:
    source_id = cause.id if cause is not None else None
    rite = Event(
        world.month_stamp,
        t("People in {region} hold a popular rite and claim it answers local pressure.", region=region.name),
        related_sects=None,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        event_type="dao_rite",
        causal_payload={"dao_rite": {"initiator_kind": "people", "initiator_id": str(region.id), "region_id": int(region.id), "tradition": region.dao_tradition.value, "is_confirmed": False, "is_popular": True}},
    )
    if source_id:
        rite.causal_links = [CausalLink(event_id=rite.id, cause_event_id=source_id, relation=CausalRelation.MOTIVATED_BY)]
    return rite


def _popular_rite_regions(world: Any) -> list[tuple[Any, Event | None]]:
    regions = []
    events = sorted(
        [event for event in getattr(world.event_manager, "get_events_between_months", lambda *_: [])(int(world.month_stamp), int(world.month_stamp)) if getattr(event, "is_major", False)],
        key=lambda event: (str(event.id), str(event.content)),
    )
    for region in sorted(getattr(getattr(world, "map", None), "regions", {}).values(), key=lambda item: int(getattr(item, "id", 0))):
        if region_semantic_relevance(world, region) >= 0.60 or any(region.id in (getattr(event, "related_regions", []) or []) for event in events):
            regions.append((region, events[0] if events else None))
    return regions


def _can_open_audience(world: Any) -> bool:
    month = int(world.month_stamp)
    return not any(
        month - int(p.created_month) < AUDIENCE_COOLDOWN_MONTHS
        for p in world.dao_petitions
    )


def _fallback_petition_content(
    initiator_name: str, tradition: DaoTradition, cause: Event
) -> str:
    return t(
        "After sustained {tradition} rites, {institution} seeks a rare audience concerning: {cause}",
        tradition=tradition.value,
        institution=initiator_name,
        cause=cause.content,
    )


async def _render_petition_content(
    world: Any,
    *,
    initiator_kind: str,
    initiator_id: str,
    initiator_name: str,
    tradition: DaoTradition,
    cause: Event,
    rite_count: int,
) -> str:
    locale = (
        str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", ""))
        or None
    )
    template = resolve_locale_template_path(
        DAO_PETITION_TEMPLATE_FILENAME, current_locale=locale
    )
    infos = {
        "initiator": {
            "kind": initiator_kind,
            "id": initiator_id,
            "name": initiator_name,
        },
        "tradition": tradition.value,
        "cause": {
            "id": str(cause.id),
            "content": str(cause.content),
            "month_stamp": int(cause.month_stamp),
        },
        "rite_count": rite_count,
    }
    try:
        draft = await call_llm_with_task_name(
            DAO_PETITION_TASK_NAME, template, infos, output_schema=DAO_PETITION_SCHEMA
        )
        content = (
            str(draft.get("content", "")).strip() if isinstance(draft, Mapping) else ""
        )
        if not content or len(content) > 600:
            raise DaoPetitionDraftError("Celestial Audience content is invalid")
        return content
    except (LLMError, ProviderCallError, DaoPetitionDraftError) as exc:
        get_logger().logger.warning(
            "Celestial Audience used deterministic fallback: %s", exc
        )
        return _fallback_petition_content(initiator_name, tradition, cause)


async def maybe_create_monthly_petition(world: Any, events: list[Event]) -> list[Event]:
    """Record contested rites; only accumulated institutional rites open an audience."""
    major_causes = sorted([event for event in events if getattr(event, "is_major", False)], key=lambda event: (str(event.id), str(event.content)))
    rites: list[Event] = []
    seen_institutions: set[tuple[str, str]] = set()
    for cause in major_causes:
        for candidate in _institution_candidates(world, cause):
            key = (candidate[0], candidate[1])
            if key not in seen_institutions:
                seen_institutions.add(key)
                rites.append(_build_rite(world, cause, candidate))
    institutional_rites = list(rites)
    # Popular rites are aggregated regional occurrences.  They are visible
    # claims and never become petitions by themselves.
    popular_rites: list[Event] = []
    for region, cause in _popular_rite_regions(world):
        popular_rites.append(_build_popular_rite(world, cause, region))
    popular_rites = sorted(
        popular_rites,
        key=lambda event: (
            str((event.causal_payload or {}).get("dao_rite", {}).get("initiator_id", "")),
            str(event.id),
        ),
    )[:2]
    rites = sorted(
        [*institutional_rites, *popular_rites],
        key=lambda event: (
            str((event.causal_payload or {}).get("dao_rite", {}).get("initiator_kind", "")),
            str((event.causal_payload or {}).get("dao_rite", {}).get("initiator_id", "")),
            str(event.id),
        ),
    )
    result: list[Event] = list(rites)
    institutional_rites = [rite for rite in rites if _is_institutional_rite(rite)]
    if not institutional_rites or not _can_open_audience(world):
        return result
    historical_rites = _recent_rite_events(world, current_events=rites)
    for rite in institutional_rites:
        claim = dict((rite.causal_payload or {}).get("dao_rite", {}))
        initiator_kind, initiator_id = (
            str(claim["initiator_kind"]),
            str(claim["initiator_id"]),
        )
        matching = [
            item
            for item in historical_rites
            if _rite_matches(item, initiator_kind, initiator_id)
        ]
        if len(matching) < RITES_REQUIRED_FOR_AUDIENCE:
            continue
        cause = next(
            event
            for event in major_causes
            if event.id == rite.causal_links[0].cause_event_id
        )
        candidate = next(
            item
            for item in _institution_candidates(world, cause)
            if item[:2] == (initiator_kind, initiator_id)
        )
        region = candidate[3]
        rite_ids = [item.id for item in matching[-RITES_REQUIRED_FOR_AUDIENCE:]]
        content = await _render_petition_content(
            world,
            initiator_kind=initiator_kind,
            initiator_id=initiator_id,
            initiator_name=candidate[2],
            tradition=region.dao_tradition,
            cause=cause,
            rite_count=len(matching),
        )
        petition = _create_petition_from_events(
            world,
            initiator_kind=initiator_kind,
            initiator_id=initiator_id,
            region_id=int(region.id),
            motivated_event_ids=[cause.id],
            rite_event_ids=rite_ids,
            content=content,
            source_events=[cause],
        )
        audience = Event(
            world.month_stamp,
            t(
                "{institution}'s accumulated rites reach a rare Celestial Audience.",
                institution=candidate[2],
            ),
            related_avatars=[petition.target_avatar_id]
            if petition.target_avatar_id
            else None,
            related_sects=[int(initiator_id)] if initiator_kind == "sect" else None,
            fact_kind=FactKind.STATE_TRANSITION,
            event_type="celestial_audience",
            is_major=True,
            causal_payload={
                "deltas": [
                    StateDelta(
                        owner_kind="dao_petition",
                        owner_id=petition.id,
                        aspect="created",
                        before=None,
                        after="pending",
                    ).to_dict()
                ],
                "target_avatar_id": petition.target_avatar_id,
                "target_evidence_event_ids": list(petition.target_evidence_event_ids),
            },
        )
        audience.causal_links = [
            CausalLink(
                event_id=audience.id,
                cause_event_id=event_id,
                relation=CausalRelation.ENABLED_BY,
            )
            for event_id in rite_ids
        ]
        audience.causal_links.append(
            CausalLink(
                event_id=audience.id,
                cause_event_id=cause.id,
                relation=CausalRelation.MOTIVATED_BY,
            )
        )
        result.append(audience)
        break
    return result


def answer_petition(world: Any, petition_id: str, response: str) -> Event:
    petition = next((p for p in world.dao_petitions if p.id == petition_id), None)
    if petition is None or petition.status != DaoPetitionStatus.PENDING:
        raise ValueError(t("Celestial Audience is not pending"))
    if response not in {"silence", "sign", "favor"}:
        raise ValueError(t("response must be silence, sign, or favor"))
    status = {
        "silence": DaoPetitionStatus.SILENCED,
        "sign": DaoPetitionStatus.SIGNED,
        "favor": DaoPetitionStatus.FAVORED,
    }[response]
    petition.status = status
    if status == DaoPetitionStatus.FAVORED:
        petition.favor_expires_month = int(world.month_stamp) + 12
    text = (
        t("The Dao remains silent.")
        if response == "silence"
        else interpret_sign(petition.tradition, t("The Dao has answered"))
    )
    if response == "favor":
        text = t(
            "{answer} A limited opportunity is granted to the institution.", answer=text
        )
    event = Event(
        world.month_stamp,
        text,
        related_avatars=[petition.target_avatar_id]
        if petition.target_avatar_id
        else None,
        related_sects=[int(petition.initiator_id)]
        if petition.initiator_kind == "sect"
        else None,
        fact_kind=FactKind.STATE_TRANSITION,
        is_major=True,
        causal_payload={
            "deltas": [
                StateDelta(
                    owner_kind="dao_petition",
                    owner_id=petition.id,
                    aspect="status",
                    before="pending",
                    after=status.value,
                ).to_dict()
            ]
        },
    )
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=event_id,
            relation=CausalRelation.TRIGGERED_BY,
        )
        for event_id in [*petition.rite_event_ids, *petition.motivated_event_ids]
    ]
    petition.response_event_id = event.id
    world.event_manager.add_event(event)
    return event
