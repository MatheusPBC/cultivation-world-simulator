"""The one canonical fact that a sect member deliberately attacked another.

This module owns a single narrow question: did an Avatar *choose* to open
hostilities against a member of another sect, and which institution actually
found out about it.  It answers nothing else.  It grants no authority, moves
no resource, changes no relation and never decides that a sect is at war:
personal aggression is a personal act, and reading it only states that a
member was the aggressor.  Whether an institution responds is a separate,
authorized institutional decision elsewhere.

Provenance is deliberately the narrowest one available, and it needs two
independent proofs that cannot be produced by prose or by an LLM parameter:

* only ``MutualAttack`` -- the one publicly offered action by which an Avatar
  opens hostilities -- reaches this producer, so a Spar, an Assassinate, an
  Occupy, a defensive internal ``Attack`` and a generic ``battle_result``
  never become a casus belli, and neither does a name, a text or a personal
  appraisal;
* the committed action's engine-written ``action_origin`` must be
  ``ACTOR_CHOICE``.  A failed ``Escape`` fallback, a ``MutualAttack`` or
  ``DriveAway`` response and a restored save all carry the fail-closed
  ``REACTIVE_RESPONSE`` value, so a defence can never bootstrap a war even
  when the victim's older, still-current decision happens to name the same
  attack;
* on top of that, the attacker's own audited decision must actually contain
  that exact ``MutualAttack`` step with that exact ``target_avatar``
  selector, so an ``ACTOR_CHOICE`` plan installed for some other action, or
  for the same action against somebody else, cannot be relabelled either.

The fact is recorded when the hostility *begins*, not when it is answered:
one initiative produces exactly one aggression, and the response -- a battle,
a flight, a successful escape -- refers back to it instead of producing a
second one.  So an attempt that the target escapes is still an aggression,
and nothing about a battle or any damage is implied by the fact itself.

A decision the player authored while roleplaying the Avatar is one of those
audited decisions.  It qualifies for exactly one reason: an accepted roleplay
command now writes its own canonical ``AgentDecision`` (``source="player"``)
before anything is queued, so it is proved by the same two independent
witnesses as an autonomous one and is subject to every check below.  A
command that was refused, or whose decision failed to persist, queues
nothing and therefore cannot reach here at all.

Everything material is snapshotted *before* the battle resolves: both
memberships and the institutions whose force-employment office holder
actually witnessed the attack.  A patriarch who witnesses an attack and dies
in it still witnessed it, and a later death, cleanup or transfer can never
rewrite who belonged to whom at the moment the attack happened.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.agent_decision import AgentDecision
from src.classes.institution import AuthorityScope, KnowledgeChannel
from src.classes.action_runtime import ActionOrigin
from src.classes.observe import is_within_observation
from src.i18n import t
from src.systems.institutional_diplomacy import (
    has_active_sect_institution,
    sect_institution_id,
)
from src.systems.institutional_memory import record_known_fact

# The audited authorship values a decision fact may claim.  ``player`` is a
# real Avatar decision the player authored by direct command; the collective
# institutional allowlists elsewhere deliberately do not include it, because
# there is no player path that decides for an institution.
_AUDITED_DECISION_SOURCES = frozenset({"llm", "rule", "injected", "player"})

DELIBERATE_ATTACK_EVENT_TYPE = "avatar_deliberate_attack"
# The one publicly offered action that opens hostilities.  The internal
# ``Attack`` is `register_action(actual=False)`: it exists only as an
# engine-installed response, so it is deliberately not this name.
INITIATING_ACTION_NAME = "MutualAttack"
# The parameter under which that action's decision records its target.
TARGET_SELECTOR_PARAM = "target_avatar"
# Runtime-only handle by which an installed response action learns which
# initiative it is answering.  Never persisted: a restored save carries no
# initiative and therefore links nothing.
_INITIATIVE_ATTR = "_initiating_aggression_event_id"

_PAYLOAD_KEY = "avatar_aggression"
_ID_FIELDS = (
    "initiator_avatar_id",
    "target_avatar_id",
    "initiator_sect_id",
    "target_sect_id",
    "initiator_institution_id",
    "target_institution_id",
    "decision_event_id",
    "target_selector",
)
_MONTH_FIELDS = ("month",)
_PAYLOAD_FIELDS = frozenset((*_ID_FIELDS, *_MONTH_FIELDS))


@dataclass(frozen=True, slots=True)
class AggressionSnapshot:
    """Everything material, frozen at the instant the attack was executed.

    Memberships and witnesses are both captured here, before the battle can
    kill anyone, so the fact recorded afterwards describes the world as it
    actually was when the attack happened.
    """

    initiator_avatar_id: str
    target_avatar_id: str
    initiator_sect_id: str
    target_sect_id: str
    decision_event_id: str
    target_selector: str
    witness_institution_ids: tuple[str, ...]


def _identifier(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        return None
    return value


def _month(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return int(value)


def _sect_id(avatar: Any) -> str | None:
    sect = getattr(avatar, "sect", None)
    raw = getattr(sect, "id", None)
    if sect is None or raw is None:
        return None
    try:
        numeric = int(raw)
    except (TypeError, ValueError):
        return None
    return str(numeric) if numeric > 0 else None


def _deliberate_decision_event_id(avatar: Any, params: Mapping[str, Any]) -> str | None:
    """The actor's own audited decision, only if it really chose this attack.

    The live decision payload is the engine-owned audit record written at the
    decision boundary; it is read here rather than the event store because a
    decision made in this same step is not queryable yet.  A chain that does
    not contain this exact ``MutualAttack`` step is not a deliberate attack.
    On its own this is *not* sufficient -- a pre-empted actor keeps its
    previous decision id, so the caller must also prove
    ``ActionOrigin.ACTOR_CHOICE``.
    """

    event_id = _identifier(str(getattr(avatar, "current_decision_event_id", "") or ""))
    payload = getattr(avatar, "_current_decision_payload", None)
    if event_id is None or not isinstance(payload, Mapping):
        return None
    decision = payload.get("decision")
    if not isinstance(decision, Mapping):
        return None
    if str(decision.get("subject_kind", "")) != "avatar" or str(
        decision.get("subject_id", "")
    ) != str(getattr(avatar, "id", "")):
        return None
    expected = dict(params)
    for step in decision.get("chosen_chain") or []:
        if not isinstance(step, Mapping):
            continue
        if str(step.get("action_name", "")) != INITIATING_ACTION_NAME:
            continue
        step_params = step.get("params")
        if isinstance(step_params, Mapping) and dict(step_params) == expected:
            return event_id
    return None


def capture_aggression_snapshot(
    world: Any,
    initiator: Any,
    target: Any,
    *,
    params: Mapping[str, Any],
    action_origin: ActionOrigin | str,
) -> AggressionSnapshot | None:
    """Snapshot the material preconditions before the battle is resolved.

    Returning ``None`` is the normal outcome: most attacks are not between
    two sect members, and most are not the actor's own deliberate choice.
    """

    if action_origin is not ActionOrigin.ACTOR_CHOICE:
        # A reactive, installed or restored action is never an aggression.
        return None
    initiator_sect_id = _sect_id(initiator)
    target_sect_id = _sect_id(target)
    if (
        initiator_sect_id is None
        or target_sect_id is None
        or initiator_sect_id == target_sect_id
    ):
        return None
    month = int(world.month_stamp)
    if not all(
        has_active_sect_institution(world, sect_id, current_month=month)
        for sect_id in (initiator_sect_id, target_sect_id)
    ):
        return None
    decision_event_id = _deliberate_decision_event_id(initiator, params)
    if decision_event_id is None:
        return None
    target_selector = _identifier(params.get(TARGET_SELECTOR_PARAM))
    if target_selector is None:
        return None
    return AggressionSnapshot(
        initiator_avatar_id=str(initiator.id),
        target_avatar_id=str(target.id),
        initiator_sect_id=initiator_sect_id,
        target_sect_id=target_sect_id,
        decision_event_id=decision_event_id,
        # The exact selector the decision actually chose, frozen here so the
        # chain stays verifiable after the target is renamed or removed.
        target_selector=target_selector,
        witness_institution_ids=_witnessing_institutions(
            world, initiator, target, month
        ),
    )


def avatar_aggression_payload(event: Any) -> dict[str, Any] | None:
    """The aggression carried by a fact, or None if it is not a valid one.

    Every field is validated here, so a malformed, hand-written or forged
    payload can only ever produce "no cause"; it can never raise inside an
    annual phase and never yields a partially trusted reading.
    """

    if not isinstance(event, Event):
        return None
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get(_PAYLOAD_KEY)
    if not isinstance(raw, Mapping) or set(raw) != _PAYLOAD_FIELDS:
        return None
    values: dict[str, Any] = {}
    for name in _ID_FIELDS:
        identifier = _identifier(raw.get(name))
        if identifier is None:
            return None
        values[name] = identifier
    for name in _MONTH_FIELDS:
        month = _month(raw.get(name))
        if month is None:
            return None
        values[name] = month
    initiator_sect_id = values["initiator_sect_id"]
    target_sect_id = values["target_sect_id"]
    if (
        not initiator_sect_id.isdigit()
        or not target_sect_id.isdigit()
        or initiator_sect_id == target_sect_id
        or values["initiator_avatar_id"] == values["target_avatar_id"]
        or values["initiator_institution_id"] != sect_institution_id(initiator_sect_id)
        or values["target_institution_id"] != sect_institution_id(target_sect_id)
    ):
        return None
    return values


def _grounded_source(
    decision_event: Any, aggression: Mapping[str, Any], occurred_month: int
) -> bool:
    """The decision fact that actually authored this attack, or nothing.

    A well-shaped payload naming a decision id proves nothing on its own: the
    source is resolved and checked here, so a fabricated or dangling citation,
    a decision by somebody else, and a decision that chose a different act all
    fail to ground the aggression and it simply never becomes a cause.
    """

    if not isinstance(decision_event, Event):
        return False
    payload = decision_event.causal_payload
    if not isinstance(payload, Mapping):
        return False
    decision = payload.get("decision")
    if not isinstance(decision, Mapping):
        return False
    try:
        audit = AgentDecision.from_dict(dict(decision))
    except (AttributeError, TypeError, ValueError):
        return False
    if (
        decision_event.fact_kind is not FactKind.DECISION
        or decision_event.is_story
        or payload.get("deltas") != []
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
        or str(audit.subject_id) != str(aggression["initiator_avatar_id"])
        or int(decision_event.month_stamp) > int(occurred_month)
    ):
        return False
    chosen_params = {TARGET_SELECTOR_PARAM: str(aggression["target_selector"])}
    return any(
        isinstance(step, Mapping)
        and str(step.get("action_name", "")) == INITIATING_ACTION_NAME
        and isinstance(step.get("params"), Mapping)
        and dict(step["params"]) == chosen_params
        for step in audit.chosen_chain
    )


def canonical_aggression(
    event: Any, *, lookup: Callable[[str], Event | None]
) -> tuple[Event, dict[str, Any]] | None:
    """One aggression fact, accepted only if it is canonical in every respect.

    ``lookup`` resolves the cited decision through step-local overlays and the
    event store.  It is required: the fact's own shape is never enough, so
    there is no permissive second contract that could offer a cause whose
    source was never verified.
    """

    if not isinstance(event, Event):
        return None
    aggression = avatar_aggression_payload(event)
    if aggression is None:
        return None
    related_avatars = {str(item) for item in (event.related_avatars or [])}
    related_sects = {str(item) for item in (event.related_sects or [])}
    if (
        event.event_type != DELIBERATE_ATTACK_EVENT_TYPE
        or event.fact_kind is not FactKind.OCCURRENCE
        or event.causal_origin is not CausalOrigin.ACTOR_DECISION
        or event.is_story
        or int(aggression["month"]) != int(event.month_stamp)
        or related_avatars
        != {
            str(aggression["initiator_avatar_id"]),
            str(aggression["target_avatar_id"]),
        }
        or related_sects
        != {str(aggression["initiator_sect_id"]), str(aggression["target_sect_id"])}
        or not any(
            link.relation is CausalRelation.MOTIVATED_BY
            and link.cause_event_id == str(aggression["decision_event_id"])
            for link in event.causal_links
        )
    ):
        return None
    if not _grounded_source(
        lookup(str(aggression["decision_event_id"])),
        aggression,
        int(event.month_stamp),
    ):
        return None
    return event, aggression


def _office_holder(world: Any, institution_id: str, month: int) -> Any | None:
    """The living current holder of the force-employment office, or None."""

    office = world.institutional_authority.office_for_scope(
        institution_id, AuthorityScope.FORCE_EMPLOYMENT
    )
    if (
        office is None
        or office.holder_ref is None
        or office.holder_since_month is None
        or int(office.holder_since_month) > month
    ):
        return None
    manager = getattr(world, "avatar_manager", None)
    getter = getattr(manager, "get_avatar", None)
    holder = getter(office.holder_ref.id) if callable(getter) else None
    if holder is None or bool(getattr(holder, "is_dead", False)):
        return None
    return holder


def _witnessing_institutions(
    world: Any, initiator: Any, target: Any, month: int
) -> tuple[str, ...]:
    """Only institutions whose own current office holder actually saw it.

    An ordinary member being attacked does not make the institution aware:
    personal experience is not institutional knowledge.  The office that could
    employ force must itself have been a participant or close enough to
    observe the attack, so nothing is broadcast and no institution is assumed
    to know every event involving its members.

    A non-participant holder must be able to observe *both* sides.  Observation
    is directed and radius depends on realm, so a holder who can see only the
    high-realm attacker at a distance did not witness who was struck, and must
    not be credited with knowing the attack on its own member.
    """

    sect_context = getattr(world, "sect_context", None)
    sects = (
        sect_context.get_active_sects()
        if sect_context is not None
        else (getattr(world, "existed_sects", []) or [])
    )
    participants = {str(initiator.id), str(target.id)}
    witnesses: list[str] = []
    for sect in sorted(sects, key=lambda item: int(getattr(item, "id", 0))):
        institution_id = sect_institution_id(str(sect.id))
        if not has_active_sect_institution(world, str(sect.id), current_month=month):
            continue
        holder = _office_holder(world, institution_id, month)
        if holder is None:
            continue
        if str(holder.id) in participants or (
            is_within_observation(holder, initiator)
            and is_within_observation(holder, target)
        ):
            witnesses.append(institution_id)
    return tuple(witnesses)


def record_deliberate_attack(
    world: Any, snapshot: AggressionSnapshot, *, initiator: Any, target: Any
) -> Event | None:
    """The canonical aggression fact, known only to those who actually saw it."""

    month = int(world.month_stamp)
    aggression = {
        "initiator_avatar_id": snapshot.initiator_avatar_id,
        "target_avatar_id": snapshot.target_avatar_id,
        "initiator_sect_id": snapshot.initiator_sect_id,
        "target_sect_id": snapshot.target_sect_id,
        "initiator_institution_id": sect_institution_id(snapshot.initiator_sect_id),
        "target_institution_id": sect_institution_id(snapshot.target_sect_id),
        "decision_event_id": snapshot.decision_event_id,
        "target_selector": snapshot.target_selector,
        "month": month,
    }
    event = Event(
        world.month_stamp,
        t(
            "{initiator} deliberately attacked {target}, a member of another sect.",
            initiator=str(getattr(initiator, "name", "") or snapshot.initiator_avatar_id),
            target=str(getattr(target, "name", "") or snapshot.target_avatar_id),
        ),
        related_avatars=[snapshot.initiator_avatar_id, snapshot.target_avatar_id],
        related_sects=[
            int(snapshot.initiator_sect_id),
            int(snapshot.target_sect_id),
        ],
        event_type=DELIBERATE_ATTACK_EVENT_TYPE,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "initiator_avatar_id": snapshot.initiator_avatar_id,
            "target_avatar_id": snapshot.target_avatar_id,
            "initiator_sect_id": snapshot.initiator_sect_id,
            "target_sect_id": snapshot.target_sect_id,
        },
        causal_payload={"deltas": [], _PAYLOAD_KEY: aggression},
    )
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=snapshot.decision_event_id,
            relation=CausalRelation.MOTIVATED_BY,
        )
    )
    if not snapshot.witness_institution_ids:
        # Nobody in office saw it.  The attack still happened; no institution
        # learned of it, so no institution can ever cite it as a cause.
        return event
    record_known_fact(
        world,
        event,
        snapshot.witness_institution_ids,
        channel=KnowledgeChannel.MEMBER_WITNESS,
    )
    return event


def carry_initiating_aggression(action: Any, aggression_event_id: str) -> None:
    """Tell an installed response action which initiative it is answering.

    Runtime only, on the action instance: a response is installed by the
    engine within the same step, and its material result has to be able to
    point back at the one aggression that provoked it rather than reading a
    global or minting a second fact.  Nothing here is persisted, so a
    restored save answers no initiative and links nothing.
    """

    if action is None or not str(aggression_event_id or "").strip():
        return
    setattr(action, _INITIATIVE_ATTR, str(aggression_event_id))


def initiating_aggression_event_id(action: Any) -> str:
    """The initiative this action is answering, or an empty string."""

    value = getattr(action, _INITIATIVE_ATTR, "")
    return value if isinstance(value, str) else ""


def link_response_to_initiative(event: Any, aggression_event_id: str) -> bool:
    """Point a response fact back at the initiative that provoked it.

    The aggression is the single material cause in this chain; a battle, a
    flight or a successful escape are answers to it.  Linking rather than
    re-recording is what keeps one initiative to exactly one aggression.
    """

    if not isinstance(event, Event) or not str(aggression_event_id or "").strip():
        return False
    cause_event_id = str(aggression_event_id)
    if any(
        link.cause_event_id == cause_event_id
        and link.relation is CausalRelation.RESPONSE_TO
        for link in event.causal_links
    ):
        return False
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=cause_event_id,
            relation=CausalRelation.RESPONSE_TO,
        )
    )
    return True


__all__ = [
    "AggressionSnapshot",
    "DELIBERATE_ATTACK_EVENT_TYPE",
    "INITIATING_ACTION_NAME",
    "TARGET_SELECTOR_PARAM",
    "avatar_aggression_payload",
    "canonical_aggression",
    "capture_aggression_snapshot",
    "carry_initiating_aggression",
    "initiating_aggression_event_id",
    "link_response_to_initiative",
    "record_deliberate_attack",
]
