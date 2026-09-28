"""A concession can emerge from scarcity without a battle or a script."""

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.sim.medieval.commitments import resolve_diplomacy
from src.sim.medieval.demand import reserve_quantity
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_memory import institutional_view
from src.sim.medieval.intelligence import refresh_trade_reports
from src.sim.medieval.procurement import review_supply
from src.sim.medieval.reciprocal_supply import (fulfill_resource_transfer, reciprocal_response_options,
                                                reciprocal_supply_options, offer_reciprocal_supply,
                                                resource_transfer_options, respond_reciprocal_supply,
                                                remediate_resource_transfer,
                                                resource_transfer_remediation_options)
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.persistence import world_snapshot
from src.sim.medieval.diplomacy_policy import _diplomacy_situation
from src.systems.calendar_agenda import ScheduledSituation
from tests.test_medieval_institutional_aid import PROVIDER, REQUESTER, prepared_world


def decide(world, option):
    return record_event(world, "reciprocal_supply_decided", "Decisão institucional recíproca.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        causal_payload={"decision_source": {"kind": "api"}},
                        decision=option.decision())


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
    # Keep the fixture genuinely dependent on a reciprocal offer: the
    # requester's other food stores cannot cover this shortage, and the blocked
    # plan must be based on current, causal inventory reports.
    for stock_id in ("stock:campomanso", "stock:pontenegro"):
        local = world.economy.stocks[stock_id]
        world.economy.stocks[stock_id] = local.model_copy(update={"goods": {**local.goods, "food": 0}})
    refresh_trade_reports(world)
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


def test_deterministic_copy_of_a_reciprocal_option_cannot_create_a_proposal():
    world = scarce_world()
    option = next(item for item in reciprocal_supply_options(world, REQUESTER)
                  if item.counterparty_ref == PROVIDER)
    decision = record_event(world, "reciprocal_supply_decided", "Payload idêntico sem escolha de ator.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="current actor decision"):
        offer_reciprocal_supply(world, REQUESTER, option.id, decision.id)

    assert world_snapshot(world) == before


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
    food_decision = decide(world, food_option)
    food_order = fulfill_resource_transfer(world, PROVIDER, food_option.id, food_decision.id)
    food_receipt = world.event_index()[food_order.last_event_id]
    food_obligation_receipt = world.event_index()[world.relations.obligations[obligations[0].id].last_event_id]
    food_authorship = {"decision_event_id": food_decision.id,
                       "actor_ref": PROVIDER.to_dict(),
                       "selected_affordance_id": food_option.id}
    assert food_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert food_receipt.causal_payload == food_authorship
    assert food_obligation_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert food_obligation_receipt.causal_payload == food_authorship
    assert world.relations.obligations[obligations[0].id].status == "fulfilled"
    assert (food_order.source_id, food_order.resource_id, food_order.quantity) == (
        delivery.source_stock_id, "food", delivery.quantity)
    assert world.economy.stocks[delivery.source_stock_id].goods["food"] == (
        goods[delivery.source_stock_id]["food"] - delivery.quantity)

    # Only then can the requester execute its own separate concession.
    pledge_option = next(item for item in resource_transfer_options(world, REQUESTER)
                         if item.obligation_id == obligations[1].id)
    pledge_decision = decide(world, pledge_option)
    pledge_order = fulfill_resource_transfer(world, REQUESTER, pledge_option.id, pledge_decision.id)
    pledge_receipt = world.event_index()[pledge_order.last_event_id]
    assert pledge_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert pledge_receipt.causal_payload == {
        "decision_event_id": pledge_decision.id,
        "actor_ref": REQUESTER.to_dict(),
        "selected_affordance_id": pledge_option.id,
    }
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


def test_material_sale_of_the_promised_stock_records_an_authored_breach():
    from src.sim.medieval.markets import purchase
    from src.sim.medieval.tariffs import export_fee, export_quote

    world = scarce_world(pledge_amount=200)
    _, agreement = accepted_commitment(world)
    pledge = agreement.clauses[1]
    obligation_id = f"{agreement.id}:term:1"
    delivery_id = f"{agreement.id}:term:0"
    delivery_option = next(item for item in resource_transfer_options(world, PROVIDER)
                           if item.obligation_id == delivery_id)
    fulfill_resource_transfer(world, PROVIDER, delivery_option.id,
                              decide(world, delivery_option).id)
    source = world.economy.stocks[pledge.source_stock_id]
    destination = world.economy.stocks[pledge.destination_stock_id]
    market = world.economy.markets[source.location_id]
    quote = export_quote(world, source.id, destination.id)
    quantity = source.goods[pledge.resource_id]
    unit_price = market.prices[pledge.resource_id]
    fee = export_fee(quantity, unit_price, quote["export_rate_permille"])
    terms = {
        "source_id": source.id, "destination_id": destination.id,
        "resource_id": pledge.resource_id, "quantity": quantity,
        "unit_price": unit_price, "quote_day": market.updated_day,
        "route_ids": list(pledge.route_ids),
        "seller_account_id": f"treasury:{source.owner_ref.id}",
        "buyer_account_id": f"treasury:{destination.owner_ref.id}",
        **quote, "total_price": quantity * unit_price + fee,
    }
    decisions = []
    for action, owner in (("buy", destination.owner_ref), ("sell", source.owner_ref)):
        decisions.append(record_event(
            world, f"{action}_decided", "Consentimento bilateral para venda do estoque.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_source": {"kind": "api"}},
            decision={**terms, "action": action, "actor_ref": owner.to_dict()},
        ))

    order = purchase(world, decisions[0].id, decisions[1].id)
    obligation = world.relations.obligations[obligation_id]
    breach = world.event_index()[obligation.breach_event_id]
    assert obligation.status == "breached"
    assert breach.causal_payload["breach_kind"] == "materially_incompatible_action"
    assert breach.causal_payload["material_event_id"] == order.last_event_id
    assert {link.cause_event_id for link in breach.causal_links} >= {
        decisions[1].id, order.last_event_id,
    }
    assert source.id == pledge.source_stock_id
    assert world.economy.stocks[source.id].goods[pledge.resource_id] < pledge.quantity
    notices = {notice.recipient_ref for notice in world.knowledge.notices.values()
               if notice.event_id == breach.id}
    assert {REQUESTER, PROVIDER} <= notices
    history = _diplomacy_situation(world, PROVIDER, ())
    assert any(item["obligation_id"] == obligation_id and item["kind"] == "materially_breached"
               for item in history["known_counterparty_breaches"])
    from src.server.medieval.queries import diplomacy_view
    assert any(item.event_id == breach.id and item.kind == "commitment_materially_breached"
               for item in diplomacy_view(world).memories)


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
    freight_receipt = world.event_index()[order.last_event_id]
    expected_authorship = {"decision_event_id": decision.id, "actor_ref": PROVIDER.to_dict(),
                           "selected_affordance_id": option.id}
    assert receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert receipt.causal_payload == expected_authorship
    assert freight_receipt.causal_origin is CausalOrigin.ACTOR_DECISION
    assert freight_receipt.causal_payload == expected_authorship
    assert decision.id in {link.cause_event_id for link in receipt.causal_links}
    assert before_breach in {link.cause_event_id for link in receipt.causal_links}
