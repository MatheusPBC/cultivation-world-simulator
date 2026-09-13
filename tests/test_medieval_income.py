"""Production pays real cohorts from existing employer funds, once per month."""

import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.economy import produce_monthly
from src.sim.medieval.persistence import world_snapshot, save_world, load_world
from src.systems.time import WorldClock

FARM = "works:campos-do-lume"
TREASURY = "treasury:auren"


def prepared_farm(cash=50):
    world = create_medieval_world(73)
    facility = world.economy.facilities[FARM]
    assert "wage_per_worker" in type(facility).model_fields, "paid production terms missing"
    world.economy.facilities = {FARM: facility.model_copy(update={"max_batches": 2, "wage_per_worker": 2})}
    account = world.economy.accounts[TREASURY]
    world.economy.accounts[TREASURY] = account.model_copy(update={"balance": cash})
    world.strategy.objectives.clear()
    return world


def money(world):
    return sum(a.balance for a in world.economy.accounts.values())


def household_money(world):
    return sum(a.balance for a in world.economy.accounts.values() if a.owner_ref.kind == "population_group")


def test_initial_households_have_accounts_without_creating_money_or_named_double_pay():
    world = create_medieval_world(73)
    accounts = [a for a in world.economy.accounts.values() if a.owner_ref.kind == "population_group"]
    assert {a.owner_ref.id for a in accounts} == set(world.society.population)
    assert len(accounts) == len(world.society.population)
    assert household_money(world) == 0
    assert money(world) == 76000


def test_production_phase_pays_actual_work_and_taxes_only_that_income():
    world = prepared_farm()
    initial = money(world)
    world.clock = WorldClock(30)
    produce_monthly(world)
    assert world.clock.absolute_day == 30
    assert world.economy.facilities[FARM].last_batches == 2
    assert world.economy.accounts[TREASURY].balance == 14  # 50 - 40 + 4
    assert household_money(world) == 36
    assert money(world) == initial
    payroll = world.economy.payrolls[FARM]
    assert (payroll.day, payroll.gross, payroll.tax) == (30, 40, 4)
    assert sum(payroll.workers_by_group.values()) == 20
    assert all(world.society.population[g].occupation == "farmer" for g in payroll.workers_by_group)
    wage_event = next(e for e in world.events if e.event_type == "wages_paid")
    tax_event = next(e for e in world.events if e.event_type == "income_tax_collected")
    assert wage_event.id in {link.cause_event_id for link in tax_event.causal_links}
    world.clock = WorldClock(60)
    produce_monthly(world)
    # Isolated production, without consumer spending:14 cannot fund a20-unit batch.
    assert world.economy.facilities[FARM].last_batches == 0
    assert household_money(world) == 36
    assert money(world) == initial


@pytest.mark.parametrize("cash,batches,net", [(19, 0, 0), (20, 1, 18)])
def test_gross_payroll_budget_limits_batches_without_creating_credit(cash, batches, net):
    world = prepared_farm(cash)
    initial = money(world)
    world.clock = WorldClock(30)
    produce_monthly(world)
    assert world.economy.facilities[FARM].last_batches == batches
    assert "payroll_funds" in world.economy.facilities[FARM].last_limitations
    assert household_money(world) == net
    assert money(world) == initial


def tax_decision(world, rate, actor="auren"):
    from src.classes.event import FactKind
    from src.sim.medieval.events import record_event
    return record_event(world, "tax_decided", "Alterar imposto sobre a renda.", fact_kind=FactKind.DECISION,
                        decision={"action": "set_income_tax", "actor_ref": {"kind": "polity", "id": actor},
                                  "polity_id": "auren", "income_rate": rate})


async def test_tax_change_requires_decision_and_links_future_income_to_policy(tmp_path):
    import src.sim.medieval.labor as labor
    world = prepared_farm()
    decision = tax_decision(world, 250)
    assert hasattr(labor, "set_income_tax"), "tax policy executor missing"
    labor.set_income_tax(world, "auren", 250, decision_event_id=decision.id)
    changed = world.authority.tax_policies["auren"].last_event_id
    assert changed != decision.id
    path = tmp_path / "income.mws"
    save_world(world, path)
    resumed = load_world(path)
    await MedievalSimulator(world).step()
    await MedievalSimulator(resumed).step()
    assert world.economy.payrolls[FARM].gross == 40
    assert world.economy.payrolls[FARM].tax == 10
    assert household_money(world) == 2  # net30 buys7rations at4
    assert world.economy.accounts[TREASURY].balance == 48
    assert world_snapshot(world) == world_snapshot(resumed)
    assert world.events == resumed.events
    tax = next(e for e in world.events if e.event_type == "income_tax_collected")
    assert changed in {link.cause_event_id for link in tax.causal_links}
    with pytest.raises(ValueError, match="executed"):
        labor.set_income_tax(resumed, "auren", 250, decision_event_id=decision.id)


