"""A prepaid, blocked purchase can recover only through both institutions."""

import sqlite3

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.economy import _delta
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.purchase_recovery import (
    purchase_recovery_request_options,
    purchase_recovery_response_options,
    request_purchase_recovery,
    respond_purchase_recovery,
)
from src.sim.medieval import purchase_recovery as purchase_recovery_module
from tests.test_medieval_markets import consent, market_world, terms


SOURCE = "stock:campomanso"
DESTINATION = "stock:salgueiro"
BLOCKED_ROUTE = "road-salgueiro-campomanso"


def total_resource(world, resource_id):
    return (sum(stock.goods.get(resource_id, 0) for stock in world.economy.stocks.values())
            + sum(parcel.quantity for parcel in world.economy.parcels.values()
                  if world.economy.freight_orders[parcel.order_id].resource_id == resource_id))


def decide(world, event_type, option, *, origin=CausalOrigin.ACTOR_DECISION):
    return record_event(world, event_type, "A instituição escolheu uma opção atual.",
                        fact_kind=FactKind.DECISION, causal_origin=origin, decision=option.decision())


async def blocked_paid_purchase():
    """A cross-polity purchase with a known, untariffed alternate route."""
    world = market_world()
    refresh_reports(world)
    values = terms(world, source=SOURCE, destination=DESTINATION, quantity=20, routes=(BLOCKED_ROUTE,))
    assert values["export_rate_permille"] == 0
    order = purchase(world, *consent(world, values))
    # The seller has genuine current stock for a replacement.  The original
    # paid parcel remains separate cargo until the seller explicitly accepts.
    source = world.economy.stocks[SOURCE]
    world.economy.stocks[SOURCE] = source.model_copy(
        update={"goods": {**source.goods, "food": source.goods["food"] + 5000}})
    route = world.map.routes[BLOCKED_ROUTE]
    record_event(world, "passage_closed", "A passagem ficou indisponível.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("route", route.id, "enabled", route.enabled, False),))
    route.update_runtime(enabled=False)
    await MedievalSimulator(world).step()
    refresh_reports(world)
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    return world, world.economy.freight_orders[order.id]


async def request_case(world, order):
    buyer = world.economy.stocks[order.destination_id].owner_ref
    option = next(item for item in purchase_recovery_request_options(world, buyer)
                  if item.order_id == order.id)
    return request_purchase_recovery(world, option.id, decision_event_id=decide(
        world, "purchase_recovery_requested_decision", option).id)


async def test_request_enumeration_skips_foreign_order_reconstruction(monkeypatch):
    world, order = await blocked_paid_purchase()
    buyer = world.economy.stocks[order.destination_id].owner_ref
    expected = purchase_recovery_request_options(world, buyer)
    assert expected

    # This order has the same expensive evidence shape but belongs to another
    # polity. Enumeration for the buyer must discard it before reconstruction.
    foreign = order.model_copy(update={"id": "foreign-purchase-order",
                                       "owner_ref": EntityRef("polity", "auren")})
    world.economy.freight_orders[foreign.id] = foreign
    unpaid = order.model_copy(update={"id": "unpaid-purchase-order", "decision_ids": ()})
    world.economy.freight_orders[unpaid.id] = unpaid
    reconstructed = []
    original = purchase_recovery_module._purchase_parts

    def track_reconstruction(current_world, current_order):
        reconstructed.append(current_order.id)
        return original(current_world, current_order)

    monkeypatch.setattr(purchase_recovery_module, "_purchase_parts", track_reconstruction)
    actual = purchase_recovery_request_options(world, buyer)

    assert actual == expected
    assert reconstructed == [order.id]


async def test_request_enumeration_skips_orders_with_an_active_case_before_reconstruction(monkeypatch):
    world, order = await blocked_paid_purchase()
    buyer = world.economy.stocks[order.destination_id].owner_ref
    await request_case(world, order)
    reconstructed = []
    original = purchase_recovery_module._purchase_parts

    def track_reconstruction(current_world, current_order):
        reconstructed.append(current_order.id)
        return original(current_world, current_order)

    monkeypatch.setattr(purchase_recovery_module, "_purchase_parts", track_reconstruction)

    assert purchase_recovery_request_options(world, buyer) == ()
    assert reconstructed == []


async def test_seller_can_re_ship_a_paid_blocked_purchase_without_second_payment_or_lost_goods(tmp_path):
    world, order = await blocked_paid_purchase()
    food_before = total_resource(world, "food")
    balances_before = {account.id: account.balance for account in world.economy.accounts.values()}
    source_before = world.economy.stocks[SOURCE].goods["food"]
    immutable_original = (order.route_ids, order.quantity, order.decision_ids, order.delivered_quantity,
                          order.created_day, order.priority)

    case = await request_case(world, order)
    seller = world.economy.stocks[order.source_id].owner_ref
    response = next(item for item in purchase_recovery_response_options(world, seller)
                    if item.case_id == case.id and item.kind == "accept")
    successor = respond_purchase_recovery(
        world, response.id,
        decision_event_id=decide(world, "purchase_recovery_response_decision", response).id,
    )

    original = world.economy.freight_orders[order.id]
    assert successor.id != original.id and successor.route_ids == response.route_ids
    assert successor.quantity == original.quantity and successor.decision_ids[-1] != order.decision_ids[0]
    assert (original.route_ids, original.quantity, original.decision_ids, original.delivered_quantity,
            original.created_day, original.priority) == immutable_original
    assert original.resolved_quantity == original.quantity
    assert not [parcel for parcel in world.economy.parcels.values() if parcel.order_id == original.id]
    assert total_resource(world, "food") == food_before
    assert world.economy.stocks[SOURCE].goods["food"] == source_before
    assert {account.id: account.balance for account in world.economy.accounts.values()} == balances_before
    receipt = world.events[-1]
    assert receipt.event_type == "purchase_recovery_completed"
    assert {link.cause_event_id for link in receipt.causal_links} >= {
        case.request_decision_id, case.payment_event_id, successor.last_event_id,
    }
    world.economy.validate(world)

    path = tmp_path / "paid-purchase-recovery.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.economy.freight_recovery_cases[case.id].status == "completed"
    assert resumed.economy.freight_orders[successor.id] == successor


async def test_seller_rejection_keeps_the_paid_cargo_and_material_accounts_unchanged():
    world, order = await blocked_paid_purchase()
    case = await request_case(world, order)
    seller = world.economy.stocks[order.source_id].owner_ref
    response = next(item for item in purchase_recovery_response_options(world, seller)
                    if item.case_id == case.id and item.kind == "reject")
    material_before = (
        {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()},
        {account.id: account.balance for account in world.economy.accounts.values()},
        {parcel.id: parcel for parcel in world.economy.parcels.values()},
        world.economy.freight_orders[order.id],
    )

    assert respond_purchase_recovery(
        world, response.id,
        decision_event_id=decide(world, "purchase_recovery_response_decision", response).id,
    ) is None

    assert (
        {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()},
        {account.id: account.balance for account in world.economy.accounts.values()},
        {parcel.id: parcel for parcel in world.economy.parcels.values()},
        world.economy.freight_orders[order.id],
    ) == material_before
    assert world.economy.freight_recovery_cases[case.id].status == "rejected"
    world.economy.validate(world)


@pytest.mark.parametrize("invalid", ["invented", "interpretation"])
async def test_recovery_rejects_an_invalid_buyer_request_without_recording_a_case(invalid):
    world, order = await blocked_paid_purchase()
    buyer = world.economy.stocks[order.destination_id].owner_ref
    option = next(item for item in purchase_recovery_request_options(world, buyer)
                  if item.order_id == order.id)
    chosen = option.model_copy(update={"id": "purchase-recovery:invented"}) if invalid == "invented" else option
    origin = CausalOrigin.LLM_INTERPRETATION if invalid == "interpretation" else CausalOrigin.ACTOR_DECISION
    decision = decide(world, "purchase_recovery_request_decision", chosen, origin=origin)
    before = world_snapshot(world)

    with pytest.raises(ValueError):
        request_purchase_recovery(world, chosen.id, decision_event_id=decision.id)

    assert world_snapshot(world) == before
    assert not world.economy.freight_recovery_cases


def test_schema_twenty_save_is_rejected_before_the_new_economy_snapshot_is_read(tmp_path):
    """The required recovery registry is guarded by the top-level save schema."""
    world = market_world()
    path = tmp_path / "schema20.mws"
    save_world(world, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=20")
    before = path.read_bytes()

    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    with pytest.raises(ValueError, match="Unsupported"):
        save_world(world, path)

    assert path.read_bytes() == before
