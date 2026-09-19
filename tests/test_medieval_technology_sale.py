"""Focused causal tests for the paid technology-sale slice."""

from dataclasses import replace

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import monthly_workforce
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import progress_research, start_research
from src.sim.medieval.technology_sale import (execute_technology_sale,
                                               record_technology_sale_acceptance,
                                               record_technology_sale_request,
                                               technology_sale_acceptance_options,
                                               technology_sale_options)
from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure
from src.systems.time import WorldClock


BUYER = EntityRef("polity", "auren")
SELLER = EntityRef("polity", "escarlia")


def researched_world():
    world = create_medieval_world(73)
    lead = world.society.characters["character:011"]
    world.society.characters[lead.id] = lead.model_copy(
        update={"skills": lead.skills.model_copy(update={"craftsmanship": 40})})
    terms = {"technology_id": "metallurgy", "site_id": "minas-de-ferroalto",
             "stock_id": "stock:ferroalto", "account_id": "treasury:escarlia",
             "researcher_id": lead.id}
    sponsor = record_event(world, "research_decided", "Financiar a pesquisa.", fact_kind=FactKind.DECISION,
                           decision={**terms, "action": "research", "actor_ref": SELLER.to_dict()})
    worker = record_event(world, "research_accepted", "Aceitar trabalho.", fact_kind=FactKind.DECISION,
                          decision={**terms, "action": "research_work",
                                    "actor_ref": EntityRef("character", lead.id).to_dict()},
                          cause_ids=(sponsor.id,))
    start_research(world, **terms, sponsor_decision_id=sponsor.id, researcher_decision_id=worker.id)
    for day in (30, 60, 90):
        world.clock = WorldClock(day)
        progress_research(world, monthly_workforce(world))
    # The buyer must own a currently usable site for the capability it is buying.
    site = world.map.infrastructure_sites["passagem-negra"]
    world.map.infrastructure_sites[site.id] = replace(site, capability_ids=("iron_production",))
    sighting = next(item for item in disclosure_options(world, SELLER)
                    if item.recipient_ref == BUYER and item.technology_id == "metallurgy")
    disclosure_decision = record_event(world, "technology_disclosed", "Divulgar técnica.",
                                       fact_kind=FactKind.DECISION, decision=sighting.decision(),
                                       cause_ids=sighting.causes())
    execute_disclosure(world, sighting, disclosure_decision.id)
    return world


def test_sale_requires_capability_and_current_sighting_before_offer():
    world = researched_world()
    assert technology_sale_options(world, BUYER)
    world.knowledge.technology_sightings.clear()
    assert not technology_sale_options(world, BUYER)

    world = researched_world()
    site = world.map.infrastructure_sites["passagem-negra"]
    world.map.infrastructure_sites[site.id] = replace(site, capability_ids=("transport",))
    assert not technology_sale_options(world, BUYER)