@pytest.mark.parametrize("case", ["foreign_actor", "revoked", "invalid_rate"])
def test_invalid_tax_policy_change_has_no_effect(case):
    import src.sim.medieval.labor as labor
    world = prepared_farm()
    rate = 1001 if case == "invalid_rate" else 250
    decision = tax_decision(world, rate, "valedouro" if case == "foreign_actor" else "auren")
    if case == "revoked":
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("trade", "supply")})
    assert hasattr(labor, "set_income_tax"), "tax policy executor missing"
    before, history = world_snapshot(world), list(world.events)
    with pytest.raises(ValueError):
        labor.set_income_tax(world, "auren", rate, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    assert world.events == history


@pytest.mark.parametrize("disabled", ["site", "employer"])
def test_unavailable_production_does_not_pay_or_tax(disabled):
    world = prepared_farm()
    if disabled == "site":
        world.map.infrastructure_sites[world.economy.facilities[FARM].site_id].update_runtime(enabled=False)
    else:
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("supply", "taxation")})
    before = money(world)
    world.clock = WorldClock(30)
    produce_monthly(world)
    assert world.economy.facilities[FARM].last_batches == 0
    assert household_money(world) == 0
    assert money(world) == before
    assert not any(e.event_type in {"wages_paid", "income_tax_collected"} for e in world.events)


def test_tax_goes_to_administrator_not_occupier_and_requires_tax_mandate():
    world = prepared_farm()
    settlement = world.society.settlements["campomanso"]
    world.society.settlements[settlement.id] = settlement.model_copy(update={"occupier_id": "valedouro"})
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(update={"scopes": ("supply", "trade")})
    before = world.economy.accounts["treasury:valedouro"].balance
    world.clock = WorldClock(30)
    produce_monthly(world)
    assert household_money(world) == 40
    assert world.economy.accounts[TREASURY].balance == 10
    assert world.economy.accounts["treasury:valedouro"].balance == before
    assert world.economy.payrolls[FARM].tax == 0


def test_payroll_cannot_repeat_on_same_day_after_save_load(tmp_path):
    world = prepared_farm(500)
    world.clock = WorldClock(30)
    produce_monthly(world)
    path = tmp_path / "paid.mws"
    save_world(world, path)
    resumed = load_world(path)
    before = world_snapshot(resumed)
    history = list(resumed.events)
    produce_monthly(resumed)
    assert world_snapshot(resumed) == before
    assert resumed.events == history


async def test_failed_salary_month_keeps_money_people_history_and_save(tmp_path, monkeypatch):
    world = prepared_farm()
    path = tmp_path / "rollback.mws"
    save_world(world, path)
    before, saved = world_snapshot(world), path.read_bytes()
    def fail(*args):
        raise OSError("disk failure")
    monkeypatch.setattr("src.sim.medieval.engine.save_world", fail)
    with pytest.raises(OSError):
        await MedievalSimulator(world, save_path=path).step()
    assert world_snapshot(world) == before
    assert world.events == []
    assert path.read_bytes() == saved


async def test_payroll_provenance_cannot_be_replaced_with_an_unrelated_event(tmp_path):
    world = prepared_farm()
    await MedievalSimulator(world).step()
    path = tmp_path / "payroll.mws"
    save_world(world, path)
    saved = path.read_bytes()
    payroll = world.economy.payrolls[FARM]
    world.economy.payrolls[FARM] = payroll.model_copy(update={"last_event_id": world.events[-1].id})
    with pytest.raises(ValueError, match="payroll"):
        save_world(world, path)
    assert path.read_bytes() == saved


def test_competing_facilities_cannot_pay_the_same_workers_twice():
    world = prepared_farm()
    remaining = 20
    for group in list(world.society.population.values()):
        if group.settlement_id != "campomanso" or group.occupation != "farmer":
            continue
        keep = min(remaining, group.count)
        remaining -= keep
        moved = group.count - keep
        if moved:
            named = tuple(c.id for c in world.society.characters.values() if c.population_group_id == group.id)
            world.society.transfer_people(group.id, "campomanso", "soldier", moved, named)
    facility = world.economy.facilities[FARM]
    other = facility.model_copy(update={"id": "works:second"})
    world.economy.facilities[other.id] = other
    world.clock = WorldClock(30)
    produce_monthly(world)
    assert sum(p.gross for p in world.economy.payrolls.values()) == 40
    assert sum(sum(p.workers_by_group.values()) for p in world.economy.payrolls.values()) == 20
    assert household_money(world) == 36
    assert world.economy.facilities[other.id].last_batches == 0


def test_previous_experimental_save_is_rejected_without_overwrite(tmp_path):
    import sqlite3
    world = create_medieval_world(73)
    path = tmp_path / "old.mws"
    save_world(world, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=5")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    with pytest.raises(ValueError, match="Unsupported"):
        save_world(world, path)
    assert path.read_bytes() == before
