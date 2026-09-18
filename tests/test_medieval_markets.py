import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.tariffs import export_fee, export_quote


def market_world():
    world = create_medieval_world(73)
    assert hasattr(world.economy, "markets"), "local market state missing"
    world.economy.facilities.clear()
    return world


def terms(world, *, source="stock:campomanso", destination="stock:portovelho", quantity=100,
          resource="food", routes=("road-campomanso-pedraclara", "river-pedraclara-portovelho")):
    seller = world.economy.stocks[source]
    buyer = world.economy.stocks[destination]
    market = world.economy.markets[seller.location_id]
    quote = export_quote(world, source, destination)
    fee = export_fee(quantity, market.prices[resource], quote["export_rate_permille"])
    return {"source_id": source, "destination_id": destination, "resource_id": resource,
            "quantity": quantity, "unit_price": market.prices[resource], "quote_day": market.updated_day,
            "route_ids": list(routes), "seller_account_id": f"treasury:{seller.owner_ref.id}",
            "buyer_account_id": f"treasury:{buyer.owner_ref.id}", **quote,
            "total_price": quantity * market.prices[resource] + fee}


def consent(world, values):
    decisions = []
    for action, stock_field in (("buy", "destination_id"), ("sell", "source_id")):
        owner = world.economy.stocks[values[stock_field]].owner_ref
        decisions.append(record_event(world, f"{action}_decided", "Termos comerciais aceitos.",
                                       fact_kind=FactKind.DECISION,
                                       decision={**values, "action": action, "actor_ref": owner.to_dict()}).id)
    return tuple(decisions)


def decide_one(world, action, stock_field, values):
    owner = world.economy.stocks[values[stock_field]].owner_ref
    return record_event(world, f"{action}_decided", "Termos comerciais aceitos.",
                        fact_kind=FactKind.DECISION,
                        decision={**values, "action": action, "actor_ref": owner.to_dict()}).id


@pytest.mark.parametrize("stale_side", ["buyer", "seller"])
def test_stale_buyer_or_seller_decision_is_rejected_despite_a_still_valid_quote(stale_side):
    from src.systems.time import WorldClock
    from src.sim.medieval.markets import purchase
    world = market_world()
    values = terms(world)
    if stale_side == "buyer":
        buy_id = decide_one(world, "buy", "destination_id", values)
        world.clock = WorldClock(1)
        sell_id = decide_one(world, "sell", "source_id", values)
    else:
        sell_id = decide_one(world, "sell", "source_id", values)
        world.clock = WorldClock(1)
        buy_id = decide_one(world, "buy", "destination_id", values)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale"):
        purchase(world, buy_id, sell_id)
    assert world_snapshot(world) == before


def test_purchase_with_current_decisions_succeeds_even_if_the_quote_predates_today():
    from src.systems.time import WorldClock
    from src.sim.medieval.markets import purchase
    world = market_world()
    values = terms(world)
    world.clock = WorldClock(1)  # market has not refreshed yet; the quote is still valid.
    decisions = consent(world, values)
    order = purchase(world, *decisions)
    assert order.owner_ref.id == "valedouro"


async def test_purchase_transfers_money_and_cargo_ownership_but_not_instant_delivery(tmp_path):
    world = market_world()
    from src.sim.medieval.markets import purchase
    values = terms(world)
    decisions = consent(world, values)
    money = sum(a.balance for a in world.economy.accounts.values())
    order = purchase(world, *decisions)
    assert order.owner_ref.id == "valedouro"
    assert world.economy.accounts["treasury:auren"].balance == 20400
    assert world.economy.accounts["treasury:valedouro"].balance == 19600
    assert sum(a.balance for a in world.economy.accounts.values()) == money
    assert world.economy.stocks["stock:campomanso"].goods["food"] == 3200
    assert world.economy.stocks["stock:portovelho"].goods["food"] == 6000
    path = tmp_path / "trade.mws"
    save_world(world, path)
    world = load_world(path)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="executed"):
        purchase(world, *decisions)
    assert world_snapshot(world) == before
    while world.economy.parcels:
        await MedievalSimulator(world).step()
    assert world.economy.stocks["stock:portovelho"].goods["food"] == 6100
    assert world.economy.freight_orders[order.id].delivered_quantity == 100


def test_trade_cannot_use_only_one_partys_decision():
    world = market_world()
    from src.sim.medieval.markets import purchase
    decisions = consent(world, terms(world))
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="consent"):
        purchase(world, decisions[0], decisions[0])
    assert world_snapshot(world) == before


@pytest.mark.parametrize("invalid", ["price", "funds", "owner", "quantity"])
def test_invalid_purchase_is_atomic(invalid):
    world = market_world()
    from src.sim.medieval.markets import purchase
    values = terms(world)
    if invalid == "price":
        values["unit_price"] = 999
    elif invalid == "funds":
        account = world.economy.accounts["treasury:valedouro"]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 1})
    elif invalid == "owner":
        values["buyer_account_id"] = "treasury:escarlia"
    else:
        values["quantity"] = 99999
    decisions = consent(world, values)
    before = world_snapshot(world)
    with pytest.raises(ValueError):
        purchase(world, *decisions)
    assert world_snapshot(world) == before


async def test_local_purchase_delivers_without_inventing_a_route():
    world = market_world()
    from src.sim.medieval.markets import purchase
    values = terms(world, source="stock:ferroalto", destination="stock:oficios-da-serra",
                   quantity=10, resource="iron", routes=())
    order = purchase(world, *consent(world, values))
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == 1
    assert world.economy.stocks["stock:oficios-da-serra"].goods["iron"] == 70
    assert not world.economy.route_flows
    assert world.economy.freight_orders[order.id].delivered_quantity == 10


