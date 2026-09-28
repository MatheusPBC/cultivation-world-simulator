"""Focused evidence for real commanders and delayed bounded doctrines."""

import asyncio

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.systems.calendar_agenda import ScheduledSituation
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.field_engagement import field_engagement_offer_options, field_strength
from src.sim.medieval.economy import _delta
from src.sim.medieval.force import raise_detachment, raise_options, withdraw_detachment, withdrawal_options
from src.sim.medieval.character_travel import is_traveling, travel_options
from src.sim.medieval.force_contact_policy import (COMMAND_REVIEW_KIND, REVIEW_KIND,
                                                   review_force_contacts, review_id)
from src.sim.medieval.force_command import (APPOINT_ACTION, SET_DOCTRINE_ACTION,
                                            appoint_detachment_commander, detachment_command_options,
                                            effective_doctrine, set_detachment_doctrine)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.medieval_ai_helpers import provider_selection_stub
from src.sim.medieval.route_intelligence import refresh_route_reports
from tests.test_medieval_field_engagement import OWNER, decide, prepared_challenger_world, tick
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.events import record_event


def _commanded_world():
    world, own_id, _, _ = prepared_challenger_world()
    # The catalog's real Auren commander has the required skill.  Setup places
    # that same existing person beside the already-real column; no character is
    # generated or cloned by the command executor.
    person = world.society.characters["character:002"]
    world.society.characters[person.id] = person.model_copy(update={"location_id": "salgueiro"})
    option = next(item for item in detachment_command_options(world, OWNER, detachment_id=own_id)
                  if item.decision()["action"] == APPOINT_ACTION)
    decision = decide(world, option)
    command = appoint_detachment_commander(world, OWNER, option.id, decision.id)
    receipt = world.event_index()[command.last_event_id]
    assert receipt.causal_origin.value == "actor_decision"
    assert receipt.causal_payload == {
        "decision_event_id": decision.id,
        "actor_ref": OWNER.to_dict(),
        "selected_affordance_id": option.id,
    }
    return world, own_id, person.id, command


def _set(world, detachment_id, doctrine):
    actor = EntityRef("character", world.society.detachment_commands[detachment_id].character_id)
    option = next(item for item in detachment_command_options(world, actor, detachment_id=detachment_id)
                  if item.decision()["action"] == SET_DOCTRINE_ACTION and item.doctrine == doctrine)
    decision = decide(world, option)
    command = set_detachment_doctrine(world, actor, option.id, decision.id)
    receipt = world.event_index()[command.last_event_id]
    assert receipt.causal_origin.value == "actor_decision"
    assert receipt.causal_payload == {
        "decision_event_id": decision.id,
        "actor_ref": actor.to_dict(),
        "selected_affordance_id": option.id,
    }
    return command


def _raised_with_commander(destination="salgueiro"):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    stock = next(item for item in world.economy.stocks.values()
                 if item.owner_ref == OWNER and item.location_id == "campomanso")
    food_before = stock.goods.get("food", 0)
    premise = record_event(
        world, "test_force_food_premise", "Premissa factual de rações da expedição.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("stock", stock.id, "food", food_before, food_before + 2000),))
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "food": food_before + 2000},
        "last_event_ids": {**stock.last_event_ids, "food": premise.id}})
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    soldiers_id = f"pop:campomanso:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 30})
    person = world.society.characters["character:002"]
    world.society.characters[person.id] = person.model_copy(update={"location_id": "campomanso"})
    refresh_settlement_reports(world)
    refresh_route_reports(world)

    raised = next(item for item in raise_options(world, OWNER, days=20)
                  if item.group_id == soldiers_id and item.destination_id == destination)
    detachment = raise_detachment(world, OWNER, raised.id, decide(world, raised).id, days=20)
    appointment = next(item for item in detachment_command_options(world, OWNER, detachment_id=detachment.id)
                       if item.character_id == person.id)
    command = appoint_detachment_commander(world, OWNER, appointment.id, decide(world, appointment).id)
    return world, detachment, person, command


