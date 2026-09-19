from typing import Literal
from pydantic import Field, model_validator
from src.classes.society.models import SocietyValue, Identity, Count, Occupation, Skills
from src.classes.economy.models import Positive
from src.classes.mechanical_language import EntityRef


class Technology(SocietyValue):
    id: Identity
    name: Identity
    field: Identity
    prerequisites: tuple[Identity, ...] = ()
    capability_id: Identity
    skill: Identity
    min_skill: int = Field(strict=True, ge=1, le=100)
    required_units: Positive
    monthly_units: Positive
    inputs: dict[Identity, Positive]
    assistant_occupation: Occupation
    assistants_per_unit: Positive
    wage_per_worker: Positive

    @model_validator(mode='after')
    def valid_definition(self):
        if self.skill not in Skills.model_fields or len(set(self.prerequisites)) != len(self.prerequisites):
            raise ValueError('invalid research skill or prerequisites')
        return self


class ResearchProject(SocietyValue):
    id: Identity
    owner_ref: EntityRef
    technology_id: Identity
    site_id: Identity
    stock_id: Identity
    account_id: Identity
    researcher_id: Identity
    sponsor_decision_id: Identity
    researcher_decision_id: Identity
    started_day: Count
    completed_units: Count = 0
    last_work_day: Count | None = None
    stage: Literal['waiting', 'researching', 'blocked', 'completed', 'superseded'] = 'waiting'
    blocker: Identity | None = None
    last_event_id: Identity


class TechnicalKnowledge(SocietyValue):
    id: Identity
    owner_ref: EntityRef
    technology_id: Identity
    learned_day: Count
    channel: Literal['research', 'teaching', 'apprenticeship', 'copied', 'sale', 'stolen']
    event_id: Identity


class RiteBlueprint(SocietyValue):
    """One authored restorative rite. There is no spell language here.

    Every term is material and engine-owned: where it may be performed, who is
    qualified, what it consumes, who is paid, how long it takes and the bounded
    relief it may give. It creates no goods, money, people or capacity.
    """
    id: Identity
    name: Identity
    capability_id: Identity
    skill: Identity
    min_skill: int = Field(strict=True, ge=1, le=100)
    inputs: dict[Identity, Positive]
    assistants: Positive
    assistant_occupation: Occupation
    wage_per_worker: Positive
    days: Positive
    health_gain_permille: int = Field(strict=True, ge=0, le=200)
    # Reach is one existing, currently usable route segment, never a plan.
    reach: Literal['local', 'adjacent'] = 'local'
    kind: Literal['restoration', 'ward'] = 'restoration'
    ward_days: int = Field(strict=True, ge=0, le=360, default=0)
    resistance_capability_id: Identity | None = None

    @model_validator(mode='after')
    def valid_rite(self):
        if self.skill not in Skills.model_fields or not self.inputs:
            raise ValueError('rite requires a known skill and real materials')
        if self.kind == 'ward':
            if (self.reach != 'local' or self.ward_days <= 0 or self.health_gain_permille
                    or not self.resistance_capability_id):
                raise ValueError('a ward protects its own place for a real term and heals nobody')
        elif self.ward_days or self.health_gain_permille < 1 or self.resistance_capability_id is not None:
            raise ValueError('a restoration gives bounded relief and no protection')
        return self

    @property
    def school(self) -> Literal['restoration', 'protection', 'countermeasure']:
        """Engine-owned school; authored kind remains the canonical source.

        Countermeasure profiles are still wards materially, but are exposed as
        a distinct school so observers can distinguish a standing barrier from
        a hazard-specific response without introducing a spell registry.
        """
        if self.kind != 'ward':
            return 'restoration'
        return 'protection' if self.resistance_capability_id == 'standing_ward' else 'countermeasure'

    @property
    def cost(self) -> dict[Identity, Positive]:
        """Material cost owned by the blueprint, never by narrative text."""
        return dict(self.inputs)

    @property
    def range(self) -> Literal['local', 'adjacent']:
        """Engine-enumerated geographic reach of the working."""
        return self.reach

    @property
    def duration_days(self) -> Positive:
        """The one applicable duration: working time or ward term."""
        return self.ward_days if self.kind == 'ward' else self.days


class RiteBlueprintMetadata(SocietyValue):
    """Transient canonical observability of one authored rite blueprint.

    This is a read model, not a second registry or persisted spell state.
    Every value is derived from :class:`RiteBlueprint` by the engine.
    """
    id: Identity
    school: Literal['restoration', 'protection', 'countermeasure']
    cost: dict[Identity, Positive]
    range: Literal['local', 'adjacent']
    duration_days: Positive


