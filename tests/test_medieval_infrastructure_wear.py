"""Operating wear remains a material, bounded Map transition."""

import pytest

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import monthly_workforce, produce_monthly
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.infrastructure import progress_repairs, review_maintenance
from src.sim.medieval.infrastructure_wear import (
    MAX_MONTHLY_INTEGRITY_LOSS,
    MIN_PRODUCTIVE_BATCHES_PER_MONTH,
    MIN_ROUTE_BULK_PER_MONTH,
    apply_monthly_infrastructure_wear,
)
from src.sim.medieval.logistics import queue_freight, resolve_parcels
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.systems.time import WorldClock


FARM = "works:campos-do-lume"
FARM_SITE = "campos-do-lume"
PORT = "docas-de-portovelho"
RIVER = "river-pedraclara-portovelho"


def _production_world(batches):
    world = create_medieval_world(73)
    facility = world.economy.facilities[FARM]
    world.economy.facilities = {
        FARM: facility.model_copy(update={"max_batches": batches}),
    }
    world.clock = WorldClock(30)
    produce_monthly(world, monthly_workforce(world))
    return world


def _depart(world, quantity):
    """Create one real, immutable cargo departure on the river route."""
    source = world.economy.stocks["stock:pedraclara"]
    destination_id = "depot:auren-portovelho"
    if destination_id not in world.economy.stocks:
        world.economy.stocks[destination_id] = Stock(
            id=destination_id, owner_ref=source.owner_ref, location_id="portovelho", capacity=10_000,
        )
    decision = record_event(
        world, "freight_decided", "Remessa própria autorizada.", fact_kind=FactKind.DECISION,
        decision={"action": "freight", "source_id": source.id, "destination_id": destination_id,
                  "resource_id": "food", "quantity": quantity, "route_ids": [RIVER],
                  "actor_ref": source.owner_ref.to_dict()},
    )
    order = queue_freight(world, source.id, destination_id, "food", quantity, (RIVER,),
                          decision_event_id=decision.id)
    parcel = next(parcel for parcel in world.economy.parcels.values() if parcel.order_id == order.id)
    world.clock = WorldClock(parcel.due_day)
    resolve_parcels(world, world.agenda.pop_due(world.clock.absolute_day))
    return order


def _finish_order(world, order):
    """Keep the fixture's historic receipt while leaving no stale agenda work."""
    while any(parcel.order_id == order.id for parcel in world.economy.parcels.values()):
        due_day = min(parcel.due_day for parcel in world.economy.parcels.values()
                      if parcel.order_id == order.id)
        world.clock = WorldClock(due_day)
        resolve_parcels(world, world.agenda.pop_due(due_day))


def test_idle_and_under_threshold_sites_do_not_wear():
    idle = create_medieval_world(73)
    idle.clock = WorldClock(30)
    assert apply_monthly_infrastructure_wear(idle) == ()
    assert all(site.integrity == 1.0 for site in idle.map.infrastructure_sites.values())

    quiet = _production_world(MIN_PRODUCTIVE_BATCHES_PER_MONTH - 1)
    assert quiet.economy.facilities[FARM].last_batches == MIN_PRODUCTIVE_BATCHES_PER_MONTH - 1
    assert apply_monthly_infrastructure_wear(quiet) == ()
    assert quiet.map.infrastructure_sites[FARM_SITE].integrity == 1.0
    assert not any(event.event_type == "site_worn" for event in quiet.events)


def test_productive_site_wear_links_the_exact_production_receipt_once():
    world = _production_world(MIN_PRODUCTIVE_BATCHES_PER_MONTH)
    receipt_id = world.economy.facilities[FARM].last_event_id

    assert apply_monthly_infrastructure_wear(world) == (FARM_SITE,)
    event = world.events[-1]
    assert event.event_type == "site_worn" and event.fact_kind == FactKind.STATE_TRANSITION
    assert world.map.infrastructure_sites[FARM_SITE].integrity == pytest.approx(1 - MAX_MONTHLY_INTEGRITY_LOSS)
    assert receipt_id in {link.cause_event_id for link in event.causal_links}
    assert all(site.integrity == 1.0 for site_id, site in world.map.infrastructure_sites.items()
               if site_id != FARM_SITE)

    count = len(world.events)
    assert apply_monthly_infrastructure_wear(world) == ()
    assert len(world.events) == count, "facts, not ephemeral process state, guard the month"


def test_route_departure_wear_reduces_capacity_and_later_cargo_waits():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    first = _depart(world, MIN_ROUTE_BULK_PER_MONTH)
    _finish_order(world, first)
    departure = next(event for event in world.events if event.event_type == "cargo_departed")
    world.clock = WorldClock(30)

    before = world.map.get_route_operational_capacity(RIVER)
    assert apply_monthly_infrastructure_wear(world) == (PORT,)
    worn = world.events[-1]
    assert departure.id in {link.cause_event_id for link in worn.causal_links}
    assert world.map.get_route_operational_capacity(RIVER) < before

    # The 0.01 loss lowers this 324-bulk river capacity to floor(320), so the
    # last unit must remain a real waiting parcel rather than disappear.
    second = _depart(world, 321)
    departing = [parcel for parcel in world.economy.parcels.values() if parcel.order_id == second.id]
    assert sum(parcel.quantity for parcel in departing if parcel.stage == "traveling") == 320
    assert sum(parcel.quantity for parcel in departing if parcel.stage == "waiting") == 1


def test_wear_is_observable_and_repair_remains_a_material_choice():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    first = _depart(world, MIN_ROUTE_BULK_PER_MONTH)
    _finish_order(world, first)
    world.clock = WorldClock(30)
    assert apply_monthly_infrastructure_wear(world) == (PORT,)
    refresh_site_reports(world, site_ids=(PORT,))

    review_maintenance(world)
    project = next(project for project in world.economy.repairs.values() if project.site_id == PORT)
    assert project.stage == "waiting"
    assert world.map.infrastructure_sites[PORT].integrity == pytest.approx(1 - MAX_MONTHLY_INTEGRITY_LOSS)

    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    stock = world.economy.stocks[project.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, **{resource_id: stock.goods.get(resource_id, 0) + amount
                                      for resource_id, amount in blueprint.inputs.items()}},
    })
    world.clock = WorldClock(60)
    refresh_site_reports(world, site_ids=(PORT,))
    progress_repairs(world, monthly_workforce(world))
    assert world.map.infrastructure_sites[PORT].integrity > 1 - MAX_MONTHLY_INTEGRITY_LOSS
    assert any(event.event_type == "repair_batch_decided" for event in world.events)


@pytest.mark.asyncio
async def test_wear_save_load_and_failed_month_commit_rollback(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    facility = world.economy.facilities[FARM]
    world.economy.facilities = {FARM: facility.model_copy(update={"max_batches": MIN_PRODUCTIVE_BATCHES_PER_MONTH})}
    world.clock = WorldClock(29)
    path = tmp_path / "wear.mws"
    save_world(world, path)
    before = world_snapshot(world)
    monkeypatch.setattr("src.sim.medieval.engine.save_world", lambda *_: (_ for _ in ()).throw(OSError("disk failure")))

    with pytest.raises(OSError, match="disk failure"):
        await MedievalSimulator(world, save_path=path).step()
    assert world_snapshot(world) == world_snapshot(load_world(path)) == before

    monkeypatch.undo()
    await MedievalSimulator(world, save_path=path).step()
    assert any(event.event_type == "site_worn" and any(delta.owner_id == FARM_SITE for delta in event.deltas)
               for event in world.events)
    assert world_snapshot(world) == world_snapshot(load_world(path))
