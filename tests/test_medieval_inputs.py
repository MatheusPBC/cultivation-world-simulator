"""Productive actors buy real inputs, not food-shaped promises or private truth."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.procurement import review_supply
from src.sim.medieval.persistence import save_world, load_world, world_snapshot
from src.systems.time import WorldClock


def test_initial_workshops_have_input_objectives_separate_from_public_food():
    world = create_medieval_world(73)
    goals = list(world.strategy.objectives.values())
    assert len(goals) == 11
    inputs = [o for o in goals if o.kind == "maintain_production_inputs"]
    assert {(o.stock_id, o.resource_id) for o in inputs} == {
        ("stock:ferroalto", "wood"), ("stock:oficios-da-serra", "wood"), ("stock:oficios-da-serra", "iron")}
    assert all(o.actor_ref == world.economy.stocks[o.stock_id].owner_ref for o in goals)


def prepared_iron_demand():
    world = create_medieval_world(73)
    goal = next((o for o in world.strategy.objectives.values()
                 if getattr(o, "stock_id", None) == "stock:oficios-da-serra"
                 and getattr(o, "resource_id", None) == "iron"), None)
    assert goal is not None, "workshop has no input goal"
    world.strategy.objectives = {goal.id: goal}
    stock = world.economy.stocks[goal.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"iron": 0, "wood": 60}})
    supplier = world.economy.stocks["stock:ferroalto"]
    world.economy.stocks[supplier.id] = supplier.model_copy(update={"goods": {**supplier.goods, "iron": 500}})
    world.clock = WorldClock(30)
    return world, goal


async def test_local_iron_purchase_requires_delivery_before_inputs_can_be_used(tmp_path):
    world, goal = prepared_iron_demand()
    initial = sum(a.balance for a in world.economy.accounts.values())
    refresh_reports(world)
    review_supply(world)
    orders = list(world.economy.freight_orders.values())
    assert len(orders) == 1
    order = orders[0]
    assert (order.resource_id, order.quantity, order.route_ids) == ("iron", 120, ())
    assert world.economy.stocks[goal.stock_id].goods["iron"] == 0
    assert world.economy.stocks["stock:ferroalto"].goods["iron"] == 380
    assert world.economy.accounts["treasury:oficios-da-serra"].balance == 560
    assert world.economy.accounts["treasury:escarlia"].balance == 21440
    path = tmp_path / "input.mws"
    save_world(world, path)
    resumed = load_world(path)
    for value in (world, resumed):
        await MedievalSimulator(value).step()
        assert value.clock.absolute_day == 31
        assert value.economy.stocks[goal.stock_id].goods["iron"] == 120
        assert value.strategy.plans[f"plan:{goal.id}"].stage == "satisfied"
        assert sum(a.balance for a in value.economy.accounts.values()) == initial
    assert world_snapshot(world) == world_snapshot(resumed)
    assert world.events == resumed.events
    while world.clock.absolute_day < 60:
        await MedievalSimulator(world).step()
    assert world.economy.facilities["works:oficinas-da-serra"].last_batches == 30
    assert world.economy.stocks[goal.stock_id].goods["tools"] == 30
    assert world.economy.stocks[goal.stock_id].goods["iron"] == 60
    assert sum(a.balance for a in world.economy.accounts.values()) == initial


def test_input_reports_do_not_disclose_other_actors_full_inventory():
    world, goal = prepared_iron_demand()
    refresh_reports(world)
    reports = world.knowledge.for_actor(goal.actor_ref)
    assert any(r.kind == "inventory" and r.stock_id == goal.stock_id and r.resource_id == "iron" for r in reports)
    assert any(r.kind == "offer" and r.stock_id == "stock:ferroalto" and r.resource_id == "iron" for r in reports)
    assert not any(r.kind == "inventory" and r.publisher_ref != goal.actor_ref for r in reports)
    assert not any(r.stock_id == "stock:torre-do-ambar" for r in reports)


def test_seller_protects_its_own_productive_wood_reserve():
    world = create_medieval_world(73)
    from src.sim.medieval.intelligence import reserve_quantity
    # Mine needs60wood per month; a two-month reserve is120, not1800people*2.
    assert reserve_quantity(world, "stock:ferroalto", "wood") == 120
    refresh_reports(world)
    offers = [r for r in world.knowledge.reports.values()
              if r.stock_id == "stock:ferroalto" and r.resource_id == "wood" and r.kind == "offer"]
    assert offers and all(r.quantity == 0 for r in offers)


def test_query_exposes_derived_input_target_not_city_population():
    from src.server.medieval.queries import governance_view
    world, goal = prepared_iron_demand()
    data = governance_view(world).model_dump(mode="json")
    assert data["objectives"][0]["target_quantity"] == 120
    facility = world.economy.facilities["works:oficinas-da-serra"]
    world.economy.facilities[facility.id] = facility.model_copy(update={"max_batches": 40})
    assert governance_view(world).model_dump(mode="json")["objectives"][0]["target_quantity"] == 160
    capacities = governance_view(world).model_dump(mode="json")["strategic_capacity"]
    assert capacities and {
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity",
    } <= set(capacities[0]["dimensions"])


def test_previous_save_without_resource_targets_is_rejected_and_preserved(tmp_path):
    import sqlite3
    world = create_medieval_world(73)
    path = tmp_path / "old.mws"
    save_world(world, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=6")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    with pytest.raises(ValueError, match="Unsupported"):
        save_world(world, path)
    assert path.read_bytes() == before


def test_missing_input_report_cannot_be_replaced_by_food_observation():
    world, goal = prepared_iron_demand()
    refresh_reports(world)
    world.knowledge.reports = {key: r for key, r in world.knowledge.reports.items()
                              if r.kind != "inventory"}
    review_supply(world)
    assert not world.economy.freight_orders
    assert world.strategy.plans[f"plan:{goal.id}"].stage == "blocked"


def test_supplier_refuses_wood_if_changed_stock_would_violate_production_reserve():
    from src.sim.medieval.procurement import consider_sale
    from src.sim.medieval.events import record_event
    from src.classes.event import FactKind
    world = create_medieval_world(73)
    stock = world.economy.stocks["stock:ferroalto"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "wood": 150}})
    refresh_reports(world)
    offer = next(r for r in world.knowledge.reports.values()
                 if r.kind == "offer" and r.stock_id == stock.id and r.resource_id == "wood")
    assert offer.quantity == 30
    terms = {"source_id": stock.id, "destination_id": "stock:oficios-da-serra", "resource_id": "wood",
             "quantity": 20, "unit_price": 6, "quote_day": 0, "route_ids": [],
             "buyer_account_id": "treasury:oficios-da-serra", "seller_account_id": "treasury:escarlia"}
    decision = record_event(world, "buy_decided", "Comprar madeira.", fact_kind=FactKind.DECISION,
                            decision={"action": "buy", "actor_ref": EntityRef("organization", "oficios-da-serra").to_dict(), **terms})
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "wood": 120}})
    before = world.economy.to_dict()
    assert consider_sale(world, terms, decision.id) is None
    assert world.economy.to_dict() == before


def test_route_search_does_not_offer_an_impossible_resource_path():
    from src.sim.medieval.routing import supply_path
    world = create_medieval_world(73)
    for route in world.map.routes.values():
        route.update_runtime(enabled=False)
    route = world.map.routes["road-campomanso-pedraclara"]
    route.update_runtime(enabled=True)
    # The route's actual resource restriction, not a parallel graph.
    world.map.routes[route.id] = type(route).from_dict({**route.to_dict(), "allowed_resource_ids": ["food"]})
    assert supply_path(world, "campomanso", "pedraclara", "food") == (route.id,)
    assert supply_path(world, "campomanso", "pedraclara", "iron") is None


async def test_natural_auditor_detects_unrecorded_non_food_loss(tmp_path, monkeypatch):
    from tools.medieval_autonomy_smoke import run
    original_step = MedievalSimulator.step
    async def lose_unrecorded_wood(engine):
        result = await original_step(engine)
        stock = engine.world.economy.stocks["stock:salgueiro"]
        engine.world.economy.stocks[stock.id] = stock.model_copy(update={
            "goods": {**stock.goods, "wood": stock.goods["wood"] - 1}})
        return result
    monkeypatch.setattr(MedievalSimulator, "step", lose_unrecorded_wood)
    with pytest.raises(AssertionError, match="resource"):
        await run(73, 30, tmp_path / "audit.mws")
