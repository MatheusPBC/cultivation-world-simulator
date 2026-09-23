import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.economy.models import Stock
from src.classes.governance.models import StrategicPlan
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.intelligence import refresh_reports, refresh_trade_reports
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.tariffs import export_fee, export_quote, review_export_tariffs, set_export_tariff, tariff_options


SOURCE, DESTINATION = "stock:campomanso", "stock:portovelho"


def tariff_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    refresh_reports(world)
    option = next(item for item in tariff_options(world, "auren") if item.export_rate_permille == 50)
    decision = record_event(world, "export_tariff_decided", "Escolha fiscal atual.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    event = set_export_tariff(world, option.id, decision_event_id=decision.id)
    assert event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert event.causal_payload == {
        "decision_event_id": decision.id,
        "actor_ref": {"kind": "polity", "id": option.polity_id},
        "selected_affordance_id": option.id,
    }
    refresh_trade_reports(world, replace_today=True)
    return world


def terms(world, quantity=100):
    source, destination = world.economy.stocks[SOURCE], world.economy.stocks[DESTINATION]
    price = world.economy.markets[source.location_id].prices["food"]
    quote = export_quote(world, SOURCE, DESTINATION)
    return {"source_id": SOURCE, "destination_id": DESTINATION, "resource_id": "food", "quantity": quantity,
            "unit_price": price, "quote_day": world.economy.markets[source.location_id].updated_day,
            "route_ids": ["road-campomanso-pedraclara", "river-pedraclara-portovelho"],
            "seller_account_id": "treasury:auren", "buyer_account_id": "treasury:valedouro", **quote,
            "total_price": quantity * price + export_fee(quantity, price, quote["export_rate_permille"])}


def foreign_order_for_auren(world):
    source, destination, quantity = "stock:portovelho", "stock:campomanso", 100
    price = world.economy.markets["portovelho"].prices["food"]
    quote = export_quote(world, source, destination)
    values = {"source_id": source, "destination_id": destination, "resource_id": "food", "quantity": quantity,
              "unit_price": price, "quote_day": world.economy.markets["portovelho"].updated_day,
              "route_ids": ["river-pedraclara-portovelho", "road-campomanso-pedraclara"],
              "seller_account_id": "treasury:valedouro", "buyer_account_id": "treasury:auren", **quote,
              "total_price": quantity * price + export_fee(quantity, price, quote["export_rate_permille"])}
    order = purchase(world, *consent(world, values))
    objective = world.strategy.objectives["supply:campomanso"]
    plan_id = f"plan:{objective.id}"
    world.strategy.plans[plan_id] = StrategicPlan(
        id=plan_id, objective_id=objective.id, stage="await_delivery", order_ids=(order.id,),
        last_review_day=world.clock.absolute_day, last_event_id=order.last_event_id)
    return order


def consent(world, values):
    buyer = world.economy.stocks[values["destination_id"]].owner_ref.to_dict()
    seller = world.economy.stocks[values["source_id"]].owner_ref.to_dict()
    return tuple(record_event(world, f"{action}_decided", "Termos públicos aceitos.", fact_kind=FactKind.DECISION,
                              decision={**values, "action": action, "actor_ref": actor}).id
                 for action, actor in (("buy", buyer),
                                       ("sell", seller)))


@pytest.mark.asyncio
async def test_export_quote_collects_once_without_losing_the_seller_alias_or_delivery(tmp_path, monkeypatch):
    world = tariff_world()
    values = terms(world)
    buyer, source_treasury = world.economy.accounts["treasury:valedouro"], world.economy.accounts["treasury:auren"]
    total = values["total_price"]
    decisions = consent(world, values)
    order = purchase(world, *decisions)
    assert world.economy.accounts[buyer.id].balance == buyer.balance - total
    assert world.economy.accounts[source_treasury.id].balance == source_treasury.balance + total
    receipt = next(event for event in world.events if event.event_type == "export_tariff_collected")
    deltas = [delta for delta in receipt.deltas if delta.owner_kind == "account" and delta.owner_id == source_treasury.id]
    assert len(deltas) == 1 and order.quantity == values["quantity"]
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="executed"):
        purchase(world, *decisions)
    assert world_snapshot(world) == before
    from src.sim.medieval import engine
    before_events, before_rng = list(world.events), world.rng.getstate()

    def fail(*args, **kwargs):
        raise OSError("taxed delivery disk unavailable")

    real_save = engine.save_world
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="taxed delivery disk"):
        await MedievalSimulator(world, save_path=tmp_path / "taxed.mws").step()
    assert world_snapshot(world) == before and world.events == before_events and world.rng.getstate() == before_rng
    monkeypatch.setattr(engine, "save_world", real_save)
    while order.id in world.economy.freight_orders and world.economy.freight_orders[order.id].delivered_quantity < order.quantity:
        await MedievalSimulator(world).step()
    assert world.economy.stocks[DESTINATION].goods["food"] == 6100


@pytest.mark.parametrize("invalid", ["tax_authority", "administrator"])
def test_export_tariff_revalidates_current_jurisdiction_without_partial_purchase(invalid):
    world = tariff_world()
    values = terms(world)
    decisions = consent(world, values)
    if invalid == "tax_authority":
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("trade", "supply")})
    else:
        settlement = world.society.settlements["campomanso"]
        world.society.settlements[settlement.id] = settlement.model_copy(update={"administrator_id": "valedouro"})
    before = world_snapshot(world)
    with pytest.raises(ValueError):
        purchase(world, *decisions)
    assert world_snapshot(world) == before


