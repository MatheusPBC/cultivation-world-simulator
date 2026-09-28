"""Focused tests for the causal family-to-polity loan vertical."""

from copy import deepcopy

import pytest

from src.classes.economy import EconomyState
from src.classes.governance import KnowledgeState
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import monthly_workforce, produce_monthly
from src.sim.medieval.family_loans import (
    LEND_ACTION,
    REPAY_ACTION,
    REQUEST_ACTION,
    family_loan_options,
    family_loan_repayment_options,
    family_loan_request_options,
    lend_to_polity,
    record_family_loan_decision,
    repay_family_loan,
    request_family_loan,
    _context as family_loan_context,
)
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.permanent_employment import (
    create_permanent_employment,
    permanent_employment_options,
    record_permanent_employment_decision,
    settle_permanent_employment,
)
from src.sim.medieval.persistence import load_world, save_world


def unpaid_payroll_world():
    world = create_medieval_world(73)
    borrower = EntityRef("polity", "auren")
    offer = next(
        item
        for item in permanent_employment_options(world, borrower)
        if item.cohort_id == "pop:pontenegro:human:farmer"
    )
    decision = record_permanent_employment_decision(
        world, borrower, offer.id, decision_source={"kind": "api"}
    )
    contract = create_permanent_employment(
        world, offer.id, decision_event_id=decision.id
    )
    world.clock = world.clock.advance(30)
    treasury = world.economy.accounts[contract.account_id]
    world.economy.accounts[treasury.id] = treasury.model_copy(update={"balance": 0})
    settle_permanent_employment(world, monthly_workforce(world))

    group = world.society.population[contract.cohort_id]
    household = world.economy.accounts[f"household:{group.id}"]
    food_reserve = (
        group.count * world.economy.markets[group.settlement_id].prices["food"]
    )
    world.economy.accounts[household.id] = household.model_copy(
        update={"balance": food_reserve + 100}
    )
    refresh_reports(world)
    return world, borrower, contract, group


def test_local_family_can_fund_and_repay_only_after_a_real_payroll_request(tmp_path):
    world, borrower, contract, group = unpaid_payroll_world()
    request_option = family_loan_request_options(world, borrower)[0]
    request_decision = record_family_loan_decision(
        world,
        borrower,
        request_option.id,
        action=REQUEST_ACTION,
        decision_source={"kind": "api"},
    )
    request = request_family_loan(
        world, borrower, request_option.id, request_decision.id
    )

    lender = EntityRef("population_group", group.id)
    other_locality = next(
        candidate
        for candidate in world.society.population.values()
        if candidate.settlement_id != group.settlement_id
    )
    assert (
        family_loan_options(world, EntityRef("population_group", other_locality.id))
        == ()
    )
    from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters

    assert borrower in monthly_actors(world)
    assert lender in monthly_actors(world)
    assert {"family_loan_request", "family_loan_lend", "family_loan_repayment"} <= {
        adapter.name for adapter in monthly_adapters()
    }
    offers = family_loan_options(world, lender)
    assert offers
    assert max(item.principal for item in offers) == 100
    lender_decision = record_family_loan_decision(
        world, lender, offers[0].id, action=LEND_ACTION, decision_source={"kind": "api"}
    )
    before_total = sum(account.balance for account in world.economy.accounts.values())
    loan = lend_to_polity(world, lender, offers[0].id, lender_decision.id)

    assert loan.request_id == request.id
    assert loan.principal == offers[0].principal
    assert loan.due_day == loan.created_day + 180
    assert world.economy.family_loan_requests[request.id].status == "partially_funded"
    assert (
        sum(account.balance for account in world.economy.accounts.values())
        == before_total
    )
    funded = world.event_index()[loan.funded_event_id]
    assert (
        request.source_event_id
        == world.economy.employment_contracts[contract.id].last_event_id
    )
    assert request.source_event_id in {
        link.cause_event_id
        for link in world.event_index()[request.request_event_id].causal_links
    }
    assert lender_decision.id in {link.cause_event_id for link in funded.causal_links}
    assert not family_loan_repayment_options(world, borrower)

    world.clock = world.clock.advance(loan.due_day - world.clock.absolute_day)
    repayment = family_loan_repayment_options(world, borrower)
    assert [item.loan_id for item in repayment] == [loan.id]
    repayment_decision = record_family_loan_decision(
        world,
        borrower,
        repayment[0].id,
        action=REPAY_ACTION,
        decision_source={"kind": "api"},
    )
    receipt = repay_family_loan(world, borrower, repayment[0].id, repayment_decision.id)

    assert receipt.event_type == "family_loan_repaid"
    assert world.economy.family_loans[loan.id].status == "repaid"
    assert (
        sum(account.balance for account in world.economy.accounts.values())
        == before_total
    )
    world.economy.validate(world)
    world.knowledge.validate(world)

    path = tmp_path / "family-loan.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.economy.family_loans[loan.id] == world.economy.family_loans[loan.id]
    assert (
        loaded.knowledge.family_loan_notices[loan.lender_notice_id].status == "repaid"
    )


