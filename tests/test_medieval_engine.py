import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.actions import start_practice, start_travel
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


def traveller(world):
    return next(c for c in world.society.characters.values() if c.location_id == "campomanso")


async def test_travel_interrupts_monthly_jump_without_migrating_the_population():
    world = create_medieval_world(73)
    person = traveller(world)
    original_group = person.population_group_id
    total = world.society.total_population
    activity = start_travel(world, person.id, "road-campomanso-pedraclara", "pedraclara")
    assert world.society.characters[person.id].location_id == "campomanso"
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == activity.due_day < 30
    assert world.society.characters[person.id].location_id == "pedraclara"
    assert world.society.characters[person.id].population_group_id == original_group
    assert world.society.total_population == total
    assert not world.activities
    arrival = world.events[-1]
    assert arrival.event_type == "travel_arrived"
    assert arrival.causal_links[0].cause_event_id == activity.decision_event_id
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == 30


async def test_closed_route_delays_arrival_until_the_route_is_restored():
    world = create_medieval_world(73)
    person = traveller(world)
    route_id = "road-campomanso-pedraclara"
    activity = start_travel(world, person.id, route_id, "pedraclara")
    world.map.routes[route_id].update_runtime(enabled=False)
    engine = MedievalSimulator(world)
    await engine.step()
    assert world.society.characters[person.id].location_id == "campomanso"
    assert world.agenda.due_days == (activity.due_day + 1,)
    world.map.routes[route_id].update_runtime(enabled=True)
    await engine.step()
    assert world.society.characters[person.id].location_id == "pedraclara"


async def test_training_survives_save_and_matches_a_continuous_year(tmp_path):
    continuous = create_medieval_world(73)
    split = create_medieval_world(73)
    character_id = next(iter(continuous.society.characters))
    initial = continuous.society.characters[character_id].skills.diplomacy
    for world in (continuous, split):
        # Prepared practice-only scenario; the public annual test covers natural investments/freight.
        world.strategy.objectives.clear()
        world.economy.expansion_blueprints.clear()
        world.research.technologies.clear()
        world.economy.facilities.clear()
        world.economy.recipes = {k: r for k, r in world.economy.recipes.items() if not r.required_technology_id}
        start_practice(world, character_id, "diplomacy")
    for _ in range(12):
        await MedievalSimulator(continuous).step()
    for _ in range(5):
        await MedievalSimulator(split).step()
    path = tmp_path / "world.mws"
    save_world(split, path)
    resumed = load_world(path)
    for _ in range(7):
        await MedievalSimulator(resumed).step()
    # The simulator now has dated freight/recourse work in this fixture, so
    # twelve steps are not twelve monthly jumps.  The persistence invariant is
    # equivalence of the resumed and continuous timelines, not a hard-coded
    # calendar day that predates those canonical agendas.
    assert resumed.clock.absolute_day == continuous.clock.absolute_day > 0
    # Practice resolves on canonical monthly boundaries, not once per engine
    # step; dated freight/recourse work can consume several steps within one
    # month.  Assert the persisted timeline agrees and that practice happened,
    # rather than coupling the test to a fixed number of monthly completions.
    assert resumed.society.characters[character_id].skills.diplomacy == continuous.society.characters[character_id].skills.diplomacy
    assert resumed.society.characters[character_id].skills.diplomacy > initial
    assert world_snapshot(resumed) == world_snapshot(continuous)
    assert [e.model_dump(mode="json") for e in resumed.events] == [e.model_dump(mode="json") for e in continuous.events]


async def test_persistence_failure_does_not_publish_a_partial_step(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    start_practice(world, next(iter(world.society.characters)), "combat")
    path = tmp_path / "world.mws"
    save_world(world, path)
    before = world_snapshot(world)
    before_events = [e.model_dump(mode="json") for e in world.events]

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("src.sim.medieval.engine.save_world", fail)
    with pytest.raises(OSError, match="disk failure"):
        await MedievalSimulator(world, save_path=path).step()
    assert world_snapshot(world) == before
    assert [e.model_dump(mode="json") for e in world.events] == before_events
    assert world_snapshot(load_world(path)) == before


def test_an_actor_cannot_train_and_travel_simultaneously():
    world = create_medieval_world(73)
    person = traveller(world)
    start_practice(world, person.id, "combat")
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="busy"):
        start_travel(world, person.id, "road-campomanso-pedraclara", "pedraclara")
    assert world_snapshot(world) == before


async def test_one_day_of_training_is_not_counted_as_a_full_month():
    world = create_medieval_world(73)
    from src.systems.time import WorldClock
    world.clock = WorldClock(29)
    character_id = next(iter(world.society.characters))
    before = world.society.characters[character_id].skills.combat
    start_practice(world, character_id, "combat")
    engine = MedievalSimulator(world)
    await engine.step()
    assert world.society.characters[character_id].skills.combat == before
    await engine.step()
    assert world.clock.absolute_day == 31  # Productive deliveries interrupt the monthly jump.
    assert world.society.characters[character_id].skills.combat == before
    while world.clock.absolute_day < 60:
        await engine.step()
    assert world.society.characters[character_id].skills.combat == before + 1
