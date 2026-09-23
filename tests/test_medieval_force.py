"""Presence is material and revocable; it never becomes administration."""

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (disband_detachment, establish_garrison, force_options, garrison_options,
                                    occupy_settlement, raise_detachment, raise_options, rotate_garrison,
                                    withdraw_garrison)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.territorial_control import territorial_control_options

OWNER = EntityRef("polity", "auren")
HOME = "campomanso"
# Auren already administers this settlement without occupying it: the seat
# for a "defend" garrison that never needs an occupation fact.
OWN_TARGET = "pedraclara"


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


def test_held_column_cites_the_physical_route_closure():
    world = soldier_world()
    option, detachment = raised(world)
    route_id = option.route_ids[0]
    closure = record_event(
        world, "route_closed_for_test", "A passagem foi fechada por causa externa.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("route", route_id, "enabled", True, False),))
    world.map.routes[route_id].update_runtime(enabled=False)

    tick(world)
    held = next(event for event in reversed(world.events)
                if event.event_type == "detachment_held" and
                any(delta.owner_id == detachment.id for delta in event.deltas))
    assert closure.id in {link.cause_event_id for link in held.causal_links}
    assert world.society.detachments[detachment.id].route_index == 0


def marched_home(world, destination=OWN_TARGET):
    option, detachment = raised(world, destination=destination)
    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    refresh_settlement_reports(world)
    return option, world.society.detachments[detachment.id]


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


def test_supplied_occupation_can_establish_and_lose_garrison_for_lack_of_treasury(tmp_path):
    world = soldier_world()
    option, detachment = raised(world)
    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)

    garrison = next(item for item in garrison_options(world, OWNER))
    account = world.economy.accounts[garrison.account_id]
    balance = account.balance
    household_before = world.economy.accounts.get(
        f"household:{detachment.source_group_id}",
    ).balance
    establish_garrison(world, OWNER, garrison.id, decide(world, garrison).id)
    garrison_id = f"garrison:{detachment.id}"
    assert world.society.garrisons[garrison_id].stage == "active"
    establish_event = next(item for item in reversed(world.events)
                           if item.event_type == "garrison_established")
    establish_decision = next(item for item in world.events
                              if item.fact_kind is FactKind.DECISION
                              and item.decision
                              and item.decision.get("selected_affordance_id") == garrison.id)
    assert establish_event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert establish_event.causal_payload == {
        "decision_event_id": establish_decision.id,
        "actor_ref": OWNER.to_dict(), "selected_affordance_id": garrison.id,
    }

    tick(world)
    assert world.society.garrisons[garrison_id].stage == "active"
    assert world.economy.accounts[garrison.account_id].balance == balance - garrison.daily_wage
    household = world.economy.accounts[f"household:{detachment.source_group_id}"]
    assert household.balance == household_before + garrison.daily_wage
    assert any(item.event_type == "garrison_maintained" for item in world.events)

    world.economy.accounts[garrison.account_id] = world.economy.accounts[garrison.account_id].model_copy(update={"balance": 0})
    tick(world)
    assert world.society.garrisons[garrison_id].stage == "lapsed"
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.detachments[detachment.id].stage == "present"
    assert any(item.event_type == "garrison_lapsed" for item in world.events)

    path = tmp_path / "garrison.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_defend_garrison_is_available_at_the_actors_own_settlement_without_occupation(tmp_path):
    world = soldier_world()
    option, detachment = marched_home(world)

    # No occupation is needed, offered or created at the actor's own,
    # already-administered settlement.
    assert world.society.settlements[OWN_TARGET].occupier_id is None
    assert all(item.kind != "occupy" for item in force_options(world, OWNER))

    garrison = next(item for item in garrison_options(world, OWNER) if item.kind == "defend")
    assert garrison.decision()["action"] == "establish_garrison"
    account = world.economy.accounts[garrison.account_id]
    balance = account.balance
    household_before = world.economy.accounts.get(
        f"household:{detachment.source_group_id}",
    ).balance
    establish_garrison(world, OWNER, garrison.id, decide(world, garrison).id)
    garrison_id = f"garrison:{detachment.id}"
    assert world.society.garrisons[garrison_id].stage == "active"
    # Establishing the defensive duty changed no occupation fact.
    assert world.society.settlements[OWN_TARGET].occupier_id is None
    # No administration is duplicated: an unoccupied, home-administered
    # settlement never offers territorial control, defend duty or not.
    assert not territorial_control_options(world, OWNER)

    tick(world)
    assert world.society.garrisons[garrison_id].stage == "active"
    assert world.economy.accounts[garrison.account_id].balance == balance - garrison.daily_wage
    household = world.economy.accounts[f"household:{detachment.source_group_id}"]
    assert household.balance == household_before + garrison.daily_wage
    assert any(item.event_type == "garrison_maintained" for item in world.events)

    world.economy.accounts[garrison.account_id] = world.economy.accounts[garrison.account_id].model_copy(
        update={"balance": 0})
    tick(world)
    assert world.society.garrisons[garrison_id].stage == "lapsed"
    assert world.society.detachments[detachment.id].stage == "present"
    assert any(item.event_type == "garrison_lapsed" for item in world.events)

    path = tmp_path / "defend-garrison.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_defend_garrison_decays_once_the_actor_no_longer_administers_the_settlement():
    world = soldier_world()
    option, detachment = marched_home(world)
    garrison = next(item for item in garrison_options(world, OWNER) if item.kind == "defend")
    establish_garrison(world, OWNER, garrison.id, decide(world, garrison).id)
    garrison_id = f"garrison:{detachment.id}"
    assert world.society.garrisons[garrison_id].stage == "active"

    # Administration of the settlement changes hands; the actor neither
    # occupies nor administers it any more, and there is no automatic defense.
    settlement = world.society.settlements[OWN_TARGET]
    world.society.settlements[OWN_TARGET] = settlement.model_copy(update={"administrator_id": "escarlia"})

    tick(world)
    assert world.society.garrisons[garrison_id].stage == "lapsed"
    assert world.society.detachments[detachment.id].stage == "present"
    assert any(item.event_type == "garrison_lapsed" for item in world.events)


