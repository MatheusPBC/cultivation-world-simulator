"""The transient event index must stay local to each transactional world."""

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event


def test_event_index_append_is_incremental_and_transaction_isolated():
    world = create_medieval_world(73)
    published_index = world.event_index()
    candidate = world.transaction_copy()
    candidate_index = candidate.event_index()

    assert candidate_index is not published_index
    first = record_event(candidate, "index_probe", "Primeiro fato.")
    assert candidate.event_index() is candidate_index
    assert candidate.event_index()[first.id] is first
    assert first.id not in world.event_index()

    second = record_event(candidate, "index_probe", "Segundo fato.")
    assert candidate.event_index() is candidate_index
    assert candidate.event_index()[second.id] is second
    assert second.id not in world.event_index()


def test_event_index_rebuilds_after_non_append_replacement():
    world = create_medieval_world(73)
    original = record_event(world, "index_probe", "Fato original.")
    previous_index = world.event_index()
    replacement = original.model_copy(update={"content": "Fato corrigido."})

    world.events[-1] = replacement

    assert world.event_index() is not previous_index
    assert world.event_index()[original.id] is replacement


def test_event_type_index_append_is_incremental_and_transaction_isolated():
    world = create_medieval_world(73)
    published = world.events_of_type("index_probe")
    assert published == ()
    published_cache = world._event_type_cache[2]
    candidate = world.transaction_copy()
    candidate_cache = candidate._event_type_cache[2]
    assert candidate_cache is not published_cache

    first = record_event(candidate, "index_probe", "Primeiro fato.")
    second = record_event(candidate, "index_probe", "Segundo fato.")

    assert candidate._event_type_cache[2] is candidate_cache
    assert candidate.events_of_type("index_probe") == (first, second)
    assert world.events_of_type("index_probe") == ()


def test_event_type_index_rebuilds_after_non_append_replacement():
    world = create_medieval_world(73)
    original = record_event(world, "index_probe", "Fato original.")
    assert world.events_of_type("index_probe") == (original,)
    previous_cache = world._event_type_cache[2]
    replacement = original.model_copy(update={"event_type": "index_replacement"})

    world.events[-1] = replacement

    assert world.events_of_type("index_probe") == ()
    assert world.events_of_type("index_replacement") == (replacement,)
    assert world._event_type_cache[2] is not previous_cache
