from types import SimpleNamespace

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import produce_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.production_priority import (
    ACTION, execute_production_priority, production_priority_options,
)


OWNER = EntityRef("polity", "valedouro")


@pytest.fixture(autouse=True)
def _authority(monkeypatch):
    monkeypatch.setattr(
        "src.sim.medieval.production_priority.can_actor_act_for",
        lambda *_args: True,
    )


def _world(*, second=True, day=30, authority=True):
    facilities = {
        "works:a": SimpleNamespace(id="works:a", stock_id="stock:a", recipe_id="recipe:a",
                                    payroll_account_id="treasury:v", site_id="site:a"),
    }
    stocks = {"stock:a": SimpleNamespace(owner_ref=OWNER, location_id="salgueiro")}
    recipes = {"recipe:a": SimpleNamespace(occupation="farmer")}
    if second:
        facilities["works:b"] = SimpleNamespace(id="works:b", stock_id="stock:b", recipe_id="recipe:b",
                                                  payroll_account_id="treasury:v", site_id="site:b")
        stocks["stock:b"] = SimpleNamespace(owner_ref=OWNER, location_id="salgueiro")
        recipes["recipe:b"] = SimpleNamespace(occupation="farmer")
    authority_state = SimpleNamespace()
    clock = SimpleNamespace(absolute_day=day)
    world = SimpleNamespace(
        economy=SimpleNamespace(facilities=facilities, stocks=stocks, recipes=recipes,
                                production_priorities={}),
        clock=clock, events=[], authority=authority_state,
    )
    # Keep the fake deliberately narrow: production code uses the canonical
    # authority function, while tests monkeypatch that boundary below.
    return world, authority


def test_options_only_exist_for_real_same_payroll_workforce_conflicts():
    world, _ = _world()
    options = production_priority_options(world, OWNER)
    assert [item.facility_id for item in options] == ["works:a", "works:b"]
    assert all(set(item.decision()) == {"action", "actor_ref", "selected_affordance_id"}
               and item.decision()["action"] == ACTION for item in options)

    isolated, _ = _world(second=False)
    assert production_priority_options(isolated, OWNER) == ()


def test_options_do_not_cross_payroll_settlement_or_occupation():
    world, _ = _world()
    world.economy.facilities["works:b"].payroll_account_id = "treasury:other"
    assert production_priority_options(world, OWNER) == ()


def test_executor_recomposes_and_rejects_stale_id(monkeypatch):
    world, _ = _world()
    option = production_priority_options(world, OWNER)[0]
    event = SimpleNamespace(id="decision:1", day=world.clock.absolute_day,
                            fact_kind=FactKind.DECISION,
                            causal_origin=CausalOrigin.ACTOR_DECISION,
                            decision=option.decision())
    world.events.append(event)
    draft = execute_production_priority(world, OWNER, option.id, event.id)
    assert draft.facility_id == option.facility_id
    assert draft.effective_day == 60
    with pytest.raises(ValueError, match="stale"):
        execute_production_priority(world, OWNER, "forged", event.id)


def test_executor_rejects_copied_decision_without_actor_authorship():
    world, _ = _world()
    option = production_priority_options(world, OWNER)[0]
    event = SimpleNamespace(id="decision:copied", day=world.clock.absolute_day,
                            fact_kind=FactKind.DECISION,
                            causal_origin=CausalOrigin.DETERMINISTIC,
                            decision=option.decision())
    world.events.append(event)

    with pytest.raises(ValueError, match="exact current actor decision"):
        execute_production_priority(world, OWNER, option.id, event.id)


def test_selected_priority_survives_save_and_orders_only_the_next_boundary(tmp_path):
    """A chosen line changes next month's real labor competition, not today."""
    from src.systems.time import WorldClock
    from src.sim.medieval.production_priority import set_production_priority

    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    option = next(item for item in production_priority_options(world, OWNER)
                  if item.facility_id == "works:campos-de-salgueiro")
    decision = record_event(
        world, "institutional_decision_turn_decided", "Escolha de produção.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=option.decision(),
    )
    priority = set_production_priority(world, OWNER, option.id, decision_event_id=decision.id)
    assert priority.effective_day == 60

    path = tmp_path / "priority.mws"
    save_world(world, path)
    resumed = load_world(path)
    resumed.clock = WorldClock(60)
    produce_monthly(resumed)

    food = resumed.economy.facilities["works:campos-de-salgueiro"]
    logging = resumed.economy.facilities["works:bosques-de-salgueiro"]
    assert food.last_batches > 0 and logging.last_batches == 0
    receipt = next(event for event in reversed(resumed.events)
                   if event.event_type in {"production_completed", "production_limited"}
                   and event.causal_payload["production"]["facility_id"] == food.id)
    assert priority.last_event_id in {link.cause_event_id for link in receipt.causal_links}
    assert receipt.causal_payload["production"]["production_priority_event_id"] == priority.last_event_id
    world_snapshot(resumed)


