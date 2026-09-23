"""Households buy actual local rations; whatever stays unpaid stays missing."""

import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import consume_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import world_snapshot, save_world, load_world
from src.systems.time import WorldClock


def prepared_consumers(food=2400, cash=10):
    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    group = sorted((g for g in world.society.population.values()
                    if g.settlement_id == "pedraclara"), key=lambda g: g.id)[0]
    account = world.economy.accounts[f"household:{group.id}"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": cash})
    stock = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": food}})
    return world, group, account.id


def total_money(world):
    return sum(a.balance for a in world.economy.accounts.values())


def test_families_pay_only_whole_received_rations_and_unpaid_demand_stays_missing():
    world, group, account_id = prepared_consumers()
    initial = total_money(world)
    consume_monthly(world)
    assert world.economy.accounts[account_id].balance == 2  # two rations at4
    assert world.economy.accounts["treasury:auren"].balance == 20008
    # Only the two rations actually bought leave the granary; nobody else in
    # pedraclara could pay, and no automatic relief tops up the rest for free.
    assert world.economy.stocks["stock:pedraclara"].goods["food"] == 2398
    assert world.economy.needs["pedraclara"].missing_food == 2398
    assert total_money(world) == initial
    purchase = next(e for e in world.events if e.event_type == "household_purchase_completed")
    assert {(d.owner_kind, d.aspect, d.before, d.after) for d in purchase.deltas} >= {
        ("stock", "food", "2400", "2398"), ("account", "balance", "10", "2")}
    decisions = [e for e in world.events if e.id in {c.cause_event_id for c in purchase.causal_links}
                 and e.fact_kind == FactKind.DECISION]
    assert {e.decision["action"] for e in decisions} == {"buy_rations", "sell_rations"}
    assert all(not e.deltas for e in decisions)
    final = next(e for e in world.events if e.id == world.economy.needs["pedraclara"].last_event_id)
    assert purchase.id in {c.cause_event_id for c in final.causal_links}
    assert final.causal_payload["subsistence"] == {
        "settlement_id": "pedraclara",
        "required": 2400,
        "public_required": 2400,
        "domestic_quantity": 0,
        "purchased_quantity": 2,
        "missing_food": 2398,
        "household_group_ids": sorted(
            group.id for group in world.society.population.values()
            if group.settlement_id == "pedraclara"
        ),
            "unaffordable_by_group": {
                group.id: (world.society.available_count(group.id) - (2 if account_id == f"household:{group.id}" else 0))
                for group in world.society.population.values()
                if group.settlement_id == "pedraclara"
            },
            "unmet_by_group": {
                group.id: (world.society.available_count(group.id) - (2 if account_id == f"household:{group.id}" else 0))
                for group in world.society.population.values()
                if group.settlement_id == "pedraclara"
            },
        }


def test_empty_granary_cannot_charge_savings():
    world, _, account_id = prepared_consumers(food=0)
    consume_monthly(world)
    assert world.economy.accounts[account_id].balance == 10
    assert world.economy.needs["pedraclara"].missing_food == 2400
    assert not any(e.event_type == "household_purchase_completed" for e in world.events)


def test_shortage_allocates_by_people_not_wealth():
    world, _, account_id = prepared_consumers(food=5, cash=100)
    # Local cohorts have480/480/960/480 people. Five rations split1/1/2/1.
    # Only this one group can actually pay; the other three cannot, and
    # nothing tops up their share for free, so it stays in the granary.
    consume_monthly(world)
    assert world.economy.accounts[account_id].balance == 96
    assert world.economy.accounts["treasury:auren"].balance == 20004
    assert world.economy.needs["pedraclara"].missing_food == 2399
    assert world.economy.stocks["stock:pedraclara"].goods["food"] == 4


def test_remainder_allocation_is_stable_and_does_not_drop_a_ration():
    from src.classes.society.models import PopulationGroup
    from src.sim.medieval.consumption import ration_shares
    groups = [PopulationGroup(id=name, settlement_id="place", people="human", occupation="artisan", count=count)
              for name, count in [("b", 1), ("a", 1), ("c", 1)]]
    assert ration_shares(groups, 2) == {"a": 1, "b": 1, "c": 0}
    assert ration_shares(list(reversed(groups)), 2) == {"a": 1, "b": 1, "c": 0}


def test_no_commercial_mandate_means_no_charge_and_food_stays_missing():
    world, _, account_id = prepared_consumers()
    world.authority.offices.clear()
    consume_monthly(world)
    assert world.economy.accounts[account_id].balance == 10
    assert world.economy.stocks["stock:pedraclara"].goods["food"] == 2400
    assert world.economy.needs["pedraclara"].missing_food == 2400


async def test_income_consumption_finances_next_production_month_and_resumes(tmp_path):
    from src.sim.medieval.engine import MedievalSimulator
    world = create_medieval_world(73)
    farm_id = "works:campos-do-lume"
    farm = world.economy.facilities[farm_id]
    world.economy.facilities = {farm_id: farm.model_copy(update={"max_batches": 2, "wage_per_worker": 2})}
    treasury = world.economy.accounts["treasury:auren"]
    world.economy.accounts[treasury.id] = treasury.model_copy(update={"balance": 50})
    world.strategy.objectives.clear()  # Prepared local circuit, no foreign procurement.
    before = total_money(world)
    await MedievalSimulator(world).step()
    assert world.economy.payrolls[farm_id].gross == 40
    assert world.economy.payrolls[farm_id].tax == 4
    assert world.economy.accounts[treasury.id].balance == 50  # wages-40, tax+4, food+36
    assert sum(a.balance for a in world.economy.accounts.values() if a.owner_ref.kind == "population_group") == 0
    path = tmp_path / "circulation.mws"
    save_world(world, path)
    resumed = load_world(path)
    await MedievalSimulator(world).step()
    await MedievalSimulator(resumed).step()
    # The monthly institutional turn may leave a dated diplomacy review for
    # the next day; save/load must preserve that real deadline instead of
    # skipping to the next month boundary.
    assert world.clock.absolute_day == 31
    assert world.economy.facilities[farm_id].last_batches == 2
    assert world.economy.payrolls[farm_id].gross == 40
    assert total_money(world) == before
    assert (world_snapshot(world), world.events) == (world_snapshot(resumed), resumed.events)


def test_monthly_consumption_is_not_repeated_after_save_load(tmp_path):
    world, _, _ = prepared_consumers(food=7200)
    consume_monthly(world)
    path = tmp_path / "consumption.mws"
    save_world(world, path)
    resumed = load_world(path)
    before = world_snapshot(resumed), list(resumed.events)
    consume_monthly(resumed)
    assert (world_snapshot(resumed), resumed.events) == before


def decisions(world, group, *, quantity=2, price=4):
    terms = {"group_id": group.id, "stock_id": "stock:pedraclara", "quantity": quantity,
             "unit_price": price, "seller_account_id": "treasury:auren"}
    buyer = record_event(world, "ration_purchase_decided", "Comprar alimento.", fact_kind=FactKind.DECISION,
                         decision={"action": "buy_rations", "actor_ref": {"kind": "population_group", "id": group.id}, **terms})
    seller = record_event(world, "ration_sale_decided", "Vender alimento.", fact_kind=FactKind.DECISION,
                          decision={"action": "sell_rations", "actor_ref": {"kind": "polity", "id": "auren"}, **terms})
    return buyer.id, seller.id


@pytest.mark.parametrize("missing_party", [0, 1])
def test_save_rejects_missing_purchase_receipt_without_overwriting(tmp_path, missing_party):
    from src.sim.medieval.consumption import buy_rations
    world, group, _ = prepared_consumers()
    buyer, seller = decisions(world, group)
    buy_rations(world, group_id=group.id, stock_id="stock:pedraclara", quantity=2, unit_price=4,
                seller_account_id="treasury:auren", buyer_decision_id=buyer, seller_decision_id=seller)
    path = tmp_path / "bilateral.mws"
    save_world(world, path)
    before = path.read_bytes()
    del world.economy.payments[(buyer, seller)[missing_party]]
    with pytest.raises(ValueError, match="receipt"):
        save_world(world, path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("invalid", ["consent", "authority", "cash", "food", "price", "location", "actor", "replay"])
def test_ration_executor_revalidates_both_parties_before_any_effect(invalid):
    import src.sim.medieval.consumption as consumption
    world, group, account_id = prepared_consumers()
    buyer, seller = decisions(world, group)
    if invalid == "consent":
        seller = buyer
    elif invalid == "authority":
        world.authority.offices.clear()
    elif invalid == "cash":
        world.economy.accounts[account_id] = world.economy.accounts[account_id].model_copy(update={"balance": 7})
    elif invalid == "food":
        stock = world.economy.stocks["stock:pedraclara"]
        world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 1}})
    elif invalid == "price":
        world.economy.markets["pedraclara"].prices["food"] = 5
    elif invalid == "location":
        world.society.population[group.id] = group.model_copy(update={"settlement_id": "campomanso"})
    elif invalid == "actor":
        world.events[-1].decision["actor_ref"]["id"] = "valedouro"
    kwargs = dict(group_id=group.id, stock_id="stock:pedraclara", quantity=2, unit_price=4,
                  seller_account_id="treasury:auren", buyer_decision_id=buyer, seller_decision_id=seller)
    if invalid == "replay":
        consumption.buy_rations(world, **kwargs)
    before = world_snapshot(world), list(world.events)
    with pytest.raises(ValueError):
        consumption.buy_rations(world, **kwargs)
    assert (world_snapshot(world), world.events) == before
