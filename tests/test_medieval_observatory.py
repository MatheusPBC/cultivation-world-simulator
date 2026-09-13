import httpx
import pytest

from src.server.medieval.app import create_app


@pytest.mark.asyncio
async def test_observatory_is_one_consistent_published_snapshot(tmp_path):
    app = create_app(save_dir=lambda: tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/api/v2/query/observatory")).status_code == 409
        await client.post("/api/v2/command/create", json={"seed": 73})
        await client.post("/api/v2/command/step", json={})
        reply = await client.get("/api/v2/query/observatory")
        assert reply.status_code == 200
        body = reply.json()
        data = body["data"]
        assert data["status"]["day"] == data["world"]["day"] == 30
        assert len(data["society"]["characters"]) == 12
        assert data["map"]["settlements"] == data["society"]["settlements"]
        assert sum(g["count"] for g in data["society"]["population_groups"]) == data["world"]["population"] == 10900
        assert all(m["updated_day"] == 30 for m in data["economy"]["markets"])
        assert len(data["economy"]["payrolls"]) == 4
        assert all(p["day"] == 30 for p in data["economy"]["payrolls"])
        assert sum(p["gross"] for p in data["economy"]["payrolls"]) > 0
        assert len(data["governance"]["tax_policies"]) == 3
        assert body["revision"] == (await client.get("/api/v2/query/status")).json()["revision"]
        assert len(data["governance"]["objectives"]) == 15
        assert len(data["governance"]["plans"]) == 15
        assert len(data["economy"]["expansions"]) == 2
        assert all(p["stage"] == "waiting" for p in data["economy"]["expansions"])
        food_goals = {o["id"] for o in data["governance"]["objectives"] if o["kind"] == "maintain_food_reserve"}
        assert all(p["stage"] == "satisfied" for p in data["governance"]["plans"] if p["objective_id"] in food_goals)
        assert any(p["stage"] == "await_delivery" for p in data["governance"]["plans"] if p["objective_id"] not in food_goals)
        governance = await client.get("/api/v2/query/governance")
        assert governance.status_code == 200
        assert governance.json()["data"] == data["governance"]
        research = await client.get("/api/v2/query/research")
        assert research.status_code == 200
        assert research.json()["data"] == data["research"]
        assert {p["technology_id"] for p in data["research"]["projects"]} == {"irrigation", "metallurgy"}
        assert all(p["completed_units"] == 0 for p in data["research"]["projects"])
        assert data["research"]["knowledge"] == []
        diplomacy = await client.get("/api/v2/query/diplomacy")
        assert diplomacy.status_code == 200
        assert diplomacy.json()["data"] == data["diplomacy"] == {"proposals": [], "obligations": [], "notices": []}


@pytest.mark.asyncio
async def test_diplomacy_snapshot_exposes_real_terms_and_receipts_without_disclosing_to_actors(tmp_path):
    from tests.test_medieval_diplomacy import world_with_knowledge, offer, respond, pay, teach, SELLER, BUYER
    from src.sim.medieval.persistence import world_snapshot, save_world, load_world

    world = world_with_knowledge()
    original = offer(world)
    proposal = offer(world, 80, original.id)
    respond(world, proposal)
    pay(world, f"{proposal.id}:term:0")
    # Persist the mixed state: payment completed, teaching still an obligation.
    path = tmp_path / 'negotiated.mws'
    save_world(world, path)
    world = load_world(path)
    app = create_app(save_dir=lambda: tmp_path / 'runtime')
    app.state.runtime._activate(world)
    before = world_snapshot(world)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        view = (await client.get('/api/v2/query/diplomacy')).json()
        observed = (await client.get('/api/v2/query/observatory')).json()
        assert view['revision'] == observed['revision']
        assert view['data'] == observed['data']['diplomacy']
        data = view['data']
        terms = next(p for p in data['proposals'] if p['id'] == proposal.id)['clauses']
        assert terms[0]['amount'] == 80 and terms[1]['depends_on'] == [0]
        assert next(p for p in data['proposals'] if p['id'] == original.id)['status'] == 'superseded'
        payment = next(o for o in data['obligations'] if o['clause_index'] == 0)
        lesson = next(o for o in data['obligations'] if o['clause_index'] == 1)
        assert payment['status'] == 'fulfilled' and lesson['status'] == 'active'
        assert payment['material_event_id'] and lesson['material_event_id'] is None
        assert {n['recipient_ref']['id'] for n in data['notices']} == {SELLER.id, BUYER.id}
        detail = (await client.get(f"/api/v2/query/causal/{payment['last_event_id']}")).json()['data']
        assert payment['material_event_id'] in {e['id'] for e in detail['causes']}
        assert world_snapshot(world) == before  # omniscient reads teach nobody and move no assets
        assert (await client.post('/api/v2/command/diplomacy', json={})).status_code == 404
        teach(world, lesson['id'])
        assert (await client.get('/api/v2/query/diplomacy')).json()['data']['obligations'][1]['status'] == 'fulfilled'


@pytest.mark.asyncio
async def test_route_reports_are_consistent_across_queries_and_reading_mutates_nothing(tmp_path):
    from src.sim.medieval.persistence import world_snapshot

    app = create_app(save_dir=lambda: tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.post("/api/v2/command/create", json={"seed": 73})
        await client.post("/api/v2/command/step", json={})
        world = app.state.runtime.require_world()
        before = world_snapshot(world)
        observatory = (await client.get("/api/v2/query/observatory")).json()
        governance = (await client.get("/api/v2/query/governance")).json()
        assert governance["data"] == observatory["data"]["governance"]
        reports = observatory["data"]["governance"]["route_reports"]
        assert reports  # the monthly routine already published dated observations
        assert all(r["observed_day"] == 30 for r in reports)
        assert world_snapshot(world) == before  # omniscient reads publish nothing new


@pytest.mark.asyncio
async def test_serves_only_medieval_bundle_and_does_not_mask_missing_api(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    app = create_app(save_dir=lambda: tmp_path / "saves", frontend_dir=frontend)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/")).status_code == 503
        (frontend / "index.html").write_text("<html>old cultivation app</html>", encoding="utf-8")
        assert (await client.get("/")).status_code == 503
        (frontend / "index.html").write_text('<html><meta name="mws-product" content="medieval-world-simulator">Atlas</html>', encoding="utf-8")
        assets = frontend / "web_static"
        assets.mkdir()
        (assets / "app.js").write_text("const medieval = true;", encoding="utf-8")
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert (await client.get("/web_static/app.js")).text == "const medieval = true;"
        assert (await client.get("/api/v2/query/missing")).status_code == 404
        assert (await client.get("/web_static/missing.js")).status_code == 404
        assert (await client.get("/web_static/%2e%2e/index.html")).status_code == 404
