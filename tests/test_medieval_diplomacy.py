"""Prepared negotiations exercise real authority, accounts and knowledge owners."""
import pytest
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import save_world, load_world, world_snapshot
from tests.test_medieval_research import prepared, authorize, work

SELLER = EntityRef('polity', 'escarlia')
BUYER = EntityRef('polity', 'auren')


def world_with_knowledge():
    world = prepared()
    authorize(world)
    for day in (30, 60, 90): work(world, day)
    return world


def clauses(amount=100):
    from src.classes.governance.diplomacy import PaymentClause, TeachingClause
    return (PaymentClause(debtor_ref=BUYER, creditor_ref=SELLER, due_day=100,
                source_account_id='treasury:auren', target_account_id='treasury:escarlia', amount=amount),
            TeachingClause(debtor_ref=SELLER, creditor_ref=BUYER, due_day=105,
                depends_on=(0,), technology_id='metallurgy'))


def offer(world, amount=100, parent_id=None):
    from src.sim.medieval.diplomacy import offer_proposal
    proposer, other = (BUYER, SELLER) if parent_id else (SELLER, BUYER)
    if parent_id:
        # A counteroffer that keeps Escarlia as the teacher is an initiated
        # request by Auren, so the fixture supplies the same factual private
        # indication a live provider would have received first.
        from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure
        option = next(item for item in disclosure_options(world, SELLER)
                      if item.recipient_ref == BUYER and item.technology_id == 'metallurgy')
        disclosed = record_event(world, 'diplomatic_decision', 'Divulgar indício técnico próprio.',
            fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=option.causes())
        execute_disclosure(world, option, disclosed.id)
    terms = clauses(amount)
    intent = {'action': 'offer_proposal', 'actor_ref': proposer.to_dict(),
        'counterparty_ref': other.to_dict(), 'clauses': [c.model_dump(mode='json') for c in terms],
        'expires_day': 95, 'parent_id': parent_id}
    event = record_event(world, 'diplomatic_decision', 'Propor condições.', fact_kind=FactKind.DECISION, decision=intent)
    return offer_proposal(world, proposer, other, terms, 95, decision_event_id=event.id, parent_id=parent_id)


def respond(world, proposal, response='accept', actor=None):
    from src.sim.medieval.diplomacy import respond_proposal
    actor = actor or proposal.counterparty_ref
    event = record_event(world, 'diplomatic_decision', 'Responder à proposta.', fact_kind=FactKind.DECISION,
        decision={'action':'respond_proposal', 'actor_ref':actor.to_dict(), 'proposal_id':proposal.id, 'response':response})
    return respond_proposal(world, proposal.id, response, decision_event_id=event.id)


def test_counteroffer_preserves_history_and_acceptance_moves_no_assets(tmp_path):
    world = world_with_knowledge()
    original = offer(world)
    revised = offer(world, 80, original.id)
    assert world.relations.proposals[original.id].status == 'superseded'
    assert world.relations.proposals[original.id].clauses[0].amount == 100
    assert revised.clauses[0].amount == 80
    with pytest.raises(ValueError, match='open'): respond(world, original)
    accounts, stocks, knowledge = dict(world.economy.accounts), dict(world.economy.stocks), dict(world.knowledge.technologies)
    respond(world, revised)
    assert len(world.relations.obligations) == 2
    assert world.economy.accounts == accounts and world.economy.stocks == stocks
    assert world.knowledge.technologies == knowledge
    assert {n.recipient_ref for n in world.knowledge.notices.values()} == {SELLER, BUYER}
    save_world(world, tmp_path / 'negotiation.mws')
    assert world_snapshot(load_world(tmp_path / 'negotiation.mws')) == world_snapshot(world)


def test_third_party_cannot_accept_and_lost_authority_cannot_bind():
    world = world_with_knowledge(); proposal = offer(world)
    with pytest.raises(ValueError, match='decision'): respond(world, proposal, actor=EntityRef('polity', 'valedouro'))
    world.authority.offices = {k:v for k,v in world.authority.offices.items() if v.institution_ref != BUYER}
    with pytest.raises(ValueError, match='authority'): respond(world, proposal)
    assert not world.relations.obligations
    assert world.relations.proposals[proposal.id].status == 'offered'


def test_rejection_creates_no_obligation():
    world = world_with_knowledge(); proposal = offer(world)
    respond(world, proposal, 'reject')
    assert world.relations.proposals[proposal.id].status == 'rejected'
    assert not world.relations.obligations


