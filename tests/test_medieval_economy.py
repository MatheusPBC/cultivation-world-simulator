import copy

import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.medieval_relief_helpers import relieve_all_settlements


def test_world_has_owned_located_stocks_and_a_complete_resource_catalog():
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "medieval world needs canonical material economy"
    economy = world.economy
    assert {"food", "wood", "stone", "iron", "tools", "weapons", "medicine", "reagents", "crystals"} <= set(economy.resources)
    assert economy.stocks["stock:pedraclara"].location_id == "pedraclara"
    assert economy.stocks["stock:pedraclara"].owner_ref.id == "auren"
    assert economy.stocks["stock:pedraclara"].goods["food"] == 7200
    economy.validate(world)


def workshop_world():
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    economy = world.economy
    facility = economy.facilities["works:oficinas-da-serra"]
    economy.facilities = {facility.id: facility}
    stock = economy.stocks[facility.stock_id]
    economy.stocks[stock.id] = stock.model_copy(update={"goods": {"iron": 5, "wood": 8}})
    return world, facility, stock.id


def test_manufacture_consumes_actual_inputs_and_records_both_sides():
    world, facility, stock_id = workshop_world()
    from src.sim.medieval.economy import produce_monthly
    produce_monthly(world)
    assert world.economy.stocks[stock_id].goods == {"iron": 1, "wood": 6, "tools": 2}
    event = next(e for e in world.events if e.event_type == "production_completed")
    changes = {d.aspect: (d.before, d.after) for d in event.deltas if d.owner_kind == "stock"}
    assert changes == {"iron": ("5", "1"), "wood": ("8", "6"), "tools": ("0", "2")}


def test_workers_are_shared_between_facilities_and_recruitment_removes_labor():
    world, facility, stock_id = workshop_world()
    from src.sim.medieval.economy import produce_monthly
    # Two workshops compete for exactly ten artisans; each batch requires ten.
    for group_id, group in list(world.society.population.items()):
        if group.settlement_id == "ferroalto":
            named = tuple(c.id for c in world.society.characters.values() if c.population_group_id == group_id)
            world.society.transfer_people(group_id, "ferroalto", "soldier", group.count, named)
    group = next(g for g in world.society.population.values() if g.settlement_id == "ferroalto" and g.occupation == "soldier")
    world.society.transfer_people(group.id, "ferroalto", "artisan", 10)
    other = facility.model_copy(update={"id": "works:second"})
    world.economy.facilities[other.id] = other
    produce_monthly(world)
    assert world.economy.stocks[stock_id].goods["tools"] == 1
    artisan = next(g for g in world.society.population.values() if g.settlement_id == "ferroalto" and g.occupation == "artisan")
    world.society.transfer_people(artisan.id, "ferroalto", "soldier", 10)
    produce_monthly(world)
    assert world.economy.stocks[stock_id].goods["tools"] == 1


def test_disabled_or_destroyed_site_produces_nothing():
    world, facility, stock_id = workshop_world()
    from src.sim.medieval.economy import produce_monthly
    before = world.economy.stocks[stock_id].goods.copy()
    world.map.infrastructure_sites[facility.site_id].update_runtime(integrity=0)
    produce_monthly(world)
    assert world.economy.stocks[stock_id].goods == before


def test_storage_capacity_limits_extraction_without_discarding_goods():
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    from src.sim.medieval.economy import produce_monthly
    farm = world.economy.facilities["works:campos-do-lume"]
    world.economy.facilities = {farm.id: farm}
    stock = world.economy.stocks[farm.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 95}, "capacity": 100})
    produce_monthly(world)
    assert world.economy.stocks[stock.id].goods == {"food": 95}


async def test_month_consumes_each_person_once_and_daily_interrupt_does_not_consume():
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    from src.sim.medieval.actions import start_travel
    person = next(c for c in world.society.characters.values() if c.location_id == "campomanso")
    start_travel(world, person.id, "road-campomanso-pedraclara", "pedraclara")
    world.economy.facilities.clear()
    before = sum(s.goods.get("food", 0) for s in world.economy.stocks.values())
    engine = MedievalSimulator(world)
    await engine.step()
    assert sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) == before
    await engine.step()
    # No household has any money and no relief act has run yet, so nothing
    # left any granary: the shortfall is real, not silently forgiven.
    assert sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) == before
    assert sum(need.missing_food for need in world.economy.needs.values()) == 10900
    # The administration now chooses, settlement by settlement, to give its
    # own stored food away -- the only way anyone actually eats.
    relieve_all_settlements(world)
    assert sum(s.goods.get("food", 0) for s in world.economy.stocks.values()) == before - 10900
    assert sum(need.missing_food for need in world.economy.needs.values()) == 0


def test_shortage_harms_health_and_recovery_requires_new_food():
    from src.sim.medieval.economy import consume_monthly
    from src.systems.time import WorldClock
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    world.economy.facilities.clear()
    stock = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 1200}})
    world.clock = WorldClock(30)
    consume_monthly(world)
    need = world.economy.needs["pedraclara"]
    # No household has money and no relief act has run: the whole ration is
    # simply missing this cycle, not silently forgiven by an automatic rate.
    assert (need.missing_food, need.health, need.unrest) == (2400, 900, 100)
    assert world.economy.stocks[stock.id].goods["food"] == 1200
    world.economy.stocks[stock.id] = world.economy.stocks[stock.id].model_copy(
        update={"goods": {"food": world.economy.stocks[stock.id].goods.get("food", 0) + 2400}})
    # Recovery now requires an actual paid ration -- an unpaid one is never
    # forgiven for free -- so every household gets enough money to buy its
    # own share this cycle.
    price = world.economy.markets["pedraclara"].prices["food"]
    for group in world.society.population.values():
        if group.settlement_id != "pedraclara":
            continue
        account = world.economy.accounts[f"household:{group.id}"]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": group.count * price})
    world.clock = WorldClock(60)
    consume_monthly(world)
    need = world.economy.needs["pedraclara"]
    assert (need.missing_food, need.health, need.unrest) == (0, 920, 80)
    assert world.society.total_population == 10900


