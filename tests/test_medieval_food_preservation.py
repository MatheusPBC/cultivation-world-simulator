"""Food storage is a bounded physical capability, not a narrative bonus."""

from copy import deepcopy
import asyncio

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _apply_stock, _delta, monthly_workforce
from src.sim.medieval.character_rite_policy import review_character_rites
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.expansion import (site_construction_options,
                                        start_site_construction,
                                        progress_expansions)
from src.sim.medieval.food_preservation import (deteriorate_public_food,
                                               protected_food_capacity)
from src.sim.medieval.infrastructure import (damage_site,
                                             execute_repair_authorization_option,
                                             progress_repairs,
                                             repair_authorization_options)
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import (accept_research_work, progress_research,
                                       researcher_work_options)
from src.sim.medieval.research_policy import (execute_research_option,
                                               research_options)
from src.systems.time import WorldClock


ACTOR = EntityRef("polity", "auren")
TECH = "food_preservation"
BLUEPRINT = "smokehouse-construction"
SETTLEMENT = "pedraclara"


def _actor_decision(world, event_type, text, decision, cause_ids=()):
    return record_event(
        world, event_type, text, fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision=decision, cause_ids=cause_ids,
    )


def _set_public_food(world, stock_id, quantity):
    stock = world.economy.stocks[stock_id]
    goods = dict(stock.goods)
    goods["food"] = quantity
    return _apply_stock(
        world, stock, goods, "food_storage_scenario_prepared",
        "Fixture causal com estoque público equivalente para comparar a conservação.",
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "public_food_storage",
            "source_refs": [{"kind": "stock", "id": stock_id}],
            "observed_day": world.clock.absolute_day,
        }},
    )


def _research_and_build_smokehouse(world, monkeypatch):
    research = next(item for item in research_options(world, ACTOR)
                    if item.technology_id == TECH
                    and world.economy.stocks[item.stock_id].location_id == SETTLEMENT)
    sponsor = _actor_decision(world, "research_sponsorship_decided",
                              "Auren financia a conservação alimentar.", research.decision())
    execute_research_option(world, ACTOR, research.id, sponsor.id)
    world.clock = WorldClock(world.clock.absolute_day + 1)
    offer = next(item for item in researcher_work_options(world, research.researcher_id)
                 if item.technology_id == TECH)
    consent = _actor_decision(world, "research_work_accepted",
                              "A pesquisadora aceita trabalhar na conservação.",
                              offer.decision(), (sponsor.id,))
    accept_research_work(world, research.researcher_id, offer.id, consent.id)
    asyncio.run(review_character_rites(world, world.agenda.pop_due(world.clock.absolute_day)))
    for day in (30, 60, 90, 120, 150, 180):
        world.clock = WorldClock(day)
        progress_research(world, monthly_workforce(world))
    assert world.knowledge.knows(ACTOR, TECH)
    control = deepcopy(world)

    option = next(item for item in site_construction_options(world, ACTOR)
                  if item.blueprint_id == BLUEPRINT and item.settlement_id == SETTLEMENT)
    from src.sim.medieval.expansion import _construction_terms
    authorization = _actor_decision(world, "smokehouse_construction_decided",
                                    "Auren escolhe construir a casa de defumação.",
                                    _construction_terms(option))
    before = world_snapshot(world)
    from src.sim.medieval import expansion
    start_impl = expansion._start_site_construction_in_place

    def fail_after_start(candidate, *args, **kwargs):
        start_impl(candidate, *args, **kwargs)
        raise RuntimeError("injected construction failure")

    monkeypatch.setattr(expansion, "_start_site_construction_in_place", fail_after_start)
    with pytest.raises(RuntimeError, match="injected construction failure"):
        start_site_construction(world, option, decision_event_id=authorization.id)
    assert world_snapshot(world) == before
    monkeypatch.undo()

    project = start_site_construction(world, option, decision_event_id=authorization.id)
    for day in (210, 240):
        world.clock = WorldClock(day)
        progress_expansions(world, monthly_workforce(world))
    assert world.economy.expansions[project.id].stage == "completed"
    return world.map.infrastructure_sites[project.new_site_id], control


