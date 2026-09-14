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
        # The seed gives every published objective one current supply plan.  The
        # exact count is intentionally not a snapshot contract: a Map-owned
        # material consequence (for example infrastructure wear) may surface a
        # new repair-input objective without making the observatory incoherent.
        objectives = data["governance"]["objectives"]
        plans = data["governance"]["plans"]
        assert {plan["objective_id"] for plan in plans} == {objective["id"] for objective in objectives}
        # As with objectives/plans above, the exact count is not a snapshot
        # contract: only referential consistency is required, not a specific
        # amount of construction activity in the natural seed.
        expansions = data["economy"]["expansions"]
        facility_ids = {f["id"] for f in data["economy"]["facilities"]}
        blueprint_ids = {b["id"] for b in data["economy"]["expansion_blueprints"]}
        assert all(e["facility_id"] in facility_ids and e["blueprint_id"] in blueprint_ids for e in expansions)
        assert all(e["stage"] in {"waiting", "building", "blocked", "completed"} for e in expansions)
        food_goals = {o["id"] for o in objectives if o["kind"] == "maintain_food_reserve"}
        assert food_goals == {f"supply:{settlement['id']}" for settlement in data["society"]["settlements"]}
        assert all(p["stage"] == "satisfied" for p in plans if p["objective_id"] in food_goals)
        assert any(p["stage"] == "await_delivery" for p in plans if p["objective_id"] not in food_goals)
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
async def test_observatory_projects_canonical_campaign_threat_and_claim_without_teaching_actors(tmp_path):
    """The Dao may inspect live campaign state without turning it into knowledge."""
    from src.classes.event import FactKind
    from src.run.medieval_creatures import DRAKE_ID
    from src.sim.medieval.authority_claims import authority_claim_options, execute_option as execute_claim
    from src.sim.medieval.creatures import creature_options, execute_creature_option
    from src.sim.medieval.dated import resolve_dated
    from src.sim.medieval.events import record_event
    from src.sim.medieval.force import force_options, occupy_settlement
    from src.sim.medieval.persistence import world_snapshot
    from tests.test_medieval_campaign_supply import OWNER, campaign_world, decide

    world, detachment_id = await campaign_world()
    occupy = next(option for option in force_options(world, OWNER) if option.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    # Keep the existing real column present while the independent creature
    # timeline reaches its already-defined demand deadline.
    detachment = world.society.detachments[detachment_id]
    world.society.detachments[detachment_id] = detachment.model_copy(update={"provisions": 1000})
    claim_option = next(option for option in authority_claim_options(world, OWNER)
                        if option.evidence_kind == "held_occupation")
    execute_claim(world, OWNER, claim_option.id, decide(world, claim_option).id)

    # Build a validated pending threat from the same existing drake/site rules.
    # The observation endpoint must read it but never distribute its full state.
    creature = world.creatures.creatures[DRAKE_ID]
    perception = record_event(world, "creature_perceived_cargo", "Percepção factual da passagem para fixture.",
                               fact_kind=FactKind.OCCURRENCE)
    world.creatures.creatures[creature.id] = creature.model_copy(update={
        "condition": creature.hunger_threshold - 1,
        "perceived_crossings": 1,
        "last_perceived_day": world.clock.absolute_day,
        "last_event_id": perception.id,
    })
    request = next(option for option in creature_options(world, creature.id) if option.kind == "request")
    execute_creature_option(world, creature.id, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    while world.clock.absolute_day <= demand.due_day:
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    damage = next(option for option in creature_options(world, creature.id) if option.kind == "damage")
    execute_creature_option(world, creature.id, damage.id, decide(world, damage).id)

    app = create_app(save_dir=lambda: tmp_path / "runtime")
    app.state.runtime._activate(world)
    before = world_snapshot(world)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        reply = await client.get("/api/v2/query/observatory")
    assert reply.status_code == 200
    data = reply.json()["data"]

    campaign = data["campaigns"]
    detachment = next(item for item in campaign["detachments"] if item["id"] == detachment_id)
    assert detachment["owner_ref"] == OWNER.to_dict()
    assert detachment["location_id"] == "salgueiro" and detachment["count"] > 0
    assert any(item == {"settlement_id": "salgueiro", "occupier_ref": OWNER.to_dict()}
               for item in campaign["occupations"])
    assert {key for key in campaign} == {"detachments", "commands", "positions", "standoffs", "field_engagements",
                                         "route_interdictions", "settlement_investments", "assembly_denials", "occupations"}

    claim = data["governance"]["claims"][0]
    assert claim["claimant_ref"] == OWNER.to_dict()
    assert claim["evidence_kind"] == "held_occupation" and claim["evidence_subject_id"] == "salgueiro"
    creature_view = next(item for item in data["creatures"]["creatures"] if item["id"] == DRAKE_ID)
    damage_view = data["creatures"]["damaged_sites"]
    assert creature_view["damaged_site_id"] == damage_view[0]["site_id"] == "docas-de-portovelho"
    assert damage_view[0]["damage_event_id"] == creature_view["damage_event_id"]
    assert damage_view[0]["integrity"] < 1

    assert world_snapshot(world) == before
    # The private state keeps its deliberately bounded notices only; the
    # observer did not create a force/claim/threat knowledge receipt for anyone.
    assert not any("detachment" in item.id or "authority-claim" in item.id
                   for item in world.knowledge.reports.values())


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