def test_shared_payroll_priority_is_receipt_gated_and_changes_next_boundary_order(tmp_path):
    import copy
    from src.systems.time import WorldClock
    from src.sim.medieval.production_priority import set_production_priority

    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    account_id = "treasury:auren"
    world.clock = WorldClock(270)
    world.economy.accounts[account_id] = world.economy.accounts[account_id].model_copy(
        update={"balance": 0}
    )
    produce_monthly(world)

    options = production_priority_options(world, actor)
    pool_options = [item for item in options if item.scope == "shared_payroll_pool"]
    assert len(pool_options) >= 2
    assert {item.payroll_account_id for item in pool_options} == {account_id}
    assert len({item.settlement_id for item in pool_options}) > 1
    world.clock = WorldClock(271)
    assert not any(item.scope == "shared_payroll_pool"
                   for item in production_priority_options(world, actor))
    world.clock = WorldClock(270)
    viability = copy.deepcopy(world)
    viability.economy.accounts[account_id] = viability.economy.accounts[account_id].model_copy(
        update={"balance": 1_000_000}
    )
    viability.clock = WorldClock(300)
    produce_monthly(viability)
    target = next(item for item in pool_options
                  if viability.economy.facilities[item.facility_id].last_batches > 0)
    decision = record_event(
        world, "institutional_decision_turn_decided", "Priorizar instalação do caixa comum.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}}, decision=target.decision(),
    )
    priority = set_production_priority(
        world, actor, target.id, decision_event_id=decision.id
    )
    assert priority.scope == "shared_payroll_pool"
    assert priority.effective_day == 300
    assert len(world.economy.production_priorities) == 1

    path = tmp_path / "shared-priority.mws"
    save_world(world, path)
    world = load_world(path)
    priority = world.economy.production_priorities[priority.id]
    target = next(item for item in pool_options if item.facility_id == priority.facility_id)
    tampered = copy.deepcopy(world)
    receipt_index = next(index for index, event in enumerate(tampered.events)
                         if event.id == priority.last_event_id)
    receipt = tampered.events[receipt_index]
    tampered.events[receipt_index] = receipt.model_copy(update={
        "causal_payload": {**receipt.causal_payload, "facility_id": "works:forged"}
    })
    with pytest.raises(ValueError, match="invalid production priority provenance"):
        tampered.economy.validate(tampered)

    recipe = world.economy.recipes[world.economy.facilities[target.facility_id].recipe_id]
    batch_cost = recipe.workers * world.economy.facilities[target.facility_id].wage_per_worker
    world.economy.accounts[account_id] = world.economy.accounts[account_id].model_copy(
        update={"balance": batch_cost}
    )
    world.clock = WorldClock(300)
    event_start = len(world.events)
    produce_monthly(world)

    account_facility_events = [
        event for event in world.events[event_start:]
        if event.event_type in {"production_completed", "production_limited"}
        and event.causal_payload["production"]["facility_id"] in {
            item.id for item in world.economy.facilities.values()
            if item.payroll_account_id == account_id
        }
    ]
    assert account_facility_events[0].causal_payload["production"]["facility_id"] == target.facility_id
    assert account_facility_events[0].causal_payload["production"]["batches"] > 0
    assert account_facility_events[0].causal_payload["production"][
        "production_priority_event_id"
    ] == priority.last_event_id
    world.economy.validate(world)


def test_priority_is_registered_in_the_single_monthly_institutional_menu():
    from src.sim.medieval.institutional_agenda import monthly_adapters, monthly_actors

    world = create_medieval_world(73)
    assert any(adapter.name == "production_priority" for adapter in monthly_adapters())
    assert OWNER in monthly_actors(world)


