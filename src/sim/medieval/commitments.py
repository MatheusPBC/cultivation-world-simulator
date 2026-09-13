"""Fulfillment delegates material changes; deadlines record consequences only."""
from src.classes.event import FactKind
from .economy import _delta, transfer_money
from .events import record_event
from .diplomacy import require_decision, disclose
from .teaching import teach_technology


def conclude_obligation(world, obligation, status, material_event_id=None, extra_causes=()):
    causes = tuple(dict.fromkeys((obligation.last_event_id, *extra_causes,
                                 *((material_event_id,) if material_event_id else ()))))
    text = {'fulfilled':'Obrigação cumprida por execução material.',
        'breached':'Prazo descumprido; nenhuma transferência forçada.',
        'excused':'Obrigação dispensada porque sua condição não foi cumprida.'}[status]
    event = record_event(world, 'commitment_' + status, text, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta('obligation', obligation.id, 'status', obligation.status, status),), cause_ids=causes)
    world.relations.obligations[obligation.id] = obligation.model_copy(update={
        'status':status, 'material_event_id':material_event_id, 'last_event_id':event.id})
    disclose(world, world.relations.proposals[obligation.proposal_id], event)


def fulfill_obligation(world, obligation_id, *, decision_event_id, acceptance_id=None):
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
        require_decision(world, decision_event_id, {'action':'pay', 'actor_ref':clause.debtor_ref.to_dict(),
            'source_id':clause.source_account_id, 'target_id':clause.target_account_id, 'amount':clause.amount})
        transfer_money(world, clause.source_account_id, clause.target_account_id, clause.amount, decision_event_id=decision_event_id)
        material = world.economy.payments[decision_event_id]
    else:
        terms = {'technology_id':clause.technology_id, 'teacher_ref':clause.debtor_ref.to_dict(),
                 'student_ref':clause.creditor_ref.to_dict()}
        require_decision(world, decision_event_id, {**terms, 'action':'teach', 'actor_ref':clause.debtor_ref.to_dict()})
        require_decision(world, acceptance_id, {**terms, 'action':'learn', 'actor_ref':clause.creditor_ref.to_dict()})
        teach_technology(world, decision_event_id, acceptance_id)
        material = next(k.event_id for k in world.knowledge.technologies.values()
                        if k.owner_ref == clause.creditor_ref and k.technology_id == clause.technology_id)
    conclude_obligation(world, obligation, 'fulfilled', material, tuple(d.last_event_id for d in dependencies))


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
