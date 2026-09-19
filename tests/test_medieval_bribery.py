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
from src.sim.medieval.events import record_event
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


def test_bribery_acceptance_is_independent_and_payment_is_later():
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


def test_bribery_rejection_creates_no_obligation():
    world = world_with_knowledge()
    proposal = _offer(world)
    response = next(item for item in bribery_response_options(world, BUYER)
                    if item.proposal_id == proposal.id and item.response == "reject")
    execute_bribery_response(world, BUYER, response.id, _decision(world, response))
    assert world.relations.proposals[proposal.id].status == "rejected"
    assert not world.relations.obligations


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
