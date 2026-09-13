"""Knowledge is learned by an actor; applying it needs real work and materials."""

import pytest
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import save_world, load_world, world_snapshot
from src.systems.time import WorldClock


def prepared():
    world = create_medieval_world(73)
    lead = world.society.characters['character:011']
    world.society.characters[lead.id] = lead.model_copy(update={'skills': lead.skills.model_copy(update={'craftsmanship': 40})})
    return world


def authorize(world, technology_id='metallurgy', actor_id='escarlia'):
    from src.sim.medieval.research import start_research
    terms = {'technology_id': technology_id, 'site_id': 'minas-de-ferroalto',
             'stock_id': 'stock:ferroalto', 'account_id': f'treasury:{actor_id}', 'researcher_id': 'character:011'}
    sponsor = record_event(world, 'research_decided', 'Financiar pesquisa.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action': 'research', 'actor_ref': EntityRef('polity', actor_id).to_dict()})
    accepted = record_event(world, 'research_accepted', 'Aceitar trabalho.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action': 'research_work', 'actor_ref': EntityRef('character', 'character:011').to_dict()},
        cause_ids=(sponsor.id,))
    return start_research(world, **terms, sponsor_decision_id=sponsor.id, researcher_decision_id=accepted.id)


def work(world, day):
    from src.sim.medieval.research import progress_research
    from src.sim.medieval.economy import monthly_workforce
    world.clock = WorldClock(day)
    progress_research(world, monthly_workforce(world))


def test_research_costs_time_materials_and_wages_without_changing_production(tmp_path):
    world = prepared()
    project = authorize(world)
    work(world, 30)
    assert world.research.projects[project.id].completed_units == 2
    assert not world.knowledge.technologies
    assert world.economy.stocks['stock:ferroalto'].goods['tools'] == 18
    assert world.economy.accounts['treasury:escarlia'].balance == 19991  #10gross -1tax
    save_world(world, tmp_path / 'science.mws')
    resumed = load_world(tmp_path / 'science.mws')
    for value in (world, resumed):
        work(value, 60)
        work(value, 90)
        assert value.research.projects[project.id].stage == 'completed'
        assert value.knowledge.knows(EntityRef('polity', 'escarlia'), 'metallurgy')
        assert not value.knowledge.knows(EntityRef('polity', 'auren'), 'metallurgy')
        assert value.economy.facilities['works:minas-de-ferroalto'].recipe_id == 'ironworking'
        assert value.economy.stocks['stock:ferroalto'].goods['tools'] == 14
        assert sum(a.balance for a in value.economy.accounts.values()) == 76000
    assert world_snapshot(world) == world_snapshot(resumed)
    before = world_snapshot(world)
    work(world, 90)
    assert world_snapshot(world) == before


@pytest.mark.parametrize('reason', ['materials', 'funds', 'absent', 'unskilled', 'authority'])
def test_research_cannot_progress_without_its_actual_requirements(reason):
    world = prepared()
    project = authorize(world)
    if reason == 'materials':
        stock = world.economy.stocks['stock:ferroalto']
        world.economy.stocks[stock.id] = stock.model_copy(update={'goods': {**stock.goods, 'tools': 0}})
    elif reason == 'funds':
        account = world.economy.accounts['treasury:escarlia']
        world.economy.accounts[account.id] = account.model_copy(update={'balance': 0})
    elif reason in {'absent', 'unskilled'}:
        person = world.society.characters['character:011']
        change = {'location_id': 'pedraclara'} if reason == 'absent' else {'skills': person.skills.model_copy(update={'craftsmanship': 0})}
        world.society.characters[person.id] = person.model_copy(update=change)
    else:
        world.authority.offices = {k: o for k,o in world.authority.offices.items() if o.institution_ref.id != 'escarlia'}
    money = dict(world.economy.accounts)
    goods = dict(world.economy.stocks['stock:ferroalto'].goods)
    work(world, 30)
    assert world.research.projects[project.id].completed_units == 0
    assert world.research.projects[project.id].stage == 'blocked'
    assert not world.knowledge.technologies
    assert world.economy.accounts == money
    assert world.economy.stocks['stock:ferroalto'].goods == goods