def test_export_policy_receipt_survives_income_tax_change_and_save(tmp_path):
    from src.sim.medieval.labor import set_income_tax

    world = tariff_world()
    policy_event = world.authority.tax_policies["auren"].export_policy_event_id
    decision = record_event(world, "income_tax_decided", "Renda.", fact_kind=FactKind.DECISION,
                            decision={"action": "set_income_tax", "actor_ref": {"kind": "polity", "id": "auren"},
                                      "polity_id": "auren", "income_rate": 250})
    set_income_tax(world, "auren", 250, decision_event_id=decision.id)
    refresh_trade_reports(world, replace_today=True)
    path = tmp_path / "tariff.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.authority.tax_policies["auren"].export_policy_event_id == policy_event
    assert resumed.authority.tax_policies["auren"].export_rate_permille == 50


def test_third_party_seller_receives_base_price_while_origin_treasury_receives_fee():
    world = tariff_world()
    source_id = "stock:third-party-exporter"
    world.economy.stocks[source_id] = Stock(id=source_id, owner_ref=EntityRef("organization", "oficios-da-serra"),
                                            location_id="campomanso", capacity=500, goods={"food": 100})
    values = terms(world)
    values.update({"source_id": source_id, "seller_account_id": "treasury:oficios-da-serra"})
    price, quantity = values["unit_price"], values["quantity"]
    seller = world.economy.accounts[values["seller_account_id"]]
    collector = world.economy.accounts["treasury:auren"]
    buyer = world.economy.accounts["treasury:valedouro"]
    purchase(world, *consent(world, values))
    fee = export_fee(quantity, price, 50)
    assert world.economy.accounts[seller.id].balance == seller.balance + quantity * price
    assert world.economy.accounts[collector.id].balance == collector.balance + fee
    assert world.economy.accounts[buyer.id].balance == buyer.balance - quantity * price - fee


@pytest.mark.parametrize("invalid", ["stale", "invented"])
def test_export_tariff_executor_rejects_stale_or_invented_selection_without_effect(invalid):
    world = create_medieval_world(73)
    refresh_reports(world)
    option = next(item for item in tariff_options(world, "auren") if item.export_rate_permille == 50)
    decision = record_event(world, "export_tariff_decided", "Escolha fiscal.", fact_kind=FactKind.DECISION,
                            decision=option.decision())
    if invalid == "stale":
        world.clock = world.clock.advance(1)
    else:
        option = option.model_copy(update={"id": option.id + ":invented"})
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale"):
        set_export_tariff(world, option.id, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    policy = world.authority.tax_policies["auren"]
    assert policy.export_rate_permille == 0 and policy.export_policy_event_id is None


@pytest.mark.asyncio
async def test_monthly_fiscal_policy_uses_a_real_paid_payroll_then_republishes_current_quote():
    world = create_medieval_world(73)
    stock = world.economy.stocks["stock:campomanso"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "food": 10_000}})
    market = world.economy.markets["campomanso"]
    world.economy.markets[market.id] = market.model_copy(update={"prices": {**market.prices, "food": 16}})
    treasury = world.economy.accounts["treasury:auren"]
    world.economy.accounts[treasury.id] = treasury.model_copy(update={"balance": 1100})
    await MedievalSimulator(world).step()
    payroll = world.economy.payrolls["works:campos-do-lume"]
    policy = world.authority.tax_policies["auren"]
    wage_event = next(
        event for event in world.events
        if event.event_type == "wages_paid"
        and any(delta.owner_kind == "account" and delta.owner_id == treasury.id
                for delta in event.deltas)
        and all(any(delta.owner_kind == "account"
                    and delta.owner_id == f"household:{group_id}"
                    for delta in event.deltas)
                for group_id in payroll.workers_by_group)
    )
    treasury_delta = next(delta for delta in wage_event.deltas
                          if delta.owner_kind == "account" and delta.owner_id == treasury.id)
    assert payroll.gross > 0
    assert int(treasury_delta.before) - int(treasury_delta.after) == payroll.gross
    assert world.economy.accounts[treasury.id].balance < 1100
    # The current conservative policy only raises the tariff when the dated
    # payroll reading still shows a cash shortfall.  Other monthly owners may
    # legitimately spend or replenish the treasury before the final quote is
    # published, so the invariant is that the quote reflects the policy that
    # actually survived that boundary, not a hard-coded rate.
    quote = next(report for report in world.knowledge.reports.values()
                 if report.kind == "offer" and report.stock_id == stock.id and report.resource_id == "food")
    assert quote.observed_day == world.clock.absolute_day == 30
    assert (quote.export_rate_permille, quote.export_policy_event_id) == (
        policy.export_rate_permille, policy.export_policy_event_id)


@pytest.mark.asyncio
async def test_only_a_pending_foreign_delivery_causes_the_conservative_tariff_withdrawal():
    pending = tariff_world()
    foreign_order_for_auren(pending)
    assert review_export_tariffs(pending)
    assert pending.authority.tax_policies["auren"].export_rate_permille == 0

    delivered = tariff_world()
    order = foreign_order_for_auren(delivered)
    while delivered.economy.freight_orders[order.id].delivered_quantity < order.quantity:
        await MedievalSimulator(delivered).step()
    assert not review_export_tariffs(delivered)
    assert delivered.authority.tax_policies["auren"].export_rate_permille == 50
