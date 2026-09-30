"""Focused causal tests for institutional technology theft."""

import copy

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.models import AuthorityOffice
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.events import record_event
from src.sim.medieval.economy import monthly_workforce, produce_monthly
from src.sim.medieval.expansion import (expansion_options, progress_expansions,
                                       start_expansion)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.technology_theft import execute_technology_theft, technology_theft_options
from tests.test_medieval_technology_sale import researched_world
from src.systems.time import WorldClock


OWNER = EntityRef("polity", "auren")


def prepared_world(skill=60, *, apply=True):
    world = researched_world()
    # A technique is stealable only from a paid, operating technical line.
    # Research and disclosure alone are not evidence that the holder applies it.
    if apply:
        facility_id = "works:minas-de-ferroalto"
        decision = record_event(world, "theft_fixture_expansion_decided", "Construir a linha de carvão observada.",
                                fact_kind=FactKind.DECISION,
                                causal_origin=CausalOrigin.ACTOR_DECISION,
                                decision={"action": "expand", "actor_ref": EntityRef("polity", "escarlia").to_dict(),
                                          "facility_id": facility_id, "blueprint_id": "charcoal-kilns"},
                                causal_payload={"decision_source": {"kind": "api"}})
        start_expansion(world, facility_id, "charcoal-kilns", decision_event_id=decision.id)
        for day in (120, 150):
            world.clock = WorldClock(day)
            progress_expansions(world, monthly_workforce(world))
        produce_monthly(world)
        assert world.economy.facilities["line:minas-de-ferroalto:charcoal"].last_batches > 0
    agent = world.society.characters["character:004"].model_copy(
        update={"skills": world.society.characters["character:004"].skills.model_copy(
            update={"investigation": skill})})
    world.society.characters[agent.id] = agent
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = AuthorityOffice(
        id=office.id, institution_ref=OWNER, holder_ref=EntityRef("character", agent.id),
        scopes=office.scopes, starts_day=office.starts_day, ends_day=office.ends_day)
    refresh_site_reports(world, site_ids=["minas-de-ferroalto"])
    return world, agent


def test_known_but_unapplied_technology_is_not_a_theft_target():
    world, _agent = prepared_world(apply=False)
    assert not technology_theft_options(world, OWNER)


def test_theft_option_disappears_when_technical_line_stops_operating():
    world, _agent = prepared_world()
    option, = technology_theft_options(world, OWNER)
    operation = world.event_index()[option.operation_event_id]
    assert operation.event_type == "production_completed"
    assert operation.causal_payload["production"]["recipe_id"] == "charcoal"
    world.clock = WorldClock(180)
    produce_monthly(world, {group_id: 0 for group_id in monthly_workforce(world)})
    refresh_site_reports(world, site_ids=["minas-de-ferroalto"])
    assert not technology_theft_options(world, OWNER)


def decide(world, option):
    return record_event(world, "technology_theft_decided", "A instituição selecionou uma tentativa de obtenção técnica.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        causal_payload={"decision_source": {"kind": "api"}},
                        decision=option.decision(),
                        cause_ids=(option.observation_event_id, option.source_knowledge_event_id))


def test_deterministic_copy_of_theft_affordance_cannot_create_a_mission():
    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    decision = record_event(world, "technology_theft_decided", "Payload idêntico sem escolha do ator.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(option.observation_event_id, option.source_knowledge_event_id))
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="exact current decision"):
        execute_technology_theft(world, OWNER, option.id, decision.id)

    assert world_snapshot(world) == before


def test_success_copies_only_sighted_canonical_technology_and_round_trips(tmp_path):
    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    before = copy.deepcopy(world.map.infrastructure_sites)
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)

    assert finding.result == "success"
    assert world.knowledge.knows(OWNER, "metallurgy")
    assert world.map.infrastructure_sites == before
    assert world.knowledge.technologies[f"technology:{OWNER.kind}:{OWNER.id}:metallurgy"].channel == "stolen"
    world.knowledge.validate(world)
    path = tmp_path / "technology-theft.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_low_skill_is_failure_and_discovery_does_not_grant_knowledge(monkeypatch):
    world, _agent = prepared_world(skill=10)
    option = technology_theft_options(world, OWNER)[0]
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "failure"
    assert not world.knowledge.knows(OWNER, "metallurgy")

    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    monkeypatch.setattr("src.sim.medieval.technology_theft._target_detects", lambda *_args: True)
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "discovered"
    assert not world.knowledge.knows(OWNER, "metallurgy")


def test_stale_selection_cannot_mutate_knowledge():
    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    decision = decide(world, option)
    events_before = list(world.events)
    knowledge_before = dict(world.knowledge.technologies)
    world.knowledge.technology_sightings.clear()
    with pytest.raises(ValueError, match="absent or stale"):
        execute_technology_theft(world, OWNER, option.id, decision.id)
    assert world.events == events_before
    assert world.knowledge.technologies == knowledge_before
    assert not world.knowledge.knows(OWNER, "metallurgy")