@pytest.mark.parametrize('change', ['technology', 'owner', 'stage'])
def test_saved_research_and_knowledge_must_match_their_own_receipts(change):
    world = prepared()
    project = authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    if change == 'stage':
        # A completed experiment cannot be relabeled as superseded; use a
        # partial experiment to expose the missing stage-receipt validation.
        world = prepared()
        project = authorize(world)
        work(world, 30)
        world.research.projects[project.id] = world.research.projects[project.id].model_copy(update={'stage': 'blocked'})
    else:
        knowledge = next(iter(world.knowledge.technologies.values()))
        update = {'technology_id': 'irrigation'} if change == 'technology' else {'owner_ref': EntityRef('polity', 'auren')}
        world.knowledge.technologies[knowledge.id] = knowledge.model_copy(update=update)
    with pytest.raises(ValueError, match='receipt|provenance'):
        world_snapshot(world)


def apply_metallurgy(world):
    from src.sim.medieval.expansion import start_expansion
    event = record_event(world, 'adaptation_decided', 'Adaptar fornos.', fact_kind=FactKind.DECISION,
        decision={'action': 'expand', 'actor_ref': EntityRef('polity', 'escarlia').to_dict(),
                  'facility_id': 'works:minas-de-ferroalto', 'blueprint_id': 'efficient-furnaces'})
    return start_expansion(world, 'works:minas-de-ferroalto', 'efficient-furnaces', decision_event_id=event.id)


def test_discovery_requires_material_adaptation_before_better_production():
    from src.sim.medieval.expansion import progress_expansions
    from src.sim.medieval.economy import monthly_workforce, produce_monthly
    world = prepared()
    with pytest.raises(ValueError):
        apply_metallurgy(world)
    authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    project = apply_metallurgy(world)
    facility_id = 'works:minas-de-ferroalto'
    world.clock = WorldClock(120)
    progress_expansions(world, monthly_workforce(world))
    assert world.economy.facilities[facility_id].recipe_id == 'ironworking'
    world.clock = WorldClock(150)
    progress_expansions(world, monthly_workforce(world))
    assert world.economy.facilities[facility_id].recipe_id == 'efficient_ironworking'
    assert world.economy.facilities[facility_id].max_batches == 60
    before = world.economy.stocks['stock:ferroalto'].goods['iron']
    produce_monthly(world)
    assert world.economy.stocks['stock:ferroalto'].goods['iron'] - before == 420
    assert world.economy.expansions[project.id].stage == 'completed'


def teach(world, teacher, student, technology_id):
    from src.sim.medieval.teaching import teach_technology
    terms = {'technology_id': technology_id, 'teacher_ref': teacher.to_dict(), 'student_ref': student.to_dict()}
    offer = record_event(world, 'teaching_offered', 'Compartilhar técnica.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action': 'teach', 'actor_ref': teacher.to_dict()})
    accept = record_event(world, 'teaching_accepted', 'Receber instruções.', fact_kind=FactKind.DECISION,
        decision={**terms, 'action': 'learn', 'actor_ref': student.to_dict()})
    return teach_technology(world, offer.id, accept.id)


def test_teaching_transmits_only_owned_knowledge_not_material_capability():
    world = prepared()
    a, b = EntityRef('polity', 'escarlia'), EntityRef('polity', 'auren')
    with pytest.raises(ValueError):
        teach(world, a, b, 'metallurgy')
    authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    holdings = world.economy.to_dict()
    teach(world, a, b, 'metallurgy')
    assert world.knowledge.knows(b, 'metallurgy')
    assert world.economy.to_dict() == holdings
    with pytest.raises(ValueError):
        teach(world, a, b, 'metallurgy')


