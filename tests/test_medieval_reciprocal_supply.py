"""A concession can emerge from scarcity without a battle or a script."""

from src.classes.event import FactKind
from src.sim.medieval.commitments import resolve_diplomacy
from src.sim.medieval.demand import reserve_quantity
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_memory import institutional_view
from src.sim.medieval.procurement import review_supply
from src.sim.medieval.reciprocal_supply import (fulfill_resource_transfer, reciprocal_response_options,
                                                reciprocal_supply_options, offer_reciprocal_supply,
                                                resource_transfer_options, respond_reciprocal_supply,
                                                remediate_resource_transfer,
                                                resource_transfer_remediation_options)
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.systems.calendar_agenda import ScheduledSituation
from tests.test_medieval_institutional_aid import PROVIDER, REQUESTER, prepared_world


def decide(world, option):
    return record_event(world, "reciprocal_supply_decided", "Decisão institucional recíproca.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def scarce_world(free_food=100, pledge_stock="stock:pedraclara", pledge_resource="tools", pledge_amount=200):
    """Reuse the aid fixture: real deficit, no cash path, a real own surplus."""
    world = prepared_world()
    stock = world.economy.stocks[pledge_stock]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, pledge_resource: pledge_amount}})
    account = world.economy.accounts[f"treasury:{REQUESTER.id}"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    source = world.economy.stocks["stock:portovelho"]
    world.economy.stocks[source.id] = source.model_copy(update={"goods": {
        **source.goods, "food": reserve_quantity(world, source.id, "food") + free_food}})
    review_supply(world)
    refresh_route_reports(world)
    return world


def accepted_commitment(world):
    """Offer, counterproposal from the counterpart's own holdings, acceptance."""
    option = next(item for item in reciprocal_supply_options(world, REQUESTER)
                  if item.counterparty_ref == PROVIDER)
    offer_reciprocal_supply(world, REQUESTER, option.id, decide(world, option).id)
    counter = next(item for item in reciprocal_response_options(world, PROVIDER) if item.kind == "counter")
    proposal = respond_reciprocal_supply(world, PROVIDER, counter.id, decide(world, counter).id)
    accept = next(item for item in reciprocal_response_options(world, REQUESTER)
                  if item.kind == "accept" and item.proposal_id == proposal.id)
    return option, respond_reciprocal_supply(world, REQUESTER, accept.id, decide(world, accept).id)


def test_a_scarce_city_trades_a_real_concession_through_two_independent_deliveries():
    world = scarce_world()
    offer, agreement = accepted_commitment(world)

    original = world.relations.proposals[agreement.parent_id]
    assert original.status == "superseded" and original.clauses[0].quantity == offer.food_quantity
    assert agreement.status == "accepted" and agreement.proposer_ref == PROVIDER
    delivery, concession = agreement.clauses
    assert delivery.quantity < offer.food_quantity and concession.depends_on == (0,)
    assert delivery.debtor_ref == PROVIDER and concession.debtor_ref == REQUESTER
    obligations = {item.clause_index: item for item in world.relations.obligations.values()
                   if item.proposal_id == agreement.id}
    assert {item.status for item in obligations.values()} == {"active"}
    goods = {key: dict(item.goods) for key, item in world.economy.stocks.items()}
    money = sum(item.balance for item in world.economy.accounts.values())
    assert not world.economy.freight_orders, "acceptance moves nothing"

    # The counterpart delivers first, on its own current decision.
    assert not resource_transfer_options(world, REQUESTER), "the concession waits for its dependency"
    food_option = next(item for item in resource_transfer_options(world, PROVIDER)
                       if item.obligation_id == obligations[0].id)
    food_order = fulfill_resource_transfer(world, PROVIDER, food_option.id, decide(world, food_option).id)
    assert world.relations.obligations[obligations[0].id].status == "fulfilled"
    assert (food_order.source_id, food_order.resource_id, food_order.quantity) == (
        delivery.source_stock_id, "food", delivery.quantity)
    assert world.economy.stocks[delivery.source_stock_id].goods["food"] == (
        goods[delivery.source_stock_id]["food"] - delivery.quantity)

    # Only then can the requester execute its own separate concession.
    pledge_option = next(item for item in resource_transfer_options(world, REQUESTER)
                         if item.obligation_id == obligations[1].id)
    pledge_order = fulfill_resource_transfer(world, REQUESTER, pledge_option.id, decide(world, pledge_option).id)
    assert world.relations.obligations[obligations[1].id].status == "fulfilled"
    assert (pledge_order.resource_id, pledge_order.quantity) == (concession.resource_id, concession.quantity)
    assert sum(item.balance for item in world.economy.accounts.values()) == money
    for resource_id, moved in ((delivery.resource_id, delivery.quantity), (concession.resource_id, concession.quantity)):
        in_stocks = sum(item.goods.get(resource_id, 0) for item in world.economy.stocks.values())
        in_cargo = sum(parcel.quantity for parcel in world.economy.parcels.values()
                       if world.economy.freight_orders[parcel.order_id].resource_id == resource_id)
        assert in_stocks + in_cargo == sum(item.get(resource_id, 0) for item in goods.values())
        assert moved > 0


def test_an_unmet_delivery_breaches_with_evidence_and_closes_that_partner():
    world = scarce_world()
    _, agreement = accepted_commitment(world)
    delivery = agreement.clauses[0]
    obligation_id = f"{agreement.id}:term:0"

    world.clock = world.clock.advance(delivery.due_day + 1 - world.clock.absolute_day)
    resolve_diplomacy(world, [ScheduledSituation(obligation_id, "diplomacy", world.clock.absolute_day)])

    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == "breached" and obligation.breach_event_id
    assert not world.economy.freight_orders, "a breach forces no transfer"
    breach = next(item for item in world.events if item.id == obligation.breach_event_id)
    assert breach.event_type == "commitment_breached"
    for party in (REQUESTER, PROVIDER):
        assert any(notice.recipient_ref == party and notice.event_id == breach.id
                   for notice in world.knowledge.notices.values())
        assert any(memory.institution_ref == party and memory.event_id == breach.id
                   for memory in world.relations.memories.values())
    assert institutional_view(world, REQUESTER, PROVIDER) == -4
    assert institutional_view(world, PROVIDER, REQUESTER) == 0

    # The next partner choice is evidenced, not scripted: this counterpart is
    # no longer offered while the remembered breach still weighs.
    refresh_route_reports(world)
    assert not any(item.counterparty_ref == PROVIDER for item in reciprocal_supply_options(world, REQUESTER))


def test_non_aid_resource_transfer_can_be_repaired_by_a_fresh_owner_decision():
    world = scarce_world()
    _, agreement = accepted_commitment(world)
    delivery = agreement.clauses[0]
    obligation_id = f"{agreement.id}:term:0"
    world.clock = world.clock.advance(delivery.due_day + 1 - world.clock.absolute_day)
    resolve_diplomacy(world, [ScheduledSituation(obligation_id, "diplomacy", world.clock.absolute_day)])

    refresh_route_reports(world)
    options = resource_transfer_remediation_options(world, PROVIDER)
    assert options and all(item.obligation_id == obligation_id for item in options)
    option = options[0]
    decision = decide(world, option)
    before_breach = world.relations.obligations[obligation_id].breach_event_id
    order = remediate_resource_transfer(world, PROVIDER, option.id, decision.id)

    obligation = world.relations.obligations[obligation_id]
    assert obligation.status == "remediated"
    assert obligation.breach_event_id == before_breach
    assert obligation.remediation_material_event_id == order.last_event_id
    receipt = next(item for item in world.events if item.event_type == "resource_transfer_remediated")
    assert decision.id in {link.cause_event_id for link in receipt.causal_links}
    assert before_breach in {link.cause_event_id for link in receipt.causal_links}
