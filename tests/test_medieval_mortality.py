"""Deprivation and age are material laws: nobody chooses them, nothing is drawn."""

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.force_command import appoint_detachment_commander, detachment_command_options
from src.sim.medieval.mortality import LIFESPAN_DAYS
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
        ration = world.society.population_at(key) * 2
        world.economy.stocks[stock.id] = stock.model_copy(
            update={"goods": {**stock.goods, "food": ration}})
        price = world.economy.markets[key].prices["food"]
        for group in world.society.population.values():
            if group.settlement_id != key:
                continue
            account = world.economy.accounts[f"household:{group.id}"]
            world.economy.accounts[account.id] = account.model_copy(update={"balance": group.count * price})


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


async def test_a_lifetime_ends_and_releases_only_the_person():
    world, character = lone_world()
    world.config = world.config.model_copy(update={"ai_enabled": False})
    owner = garrison(world, character)
    option = next(item for item in detachment_command_options(world, owner)
                  if getattr(item, "character_id", None) == character.id)
    decision = record_event(world, "force_decided", "Nomeação de comandante.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
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
