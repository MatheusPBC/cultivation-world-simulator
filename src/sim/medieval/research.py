"""Monthly research with independent consent, real specialists and material costs."""

from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import ResearchProject, TechnicalKnowledge
from src.classes.governance.authority import can_actor_act_for
from .events import record_event
from .economy import _apply_stock, _causes, _delta
from .labor import settle_work


RESEARCHER_REVIEW_KIND = "character_rite_offer_review"


def _event_causes(event):
    return {link.cause_event_id for link in event.causal_links}


def _authorization_for(world, sponsor_decision_id):
    return next((event for event in reversed(world.events)
                 if event.event_type == "research_authorized"
                 and sponsor_decision_id in _event_causes(event)), None)


def _authorization_terms(event):
    decision = event.decision or {}
    keys = ("technology_id", "site_id", "stock_id", "account_id", "researcher_id")
    return {key: decision[key] for key in keys} if all(key in decision for key in keys) else None


def _research_option_id(authorization_event_id, researcher_id):
    return f"research-work:{authorization_event_id}:{researcher_id}"


@dataclass(frozen=True)
class ResearcherWorkOption:
    id: str
    authorization_event_id: str
    sponsor_decision_id: str
    researcher_id: str
    owner_ref: EntityRef
    technology_id: str
    site_id: str
    stock_id: str
    account_id: str

    def decision(self):
        return {"action": "research_work", "actor_ref": EntityRef("character", self.researcher_id).to_dict(),
                "selected_affordance_id": self.id}


def _offer_was_declined(world, authorization_event_id, researcher_id):
    option_id = _research_option_id(authorization_event_id, researcher_id)
    actor = EntityRef("character", researcher_id).to_dict()
    return any(event.fact_kind == FactKind.DECISION
               and event.causal_origin is CausalOrigin.ACTOR_DECISION
               and (event.decision or {}).get("actor_ref") == actor
               and (event.decision or {}).get("action") == "no_action"
               and option_id in (event.decision or {}).get("declined_option_ids", ())
               for event in world.events)


def _authorization_closed(world, event):
    source = next(iter(_event_causes(event)), None)
    if source is None:
        return True
    if any(project.sponsor_decision_id == source for project in world.research.projects.values()):
        return True
    terms = _authorization_terms(event)
    return (terms is None or _offer_was_declined(world, event.id, terms["researcher_id"])
            or any(receipt.event_type == "research_offer_lapsed" and event.id in _event_causes(receipt)
                   for receipt in world.events))


def has_open_research_authorization(world, owner_ref):
    return any(event.event_type == "research_authorized"
               and not _authorization_closed(world, event)
               and _authorization_terms(event) is not None
               and (sponsor_id := next(iter(_event_causes(event)), None)) is not None
               and (sponsor := world.event_index().get(sponsor_id)) is not None
               and sponsor.causal_origin == CausalOrigin.ACTOR_DECISION
               and (sponsor.decision or {}).get("actor_ref") == owner_ref.to_dict()
               for event in world.events)


