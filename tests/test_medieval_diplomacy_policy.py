"""Decisions use isolated actor context; material execution remains independent."""
from dataclasses import replace

import pytest
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from tests.test_medieval_diplomacy import world_with_knowledge, SELLER, BUYER, clauses, respond
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.persistence import world_snapshot, save_world, load_world
from src.sim.medieval import ai_decider


def useful_buyer(world):
    # Prepared institutional complex: the buyer owns a local productive capability.
    site = world.map.infrastructure_sites['campos-do-lume']
    world.map.infrastructure_sites[site.id] = replace(
        site, capability_ids=(*site.capability_ids, 'iron_production'))


def test_actor_context_does_not_change_when_foreign_secrets_change():
    from src.sim.medieval.diplomacy_context import diplomatic_context
    world = world_with_knowledge()
    before = diplomatic_context(world, BUYER)
    account = world.economy.accounts['treasury:escarlia']
    world.economy.accounts[account.id] = account.model_copy(update={'balance':1})
    world.knowledge.technologies.clear()
    assert diplomatic_context(world, BUYER) == before


def test_diplomatic_context_exposes_only_known_directional_memory():
    from src.sim.medieval.diplomacy_context import diplomatic_context
    from src.sim.medieval.institutional_memory import institutional_views
    from tests.test_medieval_institutional_memory import breach_event_id
    from tests.test_medieval_institutional_aid import _breached_aid_world, PROVIDER, REQUESTER

    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)

    assert diplomatic_context(world, REQUESTER).institutional_views == ((PROVIDER, -4, (breach,)),)
    assert institutional_views(world, PROVIDER) == ()

    # Removing the actor's notice makes the same memory private again; the
    # read model must not leak it merely because RelationsState still has it.
    for key, notice in list(world.knowledge.notices.items()):
        if notice.recipient_ref == REQUESTER and notice.event_id == breach:
            del world.knowledge.notices[key]
    assert diplomatic_context(world, REQUESTER).institutional_views == ()


