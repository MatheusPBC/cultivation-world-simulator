"""Expansion cannot bypass material, labor, money, time or authority."""

import pytest
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.classes.event import FactKind
from src.systems.time import WorldClock
from src.sim.medieval.persistence import save_world, load_world, world_snapshot


def start(world):
    from src.sim.medieval.expansion import start_expansion
    facility = world.economy.facilities['works:minas-de-ferroalto']
    owner = world.economy.stocks[facility.stock_id].owner_ref
    event = record_event(world, 'expansion_decided', 'Ampliar serraria.', fact_kind=FactKind.DECISION,
        decision={'action': 'expand', 'actor_ref': owner.to_dict(),
                  'facility_id': facility.id, 'blueprint_id': 'workshop-extension'})
    return start_expansion(world, facility.id, 'workshop-extension', decision_event_id=event.id)


def work(world, day):
    from src.sim.medieval.expansion import progress_expansions
    world.clock = WorldClock(day)
    available = {g.id: g.count for g in world.society.population.values()}
    progress_expansions(world, available)
    return available


def test_real_materials_paid_work_and_two_months_before_capacity(tmp_path):
    world = create_medieval_world(73)
    project = start(world)
    cash = sum(a.balance for a in world.economy.accounts.values())
    work(world, 30)
    assert world.economy.expansions[project.id].completed_units == 5
    assert world.economy.facilities[project.facility_id].max_batches == 60
    assert world.economy.stocks['stock:ferroalto'].goods['tools'] == 15
    assert world.economy.stocks['stock:ferroalto'].goods['wood'] == 90
    path = tmp_path / 'project.mws'
    save_world(world, path)
    resumed = load_world(path)
    for value in (world, resumed):
        work(value, 60)
        assert value.economy.expansions[project.id].stage == 'completed'
        receipt = next(e for e in value.events if e.id == value.economy.expansions[project.id].last_event_id)
        assert 'concluída' in receipt.content
        assert value.economy.facilities[project.facility_id].max_batches == 70
        assert value.economy.stocks['stock:ferroalto'].goods['tools'] == 10
        assert value.economy.stocks['stock:ferroalto'].goods['wood'] == 80
        assert sum(a.balance for a in value.economy.accounts.values()) == cash
        assert sum(a.balance for a in value.economy.accounts.values()
                   if a.owner_ref.kind == 'population_group') == 36
    assert world_snapshot(world) == world_snapshot(resumed)
    before = world_snapshot(world)
    work(world, 60)
    assert world_snapshot(world) == before


def test_missing_materials_block_without_spending_or_free_progress():
    world = create_medieval_world(73)
    project = start(world)
    stock = world.economy.stocks['stock:ferroalto']
    world.economy.stocks[stock.id] = stock.model_copy(update={'goods': {**stock.goods, 'tools': 0}})
    money = dict(world.economy.accounts)
    work(world, 30)
    assert world.economy.expansions[project.id].completed_units == 0
    assert world.economy.expansions[project.id].blocker == 'input:tools'
    assert world.economy.accounts == money
    assert world.economy.facilities[project.facility_id].max_batches == 60


def test_storage_pressure_exposes_and_completes_granary_expansion():
    from src.sim.medieval.economy import produce_monthly
    from src.sim.medieval.expansion import expansion_options, start_expansion, progress_expansions

    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    facility = world.economy.facilities['works:campos-de-brumafria']
    stock = world.economy.stocks[facility.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={'capacity': world.economy.used_capacity(stock) + 50})
    produce_monthly(world)
    pressured_capacity = world.economy.stocks[stock.id].capacity

    option = next(item for item in expansion_options(world, stock.owner_ref)
                  if item.facility_id == facility.id and item.blueprint_id == 'granary-extension')
    decision = record_event(world, 'expansion_decided', 'Ampliar o armazém após pressão material de armazenamento.',
        fact_kind=FactKind.DECISION, decision={'action': 'expand', 'actor_ref': stock.owner_ref.to_dict(),
                                               'facility_id': facility.id, 'blueprint_id': option.blueprint_id},
        cause_ids=(world.economy.facilities[facility.id].last_event_id,))
    project = start_expansion(world, facility.id, option.blueprint_id, decision_event_id=decision.id)
    available = {group.id: group.count for group in world.society.population.values()}
    world.clock = WorldClock(60)
    progress_expansions(world, available)
    assert world.economy.expansions[project.id].completed_units == 3
    assert world.economy.stocks[stock.id].capacity == pressured_capacity

    world.clock = WorldClock(90)
    progress_expansions(world, available)
    assert world.economy.expansions[project.id].stage == 'completed'
    assert world.economy.stocks[stock.id].capacity == pressured_capacity + 10000
    receipt = next(event for event in reversed(world.events)
                   if event.id == world.economy.expansions[project.id].last_event_id)
    assert any(delta.owner_kind == 'stock' and delta.owner_id == stock.id
               and delta.aspect == 'capacity' for delta in receipt.deltas)


