"""A technique travels with a person who moved, and still buys no installation."""

from dataclasses import replace

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.apprenticeship import (apprenticeship_sponsor_options, record_apprenticeship_offer,
                                             _has_migrated, resolve_apprenticeships, specialist_offer_options,
                                             sponsor_apprenticeship)
from src.sim.medieval.economy import _delta, monthly_workforce
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import progress_research, start_research
from src.systems.time import WorldClock

HOST = EntityRef("polity", "valedouro")
ORIGIN = EntityRef("polity", "auren")
TECHNOLOGY = "irrigation"


def decide(world, option, event_type="apprenticeship_decided"):
    return record_event(world, event_type, "Decisão institucional de instrução.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def specialist_of(world, settlement_id):
    return next(character for character in sorted(world.society.characters.values(), key=lambda c: c.id)
                if character.death_day is None and character.location_id == settlement_id)


def trained_specialist_world():
    """Auren completes irrigation with a local specialist; Valedouro knows nothing."""
    world = create_medieval_world(73)
    lead = specialist_of(world, "campomanso")
    world.society.characters[lead.id] = lead.model_copy(
        update={"skills": lead.skills.model_copy(update={"craftsmanship": 40})})
    terms = {"technology_id": TECHNOLOGY, "site_id": "campos-do-lume", "stock_id": "stock:campomanso",
             "account_id": "treasury:auren", "researcher_id": lead.id}
    sponsor = record_event(world, "research_decided", "Financiar pesquisa.", fact_kind=FactKind.DECISION,
                           decision={**terms, "action": "research", "actor_ref": ORIGIN.to_dict()})
    accepted = record_event(world, "research_accepted", "Aceitar trabalho.", fact_kind=FactKind.DECISION,
                            decision={**terms, "action": "research_work",
                                      "actor_ref": EntityRef("character", lead.id).to_dict()},
                            cause_ids=(sponsor.id,))
    start_research(world, **terms, sponsor_decision_id=sponsor.id, researcher_decision_id=accepted.id)
    for day in (30, 60, 90):
        world.clock = WorldClock(day)
        progress_research(world, monthly_workforce(world))
    assert world.knowledge.knows(ORIGIN, TECHNOLOGY) and not world.knowledge.knows(HOST, TECHNOLOGY)
    return world, world.society.characters[lead.id]


def hosting_world():
    """Prepared complex: Valedouro keeps a real farm at Salgueiro, and the
    specialist physically relocates there with a recorded material fact."""
    world, lead = trained_specialist_world()
    site = world.map.infrastructure_sites["bosques-de-salgueiro"]
    world.map.infrastructure_sites[site.id] = replace(
        site, capability_ids=(*site.capability_ids, "food_production", "water_management"))
    farm = world.economy.facilities["works:campos-do-lume"]
    world.economy.facilities["works:salgueiro-farm"] = farm.model_copy(update={
        "id": "works:salgueiro-farm", "site_id": "bosques-de-salgueiro", "stock_id": "stock:salgueiro",
        "payroll_account_id": "treasury:valedouro", "last_event_id": None, "last_batches": 0,
        "last_limitations": ()})
    group = world.society.population[lead.population_group_id]
    record_event(world, "migration_arrived", "Um especialista chegou por uma jornada material.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("character", lead.id, "location_id", lead.location_id, "salgueiro"),
                         _delta("character", lead.id, "population_group_id", lead.population_group_id,
                                f"pop:salgueiro:{group.people}:{group.occupation}")))
    world.society.transfer_people(group.id, "salgueiro", group.occupation, 1, character_ids=(lead.id,))
    world.economy.validate(world)
    return world, world.society.characters[lead.id]


