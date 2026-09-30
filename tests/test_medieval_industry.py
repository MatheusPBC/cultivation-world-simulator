"""Prepared industrial chain; initial holdings are explicit, not natural outcomes."""
import pytest
from tests.test_medieval_research import prepared, authorize, work
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.expansion import (expansion_adapters, expansion_options, progress_expansions,
                                       start_expansion)
from src.sim.medieval.economy import _delta, monthly_workforce, produce_monthly
from src.sim.medieval.infrastructure import damage_site
from src.sim.medieval.persistence import save_world, load_world, world_snapshot
from src.run.medieval_world import create_medieval_world
from src.systems.time import WorldClock

MINE = 'works:minas-de-ferroalto'


def build(world, blueprint, facility=MINE):
    owner = world.economy.stocks[world.economy.facilities[facility].stock_id].owner_ref
    option = next((item for item in expansion_options(world, owner)
                   if item.facility_id == facility and item.blueprint_id == blueprint), None)
    decision = record_event(world, 'industry_decided', 'Construir uma linha produtiva.', fact_kind=FactKind.DECISION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={'decision_source': {'kind': 'api'}},
        decision=(option.decision() if option else
                  {'action': 'expand', 'actor_ref': owner.to_dict(),
                   'facility_id': facility, 'blueprint_id': blueprint}))
    if option is None:
        return start_expansion(world, facility, blueprint, decision_event_id=decision.id)
    expansion_adapters()[0].execute_fn(world, owner, option.id, decision.id)
    return next(project for project in world.economy.expansions.values()
                if project.facility_id == facility and project.blueprint_id == blueprint
                and project.started_day == world.clock.absolute_day)


def construct(world, day):
    world.clock = WorldClock(day)
    progress_expansions(world, monthly_workforce(world))


def industrial_world():
    world = prepared()
    stock = world.economy.stocks['stock:ferroalto']
    world.economy.stocks[stock.id] = stock.model_copy(update={'goods': {**stock.goods, 'wood': 2000, 'iron': 1000, 'tools': 200}})
    # This prepared chain isolates one complex, leaving real cohort labor and money.
    world.economy.facilities = {MINE: world.economy.facilities[MINE]}
    authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    return world


def authorize_from_current_menu(world, technology_id, actor_id='escarlia'):
    from src.classes.mechanical_language import EntityRef
    from src.sim.medieval.research import accept_research_work, researcher_work_options
    from src.sim.medieval.research_policy import execute_research_option, research_options

    actor = EntityRef('polity', actor_id)
    option = next(item for item in research_options(world, actor)
                  if item.technology_id == technology_id)
    sponsor = record_event(
        world, 'research_option_decided', 'A instituição seleciona uma pesquisa atual.',
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={'decision_source': {'kind': 'api'}}, decision=option.decision())
    execute_research_option(world, actor, option.id, sponsor.id)

    world.clock = WorldClock(sponsor.day + 1)
    world.agenda.cancel(f'character-rite-offer-review:{option.researcher_id}:{sponsor.id}')
    work_option = next(item for item in researcher_work_options(world, option.researcher_id)
                       if item.technology_id == technology_id)
    researcher_decision = record_event(
        world, 'research_work_decided', 'O pesquisador aceita uma oferta atual.',
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={'decision_source': {'kind': 'api'}}, decision=work_option.decision())
    project = accept_research_work(world, option.researcher_id, work_option.id,
                                   researcher_decision.id)
    assert set(sponsor.decision) == {'action', 'actor_ref', 'selected_affordance_id'}
    assert set(researcher_decision.decision) == {
        'action', 'actor_ref', 'selected_affordance_id'}
    assert sponsor.causal_origin is CausalOrigin.ACTOR_DECISION
    assert researcher_decision.causal_origin is CausalOrigin.ACTOR_DECISION
    return project


def canonical_industrial_world():
    """The integrated chain starts with menu-selected metallurgy, not a payload shortcut."""
    world = prepared()
    stock = world.economy.stocks['stock:ferroalto']
    world.economy.stocks[stock.id] = stock.model_copy(
        update={'goods': {**stock.goods, 'wood': 2000, 'iron': 1000, 'tools': 200}})
    world.economy.facilities = {MINE: world.economy.facilities[MINE]}
    project = authorize_from_current_menu(world, 'metallurgy')
    for day in (30, 60, 90):
        work(world, day)
    assert world.research.projects[project.id].stage == 'completed'
    assert world.knowledge.technologies[
        'technology:polity:escarlia:metallurgy'].channel == 'research'
    return world


