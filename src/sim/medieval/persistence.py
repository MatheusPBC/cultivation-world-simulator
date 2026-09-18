"""One atomic SQLite save contains both the world snapshot and its causal history.

Readers never consult the current content catalog to reconstruct a saved map
or society. Runtime sessions, locks and provider secrets never enter a save.
"""

import json
import os
from pathlib import Path
import random
import sqlite3
import tempfile

from src.classes.core.infrastructure import validate_infrastructure
from src.classes.core.medieval_world import MedievalWorld
from src.classes.core.medieval_config import MedievalRunConfig
from src.classes.society import SocietyState
from src.classes.economy import EconomyState
from src.classes.governance import AuthorityState, KnowledgeState, StrategyState
from src.classes.research import ResearchState
from src.classes.environment.creature import CreatureState
from src.classes.environment.regional_overflow import RegionalOverflowState
from src.classes.governance.diplomacy import RelationsState
from src.run.map_snapshot import serialize_map_snapshot
from src.run.map_source import parse_map_source
from src.run.medieval_world import build_medieval_map
from src.systems.calendar_agenda import WorldAgenda
from src.systems.time import WorldClock
from .events import WorldEvent, validate_history
from .activities import Activity, validate_activities


PRODUCT = "medieval-world-simulator"
SCHEMA = 53


def world_snapshot(world: MedievalWorld) -> dict:
    world.society.validate(set(world.map.regions), world)
    validate_activities(world)
    world.economy.validate(world)
    world.authority.validate(world)
    world.knowledge.validate(world)
    world.strategy.validate(world)
    world.research.validate(world)
    world.relations.validate(world)
    world.regional_overflow.validate(world)
    world.creatures.validate(world)
    validate_infrastructure(world)
    snapshot = serialize_map_snapshot(world.map)
    source = {
        "schema_version": 6, "id": snapshot["preset_id"], "version": snapshot["preset_version"],
        **{key: snapshot[key] for key in ("width", "height", "region_rows", "geography", "landmarks",
                                        "region_overrides", "routes", "infrastructure_sites")},
    }
    return {
        "product": PRODUCT, "schema_version": SCHEMA, "catalog_version": 1,
        "event_count": len(world.events),
        "map_force_route_interdictors": dict(sorted(world.map.force_route_interdictors.items())),
        "clock_day": world.clock.absolute_day, "agenda": world.agenda.to_dict(),
        "activities": {key: a.model_dump(mode="json") for key, a in sorted(world.activities.items())},
        "society": world.society.to_dict(), "map": source, "map_name": world.map.map_name,
        "economy": world.economy.to_dict(),
        "research": world.research.to_dict(),
        "relations": world.relations.to_dict(),
        "regional_overflow": world.regional_overflow.to_dict(),
        "creatures": world.creatures.to_dict(),
        "authority": world.authority.to_dict(),
        "knowledge": world.knowledge.to_dict(), "strategy": world.strategy.to_dict(),
        "config": world.config.model_dump(mode="json"),
        "rng_state": json.loads(json.dumps(world.rng.getstate())),
    }


