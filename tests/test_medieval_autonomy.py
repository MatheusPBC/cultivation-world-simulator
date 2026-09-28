"""Real authority boundaries; removing a mandate must prevent material execution."""

import copy

import pytest

from src.classes.governance.models import StrategicPlan
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.persistence import world_snapshot, save_world, load_world
from tests.test_medieval_markets import consent, terms
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event


def test_supply_completion_event_order_does_not_depend_on_plan_insertion_order():
    from src.sim.medieval.demand import objective_target
    from src.sim.medieval.procurement import progress_supply

    base = create_medieval_world(73)
    objectives = tuple(base.strategy.objectives.values())[:2]

    def complete(insertion_order):
        world = copy.deepcopy(base)
        targets = {objective.id: objective_target(world, objective) for objective in objectives}
        premise = record_event(
            world, "supply_completion_order_fixture", "Planos preparados no cenário de teste.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_payload={"root_premise": {
                "kind": "scenario_bootstrap", "domain": "supply_completion_order_test",
                "source_refs": [{"kind": "scenario", "id": "supply_completion_order_test"}],
                "observed_day": world.clock.absolute_day,
            }},
            deltas=tuple(delta for objective in objectives for delta in (
                _delta("stock", objective.stock_id, objective.resource_id,
                       world.economy.stocks[objective.stock_id].goods.get(objective.resource_id, 0),
                       targets[objective.id]),
                _delta("plan", f"plan:{objective.id}", "stage", None, "await_delivery"),
            )),
        )
        for objective in objectives:
            stock = world.economy.stocks[objective.stock_id]
            world.economy.stocks[stock.id] = stock.model_copy(update={
                "goods": {**stock.goods, objective.resource_id: targets[objective.id]},
                "last_event_ids": {**stock.last_event_ids, objective.resource_id: premise.id},
            })
        for objective in insertion_order:
            plan_id = f"plan:{objective.id}"
            world.strategy.plans[plan_id] = StrategicPlan(
                id=plan_id, objective_id=objective.id, stage="await_delivery",
                last_review_day=world.clock.absolute_day, last_event_id=premise.id,
            )
        progress_supply(world)
        return [event.deltas[0].owner_id for event in world.events
                if event.event_type == "supply_plan_updated"]

    ordered = complete(objectives)
    assert len(ordered) == 2
    assert ordered == complete(reversed(objectives))


def test_bootstrap_authority_is_independent_of_titles_and_character_count():
    world = create_medieval_world(73, character_count=1)
    assert hasattr(world, "authority"), "medieval authority owner missing"
    from src.classes.governance.authority import can_actor_act_for
    government = EntityRef(kind="polity", id="auren")
    person = next(iter(world.society.characters.values()))
    assert can_actor_act_for(world, government, government, "trade")
    assert not can_actor_act_for(world, EntityRef(kind="character", id=person.id), government, "trade")


def test_revoked_authority_rejects_previously_consented_purchase_without_mutation(tmp_path):
    world = create_medieval_world(73)
    assert hasattr(world, "authority"), "medieval authority owner missing"
    from src.sim.medieval.markets import purchase
    decisions = consent(world, terms(world))
    office = world.authority.offices["office:polity:valedouro"]
    world.authority.offices[office.id] = office.model_copy(update={"ends_day": 0})
    path = tmp_path / "revoked.mws"
    save_world(world, path)
    world = load_world(path)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="authority"):
        purchase(world, *decisions)
    assert world_snapshot(world) == before


def test_dead_office_holder_cannot_authorize_institution():
    world = create_medieval_world(73)
    assert hasattr(world, "authority"), "medieval authority owner missing"
    from src.classes.governance.authority import can_actor_act_for
    person = next(iter(world.society.characters.values()))
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(update={"holder_ref": EntityRef(kind="character", id=person.id)})
    government = office.institution_ref
    assert can_actor_act_for(world, government, government, "trade")
    world.society.characters[person.id] = person.model_copy(update={"death_day": 0, "population_group_id": None})
    assert not can_actor_act_for(world, government, government, "trade")


