"""Monthly institutional research and application, using only owned operations."""
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.governance.models import Objective
from .economy import _causes
from .events import record_event
from .research import start_research, research_blocker


def review_research(world):
    if world.clock.absolute_day and world.clock.absolute_day % 30 == 0:
        _propose_research(world)
        _apply_known_techniques(world)
    for project in world.research.projects.values():
        if project.stage in {'completed', 'superseded'}:
            continue
        stock = world.economy.stocks[project.stock_id]
        for rid in world.research.technologies[project.technology_id].inputs:
            if any(o.stock_id == stock.id and o.resource_id == rid for o in world.strategy.objectives.values()):
                continue
            goal = Objective(id=f'inputs:{stock.id}:{rid}', actor_ref=project.owner_ref, stock_id=stock.id,
                settlement_id=stock.location_id, resource_id=rid, kind='maintain_production_inputs',
                motivation='Obter materiais para a pesquisa autorizada.')
            world.strategy.objectives[goal.id] = goal


def _propose_research(world):
    economy = world.economy
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda s: s.id):
        owner = site.owner_ref
        if owner is None or any(p.owner_ref == owner and p.stage not in {'completed', 'superseded'} for p in world.research.projects.values()):
            continue
        accounts = [a for a in economy.accounts.values() if a.owner_ref == owner]
        stocks = [s for s in economy.stocks.values() if s.owner_ref == owner
                  and world.society.settlements[s.location_id].region_id in site.region_ids]
        if not accounts or not stocks:
            continue
        account, stock = sorted(accounts, key=lambda a: a.id)[0], sorted(stocks, key=lambda s: s.id)[0]
        for tech in sorted(world.research.technologies.values(), key=lambda t: t.id):
            if world.knowledge.knows(owner, tech.id) or tech.capability_id not in site.capability_ids:
                continue
            candidates = sorted(world.society.characters.values(), key=lambda c: (-getattr(c.skills, tech.skill), c.id))
            lead = next((c for c in candidates if c.personality.curiosity >= .25
                and not any(p.researcher_id == c.id and p.stage not in {'completed', 'superseded'} for p in world.research.projects.values())
                and research_blocker(world, tech, site.id, stock.id, account.id, c.id, owner) is None), None)
            if lead is None:
                continue
            # Estimate full experiment wages/materials; no promise that other spending cannot interrupt it.
            material_cost = sum(max(0, q * tech.required_units - stock.goods.get(r, 0)) * economy.markets[stock.location_id].prices[r]
                                for r, q in tech.inputs.items())
            wage_cost = tech.required_units * (1 + tech.assistants_per_unit) * tech.wage_per_worker
            if account.balance < material_cost + wage_cost:
                continue
            terms = dict(technology_id=tech.id, site_id=site.id, stock_id=stock.id, account_id=account.id, researcher_id=lead.id)
            offer = record_event(world, 'research_decided', f'Financiar {tech.name} com trabalho especializado.',
                fact_kind=FactKind.DECISION, decision={**terms, 'action': 'research', 'actor_ref': owner.to_dict()},
                cause_ids=_causes(account.last_event_id, site.last_event_id))
            # The deterministic researcher policy accepts qualified, local, paid work consistent with curiosity.
            accepted = record_event(world, 'research_accepted', f'{lead.name} aceita participar da pesquisa.',
                fact_kind=FactKind.DECISION, decision={**terms, 'action': 'research_work', 'actor_ref': EntityRef('character', lead.id).to_dict()},
                cause_ids=(offer.id,))
            start_research(world, **terms, sponsor_decision_id=offer.id, researcher_decision_id=accepted.id)
            break


def _apply_known_techniques(world):
    from .expansion import start_expansion
    from .industrial_lines import line_exists_or_planned
    economy = world.economy
    for facility in sorted(economy.facilities.values(), key=lambda f: f.id):
        if any(p.facility_id == facility.id and p.stage != 'completed' for p in economy.expansions.values()):
            continue
        stock = economy.stocks[facility.stock_id]
        for blueprint in sorted(economy.expansion_blueprints.values(), key=lambda b: b.id):
            if (not blueprint.required_technology_id
                    or (not blueprint.additional_recipe_id and blueprint.from_recipe_id != facility.recipe_id)
                    or not world.knowledge.knows(stock.owner_ref, blueprint.required_technology_id)):
                continue
            target = blueprint.additional_recipe_id or blueprint.to_recipe_id
            site = world.map.infrastructure_sites[facility.site_id]
            if (not target or economy.recipes[target].capability_id not in site.capability_ids
                    or not site.enabled or site.integrity <= 0
                    or line_exists_or_planned(economy, facility, blueprint)):
                continue
            from src.classes.governance.authority import can_actor_act_for
            if any(not can_actor_act_for(world, stock.owner_ref, stock.owner_ref, scope) for scope in ('trade', 'supply')):
                continue
            account = economy.accounts[facility.payroll_account_id]
            cost = blueprint.required_units * blueprint.workers_per_unit * blueprint.wage_per_worker
            cost += sum(max(0, q * blueprint.required_units - stock.goods.get(r, 0)) * economy.markets[stock.location_id].prices[r]
                        for r, q in blueprint.inputs.items())
            if account.balance < cost:
                continue
            decision = record_event(world, 'adaptation_decided', f'Aplicar conhecimento em {blueprint.name}.',
                fact_kind=FactKind.DECISION, decision={'action': 'expand', 'actor_ref': stock.owner_ref.to_dict(),
                    'facility_id': facility.id, 'blueprint_id': blueprint.id}, cause_ids=_causes(facility.last_event_id, account.last_event_id))
            start_expansion(world, facility.id, blueprint.id, decision_event_id=decision.id)
            break
