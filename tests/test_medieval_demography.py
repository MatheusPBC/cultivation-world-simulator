"""Generations are an accounted law: fed and housed people grow, and only
whoever really remains ever becomes working age."""

from src.classes.economy.models import MoneyAccount
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.demography import BIRTH_PERMILLE, DEPENDENT, MATURE_OCCUPATION
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_mortality import advance_month, people_total

TARGET = "campomanso"


def refill(world):
    """Keep the prepared plenty real for as long as the scenario lasts.

    There is no automatic relief left to feed anyone for free, so being fed
    means every household also has the money to actually buy its ration.
    """
    for key, need in tuple(world.economy.needs.items()):
        stock = world.economy.stocks[need.stock_id]
        world.economy.stocks[stock.id] = stock.model_copy(
            update={"goods": {**stock.goods, "food": world.society.population_at(key) * 2}})
        price = world.economy.markets[key].prices["food"]
        for group in world.society.population.values():
            if group.settlement_id != key:
                continue
            account_id = f"household:{group.id}"
            account = world.economy.accounts.get(account_id)
            balance = group.count * price
            if account is None:
                # A newborn dependent cohort has no household account of its
                # own yet; without one it could never pay for its own ration
                # and would drag the whole settlement into a chronic, unpaid
                # shortfall that the old automatic relief used to hide.
                world.economy.accounts[account_id] = MoneyAccount(
                    id=account_id, owner_ref=EntityRef("population_group", group.id), balance=balance)
            else:
                world.economy.accounts[account.id] = account.model_copy(update={"balance": balance})


def fed_world():
    """Full granaries, healthy settlements and no producers to interfere."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    refill(world)
    for key, need in tuple(world.economy.needs.items()):
        world.economy.needs[key] = need.model_copy(update={"health": 1000})
    return world


def dependent_id(settlement_id, people):
    return f"pop:{settlement_id}:{people}:{DEPENDENT}"


def expected_births(world, settlement_id, people):
    base = sum(max(0, world.society.available_count(group.id))
               for group in world.society.population.values()
               if group.settlement_id == settlement_id and group.people == people
               and group.occupation != DEPENDENT)
    return base * BIRTH_PERMILLE // 1000


async def fed_month(engine, world):
    await advance_month(engine, world)
    refill(world)


async def reach_fed(engine, world, day):
    for _ in range(80):
        if world.clock.absolute_day >= day:
            return
        await engine.step()
        refill(world)
    raise AssertionError(f"world never reached day {day}")


async def test_a_fed_settlement_grows_into_dependents_until_housing_is_full(tmp_path):
    world = fed_world()
    engine = MedievalSimulator(world)
    people = people_total(world)
    peoples = sorted({group.people for group in world.society.population.values()
                      if group.settlement_id == TARGET})
    wanted = {people_id: expected_births(world, TARGET, people_id) for people_id in peoples}
    assert any(wanted.values()), "the prepared settlement has adults enough to grow"

    await fed_month(engine, world)

    births = [item for item in world.events if item.event_type == "settlement_births"]
    assert births, "plenty with room grows"
    events_by_id = {item.id: item for item in world.events}
    for item in births:
        assert item.fact_kind == FactKind.STATE_TRANSITION
        assert all(delta.owner_kind in {"population_group", "birth_cohort"} for delta in item.deltas)
        assert any(events_by_id[link.cause_event_id].event_type == "subsistence_resolved"
                   for link in item.causal_links)

    for people_id, count in wanted.items():
        if not count:
            continue
        group = world.society.population[dependent_id(TARGET, people_id)]
        assert group.count == count, "the curve is exactly the declared permille"
        # Present and eating, and employed by nothing.
        assert world.society.available_count(group.id) == count
        assert all(group.id not in payroll.workers_by_group
                   for payroll in world.economy.payrolls.values())
    assert people_total(world) == people + sum(item.count for item in world.society.birth_cohorts.values())
    local = [item for item in world.society.birth_cohorts.values() if item.settlement_id == TARGET]
    assert sum(item.count for item in local) == sum(wanted.values())
    assert all(world.agenda.get(item.id) is not None and item.stage == "pending" for item in local)

    # A full settlement grows no further: the housing fact is the whole limit.
    settlement = world.society.settlements[TARGET]
    world.society.settlements[TARGET] = settlement.model_copy(
        update={"housing_capacity": world.society.population_at(TARGET)})
    known = {item.id for item in local}
    await fed_month(engine, world)
    assert not [item for item in world.society.birth_cohorts.values()
                if item.settlement_id == TARGET and item.id not in known]

    path = tmp_path / "demography.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_maturity_is_dated_and_never_invents_people(monkeypatch):
    monkeypatch.setattr("src.classes.society.demography.MATURITY_DAYS", 60)
    monkeypatch.setattr("src.sim.medieval.demography.MATURITY_DAYS", 60)
    # A batch large enough for a partial loss to be a real number; the shipped
    # permille is what the other test measures.
    monkeypatch.setattr("src.sim.medieval.demography.BIRTH_PERMILLE", 50)
    world = fed_world()
    engine = MedievalSimulator(world)
    await fed_month(engine, world)

    cohort = max((item for item in world.society.birth_cohorts.values() if item.settlement_id == TARGET),
                 key=lambda item: (item.count, item.id))
    assert cohort.matures_day == cohort.born_day + 60
    assert cohort.count >= 3, "the prepared batch can lose people and still mature some"

    # Stop further growth without starving anyone: fed, but far from healthy.
    for key, need in tuple(world.economy.needs.items()):
        world.economy.needs[key] = need.model_copy(update={"health": 0})
    # A real loss before maturity: the batch is a promise, not a claim.
    lost = 2
    source = world.society.population[dependent_id(TARGET, cohort.people)]
    world.society.population[source.id] = source.model_copy(update={"count": cohort.count - lost})
    workers_id = f"pop:{TARGET}:{cohort.people}:{MATURE_OCCUPATION}"
    workers_before = world.society.population[workers_id].count if workers_id in world.society.population else 0
    people = people_total(world)

    await reach_fed(engine, world, cohort.matures_day)

    # Several batches come of age on the same day; take this one's own fact.
    matured = next(item for item in world.events if item.event_type == "generation_matured"
                   and any(delta.owner_kind == "birth_cohort" and delta.owner_id == cohort.id
                           for delta in item.deltas))
    assert matured.day == cohort.matures_day
    assert cohort.birth_event_id in {link.cause_event_id for link in matured.causal_links}
    assert world.society.birth_cohorts[cohort.id].stage == "matured"
    assert world.agenda.get(cohort.id) is None
    assert any(delta.owner_kind == "birth_cohort" and delta.aspect == "matured_count"
               and delta.before == str(cohort.count) and delta.after == str(cohort.count - lost)
               for delta in matured.deltas)
    assert any(delta.owner_kind == "population_group" and delta.owner_id == workers_id
               and int(delta.after) - int(delta.before) == cohort.count - lost
               for delta in matured.deltas)
    # The working cohort really holds them, whether it existed before or not.
    assert world.society.population[workers_id].count == workers_before + cohort.count - lost
    assert world.society.population[source.id].count == 0
    assert people_total(world) == people, "maturity moves people, it never creates them"
    assert all(delta.owner_kind in {"population_group", "birth_cohort"} for delta in matured.deltas)
    causes = {link.cause_event_id for link in matured.causal_links}
    assert all(item.causal_origin.value != "llm_interpretation"
               for item in world.events if item.id in causes)
