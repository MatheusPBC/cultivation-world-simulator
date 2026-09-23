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
        economy=SimpleNamespace(facilities=facilities, stocks=stocks, recipes=recipes),
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
                            fact_kind=FactKind.DECISION, decision=option.decision())
    world.events.append(event)
    draft = execute_production_priority(world, OWNER, option.id, event.id)
    assert draft.facility_id == option.facility_id
    assert draft.effective_day == 60
    with pytest.raises(ValueError, match="stale"):
        execute_production_priority(world, OWNER, "forged", event.id)


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


def test_priority_is_registered_in_the_single_monthly_institutional_menu():
    from src.sim.medieval.institutional_agenda import monthly_adapters, monthly_actors

    world = create_medieval_world(73)
    assert any(adapter.name == "production_priority" for adapter in monthly_adapters())
    assert OWNER in monthly_actors(world)
