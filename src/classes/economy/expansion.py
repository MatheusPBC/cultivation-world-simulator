"""Material construction state; stock, money and people retain their owners."""

from typing import Literal
from src.classes.event import FactKind
from pydantic import model_validator
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count
from .models import Positive


class ExpansionBlueprint(SocietyValue):
    id: Identity
    name: Identity
    inputs: dict[Identity, Positive]
    workers_per_unit: Positive
    wage_per_worker: Positive
    required_units: Positive
    monthly_units: Positive
    capacity_gain: Count
    required_technology_id: Identity | None = None
    from_recipe_id: Identity | None = None
    to_recipe_id: Identity | None = None
    additional_recipe_id: Identity | None = None
    new_capacity: Positive | None = None

    @model_validator(mode='after')
    def valid_application(self):
        if bool(self.additional_recipe_id) != bool(self.new_capacity):
            raise ValueError('new line requires its recipe and positive capacity')
        if self.additional_recipe_id and (self.from_recipe_id or self.to_recipe_id or self.capacity_gain or not self.required_technology_id):
            raise ValueError('new line requires knowledge and cannot also modify its anchor')
        if bool(self.from_recipe_id) != bool(self.to_recipe_id) or not (self.capacity_gain or self.to_recipe_id or self.additional_recipe_id):
            raise ValueError('expansion must change capacity or a complete recipe pair')
        if self.to_recipe_id and (self.to_recipe_id == self.from_recipe_id or not self.required_technology_id):
            raise ValueError('technical adaptation requires a new recipe and knowledge')
        return self


class ExpansionProject(SocietyValue):
    id: Identity
    facility_id: Identity
    blueprint_id: Identity
    owner_ref: EntityRef
    decision_event_id: Identity
    started_day: Count
    completed_units: Count = 0
    last_work_day: Count | None = None
    stage: Literal['waiting', 'building', 'blocked', 'completed'] = 'waiting'
    blocker: Identity | None = None
    last_event_id: Identity


def validate_expansions(economy, world=None):
    active = set()
    events = {e.id: e for e in world.events} if world is not None else {}
    for blueprint in economy.expansion_blueprints.values():
        if not blueprint.inputs or set(blueprint.inputs) - set(economy.resources):
            raise ValueError('expansion requires known materials')
        if any(r and r not in economy.recipes for r in (blueprint.from_recipe_id, blueprint.to_recipe_id, blueprint.additional_recipe_id)):
            raise ValueError('unknown application recipe')
        if world is not None and blueprint.required_technology_id and blueprint.required_technology_id not in world.research.technologies:
            raise ValueError('unknown application technology')
    for project in economy.expansions.values():
        if project.facility_id not in economy.facilities or project.blueprint_id not in economy.expansion_blueprints:
            raise ValueError('unknown expansion target or blueprint')
        blueprint = economy.expansion_blueprints[project.blueprint_id]
        if project.completed_units > blueprint.required_units or (project.stage == 'completed') != (project.completed_units == blueprint.required_units):
            raise ValueError('invalid expansion progress')
        if project.last_work_day is not None and (project.last_work_day <= project.started_day or project.last_work_day % 30):
            raise ValueError('construction must take time')
        if project.stage != 'completed':
            if project.facility_id in active:
                raise ValueError('concurrent expansion of a facility')
            active.add(project.facility_id)
        if project.stage == 'completed' and blueprint.additional_recipe_id:
            parent = economy.facilities[project.facility_id]
            created_id = f'line:{parent.site_id}:{blueprint.additional_recipe_id}'
            if created_id not in economy.facilities:
                raise ValueError('completed construction requires its production line')
            if world is not None:
                receipt = events.get(project.last_event_id)
                if receipt is None or not all(any(d.owner_kind == 'production' and d.owner_id == created_id
                        and d.aspect == key and d.after == str(value) for d in receipt.deltas)
                        for key, value in (('recipe_id', blueprint.additional_recipe_id), ('max_batches', blueprint.new_capacity))):
                    raise ValueError('production line requires its commissioning receipt')
        if world is not None:
            decision = events.get(project.decision_event_id)
            if (project.started_day > world.clock.absolute_day or
                    (project.last_work_day is not None and project.last_work_day > world.clock.absolute_day)
                    or project.last_event_id not in events or decision is None
                    or decision.fact_kind != FactKind.DECISION or decision.day != project.started_day or decision.decision != {
                        'action': 'expand', 'actor_ref': project.owner_ref.to_dict(),
                        'facility_id': project.facility_id, 'blueprint_id': project.blueprint_id}):
                raise ValueError('invalid expansion provenance')
            event = events[project.last_event_id]
            if project.last_work_day is None:
                if (project.completed_units or project.stage != 'waiting' or event.event_type != 'expansion_started'
                        or event.day != project.started_day
                        or project.decision_event_id not in {link.cause_event_id for link in event.causal_links}):
                    raise ValueError('invalid expansion start receipt')
            elif (event.event_type != 'expansion_progressed' or event.day != project.last_work_day
                  or not any(d.owner_kind == 'expansion' and d.owner_id == project.id
                             and d.aspect == 'completed_units' and d.after == str(project.completed_units) for d in event.deltas)
                  or not any(d.owner_kind == 'expansion' and d.owner_id == project.id
                             and d.aspect == 'stage' and d.after == project.stage for d in event.deltas)):
                raise ValueError('expansion progress requires its material receipt')