def test_sale_revalidates_seller_consent_pays_and_persists_causal_evidence(tmp_path):
    world = researched_world()
    option = technology_sale_options(world, BUYER)[0]
    buyer_before = world.economy.accounts[option.buyer_account_id].balance
    seller_before = world.economy.accounts[option.seller_account_id].balance
    request = record_technology_sale_request(world, BUYER, option.id)
    acceptance_option = technology_sale_acceptance_options(world, SELLER)[0]
    acceptance = record_technology_sale_acceptance(world, SELLER, acceptance_option.id)

    receipt = execute_technology_sale(world, BUYER, option.id, request.id, acceptance.id)

    assert receipt.event_type == "technology_sale_completed"
    assert world.knowledge.knows(BUYER, "metallurgy")
    learned = next(item for item in world.knowledge.technologies.values()
                   if item.owner_ref == BUYER and item.technology_id == "metallurgy")
    assert learned.channel == "sale"
    assert world.economy.accounts[option.buyer_account_id].balance == buyer_before - option.amount
    assert world.economy.accounts[option.seller_account_id].balance == seller_before + option.amount
    payment_id = world.economy.payments[request.id]
    causes = {link.cause_event_id for link in receipt.causal_links}
    assert {request.id, acceptance.id, payment_id, learned.event_id,
            option.sighting_event_id, option.source_event_id} <= causes
    assert world.knowledge.knows(SELLER, "metallurgy")

    with pytest.raises(ValueError, match="already executed"):
        execute_technology_sale(world, BUYER, option.id, request.id, acceptance.id)
    path = tmp_path / "technology-sale.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_paid_knowledge_unlocks_a_material_production_project():
    world = researched_world()
    from src.sim.medieval.expansion import progress_expansions, start_expansion

    # Give the buyer a real ironworking line at a real owned site.  The sale
    # only transfers knowledge; this installation and its inputs remain
    # separate material prerequisites.
    site = world.map.infrastructure_sites["passagem-negra"]
    world.map.infrastructure_sites[site.id] = replace(site, capability_ids=("iron_production",))
    source = world.economy.facilities["works:minas-de-ferroalto"]
    world.economy.facilities["works:passagem-negra-iron"] = source.model_copy(update={
        "id": "works:passagem-negra-iron", "site_id": "passagem-negra", "stock_id": "stock:pontenegro",
        "payroll_account_id": "treasury:auren", "last_event_id": None, "last_batches": 0,
        "last_limitations": ()})
    local_group = next(group for group in world.society.population.values()
                       if group.settlement_id == "pontenegro")
    world.society.population[local_group.id] = local_group.model_copy(update={"occupation": "artisan"})

    option = technology_sale_options(world, BUYER)[0]
    request = record_technology_sale_request(world, BUYER, option.id)
    acceptance = record_technology_sale_acceptance(world, SELLER,
        technology_sale_acceptance_options(world, SELLER)[0].id)
    execute_technology_sale(world, BUYER, option.id, request.id, acceptance.id)
    assert world.knowledge.knows(BUYER, "metallurgy")

    expansion_decision = record_event(
        world, "expansion_decided", "Aplicar a metalurgia adquirida na linha local.",
        fact_kind=FactKind.DECISION,
        decision={"action": "expand", "actor_ref": BUYER.to_dict(),
                  "facility_id": "works:passagem-negra-iron", "blueprint_id": "efficient-furnaces"},
    )
    project = start_expansion(world, "works:passagem-negra-iron", "efficient-furnaces",
                              decision_event_id=expansion_decision.id)
    assert project.stage == "waiting"
    start_day = world.clock.absolute_day
    for day in (start_day + 30, start_day + 60, start_day + 90, start_day + 120, start_day + 150):
        world.clock = WorldClock(day)
        progress_expansions(world, monthly_workforce(world))
    assert world.economy.expansions[project.id].stage == "completed"
    assert world.economy.facilities["works:passagem-negra-iron"].recipe_id == "efficient_ironworking"
    receipt = next(event for event in reversed(world.events)
                   if event.event_type == "expansion_progressed" and project.id in {
                       delta.owner_id for delta in event.deltas})
    sale = next(event for event in world.events if event.event_type == "technology_sale_completed")
    learned = next(item for item in world.knowledge.technologies.values()
                   if item.owner_ref == BUYER and item.technology_id == "metallurgy")
    events = {event.id: event for event in world.events}
    assert learned.event_id in {link.cause_event_id for link in sale.causal_links}
    assert learned.event_id in {link.cause_event_id
                                for link in next(event for event in world.events
                                                 if event.event_type == "expansion_started").causal_links}


@pytest.mark.parametrize("missing", ["funds", "seller_capability", "authority"])
def test_sale_never_spends_or_teaches_when_a_material_gate_disappears(missing):
    world = researched_world()
    option = technology_sale_options(world, BUYER)[0]
    request = record_technology_sale_request(world, BUYER, option.id)
    acceptance = record_technology_sale_acceptance(
        world, SELLER, technology_sale_acceptance_options(world, SELLER)[0].id)
    if missing == "funds":
        account = world.economy.accounts[option.buyer_account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    elif missing == "seller_capability":
        site = world.map.infrastructure_sites[option.seller_site_id]
        world.map.infrastructure_sites[site.id] = replace(site, capability_ids=("transport",))
    else:
        world.authority.offices = {key: office for key, office in world.authority.offices.items()
                                   if office.institution_ref != SELLER}
    balances = dict(world.economy.accounts)
    with pytest.raises(ValueError):
        execute_technology_sale(world, BUYER, option.id, request.id, acceptance.id)
    assert world.economy.accounts == balances
    assert not world.knowledge.knows(BUYER, "metallurgy")
