"""A known payment breach can become a fresh, actor-chosen long-term offer."""

import pytest

from src.classes.event import FactKind
from src.sim.medieval.commitments import resolve_diplomacy
from src.sim.medieval.diplomacy_policy import (
    RENEGOTIATE_ACTION,
    _execute_renegotiation,
    _renegotiation_options,
    _execute_response,
    _execute_teaching,
    _execute_learning,
    _learning_options,
    _proposal_response_options,
    _teaching_options,
    REMEDIATE_PAYMENT_ACTION,
    _execute_payment_remediation,
    _payment_remediation_options,
)
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.systems.calendar_agenda import ScheduledSituation
from tests.test_medieval_diplomacy import BUYER, SELLER, offer, pay, respond, world_with_knowledge


def breached_payment_world():
    world = world_with_knowledge()
    proposal = offer(world)
    respond(world, proposal)
    obligation_id = f"{proposal.id}:term:0"
    world.clock = world.clock.advance(11)
    resolve_diplomacy(world, [ScheduledSituation(obligation_id, "diplomacy", 101)])
    world.agenda.cancel(obligation_id)
    world.agenda.cancel(proposal.id)
    return world, proposal, obligation_id


def test_creditor_can_offer_one_fresh_payment_term_after_known_breach(tmp_path):
    world, _, obligation_id = breached_payment_world()
    options = _renegotiation_options(world, SELLER)
    assert len(options) == 1
    option = options[0]
    assert option.obligation_id == obligation_id
    assert _renegotiation_options(world, BUYER) == ()

    decision = record_event(world, "renegotiation_decided", "Propor novo prazo após a quebra conhecida.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(option.breach_event_id,))
    assert _execute_renegotiation(world, option, decision.id)

    assert world.relations.obligations[obligation_id].status == "breached"
    successor = next(item for item in world.relations.proposals.values()
                     if item.proposal_kind == "renegotiation")
    assert successor.status == "offered"
    assert successor.clauses[0].due_day > successor.expires_day
    delivered = next(item for item in world.events if item.id == successor.last_event_id)
    assert option.breach_event_id in {link.cause_event_id for link in delivered.causal_links}
    assert all(item.decision is None or item.decision.get("action") != RENEGOTIATE_ACTION
               or item.decision == option.decision() for item in world.events)

    save_world(world, tmp_path / "renegotiation.mws")
    assert world_snapshot(load_world(tmp_path / "renegotiation.mws")) == world_snapshot(world)


def test_renegotiation_affordance_is_single_use_and_stale_decision_is_rejected():
    world, _, _ = breached_payment_world()
    option = _renegotiation_options(world, SELLER)[0]
    stale = record_event(world, "renegotiation_decided", "Escolha forjada.", fact_kind=FactKind.DECISION,
                         decision={**option.decision(), "selected_affordance_id": "forged"})
    with pytest.raises(ValueError, match="exact current decision"):
        _execute_renegotiation(world, option, stale.id)
    assert len(world.relations.proposals) == 1
    decision = record_event(world, "renegotiation_decided", "Propor novo prazo.", fact_kind=FactKind.DECISION,
                            decision=option.decision())
    assert _execute_renegotiation(world, option, decision.id)
    assert _renegotiation_options(world, SELLER) == ()


def test_debtor_can_materially_repair_a_known_payment_breach_without_erasing_history(tmp_path):
    world, _, obligation_id = breached_payment_world()
    option = _payment_remediation_options(world, BUYER)[0]
    source_before = world.economy.accounts[option.source_account_id].balance
    target_before = world.economy.accounts[option.target_account_id].balance
    decision = record_event(world, "institutional_decision_turn_decided", "Reparar pagamento descumprido.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=option.causes())
    assert _execute_payment_remediation(world, option, decision.id)
    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == "remediated"
    assert obligation.breach_event_id and obligation.remediation_material_event_id
    assert world.economy.accounts[option.source_account_id].balance == source_before - option.amount
    assert world.economy.accounts[option.target_account_id].balance == target_before + option.amount
    assert next(item for item in world.events if item.id == obligation.breach_event_id).event_type == "commitment_breached"
    assert any(item.event_type == "payment_obligation_remediated" for item in world.events)
    save_world(world, tmp_path / "payment-remediation.mws")
    assert world_snapshot(load_world(tmp_path / "payment-remediation.mws")) == world_snapshot(world)


def test_teacher_can_remediate_a_paid_but_breached_teaching_term(tmp_path):
    world = world_with_knowledge()
    # The learner must possess a real authored capability for the technique;
    # the remediation cannot turn a historical promise into free knowledge.
    from dataclasses import replace
    for site in tuple(world.map.infrastructure_sites.values()):
        if site.owner_ref == BUYER and 'iron_production' not in site.capability_ids:
            world.map.infrastructure_sites[site.id] = replace(
                site, capability_ids=(*site.capability_ids, 'iron_production'))
    proposal = offer(world, 80)
    respond(world, proposal)
    payment_id = f'{proposal.id}:term:0'
    teaching_id = f'{proposal.id}:term:1'
    pay(world, payment_id)
    world.clock = world.clock.advance(16)
    resolve_diplomacy(world, [ScheduledSituation(teaching_id, 'diplomacy', world.clock.absolute_day)])
    world.agenda.cancel(teaching_id)
    world.agenda.cancel(proposal.id)
    original = world.relations.obligations[teaching_id]
    assert original.status == 'breached'

    option = next(item for item in _renegotiation_options(world, SELLER)
                  if item.obligation_id == teaching_id)
    decision = record_event(world, 'teaching-remediation-decided', 'Propor novo ensino após breach.',
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(option.breach_event_id,))
    assert _execute_renegotiation(world, option, decision.id)
    successor = next(item for item in world.relations.proposals.values()
                     if item.proposal_kind == 'renegotiation')
    assert successor.clauses[0].kind == 'teaching'
    world.clock = world.clock.advance(1)
    response = next(item for item in _proposal_response_options(world, BUYER)
                    if item.proposal_id == successor.id and item.response == 'accept')
    response_decision = record_event(world, 'teaching-remediation-response', 'Aceitar novo ensino.',
                                     fact_kind=FactKind.DECISION, decision=response.decision())
    assert _execute_response(world, response, response_decision.id)
    world.clock = world.clock.advance(1)

    teacher = next(item for item in _teaching_options(world, SELLER)
                   if item.proposal_id == successor.id)
    teacher_decision = record_event(world, 'teaching-remediation-consent', 'Autorizar o novo ensino.',
                                    fact_kind=FactKind.DECISION, decision=teacher.decision())
    assert _execute_teaching(world, teacher, teacher_decision.id)
    learner = next(item for item in _learning_options(world, BUYER)
                   if item.proposal_id == successor.id)
    learner_decision = record_event(world, 'teaching-remediation-acceptance', 'Aceitar o novo ensino.',
                                    fact_kind=FactKind.DECISION, decision=learner.decision())
    assert _execute_learning(world, learner, learner_decision.id)

    assert world.relations.obligations[teaching_id].status == 'breached'
    successor_obligation = world.relations.obligations[f'{successor.id}:term:0']
    assert successor_obligation.status == 'fulfilled'
    assert world.knowledge.knows(BUYER, 'metallurgy')
    world.agenda.cancel(payment_id)
    world.agenda.cancel(f'diplomatic-review:{world.clock.absolute_day - 1}')
    world.agenda.cancel(f'diplomatic-review:{world.clock.absolute_day}')
    save_world(world, tmp_path / 'teaching-remediation.mws')
    assert world_snapshot(load_world(tmp_path / 'teaching-remediation.mws')) == world_snapshot(world)
