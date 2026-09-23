"""Material construction state; stock, money and people retain their owners."""

from typing import Literal
from src.classes.event import FactKind
from pydantic import model_validator
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count, Occupation
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
    stock_capacity_gain: Count = 0
    worker_occupation: Occupation = "artisan"
    required_technology_id: Identity | None = None
    from_recipe_id: Identity | None = None
    to_recipe_id: Identity | None = None
    additional_recipe_id: Identity | None = None
    # A foundation opens the site's first line for this recipe. It has no
    # anchor facility to modify, so it names the site's own capability and the
    # capacity the finished line starts with.
    foundation_recipe_id: Identity | None = None
    # A construction raises a new site on ground the Map already declares. It
    # grants exactly the authored capability below and nothing else.
    site_kind: Identity | None = None
    grants_capability_id: Identity | None = None
    new_capacity: Positive | None = None
    required_site_capabilities: tuple[Identity, ...] = ()

    @model_validator(mode='after')
    def valid_application(self):
        if len(set(self.required_site_capabilities)) != len(self.required_site_capabilities):
            raise ValueError('site capabilities must be unique')
        if any(not capability.strip() for capability in self.required_site_capabilities):
            raise ValueError('site capabilities must be non-empty')
        if bool(self.site_kind) != bool(self.grants_capability_id):
            raise ValueError('a construction requires its site kind and granted capability')
        if self.grants_capability_id and (self.foundation_recipe_id or self.additional_recipe_id
                                          or self.from_recipe_id or self.to_recipe_id
                                          or self.capacity_gain or self.stock_capacity_gain):
            raise ValueError('a construction raises a site and never touches a line')
        if self.foundation_recipe_id and self.additional_recipe_id:
            raise ValueError('a blueprint founds a line or extends an anchor, never both')
        if self.foundation_recipe_id and (self.from_recipe_id or self.to_recipe_id
                                          or self.capacity_gain or self.stock_capacity_gain):
            raise ValueError('a foundation cannot also modify an anchor facility')
        if self.foundation_recipe_id and not self.new_capacity:
            raise ValueError('a foundation requires positive starting capacity')
        if not self.foundation_recipe_id and bool(self.additional_recipe_id) != bool(self.new_capacity):
            raise ValueError('new line requires its recipe and positive capacity')
        if self.additional_recipe_id and (self.from_recipe_id or self.to_recipe_id or self.capacity_gain or not self.required_technology_id):
            raise ValueError('new line requires knowledge and cannot also modify its anchor')
        if bool(self.from_recipe_id) != bool(self.to_recipe_id) or not (
                self.capacity_gain or self.stock_capacity_gain or self.to_recipe_id
                or self.additional_recipe_id or self.foundation_recipe_id or self.grants_capability_id):
            raise ValueError('expansion must change capacity or a complete recipe pair')
        if self.to_recipe_id and (self.to_recipe_id == self.from_recipe_id or not self.required_technology_id):
            raise ValueError('technical adaptation requires a new recipe and knowledge')
        return self


class ExpansionProject(SocietyValue):
    id: Identity
    # An ordinary expansion modifies an anchor facility. A foundation has none
    # yet, so it carries the material terms the anchor would have supplied:
    # the site it builds on and the owner's local stock and payroll account.
    facility_id: Identity | None = None
    site_id: Identity | None = None
    stock_id: Identity | None = None
    account_id: Identity | None = None
    # A construction has no site yet: it names the settlement it builds in and
    # the id the Map will register when the works finish.
    settlement_id: Identity | None = None
    new_site_id: Identity | None = None
    blueprint_id: Identity
    owner_ref: EntityRef
    decision_event_id: Identity
    started_day: Count
    completed_units: Count = 0
    last_work_day: Count | None = None
    stage: Literal['waiting', 'building', 'blocked', 'completed'] = 'waiting'
    blocker: Identity | None = None
    last_event_id: Identity


def foundation_line_id(site_id, recipe_id):
    """A founded line shares the anchor naming so a site keeps one per recipe."""
    return f'line:{site_id}:{recipe_id}'


