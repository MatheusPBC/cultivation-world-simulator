"""Focused bilateral-consent checks for institutional market purchases."""

import json

from tests.test_medieval_concurrent_civil_decision import REQUESTER, civil_pressure_world

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_trade_reports
from src.sim.medieval.market_purchase_policy import (
    market_purchase_acceptance_options,
    market_purchase_adapters,
    market_purchase_response_actors,
)
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.procurement import market_purchase_options
from src.sim.medieval.procurement import execute_market_purchase_option
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.persistence import world_snapshot
import pytest


@pytest.mark.asyncio
async def test_refused_seller_request_does_not_consume_a_third_provider_call(monkeypatch):
    from src.sim.medieval import ai_decider, institutional_agenda

    world = _prepared()
    request_option = market_purchase_options(world, REQUESTER)[0]
    seller = world.economy.accounts[request_option.seller_account_id].owner_ref
    world.config = world.config.model_copy(update={"ai_calls_per_step": 2, "ai_max_calls": 2})
    monkeypatch.setattr(institutional_agenda, "monthly_actors", lambda _world: (REQUESTER, seller))
    monkeypatch.setattr(institutional_agenda, "monthly_adapters", lambda **_kwargs: market_purchase_adapters())
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    asked = []

    async def answer(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        asked.append(payload["you_are"])
        return {"selected_id": (request_option.id if payload["you_are"] == REQUESTER.to_dict()
                                else ai_decider.NO_ACTION)}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    await institutional_agenda.review_monthly_institutional_turn(world)

    assert asked == [REQUESTER.to_dict(), seller.to_dict()]
    assert seller not in market_purchase_response_actors(world)
    assert not world.economy.payments


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
                           fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                           decision=option.decision(), causal_payload={"decision_source": {"kind": "api"}})

    assert request.decision == option.decision()
    assert not world.economy.freight_orders
    assert world.economy.accounts[buyer.id].balance == buyer_before
    assert world.economy.accounts[seller.id].balance == seller_before


def test_deterministic_choice_cannot_materialize_a_current_market_purchase():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    decision = record_event(world, "institutional_decision_turn_decided",
                            "Intenção determinística de teste.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="stale or unknown"):
        execute_market_purchase_option(world, REQUESTER, option.id, decision.id,
                                       seller_decision_id="event:missing")

    assert world_snapshot(world) == before


def test_seller_acceptance_materializes_the_existing_purchase_executor():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    buyer_before = world.economy.accounts[option.buyer_account_id].balance
    request = record_event(world, "institutional_decision_turn_decided",
                           "O comprador pediu uma compra de mercado.",
                           fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                           decision=option.decision(), causal_payload={"decision_source": {"kind": "api"}})
    seller_ref = world.economy.accounts[option.seller_account_id].owner_ref
    acceptance = market_purchase_acceptance_options(world, seller_ref)[0]
    assert acceptance.id in {item.id for item in concurrent_civil_options(world, seller_ref)}
    acceptance_adapter = next(item for item in market_purchase_adapters()
                              if item.name == "market_purchase_acceptance")
    label = acceptance_adapter.label_fn(acceptance)
    assert acceptance.resource_id in label
    assert str(acceptance.quantity) in label
    assert acceptance.buyer_name in label
    assert str(acceptance.total_price) in label
    acceptance_decision = record_event(
        world, "institutional_decision_turn_decided", "O vendedor aceitou a compra.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=acceptance.decision(), causal_payload={"decision_source": {"kind": "api"}})

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
                 fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                 decision=option.decision(), causal_payload={"decision_source": {"kind": "api"}})
    seller_ref = world.economy.accounts[option.seller_account_id].owner_ref
    assert market_purchase_acceptance_options(world, seller_ref)

    world.clock = world.clock.advance(1)
    assert not market_purchase_acceptance_options(world, seller_ref)


def test_request_already_presented_to_seller_is_not_offered_again():
    world = _prepared()
    option = market_purchase_options(world, REQUESTER)[0]
    request = record_event(world, "institutional_decision_turn_decided",
                           "O comprador pediu uma compra de mercado.",
                           fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                           decision=option.decision(), causal_payload={"decision_source": {"kind": "api"}})
    seller_ref = world.economy.accounts[option.seller_account_id].owner_ref
    assert market_purchase_acceptance_options(world, seller_ref)

    record_event(
        world, "ai_decision_declined", "O vendedor recusou agir.",
        causal_payload={"selection": {"actor_ref": seller_ref.to_dict(),
                                      "selected_affordance_id": "NO_ACTION"}},
        cause_ids=(request.id,))

    # Keep the request selectable during owner revalidation; only the targeted
    # post-pass excludes a seller who has already seen it today.
    assert market_purchase_acceptance_options(world, seller_ref)
    assert seller_ref not in market_purchase_response_actors(world)
