"""Raising a new site: the last missing link between idle people and work.

Two settlements hold thousands of artisans on ground whose authored
capabilities admit no artisan recipe, so C98 could never found a line there
and those households could never earn a wage. A construction raises the site
itself. It invents nothing spatial: the Map places the works on a cell of a
region it already declares, and the granted capability comes from the authored
blueprint, never from the actor. Money and materials are the owner's own.
"""

import json

import pytest

from src.classes.core.infrastructure import validate_infrastructure
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.economy import consume_monthly, produce_monthly
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import (construction_blocker, constructed_site_id,
                                        foundation_adapters, foundation_options, progress_expansions,
                                        site_construction_adapters, site_construction_options,
                                        start_foundation, start_site_construction)
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.systems.time import WorldClock


AUREN = EntityRef("polity", "auren")
SETTLEMENT = "pedraclara"
BLUEPRINT = "craft-workshop-construction"
AUTHORED_SITE = "campos-de-pedra-clara"
FOUNDATION = "craft-workshop-foundation"


def prepared():
    """The authored world already has the gap; only the purse is topped up."""
    world = create_medieval_world(73)
    stock, account = holdings(world)
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "wood": 300, "stone": 300, "iron": 200}})
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": max(account.balance, 20000)})
    return world


def holdings(world):
    from src.sim.medieval.expansion import _local_holdings

    stock, account = _local_holdings(world, AUREN, SETTLEMENT)
    assert stock is not None and account is not None
    return stock, account


def only_option(world):
    options = [item for item in site_construction_options(world, AUREN)
               if item.settlement_id == SETTLEMENT]
    assert len(options) == 1, [item.id for item in options]
    return options[0]


def authorize(world, option):
    from src.sim.medieval.expansion import _construction_terms

    return record_event(world, "site_construction_authorized", "Autorizar a obra.",
                        fact_kind=FactKind.DECISION, decision=_construction_terms(option))


def build(world, project_id, limit=800):
    day = world.clock.absolute_day
    while world.economy.expansions[project_id].stage != "completed" and day < limit:
        day += 30
        world.clock = WorldClock(day)
        progress_expansions(world, {g.id: g.count for g in world.society.population.values()})
    return world.economy.expansions[project_id]


def total(world, resource):
    return sum(stock.goods.get(resource, 0) for stock in world.economy.stocks.values())


def test_only_a_settlement_that_lacks_the_capability_can_raise_it():
    world = prepared()
    option = only_option(world)
    assert option.new_site_id == constructed_site_id(SETTLEMENT, world.economy.expansion_blueprints[BLUEPRINT])
    # Ferroalto already has craftsmanship, so its administration is offered none.
    assert not [item for item in site_construction_options(world, EntityRef("polity", "escarlia"))]


@pytest.mark.parametrize("missing", ["administration", "capability_exists", "funds", "labor", "holdings"])
def test_every_authored_and_material_gate_is_required(missing):
    world = prepared()
    settlement = world.society.settlements[SETTLEMENT]
    blueprint = world.economy.expansion_blueprints[BLUEPRINT]
    stock, account = holdings(world)
    if missing == "administration":
        world.society.settlements[SETTLEMENT] = settlement.model_copy(update={"administrator_id": "escarlia"})
    elif missing == "capability_exists":
        from dataclasses import replace
        site_id = next(item.id for item in world.map.infrastructure_sites.values()
                       if settlement.region_id in item.region_ids)
        site = world.map.infrastructure_sites[site_id]
        world.map.infrastructure_sites[site_id] = replace(
            site, capability_ids=(*site.capability_ids, "craftsmanship"))
    elif missing == "funds":
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    elif missing == "labor":
        for group_id, group in tuple(world.society.population.items()):
            if group.settlement_id == SETTLEMENT:
                world.society.population[group_id] = group.model_copy(update={"count": 0})
    else:
        # The administration keeps no stock of its own in the settlement.
        world.economy.stocks.pop(stock.id)

    settlement = world.society.settlements[SETTLEMENT]
    from src.sim.medieval.expansion import _local_holdings
    stock, account = _local_holdings(world, AUREN, SETTLEMENT)
    assert construction_blocker(world, AUREN, settlement, blueprint, stock, account) is not None
    assert not [item for item in site_construction_options(world, AUREN)
                if item.settlement_id == SETTLEMENT]