def test_researched_smokehouse_reduces_loss_and_repair_restores_protection(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    money_before = sum(account.balance for account in world.economy.accounts.values())
    site, control = _research_and_build_smokehouse(world, monkeypatch)
    assert site.kind == "smokehouse"
    assert site.owner_ref == site.maintainer_ref == ACTOR

    stock_id = f"stock:{SETTLEMENT}"
    _set_public_food(world, stock_id, 50_000)
    _set_public_food(control, stock_id, 50_000)
    food_before_losses = sum(stock.goods.get("food", 0)
                             for stock in world.economy.stocks.values())
    need = world.economy.needs[SETTLEMENT]
    reserve = sum(world.society.available_count(group.id)
                  for group in world.society.population.values()
                  if group.settlement_id == SETTLEMENT)
    assert deteriorate_public_food(control, control.economy.needs[SETTLEMENT], 50_000) is None
    assert control.economy.stocks[stock_id].goods["food"] == 50_000
    control_event = deteriorate_public_food(control, control.economy.needs[SETTLEMENT], reserve)
    intact_event = deteriorate_public_food(world, need, reserve)
    assert control_event is not None and intact_event is not None
    assert int(control_event.deltas[0].after) == 49_762
    assert int(intact_event.deltas[0].after) == 49_772
    assert intact_event.causal_links
    assert intact_event.causal_payload["food_storage_loss"]["protected_quantity"] == 2_000

    # A real, dated site damage fact removes half the physical capacity.
    world.clock = WorldClock(241)
    damaged_site = world.map.infrastructure_sites[site.id]
    damage = record_event(
        world, "smokehouse_damaged", "Dano material reduz a integridade da instalação.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("site", site.id, "integrity", damaged_site.integrity, 0.5),),
        cause_ids=(damaged_site.last_event_id,),
    )
    damage_site(world, site.id, event_id=damage.id)
    assert protected_food_capacity(world, world.economy.stocks[stock_id])[0] == 1_000

    world.clock = WorldClock(270)
    damaged_loss = deteriorate_public_food(world, world.economy.needs[SETTLEMENT], reserve)
    assert damaged_loss is not None
    assert damaged_loss.causal_payload["food_storage_loss"]["protected_quantity"] == 1_000
    assert int(damaged_loss.deltas[0].before) - int(damaged_loss.deltas[0].after) == 231

    refresh_reports(world)
    repair_option = next(item for item in repair_authorization_options(world, ACTOR)
                         if item.site_id == site.id)
    authorization = _actor_decision(world, "smokehouse_repair_decided",
                                    "Auren escolhe reparar a casa de defumação.",
                                    repair_option.decision())
    repair = execute_repair_authorization_option(world, ACTOR, repair_option.id, authorization.id)
    assert repair.stage == "waiting"
    for day in (300, 330, 360, 390, 420):
        world.clock = WorldClock(day)
        refresh_reports(world)
        progress_repairs(world, monthly_workforce(world))
    repaired = world.map.infrastructure_sites[site.id]
    assert repaired.integrity == 1.0
    assert world.economy.repairs[repair.id].stage == "completed"
    assert world.economy.payrolls[repair.id].gross > 0
    assert protected_food_capacity(world, world.economy.stocks[stock_id])[0] == 2_000

    world.clock = WorldClock(450)
    recovered_loss = deteriorate_public_food(world, world.economy.needs[SETTLEMENT], reserve)
    assert recovered_loss is not None
    assert recovered_loss.causal_payload["food_storage_loss"]["protected_quantity"] == 2_000
    assert int(recovered_loss.deltas[0].before) - int(recovered_loss.deltas[0].after) < 231
    assert world.economy.stocks[stock_id].goods["wood"] < control.economy.stocks[stock_id].goods["wood"]
    losses = [event for event in world.events if event.event_type == "public_food_storage_loss"]
    lost_food = sum(int(delta.before) - int(delta.after)
                    for event in losses for delta in event.deltas
                    if delta.owner_kind == "stock" and delta.aspect == "food")
    assert sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values()) == food_before_losses - lost_food
    assert sum(account.balance for account in world.economy.accounts.values()) == money_before
    validate_history(world.events, world.clock.absolute_day)

    save_path = tmp_path / "food-preservation.mws"
    save_world(world, save_path)
    assert world_snapshot(load_world(save_path)) == world_snapshot(world)
