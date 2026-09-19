"""Conservative monthly investment policy over an institution's own operations."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.models import Objective
from .economy import _causes
from .events import record_event


def review_investment(world):
    from .expansion import start_expansion
    economy = world.economy
    for facility in sorted(economy.facilities.values(), key=lambda f: f.id):
        if world.clock.absolute_day == 0 or any(p.facility_id == facility.id and p.stage != 'completed' for p in economy.expansions.values()):
            continue
        stock = economy.stocks[facility.stock_id]
        owner = stock.owner_ref
        recipe = economy.recipes[facility.recipe_id]
        site = world.map.infrastructure_sites[facility.site_id]
        if (not facility.max_batches or facility.last_batches != facility.max_batches
                or not site.enabled or site.integrity < 1
                or any(not can_actor_act_for(world, owner, owner, scope) for scope in ('trade', 'supply'))):
            continue
        # With the institutional provider enabled, expansion is an explicit
        # affordance in the composed monthly menu.  The deterministic path is
        # retained only for worlds that explicitly run without an actor/provider
        # so test-mode and offline fixtures remain conservative and auditable.
        if world.config.ai_enabled:
            continue
        # Do not expand an idle plant or a full store; no foreign stock is inspected.
        if all(stock.goods.get(r, 0) >= amount * facility.max_batches * 2 for r, amount in recipe.outputs.items()):
            continue
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda b: b.id):
            if blueprint.required_technology_id:
                continue  # Technical adaptations have their own knowledge-aware policy.
            people = sum(g.count for g in world.society.population.values()
                         if g.settlement_id == stock.location_id and g.occupation == recipe.occupation)
            artisans = sum(g.count for g in world.society.population.values()
                           if g.settlement_id == stock.location_id and g.occupation == 'artisan')
            if people < (facility.max_batches + blueprint.capacity_gain) * recipe.workers or artisans < blueprint.workers_per_unit:
                continue
            price = economy.markets[stock.location_id].prices
            material_budget = sum(max(0, amount * blueprint.required_units - stock.goods.get(r, 0)) * price[r]
                                  for r, amount in blueprint.inputs.items())
            wage_budget = blueprint.required_units * blueprint.workers_per_unit * blueprint.wage_per_worker
            operating_buffer = facility.max_batches * recipe.workers * facility.wage_per_worker * 2
            account = economy.accounts[facility.payroll_account_id]
            if account.balance < material_budget + wage_budget + operating_buffer:
                continue
            decision = record_event(world, 'expansion_decided', f'{site.name}: investir em capacidade utilizada.',
                fact_kind=FactKind.DECISION, decision={'action': 'expand', 'actor_ref': owner.to_dict(),
                    'facility_id': facility.id, 'blueprint_id': blueprint.id},
                cause_ids=_causes(facility.last_event_id, account.last_event_id, *(stock.last_event_ids.get(r) for r in recipe.outputs)))
            start_expansion(world, facility.id, blueprint.id, decision_event_id=decision.id)
            break
    # Existing resource objectives include construction requirements once, not per month.
    for facility in economy.facilities.values():
        stock = economy.stocks[facility.stock_id]
        for rid in economy.recipes[facility.recipe_id].inputs:
            if any(o.stock_id == stock.id and o.resource_id == rid for o in world.strategy.objectives.values()):
                continue
            goal = Objective(id=f'inputs:{stock.id}:{rid}', actor_ref=stock.owner_ref,
                stock_id=stock.id, settlement_id=stock.location_id, resource_id=rid,
                kind='maintain_production_inputs', motivation='Abastecer as linhas produtivas em operação.')
            world.strategy.objectives[goal.id] = goal
    for project in economy.expansions.values():
        if project.stage == 'completed':
            continue
        facility = economy.facilities[project.facility_id]
        stock = economy.stocks[facility.stock_id]
        for rid in economy.expansion_blueprints[project.blueprint_id].inputs:
            if any(o.stock_id == stock.id and o.resource_id == rid for o in world.strategy.objectives.values()):
                continue
            goal = Objective(id=f'inputs:{stock.id}:{rid}', actor_ref=project.owner_ref,
                stock_id=stock.id, settlement_id=stock.location_id, resource_id=rid,
                kind='maintain_production_inputs', motivation='Obter materiais para a produção e as obras autorizadas.')
            world.strategy.objectives[goal.id] = goal
