"""Household migration preparation buys real local food through public offers."""

import pytest

from src.classes.event import FactKind
from src.classes.economy.models import Stock
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.sim.medieval.household_provisioning import buy_household_provisions, household_stock_id, review_household_provisions
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval.migration_policy import review_migration


def prepared_offer(pressure=100):
    world = create_medieval_world(73)
    group = next(group for group in world.society.population.values() if group.settlement_id == "pedraclara")
    account = world.economy.accounts[f"household:{group.id}"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 100})
    need = world.economy.needs["pedraclara"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": pressure})
    stock = world.economy.stocks[need.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": 10000}})
    refresh_reports(world)
    actor = EntityRef("population_group", group.id)
    offer = next(report for report in world.knowledge.for_actor(actor)
                 if report.kind == "offer" and report.resource_id == "food")
    seller = next(account for account in world.economy.accounts.values()
                  if account.owner_ref == world.economy.stocks[offer.stock_id].owner_ref)
    return world, group, offer, seller


def decisions(world, group, offer, seller, quantity=2):
    terms = {"group_id": group.id, "stock_id": offer.stock_id, "quantity": quantity,
             "unit_price": offer.unit_price, "seller_account_id": seller.id, "offer_id": offer.id}
    buy = record_event(world, "household_provisions_purchase_decided", "Comprar provisões.",
                       fact_kind=FactKind.DECISION,
                       decision={"action": "buy_household_provisions", "actor_ref": EntityRef("population_group", group.id).to_dict(), **terms})
    sell = record_event(world, "household_provisions_sale_decided", "Vender provisões.",
                        fact_kind=FactKind.DECISION,
                        decision={"action": "sell_household_provisions", "actor_ref": seller.owner_ref.to_dict(), **terms})
    return buy.id, sell.id


def test_public_offer_buys_real_food_into_a_bounded_household_pantry_without_consuming_it():
    world, group, offer, seller = prepared_offer()
    source_id = offer.stock_id
    buyer = world.economy.accounts[f"household:{group.id}"]
    before_food = world.economy.stocks[source_id].goods["food"]
    buyer_balance, seller_balance = buyer.balance, seller.balance
    pantry_id = household_stock_id(group.id)
    world.economy.stocks[pantry_id] = Stock(id=pantry_id, owner_ref=buyer.owner_ref,
                                            location_id=group.settlement_id, capacity=1, goods={}, last_event_ids={})
    buy, sell = decisions(world, group, offer, seller)
    receipt = buy_household_provisions(world, group_id=group.id, offer_id=offer.id, quantity=2,
                                       buyer_decision_id=buy, seller_decision_id=sell)
    pantry = world.economy.stocks[household_stock_id(group.id)]
    assert world.economy.stocks[source_id].goods["food"] == before_food - 2 and pantry.goods["food"] == 2
    cost = 2 * offer.unit_price
    assert world.economy.accounts[buyer.id].balance == buyer_balance - cost
    assert world.economy.accounts[seller.id].balance == seller_balance + cost
    assert receipt.event_type == "household_provisions_purchased"
    assert any(delta.owner_id == pantry_id and delta.aspect == "capacity" for delta in receipt.deltas)


@pytest.mark.parametrize("invalid", ["stale", "authority", "replay"])
def test_executor_revalidates_current_bilateral_terms_before_any_effect(invalid):
    world, group, offer, seller = prepared_offer()
    buy, sell = decisions(world, group, offer, seller)
    before = (dict(world.economy.stocks[offer.stock_id].goods), world.economy.accounts[f"household:{group.id}"].balance)
    if invalid == "stale":
        world.clock = world.clock.advance(1)
    elif invalid == "authority":
        world.authority.offices.clear()
    else:
        world.economy.payments[buy] = "event:already-used"
    with pytest.raises(ValueError):
        buy_household_provisions(world, group_id=group.id, offer_id=offer.id, quantity=2,
                                 buyer_decision_id=buy, seller_decision_id=sell)
    assert (dict(world.economy.stocks[offer.stock_id].goods), world.economy.accounts[f"household:{group.id}"].balance) == before


def test_review_uses_pressure_and_public_offer_but_keeps_quiet_or_unfunded_households_idle():
    world, group, _, _ = prepared_offer()
    review_household_provisions(world)
    assert world.economy.stocks[household_stock_id(group.id)].goods["food"] > 0

    quiet, quiet_group, _, _ = prepared_offer(pressure=0)
    review_household_provisions(quiet)
    assert household_stock_id(quiet_group.id) not in quiet.economy.stocks


def test_one_public_offer_can_be_accepted_once_then_declined_without_breaking_the_month():
    world, group, offer, seller = prepared_offer()
    peers = [candidate for candidate in world.society.population.values()
             if candidate.settlement_id == group.settlement_id and candidate.id != group.id]
    peer = peers[0]
    for candidate in (group, peer):
        account = world.economy.accounts[f"household:{candidate.id}"]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 16})
    stock = world.economy.stocks[offer.stock_id]
    from src.sim.medieval.demand import reserve_quantity
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": reserve_quantity(world, stock.id) + 1}})
    review_household_provisions(world)
    assert len([event for event in world.events if event.event_type == "household_provisions_purchased"]) == 1
    assert len([event for event in world.events if event.event_type == "household_provisions_sale_declined"]) >= 1


