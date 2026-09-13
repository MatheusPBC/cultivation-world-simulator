from dataclasses import dataclass, field
from src.classes.event import FactKind
from src.classes.governance.serialization import RegistrySerialization, validate_actor
from src.classes.mechanical_language import EntityRef
from .models import Technology, ResearchProject, research_terms


@dataclass
class ResearchState(RegistrySerialization):
    technologies: dict[str, Technology] = field(default_factory=dict)
    projects: dict[str, ResearchProject] = field(default_factory=dict)
    registries = {'technologies': Technology, 'projects': ResearchProject}

    def validate(self, world=None):
        super().validate(world)
        visited, visiting = set(), set()
        def visit(key):
            if key not in self.technologies or key in visiting:
                raise ValueError('research prerequisites must form a known acyclic graph')
            if key in visited:
                return
            visiting.add(key)
            for other in self.technologies[key].prerequisites:
                visit(other)
            visiting.remove(key)
            visited.add(key)
        for key in self.technologies:
            visit(key)
        owners, researchers = set(), set()
        events = {e.id: e for e in world.events} if world is not None else {}
        for p in self.projects.values():
            if p.technology_id not in self.technologies:
                raise ValueError('unknown research technology')
            tech = self.technologies[p.technology_id]
            if p.completed_units > tech.required_units or (p.stage == 'completed') != (p.completed_units == tech.required_units):
                raise ValueError('invalid research progress')
            if p.last_work_day is not None and (p.last_work_day <= p.started_day or p.last_work_day % 30):
                raise ValueError('invalid research work date')
            if p.stage not in {'completed', 'superseded'}:
                if p.owner_ref in owners or p.researcher_id in researchers:
                    raise ValueError('concurrent research contract')
                owners.add(p.owner_ref); researchers.add(p.researcher_id)
            if world is None:
                continue
            validate_actor(world, p.owner_ref)
            if (p.site_id not in world.map.infrastructure_sites or p.stock_id not in world.economy.stocks
                    or p.account_id not in world.economy.accounts or p.researcher_id not in world.society.characters
                    or p.started_day > world.clock.absolute_day
                    or (p.last_work_day is not None and p.last_work_day > world.clock.absolute_day)):
                raise ValueError('invalid research references or dates')
            terms = research_terms(p)
            for eid, action, actor in ((p.sponsor_decision_id, 'research', p.owner_ref),
                    (p.researcher_decision_id, 'research_work', EntityRef('character', p.researcher_id))):
                decision = events.get(eid)
                if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != p.started_day
                        or decision.decision != {**terms, 'action': action, 'actor_ref': actor.to_dict()}):
                    raise ValueError('research requires both contract receipts')
            event = events.get(p.last_event_id)
            if event is None:
                raise ValueError('missing research receipt')
            if p.last_work_day is None:
                if (p.completed_units or p.stage != 'waiting' or event.event_type != 'research_started'
                        or event.day != p.started_day
                        or not any(d.owner_kind == 'research' and d.owner_id == p.id and d.aspect == 'stage'
                                   and d.before == 'None' and d.after == 'waiting' for d in event.deltas)
                        or not {p.sponsor_decision_id, p.researcher_decision_id}.issubset(
                            link.cause_event_id for link in event.causal_links)):
                    raise ValueError('invalid initial research receipt')
            elif (event.day != p.last_work_day or event.event_type != 'research_progressed'
                  or not any(d.owner_kind == 'research' and d.owner_id == p.id and d.aspect == 'stage'
                             and d.after == p.stage for d in event.deltas)
                  or not any(d.owner_kind == 'research' and d.owner_id == p.id and d.aspect == 'completed_units'
                             and d.after == str(p.completed_units) for d in event.deltas)):
                raise ValueError('research progress requires a material receipt')
        if world is not None:
            for tech in self.technologies.values():
                if set(tech.inputs) - set(world.economy.resources):
                    raise ValueError('unknown research material')