def test_completion_commissions_a_map_owned_site_with_its_authored_capability(tmp_path):
    world = prepared()
    option = only_option(world)
    wood_before, stone_before = total(world, "wood"), total(world, "stone")
    money_before = sum(item.balance for item in world.economy.accounts.values())
    sites_before = set(world.map.infrastructure_sites)

    project = start_site_construction(world, option, decision_event_id=authorize(world, option).id)
    assert option.new_site_id not in world.map.infrastructure_sites, "nada existe antes da obra"
    project = build(world, project.id)

    assert project.stage == "completed" and project.facility_id is None and project.site_id is None
    created = world.map.infrastructure_sites[option.new_site_id]
    assert set(world.map.infrastructure_sites) - sites_before == {option.new_site_id}
    assert created.capability_ids == ("craftsmanship",)
    assert created.owner_ref == AUREN and created.maintainer_ref == AUREN
    assert created.region_ids == (world.society.settlements[SETTLEMENT].region_id,)

    # The site's provenance is the dated works receipt, with a site delta for
    # every aspect the canonical validator can prove.
    receipt = next(item for item in world.events if item.id == created.last_event_id)
    aspects = {delta.aspect for delta in receipt.deltas
               if delta.owner_kind == "site" and delta.owner_id == created.id}
    assert {"capability_ids", "integrity", "enabled", "service_suspended",
            "owner_ref", "maintainer_ref"} <= aspects
    granted = next(delta for delta in receipt.deltas
                   if delta.owner_kind == "site" and delta.owner_id == created.id
                   and delta.aspect == "capability_ids")
    assert granted.after == "craftsmanship" and granted.before == "None"
    validate_infrastructure(world)
    world.economy.validate(world)

    # Nothing was created: wages moved the owner's coin to the households that
    # built it, and the materials really left the stock.
    assert sum(item.balance for item in world.economy.accounts.values()) == money_before
    assert total(world, "wood") < wood_before and total(world, "stone") < stone_before
    assert world.economy.payrolls[project.id].gross > 0

    path = tmp_path / "construction.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.map.infrastructure_sites[option.new_site_id].capability_ids == ("craftsmanship",)


def test_the_works_never_land_on_ground_another_site_already_occupies():
    world = prepared()
    option = only_option(world)
    settlement = world.society.settlements[SETTLEMENT]
    taken = {cell for site in world.map.infrastructure_sites.values() for cell in site.cell_refs}

    build(world, start_site_construction(
        world, option, decision_event_id=authorize(world, option).id).id)

    created = world.map.infrastructure_sites[option.new_site_id]
    assert len(created.cell_refs) == 1
    assert created.cell_refs[0] not in taken
    assert created.cell_refs[0] in world.map.get_region_coordinates(settlement.region_id)

    # A second commission takes different ground again, never the same cell.
    second = world.map.commission_infrastructure_site(
        "site:pedraclara:second", kind="workshop", name="Segunda",
        region_id=settlement.region_id, capability_ids=("craftsmanship",),
        owner_ref=AUREN, last_event_id=created.last_event_id)
    assert second.cell_refs[0] != created.cell_refs[0]

    # When the region's only buildable ground is already taken, the Map
    # refuses outright instead of stacking two sites on one cell.
    occupied = {cell for site in world.map.infrastructure_sites.values() for cell in site.cell_refs}
    world.map._region_coordinates = lambda region_id, _cell=created.cell_refs[0]: {_cell}
    assert created.cell_refs[0] in occupied
    with pytest.raises(ValueError, match="no free buildable cell"):
        world.map.commission_infrastructure_site(
            "site:pedraclara:crowded", kind="workshop", name="Sobreposta",
            region_id=settlement.region_id, capability_ids=("craftsmanship",),
            owner_ref=AUREN, last_event_id=created.last_event_id)