def test_new_line_requires_knowledge_and_material_completion_and_survives_load(tmp_path):
    world = prepared()
    with pytest.raises(ValueError, match='knowledge'):
        build(world, 'charcoal-kilns')
    world = industrial_world()
    parent = world.economy.facilities[MINE]
    stock_before = dict(world.economy.stocks['stock:ferroalto'].goods)
    project = build(world, 'charcoal-kilns')
    line_id = 'line:minas-de-ferroalto:charcoal'
    construct(world, 120)
    assert line_id not in world.economy.facilities
    construct(world, 150)
    assert world.economy.expansions[project.id].stage == 'completed'
    line = world.economy.facilities[line_id]
    assert (line.recipe_id, line.max_batches, line.stock_id) == ('charcoal', 10, 'stock:ferroalto')
    assert world.economy.facilities[MINE].recipe_id == parent.recipe_id
    assert world.economy.facilities[MINE].max_batches == parent.max_batches
    assert world.economy.stocks[line.stock_id].goods['wood'] == stock_before['wood'] - 12
    assert world.economy.stocks[line.stock_id].goods['tools'] == stock_before['tools'] - 6
    assert sum(a.balance for a in world.economy.accounts.values()) == 76000
    save_world(world, tmp_path / 'industry.mws')
    resumed = load_world(tmp_path / 'industry.mws')
    assert world_snapshot(world) == world_snapshot(resumed)
    produce_monthly(resumed)
    assert resumed.economy.stocks[line.stock_id].goods['coal'] == 10
    produced = resumed.event_index()[resumed.economy.facilities[line_id].last_event_id]
    learned = next(item for item in resumed.knowledge.technologies.values()
                   if item.owner_ref == resumed.economy.stocks[line.stock_id].owner_ref
                   and item.technology_id == 'metallurgy')
    assert learned.event_id in {link.cause_event_id for link in produced.causal_links}
    resumed.clock = resumed.clock.advance(30)
    no_available_workers = {group_id: 0 for group_id in monthly_workforce(resumed)}
    produce_monthly(resumed, no_available_workers)
    assert resumed.economy.facilities[line_id].last_batches == 0
    assert 'labor' in resumed.economy.facilities[line_id].last_limitations
    site = resumed.map.infrastructure_sites[line.site_id]
    damage = record_event(resumed, 'fixture_site_damage', 'Instalação inutilizada no cenário pressionado.',
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta('site', site.id, 'integrity', site.integrity, 0.0),))
    damage_site(resumed, site.id, event_id=damage.id)
    resumed.clock = resumed.clock.advance(30)
    produce_monthly(resumed)
    assert resumed.economy.facilities[line_id].last_batches == 0
    assert 'site_integrity' in resumed.economy.facilities[line_id].last_limitations
    save_world(resumed, tmp_path / 'industry-limited.mws')
    assert world_snapshot(load_world(tmp_path / 'industry-limited.mws')) == world_snapshot(resumed)
    with pytest.raises(ValueError, match='line|existing'):
        build(resumed, 'charcoal-kilns')


def test_two_anchor_facilities_cannot_authorize_the_same_line():
    world = industrial_world()
    build(world, 'charcoal-kilns')
    world.economy.facilities['second-anchor'] = world.economy.facilities[MINE].model_copy(update={'id': 'second-anchor'})
    with pytest.raises(ValueError, match='line|existing'):
        build(world, 'charcoal-kilns', 'second-anchor')