@pytest.mark.parametrize('change', ['amount', 'status'])
def test_save_rejects_negotiated_conditions_or_status_without_matching_receipt(change):
    world = world_with_knowledge(); proposal = offer(world)
    update = {'clauses': clauses(1)} if change == 'amount' else {'status': 'accepted'}
    world.relations.proposals[proposal.id] = proposal.model_copy(update=update)
    with pytest.raises(ValueError, match='receipt|provenance|obligation'): world_snapshot(world)


def test_clause_cannot_pledge_third_party_money():
    from src.sim.medieval.diplomacy import offer_proposal
    world = world_with_knowledge()
    terms = clauses()
    terms = (terms[0].model_copy(update={'source_account_id': 'treasury:valedouro'}), terms[1])
    event = record_event(world, 'diplomatic_decision', 'Propor condições inválidas.', fact_kind=FactKind.DECISION,
        decision={'action':'offer_proposal', 'actor_ref':SELLER.to_dict(), 'counterparty_ref':BUYER.to_dict(),
            'clauses':[c.model_dump(mode='json') for c in terms], 'expires_day':95, 'parent_id':None})
    with pytest.raises(ValueError, match='account|owner'):
        offer_proposal(world, SELLER, BUYER, terms, 95, decision_event_id=event.id)
    assert not world.relations.proposals


def pay(world, obligation_id):
    from src.sim.medieval.commitments import fulfill_obligation
    obligation = world.relations.obligations[obligation_id]
    proposal = world.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    event = record_event(world, 'payment_decided', 'Cumprir pagamento acordado.', fact_kind=FactKind.DECISION,
        decision={'action':'pay', 'actor_ref':clause.debtor_ref.to_dict(), 'source_id':clause.source_account_id,
            'target_id':clause.target_account_id, 'amount':clause.amount}, cause_ids=(obligation.last_event_id,))
    return fulfill_obligation(world, obligation_id, decision_event_id=event.id)


def teach(world, obligation_id):
    from src.sim.medieval.commitments import fulfill_obligation
    terms = {'technology_id':'metallurgy', 'teacher_ref':SELLER.to_dict(), 'student_ref':BUYER.to_dict()}
    teacher = record_event(world, 'teaching_decided', 'Cumprir ensino acordado.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action':'teach', 'actor_ref':SELLER.to_dict()})
    student = record_event(world, 'learning_decided', 'Aceitar ensino.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action':'learn', 'actor_ref':BUYER.to_dict()})
    return fulfill_obligation(world, obligation_id, decision_event_id=teacher.id, acceptance_id=student.id)


def test_material_owners_fulfill_payment_then_teaching_once(tmp_path):
    world = world_with_knowledge(); proposal = offer(world, 80); respond(world, proposal)
    payment, lesson = f'{proposal.id}:term:0', f'{proposal.id}:term:1'
    with pytest.raises(ValueError, match='depend'): teach(world, lesson)
    before = world.economy.accounts['treasury:auren'].balance
    pay(world, payment)
    assert world.economy.accounts['treasury:auren'].balance == before - 80
    assert not world.knowledge.knows(BUYER, 'metallurgy')
    teach(world, lesson)
    assert world.knowledge.knows(BUYER, 'metallurgy')
    assert world.economy.facilities['works:minas-de-ferroalto'].recipe_id == 'ironworking'
    assert sum(a.balance for a in world.economy.accounts.values()) == 76000
    assert all(o.status == 'fulfilled' for o in world.relations.obligations.values())
    with pytest.raises(ValueError, match='active'): pay(world, payment)
    save_world(world, tmp_path / 'fulfilled.mws')
    assert world_snapshot(load_world(tmp_path / 'fulfilled.mws')) == world_snapshot(world)


@pytest.mark.parametrize('reason', ['funds', 'authority'])
def test_accepted_payment_still_requires_current_money_and_authority(reason):
    world = world_with_knowledge(); proposal = offer(world); respond(world, proposal)
    if reason == 'funds':
        account = world.economy.accounts['treasury:auren']
        world.economy.accounts[account.id] = account.model_copy(update={'balance':0})
    else:
        world.authority.offices = {k:v for k,v in world.authority.offices.items() if v.institution_ref != BUYER}
    balances = dict(world.economy.accounts)
    with pytest.raises(ValueError): pay(world, f'{proposal.id}:term:0')
    assert world.economy.accounts == balances
    assert all(o.status == 'active' for o in world.relations.obligations.values())