def test_a_commissioned_capability_cannot_be_forged_or_drift_from_its_receipt():
    """Physical ability needs the dated fact that granted it, and only that."""
    from dataclasses import replace

    world = prepared()
    option = only_option(world)
    build(world, start_site_construction(
        world, option, decision_event_id=authorize(world, option).id).id)
    validate_infrastructure(world)
    created = world.map.infrastructure_sites[option.new_site_id]

    # A capability nobody granted: the receipt no longer describes the site.
    world.map.infrastructure_sites[created.id] = replace(
        created, capability_ids=("craftsmanship", "arcane_research"))
    with pytest.raises(ValueError, match="must match the receipt that commissioned them"):
        validate_infrastructure(world)

    # A capability no authored blueprint grants, declared as if commissioned:
    # the receipt and the site agree with each other and still lie.
    world = prepared()
    option = only_option(world)
    build(world, start_site_construction(
        world, option, decision_event_id=authorize(world, option).id).id)
    created = world.map.infrastructure_sites[option.new_site_id]
    receipt = next(item for item in world.events if item.id == created.last_event_id)
    granted = next(item for item in receipt.deltas
                   if item.owner_kind == "site" and item.owner_id == created.id
                   and item.aspect == "capability_ids")
    object.__setattr__(granted, "after", "necromancy")
    object.__setattr__(created, "capability_ids", ("necromancy",))
    with pytest.raises(ValueError, match="only hold an authored blueprint capability"):
        validate_infrastructure(world)


@pytest.mark.parametrize("forged", [("craftsmanship", "craftsmanship"), ("craftsmanship", "  ")])
def test_site_capabilities_must_be_unique_and_named(forged):
    """The model refuses this on construction; the validator refuses it on load."""
    world = prepared()
    site = world.map.infrastructure_sites[AUTHORED_SITE]
    object.__setattr__(site, "capability_ids", forged)
    with pytest.raises(ValueError, match="unique and named"):
        validate_infrastructure(world)


def test_an_authored_site_keeps_its_capability_without_any_receipt():
    """Regression: authored capability needs no commissioning fact."""
    world = prepared()
    authored = world.map.infrastructure_sites[AUTHORED_SITE]
    assert authored.capability_ids and authored.last_event_id is None
    validate_infrastructure(world)


def test_a_construction_blueprint_is_never_opened_as_an_anchor_expansion():
    from src.sim.medieval.expansion import expansion_options, start_expansion

    world = prepared()
    assert not [item for item in expansion_options(world, AUREN) if item.blueprint_id == BLUEPRINT]
    facility = next(iter(world.economy.facilities.values()))
    with pytest.raises(ValueError, match="opened by its own owner"):
        start_expansion(world, facility.id, BLUEPRINT, decision_event_id="event:1")