def researcher_work_options(world, researcher_id):
    """Current engine-owned paid research offers addressed to one researcher."""
    character = world.society.characters.get(researcher_id)
    if character is None or character.death_day is not None:
        return ()
    options = []
    projects = tuple(world.research.projects.values())
    for authorization in world.events:
        if authorization.event_type != "research_authorized" or _authorization_closed(world, authorization):
            continue
        terms = _authorization_terms(authorization)
        if terms is None or terms["researcher_id"] != researcher_id:
            continue
        sponsor_id = next(iter(_event_causes(authorization)), None)
        sponsor = world.event_index().get(sponsor_id)
        if (sponsor is None or sponsor.fact_kind != FactKind.DECISION
                or sponsor.causal_origin != CausalOrigin.ACTOR_DECISION):
            continue
        owner = EntityRef.from_dict(sponsor.decision["actor_ref"])
        if any(project.stage not in {"completed", "superseded"}
               and (project.owner_ref == owner or project.researcher_id == researcher_id)
               for project in projects):
            continue
        technology = world.research.technologies.get(terms["technology_id"])
        if technology is None:
            continue
        blocker = research_blocker(world, technology, terms["site_id"], terms["stock_id"],
                                   terms["account_id"], researcher_id, owner)
        if blocker or world.knowledge.knows(owner, technology.id):
            continue
        stock = world.economy.stocks[terms["stock_id"]]
        account = world.economy.accounts[terms["account_id"]]
        material_cost = sum(max(0, amount * technology.required_units - stock.goods.get(resource, 0))
                            * world.economy.markets[stock.location_id].prices[resource]
                            for resource, amount in technology.inputs.items())
        wage_cost = technology.required_units * (1 + technology.assistants_per_unit) * technology.wage_per_worker
        if account.balance < material_cost + wage_cost:
            continue
        options.append(ResearcherWorkOption(
            id=_research_option_id(authorization.id, researcher_id),
            authorization_event_id=authorization.id, sponsor_decision_id=sponsor.id,
            researcher_id=researcher_id, owner_ref=owner, technology_id=technology.id,
            site_id=terms["site_id"], stock_id=terms["stock_id"], account_id=terms["account_id"],
        ))
    return tuple(options)


def lapse_stale_research_offers(world, researcher_id):
    """Close only offers that lost all current owner-valid work affordances."""
    active = {option.authorization_event_id for option in researcher_work_options(world, researcher_id)}
    changed = False
    for authorization in world.events:
        terms = _authorization_terms(authorization) if authorization.event_type == "research_authorized" else None
        if (terms is None or terms["researcher_id"] != researcher_id or _authorization_closed(world, authorization)
                or authorization.id in active):
            continue
        record_event(world, "research_offer_lapsed", "A oferta de pesquisa perdeu as condições materiais antes da resposta.",
                     fact_kind=FactKind.OCCURRENCE, cause_ids=(authorization.id,))
        changed = True
    return changed


