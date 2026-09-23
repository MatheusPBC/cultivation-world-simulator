"""Focused bilateral-consent checks for institutional market purchases."""

from tests.test_medieval_concurrent_civil_decision import REQUESTER, civil_pressure_world

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_trade_reports
from src.sim.medieval.market_purchase_policy import (
    market_purchase_acceptance_options,
    market_purchase_adapters,
)
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.procurement import market_purchase_options
from src.sim.medieval.route_intelligence import refresh_route_reports


def _prepared():
    world = civil_pressure_world()
    refresh_route_reports(world)
    refresh_trade_reports(world, replace_today=True)
    return world


def test_buyer_request_is_only_a_decision_until_seller_accepts():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    buyer = world.economy.accounts[option.buyer_account_id]
    seller = world.economy.accounts[option.seller_account_id]
    buyer_before, seller_before = buyer.balance, seller.balance

    request = record_event(world, "institutional_decision_turn_decided",
                           "O comprador pediu uma compra de mercado.",
                           fact_kind=FactKind.DECISION, decision=option.decision())

    assert request.decision == option.decision()
    assert not world.economy.freight_orders
    assert world.economy.accounts[buyer.id].balance == buyer_before
    assert world.economy.accounts[seller.id].balance == seller_before


def test_seller_acceptance_materializes_the_existing_purchase_executor():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    buyer_before = world.economy.accounts[option.buyer_account_id].balance
    request = record_event(world, "institutional_decision_turn_decided",
                           "O comprador pediu uma compra de mercado.",
                           fact_kind=FactKind.DECISION, decision=option.decision())
    seller_ref = world.economy.accounts[option.seller_account_id].owner_ref
    acceptance = market_purchase_acceptance_options(world, seller_ref)[0]
    assert acceptance.id in {item.id for item in concurrent_civil_options(world, seller_ref)}
    acceptance_decision = record_event(
        world, "institutional_decision_turn_decided", "O vendedor aceitou a compra.",
        fact_kind=FactKind.DECISION, decision=acceptance.decision())

    adapter = next(item for item in market_purchase_adapters()
                   if item.name == "market_purchase_acceptance")
    adapter.execute_fn(world, seller_ref, acceptance.id, acceptance_decision.id)

    orders = [order for order in world.economy.freight_orders.values()
              if order.source_id == option.source_id and order.destination_id == option.destination_id]
    assert len(orders) == 1
    assert world.economy.accounts[option.buyer_account_id].balance == buyer_before - option.total_price
    payment = next(event for event in world.events if event.event_type == "payment_completed")
    order_event = next(event for event in world.events if event.event_type == "freight_opened")
    seller_acceptance = next(event for event in world.events if event.event_type == "sell_decided")
    expected_payload = {"decision_event_id": request.id,
                        "actor_ref": request.decision["actor_ref"],
                        "selected_affordance_id": request.decision["selected_affordance_id"]}
    for event in (payment, order_event):
        assert event.causal_origin is CausalOrigin.ACTOR_DECISION
        assert event.causal_payload == expected_payload
        causes = {link.cause_event_id for link in event.causal_links}
        assert request.id in causes
        assert seller_acceptance.id in causes
    assert not market_purchase_acceptance_options(world, seller_ref)


def test_acceptance_recomposes_same_day_and_rejects_stale_request():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    record_event(world, "institutional_decision_turn_decided",
                 "O comprador pediu uma compra de mercado.",
                 fact_kind=FactKind.DECISION, decision=option.decision())
    seller_ref = world.economy.accounts[option.seller_account_id].owner_ref
    assert market_purchase_acceptance_options(world, seller_ref)

    world.clock = world.clock.advance(1)
    assert not market_purchase_acceptance_options(world, seller_ref)