def validate_expansions(economy, world=None):
    active = set()
    events = world.event_index() if world is not None else {}
    for blueprint in economy.expansion_blueprints.values():
        if not blueprint.inputs or set(blueprint.inputs) - set(economy.resources):
            raise ValueError('expansion requires known materials')
        if any(r and r not in economy.recipes for r in (blueprint.from_recipe_id, blueprint.to_recipe_id,
                                                        blueprint.additional_recipe_id, blueprint.foundation_recipe_id)):
            raise ValueError('unknown application recipe')
        if world is not None and blueprint.required_technology_id and blueprint.required_technology_id not in world.research.technologies:
            raise ValueError('unknown application technology')
    for project in economy.expansions.values():
        if project.blueprint_id not in economy.expansion_blueprints:
            raise ValueError('unknown expansion target or blueprint')
        blueprint = economy.expansion_blueprints[project.blueprint_id]
        founding = blueprint.foundation_recipe_id is not None
        constructing = blueprint.grants_capability_id is not None
        # Only a foundation or a construction may lack an anchor facility, and
        # each must instead name every material term the anchor would give.
        if not (founding or constructing) and project.facility_id not in economy.facilities:
            raise ValueError('unknown expansion target or blueprint')
        if constructing:
            if (project.facility_id is not None or project.site_id is not None
                    or project.new_site_id is None or project.settlement_id is None
                    or project.stock_id not in economy.stocks or project.account_id not in economy.accounts):
                raise ValueError('construction requires its own settlement, stock and account')
            if world is not None and project.settlement_id not in world.society.settlements:
                raise ValueError('construction requires a known settlement')
            if project.stage == 'completed':
                if world is None or project.new_site_id not in world.map.infrastructure_sites:
                    if world is not None:
                        raise ValueError('completed construction requires its commissioned site')
                elif blueprint.grants_capability_id not in world.map.infrastructure_sites[
                        project.new_site_id].capability_ids:
                    raise ValueError('a commissioned site must carry its authored capability')
            elif world is not None and project.new_site_id in world.map.infrastructure_sites:
                raise ValueError('construction target already exists')
        if founding:
            if (project.facility_id is not None or project.site_id is None
                    or project.stock_id not in economy.stocks or project.account_id not in economy.accounts):
                raise ValueError('foundation requires its own site, stock and account')
            if world is not None and project.site_id not in world.map.infrastructure_sites:
                raise ValueError('foundation requires a known site')
        target_key = (project.new_site_id if constructing else
                      foundation_line_id(project.site_id, blueprint.foundation_recipe_id) if founding else
                      project.facility_id)
        if project.completed_units > blueprint.required_units or (project.stage == 'completed') != (project.completed_units == blueprint.required_units):
            raise ValueError('invalid expansion progress')
        if project.last_work_day is not None and (project.last_work_day <= project.started_day or project.last_work_day % 30):
            raise ValueError('construction must take time')
        if project.stage != 'completed':
            if target_key in active:
                raise ValueError('concurrent expansion of a facility')
            active.add(target_key)
        if project.stage == 'completed' and (blueprint.additional_recipe_id or founding):
            created_id = (target_key if founding else
                          f'line:{economy.facilities[project.facility_id].site_id}:{blueprint.additional_recipe_id}')
            if created_id not in economy.facilities:
                raise ValueError('completed construction requires its production line')
            if world is not None:
                receipt = events.get(project.last_event_id)
                if receipt is None or not all(any(d.owner_kind == 'production' and d.owner_id == created_id
                        and d.aspect == key and d.after == str(value) for d in receipt.deltas)
                        for key, value in ((
                            'recipe_id', blueprint.foundation_recipe_id if founding else blueprint.additional_recipe_id),
                            ('max_batches', blueprint.new_capacity))):
                    raise ValueError('production line requires its commissioning receipt')
        if world is not None:
            decision = events.get(project.decision_event_id)
            if (project.started_day > world.clock.absolute_day or
                    (project.last_work_day is not None and project.last_work_day > world.clock.absolute_day)
                    or project.last_event_id not in events or decision is None
                    or decision.fact_kind != FactKind.DECISION or decision.day != project.started_day
                    or decision.decision != ({
                        'action': 'construct_site', 'actor_ref': project.owner_ref.to_dict(),
                        'settlement_id': project.settlement_id, 'new_site_id': project.new_site_id,
                        'stock_id': project.stock_id, 'account_id': project.account_id,
                        'blueprint_id': project.blueprint_id} if constructing else {
                        'action': 'found_line', 'actor_ref': project.owner_ref.to_dict(),
                        'site_id': project.site_id, 'stock_id': project.stock_id,
                        'account_id': project.account_id, 'blueprint_id': project.blueprint_id} if founding else {
                        'action': 'expand', 'actor_ref': project.owner_ref.to_dict(),
                        'facility_id': project.facility_id, 'blueprint_id': project.blueprint_id})):
                raise ValueError('invalid expansion provenance')
            event = events[project.last_event_id]
            if project.last_work_day is None:
                started_type = ('site_construction_started' if constructing else
                                'line_foundation_started' if founding else 'expansion_started')
                if (project.completed_units or project.stage != 'waiting'
                        or event.event_type != started_type
                        or event.day != project.started_day
                        or project.decision_event_id not in {link.cause_event_id for link in event.causal_links}):
                    raise ValueError('invalid expansion start receipt')
            elif (event.event_type != 'expansion_progressed' or event.day != project.last_work_day
                  or not any(d.owner_kind == 'expansion' and d.owner_id == project.id
                             and d.aspect == 'completed_units' and d.after == str(project.completed_units) for d in event.deltas)
                  or not any(d.owner_kind == 'expansion' and d.owner_id == project.id
                             and d.aspect == 'stage' and d.after == project.stage for d in event.deltas)):
                raise ValueError('expansion progress requires its material receipt')