def restore_snapshot(data: dict, events: list[WorldEvent]) -> MedievalWorld:
    required = {"product", "schema_version", "catalog_version", "clock_day", "agenda",
                "society", "economy", "research", "relations", "regional_overflow", "creatures", "authority", "knowledge", "strategy", "map", "map_name", "map_force_route_interdictors", "rng_state", "activities", "event_count", "config"}
    if (not isinstance(data, dict) or set(data) != required or data.get("product") != PRODUCT
            or type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA
            or type(data.get("catalog_version")) is not int or data["catalog_version"] != 1):
        raise ValueError("Unsupported Medieval World Simulator save")
    clock = WorldClock(data["clock_day"])
    if not isinstance(data["config"], dict) or set(data["config"]) != set(MedievalRunConfig.model_fields):
        raise ValueError("invalid saved run configuration")
    if type(data["event_count"]) is not int or data["event_count"] != len(events):
        raise ValueError("saved history count does not match the world snapshot")
    sites = data["map"].get("infrastructure_sites") if isinstance(data["map"], dict) else None
    if (not isinstance(sites, list)
            or any(not isinstance(site, dict) or "service_suspended" not in site for site in sites)):
        raise ValueError("saved infrastructure service state is missing")
    validate_history(events, clock.absolute_day)
    society = SocietyState.from_dict(data["society"])
    game_map = build_medieval_map(parse_map_source(data["map"]), society)
    interdictors = data["map_force_route_interdictors"]
    if (not isinstance(interdictors, dict)
            or any(not isinstance(route_id, str) or not isinstance(interdiction_id, str)
                   or route_id not in game_map.routes or not interdiction_id
                   for route_id, interdiction_id in interdictors.items())):
        raise ValueError("invalid saved force route interdictors")
    game_map.force_route_interdictors = dict(interdictors)
    if not isinstance(data["map_name"], str):
        raise ValueError("invalid map name")
    game_map.map_name = data["map_name"]
    rng = random.Random()
    state = data["rng_state"]
    if not isinstance(state, list) or len(state) != 3 or not isinstance(state[1], list):
        raise ValueError("invalid random state")
    rng.setstate((state[0], tuple(state[1]), state[2]))
    agenda = WorldAgenda.from_dict(data["agenda"])
    if any(day <= clock.absolute_day for day in agenda.due_days):
        raise ValueError("save has unresolved current or past agenda entries")
    if not isinstance(data["activities"], dict):
        raise ValueError("activities must be a registry")
    activities = {key: Activity.model_validate(value) for key, value in data["activities"].items()}
    world = MedievalWorld(map=game_map, society=society, rng=rng, clock=clock, agenda=agenda,
                          events=events, activities=activities, economy=EconomyState.from_dict(data["economy"]),
                          authority=AuthorityState.from_dict(data["authority"]),
                          knowledge=KnowledgeState.from_dict(data["knowledge"]),
                          strategy=StrategyState.from_dict(data["strategy"]),
                          research=ResearchState.from_dict(data["research"]),
                          relations=RelationsState.from_dict(data["relations"]),
                          regional_overflow=RegionalOverflowState.from_dict(data["regional_overflow"]),
                          creatures=CreatureState.from_dict(data["creatures"]),
                          config=MedievalRunConfig.model_validate(data["config"]))
    validate_activities(world)
    return world


def _read_metadata(conn) -> dict:
    try:
        row = conn.execute("SELECT product, schema_version FROM metadata WHERE id=1").fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Not a Medieval World Simulator save") from exc
    if row != (PRODUCT, SCHEMA):
        raise ValueError("Unsupported Medieval World Simulator save")
    return {"product": row[0], "schema_version": row[1]}


def save_world(world: MedievalWorld, path: Path) -> None:
    path = Path(path)
    validate_history(world.events, world.clock.absolute_day)
    snapshot = world_snapshot(world)
    # Validate the complete candidate before touching the destination.
    restore_snapshot(snapshot, world.events)
    payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    event_rows = [(e.sequence, e.id, e.day, json.dumps(e.model_dump(mode="json"), ensure_ascii=False, allow_nan=False))
                  for e in world.events]
    if path.is_symlink():
        raise ValueError("save destination must not be a symlink")
    if path.exists():
        existing = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            _read_metadata(existing)
        finally:
            existing.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".mws", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temp_name)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.executescript("""
                CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), product TEXT NOT NULL, schema_version INTEGER NOT NULL);
                CREATE TABLE world (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE events (sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, day INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX events_by_day ON events(day, sequence);
            """)
            with conn:
                conn.execute("INSERT INTO metadata VALUES (1, ?, ?)", (PRODUCT, SCHEMA))
                conn.execute("INSERT INTO world VALUES (1, ?)", (payload,))
                conn.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", event_rows)
        finally:
            conn.close()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_world(path: Path) -> MedievalWorld:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        _read_metadata(conn)
        row = conn.execute("SELECT payload FROM world WHERE id=1").fetchone()
        if row is None:
            raise ValueError("save has no world snapshot")
        events = []
        for seq, event_id, day, payload in conn.execute("SELECT sequence, id, day, payload FROM events ORDER BY sequence"):
            event = WorldEvent.model_validate_json(payload)
            if (event.sequence, event.id, event.day) != (seq, event_id, day):
                raise ValueError("inconsistent event index")
            events.append(event)
        return restore_snapshot(json.loads(row[0]), events)
    finally:
        conn.close()
