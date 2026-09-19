"""Reach is one real road, recovery is a real person, protection is a fact."""

from src.classes.mechanical_language import EntityRef
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.rites import (record_rite_offer, rite_offer_options, rite_sponsor_options,
                                    sponsor_rite, ward_active)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.route_intelligence import refresh_route_reports
from tests.test_medieval_rites import PLACE, SPONSOR, ailing_world, decide, tick_to, totals

DISTANT = "rite-of-distant-mending"
WARDING = "rite-of-warding"
COUNTERMEASURE = "rite-of-river-countermeasure"
FLOOD_CONTROL = "rite-of-flood-control"
SERPENT_COUNTERMEASURE = "rite-of-serpent-countermeasure"
TARGET = "pontenegro"
SEGMENT = "road-pedraclara-pontenegro"
GUARD = EntityRef("polity", "auren")


def reaching_world(target_health=700):
    """Pedraclara keeps a strong healer; Pontenegro is the ailing neighbour."""
    world, healer = ailing_world()
    need = world.economy.needs[TARGET]
    world.economy.needs[TARGET] = need.model_copy(update={"health": target_health})
    stock = world.economy.stocks["stock:ordem-da-aurora"]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "reagents": 40, "crystals": 20}})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    return world, healer


def test_rite_blueprint_exposes_engine_owned_school_cost_range_and_duration():
    world, _ = reaching_world()
    ward = world.research.rite_blueprints[WARDING]
    distant = world.research.rite_blueprints[DISTANT]

    assert (ward.school, ward.range, ward.duration_days) == ("protection", "local", ward.ward_days)
    assert ward.cost == dict(ward.inputs)
    assert ward.resistance_capability_id == "standing_ward"
    assert (distant.school, distant.range, distant.duration_days) == ("restoration", "adjacent", distant.days)


def test_countermeasure_ward_exposes_a_distinct_engine_owned_resistance_profile():
    world, _ = reaching_world()
    countermeasure = world.research.rite_blueprints[COUNTERMEASURE]
    assert countermeasure.school == "countermeasure"
    assert countermeasure.resistance_capability_id == "river_countermeasure"
    assert countermeasure.duration_days == countermeasure.ward_days


def test_flood_control_is_a_material_ward_profile_not_a_narrative_override():
    world, _ = reaching_world()
    flood_control = world.research.rite_blueprints[FLOOD_CONTROL]

    assert flood_control.school == "countermeasure"
    assert flood_control.resistance_capability_id == "flood_control"
    assert flood_control.cost == dict(flood_control.inputs)
    assert flood_control.duration_days == 30


def test_serpent_countermeasure_is_an_authored_hazard_specific_ward():
    world, _ = reaching_world()
    countermeasure = world.research.rite_blueprints[SERPENT_COUNTERMEASURE]

    assert countermeasure.school == "countermeasure"
    assert countermeasure.resistance_capability_id == "serpent_countermeasure"
    assert countermeasure.range == "local"
    assert countermeasure.duration_days == 40
    assert countermeasure.cost == dict(countermeasure.inputs)


def start(world, officiant_id, sponsor, blueprint_id):
    option = next(item for item in rite_offer_options(world, officiant_id)
                  if item.sponsor_ref == sponsor and item.blueprint_id == blueprint_id)
    offer = record_rite_offer(world, officiant_id, option.id)
    sponsored = next(item for item in rite_sponsor_options(world, sponsor)
                     if item.offer_event_id == offer.id)
    return sponsor_rite(world, sponsor, sponsored.id, decide(world, sponsored).id)


def warder(world, skill=40):
    """A qualified resident of the neighbour, moved by the canonical owner."""
    character = next(item for item in sorted(world.society.characters.values(), key=lambda c: c.id)
                     if item.death_day is None and item.location_id != TARGET)
    group = world.society.population[character.population_group_id]
    world.society.transfer_people(group.id, TARGET, group.occupation, 1, character_ids=(character.id,))
    moved = world.society.characters[character.id]
    world.society.characters[character.id] = moved.model_copy(
        update={"skills": moved.skills.model_copy(update={"protection_magic": skill})})
    stock = world.economy.stocks[f"stock:{TARGET}"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "reagents": 40}})
    target_group = next(group for group in world.society.population.values()
                        if group.settlement_id == TARGET)
    world.society.population[target_group.id] = target_group.model_copy(update={"occupation": "artisan"})
    refresh_settlement_reports(world)
    return world.society.characters[character.id]


def test_distant_rite_requires_the_sponsor_to_know_the_route():
    world, healer = reaching_world()
    before = totals(world)
    offers = rite_offer_options(world, healer.id)

    # The local order owns a healing site and stock, but it is not an endpoint
    # administration. Route knowledge is therefore absent and no distant rite
    # affordance may be fabricated for it.
    assert not any(item.sponsor_ref == SPONSOR and item.blueprint_id == DISTANT
                   for item in offers)
    assert totals(world) == before


def test_organization_without_endpoint_route_knowledge_gets_no_distant_affordance():
    """A local site does not grant an organization omniscient route knowledge."""
    world, healer = reaching_world()
    offers = rite_offer_options(world, healer.id)
    assert offers
    assert not any(item.sponsor_ref == SPONSOR and item.blueprint_id == DISTANT
                   for item in offers)


def test_a_ward_is_a_fact_and_not_a_contest():
    world, healer = reaching_world()
    guardian = warder(world)

    ward_rite = start(world, guardian.id, GUARD, WARDING)
    assert ward_rite.settlement_id == TARGET and ward_rite.target_settlement_id is None
    tick_to(world, ward_rite.due_day)
    assert world.research.rites[ward_rite.id].stage == "completed"
    ward = ward_active(world, TARGET)
    assert ward is not None and ward.sponsor_ref == GUARD
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(GUARD, TARGET).warded is True
    assert world.knowledge.settlement_report(SPONSOR, PLACE).warded is False

    refresh_route_reports(world)
    # The order still cannot act at a distance merely because another polity's
    # ward became visible. It has neither the route bulletin nor a route
    # affordance, and no material state changes occur.
    before = totals(world)
    assert not any(item.sponsor_ref == SPONSOR and item.blueprint_id == DISTANT
                   for item in rite_offer_options(world, healer.id))
    assert totals(world) == before

    # Once the term runs out the same working reaches again.
    tick_to(world, ward.until_day)
    assert ward_active(world, TARGET) is None
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(GUARD, TARGET).warded is False
