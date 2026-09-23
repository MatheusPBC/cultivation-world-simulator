"""Focused coverage for the bounded recurring local-payroll vertical."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import monthly_workforce
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.permanent_employment import (
    create_permanent_employment,
    permanent_employment_options,
    permanent_employment_adapters,
    record_permanent_employment_decision,
    review_permanent_employment_fallback,
    settle_permanent_employment,
)
from src.sim.medieval.persistence import load_world, save_world


def contracted_world():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    option = next(item for item in permanent_employment_options(world, employer)
                  if item.cohort_id == "pop:pontenegro:human:farmer")
    decision = record_permanent_employment_decision(world, employer, option.id)
    contract = create_permanent_employment(world, option.id, decision_event_id=decision.id)
    return world, contract


def next_month(world):
    world.clock = world.clock.advance(30)


def test_contract_is_explicit_local_and_its_first_payroll_is_conservative():
    world, contract = contracted_world()
    assert contract.work_site_id
    assert world.map.infrastructure_sites[contract.work_site_id].owner_ref == contract.employer_ref
    employer = world.economy.accounts[contract.account_id]
    household = world.economy.accounts[f"household:{contract.cohort_id}"]
    before_total = sum(item.balance for item in world.economy.accounts.values())
    before = employer.balance, household.balance

    next_month(world)
    available = monthly_workforce(world)
    settle_permanent_employment(world, available)

    payroll = world.economy.payrolls[contract.id]
    assert payroll.workers_by_group == {contract.cohort_id: contract.workforce_limit}
    assert payroll.gross == contract.workforce_limit * contract.wage_per_worker
    # The employer's treasury is also the taxing polity's account in this
    # fixture: gross leaves it, then the canonical income-tax owner returns
    # the collected tax to that same treasury.
    assert (world.economy.accounts[contract.account_id].balance,
            world.economy.accounts[f"household:{contract.cohort_id}"].balance) == (
                before[0] - payroll.gross + payroll.tax, before[1] + payroll.gross - payroll.tax)
    assert sum(item.balance for item in world.economy.accounts.values()) == before_total
    settled = next(item for item in world.events if item.event_type == "permanent_employment_settled")
    assert any(delta.owner_kind == "employment_contract" and delta.owner_id == contract.id
               and delta.aspect == "last_outcome" and delta.after == "paid" for delta in settled.deltas)
    assert available[contract.cohort_id] == world.society.available_count(contract.cohort_id) - contract.workforce_limit
    world.economy.validate(world)


def test_standing_employment_reuses_the_authored_facility_wage():
    world, contract = contracted_world()
    facility = next(item for item in world.economy.facilities.values()
                    if item.site_id == contract.work_site_id
                    and world.economy.recipes[item.recipe_id].occupation == contract.occupation)
    assert contract.wage_per_worker == facility.wage_per_worker


def test_material_pressure_expands_the_engine_owned_employment_offer():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    normal = next(item for item in permanent_employment_options(world, employer)
                  if item.cohort_id == "pop:pontenegro:human:farmer")
    needs = world.economy.needs[normal.settlement_id]
    world.economy.needs[needs.id] = needs.model_copy(update={"missing_food": 1})

    pressured = next(item for item in permanent_employment_options(world, employer)
                     if item.cohort_id == normal.cohort_id and item.work_site_id == normal.work_site_id)

    assert normal.workforce_limit == world.society.population[normal.cohort_id].count // 5
    assert pressured.workforce_limit == world.society.population[normal.cohort_id].count // 2


def test_new_standing_employment_cannot_overcommit_existing_monthly_payroll():
    world, contract = contracted_world()
    employer = EntityRef("polity", "auren")
    candidate = next(option for option in permanent_employment_options(world, employer)
                     if option.cohort_id != contract.cohort_id)
    account = world.economy.accounts[contract.account_id]
    committed = contract.workforce_limit * contract.wage_per_worker
    candidate_cost = candidate.workforce_limit * candidate.wage_per_worker
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": committed + candidate_cost - 1})

    assert not any(option.cohort_id == candidate.cohort_id
                   for option in permanent_employment_options(world, employer))


def test_food_labor_shortfall_does_not_offer_a_reserving_farmer_contract():
    from src.sim.medieval.economy import monthly_workforce, produce_monthly
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    produce_monthly(world, monthly_workforce(world))
    employer = EntityRef("polity", "escarlia")

    assert any(event.event_type == "production_limited"
               and any(delta.aspect == "labor_shortfall" for delta in event.deltas)
               for event in world.events)
    assert not any(option.settlement_id == "ferroalto" and option.occupation == "farmer"
                   for option in permanent_employment_options(world, employer))


@pytest.mark.parametrize(("available_workers", "balance", "outcome"), [
    (0, None, "unpaid_labor"),
    (None, 0, "unpaid_funds"),
])
def test_contract_records_nonpayment_without_inventing_wage(available_workers, balance, outcome):
    world, contract = contracted_world()
    next_month(world)
    available = monthly_workforce(world)
    if available_workers is not None:
        available[contract.cohort_id] = available_workers
    if balance is not None:
        account = world.economy.accounts[contract.account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": balance})
    before = {item.id: item.balance for item in world.economy.accounts.values()}

    settle_permanent_employment(world, available)

    current = world.economy.employment_contracts[contract.id]
    assert current.last_outcome == outcome
    assert contract.id not in world.economy.payrolls
    assert {item.id: item.balance for item in world.economy.accounts.values()} == before
    receipt = next(item for item in world.events if item.event_type == "permanent_employment_unpaid")
    assert any(delta.owner_id == contract.id and delta.aspect == "last_outcome" and delta.after == outcome
               for delta in receipt.deltas)
    world.economy.validate(world)


def test_contract_and_creation_decision_round_trip_in_current_save_schema(tmp_path):
    world, contract = contracted_world()
    path = tmp_path / "employment.mws"

    save_world(world, path)
    resumed = load_world(path)

    assert resumed.economy.employment_contracts[contract.id] == contract
    assert any(item.id == contract.decision_event_id and item.decision["selected_affordance_id"] == contract.selected_affordance_id
               for item in resumed.events)
    resumed.economy.validate(resumed)


def test_creation_rejects_a_stale_affordance_without_creating_a_contract():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    option = permanent_employment_options(world, employer)[0]
    decision = record_permanent_employment_decision(world, employer, option.id)
    account = world.economy.accounts[option.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    with pytest.raises(ValueError, match="stale or unknown"):
        create_permanent_employment(world, option.id, decision_event_id=decision.id)
    assert not world.economy.employment_contracts


def test_employment_turn_exposes_public_pressure_without_private_terms():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    options = permanent_employment_options(world, employer)
    situation = permanent_employment_adapters()[0].situation_fn(world, employer, options)

    assert situation["you_are"] == employer.to_dict()
    assert situation["employment_options"]
    first = situation["employment_options"][0]
    assert {"id", "settlement_id", "cohort_id", "occupation", "work_site_id",
            "workforce_limit", "wage_per_worker", "pressure"} <= set(first)
    # The provider gets public pressure and the engine-bounded offer, never
    # the account/stock IDs or their balances that the owner revalidates.
    assert "account_id" not in first
    assert "stock_id" not in first
    assert "balance" not in repr(situation)


def test_employment_site_is_bounded_by_its_authored_facility_occupation():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    options = permanent_employment_options(world, employer)
    assert options
    for option in options:
        facilities = [facility for facility in world.economy.facilities.values()
                      if facility.site_id == option.work_site_id]
        if facilities:
            occupations = {world.economy.recipes[facility.recipe_id].occupation
                           for facility in facilities}
            assert option.occupation in occupations


def test_offline_employment_fallback_uses_current_pressure_and_material_owner():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    refresh_reports(world)
    options = tuple(item for item in permanent_employment_options(world, employer)
                    if item.settlement_id == "campomanso")
    option = options[0]
    report = world.knowledge.settlement_report(employer, option.settlement_id)
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 4})

    contracts = review_permanent_employment_fallback(world)

    assert contracts
    contract = next(item for item in contracts if item.employer_ref == employer)
    assert contract.cohort_id in {item.cohort_id for item in options}
    decision = next(item for item in world.events if item.id == contract.decision_event_id)
    assert decision.fact_kind.value == "decision"
    assert decision.decision["selected_affordance_id"] in {item.id for item in options}
    assert any(item.event_type == "permanent_employment_created" for item in world.events)
    world.economy.validate(world)


def test_offline_employment_fallback_prefers_food_production_at_equal_pressure(monkeypatch):
    import src.sim.medieval.permanent_employment as employment

    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    refresh_reports(world)
    report = world.knowledge.settlement_report(employer, "campomanso")
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 20})
    options = (
        SimpleNamespace(id="employment:artisan", employer_ref=employer,
                        settlement_id="campomanso", occupation="artisan"),
        SimpleNamespace(id="employment:farmer", employer_ref=employer,
                        settlement_id="campomanso", occupation="farmer"),
    )
    chosen = []
    monkeypatch.setattr(employment, "permanent_employment_options", lambda _world, _actor: options)
    monkeypatch.setattr(employment, "record_permanent_employment_decision",
                        lambda _world, _actor, option_id: chosen.append(option_id)
                        or SimpleNamespace(id="decision:employment"))
    monkeypatch.setattr(employment, "create_permanent_employment",
                        lambda _world, option_id, *, decision_event_id: option_id)

    employment.review_permanent_employment_fallback(world)

    assert chosen == ["employment:farmer"]


def test_persisted_contract_rejects_an_employer_site_outside_the_cohort_settlement():
    world, contract = contracted_world()
    site = world.map.infrastructure_sites[contract.work_site_id]
    settlement = world.society.settlements[contract.settlement_id]
    remote_region = next(region_id for region_id in site.region_ids if region_id != settlement.region_id) \
        if len(site.region_ids) > 1 else next(
            region.id for region in world.map.regions.values() if region.id != settlement.region_id)
    world.map.infrastructure_sites[site.id] = replace(site, region_ids=(remote_region,))

    with pytest.raises(ValueError, match="local employer site"):
        world.economy.validate(world)