async def test_economy_resumes_equivalently_and_corruption_cannot_overwrite_save(tmp_path):
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    await MedievalSimulator(world).step()
    path = tmp_path / "economy.mws"
    save_world(world, path)
    resumed = load_world(path)
    await MedievalSimulator(world).step()
    await MedievalSimulator(resumed).step()
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.events == world.events
    before = path.read_bytes()
    resumed.economy.stocks["stock:pedraclara"].goods["food"] = -1
    with pytest.raises(ValueError):
        save_world(resumed, path)
    assert path.read_bytes() == before


def test_money_transfer_is_conservative_and_invalid_payment_is_atomic():
    world = create_medieval_world(73)
    assert hasattr(world, "economy"), "economy missing"
    from src.classes.event import FactKind
    from src.sim.medieval.events import record_event
    from src.sim.medieval.economy import transfer_money
    source, target = "treasury:auren", "treasury:valedouro"
    decision = record_event(world, "payment_decided", "Pagamento autorizado.", fact_kind=FactKind.DECISION,
                            decision={"action": "pay", "source_id": source, "target_id": target, "amount": 17,
                                      "actor_ref": world.economy.accounts[source].owner_ref.to_dict()})
    before = {key: a.balance for key, a in world.economy.accounts.items()}
    transfer_money(world, source, target, 17, decision_event_id=decision.id)
    after = {key: a.balance for key, a in world.economy.accounts.items()}
    assert sum(after.values()) == sum(before.values())
    assert after[source] == before[source] - 17
    assert after[target] == before[target] + 17
    snapshot = copy.deepcopy(world_snapshot(world))
    with pytest.raises(ValueError):
        transfer_money(world, source, target, 10**12, decision_event_id=decision.id)
    assert world_snapshot(world) == snapshot


async def test_destroyed_food_site_is_traceable_as_a_cause_of_subsistence_failure():
    from src.classes.event import FactKind
    from src.classes.state_delta import StateDelta
    from src.sim.medieval.events import record_event
    world = create_medieval_world(73)
    site = world.map.infrastructure_sites["campos-do-lume"]
    damage = record_event(world, "site_damaged", "Plantação destruída.", fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(StateDelta(owner_kind="site", owner_id=site.id, aspect="integrity", before="1.0", after="0.0"),))
    site.update_runtime(integrity=0, last_event_id=damage.id)
    stock = world.economy.stocks["stock:campomanso"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 0}})
    await MedievalSimulator(world).step()
    blocked = [e for e in world.events if e.event_type == "production_limited" and
               damage.id in {link.cause_event_id for link in e.causal_links}]
    assert len(blocked) == 1, "destroyed facility must explain lost production"
    shortage = next(e for e in world.events if any(d.owner_id == "campomanso" and d.aspect == "missing_food" for d in e.deltas))
    assert blocked[0].id in {link.cause_event_id for link in shortage.causal_links}


def test_payment_decision_cannot_be_replayed_after_save_load(tmp_path):
    from src.classes.event import FactKind
    from src.sim.medieval.events import record_event
    from src.sim.medieval.economy import transfer_money
    world = create_medieval_world(73)
    args = ("treasury:auren", "treasury:valedouro", 17)
    decision = record_event(world, "payment_decided", "Pagamento.", fact_kind=FactKind.DECISION,
                            decision={"action": "pay", "source_id": args[0], "target_id": args[1], "amount": 17,
                                      "actor_ref": world.economy.accounts[args[0]].owner_ref.to_dict()})
    transfer_money(world, *args, decision_event_id=decision.id)
    path = tmp_path / "paid.mws"
    save_world(world, path)
    resumed = load_world(path)
    before = world_snapshot(resumed)
    with pytest.raises(ValueError, match="unexecuted"):
        transfer_money(resumed, *args, decision_event_id=decision.id)
    assert world_snapshot(resumed) == before


def test_partial_site_integrity_limits_batches_before_consuming_inputs():
    from src.sim.medieval.economy import produce_monthly
    world, facility, stock_id = workshop_world()
    world.economy.facilities[facility.id] = facility.model_copy(update={"max_batches": 2})
    world.map.infrastructure_sites[facility.site_id].update_runtime(integrity=0.5)
    produce_monthly(world)
    assert world.economy.stocks[stock_id].goods == {"iron": 3, "wood": 7, "tools": 1}


@pytest.mark.parametrize("mutation", ["owner", "location", "resource", "capacity", "provenance"])
def test_invalid_stock_reference_cannot_be_saved(mutation, tmp_path):
    from src.classes.mechanical_language import EntityRef
    world = create_medieval_world(73)
    stock = world.economy.stocks["stock:pedraclara"]
    changes = {
        "owner": {"owner_ref": EntityRef("polity", "missing")},
        "location": {"location_id": "missing"},
        "resource": {"goods": {"imaginary": 100}},
        "capacity": {"capacity": 1},
        "provenance": {"last_event_ids": {"food": "absent"}},
    }
    world.economy.stocks[stock.id] = stock.model_copy(update=changes[mutation])
    path = tmp_path / "invalid.mws"
    with pytest.raises(ValueError):
        save_world(world, path)
    assert not path.exists()
