"""Decisions use isolated actor context; material execution remains independent."""
from dataclasses import replace

import pytest
from tests.test_medieval_diplomacy import world_with_knowledge, SELLER, BUYER, clauses, respond
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.persistence import world_snapshot, save_world, load_world


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
