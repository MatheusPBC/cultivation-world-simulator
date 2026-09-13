"""Prepared industrial chain; initial holdings are explicit, not natural outcomes."""
import pytest
from tests.test_medieval_research import prepared, authorize, work
from src.classes.event import FactKind
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import start_expansion, progress_expansions
from src.sim.medieval.economy import monthly_workforce, produce_monthly
from src.sim.medieval.persistence import save_world, load_world, world_snapshot
from src.systems.time import WorldClock

MINE = 'works:minas-de-ferroalto'


def build(world, blueprint, facility=MINE):
    owner = world.economy.stocks[world.economy.facilities[facility].stock_id].owner_ref
    decision = record_event(world, 'industry_decided', 'Construir uma linha produtiva.', fact_kind=FactKind.DECISION,
        decision={'action': 'expand', 'actor_ref': owner.to_dict(), 'facility_id': facility, 'blueprint_id': blueprint})
    return start_expansion(world, facility, blueprint, decision_event_id=decision.id)


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
    with pytest.raises(ValueError, match='line|existing'):
        build(resumed, 'charcoal-kilns')


def test_two_anchor_facilities_cannot_authorize_the_same_line():
    world = industrial_world()
    build(world, 'charcoal-kilns')
    world.economy.facilities['second-anchor'] = world.economy.facilities[MINE].model_copy(update={'id': 'second-anchor'})
    with pytest.raises(ValueError, match='line|existing'):
        build(world, 'charcoal-kilns', 'second-anchor')


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
    world = industrial_world()
    initial_resources, initial_events = resource_totals(world), len(world.events)
    build(world, 'charcoal-kilns')
    for day in (120, 150): tick(world, day)
    authorize(world, 'steel')
    for day in (180, 210, 240): tick(world, day)
    assert world.economy.stocks['stock:ferroalto'].goods.get('steel', 0) == 0
    build(world, 'steel-furnaces')
    for day in (270, 300): tick(world, day)
    assert world.economy.stocks['stock:ferroalto'].goods['steel'] == 20
    authorize(world, 'steam_engineering')
    for day in (330, 360, 390): tick(world, day)
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