def test_paid_mineral_separation_feeds_gunpowder_research_and_two_real_lines(tmp_path):
    """The authored powder chain has no free technology or manufactured goods."""
    from src.classes.mechanical_language import EntityRef
    from src.sim.medieval.expansion import expansion_adapters, expansion_options

    world = industrial_world()
    owner = EntityRef("polity", "escarlia")

    def commission(blueprint_id):
        option = next(item for item in expansion_options(world, owner)
                      if item.blueprint_id == blueprint_id)
        choice = record_event(
            world, "gunpowder_line_decided", "Escolha atual de uma affordance de produção.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            causal_payload={"decision_source": {"kind": "api"}}, decision=option.decision())
        expansion_adapters()[0].execute_fn(world, owner, option.id, choice.id)
        return next(project for project in world.economy.expansions.values()
                    if project.blueprint_id == blueprint_id
                    and project.started_day == world.clock.absolute_day)

    stock = world.economy.stocks["stock:ferroalto"]
    root = record_event(
        world, "gunpowder_fixture_coal", "Premissa explícita de carvão disponível para a fixture.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "gunpowder_test_fuel",
            "source_refs": [{"kind": "scenario", "id": "gunpowder_production_fixture"},
                            {"kind": "stock", "id": stock.id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("stock", stock.id, "coal", stock.goods.get("coal", 0), 100),))
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "coal": 100},
        "last_event_ids": {**stock.last_event_ids, "coal": root.id}})

    # The second product is available after real iron production even while
    # iron stocks are abundant; shared storage still bounds actual output.
    produce_monthly(world)
    assert any(option.blueprint_id == "mineral-separation-works"
               for option in expansion_options(world, owner))
    project = commission("mineral-separation-works")
    construct(world, 120)
    construct(world, 150)
    line_id = "line:minas-de-ferroalto:mineral_separation"
    assert world.economy.expansions[project.id].stage == "completed"
    assert world.economy.facilities[line_id].recipe_id == "mineral_separation"
    produce_monthly(world)
    stock = world.economy.stocks["stock:ferroalto"]
    assert stock.goods["saltpeter"] >= 2 and stock.goods["sulfur"] >= 1
    production = world.event_index()[world.economy.facilities[line_id].last_event_id]
    metallurgy = world.knowledge.technologies["technology:polity:escarlia:metallurgy"]
    assert metallurgy.event_id in {link.cause_event_id for link in production.causal_links}
    assert any(delta.owner_kind == "stock" and delta.owner_id == stock.id
               and delta.aspect == "saltpeter" for delta in production.deltas)

    research_project = authorize(world, "gunpowder", "escarlia")
    for day in (180, 210, 240, 270):
        work(world, day)
    assert world.research.projects[research_project.id].stage == "completed"
    assert world.knowledge.knows(owner, "gunpowder")

    produce_monthly(world)
    powder_project = commission("powder-mill")
    construct(world, 300)
    construct(world, 330)
    assert world.economy.expansions[powder_project.id].stage == "completed"
    powder_line = "line:minas-de-ferroalto:powder_mixing"
    assert world.economy.stocks[stock.id].goods.get("gunpowder", 0) == 0
    produce_monthly(world)
    assert world.economy.stocks[stock.id].goods.get("gunpowder", 0) > 0
    powder_receipt = world.event_index()[world.economy.facilities[powder_line].last_event_id]
    gunpowder = world.knowledge.technologies["technology:polity:escarlia:gunpowder"]
    assert gunpowder.event_id in {link.cause_event_id for link in powder_receipt.causal_links}

    artillery_project = commission("artillery-foundry")
    for day in (360, 390, 420):
        construct(world, day)
    assert world.economy.expansions[artillery_project.id].stage == "completed"
    artillery_line = "line:minas-de-ferroalto:artillery_casting"
    assert world.economy.stocks[stock.id].goods.get("artillery", 0) == 0
    produce_monthly(world)
    assert world.economy.stocks[stock.id].goods.get("artillery", 0) > 0
    artillery_receipt = world.event_index()[world.economy.facilities[artillery_line].last_event_id]
    assert gunpowder.event_id in {link.cause_event_id for link in artillery_receipt.causal_links}
    stock = world.economy.stocks[stock.id]

    # The produced stock, not a second scenario grant, now feeds the campaign.
    # Troops and the defender are explicit scenario premises so this test isolates
    # the already-implemented Freight -> investment -> bombardment composition.
    from src.sim.medieval.campaign_ordnance import (BOMBARD_ACTION, DISPATCH_ACTION,
        campaign_ordnance_options, execute_campaign_ordnance_option)
    from src.sim.medieval.campaign_supply import observe_campaign_supply_needs
    from src.sim.medieval.dated import resolve_dated
    from src.sim.medieval.route_intelligence import refresh_route_reports
    from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
        settlement_investment_options)
    from src.sim.medieval.siege_campaign import begin_siege_campaign, siege_campaign_options
    from tests.test_medieval_siege_campaign import (_defending_garrison, _prepared_attacker, decide)

    attacker = owner
    defender = EntityRef("polity", "auren")
    target = "pontenegro"
    attacker_id = _prepared_attacker(world, actor=attacker, location=target,
                                     count=40, provisions=2000)
    defender_garrison_id = _defending_garrison(world, owner=defender, location=target)
    target_region = world.society.settlements[target].region_id
    target_routes = tuple(sorted(route.id for route in world.map.routes.values()
                                 if target_region in route.endpoint_region_ids))
    refresh_route_reports(world, route_ids=target_routes)
    observe_campaign_supply_needs(world)
    bag_id = f"stock:camp:{attacker_id}"
    assert world.economy.stocks[bag_id].owner_ref == owner
    assert world.economy.stocks[stock.id].owner_ref == owner

    def decide_ordnance(action, option):
        return record_event(world, "production_campaign_decision", "Escolha material para campanha.",
            fact_kind=FactKind.DECISION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": action, "actor_ref": owner.to_dict(),
                      "selected_affordance_id": option.id},
            causal_payload={"decision_source": {"kind": "api"}})

    production_ids = {resource_id: stock.last_event_ids[resource_id]
                      for resource_id in ("artillery", "gunpowder")}
    assert production_ids["artillery"] == artillery_receipt.id
    def ancestors(event_id):
        found, pending = set(), [event_id]
        while pending:
            current_id = pending.pop()
            event = world.event_index().get(current_id)
            if event is None:
                continue
            for link in event.causal_links:
                if link.cause_event_id not in found:
                    found.add(link.cause_event_id)
                    pending.append(link.cause_event_id)
        return found

    assert powder_receipt.id in ancestors(production_ids["gunpowder"])
    for resource_id, production_id in production_ids.items():
        producing_event = world.event_index()[production_id]
        assert producing_event.event_type == "production_completed"
        assert any(delta.owner_kind == "stock" and delta.owner_id == stock.id
                   and delta.aspect == resource_id for delta in producing_event.deltas)
        option = next(item for item in campaign_ordnance_options(world, attacker)
                      if item.kind == "dispatch" and item.resource_id == resource_id
                      and item.source_stock_id == stock.id)
        assert option.route_ids and option.route_report_event_ids
        decision = decide_ordnance(DISPATCH_ACTION, option)
        order = execute_campaign_ordnance_option(world, attacker, option.id, decision.id)
        assert order.route_ids == option.route_ids
        dispatch_event = world.event_index()[order.last_event_id]
        assert production_id in {link.cause_event_id for link in dispatch_event.causal_links}
        assert set(option.route_report_event_ids) <= {
            link.cause_event_id for link in dispatch_event.causal_links
        }

    for _ in range(15):
        if world.economy.stocks[bag_id].goods.get("artillery", 0) == 1 \
                and world.economy.stocks[bag_id].goods.get("gunpowder", 0) >= 3:
            break
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
    assert world.economy.stocks[bag_id].goods.get("artillery", 0) == 1
    assert world.economy.stocks[bag_id].goods.get("gunpowder", 0) >= 3
    delivered_event_ids = {resource_id: world.economy.stocks[bag_id].last_event_ids[resource_id]
                           for resource_id in production_ids}
    for resource_id, production_id in production_ids.items():
        assert production_id in ancestors(delivered_event_ids[resource_id])

    investment = next(item for item in settlement_investment_options(
        world, attacker, detachment_id=attacker_id) if item.kind == "invest")
    execute_settlement_investment_option(world, attacker, investment.id,
                                         decide(world, investment).id)
    siege = next(item for item in siege_campaign_options(world, attacker)
                 if item.defender_garrison_id == defender_garrison_id)
    campaign = begin_siege_campaign(world, attacker, siege.id, decide(world, siege).id)
    bombard = next(item for item in campaign_ordnance_options(world, attacker)
                   if item.kind == "bombard" and item.campaign_id == campaign.id)
    shot = execute_campaign_ordnance_option(
        world, attacker, bombard.id, decide_ordnance(BOMBARD_ACTION, bombard).id)
    assert world.economy.stocks[bag_id].goods["gunpowder"] == 2
    assert shot.causal_payload["campaign_id"] == campaign.id
    assert delivered_event_ids["artillery"] in {link.cause_event_id for link in shot.causal_links}
    assert delivered_event_ids["gunpowder"] in {link.cause_event_id for link in shot.causal_links}
    validate_history(world.events, world.clock.absolute_day)
    path = tmp_path / "gunpowder-industry.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_offline_technology_policy_rechecks_lines_after_each_commit():
    from src.sim.medieval.research_policy import _apply_known_techniques

    world = industrial_world()
    world.economy.facilities['second-anchor'] = world.economy.facilities[MINE].model_copy(
        update={'id': 'second-anchor'})

    _apply_known_techniques(world)

    projects = [project for project in world.economy.expansions.values()
                if project.blueprint_id == 'charcoal-kilns']
    assert len(projects) == 1
    assert len([event for event in world.events if event.event_type == 'adaptation_decided'
                and event.decision['blueprint_id'] == 'charcoal-kilns']) == 1