def test_provider_diplomacy_situation_contains_memory_view_without_foreign_terms():
    from src.sim.medieval.diplomacy_policy import _diplomacy_situation
    from tests.test_medieval_institutional_memory import breach_event_id
    from tests.test_medieval_institutional_aid import _breached_aid_world, PROVIDER, REQUESTER

    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    situation = _diplomacy_situation(world, REQUESTER, ())

    assert situation["known_institutional_views"] == ({
        "counterparty": PROVIDER.to_dict(),
        "value": -4,
        "evidence_event_ids": [breach],
    },)
    assert "balance" not in repr(situation["known_institutional_views"])
    assert "source_stock_id" not in repr(situation)
    assert set(situation["own_strategic_capacity"]) == {
        "food_reserves", "productive_inputs", "territorial_defense",
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity"}


def test_diplomatic_context_exposes_only_recipient_private_findings():
    from src.classes.governance.models import EspionageFinding, TechnologyTheftFinding
    from src.sim.medieval.diplomacy_context import diplomatic_context

    world = world_with_knowledge()
    target_id = next(iter(world.society.settlements))
    finding = EspionageFinding(
        id="espionage_finding:event:1", mission_id="espionage:fixture",
        decision_event_id="event:1", recipient_ref=BUYER,
        agent_ref=EntityRef("character", next(iter(world.society.characters))),
        target_ref=EntityRef("settlement", target_id), target_owner_ref=SELLER,
        result="failure", learned_day=world.clock.absolute_day, event_id="event:1")
    world.knowledge.espionage_findings[finding.id] = finding
    theft = TechnologyTheftFinding(
        id="technology_theft_finding:event:2", mission_id="theft:fixture",
        decision_event_id="event:2", recipient_ref=BUYER,
        agent_ref=finding.agent_ref, site_id="minas-de-ferroalto",
        target_owner_ref=SELLER, technology_id="metallurgy",
        observation_event_id="event:1", result="failure", learned_day=world.clock.absolute_day,
        event_id="event:2")
    world.knowledge.technology_theft_findings[theft.id] = theft

    context = diplomatic_context(world, BUYER)
    assert context.strategic_evidence == ({
        "kind": "espionage", "finding_id": finding.id, "result": "failure",
        "recipient_ref": BUYER.to_dict(),
        "target_ref": finding.target_ref.to_dict(),
        "target_owner_ref": finding.target_owner_ref.to_dict(),
        "evidence_event_id": None, "event_id": "event:1",
    }, {
        "kind": "technology_theft", "finding_id": theft.id, "result": "failure",
        "recipient_ref": BUYER.to_dict(),
        "site_id": theft.site_id, "target_owner_ref": SELLER.to_dict(),
        "technology_id": "metallurgy", "observation_event_id": "event:1",
        "source_knowledge_event_id": None, "learned_knowledge_event_id": None,
        "event_id": "event:2",
    })
    assert diplomatic_context(world, SELLER).strategic_evidence == ()


def test_diplomatic_memory_context_survives_save_load_without_creating_state(tmp_path):
    from src.sim.medieval.diplomacy_context import diplomatic_context
    from tests.test_medieval_institutional_aid import _breached_aid_world, REQUESTER

    world, _ = _breached_aid_world()
    before = world_snapshot(world)
    context = diplomatic_context(world, REQUESTER)
    save_world(world, tmp_path / "memory-context.mws")
    restored = load_world(tmp_path / "memory-context.mws")

    assert world_snapshot(world) == before
    assert diplomatic_context(restored, REQUESTER) == context


@pytest.mark.asyncio
async def test_offer_counteroffer_acceptance_payment_teaching_are_distinct_steps(tmp_path):
    from src.sim.medieval.diplomacy_policy import review_diplomacy
    from src.sim.medieval.engine import MedievalSimulator
    world = world_with_knowledge(); useful_buyer(world)
    review_diplomacy(world, allow_offers=True)
    proposal = next(p for p in world.relations.proposals.values() if p.counterparty_ref == BUYER)
    assert proposal.status == 'offered'
    assert not world.knowledge.knows(BUYER, 'metallurgy')
    await MedievalSimulator(world).step()
    counter = next(p for p in world.relations.proposals.values() if p.parent_id == proposal.id)
    assert counter.clauses[0].amount < proposal.clauses[0].amount
    assert not world.relations.obligations
    await MedievalSimulator(world).step()
    assert world.relations.proposals[counter.id].status == 'accepted'
    assert all(o.status == 'active' for o in world.relations.obligations.values())
    await MedievalSimulator(world).step()
    assert world.relations.obligations[f'{counter.id}:term:0'].status == 'fulfilled'
    assert not world.knowledge.knows(BUYER, 'metallurgy')
    save_world(world, tmp_path / 'bargain.mws')
    resumed = load_world(tmp_path / 'bargain.mws')
    for w in (world, resumed): await MedievalSimulator(w).step()
    assert world.knowledge.knows(BUYER, 'metallurgy')
    assert world_snapshot(world) == world_snapshot(resumed)
    assert sum(a.balance for a in world.economy.accounts.values()) == 76000


@pytest.mark.asyncio
async def test_counteroffer_records_zero_delta_bargain_attempt_before_successor_offer():
    from src.sim.medieval.diplomacy_policy import review_diplomacy
    from src.sim.medieval.engine import MedievalSimulator
    world = world_with_knowledge(); useful_buyer(world)
    review_diplomacy(world, allow_offers=True)
    original = next(p for p in world.relations.proposals.values() if p.counterparty_ref == BUYER)
    await MedievalSimulator(world).step()

    attempt = next(event for event in world.events if event.event_type == 'diplomatic_bargain_attempted')
    successor = next(p for p in world.relations.proposals.values() if p.parent_id == original.id)
    assert attempt.fact_kind is FactKind.OCCURRENCE
    assert attempt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert attempt.deltas == ()
    assert {link.cause_event_id for link in attempt.causal_links} == {
        successor.decision_event_id, original.last_event_id,
    }
    successor_event = next(event for event in world.events if event.id == successor.last_event_id)
    assert attempt.id in {link.cause_event_id for link in successor_event.causal_links}


def test_policy_does_not_propose_unknown_techniques_or_repeat_delivered_offers():
    from src.sim.medieval.diplomacy_policy import review_diplomacy
    world = world_with_knowledge()
    review_diplomacy(world, allow_offers=True)
    assert world.relations.proposals
    assert all(p.clauses[1].technology_id == 'metallurgy' and p.proposer_ref == SELLER for p in world.relations.proposals.values())
    count = len(world.relations.proposals)
    review_diplomacy(world, allow_offers=True)
    assert len(world.relations.proposals) == count


def test_persuasion_is_a_causal_attempt_not_an_automatic_acceptance():
    from src.sim.medieval.diplomacy_policy import _execute_persuasion, _persuasion_options
    from src.sim.medieval.events import record_event
    from src.systems.time import WorldClock

    world = world_with_knowledge()
    from tests.test_medieval_diplomacy import offer
    proposal = offer(world)
    world.clock = WorldClock(proposal.offered_day + 1)
    option = next(item for item in _persuasion_options(world, SELLER)
                  if item.proposal_id == proposal.id)
    decision = record_event(world, 'persuasion_decided', 'A instituição escolheu reforçar a proposta.',
                            fact_kind=FactKind.DECISION, decision=option.decision())
    _execute_persuasion(world, option, decision.id)

    attempt = next(item for item in world.events
                   if item.event_type == 'diplomatic_persuasion_attempted')
    assert attempt.deltas == ()
    assert attempt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert world.relations.proposals[proposal.id].status == 'offered'
    assert any(notice.recipient_ref == BUYER and notice.event_id == attempt.id
               for notice in world.knowledge.notices.values())


def test_notified_counterparty_can_persuade_without_accepting_or_changing_terms():
    from src.sim.medieval.diplomacy_policy import _execute_persuasion, _persuasion_options
    from src.sim.medieval.events import record_event
    from src.systems.time import WorldClock

    world = world_with_knowledge()
    from tests.test_medieval_diplomacy import offer
    proposal = offer(world)
    world.clock = WorldClock(proposal.offered_day + 1)
    option = next(item for item in _persuasion_options(world, BUYER)
                  if item.proposal_id == proposal.id)
    assert option.counterparty_ref == SELLER
    decision = record_event(world, 'persuasion_decided', 'A contraparte escolheu manter o diálogo aberto.',
                            fact_kind=FactKind.DECISION, decision=option.decision())
    _execute_persuasion(world, option, decision.id)

    attempt = next(item for item in world.events
                   if item.event_type == 'diplomatic_persuasion_attempted')
    assert attempt.deltas == ()
    assert attempt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert world.relations.proposals[proposal.id].status == 'offered'
    assert any(notice.recipient_ref == SELLER and notice.event_id == attempt.id
               for notice in world.knowledge.notices.values())


@pytest.mark.asyncio
async def test_no_useful_capability_leads_to_refusal_without_payment():
    from src.sim.medieval.diplomacy_policy import review_diplomacy
    from src.sim.medieval.engine import MedievalSimulator
    world = world_with_knowledge()
    balances = dict(world.economy.accounts)
    review_diplomacy(world, allow_offers=True)
    proposal = next(p for p in world.relations.proposals.values() if p.counterparty_ref == BUYER)
    await MedievalSimulator(world).step()
    assert world.relations.proposals[proposal.id].status == 'rejected'
    assert world.economy.accounts == balances


def _provider_world(world, *, calls=2):
    world.config = world.config.model_copy(update={'ai_enabled': True, 'ai_calls_per_step': calls,
                                                   'ai_max_calls': 20})
    return world


def _provider(monkeypatch, chooser):
    async def call_llm_json(prompt, *args, **kwargs):
        return {'selected_id': chooser(prompt)}
    monkeypatch.setattr(ai_decider, 'provider_available', lambda: True)
    monkeypatch.setattr('src.utils.llm.client.call_llm_json', call_llm_json)


@pytest.mark.asyncio
async def test_provider_selects_a_canonical_teaching_offer_without_inventing_terms(monkeypatch, tmp_path):
    from src.sim.medieval.diplomacy_policy import review_diplomacy_with_provider, teaching_offer_options
    world = _provider_world(world_with_knowledge()); useful_buyer(world)
    option = next(item for item in teaching_offer_options(world, SELLER) if item.counterparty_ref == BUYER)
    _provider(monkeypatch, lambda prompt: option.id if option.id in prompt else 'NO_ACTION')

    await review_diplomacy_with_provider(world, allow_offers=True)

    proposal = next(item for item in world.relations.proposals.values() if item.proposer_ref == SELLER)
    event = next(item for item in world.events if item.id == proposal.decision_event_id)
    assert event.decision == option.decision()
    assert proposal.clauses[0].amount == option.amount
    save_world(world, tmp_path / 'provider-offer.mws')
    assert world_snapshot(load_world(tmp_path / 'provider-offer.mws')) == world_snapshot(world)


@pytest.mark.asyncio
@pytest.mark.parametrize('answer', ['NO_ACTION', 'forged:teaching-option'])
async def test_provider_silence_or_invalid_response_leaves_open_offer_unchanged(monkeypatch, answer):
    from src.sim.medieval.diplomacy_policy import review_diplomacy_with_provider
    from tests.test_medieval_diplomacy import offer
    world = _provider_world(world_with_knowledge()); useful_buyer(world)
    proposal = offer(world)
    world.clock = world.clock.advance(1)
    _provider(monkeypatch, lambda _prompt: answer)

    await review_diplomacy_with_provider(world)

    assert world.relations.proposals[proposal.id].status == 'offered'
    assert not world.relations.obligations


@pytest.mark.asyncio
async def test_provider_teaching_needs_distinct_teacher_and_learner_choices(monkeypatch):
    from src.sim.medieval.diplomacy_policy import (_learning_options, _teaching_options,
                                                   review_diplomacy_with_provider)
    from tests.test_medieval_diplomacy import offer, pay
    world = _provider_world(world_with_knowledge()); useful_buyer(world)
    proposal = offer(world, 80); respond(world, proposal)
    pay(world, f'{proposal.id}:term:0')
    world.clock = world.clock.advance(1)
    teacher = _teaching_options(world, SELLER)[0]
    # The learner option appears only after the teacher's current consent is
    # recorded; choosing both IDs proves no counterpart decision is fabricated.
    def choose(prompt):
        learner = tuple(item for item in _learning_options(world, BUYER) if item.id in prompt)
        return learner[0].id if learner else teacher.id
    _provider(monkeypatch, choose)

    await review_diplomacy_with_provider(world)

    decisions = [item for item in world.events if item.day == world.clock.absolute_day and item.fact_kind.name == 'DECISION']
    assert {teacher.id, f'accept-promised-teaching:{teacher.id}'} <= {
        item.decision['selected_affordance_id'] for item in decisions}
    assert world.knowledge.knows(BUYER, 'metallurgy')
