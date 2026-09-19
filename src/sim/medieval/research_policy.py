"""Monthly institutional research and application, using only owned operations."""
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.governance.models import Objective
from src.classes.society.models import SocietyValue
from .economy import _causes
from .events import record_event
from .research import start_research, research_blocker


class ResearchOption(SocietyValue):
    """Transient sponsorship choice; the owner recomposes all terms on execute."""
    id: str
    actor_ref: EntityRef
    technology_id: str
    site_id: str
    stock_id: str
    account_id: str
    researcher_id: str
    site_event_id: str | None = None
    account_event_id: str | None = None
    stock_event_ids: tuple[str, ...] = ()

    def decision(self):
        return {"action": "research", "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def research_options(world, actor):
    """Enumerate one materially feasible research sponsorship per site/tech."""
    if not isinstance(actor, EntityRef):
        return ()
    economy = world.economy
    options = []
    for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
        if site.owner_ref != actor or not site.enabled or site.integrity <= 0:
            continue
        if any(project.owner_ref == actor and project.stage not in {"completed", "superseded"}
               for project in world.research.projects.values()):
            continue
        accounts = sorted((account for account in economy.accounts.values()
                           if account.owner_ref == actor), key=lambda item: item.id)
        stocks = sorted((stock for stock in economy.stocks.values()
                         if stock.owner_ref == actor
                         and world.society.settlements[stock.location_id].region_id in site.region_ids),
                        key=lambda item: item.id)
        for account in accounts:
            for stock in stocks:
                for technology in sorted(world.research.technologies.values(), key=lambda item: item.id):
                    if world.knowledge.knows(actor, technology.id) or technology.capability_id not in site.capability_ids:
                        continue
                    candidates = sorted(world.society.characters.values(),
                                        key=lambda character: (-getattr(character.skills, technology.skill), character.id))
                    lead = next((character for character in candidates
                                 if character.personality.curiosity >= .25
                                 and not any(project.researcher_id == character.id
                                             and project.stage not in {"completed", "superseded"}
                                             for project in world.research.projects.values())
                                 and research_blocker(world, technology, site.id, stock.id,
                                                      account.id, character.id, actor) is None), None)
                    if lead is None:
                        continue
                    material_cost = sum(max(0, quantity * technology.required_units
                                            - stock.goods.get(resource, 0))
                                        * economy.markets[stock.location_id].prices[resource]
                                        for resource, quantity in technology.inputs.items())
                    wage_cost = technology.required_units * (1 + technology.assistants_per_unit) * technology.wage_per_worker
                    if account.balance < material_cost + wage_cost:
                        continue
                    option_id = (f"research:{actor.kind}:{actor.id}:{technology.id}:{site.id}:"
                                 f"{stock.id}:{account.id}:{lead.id}:{site.last_event_id}")
                    options.append(ResearchOption(
                        id=option_id, actor_ref=actor, technology_id=technology.id,
                        site_id=site.id, stock_id=stock.id, account_id=account.id,
                        researcher_id=lead.id, site_event_id=site.last_event_id,
                        account_event_id=account.last_event_id,
                        stock_event_ids=tuple(sorted(stock.last_event_ids.values()))))
    return tuple(options)


def _research_causes(world, option):
    return _causes(option.site_event_id, option.account_event_id, *option.stock_event_ids)


def execute_research_option(world, actor, option_id, decision_event_id):
    option = next((item for item in research_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("research option is stale or unknown")
    # The menu decision carries only the affordance ID.  The owner recomposes
    # private terms into a separate dated authorization receipt before
    # start_research validates and persists the project.
    sponsor = record_event(
        world, "research_authorized", "A instituição autorizou a pesquisa escolhida.",
        fact_kind=FactKind.DECISION,
        decision={
            "action": "research", "actor_ref": actor.to_dict(),
            "technology_id": option.technology_id, "site_id": option.site_id,
            "stock_id": option.stock_id, "account_id": option.account_id,
            "researcher_id": option.researcher_id,
        },
        cause_ids=(decision_event_id,))
    accepted = record_event(
        world, "research_accepted", "O pesquisador aceita participar da pesquisa.",
        fact_kind=FactKind.DECISION,
        decision={"action": "research_work", "actor_ref": EntityRef("character", option.researcher_id).to_dict(),
                  "technology_id": option.technology_id, "site_id": option.site_id,
                  "stock_id": option.stock_id, "account_id": option.account_id,
                  "researcher_id": option.researcher_id},
        cause_ids=(sponsor.id,))
    start_research(
        world, option.technology_id, option.site_id, option.stock_id, option.account_id,
        option.researcher_id, sponsor_decision_id=sponsor.id,
        researcher_decision_id=accepted.id)


def research_adapters():
    from .institutional_decision_turn import DiscretionaryAdapter
    return (DiscretionaryAdapter(
        name="research", family="production", options_fn=research_options,
        label_fn=lambda option: f"Financiar pesquisa de {option.technology_id} com {option.researcher_id}.",
        causes_fn=_research_causes, execute_fn=execute_research_option),)


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
    if world.config.ai_enabled:
        return
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
    # In provider-enabled worlds, applying a known technique is offered as a
    # production affordance in the composed civil menu.  Keep this fallback
    # only for deterministic/offline worlds; otherwise it would bypass the
    # actor's monthly choice and create a second technology planner.
    if world.config.ai_enabled:
        return
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
                    or any(capability not in site.capability_ids
                           for capability in blueprint.required_site_capabilities)
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