def test_the_new_site_lets_c98_found_the_line_and_pay_idle_artisans():
    """site -> line -> wages: the chain the settlement could not have before."""
    world = prepared()
    option = only_option(world)
    assert not [item for item in foundation_options(world, AUREN)
                if item.blueprint_id == FOUNDATION], "sem sítio capaz, nada a fundar"

    project = build(world, start_site_construction(
        world, option, decision_event_id=authorize(world, option).id).id)
    assert project.stage == "completed"

    line_option = next(item for item in foundation_options(world, AUREN)
                       if item.blueprint_id == FOUNDATION and item.site_id == option.new_site_id)
    from src.sim.medieval.expansion import _foundation_terms
    decision = record_event(world, "line_foundation_authorized", "Fundar a linha.",
                            fact_kind=FactKind.DECISION, decision=_foundation_terms(line_option))
    line = build(world, start_foundation(world, line_option, decision_event_id=decision.id).id)
    assert line.stage == "completed"

    created_line = world.economy.facilities[f"line:{option.new_site_id}:toolmaking"]
    assert created_line.recipe_id == "toolmaking"

    artisans = [group.id for group in world.society.population.values()
                if group.settlement_id == SETTLEMENT and group.occupation == "artisan"]
    assert artisans
    produce_monthly(world, {g.id: g.count for g in world.society.population.values()})
    paid = [group_id for group_id in artisans
            if world.economy.accounts.get(f"household:{group_id}") is not None
            and world.economy.accounts[f"household:{group_id}"].balance > 0]
    assert paid, "a linha nova emprega artesãos que antes não tinham empregador"

    # That income is exactly what the affordability reading measures.
    consume_monthly(world)
    reading = next(event.causal_payload["subsistence"] for event in reversed(world.events)
                   if event.causal_payload and "subsistence" in event.causal_payload
                   and event.causal_payload["subsistence"]["settlement_id"] == SETTLEMENT)
    assert reading["purchased_quantity"] > 0
    assert sum(reading["unaffordable_by_group"].get(group_id, 0) for group_id in paid) < sum(
        world.society.available_count(group_id) for group_id in paid)


@pytest.mark.asyncio
async def test_informed_administrator_can_choose_workshop_without_free_employment(monkeypatch):
    from src.sim.medieval.intelligence import refresh_reports

    world = prepared()
    world.clock = WorldClock(30)
    produce_monthly(world)
    refresh_reports(world)
    option = only_option(world)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 1,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    seen = []

    async def choose(_world, _actor, situation, choices, **_kwargs):
        local = next(item for item in situation["own_local_livelihood_readings"]
                     if item["settlement_id"] == SETTLEMENT)
        assert local["residents_by_occupation"]["artisan"] > 1000
        assert local["own_production_paid_workers_by_occupation"].get("artisan", 0) == 0
        assert option.id in {choice["id"] for choice in choices}
        seen.append(local["source_event_ids"])
        return option.id

    monkeypatch.setattr(ai_decider, "select_option", choose)
    before_money = sum(account.balance for account in world.economy.accounts.values())

    _claims, covered = await review_institutional_decision_turn(
        world, AUREN, site_construction_adapters())

    assert covered and seen
    assert any(project.blueprint_id == BLUEPRINT for project in world.economy.expansions.values())
    assert option.new_site_id not in world.map.infrastructure_sites
    assert sum(account.balance for account in world.economy.accounts.values()) == before_money
    assert any(event.event_type == "institutional_decision_turn_decided"
               and event.decision == option.decision() for event in world.events)


