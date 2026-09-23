import random
import sqlite3

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.state_delta import StateDelta
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.systems.calendar_agenda import ScheduledSituation


def test_save_restores_society_map_agenda_rng_and_causal_history(tmp_path):
    world = create_medieval_world(73)
    world.rng.random()
    world.agenda.schedule(ScheduledSituation("journey:1", "travel", 8))
    route = next(iter(world.map.routes.values()))
    route.update_runtime(enabled=False)
    event = record_event(world, "route_closed", "Uma rota foi fechada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route.id, aspect="enabled", before="True", after="False"),))
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert world_snapshot(loaded) == world_snapshot(world)
    assert [e.model_dump(mode="json") for e in loaded.events] == [event.model_dump(mode="json")]
    assert loaded.rng.random() == world.rng.random()
    assert not loaded.map.routes[route.id].enabled
    assert loaded.map.regions[801].society is loaded.society


def test_save_load_preserves_structured_causal_payload(tmp_path):
    world = create_medieval_world(73)
    event = record_event(
        world,
        "observed_route_pressure",
        "A leitura física registrou pressão na rota.",
        causal_payload={"ecology": {"species": "river_drake", "habitat_stress": 3}},
    )
    assert event.model_dump(mode="json")["causal_payload"] == {
        "ecology": {"species": "river_drake", "habitat_stress": 3}
    }
    path = tmp_path / "causal-payload.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.events[0].causal_payload == event.causal_payload
    assert loaded.events[0].model_dump(mode="json") == event.model_dump(mode="json")


def test_failed_save_keeps_previous_snapshot_and_events(tmp_path):
    world = create_medieval_world(73)
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    before = path.read_bytes()
    world.events.append(object())
    with pytest.raises((ValueError, TypeError, AttributeError)):
        save_world(world, path)
    assert path.read_bytes() == before
    assert load_world(path).clock.absolute_day == 0


def test_xianxia_or_foreign_databases_are_rejected_without_modification(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE events (month_stamp INTEGER)")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Medieval"):
        load_world(path)
    assert path.read_bytes() == before


def test_previous_freight_schema_is_rejected_without_touching_save(tmp_path):
    path = tmp_path / "schema-65.mws"
    save_world(create_medieval_world(73), path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE metadata SET schema_version=65 WHERE id=1")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported Medieval World Simulator save"):
        load_world(path)
    assert path.read_bytes() == before


def test_loading_missing_save_does_not_create_a_database(tmp_path):
    path = tmp_path / "missing.mws"
    with pytest.raises(FileNotFoundError):
        load_world(path)
    assert not path.exists()


def test_decision_cannot_apply_material_deltas():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="decision"):
        record_event(world, "choice", "Uma escolha.", fact_kind=FactKind.DECISION,
            deltas=(StateDelta(owner_kind="world", owner_id="world", aspect="people", before="1", after="0"),))
    assert world.events == []


def test_llm_interpretation_cannot_hide_state_deltas_in_causal_payload():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="causal payload"):
        record_event(
            world,
            "ai_decision_interpreted",
            "A IA interpretou as opções.",
            causal_origin=CausalOrigin.LLM_INTERPRETATION,
            causal_payload={"deltas": [{"owner_kind": "route", "owner_id": "r", "aspect": "enabled"}]},
        )
    assert world.events == []


def test_causal_links_cannot_reference_missing_events():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="cause"):
        record_event(world, "effect", "Um efeito.", cause_ids=("missing",))
    assert world.events == []


def test_repeated_save_can_replace_the_existing_file_on_windows(tmp_path):
    world = create_medieval_world(73)
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    record_event(world, "observation", "Uma observação.")
    save_world(world, path)
    assert len(load_world(path).events) == 1


def test_missing_tail_of_saved_history_is_detected(tmp_path):
    world = create_medieval_world(73)
    record_event(world, "observation", "Uma observação.")
    path = tmp_path / "campaign.mws"
    save_world(world, path)
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM events")
    with pytest.raises(ValueError, match="history"):
        load_world(path)
