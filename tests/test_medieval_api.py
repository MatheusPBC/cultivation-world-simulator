import asyncio

import httpx
import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.models import DiplomaticNotice
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.sim.medieval.events import record_event


@pytest.fixture
def app(tmp_path):
    from src.server.medieval.app import create_app
    return create_app(save_dir=lambda: tmp_path / "saves")


@pytest.fixture
async def client(app):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as value:
            yield value


async def command(client, name, payload=None):
    response = await client.post(f"/api/v2/command/{name}", json=payload or {})
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def query(client, name):
    response = await client.get(f"/api/v2/query/{name}")
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_public_lifecycle_creates_medieval_world_advances_a_year_and_resumes(client):
    assert not (await query(client, "status"))["ready"]
    await command(client, "create", {"seed": 73})
    society = await query(client, "society")
    assert len(society["characters"]) == 12
    assert len(society["settlements"]) == 8
    assert len(society["polities"]) == 3
    assert society["civic_protests"] == []
    assert society["civic_movements"] == []
    assert society["civic_strikes"] == []
    assert society["civic_amnesties"] == []
    game_map = await query(client, "map")
    assert game_map["map_id"] == "vale-das-tres-coroas"
    assert len(game_map["routes"]) == 9
    assert game_map["width"] == len(game_map["region_rows"][0]) == 24
    # Active cargo adds dated jumps; a year is elapsed time, not twelve commands.
    while (await query(client, "world"))["day"] < 360:
        await command(client, "step")
    before = await query(client, "world")
    assert before["day"] == 360
    assert before["config"]["seed"] == 73
    # Sustained deprivation is a canonical material consequence.  The public
    # lifecycle must preserve the aggregate population exposed by the same
    # snapshot, but it is not allowed to promise the initial count after a
    # year of unpaid food shortfall.
    assert 0 < before["population"] <= 10900
    economics = await query(client, "economy")
    await command(client, "save", {"save_id": "um-ano"})
    await command(client, "step")
    await command(client, "load", {"save_id": "um-ano"})
    assert await query(client, "world") == before
    assert await query(client, "economy") == economics
    assert (await query(client, "status"))["paused"]


