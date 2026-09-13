"""Export tariff knowledge is public only as a dated source-market quote."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports, refresh_trade_reports
from src.sim.medieval.persistence import load_world, restore_snapshot, save_world, world_snapshot


def quoted_world():
    world = create_medieval_world(73)
    stock = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": 10000}})
    policy = world.authority.tax_policies["auren"]
    changed = record_event(world, "export_tariff_changed", "Tarifa de exportação alterada.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("tax_policy", policy.id, "export_rate_permille",
                                          policy.export_rate_permille, 175),))
    world.authority.tax_policies[policy.id] = policy.model_copy(update={"income_rate": 333,
                                                                          "export_rate_permille": 175,
                                                                          "last_event_id": changed.id,
                                                                          "export_policy_event_id": changed.id})
    refresh_reports(world)
    inventory = world.knowledge.reports[f"inventory:polity:auren:{stock.id}:food"]
    offer = next(report for report in world.knowledge.reports.values()
                 if report.kind == "offer" and report.stock_id == stock.id and report.resource_id == "food")
    return world, changed, inventory, offer


def test_inventory_and_public_offer_carry_the_export_policy_of_the_origin_not_income_tax():
    world, changed, inventory, offer = quoted_world()
    for report in (inventory, offer):
        assert report.export_rate_permille == 175
        assert report.export_policy_event_id == changed.id
        assert report.export_collector_ref == EntityRef("polity", "auren")
    published = next(event for event in world.events if event.id == offer.event_id)
    assert changed.id in {link.cause_event_id for link in published.causal_links}
    assert offer.publisher_ref == EntityRef("polity", "auren")


def test_saved_tariff_quote_remains_historical_and_forged_policy_metadata_is_rejected(tmp_path):
    world, _, _, offer = quoted_world()
    path = tmp_path / "tariff-quote.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.knowledge.reports[offer.id] == offer

    snapshot = world_snapshot(world)
    snapshot["knowledge"]["reports"][offer.id]["export_rate_permille"] = 999
    with pytest.raises(ValueError, match="export quote|policy receipt"):
        restore_snapshot(snapshot, world.events)


def test_same_day_tariff_change_republishes_only_the_trade_quote():
    world, _, inventory, _ = quoted_world()
    policy = world.authority.tax_policies["auren"]
    changed = record_event(world, "export_tariff_changed", "Tarifa revista no mesmo dia.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("tax_policy", policy.id, "export_rate_permille",
                                          policy.export_rate_permille, 250),),
                           cause_ids=(policy.last_event_id,))
    world.authority.tax_policies[policy.id] = policy.model_copy(update={"export_rate_permille": 250,
                                                                          "last_event_id": changed.id,
                                                                          "export_policy_event_id": changed.id})
    refresh_trade_reports(world, replace_today=True)
    updated = world.knowledge.reports[inventory.id]
    assert updated.export_rate_permille == 250 and updated.export_policy_event_id == changed.id
    assert updated.event_id != inventory.event_id


def test_income_tax_change_does_not_replace_a_dated_export_quote_or_its_policy_receipt(tmp_path):
    from src.sim.medieval.labor import set_income_tax

    world, export_changed, _, offer = quoted_world()
    decision = record_event(world, "income_tax_decided", "Imposto de renda revisto.", fact_kind=FactKind.DECISION,
                            decision={"action": "set_income_tax", "actor_ref": EntityRef("polity", "auren").to_dict(),
                                      "polity_id": "auren", "income_rate": 444})
    set_income_tax(world, "auren", 444, decision_event_id=decision.id)
    policy = world.authority.tax_policies["auren"]
    assert policy.last_event_id != export_changed.id
    assert policy.export_policy_event_id == export_changed.id
    assert world.knowledge.reports[offer.id].export_policy_event_id == export_changed.id
    path = tmp_path / "income-after-export-quote.mws"
    save_world(world, path)
    assert load_world(path).knowledge.reports[offer.id] == offer
