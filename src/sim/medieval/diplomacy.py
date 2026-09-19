"""Deliver offers and bind accepted intentions without executing material clauses."""
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority
from src.classes.governance.models import DiplomaticNotice
from src.classes.governance.diplomacy import (DiplomaticProposal, Obligation, offer_intent, validate_clause_assets,
                                              validate_teaching_request_sightings)
from src.systems.calendar_agenda import ScheduledSituation
from .events import record_event
from .economy import _delta


def require_decision(world, event_id, intent):
    event = next((e for e in world.events if e.id == event_id), None)
    if event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day or event.decision != intent:
        raise ValueError('operation requires an exact current decision')


def disclose(world, proposal, event):
    for recipient in (proposal.proposer_ref, proposal.counterparty_ref):
        notice = DiplomaticNotice(id=f'notice:{event.id}:{recipient.kind}:{recipient.id}',
            proposal_id=proposal.id, recipient_ref=recipient, event_id=event.id, learned_day=world.clock.absolute_day)
        world.knowledge.notices[notice.id] = notice


def offer_proposal(world, proposer_ref, counterparty_ref, clauses, expires_day, *, decision_event_id,
                   parent_id=None, intent=None, proposal_kind='negotiated', request_affordance_id=None,
                   extra_cause_ids=()):
    """``intent`` lets a vertical authorize the offer with its own affordance
    decision shape; the decision still has to be this actor's exact current one."""
    world.relations.validate(world)
    p = DiplomaticProposal(id=f'proposal:{decision_event_id}', proposer_ref=proposer_ref,
        counterparty_ref=counterparty_ref, clauses=clauses, offered_day=world.clock.absolute_day,
        expires_day=expires_day, parent_id=parent_id, decision_event_id=decision_event_id, last_event_id=decision_event_id,
        proposal_kind=proposal_kind, request_affordance_id=request_affordance_id)
    require_decision(world, decision_event_id,
                     intent or offer_intent(proposer_ref, counterparty_ref, p.clauses, expires_day, parent_id))
    require_authority(world, proposer_ref, 'diplomacy')
    from src.classes.governance.serialization import validate_actor
    validate_actor(world, counterparty_ref)
    if not (proposal_kind == 'reciprocal_supply' and p.status == 'offered'):
        validate_clause_assets(world, p)
    validate_teaching_request_sightings(world, p)
    if p.id in world.relations.proposals:
        raise ValueError('decision already used for a proposal')
    parent = world.relations.proposals.get(parent_id) if parent_id else None
    if parent_id and (parent is None or parent.status != 'offered' or parent.expires_day <= world.clock.absolute_day
            or parent.counterparty_ref != proposer_ref or parent.proposer_ref != counterparty_ref):
        raise ValueError('counteroffer requires the open opposite proposal')
    changes = [_delta('diplomacy', p.id, 'status', None, 'offered')]
    if parent:
        changes.append(_delta('diplomacy', parent.id, 'status', 'offered', 'superseded'))
    event = record_event(world, 'diplomatic_offer_delivered', 'Condições diplomáticas entregues à contraparte.',
        fact_kind=FactKind.STATE_TRANSITION, deltas=changes,
        cause_ids=tuple(dict.fromkeys(
            ((decision_event_id, parent.last_event_id) if parent else (decision_event_id,))
            + tuple(extra_cause_ids)
        )))
    p = p.model_copy(update={'last_event_id': event.id})
    if parent:
        world.relations.proposals[parent.id] = parent.model_copy(update={'status':'superseded', 'last_event_id':event.id})
    world.relations.proposals[p.id] = p
    world.agenda.schedule(ScheduledSituation(p.id, 'diplomacy', p.expires_day))
    disclose(world, p, event)
    return p


def respond_proposal(world, proposal_id, response, *, decision_event_id, intent=None):
    world.relations.validate(world)
    p = world.relations.proposals.get(proposal_id)
    if p is None or p.status != 'offered' or p.expires_day <= world.clock.absolute_day:
        raise ValueError('response requires an open proposal')
    if response not in {'accept', 'reject'}:
        raise ValueError('unknown proposal response')
    require_decision(world, decision_event_id, intent or {'action':'respond_proposal',
        'actor_ref':p.counterparty_ref.to_dict(), 'proposal_id':p.id, 'response':response})
    require_authority(world, p.counterparty_ref, 'diplomacy')
    require_authority(world, p.proposer_ref, 'diplomacy')
    status = 'accepted' if response == 'accept' else 'rejected'
    changes = [_delta('diplomacy', p.id, 'status', 'offered', status)]
    if response == 'accept':
        changes.extend(_delta('obligation', f'{p.id}:term:{i}', 'status', None, 'active') for i in range(len(p.clauses)))
    event = record_event(world, 'diplomatic_response_delivered',
        'Proposta aceita; obrigações ainda precisam ser cumpridas.' if response == 'accept' else 'Proposta recusada.',
        fact_kind=FactKind.STATE_TRANSITION, deltas=changes, cause_ids=(p.last_event_id, decision_event_id))
    p = p.model_copy(update={'status': status, 'last_event_id':event.id})
    world.relations.proposals[p.id] = p
    if response == 'accept':
        for i, clause in enumerate(p.clauses):
            obligation = Obligation(id=f'{p.id}:term:{i}', proposal_id=p.id, clause_index=i, last_event_id=event.id)
            world.relations.obligations[obligation.id] = obligation
            world.agenda.schedule(ScheduledSituation(obligation.id, 'diplomacy', clause.due_day + 1))
    disclose(world, p, event)
    return p