def test_commander_attached_at_departure_travels_with_the_same_column(tmp_path):
    world, detachment, person, command = _raised_with_commander()

    assert is_traveling(world, person.id)
    assert travel_options(world, person.id) == ()
    assert world.society.characters[person.id].location_id == "campomanso"
    path = tmp_path / "commander-on-the-march.mws"
    save_world(world, path)
    world = load_world(path)
    assert world_snapshot(world) == world_snapshot(load_world(path))
    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)

    arrival = next(event for event in reversed(world.events) if event.event_type == "detachment_arrived"
                   and any(delta.owner_kind == "character" and delta.owner_id == person.id
                           for delta in event.deltas))
    assert world.society.characters[person.id].location_id == "salgueiro"
    assert command.id in world.society.detachment_commands
    assert not is_traveling(world, person.id)
    assert command.last_event_id in {link.cause_event_id for link in arrival.causal_links}


def test_expired_office_removes_tactical_authority_without_teleporting_marching_commander():
    world, detachment, person, command = _raised_with_commander(destination="ferroalto")
    office = world.authority.offices[command.office_id]
    world.authority.offices[office.id] = office.model_copy(
        update={"ends_day": world.clock.absolute_day + 1})
    assert len(detachment.route_ids) > 1

    tick(world)
    assert world.society.detachments[detachment.id].stage == "marching"
    assert command.id in world.society.detachment_commands
    assert is_traveling(world, person.id)
    assert detachment_command_options(world, EntityRef("character", person.id), detachment_id=detachment.id) == ()

    while world.society.detachments[detachment.id].stage == "marching":
        tick(world)
    assert world.society.characters[person.id].location_id == "ferroalto"
    assert command.id not in world.society.detachment_commands
    arrival = next(event for event in reversed(world.events) if event.event_type == "detachment_arrived"
                   and any(delta.owner_kind == "character" and delta.owner_id == person.id
                           for delta in event.deltas))
    released = next(event for event in reversed(world.events)
                    if event.event_type == "detachment_commander_released")
    assert arrival.id in {link.cause_event_id for link in released.causal_links}


