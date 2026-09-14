"""Monthly research with independent consent, real specialists and material costs."""

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import ResearchProject, TechnicalKnowledge
from src.classes.governance.authority import can_actor_act_for
from .events import record_event
from .economy import _apply_stock, _causes, _delta
from .labor import settle_work


def research_blocker(world, technology, site_id, stock_id, account_id, researcher_id, owner):
    stock = world.economy.stocks.get(stock_id)
    account = world.economy.accounts.get(account_id)
    site = world.map.infrastructure_sites.get(site_id)
    lead = world.society.characters.get(researcher_id)
    if any(not can_actor_act_for(world, owner, owner, scope) for scope in ('research', 'trade', 'supply')):
        return 'authority'
    if (stock is None or account is None or stock.owner_ref != owner or account.owner_ref != owner or
            site is None or site.owner_ref != owner or not site.enabled or site.integrity <= 0
            or technology.capability_id not in site.capability_ids
            or world.society.settlements[stock.location_id].region_id not in site.region_ids):
        return 'site'
    if any(not world.knowledge.knows(owner, tech) for tech in technology.prerequisites):
        return 'prerequisites'
    if (lead is None or lead.death_day is not None or lead.location_id != stock.location_id
            or lead.population_group_id not in world.society.population
            or world.society.population[lead.population_group_id].settlement_id != stock.location_id):
        return 'researcher_absent'
    if getattr(lead.skills, technology.skill) < technology.min_skill:
        return 'qualification'
    if (any(a.character_id == lead.id for a in world.activities.values())
            or any(a.specialist_id == lead.id and a.stage == 'training'
                   for a in world.research.apprenticeships.values())):
        return 'researcher_busy'
    return None


def start_research(world, technology_id, site_id, stock_id, account_id, researcher_id, *, sponsor_decision_id, researcher_decision_id):
    world.research.validate(world)
    technology = world.research.technologies.get(technology_id)
    stock = world.economy.stocks.get(stock_id)
    if technology is None or stock is None:
        raise ValueError('unknown technology or research stock')
    owner = stock.owner_ref
    terms = dict(technology_id=technology_id, site_id=site_id, stock_id=stock_id, account_id=account_id, researcher_id=researcher_id)
    events = {e.id: e for e in world.events}
    for eid, action, actor in ((sponsor_decision_id, 'research', owner),
            (researcher_decision_id, 'research_work', EntityRef('character', researcher_id))):
        decision = events.get(eid)
        if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != world.clock.absolute_day
                or decision.decision != {**terms, 'action': action, 'actor_ref': actor.to_dict()}
                or any(eid in (p.sponsor_decision_id, p.researcher_decision_id) for p in world.research.projects.values())):
            raise ValueError('research requires two new matching contract decisions')
    blocker = research_blocker(world, technology, site_id, stock_id, account_id, researcher_id, owner)
    if blocker or world.knowledge.knows(owner, technology_id) or any(
            p.stage not in {'completed', 'superseded'} and (p.owner_ref == owner or p.researcher_id == researcher_id) for p in world.research.projects.values()):
        raise ValueError(f'research unavailable: {blocker or "known or busy"}')
    project_id = f'research:{sponsor_decision_id}'
    event = record_event(world, 'research_started', f'Pesquisa autorizada: {technology.name}; ainda sem descoberta.',
        fact_kind=FactKind.STATE_TRANSITION, deltas=(_delta('research', project_id, 'stage', None, 'waiting'),),
        cause_ids=(sponsor_decision_id, researcher_decision_id))
    project = ResearchProject(id=project_id, owner_ref=owner, **terms,
        sponsor_decision_id=sponsor_decision_id, researcher_decision_id=researcher_decision_id,
        started_day=world.clock.absolute_day, last_event_id=event.id)
    world.research.projects[project.id] = project
    return project