async def test_shortage_and_abundance_move_prices_in_opposite_bounded_steps():
    world = market_world()
    for location, amount in (("pedraclara", 0), ("portovelho", 30000)):
        stock = world.economy.stocks[f"stock:{location}"]
        world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": amount}})
    await MedievalSimulator(world).step()
    assert world.economy.markets["pedraclara"].prices["food"] == 5
    assert world.economy.markets["portovelho"].prices["food"] == 3
    assert world.economy.markets["pedraclara"].updated_day == 30


@pytest.mark.asyncio
async def test_repair_demand_sets_a_local_quote_with_causal_receipt_and_existing_reports():
    """The market derives price; actors only receive its ordinary published quote."""
    from src.sim.medieval.economy import _delta
    from src.sim.medieval.infrastructure import damage_site, review_maintenance
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.markets import purchase, update_markets
    from src.classes.governance.models import Objective
    from src.systems.time import WorldClock

    world = market_world()
    site_id = "docas-de-portovelho"
    site = world.map.infrastructure_sites[site_id]
    damage = record_event(world, "storm_damaged_site", "Docas danificadas.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("site", site_id, "integrity", site.integrity, 0.0),))
    damage_site(world, site_id, event_id=damage.id)
    refresh_reports(world)
    review_maintenance(world)
    project = next(project for project in world.economy.repairs.values() if project.site_id == site_id)
    site_report = world.knowledge.site_report(project.maintainer_ref, site_id)
    blueprint = world.economy.repair_blueprints[project.blueprint_id]

    control = market_world()
    for candidate in (world, control):
        repair_stock = candidate.economy.stocks[project.stock_id]
        candidate.economy.stocks[repair_stock.id] = repair_stock.model_copy(
            update={"goods": {**repair_stock.goods,
                               **{resource_id: amount * 10 for resource_id, amount in blueprint.inputs.items()},
                               "tools": 11}})
        public_stock = candidate.economy.stocks["stock:portovelho"]
        candidate.economy.stocks[public_stock.id] = public_stock.model_copy(
            update={"goods": {**public_stock.goods, "tools": 0}})
        market = candidate.economy.markets["portovelho"]
        candidate.economy.markets[market.id] = market.model_copy(update={"prices": {**market.prices, "tools": 35}})
    world.clock = control.clock = WorldClock(30)
    update_markets(world)
    update_markets(control)

    market = world.economy.markets["portovelho"]
    assert market.prices["tools"] > control.economy.markets["portovelho"].prices["tools"]
    receipt = next(event for event in world.events if event.id == market.last_event_id)
    assert any(delta.owner_kind == "market" and delta.owner_id == market.id and delta.aspect == "tools"
               for delta in receipt.deltas)
    assert project.last_event_id in {link.cause_event_id for link in receipt.causal_links}
    assert site_report.event_id in {link.cause_event_id for link in receipt.causal_links}

    stock = world.economy.stocks[project.stock_id]
    buyer_stock = world.economy.stocks["stock:portovelho"]
    objective_id = f"inputs:{buyer_stock.id}:tools"
    world.strategy.objectives[objective_id] = Objective(
        id=objective_id, actor_ref=buyer_stock.owner_ref, settlement_id=buyer_stock.location_id,
        stock_id=buyer_stock.id, resource_id="tools", kind="maintain_production_inputs",
        motivation="Manter ferramentas para o trabalho produtivo.")
    refresh_reports(world)
    owner_report = next(report for report in world.knowledge.for_actor(project.maintainer_ref)
                        if report.kind == "inventory" and report.stock_id == stock.id and report.resource_id == "tools")
    assert (owner_report.publisher_ref, owner_report.recipient_ref) == (stock.owner_ref, project.maintainer_ref)
    assert owner_report.unit_price == market.prices["tools"] and owner_report.quote_day == 30

    offer = next(report for report in world.knowledge.for_actor(buyer_stock.owner_ref)
                 if report.kind == "offer" and report.stock_id == stock.id and report.resource_id == "tools")
    assert offer.unit_price == market.prices["tools"] and offer.quantity == 1
    values = terms(world, source=stock.id, destination=buyer_stock.id, quantity=1, resource="tools", routes=())
    assert (values["unit_price"], values["quote_day"]) == (offer.unit_price, offer.quote_day)
    order = purchase(world, *consent(world, values))
    await MedievalSimulator(world).step()
    assert world.economy.freight_orders[order.id].delivered_quantity == 1
    await MedievalSimulator(world).step()
    assert world.economy.repairs[project.id].restored_permille == 100


async def test_prepared_trade_scenario_recovers_after_blockade_and_preserves_accounts(tmp_path):
    from tools.medieval_trade_smoke import run
    result = await run(73, tmp_path / "trade-smoke.mws")
    assert result["day"] == 60
    assert result["missing_food_during_blockade"] == 2000
    assert result["missing_food_after_delivery"] == 0
    assert result["health_during_blockade"] == 900
    assert result["health_after_delivery"] == 920
    assert result["delivered"] == 2400
    # Both treasuries also own settlements elsewhere in the world, and now
    # that public relief is a chosen act rather than an automatic subsidy,
    # those settlements' own real hunger drives valedouro and auren through
    # further, unrelated food purchases across the same 60 days. Money is
    # never lost to that background trade -- run() enforces conservation on
    # every step -- so these balances are the deterministic result of the
    # scripted purchase plus that autonomous activity, not just the trade.
    assert result["buyer_balance"] == 14580
    # Trade income remains real; the monthly irrigation project also pays
    # one named researcher and two assistants at 2 coins each on day 60.
    assert result["seller_balance"] == 31394
    assert result["food_conserved"] and result["save_load_equivalent"]
