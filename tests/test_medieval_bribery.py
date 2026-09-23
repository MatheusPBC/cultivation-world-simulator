"""The bribe vertical is only a payment commitment, never an authority grant."""
import pytest

from src.classes.event import FactKind
from src.classes.economy.models import MoneyAccount
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.bribery import (
    bribery_offer_options, bribery_payment_options, bribery_response_options,
    execute_bribery_offer, execute_bribery_payment, execute_bribery_response,
)
from src.sim.medieval.institutional_agenda import monthly_actors
from src.sim.medieval.institutional_memory import (BRIBERY_VIEW, FULFILLMENT_VIEW, MEMORY_SPAN_DAYS,
                                                    effective_salience, institutional_view, institutional_views,
                                                    memories_of)
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_diplomacy import BUYER, SELLER, world_with_knowledge


def _decision(world, option):
    return record_event(world, "bribery_decision", "Escolher uma opção de suborno.",
                        fact_kind=FactKind.DECISION, decision=option.decision()).id


def _offer(world):
    option = next(item for item in bribery_offer_options(world, SELLER)
                  if item.counterparty_ref == BUYER)
    proposal = execute_bribery_offer(world, SELLER, option.id, _decision(world, option))
    world.clock = world.clock.advance(1)
    return proposal


def test_bribery_acceptance_is_independent_and_payment_is_later(tmp_path):
    world = world_with_knowledge()
    original_authority = dict(world.authority.offices)
    before = world.economy.accounts["treasury:escarlia"].balance
    proposal = _offer(world)
    response = next(item for item in bribery_response_options(world, BUYER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    execute_bribery_response(world, BUYER, response.id, _decision(world, response))
    assert world.relations.proposals[proposal.id].status == "accepted"
    assert world.economy.accounts["treasury:escarlia"].balance == before
    assert world.authority.offices == original_authority

    world.clock = world.clock.advance(1)
    payment = next(item for item in bribery_payment_options(world, SELLER)
                   if item.proposal_id == proposal.id)
    execute_bribery_payment(world, SELLER, payment.id, _decision(world, payment))
    assert world.economy.accounts["treasury:escarlia"].balance == before - payment.amount
    assert world.relations.obligations[payment.obligation_id].status == "fulfilled"
    assert world.authority.offices == original_authority
    receipt = world.relations.obligations[payment.obligation_id].last_event_id
    assert memories_of(world, SELLER, receipt) is not None
    assert memories_of(world, BUYER, receipt) is not None
    # The recipient remembers the material bribe as its own qualitative
    # reading, never as generic "commitment fulfilled" credit.
    assert institutional_view(world, BUYER, SELLER) == BRIBERY_VIEW
    assert institutional_view(world, BUYER, SELLER) != FULFILLMENT_VIEW
    assert (SELLER, BRIBERY_VIEW, (receipt,)) in institutional_views(world, BUYER)
    # Preserve the V1 asymmetry: only the paid party reads anything at all.
    assert institutional_view(world, SELLER, BUYER) == 0

    path = tmp_path / "bribery-memory.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert restored.relations.memories == world.relations.memories
    assert institutional_view(restored, BUYER, SELLER) == BRIBERY_VIEW

    world.clock = world.clock.advance(MEMORY_SPAN_DAYS // 2)
    memory = memories_of(world, BUYER, receipt)
    half = effective_salience(world, memory)
    assert 400 <= half <= 600
    assert institutional_view(world, BUYER, SELLER) == BRIBERY_VIEW * half // 1000
    world.clock = world.clock.advance(MEMORY_SPAN_DAYS)
    assert institutional_view(world, BUYER, SELLER) == 0


def test_bribery_rejection_creates_no_obligation_and_no_memory():
    world = world_with_knowledge()
    proposal = _offer(world)
    response = next(item for item in bribery_response_options(world, BUYER)
                    if item.proposal_id == proposal.id and item.response == "reject")
    execute_bribery_response(world, BUYER, response.id, _decision(world, response))
    assert world.relations.proposals[proposal.id].status == "rejected"
    assert not world.relations.obligations
    assert not world.relations.memories
    assert institutional_view(world, BUYER, SELLER) == 0
    assert institutional_view(world, SELLER, BUYER) == 0


def test_bribery_acceptance_without_payment_creates_no_memory():
    world = world_with_knowledge()
    proposal = _offer(world)
    response = next(item for item in bribery_response_options(world, BUYER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    execute_bribery_response(world, BUYER, response.id, _decision(world, response))
    assert world.relations.proposals[proposal.id].status == "accepted"
    assert world.relations.obligations[
        next(iter(world.relations.obligations))].status == "active"
    assert not world.relations.memories
    assert institutional_view(world, BUYER, SELLER) == 0
    assert institutional_view(world, SELLER, BUYER) == 0


def test_organization_with_a_bribery_affordance_is_included_in_monthly_turn():
    world = world_with_knowledge()
    organization = EntityRef("organization", "oficios-da-serra")
    world.economy.accounts["treasury:oficios-da-serra"] = MoneyAccount(
        id="treasury:oficios-da-serra", owner_ref=organization, balance=100)

    assert bribery_offer_options(world, organization)
    assert organization in monthly_actors(world)


@pytest.mark.parametrize("reason", ["funds", "authority"])
def test_bribery_payment_revalidates_owner_boundary(reason):
    world = world_with_knowledge()
    proposal = _offer(world)
    response = next(item for item in bribery_response_options(world, BUYER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    execute_bribery_response(world, BUYER, response.id, _decision(world, response))
    world.clock = world.clock.advance(1)
    payment = next(item for item in bribery_payment_options(world, SELLER)
                   if item.proposal_id == proposal.id)
    if reason == "funds":
        account = world.economy.accounts[payment.source_account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    else:
        world.authority.offices = {key: office for key, office in world.authority.offices.items()
                                   if office.institution_ref != SELLER}
    with pytest.raises(ValueError):
        execute_bribery_payment(world, SELLER, payment.id, _decision(world, payment))
    assert world.relations.obligations[payment.obligation_id].status == "active"
