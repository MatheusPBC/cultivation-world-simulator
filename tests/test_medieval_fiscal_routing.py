"""Focused proof for dated fiscal route choices before freight opening."""

import asyncio

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.customs import customs_open_options, open_customs_checkpoint
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.procurement import consider_sale
from src.sim.medieval.routing import fiscal_route_options
from src.sim.medieval.tariffs import export_fee, export_quote


SITE = "passagem-negra"
CHECKPOINT_ROUTE = "road-pontenegro-ferroalto"
SOURCE = "stock:campomanso"
DESTINATION = "stock:ferroalto"
ACTOR = EntityRef("polity", "escarlia")


def checkpoint_world():
    world = create_medieval_world(73)
    operator = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, operator)[0]
    decision = record_event(world, "customs_open_decided", "Abrir posto civil.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    open_customs_checkpoint(world, option.id, decision_event_id=decision.id)
    asyncio.run(MedievalSimulator(world).step())
    return world


def purchase_terms(world, option):
    source = world.economy.stocks[SOURCE]
    market = world.economy.markets[source.location_id]
    quote = export_quote(world, SOURCE, DESTINATION)
    quantity, price = option.quantity, market.prices["food"]
    fee = export_fee(quantity, price, quote["export_rate_permille"])
    return {
        "source_id": SOURCE, "destination_id": DESTINATION, "resource_id": "food", "quantity": quantity,
        "unit_price": price, "quote_day": market.updated_day, "route_ids": list(option.route_ids),
        "route_option_id": option.id, "buyer_account_id": "treasury:escarlia",
        "seller_account_id": "treasury:auren", **quote, "total_price": quantity * price + fee,
    }


def decide_purchase(world, option):
    terms = purchase_terms(world, option)
    buyer = record_event(world, "buy_decided", "Selecionar rota fiscal conhecida.",
                         fact_kind=FactKind.DECISION,
                         decision={**terms, "action": "buy", "actor_ref": ACTOR.to_dict()},
                         cause_ids=(*option.route_report_ids, *option.fiscal_route_report_ids))
    seller = consider_sale(world, terms, buyer.id)
    assert seller is not None
    return buyer.id, seller


def test_active_operator_origins_the_dated_fiscal_receipt_without_private_ledger():
    world = checkpoint_world()
    checkpoint = world.economy.customs_checkpoints[f"customs:{SITE}"]
    report = world.knowledge.fiscal_route_report(checkpoint.operator_ref, CHECKPOINT_ROUTE)
    assert report is not None
    assert (report.publisher_ref, report.checkpoint_id, report.fee_per_bulk) == (
        checkpoint.operator_ref, checkpoint.id, checkpoint.fee_per_bulk)
    assert report.channel == "administrative_fiscal_route_report"
    receipt = next(event for event in world.events if event.id == report.event_id)
    assert receipt.event_type == "fiscal_route_observed"
    assert checkpoint.last_event_id in {link.cause_event_id for link in receipt.causal_links}
    assert {"account_id", "staff_group_id", "inspection_slots_used"}.isdisjoint(report.model_dump())
    received = world.knowledge.fiscal_route_report(ACTOR, CHECKPOINT_ROUTE)
    assert received is not None and received.channel == "fiscal_route_bulletin"


def test_known_checkpoint_and_legal_no_post_paths_are_distinct_route_options():
    world = checkpoint_world()
    options = fiscal_route_options(world, ACTOR, SOURCE, DESTINATION, "food", 10)
    taxed = next(option for option in options if CHECKPOINT_ROUTE in option.route_ids)
    untaxed = next(option for option in options if CHECKPOINT_ROUTE not in option.route_ids)
    assert taxed.estimated_customs_fee > 0 and taxed.fiscal_route_report_ids
    assert untaxed.estimated_customs_fee == 0 and not untaxed.fiscal_route_report_ids
    # Every candidate still names its exact dated physical observations.
    assert taxed.route_report_ids and untaxed.route_report_ids


def test_owner_rejects_invented_or_stale_fiscal_selection_without_opening_freight():
    world = checkpoint_world()
    option = next(item for item in fiscal_route_options(world, ACTOR, SOURCE, DESTINATION, "food", 10)
                  if CHECKPOINT_ROUTE in item.route_ids)
    buyer, seller = decide_purchase(world, option)
    # A closure after the choice is not leaked to the actor, but blocks the
    # material owner from opening the selected freight.
    world.map.routes[CHECKPOINT_ROUTE].update_runtime(enabled=False)
    before = (dict(world.economy.freight_orders), dict(world.economy.parcels),
              {key: account.balance for key, account in world.economy.accounts.items()})
    with pytest.raises(ValueError, match="fiscal route option"):
        purchase(world, buyer, seller)
    assert (dict(world.economy.freight_orders), dict(world.economy.parcels),
            {key: account.balance for key, account in world.economy.accounts.items()}) == before

    world = checkpoint_world()
    option = next(item for item in fiscal_route_options(world, ACTOR, SOURCE, DESTINATION, "food", 10)
                  if CHECKPOINT_ROUTE in item.route_ids)
    forged = option.model_copy(update={"id": option.id + ":invented"})
    buyer, seller = decide_purchase(world, forged)
    before = (dict(world.economy.freight_orders), dict(world.economy.parcels),
              {key: account.balance for key, account in world.economy.accounts.items()})
    with pytest.raises(ValueError, match="fiscal route option"):
        purchase(world, buyer, seller)
    assert (dict(world.economy.freight_orders), dict(world.economy.parcels),
            {key: account.balance for key, account in world.economy.accounts.items()}) == before


def test_opened_freight_keeps_the_selected_route_when_the_map_changes_afterward():
    world = checkpoint_world()
    option = next(item for item in fiscal_route_options(world, ACTOR, SOURCE, DESTINATION, "food", 10)
                  if CHECKPOINT_ROUTE in item.route_ids)
    buyer, seller = decide_purchase(world, option)
    order = purchase(world, buyer, seller)
    world.map.routes[CHECKPOINT_ROUTE].update_runtime(enabled=False)
    assert order.route_ids == option.route_ids
    assert world.economy.freight_orders[order.id].route_ids == option.route_ids


def test_fiscal_receipts_survive_save_and_failed_month_commit_rolls_them_back(tmp_path, monkeypatch):
    world = checkpoint_world()
    path = tmp_path / "fiscal-routes.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert fiscal_route_options(restored, ACTOR, SOURCE, DESTINATION, "food", 10) == \
           fiscal_route_options(world, ACTOR, SOURCE, DESTINATION, "food", 10)

    world = create_medieval_world(73)
    operator = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, operator)[0]
    decision = record_event(world, "customs_open_decided", "Abrir posto civil.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    open_customs_checkpoint(world, option.id, decision_event_id=decision.id)
    before, history = world_snapshot(world), list(world.events)

    from src.sim.medieval import engine
    monkeypatch.setattr(engine, "save_world", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError, match="disk"):
        asyncio.run(MedievalSimulator(world, save_path=tmp_path / "failed.mws").step())
    assert world_snapshot(world) == before and world.events == history
    assert not world.knowledge.fiscal_route_reports