async def test_world_required_and_input_errors_have_stable_non_success_responses(client):
    response = await client.post("/api/v2/command/step", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORLD_NOT_READY"
    response = await client.post("/api/v2/command/create", json={"character_count": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert not (await query(client, "status"))["ready"]


async def test_public_month_exposes_paid_food_and_its_two_decisions(client):
    await command(client, "create", {"seed": 73, "character_count": 12})
    initial_population = (await query(client, "world"))["population"]
    await command(client, "step")
    economy = await query(client, "economy")
    assert sum(a["balance"] for a in economy["accounts"]) == 76000
    household_cash = sum(a["balance"] for a in economy["accounts"]
                         if a["owner_ref"]["kind"] == "population_group")
    assert 0 < household_cash < 10900 * 4
    history, after = [], 0
    while True:
        page = await query(client, f"events?after={after}&limit=100")
        history.extend(page["items"])
        if not page["has_more"]:
            break
        after = page["next_after"]
    purchases = [e for e in history if e["event_type"] == "household_purchase_completed"]
    assert purchases
    consumed = sum(int(d["before"]) - int(d["after"]) for e in history
                   if e["event_type"] in {"household_purchase_completed", "subsistence_resolved"}
                   for d in e["deltas"] if d["owner_kind"] == "stock" and d["aspect"] == "food")
    # Public relief is no longer automatic: what leaves public stock is only
    # what households could actually afford. The rest of the population's
    # need is either eaten from a household's own private stock (domestic,
    # not a public-stock delta) or goes unmet as real, reported hunger
    # (missing_food). Named people counted exactly once means these three
    # shares add back up to the whole population, with nothing left over and
    # nothing double-removed.
    society = await query(client, "society")
    domestic = sum(int(d["before"]) - int(d["after"]) for e in history
                   if e["event_type"] == "household_rations_consumed"
                   for d in e["deltas"] if d["owner_kind"] == "stock" and d["aspect"] == "food")
    missing = sum(s["missing_food"] for s in society["settlements"])
    assert consumed == initial_population - domestic - missing
    detail = await query(client, f"causal/{purchases[0]['id']}")
    assert {e["decision"]["action"] for e in detail["causes"] if e["decision"]} >= {"buy_rations", "sell_rations"}
    assert any(e["event_type"] == "subsistence_resolved" for e in detail["effects"])


async def test_create_does_not_silently_replace_existing_world(client):
    await command(client, "create", {"seed": 73})
    before = await query(client, "world")
    response = await client.post("/api/v2/command/create", json={"seed": 4})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORLD_EXISTS"
    assert await query(client, "world") == before


@pytest.mark.parametrize("save_id", ["../outside", "C:\\secret", "CON", "foo/bar", ".hidden", "x.mws"])
async def test_save_identifiers_cannot_escape_storage(client, save_id):
    await command(client, "create")
    response = await client.post("/api/v2/command/save", json={"save_id": save_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_manual_overwrite_is_explicit_and_autosave_does_not_touch_manual_file(client, app):
    await command(client, "create")
    await command(client, "save", {"save_id": "manual"})
    path = app.state.runtime.save_path("manual")
    before = path.read_bytes()
    await command(client, "step")
    assert path.read_bytes() == before
    response = await client.post("/api/v2/command/save", json={"save_id": "manual"})
    assert response.status_code == 409
    await command(client, "save", {"save_id": "manual", "overwrite": True})
    assert path.read_bytes() != before


async def test_paginated_events_and_causal_edges_return_canonical_facts(client):
    await command(client, "create")
    await command(client, "step")
    first = await query(client, "events?limit=2")
    second = await query(client, f"events?limit=2&after={first['next_after']}")
    assert len(first["items"]) == len(second["items"]) == 2
    assert first["items"][-1]["sequence"] < second["items"][0]["sequence"]
    detail = await query(client, f"causal/{first['items'][0]['id']}")
    assert detail["event"] == first["items"][0]
    response = await client.get("/api/v2/query/events?limit=1000")
    assert response.status_code == 422


async def test_dossier_api_serializes_state_delta_from_known_material_event(client, app):
    await command(client, "create", {"seed": 73})
    world = app.state.runtime.world
    actor = EntityRef("polity", "auren")
    event = record_event(
        world,
        "known_material_fact",
        "Auren recebeu uma alteração material conhecida.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        deltas=(StateDelta(
            owner_kind="region", owner_id="pedraclara", aspect="population",
            before="10", after="9", magnitude=-1,
        ),),
    )
    world.knowledge.notices["notice:known-material"] = DiplomaticNotice(
        id="notice:known-material", proposal_id="proposal:known-material",
        recipient_ref=actor, event_id=event.id, learned_day=world.clock.absolute_day,
    )

    response = await client.get("/api/v2/query/dossier/polity/auren")

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    entry = next(item for item in payload["entries"] if item["event_id"] == event.id)
    assert entry["payload"]["deltas"] == [{
        "id": f"{event.id}:delta:0", "event_id": event.id,
        "owner_kind": "region", "owner_id": "pedraclara", "aspect": "population",
        "before": "10", "after": "9", "magnitude": -1,
    }]


async def test_pause_waits_for_the_active_step_before_acknowledging(client, app, monkeypatch):
    from src.sim.medieval.engine import MedievalSimulator
    await command(client, "create")
    entered, release = asyncio.Event(), asyncio.Event()
    original = MedievalSimulator.step
    async def held_step(self):
        entered.set()
        await release.wait()
        return await original(self)
    monkeypatch.setattr(MedievalSimulator, "step", held_step)
    await command(client, "resume")
    await asyncio.wait_for(entered.wait(), timeout=3)
    paused = asyncio.create_task(command(client, "pause"))
    await asyncio.sleep(0)
    assert not paused.done()
    release.set()
    await asyncio.wait_for(paused, timeout=3)
    day = (await query(client, "world"))["day"]
    await app.state.runtime.tick()
    assert (await query(client, "world"))["day"] == day == 30


async def test_failed_step_preserves_published_world_and_pauses(client, app, monkeypatch):
    await command(client, "create")
    before = await query(client, "world")
    economics = await query(client, "economy")
    def fail(*args):
        raise OSError("private-path-must-not-leak")
    monkeypatch.setattr("src.sim.medieval.engine.save_world", fail)
    response = await client.post("/api/v2/command/step", json={})
    assert response.status_code == 500
    assert "private-path" not in response.text
    assert response.json()["error"]["code"] == "STEP_FAILED"
    assert await query(client, "world") == before
    assert await query(client, "economy") == economics
    status = await query(client, "status")
    assert status["paused"] and status["last_error"]["code"] == "STEP_FAILED"


async def test_provider_decision_failure_pauses_without_publishing_candidate(client, app, monkeypatch):
    from src.sim.medieval.ai_decider import ProviderDecisionRequired
    await command(client, "create", {"ai_enabled": True, "ai_calls_per_step": 1})
    before = await query(client, "world")

    async def fail_step(self):
        raise ProviderDecisionRequired("provider unavailable")

    monkeypatch.setattr("src.sim.medieval.engine.MedievalSimulator.step", fail_step)
    response = await client.post("/api/v2/command/step", json={})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "AI_DECISION_REQUIRED"
    assert await query(client, "world") == before
    status = await query(client, "status")
    assert status["paused"] and status["last_error"]["code"] == "AI_DECISION_REQUIRED"


async def test_observer_api_has_no_material_mutation_or_xianxia_routes(client):
    schema = (await client.get("/openapi.json")).json()
    commands = {path.rsplit("/", 1)[-1] for path in schema["paths"] if "/command/" in path}
    assert commands == {"create", "step", "pause", "resume", "speed", "save", "load"}
    assert not any("/api/v1/" in p for p in schema["paths"])
    response = await client.post("/api/v2/command/create", json={}, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert not (await query(client, "status"))["ready"]


def test_main_entrypoint_selects_the_medieval_application():
    from src.server.main import app
    schema = app.openapi()
    assert "/api/v2/command/create" in schema["paths"]
    assert not any("/api/v1/" in path for path in schema["paths"])


def test_default_storage_namespace_is_independent_of_the_source_fork(monkeypatch):
    from src.config.data_paths import _default_data_root
    monkeypatch.delenv("CWS_DATA_DIR", raising=False)
    path = _default_data_root()
    assert path.parent.name == "MedievalWorldSimulator-dev"


async def test_load_rejects_a_save_with_missing_run_configuration(client, app):
    import json
    import sqlite3
    await command(client, "create")
    await command(client, "save", {"save_id": "config"})
    with sqlite3.connect(app.state.runtime.save_path("config")) as conn:
        payload = json.loads(conn.execute("SELECT payload FROM world WHERE id=1").fetchone()[0])
        del payload["config"]["seed"]
        conn.execute("UPDATE world SET payload=? WHERE id=1", (json.dumps(payload),))
    before = await query(client, "world")
    response = await client.post("/api/v2/command/load", json={"save_id": "config"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SAVE_INVALID"
    assert await query(client, "world") == before