def test_no_reports_means_no_supply_orders_and_private_stocks_are_not_disclosed():
    world = create_medieval_world(73)
    assert hasattr(world, "knowledge"), "information owner missing"
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import review_supply
    stock = world.economy.stocks["stock:portovelho"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 0}})
    review_supply(world)
    assert not world.economy.freight_orders
    refresh_reports(world)
    own = EntityRef(kind="polity", id="valedouro")
    reports = world.knowledge.for_actor(own)
    assert any(r.stock_id == "stock:portovelho" and r.kind == "inventory" for r in reports)
    assert not any(r.stock_id == "stock:torre-do-ambar" for r in reports)
    assert not any(r.stock_id == "stock:campomanso" and r.kind == "inventory" for r in reports)


def test_seller_revalidates_reserve_and_refuses_stale_public_offer():
    world = create_medieval_world(73)
    assert hasattr(world, "knowledge"), "information owner missing"
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import consider_sale
    refresh_reports(world)
    values = terms(world, quantity=100)
    decision = consent(world, values)[0]
    stock = world.economy.stocks[values["source_id"]]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 2200}})
    before = world.economy.to_dict()
    assert consider_sale(world, values, decision) is None
    assert world.events[-1].event_type == "sale_refused"
    assert world.economy.to_dict() == before


async def test_natural_monthly_supply_creates_real_orders_without_daily_decision_spam(tmp_path):
    world = create_medieval_world(73)
    assert hasattr(world, "strategy"), "strategic intentions owner missing"
    engine = MedievalSimulator(world)
    money = sum(a.balance for a in world.economy.accounts.values())
    await engine.step()
    assert world.clock.absolute_day == 30
    assert any(o.resource_id in {"iron", "wood"} for o in world.economy.freight_orders.values())
    supply_decisions = [event for event in world.events
                        if event.event_type in {"freight_decided", "buy_decided", "sell_decided", "sale_refused"}]
    assert supply_decisions
    assert all(event.causal_payload["decision_source"] == {
        "kind": "fallback", "policy": "routine-rules",
        "rule": ("market_sale_response" if event.event_type in {"sell_decided", "sale_refused"}
                 else "supply_objective"),
    } for event in supply_decisions)
    while world.clock.absolute_day < 60:
        await engine.step()
    assert world.economy.freight_orders
    assert sum(a.balance for a in world.economy.accounts.values()) == money
    assert any(p.stage == "await_delivery" for p in world.strategy.plans.values())
    orders = len(world.economy.freight_orders)
    # "No daily decision spam" is about supply itself: the same iron/wood
    # objective must not be re-decided every day once its order is open. Real
    # hunger now drives its own, independent institutional-aid traffic (a
    # settlement request answered, say), which is genuine new activity, not
    # spam, and must not be mistaken for it here.
    supply_decision_types = {"freight_decided", "buy_decided"}
    supply_decision_count = len([e for e in world.events
                                 if e.fact_kind.value == "decision" and e.event_type in supply_decision_types])
    await engine.step()
    assert world.clock.absolute_day == 61
    assert len(world.economy.freight_orders) == orders
    assert len([e for e in world.events if e.fact_kind.value == "decision"
               and e.event_type in supply_decision_types]) == supply_decision_count
    path = tmp_path / "autonomous.mws"
    save_world(world, path)
    resumed = load_world(path)
    for value in (world, resumed):
        while value.clock.absolute_day < 90:
            await MedievalSimulator(value).step()
    assert world_snapshot(world) == world_snapshot(resumed)
    assert world.events == resumed.events
    assert sum(a.balance for a in world.economy.accounts.values()) == money
    assert any(o.delivered_quantity for o in world.economy.freight_orders.values())