@pytest.mark.asyncio
async def test_deadlines_interrupt_months_and_breach_does_not_force_payment(tmp_path):
    from src.sim.medieval.engine import MedievalSimulator
    world = world_with_knowledge(); proposal = offer(world); respond(world, proposal)
    # Prepared mandate expires after acceptance. The obligation survives, but
    # neither the policy nor its owner may spend without current authority.
    for identity, office in world.authority.offices.items():
        if office.institution_ref == BUYER:
            world.authority.offices[identity] = office.model_copy(update={'ends_day': 91})
    balances = dict(world.economy.accounts)
    sim = MedievalSimulator(world)
    await sim.step(); assert world.clock.absolute_day == 95
    assert world.relations.obligations[f'{proposal.id}:term:0'].status == 'active'
    assert world.economy.accounts == balances
    await sim.step(); assert world.clock.absolute_day == 101
    assert world.relations.obligations[f'{proposal.id}:term:0'].status == 'breached'
    assert world.economy.accounts == balances
    await sim.step(); assert world.clock.absolute_day == 106
    assert world.relations.obligations[f'{proposal.id}:term:1'].status == 'excused'
    assert not world.knowledge.knows(BUYER, 'metallurgy')
    assert not any(e.event_type == 'payment_completed' for e in world.events)
    assert {n.recipient_ref for n in world.knowledge.notices.values()} == {SELLER, BUYER}
    save_world(world, tmp_path / 'breached.mws')
    assert world_snapshot(load_world(tmp_path / 'breached.mws')) == world_snapshot(world)


@pytest.mark.asyncio
async def test_expiration_and_save_failure_are_transactional(tmp_path, monkeypatch):
    from src.sim.medieval.engine import MedievalSimulator
    world = world_with_knowledge(); proposal = offer(world)
    before = world_snapshot(world)
    def fail(*args, **kwargs): raise OSError('disk full')
    monkeypatch.setattr('src.sim.medieval.engine.save_world', fail)
    with pytest.raises(OSError, match='disk full'):
        await MedievalSimulator(world, save_path=tmp_path / 'failed.mws').step()
    assert world_snapshot(world) == before
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == 95
    assert world.relations.proposals[proposal.id].status == 'expired'
    with pytest.raises(ValueError, match='open'): respond(world, proposal)


def test_fulfillment_cannot_substitute_an_unrelated_material_receipt():
    world = world_with_knowledge(); proposal = offer(world); respond(world, proposal)
    payment = f'{proposal.id}:term:0'; pay(world, payment)
    obligation = world.relations.obligations[payment]
    unrelated = next(iter(world.knowledge.technologies.values())).event_id
    world.relations.obligations[payment] = obligation.model_copy(update={'material_event_id':unrelated})
    with pytest.raises(ValueError, match='receipt|material|payment'): world_snapshot(world)


@pytest.mark.parametrize('accepted', [False, True])
def test_pending_diplomacy_cannot_lose_its_scheduled_deadline(accepted):
    world = world_with_knowledge(); proposal = offer(world)
    if accepted: respond(world, proposal)
    day = 101 if accepted else 95
    world.agenda.pop_due(day)
    with pytest.raises(ValueError, match='agenda|deadline'): world_snapshot(world)


@pytest.mark.parametrize('dependencies', [(1,), (0, 0)])
def test_negotiation_refuses_cyclic_or_repeated_dependencies(dependencies):
    from src.classes.governance.diplomacy import DiplomaticProposal
    terms = clauses()
    terms = (terms[0], terms[1].model_copy(update={'depends_on':dependencies}))
    with pytest.raises(ValueError, match='dependencies'):
        DiplomaticProposal(id='proposal:event:1', proposer_ref=SELLER, counterparty_ref=BUYER,
            clauses=terms, offered_day=90, expires_day=95, decision_event_id='event:1', last_event_id='event:1')


def test_third_party_does_not_gain_a_diplomatic_notice_by_save_edit():
    world = world_with_knowledge(); offer(world)
    notice = next(iter(world.knowledge.notices.values()))
    world.knowledge.notices[notice.id] = notice.model_copy(update={'recipient_ref':EntityRef('polity','valedouro')})
    with pytest.raises(ValueError, match='notice'): world_snapshot(world)


@pytest.mark.parametrize('stale', [False, True])
def test_offer_decisions_cannot_be_reused_or_executed_on_a_later_day(stale):
    from src.sim.medieval.diplomacy import offer_proposal
    world = world_with_knowledge(); proposal = offer(world)
    if stale: world.clock = world.clock.advance(1)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match='decision'):
        offer_proposal(world, SELLER, BUYER, proposal.clauses, 95, decision_event_id=proposal.decision_event_id)
    assert world_snapshot(world) == before
