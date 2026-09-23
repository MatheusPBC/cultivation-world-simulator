import httpx
import pytest

from src.server.medieval.app import create_app
from src.sim.medieval.demography import BIRTH_PERMILLE


def test_campaign_view_projects_live_political_settlement_without_mutating_world():
    from src.server.medieval.queries import campaign_view
    from tests.test_medieval_administration_concession import accepted_concession, concession_world
    from src.sim.medieval.persistence import world_snapshot

    world, _ = concession_world()
    proposal = accepted_concession(world)
    before = world_snapshot(world)
    view = campaign_view(world)
    settlement = next(item for item in view.political_settlements if item.id == proposal.id)
    assert settlement.proposal_kind == "administration_concession"
    assert settlement.settlement_id == proposal.clauses[0].settlement_id
    assert settlement.status == "accepted"
    assert settlement.clause_kinds == ["administration_transfer", "withdrawal"]
    assert settlement.decision_event_id == proposal.decision_event_id
    assert world_snapshot(world) == before


def test_campaign_view_hides_expired_unanswered_political_offer():
    from src.server.medieval.queries import campaign_view
    from tests.test_medieval_force_deescalation import contact_world, decide, offer_force_deescalation, force_deescalation_offer_options, OWNER

    world, _, _, _ = contact_world()
    option = force_deescalation_offer_options(world, OWNER)[0]
    proposal = offer_force_deescalation(world, OWNER, option.id, decide(world, option).id)
    world.clock = world.clock.advance(2)
    assert proposal.expires_day < world.clock.absolute_day
    assert all(item.id != proposal.id for item in campaign_view(world).political_settlements)


def test_campaign_view_exposes_ceasefire_as_live_material_settlement(monkeypatch):
    from src.server.medieval.queries import campaign_view
    from tests.test_medieval_siege_campaign import (
        ATTACKER, DEFENDER, OTHER_EXIT, siege_world, decide,
    )
    from src.sim.medieval.campaign_ceasefire import (
        campaign_ceasefire_offer_options, offer_campaign_ceasefire,
    )
    from src.sim.medieval.siege_campaign import begin_siege_campaign
    from src.sim.medieval.force import WithdrawalOption
    world, _, garrison_id, siege_option = siege_world()
    begin_siege_campaign(world, ATTACKER, siege_option.id, decide(world, siege_option).id)
    defender_id = world.society.garrisons[garrison_id].detachment_id
    monkeypatch.setattr(
        "src.sim.medieval.campaign_ceasefire.withdrawal_options",
        lambda *_args, **_kwargs: (WithdrawalOption(
            id=f"withdraw:{defender_id}:observatory", actor_ref=DEFENDER,
            detachment_id=defender_id, destination_id="brumafria", route_ids=(OTHER_EXIT,)),),
    )
    offer = next(item for item in campaign_ceasefire_offer_options(world, DEFENDER)
                 if item.kind == "mutual")
    proposal = offer_campaign_ceasefire(world, DEFENDER, offer.id, decide(world, offer).id)

    settlement = next(item for item in campaign_view(world).political_settlements
                      if item.id == proposal.id)
    assert settlement.proposal_kind == "campaign_ceasefire"
    assert settlement.settlement_id == "ferroalto"
    assert settlement.status == "offered"
    assert settlement.clause_kinds == ["campaign_withdrawal", "campaign_withdrawal"]