def test_stolen_metallurgy_unlocks_a_paid_local_production_upgrade():
    world, _agent = prepared_world()
    # Auren has an authored local iron site and can start the base line, but
    # lacks the technique needed to apply the efficient-furnace upgrade.
    site = world.map.infrastructure_sites["passagem-negra"]
    assert site.owner_ref == OWNER and "iron_production" in site.capability_ids
    source = world.economy.facilities["works:minas-de-ferroalto"]
    world.economy.facilities["works:passagem-negra-iron"] = source.model_copy(update={
        "id": "works:passagem-negra-iron", "site_id": site.id, "stock_id": "stock:pontenegro",
        "payroll_account_id": "treasury:auren", "max_batches": 20,
        "last_batches": 0, "last_event_id": None})
    for local_group in tuple(world.society.population.values()):
        if local_group.settlement_id == "pontenegro" and local_group.occupation == "farmer":
            world.society.population[local_group.id] = local_group.model_copy(update={"occupation": "artisan"})
    stock = world.economy.stocks["stock:pontenegro"]
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "wood": max(100, stock.goods.get("wood", 0)),
                  "tools": max(20, stock.goods.get("tools", 0))}})
    account = world.economy.accounts["treasury:auren"]
    world.economy.accounts[account.id] = account.model_copy(update={
        "balance": max(10_000, account.balance)})

    facility_id = "works:passagem-negra-iron"
    assert not world.knowledge.knows(OWNER, "metallurgy")
    blocked_decision = record_event(
        world, "expansion_decided", "Tentativa de aplicar a técnica antes de obtê-la.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}},
        decision={"action": "expand", "actor_ref": OWNER.to_dict(),
                  "facility_id": facility_id, "blueprint_id": "efficient-furnaces"})
    before_blocked_application = world_snapshot(world)
    with pytest.raises(ValueError, match="technical knowledge"):
        start_expansion(world, facility_id, "efficient-furnaces",
                        decision_event_id=blocked_decision.id)
    assert world_snapshot(world) == before_blocked_application

    theft_option = next(option for option in technology_theft_options(world, OWNER)
                        if option.technology_id == "metallurgy")
    finding = execute_technology_theft(world, OWNER, theft_option.id,
                                       decide(world, theft_option).id)
    assert finding.result == "success"
    learned = next(item for item in world.knowledge.technologies.values()
                   if item.owner_ref == OWNER and item.technology_id == "metallurgy")

    # The source knowledge receipt is current at day 150.  The buyer's line
    # then operates the next day without borrowing same-day payroll capacity.
    world.clock = world.clock.advance(1)
    produce_monthly(world)
    facility = world.economy.facilities[facility_id]
    assert facility.last_batches > 0
    before_iron = world.economy.stocks["stock:pontenegro"].goods.get("iron", 0)
    application = next(option for option in expansion_options(world, OWNER)
                       if option.facility_id == facility_id
                       and option.blueprint_id == "efficient-furnaces")
    selection = record_event(
        world, "expansion_decided", "Selecionar a aplicação de fornos eficientes.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_source": {"kind": "api"}}, decision=application.decision())
    material_terms = {"action": "expand", "actor_ref": OWNER.to_dict(),
                      "facility_id": facility_id, "blueprint_id": "efficient-furnaces"}
    receipt = record_event(world, "expansion_authorized", "O owner revalidou a aplicação local.",
                           fact_kind=FactKind.DECISION, decision=material_terms,
                           cause_ids=(selection.id,))
    project = start_expansion(world, facility_id, "efficient-furnaces",
                              decision_event_id=receipt.id)
    before_materials = dict(world.economy.stocks["stock:pontenegro"].goods)
    before_cash = world.economy.accounts["treasury:auren"].balance
    for day in (180, 210, 240, 270, 300):
        world.clock = WorldClock(day)
        progress_expansions(world, monthly_workforce(world))

    assert world.economy.expansions[project.id].stage == "completed", project
    facility = world.economy.facilities[facility_id]
    assert facility.recipe_id == "efficient_ironworking"
    stock = world.economy.stocks["stock:pontenegro"]
    assert stock.goods["wood"] < before_materials["wood"]
    assert stock.goods["tools"] < before_materials["tools"]
    assert world.economy.accounts["treasury:auren"].balance < before_cash
    completion = world.economy.expansions[project.id].last_event_id
    started = world.event_index()[project.last_event_id]
    assert learned.event_id in {link.cause_event_id for link in started.causal_links}

    world.clock = WorldClock(330)
    produce_monthly(world)
    stock = world.economy.stocks["stock:pontenegro"]
    assert stock.goods["iron"] - before_iron > 0
    facility = world.economy.facilities[facility_id]
    operation = world.event_index()[facility.last_event_id]
    assert operation.event_type == "production_completed"
    assert operation.causal_payload["production"]["recipe_id"] == "efficient_ironworking"
    assert operation.causal_payload["production"]["batches"] > 0
    assert completion in {link.cause_event_id for link in operation.causal_links}
