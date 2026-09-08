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
from src.classes.institution import AuthorityScope, InstitutionKind, KnowledgeChannel
from src.systems.avatar_decision import attach_validated_actor_decision
from src.systems.institution_authority import can_actor_act_for
from src.systems.institutional_memory import decision_context, record_known_fact
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
SPONSORSHIP_ACTION_NAME = "SponsorDaoRite"
# Endorsing a mortal rite is recognition, not disposition of anything material.
SPONSORSHIP_SCOPE = AuthorityScope.RECOGNITION
# An institution witnesses through the office that could later react to what
# it saw; witnessing itself grants nothing.
WITNESS_SCOPE = AuthorityScope.COMMITMENT_NEGOTIATION
# The decision sources the engine itself writes; anything else is not an
# audited choice.  Kept in step with the aggression path's identical rule.
_AUDITED_DECISION_SOURCES = frozenset({"llm", "rule", "injected", "player"})

# These are regular bookkeeping facts, not regional pressure that would make
# a public rite meaningful.  Keep the exclusion explicit: a positive monthly
# flow must not become a ritual merely because it changed a stock.
_ROUTINE_REGIONAL_EVENT_TYPES = frozenset(
    {
        "regional_production",
        "regional_consumption",
        "regional_resource_balance",
        "regional_climate_updated",
        "regional_resource_transfer_completed",
        "regional_resource_transfer_blocked",
    }
)
_MATERIAL_REGIONAL_EVENT_TYPES = frozenset(
    {
        "regional_resource_shortage",
        "regional_flood_started",
        "regional_flood_resolved",
        "avatar_population_change",
        "population_transfer_completed",
        "population_transfer_blocked",
        "route_operational_capacity_changed",
    }
)


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


