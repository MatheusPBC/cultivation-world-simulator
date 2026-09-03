"""Causal rites, contested claims, and rare audiences with the Celestial Dao."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.agent_decision import AgentDecision
from src.classes.celestial_dao import DaoPetition, DaoPetitionStatus, DaoTradition
from src.classes.event import Event, FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
from src.systems.sect_decision_context import find_living_patriarch
from src.classes.mechanical_language import EntityRef
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


def _event_region_id(event: Event) -> int | None:
    payload = getattr(event, "causal_payload", None) or {}
    rite = payload.get("dao_rite", {}) or {}
    params = getattr(event, "render_params", None) or {}
    raw = params.get("region_id", rite.get("region_id"))
    try:
        return int(raw) if raw is not None and str(raw).strip() else None
    except (TypeError, ValueError):
        return None


def _institution_for_avatar(world: Any, avatar: Any) -> tuple[str, str, str] | None:
    """Return the single institution whose public voice the avatar may use."""
    dynasty = getattr(world, "dynasty", None)
    if dynasty is not None and str(getattr(dynasty, "current_emperor_id", "")) == str(getattr(avatar, "id", "")):
        return (
            "court",
            str(getattr(dynasty, "id", "")),
            str(getattr(dynasty, "title", "") or getattr(dynasty, "name", "court")),
        )

    sect = getattr(avatar, "sect", None)
    if sect is not None and find_living_patriarch(sect) is avatar:
        return ("sect", str(getattr(sect, "id", "")), str(getattr(sect, "name", "sect")))
    return None


def _sponsorship_payload(event: Event) -> dict[str, Any]:
    return dict((getattr(event, "causal_payload", {}) or {}).get("dao_rite", {}) or {})


def _known_sponsorship_events(world: Any) -> list[Event]:
    events = _recent_rite_events(world)
    transient = getattr(world, "_dao_sponsorship_events_this_step", {}) or {}
    return [*events, *transient.values()]


def get_sponsor_dao_rite_blocker(
    world: Any, avatar: Any, cause_event_id: str
) -> str | None:
    institution = _institution_for_avatar(world, avatar)
    if institution is None:
        return "Only the reigning emperor or a living sect patriarch may sponsor a Dao rite."

    cause_id = str(cause_event_id or "").strip()
    if not cause_id:
        return "A public Dao rite must be selected."
    cause = world.event_manager.get_event_by_id(cause_id)
    if cause is None:
        return "The sponsoring institution does not know this public Dao rite."
    payload = _sponsorship_payload(cause)
    if str(getattr(cause, "event_type", "")) != "dao_rite" or not bool(payload.get("is_popular")):
        return "Only a popular regional Dao rite can be sponsored."
    region_id = _event_region_id(cause)
    current_region = _region_for_avatar(avatar)
    if region_id is None or current_region is None or int(getattr(current_region, "id", -1)) != region_id:
        return "The sponsor must be present in the rite's region."

    month = int(world.month_stamp)
    kind, institution_id, _name = institution
    for event in _known_sponsorship_events(world):
        existing = _sponsorship_payload(event)
        if not bool(existing.get("is_sponsorship")):
            continue
        same_institution = (
            str(existing.get("sponsor_kind", existing.get("initiator_kind", ""))) == kind
            and str(existing.get("sponsor_id", existing.get("initiator_id", ""))) == institution_id
        )
        if not same_institution:
            continue
        if int(getattr(event, "month_stamp", -1)) == month:
            return "This institution has already sponsored a Dao rite this month."
        if str(existing.get("cause_event_id", "")) == cause_id:
            return "This institution has already sponsored that Dao rite."
    return None


def can_sponsor_dao_rite(world: Any, avatar: Any) -> bool:
    return _institution_for_avatar(world, avatar) is not None


def sponsor_dao_rite(world: Any, avatar: Any, cause_event_id: str) -> Event:
    blocker = get_sponsor_dao_rite_blocker(world, avatar, cause_event_id)
    if blocker is not None:
        raise ValueError(t(blocker))
    institution = _institution_for_avatar(world, avatar)
    assert institution is not None
    cause = world.event_manager.get_event_by_id(str(cause_event_id))
    assert cause is not None
    region_id = _event_region_id(cause)
    assert region_id is not None
    region = world.map.regions[region_id]
    kind, institution_id, institution_name = institution
    decision_event_id = str(getattr(avatar, "current_decision_event_id", "") or "")
    parent_payload = getattr(avatar, "_current_decision_payload", None) or {}
    parent_decision = parent_payload.get("decision", {}) if isinstance(parent_payload, Mapping) else {}
    decision_source = str(parent_decision.get("source", "") or "player")
    audit = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="avatar",
        subject_id=str(avatar.id),
        source=decision_source,
        considered_count=1,
        chosen_chain=[
            {
                "action_name": "SponsorDaoRite",
                "params": {"cause_event_id": str(cause.id)},
            }
        ],
    )
    event = Event(
        world.month_stamp,
        t(
            "{institution} sponsors the popular rite in {region}.",
            institution=institution_name,
            region=getattr(region, "name", str(region_id)),
        ),
        related_avatars=[str(avatar.id)],
        related_sects=[int(institution_id)] if kind == "sect" else None,
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        event_type="dao_rite",
        render_params={"region_id": str(region_id), "cause_event_id": str(cause.id)},
        causal_payload={
            "deltas": [],
            "decision": audit.to_dict(),
            "dao_rite": {
                "initiator_kind": kind,
                "initiator_id": institution_id,
                "sponsor_kind": kind,
                "sponsor_id": institution_id,
                "institution_name": institution_name,
                "region_id": region_id,
                "tradition": region.dao_tradition.value,
                "cause_event_id": str(cause.id),
                "is_confirmed": False,
                "is_popular": False,
                "is_sponsorship": True,
                "month_stamp": int(world.month_stamp),
            },
            "decision_source": {
                "kind": "avatar_action",
                "action_name": "SponsorDaoRite",
                "avatar_id": str(avatar.id),
                "decision_event_id": decision_event_id or None,
            },
        },
    )
    event.causal_links.append(
        CausalLink(event_id=event.id, cause_event_id=str(cause.id), relation=CausalRelation.MOTIVATED_BY)
    )
    if decision_event_id:
        event.causal_links.append(
            CausalLink(event_id=event.id, cause_event_id=decision_event_id, relation=CausalRelation.ENABLED_BY)
        )
    transient = getattr(world, "_dao_sponsorship_events_this_step", None)
    if transient is None:
        transient = {}
        setattr(world, "_dao_sponsorship_events_this_step", transient)
    transient[event.id] = event
    return event


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


def _resolve_imperial_target_from_events(
    world: Any,
    events: list[Event],
) -> tuple[str | None, list[str]]:
    crisis = getattr(getattr(world, "dynasty", None), "imperial_crisis", None)
    if crisis is None:
        return None, []
    contender_ids = {
        str(candidate_id)
        for candidate_id in (
            crisis.incumbent_id,
            *(claim.candidate_id for claim in crisis.claims if claim.status == "active"),
        )
        if candidate_id is not None
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


def _is_institutional_rite(event: Event) -> bool:
    payload = _sponsorship_payload(event)
    return bool(payload.get("is_sponsorship"))


def _build_popular_rite(
    world: Any,
    cause: Event,
    region: Any,
    *,
    condition_id: str | None = None,
) -> Event:
    source_id = cause.id
    rite = Event(
        world.month_stamp,
        t("People in {region} hold a popular rite and claim it answers local pressure.", region=region.name),
        related_sects=None,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        event_type="dao_rite",
        causal_payload={
            "dao_rite": {
                "initiator_kind": "people",
                "initiator_id": str(region.id),
                "region_id": int(region.id),
                "tradition": region.dao_tradition.value,
                "is_confirmed": False,
                "is_popular": True,
                "cause_event_id": source_id,
                "condition_id": condition_id,
            }
        },
    )
    rite.causal_links = [CausalLink(event_id=rite.id, cause_event_id=source_id, relation=CausalRelation.MOTIVATED_BY)]
    return rite


def _popular_rite_regions(
    world: Any, *, current_events: list[Event] | None = None
) -> list[tuple[Any, Event, str | None]]:
    """Select deterministic regional causes that actually exist in the world.

    A derived reading alone is not a cause.  A rite needs either an active
    canonical regional condition (and its source event) or a current public
    event carrying a region reference.
    """
    month = int(world.month_stamp)
    state = getattr(world, "mechanical_language", None)
    current_events = [
        *list(
        getattr(world.event_manager, "get_events_between_months", lambda *_: [])(month, month)
        ),
        *(current_events or []),
    ]
    current_events_by_id = {str(event.id): event for event in current_events}
    candidates: dict[int, tuple[tuple[Any, ...], Any, Event, str | None]] = {}
    for region in sorted(
        getattr(getattr(world, "map", None), "regions", {}).values(),
        key=lambda item: int(getattr(item, "id", 0)),
    ):
        region_id = int(getattr(region, "id", -1))
        if region_id < 0:
            continue
        if state is not None:
            conditions = state.get_active_conditions(EntityRef("region", str(region_id)), month)
            for condition in conditions:
                source = current_events_by_id.get(
                    str(condition.cause_event_id)
                ) or world.event_manager.get_event_by_id(str(condition.cause_event_id))
                if not isinstance(source, Event):
                    continue
                key = (0, -float(getattr(condition, "intensity", 0.0)), str(condition.id))
                candidates.setdefault(region_id, (key, region, source, str(condition.id)))

        for event in current_events:
            if str(getattr(event, "event_type", "")) == "dao_rite":
                continue
            if _event_region_id(event) != region_id:
                continue
            key = (1, -int(bool(getattr(event, "is_major", False))), str(event.id))
            existing = candidates.get(region_id)
            if existing is None or key < existing[0]:
                candidates[region_id] = (key, region, event, None)

    selected = sorted(candidates.values(), key=lambda item: (item[0], int(item[1].id)))[:2]
    return [(region, cause, condition_id) for _key, region, cause, condition_id in selected]


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


async def process_grounded_dao_rites(world: Any, events: list[Event]) -> list[Event]:
    """Create popular claims and evaluate explicit institutional sponsorships.

    Institutional rites are intentionally never synthesized here. The only
    automatic rite produced here is a bounded popular regional claim.
    A petition can be opened only by sponsorship events emitted by
    ``SponsorDaoRite``.
    """
    result: list[Event] = []
    for region, cause, condition_id in _popular_rite_regions(
        world, current_events=events
    ):
        result.append(_build_popular_rite(world, cause, region, condition_id=condition_id))
    if not _can_open_audience(world):
        return result

    historical_rites = _recent_rite_events(world, current_events=[*events, *result])
    sponsorships = [item for item in historical_rites if _is_institutional_rite(item)]
    by_institution: dict[tuple[str, str], list[Event]] = {}
    for sponsorship in sponsorships:
        payload = _sponsorship_payload(sponsorship)
        key = (
            str(payload.get("sponsor_kind", payload.get("initiator_kind", ""))),
            str(payload.get("sponsor_id", payload.get("initiator_id", ""))),
        )
        by_institution.setdefault(key, []).append(sponsorship)

    for (initiator_kind, initiator_id), matching in sorted(by_institution.items()):
        matching.sort(key=lambda item: (int(item.month_stamp), str(item.id)))
        if len(matching) < RITES_REQUIRED_FOR_AUDIENCE:
            continue
        matching_ids = {str(item.id) for item in matching}
        if any(
            str(petition.initiator_kind) == initiator_kind
            and str(petition.initiator_id) == initiator_id
            and matching_ids.intersection(str(item) for item in petition.rite_event_ids)
            for petition in getattr(world, "dao_petitions", [])
        ):
            continue
        latest = matching[-1]
        latest_payload = _sponsorship_payload(latest)
        region = world.map.regions.get(_event_region_id(latest))
        if region is None:
            continue
        cause_id = str(latest_payload.get("cause_event_id", ""))
        cause = world.event_manager.get_event_by_id(cause_id)
        if cause is None:
            cause = next((item for item in [*events, *result] if item.id == cause_id), None)
        if cause is None:
            continue
        # Retain the existing "major cause" gate, but follow the explicit
        # sponsorship's public rite back to its source event.
        source_ids = [str(link.cause_event_id) for link in cause.causal_links]
        source_events = [
            world.event_manager.get_event_by_id(source_id)
            or next((item for item in events if item.id == source_id), None)
            for source_id in source_ids
        ]
        source_events = [item for item in source_events if item is not None]
        major_cause = next((item for item in source_events if item.is_major), None)
        if major_cause is None and cause.is_major:
            major_cause = cause
        if major_cause is None:
            continue
        rite_ids = [item.id for item in matching[-RITES_REQUIRED_FOR_AUDIENCE:]]
        institution_name = str(latest_payload.get("institution_name", initiator_id))
        content = await _render_petition_content(
            world,
            initiator_kind=initiator_kind,
            initiator_id=initiator_id,
            initiator_name=institution_name,
            tradition=region.dao_tradition,
            cause=major_cause,
            rite_count=len(matching),
        )
        petition = _create_petition_from_events(
            world,
            initiator_kind=initiator_kind,
            initiator_id=initiator_id,
            region_id=int(region.id),
            motivated_event_ids=[major_cause.id],
            rite_event_ids=rite_ids,
            content=content,
            source_events=[major_cause],
        )
        audience = Event(
            world.month_stamp,
            t(
                "{institution}'s sponsored rites reach a rare Celestial Audience.",
                institution=institution_name,
            ),
            related_avatars=[petition.target_avatar_id] if petition.target_avatar_id else None,
            related_sects=[int(initiator_id)] if initiator_kind == "sect" else None,
            fact_kind=FactKind.STATE_TRANSITION,
            event_type="celestial_audience",
            is_major=True,
            causal_payload={
                "deltas": [StateDelta(
                    owner_kind="dao_petition",
                    owner_id=petition.id,
                    aspect="created",
                    before=None,
                    after="pending",
                ).to_dict()],
                "target_avatar_id": petition.target_avatar_id,
                "target_evidence_event_ids": list(petition.target_evidence_event_ids),
            },
        )
        audience.causal_links = [
            CausalLink(event_id=audience.id, cause_event_id=event_id, relation=CausalRelation.ENABLED_BY)
            for event_id in rite_ids
        ]
        audience.causal_links.append(
            CausalLink(event_id=audience.id, cause_event_id=major_cause.id, relation=CausalRelation.MOTIVATED_BY)
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