def test_lost_trade_authority_after_publication_records_refusal_instead_of_raising():
    world, group, _, _ = prepared_offer()
    world.authority.offices.clear()
    review_household_provisions(world)
    assert household_stock_id(group.id) not in world.economy.stocks
    assert any(event.event_type == "household_provisions_sale_declined" for event in world.events)


def test_private_stock_without_a_public_offer_cannot_be_used_as_household_provision():
    world, group, offer, seller = prepared_offer()
    private = world.economy.stocks[offer.stock_id].model_copy(update={"id": "private-food", "owner_ref": EntityRef("polity", "valedouro")})
    world.economy.stocks[private.id] = private
    buy, sell = decisions(world, group, offer, seller)
    with pytest.raises(ValueError, match="public|seller"):
        buy_household_provisions(world, group_id=group.id, offer_id="offer:population_group:" + group.id + ":private-food:food",
                                 quantity=2, buyer_decision_id=buy, seller_decision_id=sell)


def test_round_trip_preserves_the_pantry_and_bilateral_receipt(tmp_path):
    world, group, offer, seller = prepared_offer()
    buy, sell = decisions(world, group, offer, seller)
    buy_household_provisions(world, group_id=group.id, offer_id=offer.id, quantity=2,
                             buyer_decision_id=buy, seller_decision_id=sell)
    path = tmp_path / "household-provisions.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.economy.stocks[household_stock_id(group.id)] == world.economy.stocks[household_stock_id(group.id)]
    assert resumed.economy.payments[buy] == world.economy.payments[buy]


def test_public_food_purchase_can_materially_enable_a_pressure_migration():
    world, group, _, _ = prepared_offer()
    account = world.economy.accounts[f"household:{group.id}"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 20000})
    pantry_id = household_stock_id(group.id)
    assert pantry_id not in world.economy.stocks
    need = world.economy.needs[group.settlement_id]
    world.economy.needs[need.id] = need.model_copy(update={"health": 600})
    world.knowledge.settlement_reports.pop(
        f"settlement_report:population_group:{group.id}:{group.settlement_id}")
    refresh_reports(world)
    before_food = sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
    before_money = sum(account.balance for account in world.economy.accounts.values())
    review_household_provisions(world)
    assert world.economy.stocks[pantry_id].goods["food"] > 0
    review_migration(world)
    assert any(journey.source_group_id == group.id for journey in world.society.migrations.values())
    carried = sum(provision.food for provision in world.economy.migration_provisions.values())
    assert sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values()) + carried == before_food
    assert sum(account.balance for account in world.economy.accounts.values()) == before_money
