"""One person, one real road: agency the world can physically refuse."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.character_travel import (REVIEW_KIND, TRAVEL_ACTION, is_traveling,
                                               review_character_travel, schedule_character_travel_reviews,
                                               travel_options)
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.force_command import detachment_command_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_creature_autonomy import provider


def lone_world():
    """One named person, so a bounded provider budget reaches their turn."""
    world = create_medieval_world(73, character_count=1)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 64,
                                                   "ai_max_calls": 10000})
    character = next(iter(world.society.characters.values()))
    world.society.characters[character.id] = character.model_copy(
        update={"skills": character.skills.model_copy(update={"command": 60})})
    return world, world.society.characters[character.id]


def garrison(world, character):
    """A present column of the local administration, where this person stands."""
    settlement = world.society.settlements[character.location_id]
    owner = EntityRef("polity", settlement.administrator_id)
    resident = next(item for item in world.society.population.values()
                    if item.settlement_id == settlement.id)
    soldiers = resident.model_copy(update={"id": f"pop:{settlement.id}:{resident.people}:soldier",
                                           "occupation": "soldier", "count": 20})
    world.society.population[soldiers.id] = soldiers
    anchor = record_event(world, "fixture_garrison", "Guarnição preparada para este cenário.")
    day = world.clock.absolute_day
    world.society.detachments["detachment:fixture"] = Detachment(
        id="detachment:fixture", owner_ref=owner, source_group_id=soldiers.id, count=20,
        location_id=settlement.id, destination_id=settlement.id, provisions=100, stage="present",
        started_day=day, due_day=day, decision_event_id=anchor.id, last_event_id=anchor.id)
    world.society.validate(set(world.map.regions), world)
    return owner


def toward(destination_name):
    """Answer only travel prompts, and only for this destination."""
    def decide(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        for choice in payload["choices"]:
            if f"até {destination_name}" in choice["label"]:
                return {"selected_id": choice["id"]}
        return {"selected_id": "NO_ACTION"}
    return decide


def appointable(world, owner, character_id):
    return any(getattr(item, "character_id", None) == character_id
               for item in detachment_command_options(world, owner))


async def depart(world, engine, character_id):
    """Step until the granted turn is actually taken; other dated work may
    occupy the days in between, so this waits for the fact, not for a count."""
    for _ in range(40):
        if is_traveling(world, character_id):
            return next(item for item in world.activities.values()
                        if item.character_id == character_id)
        await engine.step()
    raise AssertionError("no individual turn produced a journey")


async def reach(world, engine, day):
    """Advance until the world really reaches one dated day."""
    for _ in range(60):
        if world.clock.absolute_day >= day:
            return
        await engine.step()
    raise AssertionError(f"world never reached day {day}")


async def test_a_person_walks_one_real_leg_and_is_absent_until_arrival(tmp_path, monkeypatch):
    world, character = lone_world()
    owner = garrison(world, character)
    leg = travel_options(world, character.id)[0]
    assert appointable(world, owner, character.id), "present at home, and usable there"

    provider(monkeypatch, toward(world.society.settlements[leg.destination_id].name))
    engine = MedievalSimulator(world)
    journey = await depart(world, engine, character.id)
    assert journey.kind == "travel" and journey.origin_id == leg.origin_id
    assert journey.due_day == journey.started_day + leg.travel_days
    # Departure is not arrival: residence is untouched and nobody may use them.
    assert world.society.characters[character.id].location_id == leg.origin_id
    assert world.society.characters[character.id].population_group_id == character.population_group_id
    assert travel_options(world, character.id) == (), "a traveller composes no local option"
    assert not appointable(world, owner, character.id)

    decided = next(item for item in world.events if item.event_type == "character_travel_decided")
    started = next(item for item in world.events if item.event_type == "character_travel_started")
    assert decided.fact_kind == FactKind.DECISION and not decided.deltas
    assert set(decided.decision) == {"action", "actor_ref", "selected_affordance_id"}
    assert decided.decision["action"] == TRAVEL_ACTION
    assert decided.decision["actor_ref"] == EntityRef("character", character.id).to_dict()
    assert {link.cause_event_id for link in started.causal_links} == {decided.id}

    await reach(world, engine, journey.due_day)

    assert world.society.characters[character.id].location_id == leg.destination_id
    assert not any(item.character_id == character.id for item in world.activities.values())
    arrival = next(item for item in world.events if item.event_type == "travel_arrived")
    assert any(delta.owner_kind == "character" and delta.owner_id == character.id
               and delta.aspect == "location_id" and delta.after == leg.destination_id
               for delta in arrival.deltas)
    reached = travel_options(world, character.id)
    assert reached and all(item.origin_id == leg.destination_id for item in reached)

    # Walking is not an economic act. Ordinary monthly production and household
    # consumption may run in between, so what has to hold is that the journey's
    # own facts touch no material owner at all.
    moves = [item for item in world.events
             if item.event_type in {"character_travel_decided", "character_travel_started",
                                    "travel_arrived", "travel_delayed"}]
    assert [item.event_type for item in moves] == ["character_travel_decided",
                                                   "character_travel_started", "travel_arrived"]
    assert [(delta.owner_kind, delta.aspect) for delta in started.deltas] == [("activity", "status")]
    assert [(delta.owner_kind, delta.aspect) for delta in arrival.deltas] == [("character", "location_id")]
    assert all(delta.owner_kind not in {"stock", "account", "population_group", "freight", "payroll",
                                        "settlement", "route", "site"}
               for item in moves for delta in item.deltas), "travel moves a person, never goods"
    path = tmp_path / "travel.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_a_closed_road_offers_nothing_and_holds_whoever_is_on_it(monkeypatch):
    world, character = lone_world()
    origin = world.society.settlements[character.location_id]

    # No provider, no turn: the gate lives in the scheduler, before any budget
    # is touched, so a disabled run grants nothing and moves nobody.
    world.config = world.config.model_copy(update={"ai_enabled": False})
    assert schedule_character_travel_reviews(world) == ()
    assert not any(entry["kind"] == REVIEW_KIND for entry in world.agenda.to_dict())

    # A closed passage is not an affordance, so no turn is even granted.
    world.config = world.config.model_copy(update={"ai_enabled": True})
    touching = [route for route in world.map.routes.values()
                if origin.region_id in route.endpoint_region_ids]
    for route in touching:
        route.update_runtime(enabled=False)
    assert travel_options(world, character.id) == ()
    assert schedule_character_travel_reviews(world) == ()
    assert not any(item.event_type.startswith("character_travel") for item in world.events)

    for route in touching:
        route.update_runtime(enabled=True)
    leg = travel_options(world, character.id)[0]
    provider(monkeypatch, toward(world.society.settlements[leg.destination_id].name))
    engine = MedievalSimulator(world)
    journey = await depart(world, engine, character.id)

    # The passage closes while the person is on it: the road holds, never moves.
    world.map.routes[journey.route_id].update_runtime(enabled=False)
    await reach(world, engine, journey.due_day)
    assert world.society.characters[character.id].location_id == origin.id
    assert any(item.event_type == "travel_delayed" for item in world.events)
    held = world.activities[journey.id]
    assert held.due_day > journey.due_day
    assert world.agenda.get(journey.id) is not None
    assert not any(item.event_type == "travel_arrived" for item in world.events)

    world.map.routes[journey.route_id].update_runtime(enabled=True)
    await reach(world, engine, held.due_day)
    assert world.society.characters[character.id].location_id == journey.destination_id
    assert sum(item.event_type == "character_travel_started" for item in world.events) == 1


async def test_scheduled_travel_pauses_when_provider_disappears(monkeypatch):
    world, character = lone_world()
    monkeypatch.setattr("src.sim.medieval.ai_decider.provider_available", lambda: True)
    scheduled = schedule_character_travel_reviews(world)
    assert scheduled
    monkeypatch.setattr("src.sim.medieval.ai_decider.provider_available", lambda: False)
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    before = world_snapshot(world)
    with pytest.raises(ProviderDecisionRequired):
        await review_character_travel(world, due)
    assert world_snapshot(world) == before
    assert not is_traveling(world, character.id)


async def test_selected_travel_route_that_closes_pauses_instead_of_becoming_noop(monkeypatch):
    world, character = lone_world()
    leg = travel_options(world, character.id)[0]
    monkeypatch.setattr("src.sim.medieval.ai_decider.provider_available", lambda: True)

    async def close_route_then_choose(prompt, *args, **kwargs):
        world.map.routes[leg.route_id].update_runtime(enabled=False)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", close_route_then_choose)
    scheduled = schedule_character_travel_reviews(world)
    assert scheduled
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    before = world_snapshot(world)
    with pytest.raises(ProviderDecisionRequired):
        await review_character_travel(world, due)
    assert not is_traveling(world, character.id)
    assert world_snapshot(world)["society"] == before["society"]