def learn_technology(world, owner, technology_id, channel, causes):
    if world.knowledge.knows(owner, technology_id):
        return
    key = f'technology:{owner.kind}:{owner.id}:{technology_id}'
    technology = world.research.technologies[technology_id]
    event = record_event(world, {'research': 'technology_discovered', 'teaching': 'technology_taught',
                                 'apprenticeship': 'technology_apprenticed',
                                 'copied': 'technique_copy_completed'}[channel],
        f'{technology.name}: conhecimento adquirido; instalações e equipamentos não foram criados.',
        fact_kind=FactKind.STATE_TRANSITION, cause_ids=causes,
        deltas=(_delta('technical_knowledge', key, 'technology_id', None, technology_id),))
    world.knowledge.technologies[key] = TechnicalKnowledge(id=key, owner_ref=owner,
        technology_id=technology_id, channel=channel, learned_day=world.clock.absolute_day, event_id=event.id)


def progress_research(world, available):
    world.research.validate(world)
    day = world.clock.absolute_day
    if day % 30:
        return
    for project in sorted(world.research.projects.values(), key=lambda p: p.id):
        if project.stage in {'completed', 'superseded'} or project.started_day >= day or project.last_work_day == day:
            continue
        tech = world.research.technologies[project.technology_id]
        blocker = research_blocker(world, tech, project.site_id, project.stock_id, project.account_id,
                                   project.researcher_id, project.owner_ref)
        known = world.knowledge.knows(project.owner_ref, tech.id)
        if known:
            blocker = 'already_known'
        stock = world.economy.stocks[project.stock_id]
        account = world.economy.accounts[project.account_id]
        lead = world.society.characters[project.researcher_id]
        units = 0
        if blocker is None:
            assistants = sum(available[g.id] for g in world.society.population.values()
                             if g.settlement_id == stock.location_id and g.occupation == tech.assistant_occupation)
            if world.society.population[lead.population_group_id].occupation == tech.assistant_occupation:
                assistants -= 1
            limits = {'schedule': tech.monthly_units, 'remaining': tech.required_units - project.completed_units,
                      'skill': max(1, getattr(lead.skills, tech.skill) // 20),
                      'labor': max(0, assistants) // tech.assistants_per_unit,
                      'payroll_funds': max(0, account.balance // tech.wage_per_worker - 1) // tech.assistants_per_unit,
                      **{f'input:{rid}': stock.goods.get(rid, 0) // amount for rid, amount in tech.inputs.items()}}
            if available.get(lead.population_group_id, 0) < 1:
                limits['labor'] = 0
            units = min(limits.values())
            blocker = next((key for key in sorted(limits) if limits[key] == 0), None)
        done = project.completed_units + units
        stage = 'superseded' if known else 'completed' if done == tech.required_units else 'researching' if units else 'blocked'
        goods = dict(stock.goods)
        for rid, amount in tech.inputs.items():
            if units:
                goods[rid] -= amount * units
        description = 'encerrada por conhecimento já adquirido' if known else 'concluída' if stage == 'completed' else 'em andamento' if units else 'impedida'
        event = _apply_stock(world, stock, goods, 'research_progressed', f'{tech.name}: pesquisa {done}/{tech.required_units}, {description}.',
            extra_deltas=(_delta('research', project.id, 'completed_units', project.completed_units, done),
                          _delta('research', project.id, 'stage', project.stage, stage)),
            cause_ids=_causes(project.last_event_id, account.last_event_id, world.map.infrastructure_sites[project.site_id].last_event_id))
        if units:
            settle_work(world, work_id=project.id, account_id=account.id, stock_id=stock.id,
                occupation=tech.assistant_occupation, worker_count=1 + units * tech.assistants_per_unit,
                wage=tech.wage_per_worker, available=available, production_event_id=event.id,
                required_workers={lead.population_group_id: 1})
        world.research.projects[project.id] = project.model_copy(update={
            'completed_units': done, 'last_work_day': day, 'stage': stage, 'blocker': blocker, 'last_event_id': event.id})
        if stage == 'completed':
            learn_technology(world, project.owner_ref, tech.id, 'research',
                             _causes(event.id, world.economy.payrolls[project.id].last_event_id))