def test_priority_menu_explains_local_tradeoffs_with_owned_evidence():
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.production_priority import production_priority_adapters

    world = create_medieval_world(73)
    refresh_reports(world)
    options = production_priority_options(world, OWNER)
    assert len(options) >= 2
    adapter = production_priority_adapters()[0]
    from src.sim.medieval.institutional_decision_turn import _composed_situation
    composed = _composed_situation(
        world, OWNER, {option.id: (adapter, option) for option in options}
    )
    situation = composed["production_priority"]

    report = world.knowledge.settlement_report(OWNER, options[0].settlement_id)
    assert report is not None
    assert report.channel == "local_settlement_report"
    causes = set(adapter.causes_fn(world, options[0]))
    assert report.event_id in causes
    cohort_sources = {
        group.last_event_id for group in world.society.population.values()
        if group.settlement_id == options[0].settlement_id
        and group.occupation == options[0].occupation and group.last_event_id
    }
    assert cohort_sources <= causes
    assert report.observed_day <= world.clock.absolute_day

    conflict = next(item for item in situation["payroll_competition"]
                    if item["settlement_id"] == options[0].settlement_id)
    assert conflict["settlement_name"] == world.society.settlements[options[0].settlement_id].name
    assert conflict["settlement_report"]["event_id"] == report.event_id
    expected_workers = sum(
        world.society.available_count(group.id) for group in world.society.population.values()
        if group.settlement_id == options[0].settlement_id
        and group.occupation == options[0].occupation
    )
    assert conflict["society_available_workers"] == expected_workers
    assert conflict["payroll_balance"] == world.economy.accounts[
        options[0].payroll_account_id
    ].balance
    assert all(line["outputs_per_batch"] and line["inputs_per_batch"] is not None
               for line in conflict["lines"])
    assert all("resource_name" in row for line in conflict["lines"]
               for row in line["outputs_per_batch"] + line["inputs_per_batch"])
    assert all("unit" in row for line in conflict["lines"]
               for row in line["outputs_per_batch"] + line["inputs_per_batch"])
    assert all("available" in row and "source_event_id" in row
               for line in conflict["lines"] for row in line["inputs_per_batch"])
    rendered = repr(situation)
    assert "stock:" not in rendered and "treasury:" not in rendered
    label = adapter.label_fn(options[0])
    assert options[0].facility_name in label
    assert options[0].settlement_name in label


def test_menu_labels_applied_priority_as_history_and_names_next_boundary():
    from src.systems.time import WorldClock
    from src.sim.medieval.intelligence import refresh_reports
    from src.sim.medieval.institutional_decision_turn import _composed_situation
    from src.sim.medieval.production_priority import (
        production_priority_adapters, set_production_priority,
    )

    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    refresh_reports(world)
    option = next(item for item in production_priority_options(world, OWNER)
                  if item.facility_id == "works:campos-de-salgueiro")
    decision = record_event(
        world, "institutional_decision_turn_decided", "Prioridade escolhida.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=option.decision(),
    )
    priority = set_production_priority(world, OWNER, option.id, decision_event_id=decision.id)

    world.clock = WorldClock(60)
    produce_monthly(world)
    options = production_priority_options(world, OWNER)
    adapter = production_priority_adapters()[0]
    situation = _composed_situation(
        world, OWNER, {item.id: (adapter, item) for item in options}
    )["production_priority"]
    conflict = next(item for item in situation["payroll_competition"]
                    if item["settlement_id"] == priority.settlement_id)

    assert conflict["next_effective_day"] == 90
    current_cycle_workers = sum(
        payroll.workers_by_group.get(group.id, 0)
        for payroll in world.economy.payrolls.values()
        if payroll.day == world.clock.absolute_day
        for group in world.society.population.values()
        if group.settlement_id == priority.settlement_id
        and group.occupation == priority.occupation
    )
    assert current_cycle_workers > 0
    expected_next_cycle_workers = sum(
        world.society.available_count(group.id) for group in world.society.population.values()
        if group.settlement_id == priority.settlement_id
        and group.occupation == priority.occupation
    )
    assert conflict["society_available_workers"] == expected_next_cycle_workers
    from src.sim.medieval.economy import monthly_workforce
    current_workforce = monthly_workforce(world)
    remaining_current_cycle = sum(
        current_workforce[group.id] for group in world.society.population.values()
        if group.settlement_id == priority.settlement_id
        and group.occupation == priority.occupation
    )
    assert expected_next_cycle_workers > remaining_current_cycle
    assert conflict["last_applied_priority"] == {
        "facility_id": priority.facility_id,
        "facility_name": "Campos de Salgueiro",
        "effective_day": 60,
        "event_id": priority.last_event_id,
    }
    assert conflict["scheduled_priority"] is None
