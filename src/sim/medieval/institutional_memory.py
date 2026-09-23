"""Read-only relevance of canonical facts an institution already knows.

KnowledgeState owns whether an institution knows a fact; RelationsState owns
which known facts are still active memories. This module derives everything
else on read: effective salience decays with time alone, and an institutional
view of another institution is recomposed from the observer's own memories.

Nothing here mutates state, schedules work, draws randomness or stores a
score. The only engine-owned historical weight used in V1 is the commitment
breach; relative scale and institutional change have no material owner yet,
and an identity anchor does not exist, so its impact is zero by absence.
"""

import json

from src.classes.governance.diplomacy import InstitutionalMemory, institutional_memory_id
from src.classes.mechanical_language import EntityRef

from .economy import _delta


MEMORY_SPAN_DAYS = 360
FULFILLMENT_VIEW = 3
BRIBERY_VIEW = -3
BREACH_VIEW = -4
REPUDIATION_VIEW = -6
REMEDIATION_VIEW = 2
REFUSAL_VIEW = -2


def next_event_id(world):
    """The ID ``record_event`` will assign, so a receipt can name its memories."""
    return f"event:{len(world.events) + 1}"


def memory_creation_deltas(world, institution_refs, event_id=None):
    """Deltas that create memories inside the very fact being recorded."""
    event_id = event_id or next_event_id(world)
    return tuple(_delta("institutional_memory", institutional_memory_id(ref, event_id),
                        "recorded_day", None, world.clock.absolute_day)
                 for ref in institution_refs)


def apply_memory_creation(world, institution_refs, event):
    """Register the memories the given fact just declared."""
    created = []
    for ref in institution_refs:
        memory = InstitutionalMemory(id=institutional_memory_id(ref, event.id), institution_ref=ref,
                                     event_id=event.id, recorded_day=event.day, last_reinforced_day=event.day)
        world.relations.memories[memory.id] = memory
        created.append(memory)
    return tuple(created)


def reinforcement_deltas(world, memories):
    """Deltas that move a memory's reinforcement day inside a later fact."""
    return tuple(_delta("institutional_memory", memory.id, "last_reinforced_day",
                        memory.last_reinforced_day, world.clock.absolute_day)
                 for memory in memories)


def apply_reinforcement(world, memories, event):
    for memory in memories:
        world.relations.memories[memory.id] = memory.model_copy(update={"last_reinforced_day": event.day})


def memories_of(world, institution_ref, event_id):
    """The institution's memory of one canonical fact, if it keeps one."""
    return world.relations.memories.get(institutional_memory_id(institution_ref, event_id))