def test_catalog_prerequisites_are_enforced_and_cycles_are_rejected():
    world = prepared()
    tech = world.research.technologies['metallurgy']
    world.research.technologies[tech.id] = tech.model_copy(update={'prerequisites': ('irrigation',)})
    with pytest.raises(ValueError, match='prerequisites'):
        authorize(world)
    other = world.research.technologies['irrigation']
    world.research.technologies[other.id] = other.model_copy(update={'prerequisites': ('metallurgy',)})
    with pytest.raises(ValueError, match='acyclic'):
        world.research.validate(world)


async def test_monthly_research_reserves_named_specialist_and_rolls_back_on_save_failure(tmp_path, monkeypatch):
    from src.sim.medieval.engine import MedievalSimulator
    world = prepared()
    project = authorize(world)
    before = world_snapshot(world)
    def fail(*args):
        raise OSError('save unavailable')
    monkeypatch.setattr('src.sim.medieval.engine.save_world', fail)
    with pytest.raises(OSError):
        await MedievalSimulator(world, save_path=tmp_path/'fail.mws').step()
    assert world_snapshot(world) == before
    await MedievalSimulator(world).step()
    assert world.research.projects[project.id].completed_units == 2
    payroll = world.economy.payrolls[project.id]
    group_id = world.society.characters[project.researcher_id].population_group_id
    assert payroll.workers_by_group[group_id] >= 1
    assert sum(payroll.workers_by_group.values()) == 5


async def test_natural_monthly_policy_starts_feasible_projects_without_daily_ai():
    from src.sim.medieval.engine import MedievalSimulator
    world = create_medieval_world(73)
    await MedievalSimulator(world).step()
    assert {p.technology_id for p in world.research.projects.values()} == {'irrigation', 'metallurgy'}
    assert all(p.completed_units == 0 for p in world.research.projects.values())
    contracts = len([e for e in world.events if e.event_type == 'research_started'])
    await MedievalSimulator(world).step()
    assert len([e for e in world.events if e.event_type == 'research_started']) == contracts


def test_remaining_research_demand_is_included_once_in_reserved_materials():
    from src.sim.medieval.demand import reserve_quantity
    from src.sim.medieval.research_policy import review_research
    world = prepared()
    authorize(world)
    review_research(world)
    assert reserve_quantity(world, 'stock:ferroalto', 'tools') == 6
    assert any(o.stock_id == 'stock:ferroalto' and o.resource_id == 'tools' for o in world.strategy.objectives.values())
    work(world, 30)
    assert reserve_quantity(world, 'stock:ferroalto', 'tools') == 4


def test_learning_from_teacher_supersedes_an_active_experiment_without_fake_work():
    # Two institutions can learn the same technique independently; receiving it stops redundant work.
    world = prepared()
    authorize(world)
    for day in (30, 60, 90):
        work(world, day)
    # Prepared ownership transfer: the former sponsor retains knowledge, not the site.
    student = EntityRef('polity', 'auren')
    stock = world.economy.stocks['stock:ferroalto']
    world.economy.stocks[stock.id] = stock.model_copy(update={'owner_ref': student})
    site = world.map.infrastructure_sites['minas-de-ferroalto']
    world.map.infrastructure_sites[site.id] = type(site).from_dict({**site.to_dict(), 'owner_ref': student.to_dict()})
    facility = world.economy.facilities['works:minas-de-ferroalto']
    world.economy.facilities[facility.id] = facility.model_copy(update={'payroll_account_id': 'treasury:auren'})
    project = authorize(world, actor_id='auren')
    teach(world, EntityRef('polity', 'escarlia'), student, 'metallurgy')
    money = dict(world.economy.accounts)
    work(world, 120)
    assert world.research.projects[project.id].stage == 'superseded'
    assert world.research.projects[project.id].completed_units == 0
    assert world.economy.accounts == money
