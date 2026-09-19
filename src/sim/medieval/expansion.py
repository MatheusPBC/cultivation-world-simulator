"""Owners finance construction from real stock and paid local labor."""

from src.classes.economy.expansion import ExpansionProject
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority, can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue
from .economy import _apply_stock, _causes, _delta
from .events import record_event
from .labor import settle_work
from .industrial_lines import line_id, line_exists_or_planned, commission_line


class ExpansionOption(SocietyValue):
    """Transient owner-bounded installation choice."""
    id: str
    actor_ref: EntityRef
    facility_id: str
    blueprint_id: str
    facility_event_id: str | None = None
    site_event_id: str | None = None

    def decision(self):
        return {"action": "expand", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def expansion_options(world, actor):
    """Enumerate expansions that are materially startable now.

    The option names only the facility and authored blueprint.  Inputs, wages,
    authority and technical knowledge are recomposed here and once more by
    ``start_expansion`` immediately before the project is persisted.
    """
    if not isinstance(actor, EntityRef):
        return ()
    economy = world.economy
    options = []
    for facility in sorted(economy.facilities.values(), key=lambda item: item.id):
        stock = economy.stocks[facility.stock_id]
        if stock.owner_ref != actor or not facility.max_batches:
            continue
        site = world.map.infrastructure_sites.get(facility.site_id)
        account = economy.accounts.get(facility.payroll_account_id)
        if (site is None or account is None or account.owner_ref != actor or not site.enabled
                or site.integrity <= 0
                or any(not can_actor_act_for(world, actor, actor, scope) for scope in ("trade", "supply"))
                or facility.last_batches != facility.max_batches):
            continue
        recipe = economy.recipes[facility.recipe_id]
        if all(stock.goods.get(rid, 0) >= amount * facility.max_batches * 2
               for rid, amount in recipe.outputs.items()):
            continue
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda item: item.id):
            target_recipe = blueprint.additional_recipe_id or blueprint.to_recipe_id
            if (line_exists_or_planned(economy, facility, blueprint)
                    or blueprint.required_technology_id and not world.knowledge.knows(actor, blueprint.required_technology_id)
                    or blueprint.from_recipe_id and facility.recipe_id != blueprint.from_recipe_id
                    or target_recipe and economy.recipes[target_recipe].capability_id not in site.capability_ids
                    or any(capability not in site.capability_ids
                           for capability in blueprint.required_site_capabilities)):
                continue
            people = sum(group.count for group in world.society.population.values()
                         if group.settlement_id == stock.location_id and group.occupation == recipe.occupation)
            artisans = sum(group.count for group in world.society.population.values()
                           if group.settlement_id == stock.location_id and group.occupation == "artisan")
            if people < (facility.max_batches + blueprint.capacity_gain) * recipe.workers or artisans < blueprint.workers_per_unit:
                continue
            prices = economy.markets[stock.location_id].prices
            material_budget = sum(max(0, amount * blueprint.required_units - stock.goods.get(resource, 0))
                                  * prices[resource] for resource, amount in blueprint.inputs.items())
            wage_budget = blueprint.required_units * blueprint.workers_per_unit * blueprint.wage_per_worker
            operating_buffer = facility.max_batches * recipe.workers * facility.wage_per_worker * 2
            if account.balance < material_budget + wage_budget + operating_buffer:
                continue
            option_id = f"expansion:{actor.kind}:{actor.id}:{facility.id}:{blueprint.id}:{facility.last_event_id}:{site.last_event_id}"
            options.append(ExpansionOption(id=option_id, actor_ref=actor,
                                            facility_id=facility.id, blueprint_id=blueprint.id,
                                            facility_event_id=facility.last_event_id,
                                            site_event_id=site.last_event_id))
    return tuple(options)


def expansion_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def execute(world, actor, option_id, decision_event_id):
        option = next((item for item in expansion_options(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("expansion option is stale or unknown")
        # The institutional turn carries only the transient affordance ID.
        # The owner recomposes the private construction terms into a dated
        # authorization receipt before the material project is created.
        authorization = record_event(
            world, "expansion_authorized", "A instituição autorizou a ampliação escolhida.",
            fact_kind=FactKind.DECISION,
            decision={"action": "expand", "actor_ref": actor.to_dict(),
                      "facility_id": option.facility_id, "blueprint_id": option.blueprint_id},
            cause_ids=(decision_event_id,))
        start_expansion(world, option.facility_id, option.blueprint_id,
                        decision_event_id=authorization.id)

    return (DiscretionaryAdapter(
        name="expansion", family="production", options_fn=expansion_options,
        label_fn=lambda option: f"Investir na instalação {option.facility_id} com {option.blueprint_id}.",
        causes_fn=lambda world, option: _causes(option.facility_event_id, option.site_event_id),
        execute_fn=execute),)


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
    site = world.map.infrastructure_sites[facility.site_id]
    if any(capability not in site.capability_ids for capability in blueprint.required_site_capabilities):
        raise ValueError('application requires the authored site capabilities')
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
        missing_capability = next((capability for capability in blueprint.required_site_capabilities
                                   if capability not in site.capability_ids), None)
        if missing_capability is not None:
            limits[f'site_capability:{missing_capability}'] = 0
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
                      f"falta capacidade física: {blocker.split(':', 1)[1]}" if blocker.startswith('site_capability:') else
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