class Rite(SocietyValue):
    """A dated rite in progress; its existence is public at the place."""
    id: Identity
    sponsor_ref: EntityRef
    blueprint_id: Identity
    officiant_id: Identity
    site_id: Identity
    settlement_id: Identity
    stock_id: Identity
    account_id: Identity
    started_day: Count
    due_day: Count
    stage: Literal['officiating', 'completed', 'failed', 'interrupted'] = 'officiating'
    # A ranged working names the place it reaches and the one segment it uses.
    target_settlement_id: Identity | None = None
    route_id: Identity | None = None
    sponsor_decision_id: Identity
    officiant_decision_id: Identity
    last_event_id: Identity

    @model_validator(mode='after')
    def valid_reach(self):
        if (self.target_settlement_id is None) != (self.route_id is None):
            raise ValueError('a ranged rite requires both its target and its segment')
        if self.target_settlement_id == self.settlement_id:
            raise ValueError('a ranged rite must reach another place')
        return self


class TechniqueCopy(SocietyValue):
    """Dated, paid work of copying a technique from works one already reaches.

    It is not espionage and holds no agent, document or secret: it names only
    the actor's own sighting, its own site observation and the site whose
    running line already requires the technique. The holder loses nothing.
    """
    id: Identity
    actor_ref: EntityRef
    holder_ref: EntityRef
    technology_id: Identity
    site_id: Identity
    stock_id: Identity
    account_id: Identity
    sighting_event_id: Identity
    report_event_id: Identity
    # The opening day proved work at the site.  A continuing repair or
    # apprenticeship is retained so the later dated resolution can verify
    # that access lasted across a monthly calendar boundary without inventing
    # a second same-day payroll.
    access_kind: Literal['repair', 'apprenticeship']
    access_id: Identity
    access_event_id: Identity
    started_day: Count
    due_day: Count
    stage: Literal['copying', 'completed', 'failed'] = 'copying'
    blocker: Identity | None = None
    decision_event_id: Identity
    last_event_id: Identity

    @model_validator(mode='after')
    def valid_copy(self):
        if (self.id != f'technique-copy:{self.decision_event_id}' or self.due_day <= self.started_day
                or self.actor_ref == self.holder_ref
                or (self.stage == 'failed') != (self.blocker is not None)):
            raise ValueError('technique copy identity, term or outcome is inconsistent')
        return self


class Ward(SocietyValue):
    """Dated protection of one settlement against foreign ranged workings.

    It hurts nobody, blocks no cargo, person, route or authority, and does not
    hinder the local working of whoever raised it.
    """
    id: Identity
    settlement_id: Identity
    sponsor_ref: EntityRef
    rite_id: Identity
    started_day: Count
    until_day: Count
    resistance_capability_id: Identity = 'standing_ward'
    last_event_id: Identity

    @model_validator(mode='after')
    def valid_term(self):
        if self.id != f'ward:{self.rite_id}' or self.until_day <= self.started_day:
            raise ValueError('a ward requires its own rite and a real term')
        return self


class RiteRecovery(SocietyValue):
    """An officiant spent; the cost of a working is time of a real person."""
    id: Identity
    character_id: Identity
    until_day: Count
    rite_id: Identity
    last_event_id: Identity

    @model_validator(mode='after')
    def valid_recovery(self):
        if self.id != self.character_id:
            raise ValueError('recovery is keyed by its own person')
        return self


class Apprenticeship(SocietyValue):
    """A dated, paid instruction contract with a resident named specialist.

    It holds only the commitment: the host institution, the technique already
    in the catalog, the specialist, the local site, and the stock, account and
    cohort that will pay for the instruction. No knowledge exists until the
    dated completion, and the specialist keeps no technique of their own.
    """
    id: Identity
    host_ref: EntityRef
    technology_id: Identity
    specialist_id: Identity
    site_id: Identity
    stock_id: Identity
    account_id: Identity
    workers: Positive
    wage_per_worker: Positive
    started_day: Count
    due_day: Count
    stage: Literal['training', 'completed', 'failed'] = 'training'
    specialist_decision_id: Identity
    sponsor_decision_id: Identity
    last_event_id: Identity


def research_terms(project):
    return {key: getattr(project, key) for key in ('technology_id', 'site_id', 'stock_id', 'account_id', 'researcher_id')}