def test_public_query_exposes_construction_and_catalog():
    from src.server.medieval.queries import economy_view
    world = create_medieval_world(73)
    project = start(world)
    data = economy_view(world).model_dump(mode='json')
    assert data['expansions'][0]['id'] == project.id
    assert next(b for b in data['expansion_blueprints'] if b['id'] == 'workshop-extension')['required_units'] == 10


@pytest.mark.parametrize('change', [{'completed_units': 5, 'stage': 'building'}, {'last_event_id': 'event:1'}])
def test_save_rejects_progress_without_material_provenance(tmp_path, change):
    world = create_medieval_world(73)
    project = start(world)
    world.economy.expansions[project.id] = project.model_copy(update=change)
    with pytest.raises(ValueError):
        save_world(world, tmp_path / 'corrupt.mws')


def test_only_owner_can_authorize_and_one_active_project():
    from src.sim.medieval.expansion import start_expansion
    world = create_medieval_world(73)
    project = start(world)
    with pytest.raises(ValueError):
        start_expansion(world, project.facility_id, project.blueprint_id, decision_event_id=project.decision_event_id)
    decision = record_event(world, 'expansion_decided', 'Sem autoridade.', fact_kind=FactKind.DECISION,
        decision={'action': 'expand', 'actor_ref': {'kind': 'polity', 'id': 'auren'},
                  'facility_id': 'works:minas-de-ferroalto', 'blueprint_id': 'workshop-extension'})
    before = world_snapshot(world)
    with pytest.raises(ValueError):
        start_expansion(world, 'works:minas-de-ferroalto', 'workshop-extension', decision_event_id=decision.id)
    assert world_snapshot(world) == before


