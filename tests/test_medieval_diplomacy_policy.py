"""Decisions use isolated actor context; material execution remains independent."""
from dataclasses import replace

import pytest
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


def test_policy_does_not_propose_unknown_techniques_or_repeat_delivered_offers():
    from src.sim.medieval.diplomacy_policy import review_diplomacy
    world = world_with_knowledge()
    review_diplomacy(world, allow_offers=True)
    assert world.relations.proposals
    assert all(p.clauses[1].technology_id == 'metallurgy' and p.proposer_ref == SELLER for p in world.relations.proposals.values())
    count = len(world.relations.proposals)
    review_diplomacy(world, allow_offers=True)
    assert len(world.relations.proposals) == count


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
