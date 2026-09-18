"""Repudiating a promise is a choice; a known breach shapes the next deal."""
import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation
from src.systems.time import WorldClock
from src.sim.medieval.commitments import repudiate_obligation, resolve_diplomacy
from src.sim.medieval.diplomacy_policy import (REPUDIATE_ACTION, _diplomacy_situation,
                                               _known_counterparty_breaches, _repudiation_options)
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.recourse_policy import review_id
from tests.test_medieval_diplomacy import BUYER, SELLER, offer, respond, world_with_knowledge
from tests.test_medieval_recourse import AUREN, ESCARLIA, breached, wronged_world


def _decision(world, option):
    return record_event(world, 'diplomatic_decision', 'A instituição escolheu repudiar.',
                        fact_kind=FactKind.DECISION, decision=option.decision())


def test_repudiation_is_a_decision_then_a_separate_transition_and_grants_recourse():
    world = wronged_world(due_day=90, expires_day=80)
    proposal = next(iter(world.relations.proposals.values()))
    obligation_id = f'{proposal.id}:term:0'
    assert world.relations.obligations[obligation_id].status == 'active'

    option = next(item for item in _repudiation_options(world, ESCARLIA) if item.obligation_id == obligation_id)
    assert option.action == REPUDIATE_ACTION

    events_before = len(world.events)
    decision = _decision(world, option)
    # The decision itself is factual history with no material change.
    assert decision.fact_kind == FactKind.DECISION and not decision.deltas
    assert len(world.events) == events_before + 1

    repudiate_obligation(world, obligation_id, decision_event_id=decision.id, decision_intent=option.decision())

    transition = world.events[-1]
    assert transition.fact_kind == FactKind.STATE_TRANSITION
    assert transition.event_type == 'commitment_breached'
    assert any(delta.owner_id == obligation_id and delta.aspect == 'status' and delta.after == 'breached'
               for delta in transition.deltas)
    # The graph must show the decision caused the transition -- "chose not
    # to" is only legible if the causal link exists, distinct from a bare
    # deadline lapse which has no such decision among its causes.
    assert decision.id in {link.cause_event_id for link in transition.causal_links}

    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == 'breached' and obligation.breach_event_id == transition.id

    # Reuse of the existing recourse path: note_breach schedules the wronged
    # creditor's own turn tomorrow, exactly like a deadline breach would.
    review = world.agenda.get(review_id(world.clock.absolute_day + 1))
    assert review is not None and review.kind == 'recourse_review'


def test_repudiation_of_a_concluded_obligation_or_stale_option_has_no_effect():
    world = wronged_world(due_day=90, expires_day=80)
    proposal = next(iter(world.relations.proposals.values()))
    obligation_id = f'{proposal.id}:term:0'
    option = next(item for item in _repudiation_options(world, ESCARLIA) if item.obligation_id == obligation_id)
    decision = _decision(world, option)
    repudiate_obligation(world, obligation_id, decision_event_id=decision.id, decision_intent=option.decision())

    relations_after_first = world.relations.to_dict()
    events_after_first = len(world.events)

    # A replay of the exact same option_id can never be reissued: the
    # obligation's last_event_id changed, so the same id no longer names a
    # current option (the basis-in-id trick every other affordance uses).
    assert not any(item.id == option.id for item in _repudiation_options(world, ESCARLIA))

    # Calling the material operation directly again on the now-concluded
    # obligation raises before mutating or recording anything at all.
    with pytest.raises(ValueError, match='active'):
        repudiate_obligation(world, obligation_id, decision_event_id=decision.id, decision_intent=option.decision())

    assert len(world.events) == events_after_first
    assert world.relations.to_dict() == relations_after_first


def test_a_notified_party_sees_a_breach_a_stranger_never_negotiated_with_does_not():
    world = world_with_knowledge()
    proposal = offer(world)
    respond(world, proposal)
    # term:0 = payment (BUYER owes SELLER, due day 100); term:1 = teaching
    # (SELLER owes BUYER, due day 105, depends_on=(0,)).
    payment_id = f'{proposal.id}:term:0'
    teaching_id = f'{proposal.id}:term:1'

    option = next(item for item in _repudiation_options(world, BUYER) if item.obligation_id == payment_id)
    decision = _decision(world, option)
    repudiate_obligation(world, payment_id, decision_event_id=decision.id, decision_intent=option.decision())

    # The dependent teaching term lapses excused once its own deadline
    # passes, since its dependency (the payment) was never fulfilled.
    world.clock = WorldClock(106)
    resolve_diplomacy(world, [ScheduledSituation(teaching_id, 'diplomacy', world.clock.absolute_day)])
    assert world.relations.obligations[payment_id].status == 'breached'
    assert world.relations.obligations[teaching_id].status == 'excused'

    # SELLER is the creditor of the repudiated payment and was notified of
    # it; it must read the choice, not a bare lapse.
    seller_breaches = {item['obligation_id']: item
                       for item in _diplomacy_situation(world, SELLER, ())['known_counterparty_breaches']}
    assert seller_breaches[payment_id]['kind'] == 'repudiated'

    # BUYER is the creditor of the excused teaching term (SELLER's own
    # dependency failed first, so the failure was never SELLER's).
    buyer_breaches = {item['obligation_id']: item
                      for item in _diplomacy_situation(world, BUYER, ())['known_counterparty_breaches']}
    assert buyer_breaches[teaching_id]['kind'] == 'excused'

    # This is the test that matters most: a third polity that never
    # negotiated with either party, and so was never notified of anything,
    # must see nothing about this history at all -- reputation, not
    # omniscience.
    stranger = EntityRef('polity', 'valedouro')
    assert _known_counterparty_breaches(world, stranger) == ()
    stranger_breaches = _diplomacy_situation(world, stranger, ())['known_counterparty_breaches']
    assert stranger_breaches == ()


async def test_an_unrepudiated_deadline_lapse_reads_as_breached_by_deadline_not_a_choice():
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    obligation = await breached(world, engine)
    assert obligation.status == 'breached'

    breaches = {item['obligation_id']: item
                for item in _diplomacy_situation(world, AUREN, ())['known_counterparty_breaches']}
    assert breaches[obligation.id]['kind'] == 'breached_by_deadline'
