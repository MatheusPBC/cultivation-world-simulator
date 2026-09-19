"""A bounded, material technology-theft mission.

The mission does not invent a technique or reveal a hidden catalog.  It can
only target a running line whose technology the actor has already sighted and
whose installation the named agent can physically observe.  Success copies the
existing canonical knowledge fact through the ``stolen`` channel; failure and
discovery leave knowledge unchanged.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import site_report_id
from src.classes.governance.models import TechnologyTheftFinding
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .economy import _causes, _delta
from .events import record_event
from .espionage import _agents, _target_detects
from .institutional_decision_turn import DiscretionaryAdapter
from .research import learn_technology


STEAL_ACTION = "steal_technology"
MIN_STEAL_SKILL = 1
SUCCESS_STEAL_SKILL = 50
REPORT_MAX_AGE = 30


@dataclass(frozen=True)
class TechnologyTheftOption:
    id: Identity
    actor_ref: EntityRef
    agent_ref: EntityRef
    site_id: Identity
    target_owner_ref: EntityRef
    technology_id: Identity
    observation_event_id: Identity
    source_knowledge_event_id: Identity

    def decision(self):
        return {"action": STEAL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _site_observation(world, actor, site_id):
    report = world.knowledge.site_report(actor, site_id)
    if (report is None or report.site_id != site_id
            or not 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE):
        return None
    event = next((item for item in world.events if item.id == report.event_id), None)
    if (event is None or event.event_type != "site_observed"
            or not any(delta.owner_kind == "site_report" and delta.owner_id == site_report_id(actor, site_id)
                       and delta.aspect == "observation" for delta in event.deltas)):
        return None
    return report, event


def _running_technology(world, site_id, owner_ref):
    site = world.map.infrastructure_sites.get(site_id)
    if site is None or not site.enabled or site.integrity <= 0 or site.service_suspended:
        return ()
    result = []
    known = {item.technology_id: item.event_id for item in world.knowledge.technologies.values()
             if item.owner_ref == owner_ref}
    for facility in sorted(world.economy.facilities.values(), key=lambda item: item.id):
        if facility.site_id != site_id:
            continue
        stock = world.economy.stocks.get(facility.stock_id)
        recipe = world.economy.recipes.get(facility.recipe_id)
        if stock is None or recipe is None or stock.owner_ref != owner_ref:
            continue
        for technology_id, source_event_id in sorted(known.items()):
            technology = world.research.technologies.get(technology_id)
            if technology is not None and technology.capability_id in site.capability_ids:
                result.append((technology_id, source_event_id))
    return tuple(result)


def _already_resolved(world, actor, agent, site_id, technology_id):
    return any(item.recipient_ref == actor and item.agent_ref == agent and item.site_id == site_id
               and item.technology_id == technology_id and item.learned_day == world.clock.absolute_day
               for item in world.knowledge.technology_theft_findings.values())


def technology_theft_options(world, actor_ref):
    if (not isinstance(actor_ref, EntityRef) or actor_ref.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor_ref, actor_ref, "research")
            or not can_actor_act_for(world, actor_ref, actor_ref, "diplomacy")):
        return ()
    day = world.clock.absolute_day
    options = []
    for agent in _agents(world, actor_ref):
        if agent.skills.investigation < MIN_STEAL_SKILL:
            continue
        agent_ref = EntityRef("character", agent.id)
        for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
            settlement = next((item for item in world.society.settlements.values()
                               if item.region_id in site.region_ids), None)
            if settlement is None or agent.location_id != settlement.id:
                continue
            target_owner = site.owner_ref
            if target_owner is None or target_owner == actor_ref or target_owner.kind not in {"polity", "organization"}:
                continue
            observation = _site_observation(world, actor_ref, site.id)
            if observation is None:
                continue
            for technology_id, source_event_id in _running_technology(world, site.id, target_owner):
                if world.knowledge.knows(actor_ref, technology_id):
                    continue
                if not world.knowledge.has_current_technology_sighting(actor_ref, target_owner, technology_id, day):
                    continue
                if _already_resolved(world, actor_ref, agent_ref, site.id, technology_id):
                    continue
                options.append(TechnologyTheftOption(
                    id=f"technology-theft:{actor_ref.kind}:{actor_ref.id}:{agent.id}:{site.id}:{technology_id}:{observation[1].id}",
                    actor_ref=actor_ref, agent_ref=agent_ref, site_id=site.id,
                    target_owner_ref=target_owner, technology_id=technology_id,
                    observation_event_id=observation[1].id, source_knowledge_event_id=source_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def _decision(world, decision_event_id, option):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision != option.decision()):
        raise ValueError("technology theft requires its exact current decision")
    return event


def execute_technology_theft(world, actor_ref, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in technology_theft_options(candidate, actor_ref) if item.id == option_id), None)
    if option is None:
        raise ValueError("technology theft option is absent or stale")
    decision = _decision(candidate, decision_event_id, option)
    require_authority(candidate, actor_ref, "research")
    require_authority(candidate, actor_ref, "diplomacy")
    agent = candidate.society.characters.get(option.agent_ref.id)
    site = candidate.map.infrastructure_sites.get(option.site_id)
    if (agent is None or agent.death_day is not None or site is None or agent.location_id != next(
            item.id for item in candidate.society.settlements.values() if item.region_id in site.region_ids)):
        raise ValueError("technology theft agent or site is no longer valid")
    observation = _site_observation(candidate, actor_ref, site.id)
    if observation is None or observation[1].id != option.observation_event_id:
        raise ValueError("technology theft observation is stale")
    source = next((item for item in candidate.knowledge.technologies.values()
                   if item.owner_ref == option.target_owner_ref and item.technology_id == option.technology_id
                   and item.event_id == option.source_knowledge_event_id), None)
    if source is None or not candidate.knowledge.has_current_technology_sighting(
            actor_ref, option.target_owner_ref, option.technology_id, candidate.clock.absolute_day):
        raise ValueError("technology theft source evidence is stale")
    detected = _target_detects(candidate, EntityRef("settlement", next(
        item.id for item in candidate.society.settlements.values() if item.region_id in site.region_ids)), option.target_owner_ref)
    result = "discovered" if detected else ("success" if agent.skills.investigation >= SUCCESS_STEAL_SKILL else "failure")
    finding_id = f"technology_theft_finding:{decision.id}"
    causes = _causes(decision.id, option.observation_event_id, option.source_knowledge_event_id)
    learned_event_id = None
    if result == "success":
        learn_technology(candidate, actor_ref, option.technology_id, "stolen", causes)
        learned_event_id = next(item.event_id for item in candidate.knowledge.technologies.values()
                                if item.owner_ref == actor_ref and item.technology_id == option.technology_id)
    deltas = [_delta("technology_theft_finding", finding_id, "result", None, result)]
    if result == "success":
        deltas.extend((
            _delta("technology_theft_finding", finding_id, "source_knowledge_event_id", None,
                   option.source_knowledge_event_id),
            _delta("technology_theft_finding", finding_id, "learned_knowledge_event_id", None,
                   learned_event_id),
        ))
    event = record_event(
        candidate, "technology_theft_resolved", "Uma tentativa material de obter uma técnica foi resolvida.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(deltas),
        cause_ids=_causes(*causes, *( (learned_event_id,) if learned_event_id else ())))
    finding = TechnologyTheftFinding(
        id=finding_id, mission_id=option.id, decision_event_id=decision.id, recipient_ref=actor_ref,
        agent_ref=option.agent_ref, site_id=option.site_id, target_owner_ref=option.target_owner_ref,
        technology_id=option.technology_id, observation_event_id=option.observation_event_id, result=result,
        source_knowledge_event_id=option.source_knowledge_event_id if result == "success" else None,
        learned_knowledge_event_id=learned_event_id, learned_day=candidate.clock.absolute_day, event_id=event.id)
    candidate.knowledge.technology_theft_findings[finding.id] = finding
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return finding


def technology_theft_adapters():
    return (DiscretionaryAdapter(
        name="technology_theft", family="research", options_fn=technology_theft_options,
        label_fn=lambda option: f"Tentar obter a técnica {option.technology_id} na instalação observada.",
        causes_fn=lambda _world, option: (option.observation_event_id, option.source_knowledge_event_id),
        execute_fn=lambda world, actor, option_id, decision_event_id:
            execute_technology_theft(world, actor, option_id, decision_event_id),
    ),)


__all__ = ["STEAL_ACTION", "TechnologyTheftOption", "technology_theft_options",
           "execute_technology_theft", "technology_theft_adapters"]
