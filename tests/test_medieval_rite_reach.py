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
    refresh_settlement_reports(world)
    return world.society.characters[character.id]


def test_reach_is_one_real_segment_and_the_road_revokes_it(tmp_path):
    world, healer = reaching_world()
    goods, money, people = totals(world)
    blueprint = world.research.rite_blueprints[DISTANT]
    before_here = world.economy.needs[PLACE].health
    before_there = world.economy.needs[TARGET].health

    rite = start(world, healer.id, SPONSOR, DISTANT)
    assert rite.target_settlement_id == TARGET and rite.route_id == SEGMENT
    assert totals(world) == (goods, money, people), "starting consumes nothing"

    tick_to(world, rite.due_day)
    done = world.research.rites[rite.id]
    assert done.stage == "completed"
    assert world.economy.needs[TARGET].health == before_there + blueprint.health_gain_permille
    assert world.economy.needs[PLACE].health == before_here, "the reached place is the one relieved"
    assert world.society.settlements[TARGET].administrator_id == "auren"
    # Officiating spent a real person for a declared term.
    recovery = world.research.rite_recoveries[healer.id]
    assert recovery.until_day > world.clock.absolute_day and recovery.rite_id == rite.id
    assert not [item for item in rite_offer_options(world, healer.id)]
    path = tmp_path / "reach.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    # The same working again, with the segment closed before it resolves.
    tick_to(world, recovery.until_day)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    again = start(world, healer.id, SPONSOR, DISTANT)
    health_before = world.economy.needs[TARGET].health
    world.map.routes[SEGMENT].update_runtime(enabled=False)
    tick_to(world, again.due_day)
    failed = world.research.rites[again.id]
    assert failed.stage == "failed"
    assert "reach_lost" in next(item for item in world.events
                                if item.id == failed.last_event_id).content
    assert world.economy.needs[TARGET].health == health_before, "a closed road heals nobody"


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
    blocked = start(world, healer.id, SPONSOR, DISTANT)
    health_before = world.economy.needs[TARGET].health
    goods, money, people = totals(world)
    tick_to(world, blocked.due_day)
    failed = world.research.rites[blocked.id]
    assert failed.stage == "failed"
    assert "warded" in next(item for item in world.events if item.id == failed.last_event_id).content
    assert world.economy.needs[TARGET].health == health_before
    assert totals(world)[2] == people, "protection hurts nobody"
    assert totals(world)[1] == money, "and takes nothing from anyone"

    # Once the term runs out the same working reaches again.
    tick_to(world, ward.until_day)
    assert ward_active(world, TARGET) is None
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(GUARD, TARGET).warded is False
