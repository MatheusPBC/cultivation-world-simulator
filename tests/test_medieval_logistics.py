import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot

ROAD = "road-campomanso-pedraclara"
SOURCE = "stock:campomanso"
DEST = "stock:pedraclara"


def cargo_world():
    world = create_medieval_world(73)
    assert hasattr(world.economy, "freight_orders"), "freight owner not implemented"
    world.economy.facilities.clear()
    return world


def ship(world, amount=100, *, source=SOURCE, destination=DEST, routes=(ROAD,)):
    from src.sim.medieval.logistics import queue_freight
    intent = {"action": "freight", "source_id": source, "destination_id": destination,
              "resource_id": "food", "quantity": amount, "route_ids": list(routes),
              "actor_ref": world.economy.stocks[source].owner_ref.to_dict()}
    choice = record_event(world, "freight_decided", "Remessa autorizada.",
                          fact_kind=FactKind.DECISION, decision=intent)
    return queue_freight(world, source, destination, "food", amount, routes, decision_event_id=choice.id)


def total_food(world):
    return (sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) +
            sum(p.quantity for p in world.economy.parcels.values()
                if world.economy.freight_orders[p.order_id].resource_id == "food"))


async def test_two_orders_share_route_throughput_without_duplicating_goods():
    world = cargo_world()
    before = total_food(world)
    first = ship(world)
    second = ship(world)
    assert total_food(world) == before
    assert world.economy.stocks[SOURCE].goods["food"] == 3100
    engine = MedievalSimulator(world)
    await engine.step()
    assert world.clock.absolute_day == 1
    assert sum(p.quantity for p in world.economy.parcels.values() if p.stage == "traveling") == 162
    assert sum(p.quantity for p in world.economy.parcels.values() if p.stage == "waiting") == 38
    while world.economy.parcels:
        await engine.step()
        assert total_food(world) == before
    assert world.clock.absolute_day == 6
    assert world.economy.freight_orders[first.id].delivered_quantity == 100
    assert world.economy.freight_orders[second.id].delivered_quantity == 100
    assert world.economy.stocks[DEST].goods["food"] == 7400


async def test_opposite_directions_share_the_same_daily_capacity():
    world = cargo_world()
    ship(world, 100)
    ship(world, 100, source=DEST, destination=SOURCE)
    await MedievalSimulator(world).step()
    assert sum(p.quantity for p in world.economy.parcels.values() if p.stage == "traveling") == 162


async def test_blocked_route_keeps_goods_until_reopened():
    world = cargo_world()
    before = total_food(world)
    order = ship(world)
    world.map.routes[ROAD].update_runtime(enabled=False)
    engine = MedievalSimulator(world)
    await engine.step()
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    assert next(iter(world.economy.parcels.values())).stage == "waiting"
    assert total_food(world) == before
    world.map.routes[ROAD].update_runtime(enabled=True)
    while world.economy.parcels:
        await engine.step()
    assert total_food(world) == before
    assert world.economy.freight_orders[order.id].delivered_quantity == 100


async def test_full_destination_keeps_undelivered_quantity_at_the_destination():
    world = cargo_world()
    stock = world.economy.stocks[DEST]
    world.economy.stocks[DEST] = stock.model_copy(update={"capacity": world.economy.used_capacity(stock) + 40})
    order = ship(world)
    engine = MedievalSimulator(world)
    await engine.step()
    await engine.step()
    assert world.economy.freight_orders[order.id].delivered_quantity == 40
    parcel = next(iter(world.economy.parcels.values()))
    assert (parcel.stage, parcel.quantity) == ("unloading", 60)
    stock = world.economy.stocks[DEST]
    world.economy.stocks[DEST] = stock.model_copy(update={"capacity": stock.capacity + 60})
    await engine.step()
    assert not world.economy.parcels
    assert world.economy.freight_orders[order.id].delivered_quantity == 100


async def test_multiple_hops_use_canonical_routes_and_survive_midway_save(tmp_path):
    world = cargo_world()
    from src.classes.economy.models import Stock
    world.economy.stocks["depot:auren"] = Stock(id="depot:auren", owner_ref=world.economy.stocks[SOURCE].owner_ref,
                                               location_id="portovelho", capacity=1000)
    ship(world, 200, destination="depot:auren", routes=(ROAD, "river-pedraclara-portovelho"))
    engine = MedievalSimulator(world)
    await engine.step()
    path = tmp_path / "cargo.mws"
    save_world(world, path)
    resumed = load_world(path)
    while world.economy.parcels:
        await engine.step()
        await MedievalSimulator(resumed).step()
    assert world.economy.stocks["depot:auren"].goods["food"] == 200
    assert world.clock.absolute_day > 6
    assert world_snapshot(world) == world_snapshot(resumed)
    assert world.events == resumed.events


