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

from src.classes.governance.diplomacy import InstitutionalMemory, institutional_memory_id

from .economy import _delta


MEMORY_SPAN_DAYS = 360
BREACH_VIEW = -4
REMEDIATION_VIEW = 2


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
        return None, None
    for delta in event.deltas:
        if delta.owner_kind != "obligation":
            continue
        obligation = world.relations.obligations.get(delta.owner_id)
        if obligation is None:
            continue
        proposal = world.relations.proposals.get(obligation.proposal_id)
        clause = proposal.clauses[obligation.clause_index] if proposal is not None else None
        # Aid and reciprocal supply are remembered through the same evidence:
        # a material delivery that was promised to a named creditor.
        if clause is not None and clause.kind == "resource_transfer":
            return event, clause
    return None, None


def aid_evidence(world, observer_ref):
    """Directions this observer actually remembers, with the facts behind them.

    Only aid memories that name a debtor produce a direction; there is no
    generic social graph here and no reading without its own evidence.
    """
    events = {event.id: event for event in world.events}
    directions = {}
    for memory in world.relations.memories_for(observer_ref):
        event, clause = _remembered_obligation(world, memory, events)
        if clause is None or clause.creditor_ref != observer_ref:
            continue
        if event.event_type in {"commitment_breached", "institutional_aid_remediated"}:
            directions.setdefault(clause.debtor_ref, []).append(memory.event_id)
    return tuple((subject, tuple(sorted(event_ids))) for subject, event_ids in
                 sorted(directions.items(), key=lambda item: (item[0].kind, item[0].id)))


def institutional_view(world, observer_ref, subject_ref):
    """Directional reading of one institution by another, from memory alone.

    Only the creditor of a breached aid obligation carries the breach, and only
    its own remediation memory offsets it. The debtor gains no artificial
    penalty for having been wronged by nobody.
    """
    events = {event.id: event for event in world.events}
    total = 0
    for memory in world.relations.memories_for(observer_ref):
        event, clause = _remembered_obligation(world, memory, events)
        if clause is None or clause.debtor_ref != subject_ref or clause.creditor_ref != observer_ref:
            continue
        weight = {"commitment_breached": BREACH_VIEW,
                  "institutional_aid_remediated": REMEDIATION_VIEW}.get(event.event_type, 0)
        if weight:
            total += weight * effective_salience(world, memory) // 1000
    return total