def test_multiple_households_can_fund_a_request_without_overfunding(tmp_path):
    world, borrower, _, first_group = unpaid_payroll_world()
    request_option = family_loan_request_options(world, borrower)[0]
    request_decision = record_family_loan_decision(
        world,
        borrower,
        request_option.id,
        action=REQUEST_ACTION,
        decision_source={"kind": "api"},
    )
    request = request_family_loan(
        world, borrower, request_option.id, request_decision.id
    )

    second_group = world.society.population["pop:pontenegro:dwarf:farmer"]
    second_account = world.economy.accounts[f"household:{second_group.id}"]
    reserve = (
        second_group.count
        * world.economy.markets[second_group.settlement_id].prices["food"]
    )
    world.economy.accounts[second_account.id] = second_account.model_copy(
        update={"balance": reserve + 200}
    )
    first_lender = EntityRef("population_group", first_group.id)
    second_lender = EntityRef("population_group", second_group.id)

    stale_second_offer = max(
        family_loan_options(world, second_lender), key=lambda item: item.principal
    )
    stale_second_decision = record_family_loan_decision(
        world,
        second_lender,
        stale_second_offer.id,
        action=LEND_ACTION,
        decision_source={"kind": "api"},
    )
    first_options = family_loan_options(world, first_lender)
    first_offer = next(item for item in first_options if item.principal == 100)
    first_decision = record_family_loan_decision(
        world,
        first_lender,
        first_offer.id,
        action=LEND_ACTION,
        decision_source={"kind": "api"},
    )
    no_loan_control = deepcopy(world)
    before_total = sum(account.balance for account in world.economy.accounts.values())
    first_loan = lend_to_polity(world, first_lender, first_offer.id, first_decision.id)

    current_request = world.economy.family_loan_requests[request.id]
    assert current_request.status == "partially_funded"
    assert current_request.family_loan_ids == (first_loan.id,)
    assert not family_loan_options(world, first_lender)
    unchanged_balances = {
        account_id: account.balance
        for account_id, account in world.economy.accounts.items()
    }
    unchanged_event_count = len(world.events)
    with pytest.raises(ValueError, match="stale or unknown"):
        lend_to_polity(
            world, second_lender, stale_second_offer.id, stale_second_decision.id
        )
    assert len(world.events) == unchanged_event_count
    assert {
        account_id: account.balance
        for account_id, account in world.economy.accounts.items()
    } == unchanged_balances

    second_options = family_loan_options(world, second_lender)
    assert (
        max(item.principal for item in second_options)
        == request.principal - first_loan.principal
    )
    second_notice = next(
        notice
        for notice in world.knowledge.family_loan_notices.values()
        if notice.request_id == request.id and notice.recipient_ref == second_lender
    )
    assert second_notice.status == "requested"

    second_offer = max(second_options, key=lambda item: item.principal)
    second_decision = record_family_loan_decision(
        world,
        second_lender,
        second_offer.id,
        action=LEND_ACTION,
        decision_source={"kind": "api"},
    )
    second_loan = lend_to_polity(
        world, second_lender, second_offer.id, second_decision.id
    )

    current_request = world.economy.family_loan_requests[request.id]
    assert current_request.status == "funded"
    assert set(current_request.family_loan_ids) == {first_loan.id, second_loan.id}
    assert first_loan.principal + second_loan.principal == request.principal
    assert not family_loan_options(world, second_lender)
    assert (
        sum(account.balance for account in world.economy.accounts.values())
        == before_total
    )
    world.economy.validate(world)
    world.knowledge.validate(world)

    path = tmp_path / "family-loan-multiple-lenders.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.economy.family_loan_requests[request.id] == current_request
    assert set(loaded.economy.family_loan_requests[request.id].family_loan_ids) == {
        first_loan.id,
        second_loan.id,
    }
    old_economy = loaded.economy.to_dict()
    old_economy["schema_version"] = 18
    with pytest.raises(ValueError, match="invalid economy schema"):
        EconomyState.from_dict(old_economy)
    old_knowledge = loaded.knowledge.to_dict()
    old_knowledge["schema_version"] = 9
    with pytest.raises(ValueError, match="invalid governance state schema"):
        KnowledgeState.from_dict(old_knowledge)

    household_id = f"household:{first_group.id}"
    household_before_payroll = world.economy.accounts[household_id].balance
    world.clock = world.clock.advance(30)
    no_loan_control.clock = no_loan_control.clock.advance(30)
    settle_permanent_employment(world, monthly_workforce(world))
    settle_permanent_employment(no_loan_control, monthly_workforce(no_loan_control))

    assert (
        world.economy.employment_contracts["employment:" + first_group.id].last_outcome
        == "paid"
    )
    assert (
        world.economy.payrolls["employment:" + first_group.id].gross
        == request.principal
    )
    assert world.economy.accounts[household_id].balance > household_before_payroll
    assert (
        no_loan_control.economy.employment_contracts[
            "employment:" + first_group.id
        ].last_outcome
        == "unpaid_funds"
    )
    assert "employment:" + first_group.id not in no_loan_control.economy.payrolls
    world.economy.validate(world)
    world.knowledge.validate(world)
    no_loan_control.economy.validate(no_loan_control)
    no_loan_control.knowledge.validate(no_loan_control)