async def test_failed_cargo_step_does_not_publish_or_change_save(tmp_path, monkeypatch):
    world = cargo_world()
    ship(world, 200)
    path = tmp_path / "cargo.mws"
    save_world(world, path)
    before = world_snapshot(world)
    def fail(*args):
        raise OSError("disk failure")
    monkeypatch.setattr("src.sim.medieval.engine.save_world", fail)
    with pytest.raises(OSError, match="disk failure"):
        await MedievalSimulator(world, save_path=path).step()
    assert world_snapshot(world) == world_snapshot(load_world(path)) == before


def test_cargo_quantity_corruption_and_missing_agenda_are_rejected(tmp_path):
    world = cargo_world()
    ship(world)
    parcel = next(iter(world.economy.parcels.values()))
    world.economy.parcels[parcel.id] = parcel.model_copy(update={"quantity": 101})
    with pytest.raises(ValueError, match="quantity"):
        save_world(world, tmp_path / "corrupt.mws")
    world.economy.parcels[parcel.id] = parcel
    world.agenda.pop_due(parcel.due_day)
    with pytest.raises(ValueError, match="agenda"):
        save_world(world, tmp_path / "corrupt.mws")


async def test_delivery_on_month_boundary_can_fund_causal_relief():
    from src.systems.time import WorldClock
    world = cargo_world()
    world.clock = WorldClock(26)
    world.map.routes[ROAD].update_runtime(capacity=1000, quality=1)
    stock = world.economy.stocks[DEST]
    world.economy.stocks[DEST] = stock.model_copy(update={"goods": {"food": 0}})
    ship(world, 300)
    engine = MedievalSimulator(world)
    await engine.step()
    await engine.step()
    assert world.clock.absolute_day == 30
    # Offline routine-rules now selects a real distribution affordance at the
    # month boundary. The 300 units delivered beforehand can reduce the gap;
    # no stock or ration is granted merely by this test's expectation.
    assert world.economy.needs["pedraclara"].missing_food == 2100
    arrival = next(e for e in world.events if e.event_type == "cargo_delivered")
    relief = next(e for e in world.events if e.event_type == "relief_distributed"
                  and any(delta.owner_kind == "stock" and delta.owner_id == DEST for delta in e.deltas))
    assert any(e.event_type == "relief_distribution_decided" and e.id in
               {link.cause_event_id for link in relief.causal_links} for e in world.events)
    assert arrival.id in {link.cause_event_id for link in relief.causal_links}


@pytest.mark.parametrize("routes", [("missing",), (ROAD, ROAD), ("river-pedraclara-portovelho",)])
def test_invalid_path_does_not_remove_goods(routes):
    world = cargo_world()
    before = total_food(world)
    with pytest.raises(ValueError):
        ship(world, routes=routes)
    assert total_food(world) == before
    assert not world.economy.parcels


def test_stale_freight_decision_is_rejected_and_leaves_no_new_state():
    from src.systems.time import WorldClock
    world = cargo_world()
    intent = {"action": "freight", "source_id": SOURCE, "destination_id": DEST,
              "resource_id": "food", "quantity": 100, "route_ids": list((ROAD,)),
              "actor_ref": world.economy.stocks[SOURCE].owner_ref.to_dict()}
    choice = record_event(world, "freight_decided", "Remessa autorizada.",
                          fact_kind=FactKind.DECISION, decision=intent)
    world.clock = WorldClock(1)
    before = world_snapshot(world)
    from src.sim.medieval.logistics import queue_freight
    with pytest.raises(ValueError, match="stale"):
        queue_freight(world, SOURCE, DEST, "food", 100, (ROAD,), decision_event_id=choice.id)
    assert world_snapshot(world) == before


def test_internal_transfer_requires_same_owner_and_cannot_replay():
    world = cargo_world()
    from src.sim.medieval.logistics import queue_freight
    order = ship(world)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="executed"):
        queue_freight(world, SOURCE, DEST, "food", 100, (ROAD,), decision_event_id=order.decision_ids[0])
    assert world_snapshot(world) == before
    with pytest.raises(ValueError, match="owner"):
        ship(world, destination="stock:portovelho", routes=(ROAD, "river-pedraclara-portovelho"))