def test_campaign_view_projects_creature_habitat_stress_from_canonical_ecology():
    from src.classes.event import FactKind
    from src.classes.state_delta import StateDelta
    from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
    from src.run.medieval_world import create_medieval_world
    from src.server.medieval.queries import campaign_view
    from src.sim.medieval.creatures import apply_monthly_creature_ecology
    from src.sim.medieval.events import record_event

    world = create_medieval_world(73)
    route = world.map.routes[ROUTE_ID]
    before = route.quality
    route.update_runtime(quality=before / 2)
    record_event(
        world, "route_capacity_reduced_for_habitat", "A capacidade da rota caiu.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=ROUTE_ID, aspect="quality",
                            before=str(before), after=str(route.quality)),),
    )
    apply_monthly_creature_ecology(world)
    ecology_event_ids = {creature.last_event_id for creature in world.creatures.creatures.values()}
    threat = next(item for item in campaign_view(world).threats
                  if item.kind == "creature_habitat_stress")
    assert threat.route_id == ROUTE_ID
    assert threat.source_event_id in ecology_event_ids


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
        assert sum(g["count"] for g in data["society"]["population_groups"]) == data["world"]["population"]
        initial_population = 10900
        assert initial_population <= data["world"]["population"] <= (
            initial_population + initial_population * BIRTH_PERMILLE // 1000
        )
        assert all(m["updated_day"] == 30 for m in data["economy"]["markets"])
        assert len(data["economy"]["payrolls"]) == 11
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
        assert all(p["stage"] in {"satisfied", "await_delivery", "blocked"}
                   for p in plans if p["objective_id"] in food_goals)
        assert any(p["stage"] == "await_delivery" for p in plans if p["objective_id"] not in food_goals)
        governance = await client.get("/api/v2/query/governance")
        assert governance.status_code == 200
        assert governance.json()["data"] == data["governance"]
        research = await client.get("/api/v2/query/research")
        assert research.status_code == 200
        assert research.json()["data"] == data["research"]
        project_technologies = {p["technology_id"] for p in data["research"]["projects"]}
        assert "irrigation" in project_technologies
        assert project_technologies <= {tech["id"] for tech in data["research"]["technologies"]}
        assert all(p["completed_units"] == 0 for p in data["research"]["projects"])
        assert data["research"]["knowledge"] == []
        diplomacy = await client.get("/api/v2/query/diplomacy")
        assert diplomacy.status_code == 200
        # The monthly civil turn may already have opened aid notices.  The
        # contract is that the dedicated query and the atomic observatory
        # expose the same complete diplomacy projection.
        assert diplomacy.json()["data"] == data["diplomacy"]


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
    from src.classes.causal_origin import CausalOrigin
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
    claim_decision = decide(world, claim_option)
    execute_claim(world, OWNER, claim_option.id, claim_decision.id)
    claim_event = next(item for item in reversed(world.events)
                       if item.event_type == "authority_claim_declared")
    assert claim_event.causal_origin == CausalOrigin.ACTOR_DECISION
    assert claim_event.causal_payload == {
        "decision_event_id": claim_decision.id,
        "actor_ref": OWNER.to_dict(),
        "selected_affordance_id": claim_option.id,
    }

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
    from src.server.medieval.queries import campaign_view
    threat = next(item for item in campaign_view(world).threats
                  if item.id == f"creature-demand:{demand.id}")
    assert threat.route_id == demand.route_id and threat.source_event_id == demand.perception_event_id
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
                                         "route_interdictions", "settlement_investments", "garrisons",
                                         "siege_campaigns", "assembly_denials", "occupations",
                                         "territorial_controls", "political_settlements", "threats"}

    claim = data["governance"]["claims"][0]
    assert claim["claimant_ref"] == OWNER.to_dict()
    assert claim["evidence_kind"] == "held_occupation" and claim["evidence_subject_id"] == "salgueiro"
    creature_view = next(item for item in data["creatures"]["creatures"] if item["id"] == DRAKE_ID)
    damage_view = data["creatures"]["damaged_sites"]
    assert creature_view["damaged_site_id"] == damage_view[0]["site_id"] == "docas-de-portovelho"
    assert damage_view[0]["damage_event_id"] == creature_view["damage_event_id"]
    assert damage_view[0]["integrity"] < 1
    impact = data["creatures"]["hazard_impacts"][0]
    assert impact["event_id"] == damage_view[0]["damage_event_id"]
    assert impact["hazard_kind"] == "river_drake"
    assert impact["target_ref"] == {"kind": "infrastructure_site", "id": "docas-de-portovelho"}
    assert impact["resistance"] == {"standing_ward": False}
    hazard_threat = next(item for item in campaign["threats"] if item["kind"] == "hazard_damage")
    assert hazard_threat["site_id"] == "docas-de-portovelho"
    assert hazard_threat["source_event_id"] == damage_view[0]["damage_event_id"]

    assert world_snapshot(world) == before
    # The private state keeps its deliberately bounded notices only; the
    # observer did not create a force/claim/threat knowledge receipt for anyone.
    assert not any("detachment" in item.id or "authority-claim" in item.id
                   for item in world.knowledge.reports.values())


