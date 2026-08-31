"""Small, deterministic application service for Dao petitions and omens."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.celestial_dao import DaoPetition, DaoPetitionStatus, DaoTradition
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.i18n import t
from src.i18n.template_resolver import resolve_locale_template_path
from src.run.log import get_logger
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


class DaoPetitionDraftError(ValueError):
    """The petition voice was missing or unusable; facts remain deterministic."""


def assign_region_traditions(world: Any) -> None:
    traditions = tuple(DaoTradition)
    for region in world.map.regions.values():
        # stable across reloads and independent from dictionary order
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


def get_dao_context(world: Any, *, region_id: int | None = None, initiator_id: str | None = None) -> list[dict[str, Any]]:
    """Observable answers are decision context, never imperative instructions."""
    current_month = int(world.month_stamp)
    observer_region = (getattr(getattr(world, "map", None), "regions", {}) or {}).get(int(region_id)) if region_id is not None else None
    observer_tradition = getattr(observer_region, "dao_tradition", None)
    context: list[dict[str, Any]] = []
    for petition in getattr(world, "dao_petitions", []):
        if petition.status == DaoPetitionStatus.SIGNED:
            # Omens are public.  The source tradition records where the plea
            # arose, while each observing region gives the same sign its own reading.
            reading_tradition = observer_tradition or petition.tradition
            context.append(
                {
                    "kind": "omen",
                    "tradition": reading_tradition.value,
                    "source_tradition": petition.tradition.value,
                    "interpretation": interpret_sign(reading_tradition, t("A public omen")),
                    "initiator_id": str(petition.initiator_id),
                    "source_event_id": petition.response_event_id,
                }
            )
        elif petition.status == DaoPetitionStatus.FAVORED and petition.favor_expires_month and current_month <= petition.favor_expires_month:
            if region_id is not None and petition.region_id != int(region_id):
                continue
            if initiator_id is None or petition.initiator_id == str(initiator_id):
                context.append({"kind": "limited_favor", "tradition": petition.tradition.value, "initiator_id": str(petition.initiator_id), "expires_month": petition.favor_expires_month, "source_event_id": petition.response_event_id})
    return context


def create_petition(world: Any, *, initiator_kind: str, initiator_id: str, region_id: int, motivated_event_ids: list[str], content: str = "") -> DaoPetition:
    region = world.map.regions[int(region_id)]
    if sum(p.status == DaoPetitionStatus.PENDING for p in world.dao_petitions) >= 3:
        raise ValueError(t("Too many pending Dao petitions"))
    petition = DaoPetition(initiator_kind=initiator_kind, initiator_id=str(initiator_id), region_id=int(region_id), tradition=region.dao_tradition, motivated_event_ids=list(motivated_event_ids), content=content or t("A {tradition} petition seeks the Dao's notice.", tradition=region.dao_tradition.value), created_month=int(world.month_stamp))
    world.dao_petitions.append(petition)
    return petition


def _region_for_avatar(avatar: Any) -> Any | None:
    return getattr(getattr(avatar, "tile", None), "region", None)


def _find_monthly_petition_candidate(world: Any, events: list[Event]) -> tuple[Event, str, str, str, Any] | None:
    """The relevance filter is rules-only; narration never controls selection."""
    month = int(world.month_stamp)
    if any(p.created_month == month for p in world.dao_petitions):
        return None
    for cause in events:
        if not getattr(cause, "is_major", False):
            continue
        related_avatar_ids = {str(avatar_id) for avatar_id in getattr(cause, "related_avatars", None) or []}
        dynasty = getattr(world, "dynasty", None)
        if dynasty is not None:
            emperor = world.avatar_manager.get_avatar(str(getattr(dynasty, "current_emperor_id", "") or ""))
            crisis = getattr(dynasty, "imperial_crisis", None)
            court_ids = {str(getattr(emperor, "id", "") or "")}
            if crisis is not None:
                court_ids.add(str(getattr(crisis, "claimant_avatar_id", "") or ""))
            region = _region_for_avatar(emperor)
            if region is not None and related_avatar_ids & court_ids:
                return cause, "court", str(dynasty.id), str(getattr(dynasty, "title", "") or getattr(dynasty, "name", "") or ""), region

        sects_by_id = {int(getattr(sect, "id", 0)): sect for sect in getattr(world, "existed_sects", []) or []}
        for sect_id in getattr(cause, "related_sects", None) or []:
            sect = sects_by_id.get(int(sect_id))
            if sect is None:
                continue
            representative = next(
                (
                    avatar
                    for avatar in world.avatar_manager.get_living_avatars()
                    if int(getattr(getattr(avatar, "sect", None), "id", 0) or 0) == int(sect_id)
                    and _region_for_avatar(avatar) is not None
                ),
                None,
            )
            region = _region_for_avatar(representative)
            if region is not None:
                return cause, "sect", str(sect.id), str(getattr(sect, "name", "") or ""), region

        for avatar_id in getattr(cause, "related_avatars", None) or []:
            avatar = world.avatar_manager.get_avatar(str(avatar_id))
            region = _region_for_avatar(avatar)
            if avatar is None or region is None:
                continue
            return cause, "avatar", str(avatar.id), str(avatar.name), region
    return None


def _fallback_petition_content(initiator_name: str, tradition: DaoTradition, cause: Event) -> str:
    return t("{avatar} asks the Dao to witness this {tradition} concern: {cause}", avatar=initiator_name, tradition=tradition.value, cause=cause.content)


async def _render_petition_content(world: Any, *, initiator_kind: str, initiator_id: str, initiator_name: str, tradition: DaoTradition, cause: Event) -> str:
    locale = str((getattr(world, "run_config_snapshot", {}) or {}).get("content_locale", "")) or None
    template = resolve_locale_template_path(DAO_PETITION_TEMPLATE_FILENAME, current_locale=locale)
    infos = {
        "initiator": {"kind": initiator_kind, "id": initiator_id, "name": initiator_name},
        "tradition": tradition.value,
        "cause": {"id": str(cause.id), "content": str(cause.content), "month_stamp": int(cause.month_stamp)},
    }
    try:
        draft = await call_llm_with_task_name(
            DAO_PETITION_TASK_NAME,
            template,
            infos,
            output_schema=DAO_PETITION_SCHEMA,
        )
        content = str(draft.get("content", "")).strip() if isinstance(draft, Mapping) else ""
        if not content or len(content) > 600:
            raise DaoPetitionDraftError("Dao petition content is invalid")
        return content
    except (LLMError, ProviderCallError, DaoPetitionDraftError) as exc:
        get_logger().logger.warning("Dao petition used deterministic fallback: %s", exc)
        return _fallback_petition_content(initiator_name, tradition, cause)


async def maybe_create_monthly_petition(world: Any, events: list[Event]) -> Event | None:
    """Create at most one relevant petition; LLM only gives its factual plea a voice."""
    candidate = _find_monthly_petition_candidate(world, events)
    if candidate is None:
        return None
    cause, initiator_kind, initiator_id, initiator_name, region = candidate
    content = await _render_petition_content(
        world,
        initiator_kind=initiator_kind,
        initiator_id=initiator_id,
        initiator_name=initiator_name,
        tradition=region.dao_tradition,
        cause=cause,
    )
    petition = create_petition(
        world,
        initiator_kind=initiator_kind,
        initiator_id=initiator_id,
        region_id=int(region.id),
        motivated_event_ids=[cause.id],
        content=content,
    )
    event = Event(
        world.month_stamp,
        t("{avatar} sends a petition to the Celestial Dao.", avatar=initiator_name),
        related_avatars=[initiator_id] if initiator_kind == "avatar" else None,
        related_sects=[int(initiator_id)] if initiator_kind == "sect" else None,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"deltas": [StateDelta(owner_kind="dao_petition", owner_id=petition.id, aspect="created", before=None, after="pending").to_dict()]},
    )
    event.causal_links = [CausalLink(event_id=event.id, cause_event_id=cause.id, relation=CausalRelation.MOTIVATED_BY)]
    return event


def answer_petition(world: Any, petition_id: str, response: str) -> Event:
    petition = next((p for p in world.dao_petitions if p.id == petition_id), None)
    if petition is None or petition.status != DaoPetitionStatus.PENDING:
        raise ValueError(t("Petition is not pending"))
    if response not in {"silence", "sign", "favor"}:
        raise ValueError(t("response must be silence, sign, or favor"))
    status = {"silence": DaoPetitionStatus.SILENCED, "sign": DaoPetitionStatus.SIGNED, "favor": DaoPetitionStatus.FAVORED}[response]
    petition.status = status
    if status == DaoPetitionStatus.FAVORED:
        petition.favor_expires_month = int(world.month_stamp) + 12
    text = t("The Dao remains silent.") if response == "silence" else interpret_sign(petition.tradition, t("The Dao has answered"))
    if response == "favor":
        text = t("{answer} A limited opportunity is granted to the petitioner.", answer=text)
    event = Event(world.month_stamp, text, related_avatars=[petition.initiator_id] if petition.initiator_kind == "avatar" else None,
                  related_sects=[int(petition.initiator_id)] if petition.initiator_kind == "sect" else None, fact_kind=FactKind.STATE_TRANSITION, is_major=True,
                  causal_payload={"deltas": [StateDelta(owner_kind="dao_petition", owner_id=petition.id, aspect="status", before="pending", after=status.value).to_dict()]})
    event.causal_links = [CausalLink(event_id=event.id, cause_event_id=eid, relation=CausalRelation.TRIGGERED_BY) for eid in petition.motivated_event_ids]
    petition.response_event_id = event.id
    world.event_manager.add_event(event)
    return event
