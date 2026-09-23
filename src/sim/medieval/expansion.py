"""Owners finance construction from real stock and paid local labor."""

import json

from src.classes.economy.expansion import ExpansionProject, foundation_line_id
from src.classes.event import FactKind
from src.classes.governance.authority import require_authority, can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.economy.models import ProductionFacility
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
                or any(not can_actor_act_for(world, actor, actor, scope) for scope in ("trade", "supply"))):
            continue
        recipe = economy.recipes[facility.recipe_id]
        output_store_full = all(stock.goods.get(rid, 0) >= amount * facility.max_batches * 2
                                for rid, amount in recipe.outputs.items())
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda item: item.id):
            # A foundation opens a site's first line and a construction raises
            # the site itself; neither has an anchor to modify, so both belong
            # to their own owners, never to this one.
            if blueprint.foundation_recipe_id or blueprint.grants_capability_id:
                continue
            storage_pressure = (blueprint.stock_capacity_gain > 0
                                and facility.last_batches < facility.max_batches
                                and "storage" in facility.last_limitations)
            production_pressure = blueprint.stock_capacity_gain == 0 and facility.last_batches == facility.max_batches
            if not (storage_pressure or production_pressure):
                continue
            if output_store_full and not storage_pressure:
                continue
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
            builders = sum(group.count for group in world.society.population.values()
                           if group.settlement_id == stock.location_id
                           and group.occupation == blueprint.worker_occupation)
            required_batches = (facility.max_batches + blueprint.capacity_gain
                                if blueprint.stock_capacity_gain == 0 else facility.last_batches)
            if people < required_batches * recipe.workers or builders < blueprint.workers_per_unit:
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


class FoundationOption(SocietyValue):
    """Transient choice to open a site's first line for an authored recipe."""
    id: str
    actor_ref: EntityRef
    site_id: str
    blueprint_id: str
    stock_id: str
    account_id: str
    site_event_id: str | None = None
    stock_event_id: str | None = None

    def decision(self):
        return {"action": "found_line", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _foundation_terms(option):
    return {"action": "found_line", "actor_ref": option.actor_ref.to_dict(),
            "site_id": option.site_id, "stock_id": option.stock_id,
            "account_id": option.account_id, "blueprint_id": option.blueprint_id}


def _local_holdings(world, actor, settlement_id):
    economy = world.economy
    stock = next((item for item in sorted(economy.stocks.values(), key=lambda value: value.id)
                  if item.owner_ref == actor and item.location_id == settlement_id), None)
    account = next((item for item in sorted(economy.accounts.values(), key=lambda value: value.id)
                    if item.owner_ref == actor), None)
    return stock, account


def _site_settlement(world, site):
    return next((item for item in sorted(world.society.settlements.values(), key=lambda value: value.id)
                 if item.region_id in site.region_ids), None)


def foundation_blocker(world, actor, site, blueprint, stock, account):
    """Every authored and material gate, recomposed identically by the owner."""
    economy = world.economy
    recipe = economy.recipes.get(blueprint.foundation_recipe_id)
    if recipe is None:
        return "unknown_recipe"
    if site.owner_ref != actor or not site.enabled or site.integrity <= 0:
        return "site"
    # Physical capability is authored on the Map and is never created here.
    if recipe.capability_id not in site.capability_ids or any(
            capability not in site.capability_ids for capability in blueprint.required_site_capabilities):
        return "site_capability"
    if blueprint.required_technology_id and not world.knowledge.knows(actor, blueprint.required_technology_id):
        return "knowledge"
    if any(not can_actor_act_for(world, actor, actor, scope) for scope in ("trade", "supply")):
        return "authority"
    if foundation_line_id(site.id, recipe.id) in economy.facilities or any(
            item.site_id == site.id and item.recipe_id == recipe.id for item in economy.facilities.values()):
        return "line_exists"
    if any(project.stage != "completed"
           and economy.expansion_blueprints[project.blueprint_id].foundation_recipe_id == recipe.id
           and project.site_id == site.id for project in economy.expansions.values()):
        return "line_planned"
    if stock is None or account is None:
        return "holdings"
    settlement = _site_settlement(world, site)
    if settlement is None or stock.location_id != settlement.id:
        return "holdings"
    builders = sum(group.count for group in world.society.population.values()
                   if group.settlement_id == settlement.id
                   and group.occupation == blueprint.worker_occupation)
    operators = sum(group.count for group in world.society.population.values()
                    if group.settlement_id == settlement.id and group.occupation == recipe.occupation)
    if builders < blueprint.workers_per_unit or operators < recipe.workers:
        return "labor"
    prices = economy.markets[stock.location_id].prices
    material_budget = sum(max(0, amount * blueprint.required_units - stock.goods.get(resource, 0))
                          * prices[resource] for resource, amount in blueprint.inputs.items())
    wage_budget = blueprint.required_units * blueprint.workers_per_unit * blueprint.wage_per_worker
    if account.balance < material_budget + wage_budget:
        return "funds"
    return None


def foundation_options(world, actor):
    """Enumerate first lines an owner could actually build on its own sites.

    The option names only the site and the authored blueprint. Stock, account,
    builders, materials and knowledge are recomposed here and once more by
    ``start_foundation`` immediately before the project is persisted.
    """
    if not isinstance(actor, EntityRef):
        return ()
    economy = world.economy
    options = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if site.owner_ref != actor:
            continue
        settlement = _site_settlement(world, site)
        if settlement is None:
            continue
        stock, account = _local_holdings(world, actor, settlement.id)
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda item: item.id):
            if not blueprint.foundation_recipe_id:
                continue
            if foundation_blocker(world, actor, site, blueprint, stock, account) is not None:
                continue
            options.append(FoundationOption(
                id=(f"foundation:{actor.kind}:{actor.id}:{site.id}:{blueprint.id}:"
                    f"{site.last_event_id}:{stock.last_event_ids.get(next(iter(blueprint.inputs)))}"),
                actor_ref=actor, site_id=site.id, blueprint_id=blueprint.id,
                stock_id=stock.id, account_id=account.id, site_event_id=site.last_event_id,
                stock_event_id=stock.last_event_ids.get(next(iter(blueprint.inputs)))))
    return tuple(options)