def test_request_affordance_requires_current_unpaid_funds_receipt():
    world, borrower, contract, _ = unpaid_payroll_world()
    assert family_loan_request_options(world, borrower)
    current = world.economy.accounts[contract.account_id]
    world.economy.accounts[current.id] = current.model_copy(
        update={"balance": contract.staffing_target * contract.wage_per_worker}
    )
    assert family_loan_request_options(world, borrower) == ()


def test_stale_offer_rejects_without_partial_transfer():
    world, borrower, _, group = unpaid_payroll_world()
    request_option = family_loan_request_options(world, borrower)[0]
    request_decision = record_family_loan_decision(
        world,
        borrower,
        request_option.id,
        action=REQUEST_ACTION,
        decision_source={"kind": "api"},
    )
    request = request_family_loan(
        world, borrower, request_option.id, request_decision.id
    )
    lender = EntityRef("population_group", group.id)
    offer = family_loan_options(world, lender)[0]
    decision = record_family_loan_decision(
        world, lender, offer.id, action=LEND_ACTION, decision_source={"kind": "api"}
    )
    household = world.economy.accounts[f"household:{group.id}"]
    world.economy.accounts[household.id] = household.model_copy(update={"balance": 0})
    before = {item.id: item.balance for item in world.economy.accounts.values()}

    with pytest.raises(ValueError, match="stale or unknown"):
        lend_to_polity(world, lender, offer.id, decision.id)

    assert {item.id: item.balance for item in world.economy.accounts.values()} == before
    assert not world.economy.family_loans
    assert world.economy.family_loan_requests[request.id].status == "open"


def test_family_credit_can_fund_one_food_batch_without_producing_automatically():
    world = create_medieval_world(73)
    borrower = EntityRef("polity", "auren")
    facility = next(
        item for item in world.economy.facilities.values()
        if world.economy.stocks[item.stock_id].owner_ref == borrower
        and "food" in world.economy.recipes[item.recipe_id].outputs
    )
    account = world.economy.accounts[facility.payroll_account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    produce_monthly(world, monthly_workforce(world))
    facility = world.economy.facilities[facility.id]
    source = world.event_index()[facility.last_event_id]
    assert source.event_type == "production_limited"
    assert source.causal_payload["production"]["limitations"] == ["payroll_funds"]

    option = next(
        item for item in family_loan_request_options(world, borrower)
        if item.production_facility_id == facility.id
    )
    recipe = world.economy.recipes[facility.recipe_id]
    assert option.principal == recipe.workers * facility.wage_per_worker
    assert option.purpose == "food_production_payroll"

    decision = record_family_loan_decision(
        world, borrower, option.id, action=REQUEST_ACTION,
        decision_source={"kind": "api"},
    )
    request = request_family_loan(world, borrower, option.id, decision.id)
    assert request.source_event_id == source.id
    assert request.production_facility_id == facility.id
    assert request.employment_contract_id is None

    lender_group = next(
        group for group in world.society.population.values()
        if group.settlement_id == option.settlement_id
        and world.society.available_count(group.id) > 0
    )
    lender = EntityRef("population_group", lender_group.id)
    household = world.economy.accounts[f"household:{lender_group.id}"]
    reserve = lender_group.count * world.economy.markets[option.settlement_id].prices["food"]
    world.economy.accounts[household.id] = household.model_copy(
        update={"balance": reserve + option.principal}
    )
    refresh_reports(world)
    offer = next(item for item in family_loan_options(world, lender)
                 if item.request_id == request.id)
    known_request = next(
        item for item in family_loan_context(world, lender, (offer,))["known_requests"]
        if item["request_id"] == request.id
    )
    assert known_request["purpose"] == "food_production_payroll"
    assert known_request["disbursement_scope"] == "borrower_account_fungible_balance"
    assert known_request["earmarked_for_request"] is False
    assert known_request["outcome_guaranteed"] is False
    assert "production_facility_id" not in known_request
    loan_decision = record_family_loan_decision(
        world, lender, offer.id, action=LEND_ACTION,
        decision_source={"kind": "api"},
    )
    stock = world.economy.stocks[facility.stock_id]
    food_before = stock.goods.get("food", 0)
    money_before = sum(item.balance for item in world.economy.accounts.values())
    loan = lend_to_polity(world, lender, offer.id, loan_decision.id)

    assert loan.principal == option.principal
    assert sum(item.balance for item in world.economy.accounts.values()) == money_before
    assert world.economy.stocks[facility.stock_id].goods.get("food", 0) == food_before
    assert world.economy.facilities[facility.id].last_batches == 0
    world.economy.validate(world)
    world.knowledge.validate(world)