@pytest.mark.asyncio
async def test_authority_claim_rejects_a_prior_day_decision_without_mutation():
    from src.sim.medieval.authority_claims import authority_claim_options, execute_option as execute_claim
    from src.sim.medieval.force import force_options, occupy_settlement
    from src.sim.medieval.persistence import world_snapshot
    from tests.test_medieval_campaign_supply import OWNER, campaign_world, decide

    world, _ = await campaign_world()
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)
    option = next(item for item in authority_claim_options(world, OWNER)
                  if item.evidence_kind == "held_occupation")
    decision = decide(world, option)
    world.clock = world.clock.advance(1)
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="exact canonical decision"):
        execute_claim(world, OWNER, option.id, decision.id)

    assert world_snapshot(world) == before


@pytest.mark.asyncio
async def test_observatory_projects_completed_sale_receipts_and_their_why_chain(tmp_path):
    """A Dao read joins completed sale evidence, without making it actor knowledge."""
    from src.sim.medieval.persistence import SCHEMA, load_world, save_world, world_snapshot
    from src.sim.medieval.technology_sale import (execute_technology_sale,
                                                   record_technology_sale_acceptance,
                                                   record_technology_sale_request,
                                                   technology_sale_acceptance_options,
                                                   technology_sale_options)
    from tests.test_medieval_technology_sale import BUYER, SELLER, researched_world

    world = researched_world()
    option = technology_sale_options(world, BUYER)[0]
    request = record_technology_sale_request(world, BUYER, option.id)
    acceptance = record_technology_sale_acceptance(
        world, SELLER, technology_sale_acceptance_options(world, SELLER)[0].id)
    receipt = execute_technology_sale(world, BUYER, option.id, request.id, acceptance.id)
    payment_event_id = world.economy.payments[request.id]
    learned = next(item for item in world.knowledge.technologies.values()
                   if item.owner_ref == BUYER and item.technology_id == option.technology_id)
    save_path = tmp_path / "sale-schema-67.mws"
    save_world(world, save_path)
    assert SCHEMA == 67
    world = load_world(save_path)

    app = create_app(save_dir=lambda: tmp_path / "runtime")
    app.state.runtime._activate(world)
    before = world_snapshot(world)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        observed = (await client.get("/api/v2/query/observatory")).json()["data"]
        sale = observed["research"]["technology_sales"]
        assert sale == [{"receipt_event_id": receipt.id, "buyer_ref": BUYER.to_dict(), "seller_ref": SELLER.to_dict(),
                         "technology_id": option.technology_id, "request_event_id": request.id,
                         "acceptance_event_id": acceptance.id, "payment_event_id": payment_event_id,
                         "knowledge_event_id": learned.event_id}]
        why = (await client.get(f"/api/v2/query/causal/{receipt.id}")).json()["data"]
    assert {request.id, acceptance.id, payment_event_id, learned.event_id} <= {event["id"] for event in why["causes"]}
    assert world_snapshot(world) == before


@pytest.mark.asyncio
async def test_observatory_projects_persistent_siege_campaign_without_control_transfer(tmp_path):
    from src.sim.medieval.persistence import world_snapshot
    from src.sim.medieval.siege_campaign import begin_siege_campaign
    from tests.test_medieval_siege_campaign import ATTACKER, decide, siege_world

    world, _, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    app = create_app(save_dir=lambda: tmp_path / "runtime")
    app.state.runtime._activate(world)
    before = world_snapshot(world)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        observed = (await client.get("/api/v2/query/observatory")).json()["data"]
        why = (await client.get(f"/api/v2/query/causal/{campaign.last_event_id}")).json()["data"]
    assert observed["campaigns"]["siege_campaigns"] == [campaign.model_dump(mode="json")]
    assert campaign.decision_event_id in {event["id"] for event in why["causes"]}
    assert world_snapshot(world) == before


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


def test_campaign_view_projects_active_route_interdiction_as_material_threat():
    from src.server.medieval.queries import campaign_view
    from src.sim.medieval.route_interdiction import execute_route_interdiction_option, route_interdiction_options
    from tests.test_medieval_route_interdiction import OWNER, decide, prepared_contact_world

    world, detachment_id = prepared_contact_world()
    option = next(item for item in route_interdiction_options(world, OWNER, detachment_id=detachment_id)
                  if item.kind == "interdict")
    active = execute_route_interdiction_option(world, OWNER, option.id, decide(world, option).id)
    threat = next(item for item in campaign_view(world).threats
                  if item.id == f"route-interdiction:{active.id}")
    assert threat.kind == "route_interdiction"
    assert threat.route_id == option.route_id and threat.status == "active"