async def test_save_failure_rolls_back_new_reports_plans_money_and_orders(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    await MedievalSimulator(world).step()
    before = world_snapshot(world)
    history = list(world.events)
    from src.sim.medieval import engine
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="disk"):
        await MedievalSimulator(world, save_path=tmp_path / "failed.mws").step()
    assert world_snapshot(world) == before
    assert world.events == history


def test_insufficient_funds_blocks_plan_without_granting_food_or_money():
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import review_supply
    world = create_medieval_world(73)
    # Isolate public food procurement; solvent workshops have independent input goals.
    world.strategy.objectives = {k: o for k, o in world.strategy.objectives.items() if o.kind == "maintain_food_reserve"}
    # Prepared shortage: every Valedouro stock has no surplus; no internal escape.
    for key, stock in list(world.economy.stocks.items()):
        if stock.owner_ref.id == "valedouro":
            world.economy.stocks[key] = stock.model_copy(update={"goods": {"food": 0}})
    account = world.economy.accounts["treasury:valedouro"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    before = world.economy.to_dict()
    refresh_reports(world)
    review_supply(world)
    plan = world.strategy.plans["plan:supply:portovelho"]
    assert plan.stage == "blocked"
    assert "saldo insuficiente" in plan.blocker
    assert world.economy.to_dict() == before


def test_planner_cannot_see_new_foreign_surplus_without_disclosure():
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import review_supply
    world = create_medieval_world(73)
    for key, stock in list(world.economy.stocks.items()):
        world.economy.stocks[key] = stock.model_copy(update={"goods": {"food": 0}})
    refresh_reports(world)
    stock = world.economy.stocks["stock:campomanso"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 10000}})
    review_supply(world)
    assert not world.economy.freight_orders


def test_path_uses_open_canonical_alternative_or_reports_no_route():
    from src.sim.medieval.routing import supply_path
    world = create_medieval_world(73)
    assert supply_path(world, "campomanso", "pedraclara") == ("road-campomanso-pedraclara",)
    world.map.routes["road-campomanso-pedraclara"].update_runtime(enabled=False)
    assert supply_path(world, "campomanso", "pedraclara") == (
        "road-salgueiro-campomanso", "road-portovelho-salgueiro", "river-pedraclara-portovelho")
    world.map.routes["road-salgueiro-campomanso"].update_runtime(enabled=False)
    assert supply_path(world, "campomanso", "pedraclara") is None


def test_save_rejects_invalid_observation_channel_and_orphaned_plan():
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import review_supply
    from src.sim.medieval.persistence import restore_snapshot
    world = create_medieval_world(73)
    refresh_reports(world)
    review_supply(world)
    snapshot = world_snapshot(world)
    report = next(r for r in snapshot["knowledge"]["reports"].values() if r["kind"] == "inventory")
    report["recipient_ref"] = {"kind": "polity", "id": "unregistered-spy"}
    with pytest.raises(ValueError, match="actor"):
        restore_snapshot(snapshot, world.events)
    snapshot = world_snapshot(world)
    next(iter(snapshot["strategy"]["plans"].values()))["objective_id"] = "missing"
    with pytest.raises(ValueError, match="objective"):
        restore_snapshot(snapshot, world.events)


def test_refusal_is_a_direct_cause_of_the_blocked_plan():
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.procurement import review_supply
    world = create_medieval_world(73)
    for key, stock in list(world.economy.stocks.items()):
        if stock.id != "stock:campomanso":
            world.economy.stocks[key] = stock.model_copy(update={"goods": {"food": 0}})
    refresh_reports(world)
    stock = world.economy.stocks["stock:campomanso"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 2200}})
    review_supply(world)
    plan = world.strategy.plans["plan:supply:portovelho"]
    assert plan.stage == "blocked"
    event = next(e for e in world.events if e.id == plan.last_event_id)
    refusals = {e.id for e in world.events if e.event_type == "sale_refused"}
    assert refusals.intersection(link.cause_event_id for link in event.causal_links)