def test_advanced_knowledge_does_not_manufacture_engines_or_steel():
    world = industrial_world()
    assert world.research.technologies['steel'].prerequisites == ('metallurgy',)
    assert world.research.technologies['steam_engineering'].prerequisites == ('steel',)
    assert world.economy.stocks['stock:ferroalto'].goods.get('steel', 0) == 0
    assert world.economy.stocks['stock:ferroalto'].goods.get('steam_engines', 0) == 0
    with pytest.raises(ValueError, match='knowledge'):
        build(world, 'steel-furnaces')


def tick(world, day):
    work(world, day)
    construct(world, day)
    produce_monthly(world)


def test_complete_steel_and_steam_chain_consumes_machines_and_needs_fuel(tmp_path):
    from collections import Counter
    from tools.medieval_autonomy_smoke import resource_totals
    world = canonical_industrial_world()
    initial_resources, initial_events = resource_totals(world), len(world.events)
    build(world, 'charcoal-kilns')
    for day in (120, 150): tick(world, day)
    steel_research = authorize_from_current_menu(world, 'steel')
    for day in (180, 210, 240): tick(world, day)
    assert world.research.projects[steel_research.id].stage == 'completed'
    assert world.knowledge.technologies['technology:polity:escarlia:steel'].channel == 'research'
    assert world.economy.stocks['stock:ferroalto'].goods.get('steel', 0) == 0
    build(world, 'steel-furnaces')
    for day in (270, 300): tick(world, day)
    assert world.economy.stocks['stock:ferroalto'].goods['steel'] == 20
    steam_research = authorize_from_current_menu(world, 'steam_engineering')
    for day in (330, 360, 390): tick(world, day)
    assert world.research.projects[steam_research.id].stage == 'completed'
    assert world.knowledge.technologies[
        'technology:polity:escarlia:steam_engineering'].channel == 'research'
    assert world.economy.stocks['stock:ferroalto'].goods.get('steam_engines', 0) == 0
    build(world, 'engine-workshop')
    for day in (420, 450): tick(world, day)
    assert world.economy.stocks['stock:ferroalto'].goods['steam_engines'] == 10
    build(world, 'efficient-furnaces')
    for day in (480, 510): tick(world, day)
    assert world.economy.facilities[MINE].recipe_id == 'efficient_ironworking'
    machines = world.economy.stocks['stock:ferroalto'].goods['steam_engines']
    # Prepared operating choice: stop assembly after obtaining the machines.
    for key, line in list(world.economy.facilities.items()):
        world.economy.facilities[key] = line.model_copy(update={'max_batches': 1 if key == MINE else 0})
    project = build(world, 'steam-pumps')
    construct(world, 540)
    assert world.economy.facilities[MINE].recipe_id == 'efficient_ironworking'
    construct(world, 570)
    assert world.economy.facilities[MINE].recipe_id == 'steam_ironworking'
    assert world.economy.stocks['stock:ferroalto'].goods['steam_engines'] == machines - 6
    assert world.economy.expansions[project.id].stage == 'completed'
    while world.economy.stocks['stock:ferroalto'].goods.get('coal', 0):
        world.clock = world.clock.advance(30)
        produce_monthly(world)
        assert world.clock.absolute_day < 1500
    world.clock = world.clock.advance(30)
    produce_monthly(world)
    assert world.economy.facilities[MINE].last_batches == 0
    assert 'input:coal' in world.economy.facilities[MINE].last_limitations
    kiln_id = 'line:minas-de-ferroalto:charcoal'
    world.economy.facilities[kiln_id] = world.economy.facilities[kiln_id].model_copy(update={'max_batches': 10})
    before = world.economy.stocks['stock:ferroalto'].goods['iron']
    world.clock = world.clock.advance(30)
    produce_monthly(world)
    assert world.economy.stocks['stock:ferroalto'].goods['iron'] == before + 12
    assert world.economy.stocks['stock:ferroalto'].goods['coal'] == 9
    assert sum(a.balance for a in world.economy.accounts.values()) == 76000
    changes = Counter()
    for event in world.events[initial_events:]:
        if event.event_type in {'research_progressed', 'expansion_progressed', 'production_completed', 'production_limited'}:
            for delta in event.deltas:
                if delta.owner_kind == 'stock':
                    changes[delta.aspect] += int(delta.after) - int(delta.before)
    assert resource_totals(world) == {r: q + changes[r] for r, q in initial_resources.items()}
    save_world(world, tmp_path / 'steam.mws')
    assert world_snapshot(load_world(tmp_path / 'steam.mws')) == world_snapshot(world)


