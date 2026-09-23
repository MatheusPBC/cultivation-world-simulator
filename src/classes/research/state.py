from dataclasses import dataclass, field
from src.classes.event import FactKind
from src.classes.governance.serialization import RegistrySerialization, validate_actor
from src.classes.mechanical_language import EntityRef
from .models import (Apprenticeship, Rite, RiteBlueprint, RiteRecovery, TechniqueCopy, Technology,
                     ResearchProject, Ward, research_terms)


@dataclass
class ResearchState(RegistrySerialization):
    technologies: dict[str, Technology] = field(default_factory=dict)
    projects: dict[str, ResearchProject] = field(default_factory=dict)
    apprenticeships: dict[str, Apprenticeship] = field(default_factory=dict)
    rite_blueprints: dict[str, RiteBlueprint] = field(default_factory=dict)
    rites: dict[str, Rite] = field(default_factory=dict)
    wards: dict[str, Ward] = field(default_factory=dict)
    rite_recoveries: dict[str, RiteRecovery] = field(default_factory=dict)
    technique_copies: dict[str, TechniqueCopy] = field(default_factory=dict)
    registries = {'technologies': Technology, 'projects': ResearchProject,
                  'apprenticeships': Apprenticeship, 'rite_blueprints': RiteBlueprint, 'rites': Rite,
                  'wards': Ward, 'rite_recoveries': RiteRecovery, 'technique_copies': TechniqueCopy}
    schema_version = 3

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
        events = world.event_index() if world is not None else {}
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
        specialists = set()
        for a in self.apprenticeships.values():
            if (a.technology_id not in self.technologies or a.due_day <= a.started_day
                    or (a.stage == 'training' and a.specialist_id in specialists)):
                raise ValueError('invalid apprenticeship contract')
            if a.stage == 'training':
                specialists.add(a.specialist_id)
            if world is None:
                continue
            validate_actor(world, a.host_ref)
            if (a.site_id not in world.map.infrastructure_sites or a.stock_id not in world.economy.stocks
                    or a.account_id not in world.economy.accounts
                    or a.specialist_id not in world.society.characters
                    or a.started_day > world.clock.absolute_day
                    or world.economy.stocks[a.stock_id].owner_ref != a.host_ref
                    or world.economy.accounts[a.account_id].owner_ref != a.host_ref):
                raise ValueError('invalid apprenticeship references')
            scheduled = world.agenda.get(a.id)
            if a.stage == 'training' and (scheduled is None or scheduled.kind != 'apprenticeship'
                                          or scheduled.due_day != a.due_day):
                raise ValueError('apprenticeship requires its own dated completion')
            if a.stage != 'training' and scheduled is not None:
                raise ValueError('a concluded apprenticeship cannot stay on the agenda')
            for eid, actor in ((a.specialist_decision_id, EntityRef('character', a.specialist_id)),
                               (a.sponsor_decision_id, a.host_ref)):
                decision = events.get(eid)
                if (decision is None or decision.fact_kind != FactKind.DECISION
                        or decision.day != a.started_day
                        or (decision.decision or {}).get('actor_ref') != actor.to_dict()):
                    raise ValueError('apprenticeship requires both current contract receipts')
            event = events.get(a.last_event_id)
            expected = {'training': 'apprenticeship_started', 'completed': 'apprenticeship_completed',
                        'failed': 'apprenticeship_failed'}[a.stage]
            if (event is None or event.event_type != expected
                    or not any(d.owner_kind == 'apprenticeship' and d.owner_id == a.id and d.aspect == 'stage'
                               and d.after == a.stage for d in event.deltas)):
                raise ValueError('apprenticeship requires its own stage receipt')
            if a.stage == 'training' and (event.day != a.started_day
                                          or not {a.specialist_decision_id, a.sponsor_decision_id}.issubset(
                                              link.cause_event_id for link in event.causal_links)):
                raise ValueError('apprenticeship requires its own start receipt')
        officiants = set()
        for rite in self.rites.values():
            blueprint = self.rite_blueprints.get(rite.blueprint_id)
            if (blueprint is None or rite.due_day <= rite.started_day
                    or (rite.stage == 'officiating' and rite.officiant_id in officiants)):
                raise ValueError('invalid rite contract')
            if rite.stage == 'officiating':
                officiants.add(rite.officiant_id)
            if world is None:
                continue
            validate_actor(world, rite.sponsor_ref)
            stock = world.economy.stocks.get(rite.stock_id)
            account = world.economy.accounts.get(rite.account_id)
            if (rite.site_id not in world.map.infrastructure_sites or stock is None or account is None
                    or rite.officiant_id not in world.society.characters
                    or rite.settlement_id not in world.society.settlements
                    or rite.started_day > world.clock.absolute_day
                    or stock.owner_ref != rite.sponsor_ref or account.owner_ref != rite.sponsor_ref
                    or stock.location_id != rite.settlement_id):
                raise ValueError('invalid rite references')
            scheduled = world.agenda.get(rite.id)
            if rite.stage == 'officiating' and (scheduled is None or scheduled.kind != 'rite'
                                                or scheduled.due_day != rite.due_day):
                raise ValueError('a rite in progress requires its dated resolution')
            if rite.stage != 'officiating' and scheduled is not None:
                raise ValueError('a concluded rite cannot stay on the agenda')
            for eid, actor, accepted_days in (
                    (rite.officiant_decision_id, EntityRef('character', rite.officiant_id),
                     {rite.started_day - 1, rite.started_day}),
                    (rite.sponsor_decision_id, rite.sponsor_ref, {rite.started_day}),
            ):
                decision = events.get(eid)
                if (decision is None or decision.fact_kind != FactKind.DECISION
                        or decision.day not in accepted_days
                        or (decision.decision or {}).get('actor_ref') != actor.to_dict()):
                    raise ValueError('rite requires both current contract receipts')
            event = events.get(rite.last_event_id)
            expected = {'officiating': 'rite_started', 'completed': 'rite_completed',
                        'failed': 'rite_failed', 'interrupted': 'rite_interrupted'}[rite.stage]
            if (event is None or event.event_type != expected
                    or not any(d.owner_kind == 'rite' and d.owner_id == rite.id and d.aspect == 'stage'
                               and d.after == rite.stage for d in event.deltas)):
                raise ValueError('rite requires its own stage receipt')
            if rite.stage == 'interrupted' and not any(
                    events.get(link.cause_event_id) is not None
                    and events[link.cause_event_id].event_type == 'assembly_denied'
                    for link in event.causal_links):
                raise ValueError('interrupted rite requires a factual assembly denial')
        for copy in self.technique_copies.values():
            if copy.technology_id not in self.technologies:
                raise ValueError('technique copy requires a catalogued technique')
            if world is None:
                continue
            validate_actor(world, copy.actor_ref)
            validate_actor(world, copy.holder_ref)
            decision = events.get(copy.decision_event_id)
            event = events.get(copy.last_event_id)
            scheduled = world.agenda.get(copy.id)
            if (copy.site_id not in world.map.infrastructure_sites
                    or copy.stock_id not in world.economy.stocks
                    or copy.account_id not in world.economy.accounts
                    or copy.started_day > world.clock.absolute_day or event is None
                    or decision is None or decision.fact_kind != FactKind.DECISION
                    or decision.day != copy.started_day or decision.decision is None
                    or decision.decision.get('action') != 'copy_technique'
                    or decision.decision.get('actor_ref') != copy.actor_ref.to_dict()
                    or set(decision.decision) != {'action', 'actor_ref', 'selected_affordance_id'}):
                raise ValueError('technique copy requires its own current decision')
            access_event = events.get(copy.access_event_id)
            if access_event is None:
                raise ValueError('technique copy requires its factual work-access receipt')
            if copy.access_kind == 'repair':
                access = world.economy.repairs.get(copy.access_id)
                if (access is None or access.site_id != copy.site_id
                        or access.maintainer_ref != copy.actor_ref):
                    raise ValueError('technique copy repair access is inconsistent')
                def precedes_repair(event_id, seen=frozenset()):
                    if event_id in seen:
                        return False
                    candidate = events.get(event_id)
                    if candidate is None:
                        return False
                    if (candidate.event_type == 'repair_progressed'
                            and any(delta.owner_kind == 'repair' and delta.owner_id == copy.access_id
                                    for delta in candidate.deltas)):
                        return True
                    return any(precedes_repair(link.cause_event_id, seen | {event_id})
                               for link in candidate.causal_links)
                if (access_event.day != copy.started_day
                        or access_event.event_type not in {'wages_paid', 'income_tax_collected'}
                        or not precedes_repair(copy.access_event_id)):
                    raise ValueError('technique copy repair access lacks its paid local work receipt')
            elif copy.access_kind == 'apprenticeship':
                access = self.apprenticeships.get(copy.access_id)
                if (access is None or access.site_id != copy.site_id
                        or access.host_ref != copy.actor_ref):
                    raise ValueError('technique copy apprenticeship access is inconsistent')
                if (access_event.event_type != 'apprenticeship_started'
                        or not any(delta.owner_kind == 'apprenticeship' and delta.owner_id == copy.access_id
                                   and delta.aspect == 'stage' and delta.after == 'training'
                                   for delta in access_event.deltas)):
                    raise ValueError('technique copy apprenticeship access lacks its start receipt')
            if copy.stage == 'copying':
                if (scheduled is None or scheduled.kind != 'technique_copy'
                        or scheduled.due_day != copy.due_day or copy.due_day <= world.clock.absolute_day):
                    raise ValueError('an open technique copy requires its dated conclusion')
            elif scheduled is not None or event.event_type != f'technique_copy_{copy.stage}':
                raise ValueError('a concluded technique copy lacks its own receipt')
        for ward in self.wards.values():
            rite = self.rites.get(ward.rite_id)
            blueprint = self.rite_blueprints.get(rite.blueprint_id) if rite is not None else None
            if (rite is None or blueprint is None or blueprint.kind != 'ward' or rite.stage != 'completed'
                    or ward.settlement_id != rite.settlement_id or ward.sponsor_ref != rite.sponsor_ref
                    or ward.until_day != ward.started_day + blueprint.ward_days):
                raise ValueError('a ward requires its own completed ward rite')
            if world is not None:
                event = events.get(ward.last_event_id)
                if (ward.settlement_id not in world.society.settlements or event is None
                        or not any(d.owner_kind == 'ward' and d.owner_id == ward.id and d.aspect == 'until_day'
                                   and d.after == str(ward.until_day) for d in event.deltas)):
                    raise ValueError('a ward requires its factual receipt')
        for recovery in self.rite_recoveries.values():
            rite = self.rites.get(recovery.rite_id)
            if rite is None or rite.officiant_id != recovery.character_id or rite.stage == 'officiating':
                raise ValueError('recovery requires its own concluded rite')
            if world is not None and recovery.character_id not in world.society.characters:
                raise ValueError('recovery requires an existing person')
        for rite in self.rites.values():
            blueprint = self.rite_blueprints[rite.blueprint_id]
            if (blueprint.reach == 'adjacent') != (rite.target_settlement_id is not None):
                raise ValueError('rite reach and target disagree')
            if world is not None and rite.target_settlement_id is not None and (
                    rite.target_settlement_id not in world.society.settlements
                    or rite.route_id not in world.map.routes):
                raise ValueError('a ranged rite requires an existing target and segment')
        if world is not None:
            for tech in self.technologies.values():
                if set(tech.inputs) - set(world.economy.resources):
                    raise ValueError('unknown research material')
            for blueprint in self.rite_blueprints.values():
                if set(blueprint.inputs) - set(world.economy.resources):
                    raise ValueError('unknown rite material')
            for entry in world.agenda.to_dict():
                if entry['kind'] == 'rite' and entry['id'] not in self.rites:
                    raise ValueError('agenda references a missing rite')
                if entry['kind'] == 'rite_interruption' and entry['id'] not in world.society.assembly_denials:
                    raise ValueError('agenda references a missing assembly denial')
            for entry in world.agenda.to_dict():
                if entry['kind'] == 'apprenticeship' and entry['id'] not in self.apprenticeships:
                    raise ValueError('agenda references a missing apprenticeship')