def effective_salience(world, memory):
    """Permille of the original weight still active today; pure in the day."""
    age = world.clock.absolute_day - memory.last_reinforced_day
    if age < 0:
        return 0
    return max(0, 1000 - (1000 * age) // MEMORY_SPAN_DAYS)


def _remembered_obligation(world, memory, events):
    event = events.get(memory.event_id)
    if event is None:
        return None, None, None
    for delta in event.deltas:
        if delta.owner_kind != "obligation":
            continue
        obligation = world.relations.obligations.get(delta.owner_id)
        if obligation is None:
            continue
        proposal = world.relations.proposals.get(obligation.proposal_id)
        clause = proposal.clauses[obligation.clause_index] if proposal is not None else None
        # Every negotiated term is remembered through the same evidence: a
        # concluded obligation whose debtor and creditor are named by the
        # canonical clause. Assets remain owned by their material owners.
        # The proposal itself is also returned so a caller can tell a bribery
        # term apart from an ordinary negotiated one without a second owner.
        if clause is not None:
            return event, clause, proposal
    return None, None, None


def _remembered_refusal(world, memory, events):
    """Return the refused provider for a remembered aid request.

    A refusal has no obligation to inspect: the canonical request event names
    its requester and provider, while the response event remains the factual
    memory anchor.  Only the requester receives this social reading; the
    provider's own decision is not turned into an automatic grievance against
    itself.
    """
    event = events.get(memory.event_id)
    if event is None or event.event_type != "institutional_aid_rejected":
        return None, None
    request = next((candidate for link in event.causal_links
                    for candidate in events.values()
                    if candidate.id == link.cause_event_id
                    and candidate.event_type == "institutional_aid_requested"), None)
    if request is None:
        return None, None
    provider_payload = next((delta.after for delta in request.deltas
                             if delta.owner_kind == "aid_request" and delta.aspect == "provider_ref"), None)
    try:
        provider = EntityRef.from_dict(json.loads(provider_payload)) if isinstance(provider_payload, str) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        provider = None
    return event, provider


def aid_evidence(world, observer_ref):
    """Directions this observer remembers, with the facts behind them.

    The historical name is retained for the existing projection contract; the
    evidence now covers every concluded bilateral obligation, not only aid.
    Bribery receipts remain evidence in this directional index; the view layer
    assigns them their own weight rather than treating them as fulfillment.
    """
    events = world.event_index()
    directions = {}
    for memory in world.relations.memories_for(observer_ref):
        event, clause, proposal = _remembered_obligation(world, memory, events)
        if clause is not None and clause.creditor_ref == observer_ref:
            if event.event_type in {"commitment_fulfilled", "institutional_aid_fulfilled",
                                    "commitment_breached", "institutional_aid_remediated",
                                    "payment_obligation_remediated"}:
                directions.setdefault(clause.debtor_ref, []).append(memory.event_id)
            continue
        refusal, provider = _remembered_refusal(world, memory, events)
        if refusal is not None and provider is not None:
            directions.setdefault(provider, []).append(memory.event_id)
    return tuple((subject, tuple(sorted(event_ids))) for subject, event_ids in
                 sorted(directions.items(), key=lambda item: (item[0].kind, item[0].id)))


def institutional_views(world, observer_ref):
    """Known directional readings, composed from this observer's memories.

    ``KnowledgeState`` remains the privacy boundary: a memory without a
    notice for ``observer_ref`` is not exposed to a decision context, even if
    an invalid or partially assembled in-memory world happens to contain it.
    The returned tuples are a read model only; no relation score or planner
    state is stored.
    """
    known_event_ids = {
        notice.event_id
        for notice in world.knowledge.notices.values()
        if notice.recipient_ref == observer_ref
    }
    known_event_ids.update(
        notice.event_id
        for notice in world.knowledge.institutional_aid_notices.values()
        if notice.recipient_ref == observer_ref
    )
    known_directions = tuple(
        (subject, event_ids)
        for subject, event_ids in aid_evidence(world, observer_ref)
        if set(event_ids) <= known_event_ids
    )
    return tuple(
        (subject, institutional_view(world, observer_ref, subject), event_ids)
        for subject, event_ids in known_directions
    )


def institutional_view(world, observer_ref, subject_ref):
    """Directional reading of one institution by another, from memory alone.

    Only the creditor of a breached aid obligation carries the breach, and only
    its own remediation memory offsets it. The debtor gains no artificial
    penalty for having been wronged by nobody.
    """
    return sum(weight * effective_salience(world, memory) // 1000
               for memory, weight in _view_entries(world, observer_ref, subject_ref))


def _view_entries(world, observer_ref, subject_ref):
    events = world.event_index()
    entries = []
    for memory in world.relations.memories_for(observer_ref):
        event, clause, proposal = _remembered_obligation(world, memory, events)
        if clause is None or clause.debtor_ref != subject_ref or clause.creditor_ref != observer_ref:
            refusal, provider = _remembered_refusal(world, memory, events)
            if refusal is not None and provider == subject_ref:
                entries.append((memory, REFUSAL_VIEW))
            continue
        if proposal is not None and proposal.proposal_kind == "bribery":
            # A paid bribe is a material fact remembered by both parties, but
            # it is never read as an honored public/institutional commitment:
            # it keeps the same directional machine (only the paid party
            # reads the payer, by the same debtor/creditor match above) with
            # its own, deliberately negative, qualitative weight instead of
            # FULFILLMENT_VIEW or the generic commitment_fulfilled lookup.
            if event.event_type == "commitment_fulfilled":
                entries.append((memory, BRIBERY_VIEW))
            continue
        weight = {"commitment_fulfilled": FULFILLMENT_VIEW,
                  "institutional_aid_fulfilled": FULFILLMENT_VIEW,
                  "institutional_aid_remediated": REMEDIATION_VIEW,
                  "payment_obligation_remediated": REMEDIATION_VIEW}.get(event.event_type, 0)
        if event.event_type == "commitment_breached":
            deliberate = any(
                (cause := next((candidate for candidate in events.values()
                                if candidate.id == link.cause_event_id), None)) is not None
                and cause.fact_kind.value == "decision"
                and cause.decision is not None
                and cause.decision.get("action") == "repudiate_obligation"
                for link in event.causal_links
            )
            weight = REPUDIATION_VIEW if deliberate else BREACH_VIEW
        if weight:
            entries.append((memory, weight))
    return tuple(entries)