@pytest.mark.asyncio
async def test_chosen_workshop_pays_artisans_and_improves_food_access_against_no_works(monkeypatch, tmp_path):
    """One pressed chain, with an identical no-works world as counterfactual."""
    from src.sim.medieval.intelligence import refresh_reports

    world, control = prepared(), prepared()
    for candidate in (world, control):
        candidate.clock = WorldClock(30)
        produce_monthly(candidate)
        refresh_reports(candidate)
    initial_money = sum(account.balance for account in world.economy.accounts.values())
    initial_population = sum(group.count for group in world.society.population.values())
    option = only_option(world)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 2,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def choose(_world, _actor, situation, choices, **_kwargs):
        ids = {choice["id"] for choice in choices}
        if option.id in ids:
            local = next(item for item in situation["own_local_livelihood_readings"]
                         if item["settlement_id"] == SETTLEMENT)
            assert local["residents_by_occupation"]["artisan"] > 1000
            assert local["own_production_paid_workers_by_occupation"].get("artisan", 0) == 0
            selected = option.id
        else:
            selected = next(item.id for item in foundation_options(_world, AUREN)
                            if item.blueprint_id == FOUNDATION and item.site_id == option.new_site_id)
            assert selected in ids
        chosen.append(selected)
        return selected

    monkeypatch.setattr(ai_decider, "select_option", choose)
    await review_institutional_decision_turn(world, AUREN, site_construction_adapters())
    site_project = next(project for project in world.economy.expansions.values()
                        if project.blueprint_id == BLUEPRINT)
    assert build(world, site_project.id).stage == "completed"
    assert option.new_site_id in world.map.infrastructure_sites

    await review_institutional_decision_turn(world, AUREN, foundation_adapters())
    line_project = next(project for project in world.economy.expansions.values()
                        if project.blueprint_id == FOUNDATION)
    assert build(world, line_project.id).stage == "completed"
    line_id = f"line:{option.new_site_id}:toolmaking"
    assert line_id in world.economy.facilities
    assert len(chosen) == 2

    # Both worlds reach the same subsequent production boundary. The fixture
    # supplies materials and treasury up front, but neither path gets wages,
    # food or a line merely from the provider's answer.
    control.clock = world.clock = WorldClock(world.clock.absolute_day + 30)
    artisans = {group.id for group in world.society.population.values()
                if group.settlement_id == SETTLEMENT and group.occupation == "artisan"}
    before = {group_id: world.economy.accounts[f"household:{group_id}"].balance
              for group_id in artisans}
    produce_monthly(world)
    produce_monthly(control)
    payroll = world.economy.payrolls[line_id]
    assert payroll.gross > 0 and artisans.intersection(payroll.workers_by_group)
    assert any(world.economy.accounts[f"household:{group_id}"].balance > before[group_id]
               for group_id in payroll.workers_by_group)
    assert line_id not in control.economy.facilities

    consume_monthly(world)
    consume_monthly(control)

    def reading(candidate):
        return next(event.causal_payload["subsistence"] for event in reversed(candidate.events)
                    if event.causal_payload and "subsistence" in event.causal_payload
                    and event.causal_payload["subsistence"]["settlement_id"] == SETTLEMENT)

    with_works, without_works = reading(world), reading(control)
    assert with_works["purchased_quantity"] > without_works["purchased_quantity"]
    assert with_works["missing_food"] < without_works["missing_food"]
    assert world.economy.needs[SETTLEMENT].health > control.economy.needs[SETTLEMENT].health
    decisions = [event for event in world.events
                 if event.event_type == "institutional_decision_turn_decided"
                 and event.decision and event.decision.get("selected_affordance_id") in chosen]
    assert len(decisions) == 2
    events_by_id = world.event_index()
    for project, selected in ((site_project, option.id), (line_project, chosen[1])):
        actor_decision = next(event for event in decisions
                              if event.decision["selected_affordance_id"] == selected)
        authorization = events_by_id[project.decision_event_id]
        assert actor_decision.id in {link.cause_event_id for link in authorization.causal_links}
    production = next(event for event in world.events
                      if event.event_type == "production_completed" and event.causal_payload
                      and event.causal_payload.get("production", {}).get("facility_id") == line_id)
    wage = next(event for event in world.events
                if event.event_type == "wages_paid"
                and production.id in {link.cause_event_id for link in event.causal_links})
    income_events = {wage.id}
    income_events.update(event.id for event in world.events
                         if event.event_type == "income_tax_collected"
                         and wage.id in {link.cause_event_id for link in event.causal_links})
    assert any(event.event_type == "household_purchase_completed"
               and income_events.intersection(link.cause_event_id for link in event.causal_links)
               and any(delta.owner_id == f"household:{group_id}" for delta in event.deltas)
               for event in world.events for group_id in payroll.workers_by_group)
    assert sum(account.balance for account in world.economy.accounts.values()) == initial_money
    assert sum(group.count for group in world.society.population.values()) == initial_population

    path = tmp_path / "workshop-chain.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


