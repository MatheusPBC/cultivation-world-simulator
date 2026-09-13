"""Owners finance construction from real stock and paid local labor."""

from src.classes.economy.expansion import ExpansionProject
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority, can_actor_act_for
from .economy import _apply_stock, _causes, _delta
from .events import record_event
from .labor import settle_work
from .industrial_lines import line_id, line_exists_or_planned, commission_line


def review_expansions(world):
    from .investment import review_investment
    review_investment(world)


def start_expansion(world, facility_id, blueprint_id, *, decision_event_id):
    economy = world.economy
    economy.validate(world)
    facility = economy.facilities.get(facility_id)
    if facility is None or blueprint_id not in economy.expansion_blueprints:
        raise ValueError('unknown expansion target or blueprint')
    stock = economy.stocks[facility.stock_id]
    blueprint = economy.expansion_blueprints[blueprint_id]
    if line_exists_or_planned(economy, facility, blueprint):
        raise ValueError('production line already exists or is planned')
    if blueprint.required_technology_id and not world.knowledge.knows(stock.owner_ref, blueprint.required_technology_id):
        raise ValueError('application requires owned technical knowledge')
    if blueprint.from_recipe_id and facility.recipe_id != blueprint.from_recipe_id:
        raise ValueError('application requires the matching original recipe')
    target_recipe = blueprint.additional_recipe_id or blueprint.to_recipe_id
    if target_recipe and economy.recipes[target_recipe].capability_id not in world.map.infrastructure_sites[facility.site_id].capability_ids:
        raise ValueError('application requires a capable site')
    decision = next((e for e in world.events if e.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != world.clock.absolute_day
            or decision.decision != {'action': 'expand', 'actor_ref': stock.owner_ref.to_dict(),
                                     'facility_id': facility_id, 'blueprint_id': blueprint_id}
            or any(p.decision_event_id == decision_event_id or (p.facility_id == facility_id and p.stage != 'completed')
                   for p in economy.expansions.values())):
        raise ValueError('expansion needs a new matching owner decision and no active project')
    require_authority(world, stock.owner_ref, 'trade')
    require_authority(world, stock.owner_ref, 'supply')
    project_id = f'expansion:{decision_event_id}'
    event = record_event(world, 'expansion_started', 'Projeto de ampliação autorizado; capacidade ainda inalterada.',
        fact_kind=FactKind.STATE_TRANSITION, cause_ids=_causes(decision_event_id,
            *(k.event_id for k in world.knowledge.technologies.values()
              if k.owner_ref == stock.owner_ref and k.technology_id == blueprint.required_technology_id)),
        deltas=(_delta('expansion', project_id, 'stage', None, 'waiting'),))
    project = ExpansionProject(id=project_id, facility_id=facility_id, blueprint_id=blueprint_id,
        owner_ref=stock.owner_ref, decision_event_id=decision_event_id,
        started_day=world.clock.absolute_day, last_event_id=event.id)
    economy.expansions[project.id] = project
    return project


def progress_expansions(world, available):
    economy = world.economy
    economy.validate(world)
    day = world.clock.absolute_day
    if day % 30:
        return
    for project in sorted(economy.expansions.values(), key=lambda p: p.id):
        if project.stage == 'completed' or project.started_day >= day or project.last_work_day == day:
            continue
        facility = economy.facilities[project.facility_id]
        blueprint = economy.expansion_blueprints[project.blueprint_id]
        stock = economy.stocks[facility.stock_id]
        site = world.map.infrastructure_sites[facility.site_id]
        limits = {'schedule': blueprint.monthly_units,
                  'remaining': blueprint.required_units - project.completed_units,
                  'payroll_funds': economy.accounts[facility.payroll_account_id].balance // (blueprint.workers_per_unit * blueprint.wage_per_worker),
                  'labor': sum(available[g.id] for g in world.society.population.values()
                               if g.settlement_id == stock.location_id and g.occupation == 'artisan') // blueprint.workers_per_unit}
        limits.update({f'input:{r}': stock.goods.get(r, 0) // amount for r, amount in blueprint.inputs.items()})
        if stock.owner_ref != project.owner_ref or any(not can_actor_act_for(world, project.owner_ref, project.owner_ref, scope)
                                                       for scope in ('trade', 'supply')):
            limits['authority'] = 0
        if not site.enabled or site.integrity <= 0:
            limits['site_unavailable'] = 0
        if blueprint.required_technology_id and not world.knowledge.knows(project.owner_ref, blueprint.required_technology_id):
            limits['knowledge'] = 0
        if blueprint.from_recipe_id and facility.recipe_id != blueprint.from_recipe_id:
            limits['recipe_changed'] = 0
        if line_exists_or_planned(economy, facility, blueprint, exclude_project=project.id):
            limits['line_exists'] = 0
        units = min(limits.values())
        done = project.completed_units + units
        stage = 'completed' if done == blueprint.required_units else 'building' if units else 'blocked'
        blocker = next((name for name in sorted(limits) if limits[name] == 0), None)
        goods = {**stock.goods}
        for rid, amount in blueprint.inputs.items():
            if units:
                goods[rid] -= amount * units
        changes = [_delta('expansion', project.id, 'completed_units', project.completed_units, done),
                   _delta('expansion', project.id, 'stage', project.stage, stage)]
        if stage == 'completed':
            if blueprint.additional_recipe_id:
                changes.extend((_delta('production', line_id(facility, blueprint), 'recipe_id', None, blueprint.additional_recipe_id),
                                _delta('production', line_id(facility, blueprint), 'max_batches', 0, blueprint.new_capacity)))
            else:
                changes.append(_delta('production', facility.id, 'max_batches', facility.max_batches,
                                      facility.max_batches + blueprint.capacity_gain))
            if blueprint.to_recipe_id:
                changes.append(_delta('production', facility.id, 'recipe_id', facility.recipe_id, blueprint.to_recipe_id))
        description = {'completed': 'concluída', 'building': 'em construção', 'blocked': 'impedida'}[stage]
        if blocker:
            reason = (f"faltam materiais: {economy.resources[blocker[6:]].name}" if blocker.startswith('input:') else
                      {'authority': 'sem autoridade vigente', 'payroll_funds': 'sem saldo para salários',
                       'labor': 'sem artesãos disponíveis', 'site_unavailable': 'instalação indisponível',
                       'knowledge': 'conhecimento indisponível', 'recipe_changed': 'instalação já alterada',
                       'line_exists': 'linha produtiva já existente ou planejada'}[blocker])
            description += f'; {reason}'
        event = _apply_stock(world, stock, goods, 'expansion_progressed',
            f'{site.name}: ampliação {done}/{blueprint.required_units}; {description}.',
            extra_deltas=changes, cause_ids=_causes(project.last_event_id, facility.last_event_id, site.last_event_id,
                                                  economy.accounts[facility.payroll_account_id].last_event_id))
        if units:
            settle_work(world, work_id=project.id, account_id=facility.payroll_account_id,
                stock_id=facility.stock_id, occupation='artisan', worker_count=units * blueprint.workers_per_unit,
                wage=blueprint.wage_per_worker, available=available, production_event_id=event.id)
        economy.expansions[project.id] = project.model_copy(update={'completed_units': done, 'stage': stage,
            'blocker': blocker, 'last_work_day': day, 'last_event_id': event.id})
        if stage == 'completed':
            if blueprint.additional_recipe_id:
                commission_line(economy, facility, blueprint, event.id)
            else:
                economy.facilities[facility.id] = facility.model_copy(update={
                    'max_batches': facility.max_batches + blueprint.capacity_gain, 'last_event_id': event.id,
                    'recipe_id': blueprint.to_recipe_id or facility.recipe_id})