def start_foundation(world, option, *, decision_event_id):
    """Owner-side revalidation before any dated construction exists."""
    economy = world.economy
    economy.validate(world)
    site = world.map.infrastructure_sites.get(option.site_id)
    blueprint = economy.expansion_blueprints.get(option.blueprint_id)
    stock = economy.stocks.get(option.stock_id)
    account = economy.accounts.get(option.account_id)
    if site is None or blueprint is None or not blueprint.foundation_recipe_id:
        raise ValueError('unknown foundation site or blueprint')
    if stock is None or account is None or stock.owner_ref != option.actor_ref or account.owner_ref != option.actor_ref:
        raise ValueError('foundation requires the owner own local stock and account')
    blocker = foundation_blocker(world, option.actor_ref, site, blueprint, stock, account)
    if blocker is not None:
        raise ValueError(f'foundation unavailable: {blocker}')
    decision = next((item for item in world.events if item.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision != _foundation_terms(option)
            or any(project.decision_event_id == decision_event_id for project in economy.expansions.values())):
        raise ValueError('foundation needs a new matching owner decision')
    require_authority(world, option.actor_ref, 'trade')
    require_authority(world, option.actor_ref, 'supply')
    project_id = f'expansion:{decision_event_id}'
    event = record_event(
        world, 'line_foundation_started',
        f'{site.name}: fundação de linha autorizada; nenhuma produção existe ainda.',
        fact_kind=FactKind.STATE_TRANSITION,
        cause_ids=_causes(decision_event_id, site.last_event_id,
                          *(item.event_id for item in world.knowledge.technologies.values()
                            if item.owner_ref == option.actor_ref
                            and item.technology_id == blueprint.required_technology_id)),
        deltas=(_delta('expansion', project_id, 'stage', None, 'waiting'),))
    project = ExpansionProject(id=project_id, facility_id=None, site_id=site.id, stock_id=stock.id,
                               account_id=account.id, blueprint_id=blueprint.id, owner_ref=option.actor_ref,
                               decision_event_id=decision_event_id,
                               started_day=world.clock.absolute_day, last_event_id=event.id)
    economy.expansions[project.id] = project
    return project


def foundation_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def execute(world, actor, option_id, decision_event_id):
        option = next((item for item in foundation_options(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("foundation option is stale or unknown")
        # The institutional turn carries only the transient affordance ID; the
        # owner recomposes site, stock and account into its own dated receipt.
        authorization = record_event(
            world, "line_foundation_authorized", "A instituição autorizou a fundação da linha escolhida.",
            fact_kind=FactKind.DECISION, decision=_foundation_terms(option),
            cause_ids=(decision_event_id,))
        start_foundation(world, option, decision_event_id=authorization.id)

    return (DiscretionaryAdapter(
        name="line_foundation", family="production", options_fn=foundation_options,
        label_fn=lambda option: f"Fundar a linha {option.blueprint_id} no sítio {option.site_id}.",
        causes_fn=lambda world, option: _causes(option.site_event_id, option.stock_event_id),
        execute_fn=execute),)


class SiteConstructionOption(SocietyValue):
    """Transient choice to raise an authored site kind in a settlement."""
    id: str
    actor_ref: EntityRef
    settlement_id: str
    new_site_id: str
    blueprint_id: str
    stock_id: str
    account_id: str
    stock_event_id: str | None = None


    def decision(self):
        return {"action": "construct_site", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _construction_terms(option):
    return {"action": "construct_site", "actor_ref": option.actor_ref.to_dict(),
            "settlement_id": option.settlement_id, "new_site_id": option.new_site_id,
            "stock_id": option.stock_id, "account_id": option.account_id,
            "blueprint_id": option.blueprint_id}


def constructed_site_id(settlement_id, blueprint):
    return f'site:{settlement_id}:{blueprint.site_kind}'


def construction_blocker(world, actor, settlement, blueprint, stock, account):
    """Authored and material gates, recomposed identically by the owner."""
    economy = world.economy
    if not blueprint.grants_capability_id:
        return "not_a_construction"
    if any(not can_actor_act_for(world, actor, actor, scope) for scope in ("trade", "supply")):
        return "authority"
    # A settlement is administered by one polity; only it may build there.
    if settlement.administrator_id != actor.id:
        return "administration"
    if settlement.occupier_id not in (None, actor.id):
        return "occupation"
    if blueprint.required_technology_id and not world.knowledge.knows(actor, blueprint.required_technology_id):
        return "knowledge"
    # The material ceiling: one site of this kind per settlement, and never a
    # second source of a capability the place already has.
    if constructed_site_id(settlement.id, blueprint) in world.map.infrastructure_sites:
        return "site_exists"
    if any(settlement.region_id in site.region_ids
           and (site.kind == blueprint.site_kind
                or blueprint.grants_capability_id in site.capability_ids)
           for site in world.map.infrastructure_sites.values()):
        return "capability_exists"
    if any(project.stage != "completed"
           and economy.expansion_blueprints[project.blueprint_id].grants_capability_id == blueprint.grants_capability_id
           and project.settlement_id == settlement.id for project in economy.expansions.values()):
        return "site_planned"
    if stock is None or account is None or stock.location_id != settlement.id:
        return "holdings"
    builders = sum(group.count for group in world.society.population.values()
                   if group.settlement_id == settlement.id
                   and group.occupation == blueprint.worker_occupation)
    if builders < blueprint.workers_per_unit:
        return "labor"
    prices = economy.markets[settlement.id].prices
    material_budget = sum(max(0, amount * blueprint.required_units - stock.goods.get(resource, 0))
                          * prices[resource] for resource, amount in blueprint.inputs.items())
    wage_budget = blueprint.required_units * blueprint.workers_per_unit * blueprint.wage_per_worker
    if account.balance < material_budget + wage_budget:
        return "funds"
    return None


def site_construction_options(world, actor):
    """Enumerate authored site kinds this administration could actually raise.

    The option names only the settlement and the authored blueprint. Stock,
    account, builders, materials and the ceiling are recomposed here and once
    more by ``start_site_construction`` before any project is persisted.
    """
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    economy = world.economy
    options = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        stock, account = _local_holdings(world, actor, settlement.id)
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda item: item.id):
            if not blueprint.grants_capability_id:
                continue
            if construction_blocker(world, actor, settlement, blueprint, stock, account) is not None:
                continue
            options.append(SiteConstructionOption(
                id=(f"site-construction:{actor.kind}:{actor.id}:{settlement.id}:{blueprint.id}:"
                    f"{stock.last_event_ids.get(next(iter(blueprint.inputs)))}"),
                actor_ref=actor, settlement_id=settlement.id,
                new_site_id=constructed_site_id(settlement.id, blueprint),
                blueprint_id=blueprint.id, stock_id=stock.id, account_id=account.id,
                stock_event_id=stock.last_event_ids.get(next(iter(blueprint.inputs)))))
    return tuple(options)


def start_site_construction(world, option, *, decision_event_id):
    """Owner-side revalidation before any dated construction exists."""
    economy = world.economy
    economy.validate(world)
    settlement = world.society.settlements.get(option.settlement_id)
    blueprint = economy.expansion_blueprints.get(option.blueprint_id)
    stock = economy.stocks.get(option.stock_id)
    account = economy.accounts.get(option.account_id)
    if settlement is None or blueprint is None or not blueprint.grants_capability_id:
        raise ValueError('unknown construction settlement or blueprint')
    if stock is None or account is None or stock.owner_ref != option.actor_ref or account.owner_ref != option.actor_ref:
        raise ValueError('construction requires the owner own local stock and account')
    blocker = construction_blocker(world, option.actor_ref, settlement, blueprint, stock, account)
    if blocker is not None:
        raise ValueError(f'construction unavailable: {blocker}')
    decision = next((item for item in world.events if item.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision != _construction_terms(option)
            or any(project.decision_event_id == decision_event_id for project in economy.expansions.values())):
        raise ValueError('construction needs a new matching owner decision')
    require_authority(world, option.actor_ref, 'trade')
    require_authority(world, option.actor_ref, 'supply')
    project_id = f'expansion:{decision_event_id}'
    event = record_event(
        world, 'site_construction_started',
        f'{settlement.name}: obra de {blueprint.name} autorizada; nenhuma capacidade existe ainda.',
        fact_kind=FactKind.STATE_TRANSITION,
        cause_ids=_causes(decision_event_id, account.last_event_id,
                          *(item.event_id for item in world.knowledge.technologies.values()
                            if item.owner_ref == option.actor_ref
                            and item.technology_id == blueprint.required_technology_id)),
        deltas=(_delta('expansion', project_id, 'stage', None, 'waiting'),))
    project = ExpansionProject(id=project_id, facility_id=None, site_id=None,
                               settlement_id=settlement.id, new_site_id=option.new_site_id,
                               stock_id=stock.id, account_id=account.id, blueprint_id=blueprint.id,
                               owner_ref=option.actor_ref, decision_event_id=decision_event_id,
                               started_day=world.clock.absolute_day, last_event_id=event.id)
    economy.expansions[project.id] = project
    return project


def site_construction_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter

    def execute(world, actor, option_id, decision_event_id):
        option = next((item for item in site_construction_options(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("site construction option is stale or unknown")
        authorization = record_event(
            world, "site_construction_authorized", "A instituição autorizou a obra escolhida.",
            fact_kind=FactKind.DECISION, decision=_construction_terms(option),
            cause_ids=(decision_event_id,))
        start_site_construction(world, option, decision_event_id=authorization.id)

    return (DiscretionaryAdapter(
        name="site_construction", family="production", options_fn=site_construction_options,
        label_fn=lambda option: f"Construir {option.blueprint_id} em {option.settlement_id}.",
        causes_fn=lambda world, option: _causes(option.stock_event_id),
        execute_fn=execute),)


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
    if blueprint.foundation_recipe_id or blueprint.grants_capability_id:
        raise ValueError('a foundation or construction blueprint is opened by its own owner, not as an expansion')
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
        blueprint = economy.expansion_blueprints[project.blueprint_id]
        founding = blueprint.foundation_recipe_id is not None
        constructing = blueprint.grants_capability_id is not None
        # A foundation or a construction has no anchor facility, so the project
        # itself supplies the material terms an anchor would have given: whose
        # stock feeds the works and whose account pays them. A construction has
        # no site at all yet -- that is precisely what it is building.
        facility = economy.facilities[project.facility_id] if not (founding or constructing) else None
        stock = economy.stocks[facility.stock_id if facility is not None else project.stock_id]
        site = (world.map.infrastructure_sites[facility.site_id if facility is not None else project.site_id]
                if not constructing else None)
        place = site.name if site is not None else world.society.settlements[project.settlement_id].name
        account_id = facility.payroll_account_id if facility is not None else project.account_id
        limits = {'schedule': blueprint.monthly_units,
                  'remaining': blueprint.required_units - project.completed_units,
                  'payroll_funds': economy.accounts[account_id].balance // (blueprint.workers_per_unit * blueprint.wage_per_worker),
                  'labor': sum(available[g.id] for g in world.society.population.values()
                               if g.settlement_id == stock.location_id
                               and g.occupation == blueprint.worker_occupation) // blueprint.workers_per_unit}
        limits.update({f'input:{r}': stock.goods.get(r, 0) // amount for r, amount in blueprint.inputs.items()})
        if stock.owner_ref != project.owner_ref or any(not can_actor_act_for(world, project.owner_ref, project.owner_ref, scope)
                                                       for scope in ('trade', 'supply')):
            limits['authority'] = 0
        if site is not None and (not site.enabled or site.integrity <= 0):
            limits['site_unavailable'] = 0
        missing_capability = None if site is None else next(
            (capability for capability in blueprint.required_site_capabilities
             if capability not in site.capability_ids), None)
        if missing_capability is not None:
            limits[f'site_capability:{missing_capability}'] = 0
        if blueprint.required_technology_id and not world.knowledge.knows(project.owner_ref, blueprint.required_technology_id):
            limits['knowledge'] = 0
        if constructing:
            settlement = world.society.settlements.get(project.settlement_id)
            # The works stop if the administration changed hands or the place
            # already gained this capability some other way.
            if settlement is None or settlement.administrator_id != project.owner_ref.id:
                limits['administration'] = 0
            elif settlement.occupier_id not in (None, project.owner_ref.id):
                limits['occupation'] = 0
            elif project.new_site_id in world.map.infrastructure_sites or any(
                    settlement.region_id in item.region_ids
                    and blueprint.grants_capability_id in item.capability_ids
                    for item in world.map.infrastructure_sites.values()):
                limits['capability_exists'] = 0
        elif founding:
            created_id = foundation_line_id(site.id, blueprint.foundation_recipe_id)
            if (economy.recipes[blueprint.foundation_recipe_id].capability_id not in site.capability_ids):
                limits['site_capability:' + economy.recipes[blueprint.foundation_recipe_id].capability_id] = 0
            if created_id in economy.facilities or any(
                    item.site_id == site.id and item.recipe_id == blueprint.foundation_recipe_id
                    for item in economy.facilities.values()):
                limits['line_exists'] = 0
        else:
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
            if constructing:
                # The Map owns sites; this receipt is the fact it commissions on.
                # The capability is declared here so the place can never hold a
                # physical ability that no dated fact granted it.
                changes.extend((
                    _delta('site', project.new_site_id, 'capability_ids', None,
                           blueprint.grants_capability_id),
                    _delta('site', project.new_site_id, 'integrity', None, str(1.0)),
                    _delta('site', project.new_site_id, 'enabled', None, str(True)),
                    _delta('site', project.new_site_id, 'service_suspended', None, str(False)),
                    _delta('site', project.new_site_id, 'owner_ref', None,
                           json.dumps(project.owner_ref.to_dict(), sort_keys=True)),
                    _delta('site', project.new_site_id, 'maintainer_ref', None,
                           json.dumps(project.owner_ref.to_dict(), sort_keys=True)),
                ))
            elif founding:
                created_id = foundation_line_id(site.id, blueprint.foundation_recipe_id)
                changes.extend((_delta('production', created_id, 'recipe_id', None, blueprint.foundation_recipe_id),
                                _delta('production', created_id, 'max_batches', 0, blueprint.new_capacity)))
            elif blueprint.additional_recipe_id:
                changes.extend((_delta('production', line_id(facility, blueprint), 'recipe_id', None, blueprint.additional_recipe_id),
                                _delta('production', line_id(facility, blueprint), 'max_batches', 0, blueprint.new_capacity)))
            else:
                changes.append(_delta('production', facility.id, 'max_batches', facility.max_batches,
                                      facility.max_batches + blueprint.capacity_gain))
            if blueprint.stock_capacity_gain:
                changes.append(_delta('stock', stock.id, 'capacity', stock.capacity,
                                      stock.capacity + blueprint.stock_capacity_gain))
            if blueprint.to_recipe_id:
                changes.append(_delta('production', facility.id, 'recipe_id', facility.recipe_id, blueprint.to_recipe_id))
        description = {'completed': 'concluída', 'building': 'em construção', 'blocked': 'impedida'}[stage]
        if blocker:
            reason = (f"faltam materiais: {economy.resources[blocker[6:]].name}" if blocker.startswith('input:') else
                      f"falta capacidade física: {blocker.split(':', 1)[1]}" if blocker.startswith('site_capability:') else
                      {'authority': 'sem autoridade vigente', 'payroll_funds': 'sem saldo para salários',
                       'labor': 'sem artesãos disponíveis', 'site_unavailable': 'instalação indisponível',
                       'knowledge': 'conhecimento indisponível', 'recipe_changed': 'instalação já alterada',
                       'line_exists': 'linha produtiva já existente ou planejada',
                       'administration': 'sem administração vigente do assentamento',
                       'occupation': 'assentamento ocupado por outra instituição',
                       'capability_exists': 'a capacidade já existe no local'}[blocker])
            description += f'; {reason}'
        kind = 'obra' if constructing else 'fundação' if founding else 'ampliação'
        event = _apply_stock(world, stock, goods, 'expansion_progressed',
            f'{place}: {kind} {done}/{blueprint.required_units}; {description}.',
            extra_deltas=changes, cause_ids=_causes(project.last_event_id,
                                                  facility.last_event_id if facility is not None else None,
                                                  site.last_event_id if site is not None else None,
                                                  economy.accounts[account_id].last_event_id))
        if units:
            settle_work(world, work_id=project.id, account_id=account_id,
                stock_id=stock.id, occupation=blueprint.worker_occupation,
                worker_count=units * blueprint.workers_per_unit,
                wage=blueprint.wage_per_worker, available=available, production_event_id=event.id)
        economy.expansions[project.id] = project.model_copy(update={'completed_units': done, 'stage': stage,
            'blocker': blocker, 'last_work_day': day, 'last_event_id': event.id})
        if stage == 'completed':
            if constructing:
                settlement = world.society.settlements[project.settlement_id]
                world.map.commission_infrastructure_site(
                    project.new_site_id, kind=blueprint.site_kind,
                    name=f'{blueprint.name} de {settlement.name}',
                    region_id=settlement.region_id,
                    capability_ids=(blueprint.grants_capability_id,),
                    owner_ref=project.owner_ref, last_event_id=event.id)
            elif founding:
                # The finished works are the site's first line for this recipe:
                # it shares the site's canonical stock and the owner's payroll.
                created = ProductionFacility(
                    id=foundation_line_id(site.id, blueprint.foundation_recipe_id), site_id=site.id,
                    stock_id=stock.id, recipe_id=blueprint.foundation_recipe_id,
                    max_batches=blueprint.new_capacity, payroll_account_id=account_id,
                    wage_per_worker=blueprint.wage_per_worker, last_event_id=event.id)
                economy.facilities[created.id] = created
            elif blueprint.additional_recipe_id:
                commission_line(economy, facility, blueprint, event.id)
            else:
                economy.facilities[facility.id] = facility.model_copy(update={
                    'max_batches': facility.max_batches + blueprint.capacity_gain, 'last_event_id': event.id,
                    'recipe_id': blueprint.to_recipe_id or facility.recipe_id})
            if blueprint.stock_capacity_gain:
                current_stock = economy.stocks[stock.id]
                economy.stocks[stock.id] = current_stock.model_copy(
                    update={'capacity': current_stock.capacity + blueprint.stock_capacity_gain})