def test_actor_can_withdraw_garrison_without_moving_column_or_administration():
    world = soldier_world()
    option, detachment = raised(world)
    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    current = world.society.detachments[detachment.id]
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    garrison = next(item for item in garrison_options(world, OWNER) if item.kind == "garrison")
    establish_garrison(world, OWNER, garrison.id, decide(world, garrison).id)
    withdrawal = next(item for item in garrison_options(world, OWNER) if item.kind == "withdraw")
    administrator = world.society.settlements[current.location_id].administrator_id
    withdraw_garrison(world, OWNER, withdrawal.id, decide(world, withdrawal).id)

    assert world.society.garrisons[f"garrison:{detachment.id}"].stage == "withdrawn"
    assert world.society.detachments[detachment.id].stage == "present"
    assert world.society.settlements[current.location_id].occupier_id == OWNER.id
    assert world.society.settlements[current.location_id].administrator_id == administrator
    withdrawal_event = next(item for item in reversed(world.events)
                            if item.event_type == "garrison_withdrawn")
    withdrawal_decision = next(item for item in world.events
                               if item.fact_kind is FactKind.DECISION
                               and item.decision
                               and item.decision.get("selected_affordance_id") == withdrawal.id)
    assert withdrawal_event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert withdrawal_event.causal_payload == {
        "decision_event_id": withdrawal_decision.id,
        "actor_ref": OWNER.to_dict(), "selected_affordance_id": withdrawal.id,
    }


def test_actor_can_rotate_a_paid_garrison_without_changing_control(tmp_path):
    world = soldier_world()
    option, current = raised(world)
    while world.society.detachments[current.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    establish = next(item for item in garrison_options(world, OWNER) if item.kind == "garrison")
    establish_garrison(world, OWNER, establish.id, decide(world, establish).id)

    group = next(item for item in world.society.population.values()
                 if item.settlement_id == HOME and item.occupation == "soldier")
    replacement_group = group.model_copy(update={"id": "pop:campomanso:orc:soldier", "people": "orc", "count": 5})
    world.society.population[replacement_group.id] = replacement_group
    arrival = record_event(world, "rotation_column_present", "Fixture de uma coluna de rotação abastecida.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("detachment", "detachment:rotation", "stage", None, "present"),))
    replacement = Detachment(
        id="detachment:rotation", owner_ref=OWNER, source_group_id=replacement_group.id,
        count=5, location_id=TARGET, destination_id=TARGET, provisions=5, stage="present",
        started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 1,
        decision_event_id=arrival.id, last_event_id=arrival.id)
    world.society.detachments[replacement.id] = replacement

    rotation = next(item for item in garrison_options(world, OWNER) if item.kind == "rotate")
    old_control = world.society.territorial_controls.get(f"territorial-control:{TARGET}")
    rotate_garrison(world, OWNER, rotation.id, decide(world, rotation).id)

    assert world.society.garrisons[f"garrison:{current.id}"].stage == "withdrawn"
    assert world.society.garrisons[f"garrison:{replacement.id}"].stage == "active"
    assert world.society.settlements[TARGET].occupier_id == OWNER.id
    assert world.society.territorial_controls.get(f"territorial-control:{TARGET}") == old_control
    event = next(item for item in reversed(world.events) if item.event_type == "garrison_rotated")
    rotation_decision = next(item for item in world.events
                             if item.fact_kind is FactKind.DECISION
                             and item.decision
                             and item.decision.get("selected_affordance_id") == rotation.id)
    assert event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert event.causal_payload == {
        "decision_event_id": rotation_decision.id,
        "actor_ref": OWNER.to_dict(), "selected_affordance_id": rotation.id,
    }
    assert any(delta.owner_id == f"garrison:{current.id}" and delta.after == "withdrawn"
               for delta in event.deltas)
    assert any(delta.owner_id == f"garrison:{replacement.id}" and delta.after == "active"
               for delta in event.deltas)
    path = tmp_path / "garrison-rotation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
