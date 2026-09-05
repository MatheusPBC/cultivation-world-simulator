"""Bilateral negotiated cessation of a formal institutional war.

This module owns only how a war episode may be *ended by agreement*.  It never
starts a war, never grants a truce, troops, resources or any non-aggression
obligation, and it never changes anything except the ``kind`` of the canonical
relation once both sides have actually decided.

The negotiation is two independent decisions over one persisted fact:

1. an authorized sect at war may propose peace, motivated by a real canonical
   war declaration it actually knows about; the proposal persists as a typed
   factual event, not as an affordance and not as new state;
2. on a later decision cycle the counterparty independently accepts, rejects
   or maintains.  Only acceptance moves the relation, and only after both
   parties, their negotiating authority and the exact war episode have been
   revalidated against current canonical state.

Everything the negotiation needs is derived from canonical events, knowledge
and relations, so a pending proposal survives save and load with no runtime
cache anywhere in World.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import (
    DomainAffordance,
    DomainDecision,
    DomainDecisionKind,
)
from src.classes.event import Event, FactKind
from src.classes.institution import InstitutionalRelation
from src.i18n import t
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
    event_lookup,
    stale_affordance_blocked_event,
    validate_actor_decision,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    conclude_formal_war,
    negotiating_sect,
    sect_institution_id,
    sect_institution_ref,
    sect_war_relation,
)
from src.systems.institutional_memory import (
    decision_context as institutional_decision_context,
    record_known_fact,
)

PROPOSAL_DOMAIN = "institutional_peace_proposal"
RESPONSE_DOMAIN = "institutional_peace_response"
PROPOSE_ACTION = "propose_institutional_peace"
ACCEPT_ACTION = "accept_institutional_peace"
REJECT_ACTION = "reject_institutional_peace"
PROPOSED_EVENT_TYPE = "institutional_peace_proposed"
ACCEPTED_EVENT_TYPE = "institutional_peace_accepted"
REJECTED_EVENT_TYPE = "institutional_peace_rejected"
INTERPRETER_TEMPLATE = "institutional_peace_interpreter.txt"

# A proposal is answerable for this many decision cycles and then simply
# lapses.  Deriving the deadline from the live cadence at issuance time gives
# the counterparty at least one real turn: an unanswered proposal is never a
# permanent implicit refusal, and it can never be replayed forever either.
RESPONSE_CYCLES = 2
# War weariness is the only material pressure this module reads.  It is an
# existing Sect-owned counter (0-100) maintained annually from the number of
# active wars, so urgency stays a projection of canonical state.
WEARINESS_URGENCY_SCALE = 10.0

_PAYLOAD_KEY = "peace_proposal"
_ID_FIELDS = (
    "proposer_sect_id",
    "counterparty_sect_id",
    "proposer_institution_id",
    "counterparty_institution_id",
    "relation_id",
    "war_event_id",
)
_MONTH_FIELDS = ("proposal_month", "expires_month")
_PROPOSAL_FIELDS = frozenset((*_ID_FIELDS, *_MONTH_FIELDS))


@dataclass(frozen=True, slots=True)
class PeaceAffordanceContext(AffordanceContext):
    """Step-local causal evidence only; never World state and never persisted."""

    event_overlays: tuple[Event, ...] = field(default_factory=tuple)


def decision_interval_years() -> int:
    from src.utils.config import CONFIG

    return max(1, int(getattr(CONFIG.sect, "decision_interval_years", 1) or 1))


def response_window_months() -> int:
    """The window granted to a proposal issued right now."""

    return RESPONSE_CYCLES * 12 * decision_interval_years()


def _urgency(sect: Any) -> float:
    weariness = int(getattr(sect, "war_weariness", 0) or 0)
    return max(0.0, min(1.0, weariness / WEARINESS_URGENCY_SCALE))


def _month(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return int(value)


def _identifier(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        return None
    return value


def _sect_by_id(world: Any, sect_id: int | str) -> Any | None:
    context = getattr(world, "sect_context", None)
    sects = (
        context.get_active_sects()
        if context is not None
        else (getattr(world, "existed_sects", []) or [])
    )
    return next(
        (sect for sect in sects if str(getattr(sect, "id", "")) == str(sect_id)),
        None,
    )


def _sect_ids_for_institution(world: Any, institution_id: str) -> tuple[str, ...]:
    institution = world.institutional_authority.get_institution(institution_id)
    owner = getattr(institution, "owner_ref", None)
    return (str(owner.id),) if owner is not None and owner.kind == "sect" else ()


def _is_war_declaration(
    event: Any, *, sect_ids: tuple[str, str], not_after_month: int
) -> bool:
    """A war anchor must be a real, factual, bilateral declaration.

    A matching ``event_type`` alone proves nothing: a story, an interpretation
    or a non-transition carrying the same name is not a canonical war, and a
    declaration that does not name both belligerents is not this war.
    """

    if not isinstance(event, Event):
        return False
    related = {str(item) for item in (event.related_sects or [])}
    return (
        event.event_type == WAR_DECLARED_EVENT_TYPE
        and event.fact_kind is FactKind.STATE_TRANSITION
        and event.causal_origin is not CausalOrigin.LLM_INTERPRETATION
        and not event.is_story
        and set(sect_ids) <= related
        and int(event.month_stamp) <= int(not_after_month)
    )


def war_episode_anchor(
    world: Any,
    sect_a_id: int | str,
    sect_b_id: int | str,
    *,
    lookup: Callable[[str], Event | None],
) -> Event | None:
    """The declaration event that started the war episode running right now.

    Identity is the event, not the month: a war concluded and re-declared in
    the same month yields a different anchor, so a proposal about the earlier
    episode can never resolve the later one.  Resolution is fail-closed and
    walks the evidence newest-first: unresolvable evidence stops the search
    instead of silently selecting an older, already superseded declaration,
    and a war whose declaration was never recorded as a typed canonical fact
    simply has no anchor and therefore no option.  Nothing is backfilled.
    """

    relation = sect_war_relation(world, sect_a_id, sect_b_id)
    if relation is None:
        return None
    sect_ids = (str(sect_a_id), str(sect_b_id))
    for event_id in reversed(relation.evidence_event_ids):
        event = lookup(str(event_id))
        if event is None:
            return None
        if _is_war_declaration(
            event, sect_ids=sect_ids, not_after_month=relation.since_month
        ):
            return event
    return None


def peace_proposal_payload(event: Any) -> dict[str, Any] | None:
    """The proposal carried by a fact, or None if it is not a valid one.

    Every field is validated here so a malformed or hand-written payload can
    only produce "no options"; it can never raise inside an annual phase.
    """

    if not isinstance(event, Event):
        return None
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get(_PAYLOAD_KEY)
    if not isinstance(raw, Mapping) or set(raw) != _PROPOSAL_FIELDS:
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
    proposer_id = values["proposer_sect_id"]
    counterparty_id = values["counterparty_sect_id"]
    if (
        not proposer_id.isdigit()
        or not counterparty_id.isdigit()
        or proposer_id == counterparty_id
        or values["proposer_institution_id"] != sect_institution_id(proposer_id)
        or values["counterparty_institution_id"]
        != sect_institution_id(counterparty_id)
        or values["relation_id"]
        != InstitutionalRelation.id_for(
            values["proposer_institution_id"],
            values["counterparty_institution_id"],
        )
        or values["expires_month"] < values["proposal_month"]
    ):
        return None
    return values


def _canonical_proposal_fact(event: Any) -> tuple[Event, dict[str, Any]] | None:
    """One proposal event, accepted only if it is canonical in every respect."""

    if not isinstance(event, Event):
        return None
    proposal = peace_proposal_payload(event)
    if proposal is None:
        return None
    related = {str(item) for item in (event.related_sects or [])}
    if (
        event.event_type != PROPOSED_EVENT_TYPE
        or event.fact_kind is not FactKind.OCCURRENCE
        or event.causal_origin is not CausalOrigin.ACTOR_DECISION
        or event.is_story
        or int(proposal["proposal_month"]) != int(event.month_stamp)
        or related
        != {
            str(proposal["proposer_sect_id"]),
            str(proposal["counterparty_sect_id"]),
        }
    ):
        return None
    return event, proposal


def canonical_proposal(
    event_id: str, *, lookup: Callable[[str], Event | None]
) -> tuple[Event, dict[str, Any]] | None:
    """Resolve a proposal through trusted evidence only.

    The caller's own object is never its own proof: whatever was handed in as
    a trigger is re-resolved from the event store or from explicit step-local
    overlays, so a forged object reusing a known proposal id resolves to the
    real fact or to nothing at all.
    """

    return _canonical_proposal_fact(lookup(str(event_id)))


def _answers_proposal(event: Any) -> str | None:
    """The proposal id one canonical outcome fact actually consumed."""

    if not isinstance(event, Event) or event.is_story:
        return None
    expected_kind = (
        FactKind.STATE_TRANSITION
        if event.event_type == ACCEPTED_EVENT_TYPE
        else FactKind.OCCURRENCE
        if event.event_type == REJECTED_EVENT_TYPE
        else None
    )
    if (
        expected_kind is None
        or event.fact_kind is not expected_kind
        or event.causal_origin is not CausalOrigin.ACTOR_DECISION
    ):
        return None
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    answered_id = _identifier(payload.get("proposal_event_id"))
    if answered_id is None:
        return None
    # The link is what makes it an answer to *this* proposal rather than a
    # typed event merely naming it.
    return (
        answered_id
        if any(
            link.relation is CausalRelation.RESPONSE_TO
            and link.cause_event_id == answered_id
            for link in event.causal_links
        )
        else None
    )


def _sect_institution_ids(world: Any) -> frozenset[str]:
    context = getattr(world, "sect_context", None)
    sects = (
        context.get_active_sects()
        if context is not None
        else (getattr(world, "existed_sects", []) or [])
    )
    return frozenset(sect_institution_id(str(sect.id)) for sect in sects)


def _negotiation_facts(
    world: Any,
    *,
    institution_ids: frozenset[str],
    overlays: tuple[Event, ...],
) -> tuple[dict[str, tuple[Event, dict[str, Any]]], set[str]]:
    """Every canonical proposal and answer these institutions actually know.

    Discovery goes through the knowledge owner rather than a month window:
    both parties record every proposal and every answer as a known fact, and
    knowledge is saved state, so the same negotiations reappear after a reload
    and no configuration change can hide a proposal that is still valid.
    """

    lookup = event_lookup(world, overlays)
    candidate_ids: list[str] = [
        fact.event_id
        for fact in world.institutional_knowledge.known_facts.values()
        if fact.institution_id in institution_ids
    ]
    candidate_ids.extend(event.id for event in overlays if isinstance(event, Event))
    proposals: dict[str, tuple[Event, dict[str, Any]]] = {}
    answered: set[str] = set()
    for event_id in dict.fromkeys(candidate_ids):
        event = lookup(str(event_id))
        if event is None:
            continue
        found = _canonical_proposal_fact(event)
        if found is not None:
            proposals[found[0].id] = found
            continue
        answered_id = _answers_proposal(event)
        if answered_id is not None:
            answered.add(answered_id)
    return proposals, answered


def _parties_of(proposal: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(
        (
            str(proposal["proposer_institution_id"]),
            str(proposal["counterparty_institution_id"]),
        )
    )


def _proposal_matches_current_war(
    world: Any,
    proposal: Mapping[str, Any],
    *,
    lookup: Callable[[str], Event | None],
) -> bool:
    relation = sect_war_relation(
        world,
        str(proposal["proposer_sect_id"]),
        str(proposal["counterparty_sect_id"]),
    )
    if relation is None or relation.id != str(proposal["relation_id"]):
        return False
    anchor = war_episode_anchor(
        world,
        str(proposal["proposer_sect_id"]),
        str(proposal["counterparty_sect_id"]),
        lookup=lookup,
    )
    return anchor is not None and anchor.id == str(proposal["war_event_id"])


def _is_open(
    world: Any,
    proposal_event: Event,
    proposal: Mapping[str, Any],
    *,
    overlays: tuple[Event, ...],
) -> bool:
    """Every condition that keeps one proposal answerable, in one place.

    The deadline is the one frozen into the proposal itself, never a value
    recomputed from a configuration that may have changed since issuance.
    """

    if int(world.month_stamp) > int(proposal["expires_month"]):
        return False
    _proposals, answered = _negotiation_facts(
        world, institution_ids=_parties_of(proposal), overlays=overlays
    )
    if proposal_event.id in answered:
        return False
    return _proposal_matches_current_war(
        world, proposal, lookup=event_lookup(world, overlays)
    )


def open_peace_proposals(
    world: Any, *, overlays: tuple[Event, ...] = ()
) -> list[tuple[Event, dict[str, Any]]]:
    """Every canonical proposal still awaiting an answer, oldest first.

    Derived from knowledge, relations and outcome facts, never from a cached
    pending list, so a reloaded world sees exactly the same open negotiations.
    """

    proposals, answered = _negotiation_facts(
        world, institution_ids=_sect_institution_ids(world), overlays=overlays
    )
    lookup = event_lookup(world, overlays)
    open_items = [
        (event, proposal)
        for event, proposal in proposals.values()
        if event.id not in answered
        and int(world.month_stamp) <= int(proposal["expires_month"])
        and _proposal_matches_current_war(world, proposal, lookup=lookup)
    ]
    return sorted(open_items, key=lambda item: (int(item[0].month_stamp), item[0].id))


def proposal_affordances(context: AffordanceContext):
    """Peace options for one authorized sect, one per known live war."""

    world = context.world
    if context.actor_ref.kind != "sect":
        return ()
    proposer_id = str(context.actor_ref.id)
    proposer = _sect_by_id(world, proposer_id)
    if proposer is None or not negotiating_sect(world, proposer_id):
        return ()
    overlays = tuple(getattr(context, "event_overlays", ()) or ())
    lookup = event_lookup(world, overlays)
    open_episodes = {
        str(proposal["war_event_id"])
        for _event, proposal in open_peace_proposals(world, overlays=overlays)
    }
    proposer_institution_id = sect_institution_id(proposer_id)
    options: list[DomainAffordance] = []
    for relation in sorted(
        world.institutional_relations.relations.values(), key=lambda item: item.id
    ):
        if proposer_institution_id not in (
            relation.institution_a_id,
            relation.institution_b_id,
        ):
            continue
        counterparty_institution_id = (
            relation.institution_b_id
            if relation.institution_a_id == proposer_institution_id
            else relation.institution_a_id
        )
        for counterparty_id in _sect_ids_for_institution(
            world, counterparty_institution_id
        ):
            if _sect_by_id(world, counterparty_id) is None:
                continue
            anchor = war_episode_anchor(
                world, proposer_id, counterparty_id, lookup=lookup
            )
            if anchor is None:
                # No canonical war declaration means no source, hence no
                # option and no interpreter call.
                continue
            if not world.institutional_knowledge.contains(
                proposer_institution_id, anchor.id
            ):
                # A sect may only act on a war it actually knows about.
                continue
            if anchor.id in open_episodes:
                # One outstanding proposal per war episode, whoever opened it.
                continue
            if not negotiating_sect(world, counterparty_id):
                continue
            options.append(
                DomainAffordance(
                    domain=context.domain,
                    actor_ref=context.actor_ref,
                    action_kind=PROPOSE_ACTION,
                    target_refs=(sect_institution_ref(counterparty_id),),
                    parameters={
                        "proposer_sect_id": proposer_id,
                        "counterparty_sect_id": counterparty_id,
                        "proposer_institution_id": proposer_institution_id,
                        "counterparty_institution_id": counterparty_institution_id,
                        "relation_id": relation.id,
                        "war_event_id": anchor.id,
                    },
                    urgency=_urgency(proposer),
                    motivation_event_ids=(anchor.id,),
                )
            )
    return tuple(options)


def response_affordances(context: AffordanceContext):
    """The counterparty's own accept and reject options for one proposal.

    The proposal is re-resolved from trusted evidence and its openness is
    rechecked here rather than trusted from whoever composed the cycle, so a
    directly composed context can neither answer an expired or already
    answered proposal nor smuggle in a forged one.
    """

    world = context.world
    if context.actor_ref.kind != "sect":
        return ()
    overlays = tuple(getattr(context, "event_overlays", ()) or ())
    resolved = canonical_proposal(
        getattr(context.trigger_event, "id", ""),
        lookup=event_lookup(world, overlays),
    )
    if resolved is None:
        return ()
    proposal_event, proposal = resolved
    if peace_proposal_payload(context.trigger_event) != proposal:
        return ()
    counterparty_id = str(proposal["counterparty_sect_id"])
    proposer_id = str(proposal["proposer_sect_id"])
    counterparty = _sect_by_id(world, counterparty_id)
    if (
        counterparty is None
        or context.actor_ref != sect_institution_ref(counterparty_id)
        or not negotiating_sect(world, counterparty_id)
        or not negotiating_sect(world, proposer_id)
        or not _is_open(world, proposal_event, proposal, overlays=overlays)
        or not world.institutional_knowledge.contains(
            str(proposal["counterparty_institution_id"]), proposal_event.id
        )
    ):
        return ()
    parameters = {**proposal, "proposal_event_id": proposal_event.id}
    return tuple(
        DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind=action_kind,
            target_refs=(sect_institution_ref(proposer_id),),
            parameters=parameters,
            urgency=urgency,
            motivation_event_ids=(proposal_event.id,),
        )
        for action_kind, urgency in (
            # Accepting is ranked by the counterparty's own material war
            # pressure.  Refusing carries none, so the deterministic fallback
            # never rejects on its own: it accepts under real pressure and
            # otherwise maintains, leaving the proposal open.
            (ACCEPT_ACTION, _urgency(counterparty)),
            (REJECT_ACTION, 0.0),
        )
    )


def _linked(event: Event, pairs: tuple[tuple[str, CausalRelation], ...]) -> Event:
    event.causal_links.extend(
        CausalLink(event_id=event.id, cause_event_id=cause_id, relation=relation)
        for cause_id, relation in pairs
        if cause_id
    )
    return event


def _parties(proposal: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(proposal["proposer_institution_id"]),
        str(proposal["counterparty_institution_id"]),
    )


def _sect_name(world: Any, sect_id: str) -> str:
    sect = _sect_by_id(world, sect_id)
    return str(getattr(sect, "name", "") or sect_id)


def _names(world: Any, proposal: Mapping[str, Any]) -> dict[str, str]:
    return {
        "proposer": _sect_name(world, str(proposal["proposer_sect_id"])),
        "counterparty": _sect_name(world, str(proposal["counterparty_sect_id"])),
    }


def _related_sects(proposal: Mapping[str, Any]) -> list[int]:
    return [
        int(proposal["proposer_sect_id"]),
        int(proposal["counterparty_sect_id"]),
    ]


def _execute_proposal(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    **_: Any,
) -> Event:
    world = context.world
    validate_actor_decision(decision_event, context, option, label="peace")
    params = dict(option.parameters)
    if not negotiating_sect(
        world, str(params["proposer_sect_id"])
    ) or not negotiating_sect(world, str(params["counterparty_sect_id"])):
        raise StaleAffordanceError("negotiating authority changed")
    proposal = {
        **params,
        "proposal_month": int(world.month_stamp),
        # The deadline is fixed at issuance: a later configuration change must
        # not silently extend or retract a proposal already on the table.
        "expires_month": int(world.month_stamp) + response_window_months(),
    }
    event = Event(
        world.month_stamp,
        t(
            "{proposer} proposed to {counterparty} that the war between them be ended.",
            **_names(world, proposal),
        ),
        related_sects=_related_sects(proposal),
        event_type=PROPOSED_EVENT_TYPE,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "proposer_sect_id": str(params["proposer_sect_id"]),
            "counterparty_sect_id": str(params["counterparty_sect_id"]),
            "war_event_id": str(params["war_event_id"]),
            "affordance_id": option.id,
        },
        causal_payload={"deltas": [], _PAYLOAD_KEY: proposal},
    )
    _linked(
        event,
        (
            (decision_event.id, CausalRelation.MOTIVATED_BY),
            (str(params["war_event_id"]), CausalRelation.RESPONSE_TO),
        ),
    )
    # Only the two negotiating parties learn of the proposal; nothing here is
    # broadcast to the rest of the world.
    record_known_fact(world, event, _parties(proposal))
    return event


def _revalidated_proposal(
    context: AffordanceContext,
    option: DomainAffordance,
    decision_event: Event | None,
) -> tuple[dict[str, Any], Event]:
    world = context.world
    validate_actor_decision(decision_event, context, option, label="peace")
    params = dict(option.parameters)
    claimed_id = str(params.pop("proposal_event_id", ""))
    overlays = tuple(getattr(context, "event_overlays", ()) or ())
    resolved = canonical_proposal(
        claimed_id, lookup=event_lookup(world, overlays)
    )
    if (
        resolved is None
        or claimed_id != str(getattr(context.trigger_event, "id", ""))
        or resolved[1] != params
        or peace_proposal_payload(context.trigger_event) != resolved[1]
    ):
        raise StaleAffordanceError("peace option does not match a canonical proposal")
    proposal_event, proposal = resolved
    if not negotiating_sect(
        world, str(proposal["proposer_sect_id"])
    ) or not negotiating_sect(world, str(proposal["counterparty_sect_id"])):
        raise StaleAffordanceError("negotiating authority changed")
    if not _is_open(world, proposal_event, proposal, overlays=overlays):
        raise StaleAffordanceError(
            "the proposal expired, was already answered, or names another war"
        )
    return proposal, proposal_event


def _execute_acceptance(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    **_: Any,
) -> Event:
    world = context.world
    proposal, proposal_event = _revalidated_proposal(context, option, decision_event)
    before = sect_war_relation(
        world,
        str(proposal["proposer_sect_id"]),
        str(proposal["counterparty_sect_id"]),
    )
    if before is None:
        raise StaleAffordanceError("the war is no longer current")
    event = Event(
        world.month_stamp,
        t(
            "{proposer} and {counterparty} agreed to end the war between them.",
            **_names(world, proposal),
        ),
        related_sects=_related_sects(proposal),
        is_major=True,
        event_type=ACCEPTED_EVENT_TYPE,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "proposer_sect_id": str(proposal["proposer_sect_id"]),
            "counterparty_sect_id": str(proposal["counterparty_sect_id"]),
            "war_event_id": str(proposal["war_event_id"]),
            "affordance_id": option.id,
        },
    )
    after = conclude_formal_war(
        world,
        str(proposal["proposer_sect_id"]),
        str(proposal["counterparty_sect_id"]),
        current_month=int(world.month_stamp),
        evidence_event_ids=(event.id,),
    )
    deltas = [
        StateDelta(
            event_id=event.id,
            owner_kind="institutional_relation",
            owner_id=after.id,
            aspect=aspect,
            before=before_value,
            after=after_value,
        ).to_dict()
        for aspect, before_value, after_value in (
            ("kind", before.kind.value, after.kind.value),
            ("since_month", str(before.since_month), str(after.since_month)),
            (
                "evidence_event_ids",
                ",".join(before.evidence_event_ids),
                ",".join(after.evidence_event_ids),
            ),
        )
        if before_value != after_value
    ]
    event.causal_payload = {
        "deltas": deltas,
        _PAYLOAD_KEY: proposal,
        "proposal_event_id": proposal_event.id,
    }
    _linked(
        event,
        (
            (decision_event.id, CausalRelation.MOTIVATED_BY),
            (proposal_event.id, CausalRelation.RESPONSE_TO),
            (str(proposal["war_event_id"]), CausalRelation.RESOLVES),
        ),
    )
    record_known_fact(world, event, _parties(proposal))
    return event


def _execute_rejection(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event: Event | None = None,
    **_: Any,
) -> Event:
    world = context.world
    proposal, proposal_event = _revalidated_proposal(context, option, decision_event)
    event = Event(
        world.month_stamp,
        t(
            "{counterparty} refused to end the war with {proposer}, and the war goes on.",
            **_names(world, proposal),
        ),
        related_sects=_related_sects(proposal),
        event_type=REJECTED_EVENT_TYPE,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "proposer_sect_id": str(proposal["proposer_sect_id"]),
            "counterparty_sect_id": str(proposal["counterparty_sect_id"]),
            "war_event_id": str(proposal["war_event_id"]),
            "affordance_id": option.id,
        },
        causal_payload={
            "deltas": [],
            _PAYLOAD_KEY: proposal,
            "proposal_event_id": proposal_event.id,
            "outcome": "rejected",
        },
    )
    _linked(
        event,
        (
            (decision_event.id, CausalRelation.MOTIVATED_BY),
            (proposal_event.id, CausalRelation.RESPONSE_TO),
        ),
    )
    record_known_fact(world, event, _parties(proposal))
    return event


for _domain, _provider in (
    (PROPOSAL_DOMAIN, proposal_affordances),
    (RESPONSE_DOMAIN, response_affordances),
):
    DOMAIN_AFFORDANCES.register_provider(_domain, _provider)

for _action, _executor in (
    (PROPOSE_ACTION, _execute_proposal),
    (ACCEPT_ACTION, _execute_acceptance),
    (REJECT_ACTION, _execute_rejection),
):
    DOMAIN_AFFORDANCES.register_executor(_action, _executor)


InjectedDecisions = (
    Mapping[str, DomainDecision]
    | Callable[[str, str, Event], DomainDecision | None]
    | None
)


def _injected(
    injected_decisions: InjectedDecisions,
    domain: str,
    sect_id: str,
    trigger_event: Event,
) -> DomainDecision | None:
    if injected_decisions is None:
        return None
    if callable(injected_decisions):
        return injected_decisions(domain, sect_id, trigger_event)
    return injected_decisions.get(f"{domain}:{sect_id}")


async def _decide_and_execute(
    world: Any,
    *,
    domain: str,
    sect: Any,
    trigger_event: Event,
    overlays: tuple[Event, ...],
    task_name: str,
    role: str,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None,
    injected_decisions: InjectedDecisions,
    force_rule: bool,
    budget: CausalBudget | None,
) -> list[Event]:
    sect_id = str(sect.id)
    context = PeaceAffordanceContext(
        world,
        domain,
        sect_institution_ref(sect_id),
        trigger_event,
        None,
        overlays,
    )
    options = DOMAIN_AFFORDANCES.compose(context)
    if not options:
        # No grounded source means no option and no interpreter call at all.
        return []
    if budget is not None and not budget.consume_interpreter_call():
        return []
    decision, decision_event = await interpret_domain_affordances(
        world,
        domain=domain,
        actor_ref=context.actor_ref,
        actor_label=str(getattr(sect, "name", sect_id)),
        trigger_event=trigger_event,
        affordances=options,
        task_name=task_name,
        template_name=INTERPRETER_TEMPLATE,
        extra_context={
            "role": role,
            "institution": institutional_decision_context(
                world,
                sect_institution_id(sect_id),
                event_overlays=(trigger_event, *overlays),
            ),
        },
        llm_call=llm_call,
        force_rule=force_rule,
        injected_decision=_injected(
            injected_decisions, domain, sect_id, trigger_event
        ),
    )
    events = [decision_event]
    if decision.decision is not DomainDecisionKind.ACT:
        # Maintaining is neither an answer nor a refusal: the proposal stays
        # open for the remainder of its own window.
        return events
    if budget is not None and not budget.consume_domain_mutation():
        return events
    try:
        events.append(
            DOMAIN_AFFORDANCES.execute(
                context,
                decision.selected_affordance_id or "",
                decision_event=decision_event,
            )
        )
    except StaleAffordanceError:
        # A stale, superseded or forged selection changes nothing at all.
        events.append(
            stale_affordance_blocked_event(
                context,
                decision_event_id=decision_event.id,
                selected_affordance_id=decision.selected_affordance_id or "",
            )
        )
    return events


def _proposal_trigger(
    world: Any, sect: Any, overlays: tuple[Event, ...]
) -> Event | None:
    """The known war declaration used as this sect's decision trigger.

    It is always a canonical war fact resolved through the same fail-closed
    anchor rule as the options themselves, so a cycle with no such known fact
    produces no decision and no interpreter call.
    """

    lookup = event_lookup(world, overlays)
    proposer_institution_id = sect_institution_id(str(sect.id))
    candidates = [
        anchor
        for relation in world.institutional_relations.relations.values()
        if proposer_institution_id
        in (relation.institution_a_id, relation.institution_b_id)
        for counterparty_id in _sect_ids_for_institution(
            world,
            relation.institution_b_id
            if relation.institution_a_id == proposer_institution_id
            else relation.institution_a_id,
        )
        if (
            anchor := war_episode_anchor(
                world, str(sect.id), counterparty_id, lookup=lookup
            )
        )
        is not None
        and world.institutional_knowledge.contains(proposer_institution_id, anchor.id)
    ]
    return min(candidates, key=lambda item: item.id) if candidates else None


async def process_institutional_peace_negotiation(
    world: Any,
    *,
    event_overlays: tuple[Event, ...] = (),
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    injected_decisions: InjectedDecisions = None,
    force_rule: bool = False,
    budget: CausalBudget | None = None,
) -> list[Event]:
    """One decision cycle of peace negotiation for every warring sect.

    Answers come first, so a proposal opened in this cycle is never resolved
    by the cycle that produced it: the counterparty always gets its own,
    independent turn, which is also what makes a pending proposal outlive a
    save and load with nothing cached in World.
    """

    budget = budget or CausalBudget.from_world(world)
    overlays = tuple(event_overlays)
    produced: list[Event] = []

    for proposal_event, proposal in open_peace_proposals(world, overlays=overlays):
        counterparty = _sect_by_id(world, str(proposal["counterparty_sect_id"]))
        if counterparty is None:
            continue
        events = await _decide_and_execute(
            world,
            domain=RESPONSE_DOMAIN,
            sect=counterparty,
            trigger_event=proposal_event,
            overlays=overlays,
            task_name="institutional_peace_response_interpreter",
            role="counterparty",
            llm_call=llm_call,
            injected_decisions=injected_decisions,
            force_rule=force_rule,
            budget=budget,
        )
        produced.extend(events)
        overlays = (*overlays, *events)

    sect_context = getattr(world, "sect_context", None)
    active_sects = (
        sect_context.get_active_sects()
        if sect_context is not None
        else (getattr(world, "existed_sects", []) or [])
    )
    for sect in sorted(active_sects, key=lambda item: int(getattr(item, "id", 0))):
        trigger = _proposal_trigger(world, sect, overlays)
        if trigger is None:
            continue
        events = await _decide_and_execute(
            world,
            domain=PROPOSAL_DOMAIN,
            sect=sect,
            trigger_event=trigger,
            overlays=overlays,
            task_name="institutional_peace_proposal_interpreter",
            role="proposer",
            llm_call=llm_call,
            injected_decisions=injected_decisions,
            force_rule=force_rule,
            budget=budget,
        )
        produced.extend(events)
        overlays = (*overlays, *events)
    return produced


__all__ = [
    "ACCEPTED_EVENT_TYPE",
    "ACCEPT_ACTION",
    "PROPOSAL_DOMAIN",
    "PROPOSED_EVENT_TYPE",
    "PROPOSE_ACTION",
    "PeaceAffordanceContext",
    "REJECTED_EVENT_TYPE",
    "REJECT_ACTION",
    "RESPONSE_DOMAIN",
    "open_peace_proposals",
    "peace_proposal_payload",
    "process_institutional_peace_negotiation",
    "proposal_affordances",
    "response_affordances",
    "response_window_months",
    "war_episode_anchor",
]