async def test_monthly_engine_shares_construction_workers_with_production():
    from src.sim.medieval.engine import MedievalSimulator
    world = create_medieval_world(73)
    project = start(world)
    # The mine asks for more labor than the currently available local artisans;
    # construction reserves its workers first on the same monthly boundary.
    mine = world.economy.facilities[project.facility_id]
    recipe = world.economy.recipes[mine.recipe_id]
    stock = world.economy.stocks[mine.stock_id]
    local_workers = sum(world.society.available_count(group.id)
                        for group in world.society.population.values()
                        if group.settlement_id == stock.location_id
                        and group.occupation == recipe.occupation)
    world.economy.facilities = {mine.id: mine.model_copy(update={'max_batches': 180})}
    world.economy.stocks[stock.id] = stock.model_copy(update={'goods': {**stock.goods, 'wood': 500}})
    await MedievalSimulator(world).step()
    assert world.economy.expansions[project.id].completed_units == 5
    builders = sum(world.economy.payrolls[project.id].workers_by_group.values())
    assert builders > 0
    assert world.economy.facilities[mine.id].last_batches == min(
        180, (local_workers - builders) // recipe.workers)
    assert world.economy.payrolls[project.id].gross == (
        builders * world.economy.expansion_blueprints[project.blueprint_id].wage_per_worker)
    assert world.economy.payrolls[mine.id].gross == (
        world.economy.facilities[mine.id].last_batches * recipe.workers * mine.wage_per_worker)


def test_project_material_demand_is_remaining_not_monthly_multiplied():
    from src.sim.medieval.demand import reserve_quantity, objective_target
    from src.sim.medieval.expansion import review_expansions
    world = create_medieval_world(73)
    project = start(world)
    review_expansions(world)
    tools_goal = next(o for o in world.strategy.objectives.values() if o.stock_id == 'stock:ferroalto' and o.resource_id == 'tools')
    assert objective_target(world, tools_goal) == 10
    assert reserve_quantity(world, 'stock:ferroalto', 'wood') == 140  #120 operating +20 construction
    work(world, 30)
    assert objective_target(world, tools_goal) == 5
    work(world, 60)
    assert objective_target(world, tools_goal) == 0


def test_monthly_policy_does_not_expand_idle_or_labor_limited_facilities():
    from src.sim.medieval.expansion import review_expansions
    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    review_expansions(world)
    assert not world.economy.expansions
    facility = world.economy.facilities['works:minas-de-ferroalto']
    world.economy.facilities[facility.id] = facility.model_copy(update={'last_batches': 60})
    review_expansions(world)
    assert len(world.economy.expansions) == 1
    review_expansions(world)
    assert len(world.economy.expansions) == 1


async def test_save_failure_rolls_back_work_wages_materials_and_capacity(tmp_path, monkeypatch):
    from src.sim.medieval.engine import MedievalSimulator
    import src.sim.medieval.engine as engine
    world = create_medieval_world(73)
    start(world)
    before = world_snapshot(world)
    def fail(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(engine, 'save_world', fail)
    with pytest.raises(OSError):
        await MedievalSimulator(world, save_path=tmp_path / 'failed.mws').step()
    assert world_snapshot(world) == before


async def test_missing_tools_trigger_real_purchase_delivery_and_later_capacity():
    from src.sim.medieval.engine import MedievalSimulator
    world = create_medieval_world(73)
    # Isolate the expansion contract from competing research demand in this prepared chain.
    world.research.technologies.clear()
    world.economy.recipes = {k: r for k, r in world.economy.recipes.items() if not r.required_technology_id}
    world.economy.expansion_blueprints = {k: b for k, b in world.economy.expansion_blueprints.items() if not b.required_technology_id}
    project = start(world)
    stock = world.economy.stocks['stock:ferroalto']
    world.economy.stocks[stock.id] = stock.model_copy(update={'goods': {**stock.goods, 'tools': 0, 'wood': 1000}})
    # Prepared shortage: no pre-existing public tools, so the workshop is the supplier.
    for key, other in list(world.economy.stocks.items()):
        if other.owner_ref.kind == 'polity':
            world.economy.stocks[key] = other.model_copy(update={'goods': {**other.goods, 'tools': 0}})
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == 30
    assert world.economy.expansions[project.id].completed_units == 0
    orders = [o for o in world.economy.freight_orders.values() if o.resource_id == 'tools' and o.destination_id == stock.id]
    assert len(orders) == 1
    blueprint = world.economy.expansion_blueprints[project.blueprint_id]
    required_tools = blueprint.inputs["tools"] * blueprint.required_units
    # The same owner may replenish the active production reserve in this
    # order; the construction obligation is the lower bound, not an exclusive
    # quantity.
    assert orders[0].quantity >= required_tools
    assert orders[0].source_id == 'stock:oficios-da-serra'
    assert world.economy.stocks[stock.id].goods['tools'] == 0
    await MedievalSimulator(world).step()
    assert world.clock.absolute_day == 31
    assert world.economy.stocks[stock.id].goods['tools'] == orders[0].quantity
    while world.clock.absolute_day < 90:
        await MedievalSimulator(world).step()
    assert world.economy.expansions[project.id].stage == 'completed'
    assert world.economy.facilities[project.facility_id].max_batches == 70
    assert world.economy.facilities[project.facility_id].last_batches == 70
    assert sum(a.balance for a in world.economy.accounts.values()) == 76000


@pytest.mark.parametrize('blocker', ['authority', 'payroll_funds', 'labor', 'site_unavailable'])
def test_progress_revalidates_constraints_without_spending(blocker):
    world = create_medieval_world(73)
    project = start(world)
    if blocker == 'authority':
        world.authority.offices = {k: v for k, v in world.authority.offices.items() if v.institution_ref != project.owner_ref}
    elif blocker == 'payroll_funds':
        account = world.economy.accounts['treasury:escarlia']
        world.economy.accounts[account.id] = account.model_copy(update={'balance': 0})
    elif blocker == 'labor':
        for key, group in list(world.society.population.items()):
            if group.settlement_id == 'ferroalto':
                world.society.population[key] = group.model_copy(update={'occupation': 'farmer'})
    else:
        site = world.map.infrastructure_sites['minas-de-ferroalto']
        site.enabled = False
    money = dict(world.economy.accounts)
    goods = dict(world.economy.stocks['stock:ferroalto'].goods)
    work(world, 30)
    assert world.economy.expansions[project.id].blocker == blocker
    assert world.economy.expansions[project.id].completed_units == 0
    assert world.economy.accounts == money
    assert world.economy.stocks['stock:ferroalto'].goods == goods
