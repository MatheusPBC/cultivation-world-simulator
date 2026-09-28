"""Focused coverage for the bounded recurring local-payroll vertical."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import monthly_workforce
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.permanent_employment import (
    create_permanent_employment,
    employment_staffing_options,
    employment_staffing_adapters,
    permanent_employment_options,
    permanent_employment_adapters,
    record_permanent_employment_decision,
    record_employment_staffing_decision,
    review_permanent_employment_fallback,
    set_employment_staffing,
    settle_permanent_employment,
)
from src.sim.medieval.persistence import load_world, save_world


def contracted_world():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    option = next(item for item in permanent_employment_options(world, employer)
                  if item.cohort_id == "pop:pontenegro:human:farmer")
    decision = record_permanent_employment_decision(world, employer, option.id,
                                                   decision_source={"kind": "api"})
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


def test_staffing_context_sums_shared_account_contracts_and_links_their_sources():
    from src.sim.medieval.permanent_employment import (
        EmploymentStaffingOption, _staffing_causes, _staffing_context,
    )

    world, contract = contracted_world()
    employer = contract.employer_ref
    second_offer = next(option for option in permanent_employment_options(world, employer)
                        if option.account_id == contract.account_id
                        and option.cohort_id != contract.cohort_id)
    second_decision = record_permanent_employment_decision(
        world, employer, second_offer.id, decision_source={"kind": "api"})
    second_contract = create_permanent_employment(
        world, second_offer.id, decision_event_id=second_decision.id)
    option = EmploymentStaffingOption(
        id="fixture-staffing-summary", employer_ref=employer, contract_id=contract.id,
        target=0, current_target=contract.staffing_target,
        workforce_limit=contract.workforce_limit, pressure_event_id=contract.last_event_id,
    )

    context = _staffing_context(world, option)
    expected_payroll = sum(
        item.staffing_target * item.wage_per_worker
        for item in world.economy.employment_contracts.values()
        if item.account_id == contract.account_id
    )
    assert context["account_current_standing_contract_payroll"] == expected_payroll
    assert context["account_payroll_after_selected_change"] == (
        expected_payroll - contract.staffing_target * contract.wage_per_worker)
    assert context["account_standing_contract_count"] == 2
    assert "exclui folha das instalações" in context["payroll_scope"]
    assert {contract.last_event_id, second_contract.last_event_id} <= set(
        _staffing_causes(world, option))


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


@pytest.mark.parametrize("limit_kind", ["labor", "funds"])
def test_contract_pays_only_the_workers_and_wages_actually_available(limit_kind):
    world, contract = contracted_world()
    next_month(world)
    available = monthly_workforce(world)
    workers = contract.workforce_limit - 1
    if limit_kind == "labor":
        available[contract.cohort_id] = workers
    else:
        account = world.economy.accounts[contract.account_id]
        world.economy.accounts[account.id] = account.model_copy(
            update={"balance": workers * contract.wage_per_worker})
    before_total = sum(item.balance for item in world.economy.accounts.values())

    settle_permanent_employment(world, available)

    payroll = world.economy.payrolls[contract.id]
    assert payroll.workers_by_group == {contract.cohort_id: workers}
    assert payroll.gross == workers * contract.wage_per_worker
    assert world.economy.employment_contracts[contract.id].last_outcome == "paid"
    assert sum(item.balance for item in world.economy.accounts.values()) == before_total
    receipt = next(item for item in world.events if item.event_type == "permanent_employment_settled")
    assert f"{workers}/{contract.workforce_limit}" in receipt.content
    world.economy.validate(world)


def test_employer_can_choose_lower_staffing_after_real_production_payroll_limit(tmp_path):
    from src.sim.medieval.economy import produce_monthly

    world, contract = contracted_world()
    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": contract.workforce_limit * contract.wage_per_worker})
    next_month(world)
    available = monthly_workforce(world)
    settle_permanent_employment(world, available)
    produce_monthly(world, available)
    employer = contract.employer_ref
    choices = employment_staffing_options(world, employer)
    assert choices
    assert any(world.event_index()[option.pressure_event_id].event_type == "production_limited"
               for option in choices)
    situation = employment_staffing_adapters()[0].situation_fn(world, employer, choices)
    assert len(situation["staffing_options"]) == len(choices)
    assert len(situation["staffing_contracts"]) == len({item.contract_id for item in choices})
    assert all("id" not in item for item in situation["staffing_options"])
    option = next(item for item in choices if item.contract_id == contract.id and item.target == 0)
    unrevised = deepcopy(world)
    decision = record_employment_staffing_decision(world, employer, option.id,
                                                   decision_source={"kind": "api"})
    revised = set_employment_staffing(world, employer, option.id, decision_event_id=decision.id)
    assert revised.staffing_target == option.target
    assert revised.workforce_limit == contract.workforce_limit
    assert revised.last_event_id in {event.id for event in world.events
                                     if event.event_type == "employment_staffing_changed"}
    assert not any(item.id == option.id for item in employment_staffing_options(world, employer))
    assert situation["own_production_readings"]
    staffing_context = next(item for item in situation["staffing_options"]
                            if item["contract_id"] == contract.id
                            and item["proposed_target"] == option.target)
    contract_context = next(item for item in situation["staffing_contracts"]
                            if item["contract_id"] == contract.id)
    assert "id" not in staffing_context
    assert contract_context["employer_account_balance"] == world.economy.accounts[contract.account_id].balance
    assert contract_context["current_contract_payroll"] == (
        option.current_target * revised.wage_per_worker)
    assert staffing_context["proposed_contract_payroll"] == (
        option.target * revised.wage_per_worker)
    assert contract_context["account_balance_event_id"] == world.economy.accounts[contract.account_id].last_event_id
    assert "exclui folha das instalações" in contract_context["payroll_scope"]
    constrained = next(item for item in situation["payroll_limited_production"]
                       if item["event_id"] == option.pressure_event_id)
    facility = world.economy.facilities[constrained["facility_id"]]
    recipe = world.economy.recipes[facility.recipe_id]
    assert constrained["settlement_id"] == world.economy.stocks[facility.stock_id].location_id
    assert constrained["inputs_per_batch"] == recipe.inputs
    assert constrained["outputs_per_batch"] == recipe.outputs
    assert "payroll_funds" in constrained["limitations"]
    assert all(world.economy.stocks[facility.stock_id].owner_ref == employer
               for facility in world.economy.facilities.values()
               if any(reading["facility_id"] == facility.id
                      for reading in situation["payroll_limited_production"]))
    path = tmp_path / "staffing.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.economy.employment_contracts[contract.id].staffing_target == option.target
    resumed.economy.validate(resumed)
    from tools.medieval_causal_audit import audit
    audit_result = audit(path)
    assert audit_result["ok"] is True, audit_result
    saved_contract = resumed.economy.employment_contracts[contract.id]
    resumed.economy.employment_contracts[contract.id] = saved_contract.model_copy(
        update={"staffing_target": contract.workforce_limit})
    with pytest.raises(ValueError, match="staffing decision provenance"):
        resumed.economy.validate(resumed)

    # Same available funds at the next boundary: the actor's explicit
    # suspension leaves real payroll and workers for a facility. No output is
    # granted by the staffing decision itself.
    produced = []
    staffed_workers = []
    for candidate in (unrevised, world):
        treasury = candidate.economy.accounts[contract.account_id]
        candidate.economy.accounts[treasury.id] = treasury.model_copy(
            update={"balance": contract.workforce_limit * contract.wage_per_worker})
        next_month(candidate)
        workforce = monthly_workforce(candidate)
        settle_permanent_employment(candidate, workforce)
        staffed_workers.append(candidate.economy.payrolls.get(contract.id))
        produce_monthly(candidate, workforce)
        produced.append(sum(facility.last_batches for facility in candidate.economy.facilities.values()
                            if facility.payroll_account_id == contract.account_id))
    assert produced[1] > produced[0]
    assert staffed_workers[0] is not None
    assert staffed_workers[0].day == world.clock.absolute_day
    assert staffed_workers[1] is not None
    assert staffed_workers[1].day < world.clock.absolute_day
    paused = world.economy.employment_contracts[contract.id]
    assert paused.staffing_target == 0
    assert paused.last_outcome == "paused"
    assert any(event.event_type == "permanent_employment_paused"
               and event.day == world.clock.absolute_day for event in world.events)
    event_index = world.event_index()
    paused_receipt = next(
        event for event in world.events
        if event.event_type == "permanent_employment_paused"
        and event.day == world.clock.absolute_day
        and any(delta.owner_kind == "employment_contract" and delta.owner_id == contract.id
                for delta in event.deltas)
    )
    transition = event_index[paused.last_event_id]
    assert paused_receipt.id == transition.id
    assert revised.last_event_id in {link.cause_event_id for link in paused_receipt.causal_links}
    assert decision.id in {link.cause_event_id for link in event_index[revised.last_event_id].causal_links}

    facility_events = [
        event for event in world.events
        if event.day == world.clock.absolute_day
        and event.event_type in {"production_completed", "production_limited"}
        and event.causal_payload
        and (facility := world.economy.facilities.get(
            event.causal_payload.get("production", {}).get("facility_id"))) is not None
        and facility.payroll_account_id == contract.account_id
    ]
    assert facility_events
    assert any(paused_receipt.id in {link.cause_event_id for link in event.causal_links}
               for event in facility_events)

    # The explicit staffing choice must remain explainable through production
    # and its actual payroll receipt, not merely sit beside a material event.
    outgoing = {}
    for event in world.events:
        for link in event.causal_links:
            outgoing.setdefault(link.cause_event_id, set()).add(event.id)
    reachable = {decision.id}
    frontier = [decision.id]
    while frontier:
        current = frontier.pop()
        for child in outgoing.get(current, set()) - reachable:
            reachable.add(child)
            frontier.append(child)
    reachable_events = [event_index[event_id] for event_id in reachable if event_id in event_index]
    reachable_types = {event.event_type for event in reachable_events}
    assert any(event.event_type == "production_completed"
               and event.causal_payload
               and world.economy.facilities[event.causal_payload["production"]["facility_id"]].payroll_account_id
               == contract.account_id for event in reachable_events)
    assert "wages_paid" in reachable_types
    world.economy.validate(world)
    paused_path = tmp_path / "paused-staffing.mws"
    save_world(world, paused_path)
    paused_round_trip = load_world(paused_path)
    paused_round_trip.economy.validate(paused_round_trip)
    assert paused_round_trip.economy.employment_contracts[contract.id].staffing_target == 0
    assert paused_round_trip.economy.employment_contracts[contract.id].last_outcome == "paused"


def test_repeated_payroll_pressure_only_offers_reductions_from_current_target():
    from src.sim.medieval.economy import produce_monthly

    world, contract = contracted_world()
    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": contract.workforce_limit * contract.wage_per_worker})
    next_month(world)
    workforce = monthly_workforce(world)
    settle_permanent_employment(world, workforce)
    produce_monthly(world, workforce)

    first_options = [item for item in employment_staffing_options(world, contract.employer_ref)
                     if item.contract_id == contract.id and 0 < item.target < item.current_target]
    assert first_options
    first_option = next(item for item in first_options
                        if item.target == max(1, contract.staffing_target // 2))
    decision = record_employment_staffing_decision(
        world, contract.employer_ref, first_option.id, decision_source={"kind": "api"})
    reduced = set_employment_staffing(world, contract.employer_ref, first_option.id,
                                      decision_event_id=decision.id)
    assert reduced.staffing_target < reduced.workforce_limit

    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": reduced.staffing_target * reduced.wage_per_worker})
    next_month(world)
    workforce = monthly_workforce(world)
    settle_permanent_employment(world, workforce)
    produce_monthly(world, workforce)

    pressured = [item for item in employment_staffing_options(world, contract.employer_ref)
                 if item.contract_id == contract.id]
    assert pressured
    assert all(item.target < item.current_target for item in pressured)
    assert all(item.target <= reduced.staffing_target for item in pressured)


def test_employer_can_suspend_contract_after_its_own_current_unpaid_funds_receipt():
    from src.classes.causal_origin import CausalOrigin
    from src.classes.event import FactKind
    from src.sim.medieval.permanent_employment import _standing_monthly_cost
    from src.sim.medieval.events import record_event

    world, contract = contracted_world()
    employer = contract.employer_ref
    second_offer = next(option for option in permanent_employment_options(world, employer)
                        if option.account_id == contract.account_id
                        and option.cohort_id != contract.cohort_id)
    second_decision = record_permanent_employment_decision(
        world, employer, second_offer.id, decision_source={"kind": "api"})
    second_contract = create_permanent_employment(
        world, second_offer.id, decision_event_id=second_decision.id)
    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    next_month(world)
    settle_permanent_employment(world, monthly_workforce(world))

    failed = world.event_index()[world.economy.employment_contracts[contract.id].last_event_id]
    assert failed.event_type == "permanent_employment_unpaid"
    assert failed.day == world.clock.absolute_day
    choices = [option for option in employment_staffing_options(world, contract.employer_ref)
               if option.contract_id == contract.id]
    assert [option.target for option in choices] == [0]
    option = choices[0]
    from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters
    from src.sim.medieval.institutional_decision_turn import _by_id
    assert employer in monthly_actors(world)
    assert option.id in _by_id(world, employer, monthly_adapters())
    committed_before = _standing_monthly_cost(world, contract.account_id)

    incomplete_decision = record_event(
        world, "employment_staffing_decided", "Decisão que omite o outro vínculo da conta.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), causal_payload={"decision_source": {"kind": "api"}},
        cause_ids=(option.pressure_event_id,))
    with pytest.raises(ValueError, match="matching sourced decision"):
        set_employment_staffing(world, employer, option.id,
                                decision_event_id=incomplete_decision.id)
    assert world.economy.employment_contracts[contract.id].staffing_target == contract.staffing_target

    decision = record_employment_staffing_decision(world, employer, option.id,
                                                   decision_source={"kind": "api"})
    changed = set_employment_staffing(world, employer, option.id,
                                      decision_event_id=decision.id)

    assert option.pressure_event_id == failed.id
    assert changed.staffing_target == 0
    assert second_contract.id in world.economy.employment_contracts
    assert _standing_monthly_cost(world, contract.account_id) == (
        committed_before - contract.workforce_limit * contract.wage_per_worker)
    transition = world.event_index()[changed.last_event_id]
    assert failed.id in {link.cause_event_id for link in transition.causal_links}
    assert transition.causal_origin.value == "actor_decision"


def test_staffing_rejects_stale_or_unsourced_choice_without_mutation():
    from src.classes.event import FactKind
    from src.sim.medieval.economy import produce_monthly
    from src.sim.medieval.events import record_event

    world, contract = contracted_world()
    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    next_month(world)
    produce_monthly(world, monthly_workforce(world))
    option = next(item for item in employment_staffing_options(world, contract.employer_ref)
                  if item.contract_id == contract.id and item.target == 0)
    unsourced = record_event(world, "fixture_unsourced_staffing", "Escolha sem relatório.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    before = world.economy.employment_contracts[contract.id]
    with pytest.raises(ValueError, match="matching sourced decision"):
        set_employment_staffing(world, contract.employer_ref, option.id,
                                decision_event_id=unsourced.id)
    assert world.economy.employment_contracts[contract.id] == before
    decision = record_employment_staffing_decision(
        world, contract.employer_ref, option.id, decision_source={"kind": "api"})
    world.clock = world.clock.advance(1)
    with pytest.raises(ValueError, match="stale"):
        set_employment_staffing(world, contract.employer_ref, option.id,
                                decision_event_id=decision.id)
    assert world.economy.employment_contracts[contract.id] == before


@pytest.mark.asyncio
async def test_staffing_option_joins_the_single_institutional_provider_menu(monkeypatch):
    import json
    from src.sim.medieval import ai_decider
    from src.sim.medieval.economy import produce_monthly
    from src.sim.medieval.institutional_agenda import monthly_adapters
    from src.sim.medieval.institutional_decision_turn import (
        _by_id, review_institutional_decision_turn_with_provider)

    world, contract = contracted_world()
    next_month(world)
    settle_permanent_employment(world, monthly_workforce(world))
    account = world.economy.accounts[contract.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    produce_monthly(world, monthly_workforce(world))
    refresh_reports(world)
    option = next(item for item in employment_staffing_options(world, contract.employer_ref)
                  if item.contract_id == contract.id and item.target == 0)
    assert option.id in _by_id(world, contract.employer_ref, monthly_adapters())
    world.config = world.config.model_copy(update={"ai_enabled": True,
                                                   "ai_calls_per_step": 100, "ai_max_calls": 100})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    prompts = []

    async def choose(prompt, *args, **kwargs):
        prompts.append(prompt)
        return {"selected_id": option.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    _, covered = await review_institutional_decision_turn_with_provider(
        world, monthly_adapters(), actors=(contract.employer_ref,))
    assert contract.employer_ref in covered
    assert world.economy.employment_contracts[contract.id].staffing_target == option.target
    assert option.target == 0
    decision = next(event for event in reversed(world.events)
                    if event.event_type == "institutional_decision_turn_decided")
    assert decision.decision == option.decision()
    assert not decision.deltas
    payload = json.loads(prompts[0][prompts[0].index("{"):])
    staffing = payload["situation"]["employment_staffing"]
    livelihood = next(item for item in staffing["own_local_livelihood_readings"]
                      if item["settlement_id"] == contract.settlement_id)
    assert livelihood["own_standing_employment_paid_workers_by_occupation"][contract.occupation] > 0
    local_pressure = next(item for item in staffing["settlement_reports"]
                          if item["settlement_id"] == contract.settlement_id)
    selected_context = next(item for item in staffing["staffing_options"]
                            if item["contract_id"] == contract.id and item["proposed_target"] == 0)
    contract_context = next(item for item in staffing["staffing_contracts"]
                            if item["contract_id"] == contract.id)
    assert local_pressure["observed_day"] == world.clock.absolute_day
    assert {"missing_food", "health", "unrest", "unaffordable_food"} <= set(local_pressure)
    assert contract_context["account_current_standing_contract_payroll"] == (
        contract.staffing_target * contract.wage_per_worker)
    assert selected_context["account_payroll_after_selected_change"] == 0
    assert livelihood["source_event_ids"]
    assert contract.cohort_id not in repr(livelihood), "actor context stays aggregate"
    constrained = next(item for item in staffing["payroll_limited_production"]
                       if item["event_id"] == option.pressure_event_id)
    recipe = world.economy.recipes[world.economy.facilities[constrained["facility_id"]].recipe_id]
    assert constrained["inputs_per_batch"] == recipe.inputs
    assert constrained["outputs_per_batch"] == recipe.outputs
    assert option.id in {item["id"] for item in payload["choices"]}
    decision_causes = {link.cause_event_id for link in decision.causal_links}
    assert set(livelihood["source_event_ids"]) <= decision_causes
    if local_pressure["affordability_event_id"] is not None:
        assert local_pressure["affordability_event_id"] in decision_causes


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
    decision = record_permanent_employment_decision(world, employer, option.id,
                                                   decision_source={"kind": "api"})
    account = world.economy.accounts[option.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    with pytest.raises(ValueError, match="stale or unknown"):
        create_permanent_employment(world, option.id, decision_event_id=decision.id)
    assert not world.economy.employment_contracts


def test_employment_turn_exposes_public_pressure_without_private_terms():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    refresh_reports(world)
    options = permanent_employment_options(world, employer)
    situation = permanent_employment_adapters()[0].situation_fn(world, employer, options)

    assert situation["you_are"] == employer.to_dict()
    assert situation["employment_options"]
    assert situation["own_local_livelihood_readings"]
    first = situation["employment_options"][0]
    assert {"id", "settlement_id", "cohort_id", "occupation", "work_site_id",
            "workforce_limit", "wage_per_worker", "pressure"} <= set(first)
    assert {"unaffordable_food", "health", "missing_food", "unrest"} <= set(first["pressure"])
    livelihood = next(item for item in situation["own_local_livelihood_readings"]
                      if item["settlement_id"] == first["settlement_id"])
    assert {"residents_by_occupation", "own_production_paid_workers_by_occupation",
            "source_event_ids"} <= set(livelihood)
    evidence = set(permanent_employment_adapters()[0].causes_fn(world, options[0]))
    assert evidence.intersection(livelihood["source_event_ids"])
    # The provider gets public pressure and the engine-bounded offer, never
    # the account/stock IDs or their balances that the owner revalidates.
    assert "account_id" not in first
    assert "stock_id" not in first
    assert "balance" not in repr(situation)
    assert "não opera instalações nem cria alimentos" in situation["employment_effect"]


@pytest.mark.asyncio
async def test_employment_choice_cites_local_livelihood_evidence(monkeypatch):
    from src.sim.medieval import ai_decider
    from src.sim.medieval.institutional_agenda import monthly_adapters
    from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn_with_provider

    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    refresh_reports(world)
    option = permanent_employment_options(world, employer)[0]
    situation = permanent_employment_adapters()[0].situation_fn(
        world, employer, permanent_employment_options(world, employer))
    livelihood = next(item for item in situation["own_local_livelihood_readings"]
                      if item["settlement_id"] == option.settlement_id)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 20, "ai_max_calls": 20,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def choose(_prompt, *args, **kwargs):
        return {"selected_id": option.id}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    await review_institutional_decision_turn_with_provider(
        world, monthly_adapters(), actors=(employer,))

    decision = next(event for event in reversed(world.events)
                    if event.event_type == "institutional_decision_turn_decided")
    causes = {link.cause_event_id for link in decision.causal_links}
    assert set(livelihood["source_event_ids"]) <= causes
    assert decision.decision == option.decision()


def test_employment_site_is_bounded_by_its_authored_facility_occupation():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "auren")
    options = permanent_employment_options(world, employer)
    assert options
    for option in options:
        facilities = [facility for facility in world.economy.facilities.values()
                      if facility.site_id == option.work_site_id]
        assert facilities, "unmodeled empty infrastructure is not a job site"
        occupations = {world.economy.recipes[facility.recipe_id].occupation
                       for facility in facilities}
        assert option.occupation in occupations


def test_offline_employment_fallback_uses_current_pressure_and_material_owner():
    world = create_medieval_world(73)
    employer = EntityRef("polity", "escarlia")
    refresh_reports(world)
    options = tuple(item for item in permanent_employment_options(world, employer)
                    if item.settlement_id == "ferroalto" and item.occupation == "artisan")
    option = options[0]
    report = world.knowledge.settlement_report(employer, option.settlement_id)
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 4})

    contracts = review_permanent_employment_fallback(world)

    assert contracts
    contract = next(item for item in contracts if item.employer_ref == employer)
    assert contract.cohort_id in {item.cohort_id for item in options}
    decision = next(item for item in world.events if item.id == contract.decision_event_id)
    assert decision.fact_kind.value == "decision"
    assert decision.causal_origin.value == "actor_decision"
    assert decision.decision["selected_affordance_id"] in {item.id for item in options}
    assert decision.causal_payload["decision_source"] == {
        "kind": "fallback", "policy": "routine-rules", "rule": "permanent_employment",
    }
    assert any(item.event_type == "permanent_employment_created" for item in world.events)
    world.economy.validate(world)


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
