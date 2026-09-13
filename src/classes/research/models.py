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
    channel: Literal['research', 'teaching']
    event_id: Identity


def research_terms(project):
    return {key: getattr(project, key) for key in ('technology_id', 'site_id', 'stock_id', 'account_id', 'researcher_id')}
