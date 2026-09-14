"""Presence is material and revocable; it never becomes administration."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (disband_detachment, force_options, occupy_settlement, raise_detachment,
                                    raise_options)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports

OWNER = EntityRef("polity", "auren")
HOME = "campomanso"


def decide(world, option):
    return record_event(world, "force_decided", "Decisão militar institucional.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def soldier_world(count=20):
    """Prepared garrison: Auren keeps a real soldier cohort at Campomanso."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    world.society.population[f"pop:{HOME}:{group.people}:soldier"] = group.model_copy(
        update={"id": f"pop:{HOME}:{group.people}:soldier", "occupation": "soldier", "count": count})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    return world


def food_total(world):
    return (sum(item.goods.get("food", 0) for item in world.economy.stocks.values())
            + sum(item.provisions for item in world.society.detachments.values() if item.stage != "disbanded")
            + sum(item.quantity for item in world.economy.parcels.values()
                  if world.economy.freight_orders[item.order_id].resource_id == "food"))


def people_total(world):
    return sum(item.count for item in world.society.population.values())


def tick(world, days=1):
    for _ in range(days):
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


TARGET = "salgueiro"


def raised(world, destination=TARGET):
    option = next(item for item in raise_options(world, OWNER) if item.destination_id == destination)
    return option, raise_detachment(world, OWNER, option.id, decide(world, option).id)


def test_a_supplied_force_marches_and_occupies_without_taking_administration(tmp_path):
    world = soldier_world()
    food, people = food_total(world), people_total(world)
    money = sum(item.balance for item in world.economy.accounts.values())
    target = world.society.settlements[TARGET]
    owners = {key: item.owner_ref for key, item in world.economy.stocks.items()}
    sites = {key: (item.owner_ref, item.maintainer_ref) for key, item in world.map.infrastructure_sites.items()}
    taxes = {key: (item.account_id, item.income_rate) for key, item in world.authority.tax_policies.items()}

    option, detachment = raised(world)
    # Provisions left the local stock for the column; nothing was created.
    assert detachment.stage == "marching" and detachment.provisions == option.provisions
    assert world.society.available_count(option.group_id) == 0, "raised soldiers are not locally available"
    assert food_total(world) == food and people_total(world) == people
    assert sum(item.balance for item in world.economy.accounts.values()) == money, "wages moved, never appeared"
    assert all(item.kind != "occupy" for item in force_options(world, OWNER))

    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    current = world.society.detachments[detachment.id]
    assert current.location_id == TARGET and current.provisions < option.provisions
    # The only food that left the world is the ration the column recorded eating.
    eaten = option.provisions - current.provisions
    assert eaten > 0 and food_total(world) == food - eaten
    assert people_total(world) == people
    assert world.society.settlements[TARGET].occupier_id is None, "arrival alone occupies nothing"
    assert world.knowledge.settlement_report(OWNER, TARGET) is not None, "presence is observation"

    marched_food = food_total(world)
    balances = {key: item.balance for key, item in world.economy.accounts.items()}
    goods = {key: dict(item.goods) for key, item in world.economy.stocks.items()}
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)

    held = world.society.settlements[TARGET]
    assert held.occupier_id == OWNER.id
    assert held.administrator_id == target.administrator_id and held.claimant_ids == target.claimant_ids
    # A present force now has its own bounded campaign bag.  Occupation still
    # cannot change the ownership of any stock that already existed.
    assert {key: world.economy.stocks[key].owner_ref for key in owners} == owners
    assert {key: dict(item.goods) for key, item in world.economy.stocks.items()} == goods
    assert {key: item.balance for key, item in world.economy.accounts.items()} == balances
    assert {key: (item.owner_ref, item.maintainer_ref) for key, item in world.map.infrastructure_sites.items()} == sites
    assert {key: (item.account_id, item.income_rate) for key, item in world.authority.tax_policies.items()} == taxes
    assert food_total(world) == marched_food, "occupying consumes nothing"
    assert people_total(world) == people
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(EntityRef("polity", target.administrator_id),
                                             TARGET).occupier_id == OWNER.id
    path = tmp_path / "force.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_presence_without_means_or_mandate_takes_nothing():
    world = soldier_world()
    option = next(item for item in raise_options(world, OWNER) if item.destination_id == TARGET)

    # No military mandate, no force at all.
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "military")})
    assert not raise_options(world, OWNER)
    with pytest.raises(ValueError):
        raise_detachment(world, OWNER, option.id, decide(world, option).id)
    world.authority.offices[office.id] = office

    option, detachment = raised(world)
    before = world_snapshot(world)
    # Forged and replayed selections are refused atomically.
    with pytest.raises(ValueError, match="stale|unknown"):
        raise_detachment(world, OWNER, option.id + ":forged", decide(world, option).id)
    with pytest.raises(ValueError):
        raise_detachment(world, OWNER, option.id, world.society.detachments[detachment.id].decision_event_id)
    assert world_snapshot(world)["event_count"] == before["event_count"] + 1

    # While the column is still marching there is nothing to occupy.
    assert all(item.kind != "occupy" for item in force_options(world, OWNER))
    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")

    # A rival column arrived after the report this option was built on. The
    # actor still sees the option; the material owner refuses it, and says
    # nothing about who is there.
    standing = world.society.detachments[detachment.id]
    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    rival = standing.model_copy(update={
        "id": "detachment:rival", "owner_ref": EntityRef("polity", "escarlia"),
        "source_group_id": rival_group.id, "count": 5, "provisions": 5,
        "route_ids": (), "route_index": 0, "stage": "present", "destination_id": TARGET})
    world.society.detachments[rival.id] = rival
    world.society.validate(set(world.map.regions), world)
    assert any(item.kind == "occupy" for item in force_options(world, OWNER)), "knowledge did not change"
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="no longer possible"):
        occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    assert world.society.settlements[TARGET].occupier_id is None
    assert world_snapshot(world)["event_count"] == before["event_count"] + 1
    del world.society.detachments[rival.id]

    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    assert world.society.settlements[TARGET].occupier_id == OWNER.id

    # Provisions run out: the presence lapses by its own fact and frees the place.
    people = people_total(world)
    while world.society.detachments[detachment.id].stage != "disbanded":
        tick(world)
    assert world.society.settlements[TARGET].occupier_id is None
    assert people_total(world) == people
    assert any(item.event_type == "detachment_lapsed" for item in world.events)
    assert not any(item.event_type in {"battle_resolved", "casualties_taken"} for item in world.events)
    assert world.society.available_count(option.group_id) >= 0