def test_arbitrary_relocation_receipt_does_not_count_as_migration():
    world, lead = trained_specialist_world()
    record_event(world, "specialist_relocated", "Um especialista mudou de residência.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("character", lead.id, "location_id", lead.location_id, "salgueiro"),))
    assert not _has_migrated(world, lead, "salgueiro")


def contracted(world, specialist):
    offer_option = next(item for item in specialist_offer_options(world, specialist.id)
                        if item.technology_id == TECHNOLOGY)
    offer = record_apprenticeship_offer(world, specialist.id, offer_option.id)
    sponsor_option = next(item for item in apprenticeship_sponsor_options(world, HOST)
                          if item.offer_event_id == offer.id)
    contract = sponsor_apprenticeship(world, HOST, sponsor_option.id, decide(world, sponsor_option).id)
    return offer, sponsor_option, contract


def expand(world, facility_id="works:salgueiro-farm", blueprint_id="irrigation-works"):
    from src.sim.medieval.expansion import start_expansion
    decision = record_event(world, "expansion_decided", "Autorizar obra.", fact_kind=FactKind.DECISION,
                            decision={"action": "expand", "actor_ref": HOST.to_dict(),
                                      "facility_id": facility_id, "blueprint_id": blueprint_id})
    return start_expansion(world, facility_id, blueprint_id, decision_event_id=decision.id)


def test_a_migrated_specialist_instructs_for_real_wages_before_any_technique_exists(tmp_path):
    world, specialist = hosting_world()
    with pytest.raises(ValueError, match="knowledge"):
        expand(world)

    offer, sponsor_option, contract = contracted(world, specialist)
    assert offer.fact_kind == FactKind.DECISION and not offer.deltas
    assert contract.stage == "training" and contract.due_day == contract.started_day + 30
    assert not world.knowledge.knows(HOST, TECHNOLOGY), "sponsorship grants no technique"
    balance = world.economy.accounts["treasury:valedouro"].balance
    recipes = {key: item.recipe_id for key, item in world.economy.facilities.items()}
    with pytest.raises(ValueError, match="knowledge"):
        expand(world)

    world.clock = world.clock.advance(30)
    resolve_apprenticeships(world, world.agenda.pop_due(world.clock.absolute_day))

    assert world.research.apprenticeships[contract.id].stage == "completed"
    assert world.knowledge.knows(HOST, TECHNOLOGY)
    assert world.knowledge.knows(ORIGIN, TECHNOLOGY), "the origin keeps its own knowledge"
    learned = next(item for item in world.knowledge.technologies.values()
                   if item.owner_ref == HOST and item.technology_id == TECHNOLOGY)
    assert learned.channel == "apprenticeship"
    receipt = next(item for item in world.events if item.id == learned.event_id)
    assert receipt.event_type == "technology_apprenticed"
    assert world.economy.accounts["treasury:valedouro"].balance < balance, "instruction was paid"
    assert world.economy.payrolls[contract.id].gross == contract.workers * contract.wage_per_worker
    assert {key: item.recipe_id for key, item in world.economy.facilities.items()} == recipes

    # The technique only makes the work possible; capacity still needs the work.
    project = expand(world)
    assert project.stage == "waiting" and project.completed_units == 0
    assert world.economy.facilities["works:salgueiro-farm"].recipe_id == recipes["works:salgueiro-farm"]
    path = tmp_path / "apprenticeship.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_irrigation_application_requires_authored_water_management_capacity():
    world, specialist = hosting_world()
    offer, sponsor_option, contract = contracted(world, specialist)
    world.clock = world.clock.advance(30)
    resolve_apprenticeships(world, world.agenda.pop_due(world.clock.absolute_day))
    site = world.map.infrastructure_sites["bosques-de-salgueiro"]
    world.map.infrastructure_sites[site.id] = replace(
        site, capability_ids=tuple(capability for capability in site.capability_ids
                                   if capability != "water_management"))

    with pytest.raises(ValueError, match="site capabilities|capable site"):
        expand(world)


def test_no_shortcut_grants_the_technique():
    world, specialist = hosting_world()
    offer_option = next(item for item in specialist_offer_options(world, specialist.id)
                        if item.technology_id == TECHNOLOGY)

    # A resident who is not qualified offers nothing at all.
    poor = world.society.characters[specialist.id]
    world.society.characters[poor.id] = poor.model_copy(
        update={"skills": poor.skills.model_copy(update={"craftsmanship": 1})})
    assert not specialist_offer_options(world, specialist.id)
    world.society.characters[poor.id] = poor

    offer = record_apprenticeship_offer(world, specialist.id, offer_option.id)
    sponsor_option = next(item for item in apprenticeship_sponsor_options(world, HOST)
                          if item.offer_event_id == offer.id)
    before = world_snapshot(world)

    # The specialist cannot sponsor itself, and a forged option is refused.
    self_decision = record_event(world, "apprenticeship_decided", "Autopatrocínio.", fact_kind=FactKind.DECISION,
                                 decision={"action": "sponsor_apprenticeship",
                                           "actor_ref": EntityRef("character", specialist.id).to_dict(),
                                           "selected_affordance_id": sponsor_option.id})
    with pytest.raises(ValueError):
        sponsor_apprenticeship(world, HOST, sponsor_option.id, self_decision.id)
    forged = decide(world, sponsor_option)
    with pytest.raises(ValueError, match="stale|unknown"):
        sponsor_apprenticeship(world, HOST, sponsor_option.id + ":forged", forged.id)
    assert not world.knowledge.knows(HOST, TECHNOLOGY)
    assert world_snapshot(world)["event_count"] == before["event_count"] + 2

    contract = sponsor_apprenticeship(world, HOST, sponsor_option.id, forged.id)
    # A used decision cannot be replayed, and an occupied specialist offers nothing.
    with pytest.raises(ValueError):
        sponsor_apprenticeship(world, HOST, sponsor_option.id, forged.id)
    assert not specialist_offer_options(world, specialist.id)

    # A specialist who left before the dated completion earns no technique.
    world.clock = world.clock.advance(30)
    moved = world.society.characters[specialist.id]
    world.society.characters[moved.id] = moved.model_copy(update={"location_id": "campomanso"})
    resolve_apprenticeships(world, world.agenda.pop_due(world.clock.absolute_day))
    assert world.research.apprenticeships[contract.id].stage == "failed"
    assert not world.knowledge.knows(HOST, TECHNOLOGY)
    assert contract.id not in world.economy.payrolls


def test_migrated_artisan_can_carry_source_institution_knowledge_without_research_credit():
    world, lead = hosting_world()
    artisan = next(character for character in world.society.characters.values()
                   if character.id != lead.id and character.location_id == "campomanso"
                   and character.death_day is None)
    artisan = artisan.model_copy(update={"skills": artisan.skills.model_copy(update={"craftsmanship": 40})})
    world.society.characters[artisan.id] = artisan
    source_group = world.society.population[artisan.population_group_id]
    record_event(world, "migration_arrived", "Um artesão chegou com prática da instituição de origem.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("character", artisan.id, "location_id", artisan.location_id, "salgueiro"),
                         _delta("character", artisan.id, "population_group_id", artisan.population_group_id,
                                f"pop:salgueiro:{source_group.people}:{source_group.occupation}")))
    world.society.transfer_people(source_group.id, "salgueiro", source_group.occupation, 1,
                                  character_ids=(artisan.id,))
    option = next(item for item in specialist_offer_options(world, artisan.id)
                  if item.technology_id == TECHNOLOGY)
    assert option.source_event_ids
    offer = record_apprenticeship_offer(world, artisan.id, option.id)
    assert {link.cause_event_id for link in offer.causal_links} == set(option.source_event_ids)
