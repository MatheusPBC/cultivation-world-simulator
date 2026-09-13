import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


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
    return {"source_id": source, "destination_id": destination, "resource_id": resource,
            "quantity": quantity, "unit_price": market.prices[resource], "quote_day": market.updated_day,
            "route_ids": list(routes), "seller_account_id": f"treasury:{seller.owner_ref.id}",
            "buyer_account_id": f"treasury:{buyer.owner_ref.id}"}


def consent(world, values):
    decisions = []
    for action, stock_field in (("buy", "destination_id"), ("sell", "source_id")):
        owner = world.economy.stocks[values[stock_field]].owner_ref
        decisions.append(record_event(world, f"{action}_decided", "Termos comerciais aceitos.",
                                       fact_kind=FactKind.DECISION,
                                       decision={**values, "action": action, "actor_ref": owner.to_dict()}).id)
    return tuple(decisions)


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


async def test_prepared_trade_scenario_recovers_after_blockade_and_preserves_accounts(tmp_path):
    from tools.medieval_trade_smoke import run
    result = await run(73, tmp_path / "trade-smoke.mws")
    assert result["day"] == 60
    assert result["missing_food_during_blockade"] == 2000
    assert result["missing_food_after_delivery"] == 0
    assert result["health_during_blockade"] == 900
    assert result["health_after_delivery"] == 920
    assert result["delivered"] == 2400
    assert result["buyer_balance"] == 10400
    # Trade income remains real; the monthly irrigation project also pays
    # one named researcher and two assistants at 2 coins each on day 60.
    assert result["seller_balance"] == 29594
    assert result["food_conserved"] and result["save_load_equivalent"]