@pytest.mark.asyncio
async def test_workshop_choice_reappears_as_foundation_in_the_normal_monthly_engine(monkeypatch, tmp_path):
    """The phase runner, not a test-only owner sequence, advances the chain."""
    world = prepared()
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 2000,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def choose(_world, actor, _situation, choices, **_kwargs):
        ids = {choice["id"] for choice in choices}
        if actor == AUREN:
            if option := next((item for item in site_construction_options(_world, actor)
                               if item.settlement_id == SETTLEMENT and item.id in ids), None):
                chosen.append(("site", _world.clock.absolute_day, option.id))
                return option.id
            if option := next((item for item in foundation_options(_world, actor)
                               if item.blueprint_id == FOUNDATION and item.id in ids), None):
                chosen.append(("line", _world.clock.absolute_day, option.id))
                return option.id
        return ai_decider.NO_ACTION

    monkeypatch.setattr(ai_decider, "select_option", choose)
    engine = MedievalSimulator(world)
    line_id = f"line:{constructed_site_id(SETTLEMENT, world.economy.expansion_blueprints[BLUEPRINT])}:toolmaking"
    for _ in range(60):
        await engine.step()
        if any(event.event_type == "production_completed" and event.causal_payload
               and event.causal_payload.get("production", {}).get("facility_id") == line_id
               for event in engine.world.events):
            break
    else:
        pytest.fail(f"monthly engine did not produce from the chosen line by day {engine.world.clock.absolute_day}")

    assert [kind for kind, _, _ in chosen] == ["site", "line"]
    assert chosen[0][1] < chosen[1][1] < engine.world.clock.absolute_day
    payroll = engine.world.economy.payrolls[line_id]
    assert payroll.gross > 0
    assert any(event.event_type == "household_purchase_completed"
               and payroll.last_event_id in {link.cause_event_id for link in event.causal_links}
               and any(delta.owner_id == f"household:{group_id}" for delta in event.deltas)
               for event in engine.world.events for group_id in payroll.workers_by_group)
    path = tmp_path / "monthly-workshop.mws"
    save_world(engine.world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(engine.world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


@pytest.mark.asyncio
async def test_unmodified_seed_offers_workshop_beside_dated_livelihood_reading(monkeypatch):
    world = create_medieval_world(73)
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 2000,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    observed = []

    async def observe(_world, actor, situation, choices, **_kwargs):
        if actor == AUREN and any(item["id"].startswith("site-construction:") for item in choices):
            observed.append((situation, choices))
        return ai_decider.NO_ACTION

    monkeypatch.setattr(ai_decider, "select_option", observe)
    engine = MedievalSimulator(world)
    while engine.world.clock.absolute_day < 30:
        await engine.step()

    assert len(observed) == 1
    situation, choices = observed[0]
    assert len(choices) > 1, "a oficina compete no menu institucional real"
    assert any(item["id"].startswith("site-construction:polity:auren:pedraclara:") for item in choices)
    reading = next(item for item in situation["own_local_livelihood_readings"]
                   if item["settlement_id"] == SETTLEMENT)
    residents = reading["residents_by_occupation"]["artisan"]
    paid = reading["own_production_paid_workers_by_occupation"].get("artisan", 0)
    assert residents > paid
    assert reading["source_event_ids"]
    assert not engine.world.economy.expansions, "NO_ACTION não constrói a oficina"


async def test_a_stale_construction_choice_fails_closed(monkeypatch):
    world = prepared()
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item for item in payload["choices"]
                       if item["label"].startswith("Construir")), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["id"])
        # The settlement changes hands while the actor answers.
        settlement = world.society.settlements[SETTLEMENT]
        world.society.settlements[SETTLEMENT] = settlement.model_copy(
            update={"administrator_id": "escarlia"})
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, AUREN, site_construction_adapters())
    assert len(chosen) == 1
    assert not world.economy.expansions
    assert constructed_site_id(SETTLEMENT, world.economy.expansion_blueprints[BLUEPRINT]) \
        not in world.map.infrastructure_sites

    decision = next((item for item in world.events
                     if item.event_type == "institutional_decision_turn_decided"), None)
    if decision is not None:
        assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}