def test_marching_commander_personally_observes_only_routes_at_a_physical_block(tmp_path):
    world, detachment, person, command = _raised_with_commander(destination="ferroalto")
    blocked_route_id = detachment.route_ids[0]
    blocked = world.map.routes[blocked_route_id]
    record_event(world, "fixture_field_route_closed", "A passagem à frente foi fechada.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("route", blocked.id, "enabled", blocked.enabled, False),))
    blocked.update_runtime(enabled=False)

    tick(world)
    held = next(event for event in reversed(world.events) if event.event_type == "detachment_held"
                and (event.causal_payload or {}).get("detachment_id") == detachment.id)
    actor = EntityRef("character", person.id)
    report = world.knowledge.route_report(actor, blocked_route_id)
    assert report is not None
    assert report.channel == "field_route_observation"
    assert report.travel_days is None
    receipt = world.event_index()[report.event_id]
    causes = {link.cause_event_id for link in receipt.causal_links}
    assert held.id in causes and command.last_event_id in causes
    assert receipt.causal_payload["position_region_id"] in blocked.endpoint_region_ids
    assert receipt.causal_payload["actor_ref"] == actor.to_dict()
    assert all(world.knowledge.route_report(actor, route.id) is not None
               for route in world.map.routes.values()
               if receipt.causal_payload["position_region_id"] in route.endpoint_region_ids)
    world.knowledge.validate(world)

    path = tmp_path / "commander-field-observation.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)


def test_real_commander_is_thresholded_local_delayed_and_round_trips(tmp_path):
    world, own_id, person_id, command = _commanded_world()
    assert command.character_id == person_id
    assert command.id == command.detachment_id == own_id
    assert world.society.characters[person_id].skills.command >= 40
    assert effective_doctrine(world, own_id) is None
    assert not any(option.decision()["action"] == SET_DOCTRINE_ACTION
                   for option in detachment_command_options(world, OWNER, detachment_id=own_id))

    command = _set(world, own_id, "hold")
    assert command.doctrine_effective_day == world.clock.absolute_day + 1
    assert effective_doctrine(world, own_id) is None
    tick(world)
    assert effective_doctrine(world, own_id) == "hold"

    path = tmp_path / "force-command.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    assert restored.society.detachment_commands[own_id].character_id == person_id


def test_hold_and_press_redistribute_existing_strength_without_inflation():
    world, own_id, _, _ = _commanded_world()
    detachment = world.society.detachments[own_id]
    # Prepared but hungry: hold spends the established position, press does not.
    world.society.detachments[own_id] = detachment.model_copy(update={"provisions": 0})
    baseline = field_strength(world, world.society.detachments[own_id])[0]
    _set(world, own_id, "hold")
    world.clock = world.clock.advance(1)
    hold = field_strength(world, world.society.detachments[own_id])[0]
    assert (baseline, hold) == (detachment.count * 3, detachment.count * 4)

    # A new command decision only changes the allocation tomorrow; press is
    # valuable only when actual provisions are present, never above total +4.
    world.society.detachments[own_id] = world.society.detachments[own_id].model_copy(
        update={"provisions": detachment.count * 3})
    assert not field_engagement_offer_options(world, OWNER), "hold cannot initiate a field engagement"
    _set(world, own_id, "press")
    assert effective_doctrine(world, own_id) == "hold", "replacement is not early"
    world.clock = world.clock.advance(1)
    press = field_strength(world, world.society.detachments[own_id])[0]
    assert press == detachment.count * 4
    assert press <= detachment.count * 4


def test_withdrawal_releases_commander_and_leaves_the_real_person_at_column_location():
    world, own_id, person_id, _ = _commanded_world()
    location = world.society.detachments[own_id].location_id
    option = withdrawal_options(world, OWNER, detachment_id=own_id)[0]
    decision = decide(world, option)
    withdraw_detachment(world, OWNER, option.id, decision.id)
    assert own_id not in world.society.detachment_commands
    assert world.society.characters[person_id].location_id == location
    released = [event for event in world.events if event.event_type == "detachment_commander_released"]
    assert len(released) == 1 and decision.id in {link.cause_event_id for link in released[0].causal_links}
    assert all(event.fact_kind == FactKind.STATE_TRANSITION for event in released)


def test_contact_gives_the_named_commander_a_separate_later_turn(monkeypatch, tmp_path):
    world, own_id, person_id, _ = _commanded_world()
    notice = next(item for item in world.knowledge.force_contact_notices.values()
                  if item.own_detachment_id == own_id and item.recipient_ref == OWNER)
    world.config = world.config.model_copy(update={"ai_enabled": True})
    asked = []

    async def choose(_world, actor, _situation, choices, **_kwargs):
        asked.append(actor)
        if actor.kind == "polity":
            return ai_decider.NO_ACTION
        assert actor == EntityRef("character", person_id)
        return next(item["id"] for item in choices if ":press:" in item["id"])

    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(choose))
    institutional = ScheduledSituation(review_id(notice.id), REVIEW_KIND, world.clock.absolute_day)
    asyncio.run(review_force_contacts(world, (institutional,)))
    assert asked == [OWNER]
    assert world.society.detachment_commands[own_id].doctrine is None

    path = tmp_path / "pending-commander-turn.mws"
    save_world(world, path)
    world = load_world(path)

    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    assert any(item.kind == COMMAND_REVIEW_KIND for item in due)
    resolve_dated(world, due)
    asyncio.run(review_force_contacts(world, due))
    assert asked[0] == OWNER and asked[-1] == EntityRef("character", person_id)
    assert world.society.detachment_commands[own_id].doctrine == "press"
    decision = next(item for item in reversed(world.events)
                    if item.event_type == "detachment_commander_decided")
    assert decision.decision["actor_ref"] == EntityRef("character", person_id).to_dict()
    assert notice.event_id in {link.cause_event_id for link in decision.causal_links}


def test_commander_no_action_is_a_decision_without_a_doctrine(monkeypatch):
    world, own_id, person_id, _ = _commanded_world()
    notice = next(item for item in world.knowledge.force_contact_notices.values()
                  if item.own_detachment_id == own_id and item.recipient_ref == OWNER)

    async def decline(_world, actor, _situation, _choices, **_kwargs):
        assert actor == EntityRef("character", person_id)
        return ai_decider.NO_ACTION

    monkeypatch.setattr(ai_decider, "select_option", provider_selection_stub(decline))
    situation = ScheduledSituation(f"detachment-command-review:{notice.id}", COMMAND_REVIEW_KIND,
                                   world.clock.absolute_day)
    asyncio.run(review_force_contacts(world, (situation,)))
    assert world.society.detachment_commands[own_id].doctrine is None
    declined = [event for event in world.events if event.event_type == "detachment_commander_declined"]
    assert len(declined) == 1 and not declined[0].deltas
    assert declined[0].decision["actor_ref"] == EntityRef("character", person_id).to_dict()