def accept_research_work(world, researcher_id, option_id, decision_event_id):
    from copy import deepcopy

    candidate = deepcopy(world)
    option = next((item for item in researcher_work_options(candidate, researcher_id)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("researcher work option is stale or unknown")
    decision = candidate.event_index().get(decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != candidate.clock.absolute_day or decision.decision != option.decision()
            or decision.causal_origin != CausalOrigin.ACTOR_DECISION):
        raise ValueError("research requires the researcher's current actor decision")
    start_research(candidate, option.technology_id, option.site_id, option.stock_id, option.account_id,
                   researcher_id, sponsor_decision_id=option.sponsor_decision_id,
                   researcher_decision_id=decision.id)
    world.__dict__.update(candidate.__dict__)
    return world.research.projects[f"research:{option.sponsor_decision_id}"]


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
    events = world.event_index()
    sponsor = events.get(sponsor_decision_id)
    researcher = events.get(researcher_decision_id)
    sponsor_data = sponsor.decision if sponsor is not None else None
    researcher_data = researcher.decision if researcher is not None else None
    authorization = _authorization_for(world, sponsor_decision_id)
    authorization_terms = _authorization_terms(authorization) if authorization is not None else None
    valid_sponsor = (sponsor is not None and sponsor.fact_kind == FactKind.DECISION
                     and sponsor.causal_origin == CausalOrigin.ACTOR_DECISION
                     and sponsor.day <= world.clock.absolute_day
                     and sponsor_data.get('action') == 'research'
                     and sponsor_data.get('actor_ref') == owner.to_dict())
    if authorization_terms is not None:
        valid_sponsor = (valid_sponsor and authorization_terms == terms
                         and authorization.day == sponsor.day)
    else:
        # The offline routine-rules path owns a fully specified decision on the
        # same boundary; it remains explicit as fallback, never as provider consent.
        valid_sponsor = (valid_sponsor and sponsor.day == world.clock.absolute_day
                         and all(sponsor_data.get(key) == value for key, value in terms.items()))
    expected_researcher = {**terms, 'action': 'research_work',
                           'actor_ref': EntityRef('character', researcher_id).to_dict()}
    valid_researcher = (researcher is not None and researcher.fact_kind == FactKind.DECISION
                        and researcher.causal_origin == CausalOrigin.ACTOR_DECISION
                        and researcher.day == world.clock.absolute_day
                        and researcher_data.get('actor_ref') == expected_researcher['actor_ref']
                        and (researcher_data == expected_researcher
                             or authorization is not None
                             and researcher_data == {"action": "research_work",
                                 "actor_ref": expected_researcher["actor_ref"],
                                 "selected_affordance_id": _research_option_id(authorization.id, researcher_id)}))
    if (not valid_sponsor or not valid_researcher
            or any(eid in (p.sponsor_decision_id, p.researcher_decision_id)
                   for p in world.research.projects.values()
                   for eid in (sponsor_decision_id, researcher_decision_id))):
        raise ValueError('research requires a prior sponsorship and current researcher decision')
    blocker = research_blocker(world, technology, site_id, stock_id, account_id, researcher_id, owner)
    if blocker or world.knowledge.knows(owner, technology_id) or any(
            p.stage not in {'completed', 'superseded'} and (p.owner_ref == owner or p.researcher_id == researcher_id) for p in world.research.projects.values()):
        raise ValueError(f'research unavailable: {blocker or "known or busy"}')
    project_id = f'research:{sponsor_decision_id}'
    start_causes = [sponsor_decision_id, researcher_decision_id]
    if authorization is not None:
        start_causes.append(authorization.id)
    event = record_event(world, 'research_started', f'Pesquisa autorizada: {technology.name}; ainda sem descoberta.',
        fact_kind=FactKind.STATE_TRANSITION, deltas=(_delta('research', project_id, 'stage', None, 'waiting'),),
        cause_ids=tuple(start_causes))
    project = ResearchProject(id=project_id, owner_ref=owner, **terms,
        sponsor_decision_id=sponsor_decision_id, researcher_decision_id=researcher_decision_id,
        started_day=world.clock.absolute_day, last_event_id=event.id)
    world.research.projects[project.id] = project
    return project


def learn_technology(world, owner, technology_id, channel, causes, *, causal_payload=None):
    if world.knowledge.knows(owner, technology_id):
        return
    key = f'technology:{owner.kind}:{owner.id}:{technology_id}'
    technology = world.research.technologies[technology_id]
    if any(not world.knowledge.knows(owner, prerequisite) for prerequisite in technology.prerequisites):
        raise ValueError("technology prerequisites are not known by the learner")
    event = record_event(world, {'research': 'technology_discovered', 'teaching': 'technology_taught',
                                 'apprenticeship': 'technology_apprenticed',
                                 'copied': 'technique_copy_completed',
                                 'sale': 'technology_sold',
                                 'stolen': 'technology_stolen'}[channel],
        f'{technology.name}: conhecimento adquirido; instalações e equipamentos não foram criados.',
        fact_kind=FactKind.STATE_TRANSITION, causal_payload=causal_payload, cause_ids=causes,
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
        assistant_shortfall = 0
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
            if (units == 0 and limits['labor'] == 0
                    and available.get(lead.population_group_id, 0) >= 1
                    and all(value > 0 for key, value in limits.items() if key != 'labor')):
                assistant_shortfall = max(0, tech.assistants_per_unit - assistants)
        done = project.completed_units + units
        stage = 'superseded' if known else 'completed' if done == tech.required_units else 'researching' if units else 'blocked'
        goods = dict(stock.goods)
        for rid, amount in tech.inputs.items():
            if units:
                goods[rid] -= amount * units
        description = 'encerrada por conhecimento já adquirido' if known else 'concluída' if stage == 'completed' else 'em andamento' if units else 'impedida'
        event = _apply_stock(world, stock, goods, 'research_progressed', f'{tech.name}: pesquisa {done}/{tech.required_units}, {description}.',
            extra_deltas=(_delta('research', project.id, 'completed_units', project.completed_units, done),
                          _delta('research', project.id, 'stage', project.stage, stage),
                          *((_delta('research', project.id, 'labor_shortfall', 0, assistant_shortfall),)
                            if assistant_shortfall else ())),
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
