"""Deprivation and age are material laws: nobody chooses them, nothing is drawn."""

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.force_command import appoint_detachment_commander, detachment_command_options
import src.sim.medieval.mortality as mortality
from src.sim.medieval.mortality import LIFESPAN_DAYS, _deprivation_deaths
from src.sim.medieval.economy import consume_monthly
from src.systems.time import WorldClock
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_character_travel import garrison, lone_world

TARGET = "campomanso"


def famine_world():
    """Prepared scenario: no granary, no producer, and health already pressed."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    for key, stock in tuple(world.economy.stocks.items()):
        world.economy.stocks[key] = stock.model_copy(update={"goods": {**stock.goods, "food": 0}})
    for key, need in tuple(world.economy.needs.items()):
        world.economy.needs[key] = need.model_copy(update={"health": 150})
    return world


def feed(world):
    """Stock the granary and fund every household so the ration is actually
    bought this cycle -- there is no automatic relief left to fill the gap
    for free, so being fed now requires real, paid consumption."""
    for key, need in world.economy.needs.items():
        stock = world.economy.stocks[need.stock_id]
        # Leave room for births before the monthly consumption pass; a two-
        # ration shortage in an artisan town still triggers the mortality law.
        ration = world.society.population_at(key) * 2 + 100
        world.economy.stocks[stock.id] = stock.model_copy(
            update={"goods": {**stock.goods, "food": ration}})
        price = world.economy.markets[key].prices["food"]
        for group in world.society.population.values():
            if group.settlement_id != key:
                continue
            account = world.economy.accounts[f"household:{group.id}"]
            world.economy.accounts[account.id] = account.model_copy(update={"balance": group.count * price * 2})


def people_total(world):
    return sum(item.count for item in world.society.population.values())


def living_named(world):
    return sum(1 for item in world.society.characters.values() if item.death_day is None)


async def advance_month(engine, world):
    """Close one whole monthly cycle, whatever dated work sits in between."""
    target = (world.clock.absolute_day // 30 + 1) * 30
    for _ in range(60):
        if world.clock.absolute_day >= target:
            return
        await engine.step()
    raise AssertionError("the monthly cycle never closed")


async def test_sustained_deprivation_kills_and_a_fed_cycle_stops_it(tmp_path):
    world = famine_world()
    engine = MedievalSimulator(world)
    people, named = people_total(world), living_named(world)

    for _ in range(8):
        await advance_month(engine, world)
        if world.economy.needs[TARGET].health == 0:
            break
        assert people_total(world) == people, "privação ainda não sustentada não mata ninguém"
        assert not any(item.event_type == "deprivation_deaths" for item in world.events)
    assert world.economy.needs[TARGET].health == 0 and world.economy.needs[TARGET].missing_food > 0

    deaths = [item for item in world.events if item.event_type == "deprivation_deaths"]
    assert deaths, "o piso da saúde com déficit no mesmo ciclo custa vidas"
    events_by_id = {item.id: item for item in world.events}
    for item in deaths:
        assert all(delta.owner_kind == "population_group" for delta in item.deltas)
        assert any(events_by_id[link.cause_event_id].event_type == "subsistence_resolved"
                   for link in item.causal_links), "a perda cita o recibo de subsistência do ciclo"
        assert item.causal_payload["source_subsistence_event_id"]
        assert all("exposed" in details and "deficit" in details and "loss" in details
                   for details in item.causal_payload["losses_by_group"].values())
    lost = sum(int(delta.before) - int(delta.after) for item in deaths for delta in item.deltas)
    assert lost > 0 and people_total(world) == people - lost
    assert living_named(world) == named, "nenhum nomeado é consumido por uma perda agregada"

    # A fed cycle stops it: the accumulator rises again and nobody else dies.
    feed(world)
    recorded, alive = len(deaths), people_total(world)
    await advance_month(engine, world)
    assert world.economy.needs[TARGET].health > 0
    assert len([item for item in world.events if item.event_type == "deprivation_deaths"]) == recorded
    assert people_total(world) == alive

    path = tmp_path / "mortality.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_deprivation_uses_same_receipt_unmet_groups_and_rejects_missing_receipt():
    world = famine_world()
    need = world.economy.needs[TARGET]
    target_groups = [item for item in world.society.population.values()
                     if item.settlement_id == TARGET and world.society.available_count(item.id) > 0]
    unfed_group = max(target_groups, key=lambda item: item.count)
    fed_group = next(item for item in target_groups if item.id != unfed_group.id)
    stock = world.economy.stocks[need.stock_id]
    available = {item.id: world.society.available_count(item.id) for item in target_groups}
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": sum(available.values())}})
    price = world.economy.markets[TARGET].prices["food"]
    for item in target_groups:
        account = world.economy.accounts[f"household:{item.id}"]
        world.economy.accounts[account.id] = account.model_copy(
            update={"balance": 0 if item.id == unfed_group.id else available[item.id] * price})
    world.economy.needs[TARGET] = need.model_copy(update={"health": 0})
    consume_monthly(world)
    receipt = next(event for event in reversed(world.events)
                   if event.event_type == "subsistence_resolved"
                   and event.causal_payload["subsistence"]["settlement_id"] == TARGET)
    payload = receipt.causal_payload["subsistence"]
    assert {fed_group.id, unfed_group.id}.issubset(payload["household_group_ids"])
    assert fed_group.id not in payload["unmet_by_group"]
    assert payload["unmet_by_group"].get(unfed_group.id) == available[unfed_group.id]
    assert payload["unmet_by_group"].get(fed_group.id, 0) == 0
    removed = _deprivation_deaths(world)
    assert removed.get(unfed_group.id, 0) == available[unfed_group.id] * 20 // 1000
    assert all(delta.owner_id == unfed_group.id
               for event in world.events if event.event_type == "deprivation_deaths"
               for delta in event.deltas)
    assert world.society.population[fed_group.id].count == fed_group.count
    assert world.society.population[unfed_group.id].count == unfed_group.count - (
        available[unfed_group.id] * 20 // 1000)

    invalid = famine_world()
    invalid_need = invalid.economy.needs[TARGET]
    invalid.economy.needs[TARGET] = invalid_need.model_copy(update={"health": 0, "missing_food": 100})
    before = world_snapshot(invalid)
    with pytest.raises(ValueError, match="canonical subsistence receipt"):
        _deprivation_deaths(invalid)
    assert world_snapshot(invalid) == before


def _real_floor_receipt_world():
    world = famine_world()
    need = world.economy.needs[TARGET]
    groups = [item for item in world.society.population.values()
              if item.settlement_id == TARGET and world.society.available_count(item.id) > 0]
    unfed = max(groups, key=lambda item: item.count)
    available = {item.id: world.society.available_count(item.id) for item in groups}
    stock = world.economy.stocks[need.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": sum(available.values())}})
    price = world.economy.markets[TARGET].prices["food"]
    for item in groups:
        account = world.economy.accounts[f"household:{item.id}"]
        world.economy.accounts[account.id] = account.model_copy(
            update={"balance": 0 if item.id == unfed.id else available[item.id] * price})
    world.economy.needs[TARGET] = need.model_copy(update={"health": 0})
    consume_monthly(world)
    receipt = next(event for event in reversed(world.events)
                   if event.event_type == "subsistence_resolved"
                   and event.causal_payload["subsistence"]["settlement_id"] == TARGET)
    return world, receipt


def _real_zero_delta_receipt_world():
    world = famine_world()
    need = world.economy.needs[TARGET]
    groups = [item for item in world.society.population.values()
              if item.settlement_id == TARGET and world.society.available_count(item.id) > 0]
    unfed = max(groups, key=lambda item: item.count)
    available = {item.id: world.society.available_count(item.id) for item in groups}
    stock = world.economy.stocks[need.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": sum(available.values())}})
    price = world.economy.markets[TARGET].prices["food"]
    for item in groups:
        account = world.economy.accounts[f"household:{item.id}"]
        world.economy.accounts[account.id] = account.model_copy(
            update={"balance": 0 if item.id == unfed.id else available[item.id] * price})
    world.economy.needs[TARGET] = need.model_copy(
        update={"health": 0, "unrest": 1000, "missing_food": available[unfed.id]})
    consume_monthly(world)
    receipt = next(event for event in reversed(world.events)
                   if event.event_type == "subsistence_resolved"
                   and event.causal_payload["subsistence"]["settlement_id"] == TARGET)
    return world, receipt, unfed


def test_deprivation_accepts_deterministic_zero_delta_receipt_and_rejects_llm_origin():
    world, receipt, unfed = _real_zero_delta_receipt_world()
    assert receipt.fact_kind is FactKind.OCCURRENCE
    assert receipt.causal_origin is CausalOrigin.DETERMINISTIC
    assert not receipt.deltas
    counts_before = {group.id: group.count for group in world.society.population.values()}
    available_before = world.society.available_count(unfed.id)
    removed = _deprivation_deaths(world)
    expected = min(available_before, receipt.causal_payload["subsistence"]["unmet_by_group"][unfed.id]) * 20 // 1000
    assert removed.get(unfed.id, 0) == expected
    assert all(group.count == count for group_id, count in counts_before.items()
               for group in [world.society.population[group_id]]
               if group_id != unfed.id)
    death = next(event for event in world.events if event.event_type == "deprivation_deaths")
    assert death.causal_payload["source_subsistence_event_id"] == receipt.id

    invalid = _real_zero_delta_receipt_world()[0]
    invalid_receipt = next(event for event in reversed(invalid.events)
                           if event.event_type == "subsistence_resolved"
                           and event.causal_payload["subsistence"]["settlement_id"] == TARGET)
    index = invalid.events.index(invalid_receipt)
    invalid.events[index] = invalid_receipt.model_copy(update={"causal_origin": CausalOrigin.LLM_INTERPRETATION})
    before = world_snapshot(invalid)
    with pytest.raises(ValueError, match="canonical subsistence receipt"):
        _deprivation_deaths(invalid)
    assert world_snapshot(invalid) == before


@pytest.mark.parametrize("variant", ("missing", "stale", "wrong_settlement", "aggregate_mismatch"))
def test_deprivation_rejects_invalid_real_receipt_without_mutation(variant):
    world, receipt = _real_floor_receipt_world()
    need = world.economy.needs[TARGET]
    if variant == "missing":
        updated_payload = {}
        updated_need = need
    elif variant == "stale":
        updated_payload = receipt.causal_payload
        updated_need = need
    else:
        subsistence = dict(receipt.causal_payload["subsistence"])
        if variant == "wrong_settlement":
            subsistence["settlement_id"] = "other-settlement"
        else:
            subsistence["unmet_by_group"] = {
                **subsistence["unmet_by_group"],
                next(iter(subsistence["unmet_by_group"])): 1,
            }
        updated_payload = {"subsistence": subsistence}
        updated_need = need
    index = world.events.index(receipt)
    world.events[index] = receipt.model_copy(update={"causal_payload": updated_payload})
    world.economy.needs[TARGET] = updated_need
    if variant == "stale":
        world.clock = WorldClock(receipt.day + 30)
    before = (
        len(world.events),
        world.economy.needs[TARGET].health,
        world.economy.needs[TARGET].missing_food,
        world.economy.needs[TARGET].last_event_id,
        {group_id: group.count for group_id, group in world.society.population.items()},
    )
    with pytest.raises(ValueError):
        _deprivation_deaths(world)
    assert (
        len(world.events),
        world.economy.needs[TARGET].health,
        world.economy.needs[TARGET].missing_food,
        world.economy.needs[TARGET].last_event_id,
        {group_id: group.count for group_id, group in world.society.population.items()},
    ) == before


def test_deprivation_cap_preserves_named_and_reserved_people(monkeypatch):
    world, receipt = _real_floor_receipt_world()
    world.economy.needs[TARGET] = world.economy.needs[TARGET].model_copy(update={"health": 0})
    monkeypatch.setattr(type(world.society), "available_count", lambda self, group_id: 50)
    monkeypatch.setattr(mortality, "_living_named", lambda world, group_id: 50)
    before = world_snapshot(world)
    assert _deprivation_deaths(world) == {}
    assert world_snapshot(world) == before


async def test_a_lifetime_ends_and_releases_only_the_person():
    world, character = lone_world()
    world.config = world.config.model_copy(update={"ai_enabled": False})
    owner = garrison(world, character)
    option = next(item for item in detachment_command_options(world, owner)
                  if getattr(item, "character_id", None) == character.id)
    decision = record_event(world, "force_decided", "Nomeação de comandante.",
                            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                            causal_payload={"decision_source": {"kind": "api"}},
                            decision=option.decision())
    appoint_detachment_commander(world, owner, option.id, decision.id)
    assert "detachment:fixture" in world.society.detachment_commands

    world.society.characters[character.id] = world.society.characters[character.id].model_copy(
        update={"birth_day": world.clock.absolute_day - LIFESPAN_DAYS})
    group_id = character.population_group_id
    cohort = world.society.population[group_id].count
    column = world.society.detachments["detachment:fixture"]
    offices = {key: (item.institution_ref, item.holder_ref, item.scopes)
               for key, item in world.authority.offices.items()}
    places = {key: (item.administrator_id, item.occupier_id)
              for key, item in world.society.settlements.items()}

    engine = MedievalSimulator(world)
    await advance_month(engine, world)

    ended = next(item for item in world.events if item.event_type == "character_lifetime_ended")
    dead = world.society.characters[character.id]
    assert dead.death_day == ended.day and dead.population_group_id is None
    assert world.society.population[group_id].count == cohort - 1
    assert {(delta.owner_kind, delta.aspect) for delta in ended.deltas} == {
        ("character", "death_day"), ("population_group", "count")}

    # The command falls by the existing revocation; the column keeps everything.
    assert "detachment:fixture" not in world.society.detachment_commands
    released = next(item for item in world.events if item.event_type == "detachment_commander_released")
    assert all(delta.owner_kind == "detachment_command" for delta in released.deltas)
    current = world.society.detachments["detachment:fixture"]
    assert (current.owner_ref, current.count, current.location_id, current.provisions) == (
        column.owner_ref, column.count, column.location_id, column.provisions)
    assert {key: (item.institution_ref, item.holder_ref, item.scopes)
            for key, item in world.authority.offices.items()} == offices
    assert {key: (item.administrator_id, item.occupier_id)
            for key, item in world.society.settlements.items()} == places

    # A law, not a decision: no interpretation participates in either death.
    events_by_id = {item.id: item for item in world.events}
    for item in (ended, released):
        assert item.fact_kind == FactKind.STATE_TRANSITION
        assert all(events_by_id[link.cause_event_id].causal_origin.value != "llm_interpretation"
                   for link in item.causal_links)


def test_deterministic_copy_of_commander_affordance_does_not_appoint():
    world, character = lone_world()
    owner = garrison(world, character)
    option = next(item for item in detachment_command_options(world, owner)
                  if getattr(item, "character_id", None) == character.id)
    decision = record_event(world, "force_decided", "Payload de nomeação sem escolha do ator.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    before = world_snapshot(world)

    try:
        appoint_detachment_commander(world, owner, option.id, decision.id)
    except ValueError as exc:
        assert "current actor decision" in str(exc)
    else:
        raise AssertionError("deterministic payload appointed a commander")

    assert world_snapshot(world) == before