def test_monthly_policy_commissions_feasible_line_and_adds_its_input_objective():
    from src.sim.medieval.research_policy import review_research
    from src.sim.medieval.investment import review_investment
    world = industrial_world()
    review_research(world)
    assert any(p.blueprint_id == 'charcoal-kilns' for p in world.economy.expansions.values())
    construct(world, 120); construct(world, 150)
    # The completed line needs wood even if bootstrap objectives were absent.
    world.strategy.objectives.clear()
    review_investment(world)
    assert any(o.stock_id == 'stock:ferroalto' and o.resource_id == 'wood' for o in world.strategy.objectives.values())


def test_offline_investment_decision_is_explicitly_actor_authored():
    from src.sim.medieval.investment import review_investment

    world = create_medieval_world(73)
    facility = next(iter(world.economy.facilities.values()))
    world.clock = WorldClock(30)
    world.economy.facilities[facility.id] = facility.model_copy(update={
        'max_batches': 10, 'last_batches': 9, 'last_limitations': ('storage',),
    })
    account = world.economy.accounts[facility.payroll_account_id]
    world.economy.accounts[account.id] = account.model_copy(update={'balance': 1_000_000})
    stock = world.economy.stocks[facility.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(update={
        'goods': {**stock.goods, 'wood': 1000, 'stone': 1000, 'tools': 1000, 'food': 10000},
    })

    review_investment(world)

    decision = next(event for event in world.events if event.event_type == 'expansion_decided')
    assert decision.causal_origin.value == 'actor_decision'
    assert decision.causal_payload['decision_source'] == {
        'kind': 'fallback', 'policy': 'routine-rules', 'rule': 'investment',
    }
    assert world.economy.expansions


@pytest.mark.asyncio
async def test_line_commissioning_rolls_back_with_failed_save(tmp_path, monkeypatch):
    from src.sim.medieval.engine import MedievalSimulator
    world = industrial_world()
    build(world, 'charcoal-kilns')
    construct(world, 120)
    before = world_snapshot(world)
    def fail(*args, **kwargs): raise OSError('disk full')
    monkeypatch.setattr('src.sim.medieval.engine.save_world', fail)
    with pytest.raises(OSError, match='disk full'):
        await MedievalSimulator(world, save_path=tmp_path / 'failed.mws').step()
    assert world_snapshot(world) == before
    assert 'line:minas-de-ferroalto:charcoal' not in world.economy.facilities


def test_completed_line_cannot_disappear_from_save():
    world = industrial_world()
    build(world, 'charcoal-kilns')
    construct(world, 120); construct(world, 150)
    del world.economy.facilities['line:minas-de-ferroalto:charcoal']
    with pytest.raises(ValueError, match='line'):
        world_snapshot(world)


def test_operating_an_advanced_line_requires_its_owners_knowledge():
    world = industrial_world()
    build(world, 'charcoal-kilns')
    construct(world, 120); construct(world, 150)
    world.knowledge.technologies.clear()
    produce_monthly(world)
    line = world.economy.facilities['line:minas-de-ferroalto:charcoal']
    assert line.last_batches == 0
    assert 'knowledge' in line.last_limitations
    assert world.economy.stocks[line.stock_id].goods.get('coal', 0) == 0