def _month_stamp(event: Event) -> int | None:
    try:
        return int(getattr(event, "month_stamp", None))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _has_nonzero_material_delta(event: Event) -> bool:
    """Return whether an event records a meaningful domain state change."""
    payload = getattr(event, "causal_payload", None) or {}
    for raw_delta in payload.get("deltas", ()) or ():
        if not isinstance(raw_delta, Mapping):
            continue
        owner_kind = str(raw_delta.get("owner_kind", ""))
        if owner_kind not in {"region", "route", "city", "regional_flood"}:
            continue
        try:
            magnitude = float(raw_delta.get("magnitude", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if magnitude != 0.0:
            return True
    return False


def _is_eligible_regional_event(event: Event) -> bool:
    """Accept only a real regional pressure signal for a popular rite.

    Major events are meaningful by definition, while non-major material facts
    need either an explicitly material event type or a non-zero canonical
    domain delta.  Routine economy/climate bookkeeping is excluded first so a
    normal production or weather tick cannot satisfy either branch.
    """
    event_type = str(getattr(event, "event_type", "") or "")
    if event_type in _ROUTINE_REGIONAL_EVENT_TYPES or bool(getattr(event, "is_story", False)):
        return False
    if bool(getattr(event, "is_major", False)):
        return True
    return event_type in _MATERIAL_REGIONAL_EVENT_TYPES or _has_nonzero_material_delta(event)


def _institution_candidate(world: Any, avatar: Any) -> tuple[str, str, str] | None:
    """Return the single institution whose public voice the avatar may claim.

    This answers identity only -- who this avatar would be speaking for -- and
    deliberately grants nothing.  Whether that voice is actually authorized
    right now is `can_actor_act_for`'s answer, in `_sponsoring_institution`.
    """
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


def _sponsoring_institution(
    world: Any, avatar: Any
) -> tuple[str, str, str, str] | None:
    """The candidate voice plus the canonical institution that authorizes it.

    Sponsoring a rite is a public endorsement, so the authorizing scope is
    `RECOGNITION`: the one scope both the dynasty's sovereign office and a
    sect's patriarch office actually hold, and the one that grants no
    resources, troops or territory.  There is no permissive fallback -- a
    world with no bootstrapped authority state simply has nobody who can
    sponsor, rather than everybody.

    ``"court"`` stays a Dao-domain label for the payload; the canonical
    identity is the returned `Institution` ID, resolved from the dynasty or
    sect `EntityRef`.
    """
    candidate = _institution_candidate(world, avatar)
    if candidate is None:
        return None
    kind, owner_id, name = candidate
    if not owner_id.strip():
        return None
    verdict = can_actor_act_for(
        world,
        EntityRef("avatar", str(getattr(avatar, "id", ""))),
        EntityRef("dynasty" if kind == "court" else "sect", owner_id),
        SPONSORSHIP_SCOPE,
        current_month=int(world.month_stamp),
    )
    if not verdict.allowed or not verdict.institution_id:
        return None
    return kind, owner_id, name, verdict.institution_id


def _sponsorship_payload(event: Event) -> dict[str, Any]:
    return dict((getattr(event, "causal_payload", {}) or {}).get("dao_rite", {}) or {})


def _register_sponsorship_event(world: Any, event: Event) -> None:
    """Keep this step's not-yet-stored sponsorships visible to the same month.

    Only the current rite window is retained: older sponsorships are already
    canonical events, so keeping them here would make a live session refuse
    what a reloaded one allows, and would grow without bound for the lifetime
    of the world.
    """
    transient = getattr(world, "_dao_sponsorship_events_this_step", None)
    if not isinstance(transient, dict):
        transient = {}
        setattr(world, "_dao_sponsorship_events_this_step", transient)
    oldest = int(world.month_stamp) - RITE_WINDOW_MONTHS + 1
    for event_id in [
        key
        for key, item in transient.items()
        if (month := _month_stamp(item)) is None or month < oldest
    ]:
        del transient[event_id]
    transient[event.id] = event


def _known_sponsorship_events(world: Any) -> list[Event]:
    events = _recent_rite_events(world)
    transient = getattr(world, "_dao_sponsorship_events_this_step", {}) or {}
    return [*events, *transient.values()]


def get_sponsor_dao_rite_blocker(
    world: Any, avatar: Any, cause_event_id: str
) -> str | None:
    institution = _sponsoring_institution(world, avatar)
    if institution is None:
        return "Only the reigning emperor or a living sect patriarch may sponsor a Dao rite."

    cause_id = str(cause_event_id or "").strip()
    if not cause_id:
        return "A public Dao rite must be selected."
    cause = world.event_manager.get_event_by_id(cause_id)
    if cause is None:
        return "The sponsoring institution does not know this public Dao rite."
    payload = _sponsorship_payload(cause)
    if (
        str(getattr(cause, "event_type", "")) != "dao_rite"
        or not bool(payload.get("is_popular"))
        or bool(getattr(cause, "is_story", False))
    ):
        return "Only a popular regional Dao rite can be sponsored."
    # The sponsorable set is exactly the rite window the institution can still
    # see.  An older rite, and a rite stamped after the current month (a
    # replayed or rolled-back step), are both outside what it knows now.
    cause_month = _month_stamp(cause)
    month = int(world.month_stamp)
    if cause_month is None or not (month - RITE_WINDOW_MONTHS < cause_month <= month):
        return "The sponsoring institution does not know this public Dao rite."
    region_id = _event_region_id(cause)
    current_region = _region_for_avatar(avatar)
    if region_id is None or current_region is None or int(getattr(current_region, "id", -1)) != region_id:
        return "The sponsor must be present in the rite's region."

    kind, owner_id, _name, _institution_id = institution
    for event in _known_sponsorship_events(world):
        existing = _sponsorship_payload(event)
        if not bool(existing.get("is_sponsorship")):
            continue
        same_institution = (
            str(existing.get("sponsor_kind", existing.get("initiator_kind", ""))) == kind
            and str(existing.get("sponsor_id", existing.get("initiator_id", ""))) == owner_id
        )
        if not same_institution:
            continue
        if int(getattr(event, "month_stamp", -1)) == month:
            return "This institution has already sponsored a Dao rite this month."
        if str(existing.get("cause_event_id", "")) == cause_id:
            return "This institution has already sponsored that Dao rite."
    return None


def can_sponsor_dao_rite(world: Any, avatar: Any) -> bool:
    return _sponsoring_institution(world, avatar) is not None


def _living_office_holder(world: Any, institution: Any) -> Any | None:
    """The institution's current negotiating holder, if it has a living one."""
    state = getattr(world, "institutional_authority", None)
    if state is None:
        return None
    office = state.office_for_scope(institution.id, WITNESS_SCOPE)
    if office is None or office.holder_ref is None:
        return None
    if not can_actor_act_for(
        world,
        office.holder_ref,
        institution.owner_ref,
        WITNESS_SCOPE,
        current_month=int(world.month_stamp),
    ).allowed:
        return None
    getter = getattr(getattr(world, "avatar_manager", None), "get_avatar", None)
    holder = getter(str(office.holder_ref.id)) if callable(getter) else None
    return holder if holder is not None and not bool(getattr(holder, "is_dead", False)) else None


def _witness_institution_ids(
    world: Any, sponsor_avatar: Any, sponsor_institution_id: str
) -> tuple[str, ...]:
    """Institutions whose own negotiating holder actually saw this sponsorship.

    Witnessing is a fact about people, captured at the exact moment the act
    happens and never recomputed from where anyone stands later.  Sharing a
    region, sharing a membership or being mentioned in prose proves nothing:
    the institution's current holder must be alive, actually authorized under
    `COMMITMENT_NEGOTIATION`, and have the sponsoring avatar inside its own
    observation radius.  The sponsor is never its own witness, and only
    dynasties and sects can witness -- a city institution holds no office that
    could have been present.
    """
    from src.classes.observe import is_within_observation

    state = getattr(world, "institutional_authority", None)
    if state is None or sponsor_avatar is None:
        return ()
    month = int(world.month_stamp)
    witnesses: list[str] = []
    for institution in state.institutions.values():
        if institution.id == sponsor_institution_id:
            continue
        if institution.kind not in (InstitutionKind.DYNASTY, InstitutionKind.SECT):
            continue
        if not institution.is_active(month):
            continue
        holder = _living_office_holder(world, institution)
        if holder is None or holder is sponsor_avatar:
            continue
        try:
            seen = is_within_observation(holder, sponsor_avatar)
        except (AttributeError, TypeError):
            continue
        if seen:
            witnesses.append(institution.id)
    return tuple(sorted(witnesses))


def _identity_anchor_impact(world: Any, institution_id: str, region_id: int) -> float:
    """Whether this institution's own identity is anchored in the rite's region."""
    state = getattr(world, "institutional_authority", None)
    anchors = getattr(state, "identity_anchors", None) or {}
    subject = EntityRef("region", str(region_id))
    return (
        1.0
        if any(
            anchor.institution_id == institution_id and anchor.subject == subject
            for anchor in anchors.values()
        )
        else 0.0
    )


def _sponsorship_memory_factors(
    world: Any, institution_id: str, region_id: int
) -> dict[str, float]:
    """The four frozen engine factors, each read from canonical state.

    ``relative_scale`` is this one act's share of the domain's own audience
    threshold: a single sponsorship is exactly one of the
    `RITES_REQUIRED_FOR_AUDIENCE` an audience takes.  It is deliberately not
    cumulative -- counting the institution's prior sponsorships would read the
    persisted window and the runtime cache together, double-counting an event
    present in both and giving the same fact a different weight after a
    reload.  Sponsoring changes no office and breaches no commitment, so those
    two factors are zero as a matter of fact rather than as a default.  No LLM
    weighting is involved anywhere.
    """
    return {
        "relative_scale": 1.0 / RITES_REQUIRED_FOR_AUDIENCE,
        "institutional_change": 0.0,
        "commitment_breach": 0.0,
        "identity_anchor_impact": _identity_anchor_impact(
            world, institution_id, region_id
        ),
    }


def get_sponsor_institution_memory(world: Any, avatar: Any) -> dict[str, Any] | None:
    """This avatar's own institution's bounded memory, or nothing.

    Knowledge is not omniscient and this is not a broadcast: only the avatar
    who may currently speak for the institution under `RECOGNITION` sees it,
    an ordinary member sees nothing, and the projection is the shared bounded
    `decision_context` rather than a second reading of the same state.
    """
    institution = _sponsoring_institution(world, avatar)
    if institution is None:
        return None
    return decision_context(
        world, institution[3], authority_scope=SPONSORSHIP_SCOPE
    )


def record_dao_rite_sponsorship(
    world: Any,
    avatar: Any,
    cause_event_id: str,
    *,
    action_origin: Any,
) -> Event | None:
    """The institution's sponsorship fact, only when its own decision chose it.

    This runs at the execution boundary, not at ``start``: the engine writes
    ``ActionOrigin.ACTOR_CHOICE`` onto the committed action only after
    ``start`` returns, so authorship can only be proved here.  Two independent
    witnesses are required and neither is forgeable by prose or by a direct
    call: the shared owner in ``avatar_decision`` must find this exact
    ``SponsorDaoRite`` step with this exact cause in the actor's own audited
    decision, and the sponsorship rule must still hold now.  A reactive
    install, a restored save, a decision that chose something else and a rite
    that went stale between commit and execution all return ``None`` -- no
    sponsorship fact exists, rather than an unauthored one.

    Authority is asked the same way at both ends: the blocker resolves the
    canonical institution through `can_actor_act_for` under `RECOGNITION`, so
    an office that lost its holder, changed hands or lost the scope between
    commit and execution refuses here and mutates nothing.

    The fact itself is an OCCURRENCE that transitions no domain owner --
    sponsoring moves no resource and changes no office.  The only deltas it
    carries are the ones institutional knowledge and memory append for
    themselves when the institution records its own act.
    """
    if get_sponsor_dao_rite_blocker(world, avatar, cause_event_id) is not None:
        return None
    institution = _sponsoring_institution(world, avatar)
    assert institution is not None
    cause = world.event_manager.get_event_by_id(str(cause_event_id))
    assert cause is not None
    region_id = _event_region_id(cause)
    assert region_id is not None
    region = world.map.regions[region_id]
    kind, owner_id, institution_name, institution_id = institution
    # Captured now, from who is actually present now.  This snapshot is the
    # historical fact; nothing downstream recomputes it from later positions.
    witness_institution_ids = _witness_institution_ids(world, avatar, institution_id)
    event = Event(
        world.month_stamp,
        t(
            "{institution} sponsors the popular rite in {region}.",
            institution=institution_name,
            region=getattr(region, "name", str(region_id)),
        ),
        related_avatars=[str(avatar.id)],
        related_sects=[int(owner_id)] if kind == "sect" else None,
        fact_kind=FactKind.OCCURRENCE,
        event_type="dao_rite",
        render_params={"region_id": str(region_id), "cause_event_id": str(cause.id)},
        causal_payload={
            "deltas": [],
            "dao_rite": {
                # ``sponsor_kind``/``sponsor_id`` stay the legacy Dao labels
                # ("court" is not an EntityRef kind); the canonical identity is
                # ``sponsor_institution_id``.
                "initiator_kind": kind,
                "initiator_id": owner_id,
                "sponsor_kind": kind,
                "sponsor_id": owner_id,
                "sponsor_institution_id": institution_id,
                "witness_institution_ids": list(witness_institution_ids),
                "institution_name": institution_name,
                "region_id": region_id,
                "tradition": region.dao_tradition.value,
                "cause_event_id": str(cause.id),
                "is_confirmed": False,
                "is_popular": False,
                "is_sponsorship": True,
                "month_stamp": int(world.month_stamp),
            },
        },
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=str(cause.id),
            relation=CausalRelation.MOTIVATED_BY,
        )
    )
    # The single owner of "which decision authored this consequence".  It sets
    # the actor-decision origin and the persisted ``decision_source`` citation
    # that the audience path reads back; without a proved decision it writes
    # nothing and the fact is discarded.
    if (
        attach_validated_actor_decision(
            event,
            avatar,
            action_name=SPONSORSHIP_ACTION_NAME,
            params={"cause_event_id": str(cause_event_id)},
            action_origin=action_origin,
        )
        is None
    ):
        return None
    # The institution learns what it itself did, through `OWN_ACTION`.  This is
    # still not a public announcement: the only others who learn are the
    # institutions whose own holder was actually present, on their own channel
    # below.  The knowledge and memory deltas are appended by their owners onto
    # this still uncommitted event, so no already-persisted fact is mutated.
    record_known_fact(
        world,
        event,
        (institution_id,),
        factors=_sponsorship_memory_factors(world, institution_id, region_id),
        channel=KnowledgeChannel.OWN_ACTION,
    )
    if witness_institution_ids:
        # Those who were actually there learn the same fact through a different
        # channel, on the same uncommitted event.  No memory is fabricated for
        # them: what a sponsorship is worth to an onlooker has no engine-owned
        # weight, so they know it without yet remembering it.
        record_known_fact(
            world,
            event,
            witness_institution_ids,
            channel=KnowledgeChannel.MEMBER_WITNESS,
        )
    _register_sponsorship_event(world, event)
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


def _cited_decision_authored_sponsorship(
    world: Any, event: Event, overlays: Mapping[str, Event]
) -> bool:
    """Follow the citation to the decision and check it really chose this.

    A ``decision_source`` is a pointer, not evidence, so it is resolved rather
    than trusted: the cited event must exist, be a real ``DECISION`` fact
    carrying no delta of its own, belong to the avatar named by the citation,
    and its audited chain must contain a ``SponsorDaoRite`` step naming this
    exact rite.  A forged pointer, a pointer to some other decision, and a
    decision that chose a different action or a different rite all fail here.
    """
    payload = _sponsorship_payload(event)
    cause_event_id = str(payload.get("cause_event_id") or "").strip()
    source = (getattr(event, "causal_payload", {}) or {}).get("decision_source")
    if not cause_event_id or not isinstance(source, Mapping):
        return False
    if str(source.get("action_name", "")) != SPONSORSHIP_ACTION_NAME:
        return False
    avatar_id = str(source.get("avatar_id") or "").strip()
    decision_event_id = str(source.get("decision_event_id") or "").strip()
    fact_month = _month_stamp(event)
    if not avatar_id or not decision_event_id or fact_month is None:
        return False
    # A decision taken in this same step is not queryable yet, so the step's
    # own events are searched before the store.
    decision_event = overlays.get(decision_event_id) or world.event_manager.get_event_by_id(
        decision_event_id
    )
    if not isinstance(decision_event, Event):
        return False
    decision_payload = decision_event.causal_payload
    if not isinstance(decision_payload, Mapping):
        return False
    decision = decision_payload.get("decision")
    if not isinstance(decision, Mapping):
        return False
    try:
        audit = AgentDecision.from_dict(dict(decision))
    except (AttributeError, TypeError, ValueError):
        return False
    if (
        decision_event.fact_kind is not FactKind.DECISION
        or decision_event.is_story
        or decision_payload.get("deltas") != []
        # A partial record must not be blessed by dataclass defaults.
        or set(decision) != set(audit.to_dict())
        or not isinstance(audit.id, str)
        or not audit.id.strip()
        or audit.source not in _AUDITED_DECISION_SOURCES
        # A malformed month is not comparable and must never raise here.
        or isinstance(audit.month_stamp, bool)
        or type(audit.month_stamp) is not int
        or audit.month_stamp != int(decision_event.month_stamp)
        or audit.subject_kind != "avatar"
        or str(audit.subject_id) != avatar_id
        # A decision taken after the fact it supposedly authored is not its
        # author.  Who holds the office *today* is deliberately not rechecked:
        # a later leadership change does not unmake a sponsorship that happened.
        or int(decision_event.month_stamp) > fact_month
    ):
        return False
    chosen_params = {"cause_event_id": cause_event_id}
    return any(
        isinstance(step, Mapping)
        and str(step.get("action_name", "")) == SPONSORSHIP_ACTION_NAME
        and isinstance(step.get("params"), Mapping)
        and dict(step["params"]) == chosen_params
        for step in audit.chosen_chain
    )


def _is_institutional_rite(
    world: Any, event: Event, overlays: Mapping[str, Event]
) -> bool:
    """Count a sponsorship towards an audience only if the fact proves itself.

    Every witness read here is persisted with the event, so a sponsorship
    reloaded from a save is judged exactly as it was in the step that produced
    it.  ``causal_links`` are deliberately not consulted: the windowed query
    used to gather rites does not rehydrate them, so a link-based rule would
    silently stop recognising stored sponsorships.  A Story, a hand-written
    ``is_sponsorship`` payload and a fact whose cited decision does not
    actually name this rite are all simply not sponsorships.
    """
    payload = _sponsorship_payload(event)
    if not bool(payload.get("is_sponsorship")) or bool(getattr(event, "is_story", False)):
        return False
    if getattr(event, "fact_kind", None) is not FactKind.OCCURRENCE:
        return False
    if getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION:
        return False
    return _cited_decision_authored_sponsorship(world, event, overlays)


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


def _used_popular_rite_source_keys(
    world: Any,
    *,
    current_events: list[Event],
) -> set[str]:
    """Return canonical causes that have already received a popular rite.

    One condition instance or material event can motivate one aggregate public
    rite.  A persistent condition may motivate a later rite only after it
    resolves and a new condition instance is created.
    """
    month = int(world.month_stamp)
    persisted = list(
        getattr(world.event_manager, "get_events_between_months", lambda *_: [])(
            -(2**63), month
        )
    )
    keys: set[str] = set()
    for event in (*persisted, *current_events):
        if str(getattr(event, "event_type", "")) != "dao_rite":
            continue
        payload = dict(
            (getattr(event, "causal_payload", {}) or {}).get("dao_rite", {}) or {}
        )
        if not bool(payload.get("is_popular")) or bool(payload.get("is_sponsorship")):
            continue
        condition_id = str(payload.get("condition_id") or "")
        cause_event_id = str(payload.get("cause_event_id") or "")
        if condition_id:
            keys.add(f"condition:{condition_id}")
        if cause_event_id:
            keys.add(f"event:{cause_event_id}")
    return keys


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
    used_source_keys = _used_popular_rite_source_keys(
        world,
        current_events=current_events,
    )
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
                if f"condition:{condition.id}" in used_source_keys:
                    continue
                source = current_events_by_id.get(
                    str(condition.cause_event_id)
                ) or world.event_manager.get_event_by_id(str(condition.cause_event_id))
                if not isinstance(source, Event):
                    continue
                if f"event:{source.id}" in used_source_keys:
                    continue
                key = (0, -float(getattr(condition, "intensity", 0.0)), str(condition.id))
                candidates.setdefault(region_id, (key, region, source, str(condition.id)))

        for event in current_events:
            if str(getattr(event, "event_type", "")) == "dao_rite":
                continue
            if _event_region_id(event) != region_id:
                continue
            if not _is_eligible_regional_event(event):
                continue
            if f"event:{event.id}" in used_source_keys:
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
    # This step's own facts, including the decisions taken this month, are not
    # in the store yet, so they are offered to the citation check as overlays.
    overlays = {str(item.id): item for item in [*events, *result]}
    sponsorships = [
        item for item in historical_rites if _is_institutional_rite(world, item, overlays)
    ]
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
                "deltas": [],
                "target_avatar_id": petition.target_avatar_id,
                "target_evidence_event_ids": list(petition.target_evidence_event_ids),
            },
        )
        audience.causal_payload["deltas"] = [
            StateDelta(
                event_id=audience.id,
                owner_kind="dao_petition",
                owner_id=petition.id,
                aspect="created",
                before=None,
                after="pending",
            ).to_dict()
        ]
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
    decision = AgentDecision(
        month_stamp=int(world.month_stamp),
        subject_kind="player",
        subject_id=str(petition.target_avatar_id or "celestial_dao"),
        source="api",
        considered_count=3,
        chosen_chain=[
            {
                "action_name": "AnswerDaoPetition",
                "params": {"petition_id": petition.id, "response": response},
            }
        ],
    )
    decision_event = Event(
        world.month_stamp,
        t("The Dao considered an institutional petition."),
        related_avatars=[petition.target_avatar_id]
        if petition.target_avatar_id
        else None,
        related_sects=[int(petition.initiator_id)]
        if petition.initiator_kind == "sect"
        else None,
        fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        event_type="dao_petition_decision",
        causal_payload={"deltas": [], "decision": decision.to_dict()},
    )
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
        causal_origin=CausalOrigin.ACTOR_DECISION,
        event_type="dao_petition_answer",
        causal_payload={"deltas": []},
    )
    event.causal_payload["deltas"] = [
        StateDelta(
            event_id=event.id,
            owner_kind="dao_petition",
            owner_id=petition.id,
            aspect="status",
            before="pending",
            after=status.value,
        ).to_dict()
    ]
    event.causal_links = [
        CausalLink(
            event_id=event.id,
            cause_event_id=decision_event.id,
            relation=CausalRelation.TRIGGERED_BY,
        ),
        *[
        CausalLink(
            event_id=event.id,
            cause_event_id=event_id,
            relation=CausalRelation.ENABLED_BY,
        )
        for event_id in [*petition.rite_event_ids, *petition.motivated_event_ids]
        ],
    ]
    petition.response_event_id = event.id
    world.event_manager.add_event(decision_event)
    world.event_manager.add_event(event)
    return event
