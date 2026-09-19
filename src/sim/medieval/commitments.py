"""Fulfillment delegates material changes; deadlines record consequences only."""
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority
from .economy import _delta, transfer_money
from .events import record_event
from .diplomacy import require_decision, disclose
from .institutional_memory import apply_memory_creation, memory_creation_deltas
from .teaching import teach_technology


def conclude_obligation(world, obligation, status, material_event_id=None, extra_causes=(), repudiated=False):
    causes = tuple(dict.fromkeys((obligation.last_event_id, *extra_causes,
                                 *((material_event_id,) if material_event_id else ()))))
    text = {'fulfilled':'Obrigação cumprida por execução material.',
        'breached':'A promessa foi repudiada pelo próprio devedor antes do prazo.' if repudiated
                   else 'Prazo descumprido; nenhuma transferência forçada.',
        'excused':'Obrigação dispensada porque sua condição não foi cumprida.'}[status]
    proposal = world.relations.proposals[obligation.proposal_id]
    # A breached material delivery or withdrawal promise matters to both
    # parties. The same factual event declares their memories; Knowledge still
    # owns who learned the fact and no score is stored here.
    # Every concluded bilateral term is a social fact known to both parties.
    # Relations stores only relevance; the material owner still validates the
    # payment, teaching, freight, withdrawal or administration transition.
    remembering = ((proposal.proposer_ref, proposal.counterparty_ref)
                   if status in {'fulfilled', 'breached'} else ())
    event = record_event(world, 'commitment_' + status, text, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta('obligation', obligation.id, 'status', obligation.status, status),
                *memory_creation_deltas(world, remembering)), cause_ids=causes)
    world.relations.obligations[obligation.id] = obligation.model_copy(update={
        'status':status, 'material_event_id':material_event_id,
        'breach_event_id': event.id if status == 'breached' else None,
        'remediation_material_event_id': None, 'last_event_id':event.id})
    if status in {'breached', 'excused'}:
        world.agenda.cancel(obligation.id)
    apply_memory_creation(world, remembering, event)
    disclose(world, proposal, event)
    if status == 'breached':
        # The wronged creditor earns a dated turn; the breach itself still
        # causes nothing and no recourse is owed, chosen or implied here.
        from .recourse_policy import note_breach
        note_breach(world, proposal.clauses[obligation.clause_index])


def fulfill_obligation(world, obligation_id, *, decision_event_id, acceptance_id=None,
                       decision_intent=None, acceptance_intent=None):
    world.relations.validate(world)
    obligation = world.relations.obligations.get(obligation_id)
    if obligation is None or obligation.status != 'active':
        raise ValueError('fulfillment requires an active obligation')
    proposal = world.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    if world.clock.absolute_day > clause.due_day:
        raise ValueError('fulfillment deadline has passed')
    dependencies = [world.relations.obligations[f'{proposal.id}:term:{i}'] for i in clause.depends_on]
    if any(d.status != 'fulfilled' for d in dependencies):
        raise ValueError('fulfillment requires satisfied dependencies')
    if clause.kind == 'payment':
        if acceptance_id is not None:
            raise ValueError('payment does not consume teaching consent')
        intent = decision_intent or {'action':'pay', 'actor_ref':clause.debtor_ref.to_dict(),
                                     'source_id':clause.source_account_id, 'target_id':clause.target_account_id,
                                     'amount':clause.amount}
        require_decision(world, decision_event_id, intent)
        transfer_money(world, clause.source_account_id, clause.target_account_id, clause.amount,
                       decision_event_id=decision_event_id, decision_intent=decision_intent)
        material = world.economy.payments[decision_event_id]
    else:
        terms = {'technology_id':clause.technology_id, 'teacher_ref':clause.debtor_ref.to_dict(),
                 'student_ref':clause.creditor_ref.to_dict()}
        teacher_intent = decision_intent or {**terms, 'action':'teach', 'actor_ref':clause.debtor_ref.to_dict()}
        learner_intent = acceptance_intent or {**terms, 'action':'learn', 'actor_ref':clause.creditor_ref.to_dict()}
        require_decision(world, decision_event_id, teacher_intent)
        require_decision(world, acceptance_id, learner_intent)
        teach_technology(world, decision_event_id, acceptance_id, teacher_intent=decision_intent,
                         learner_intent=acceptance_intent, expected_terms=terms)
        material = next(k.event_id for k in world.knowledge.technologies.values()
                        if k.owner_ref == clause.creditor_ref and k.technology_id == clause.technology_id)
    conclude_obligation(world, obligation, 'fulfilled', material, tuple(d.last_event_id for d in dependencies))


def repudiate_obligation(world, obligation_id, *, decision_event_id, decision_intent=None):
    """The debtor's own choice not to honor an obligation it could still meet.

    Distinct from the deadline lapse in :func:`resolve_diplomacy`: this is
    only reachable while the obligation is still ``active`` and its deadline
    has not yet passed, so it can never stand in for "simply failed to act
    in time". The material conclusion is the same ``breached`` transition
    every other breach uses; only the decision that causes it, and the
    ``repudiated`` flag threaded to :func:`conclude_obligation`, mark the
    difference between not managing to honor a promise and not wanting to.
    """
    world.relations.validate(world)
    obligation = world.relations.obligations.get(obligation_id)
    if obligation is None or obligation.status != 'active':
        raise ValueError('repudiation requires an active obligation')
    proposal = world.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    if world.clock.absolute_day > clause.due_day:
        raise ValueError('repudiation deadline has passed')
    intent = decision_intent or {'action': 'repudiate_obligation', 'actor_ref': clause.debtor_ref.to_dict(),
                                 'obligation_id': obligation.id}
    require_decision(world, decision_event_id, intent)
    require_authority(world, clause.debtor_ref, 'diplomacy')
    conclude_obligation(world, obligation, 'breached', extra_causes=(decision_event_id,), repudiated=True)


def resolve_diplomacy(world, situations):
    for situation in sorted(situations, key=lambda s:s.id):
        if situation.due_day != world.clock.absolute_day:
            raise ValueError('diplomatic deadline resolved on wrong day')
        proposal = world.relations.proposals.get(situation.id)
        if proposal:
            if situation.due_day != proposal.expires_day:
                raise ValueError('incorrect proposal deadline')
            if proposal.status != 'offered':
                continue
            event = record_event(world, 'diplomatic_offer_expired', 'Oferta expirou sem aceitação.',
                fact_kind=FactKind.STATE_TRANSITION,
                deltas=(_delta('diplomacy', proposal.id, 'status', 'offered', 'expired'),),
                cause_ids=(proposal.last_event_id,))
            world.relations.proposals[proposal.id] = proposal.model_copy(update={'status':'expired', 'last_event_id':event.id})
            disclose(world, proposal, event)
            continue
        obligation = world.relations.obligations.get(situation.id)
        if obligation is None:
            raise ValueError('unknown diplomatic deadline')
        proposal = world.relations.proposals[obligation.proposal_id]
        clause = proposal.clauses[obligation.clause_index]
        if situation.due_day != clause.due_day + 1:
            raise ValueError('incorrect obligation deadline')
        if obligation.status != 'active':
            continue
        dependencies = [world.relations.obligations[f'{proposal.id}:term:{i}'] for i in clause.depends_on]
        status = 'excused' if any(d.status != 'fulfilled' for d in dependencies) else 'breached'
        conclude_obligation(world, obligation, status, extra_causes=tuple(d.last_event_id for d in dependencies))
