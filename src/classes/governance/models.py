"""Intent and authority values contain no material inventories."""

from typing import Literal
from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count
from src.classes.economy.models import Permille


class AuthorityOffice(SocietyValue):
    id: Identity
    institution_ref: EntityRef
    holder_ref: EntityRef
    scopes: tuple[Literal["trade", "supply", "taxation", "research", "diplomacy"], ...]
    starts_day: Count = 0
    ends_day: Count | None = None

    @model_validator(mode="after")
    def valid_term(self):
        if not self.scopes or len(set(self.scopes)) != len(self.scopes):
            raise ValueError("office requires unique authority scopes")
        if self.ends_day is not None and self.ends_day < self.starts_day:
            raise ValueError("office cannot end before it starts")
        return self


class TaxPolicy(SocietyValue):
    id: Identity  # polity ID
    account_id: Identity
    income_rate: Permille = 100
    last_event_id: Identity | None = None


class KnowledgeReport(SocietyValue):
    """Dated inventory observation or advertised offer; never a material owner."""
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    stock_id: Identity
    resource_id: Identity
    kind: Literal["inventory", "offer"]
    channel: Literal["administrative_report", "market_bulletin"]
    observed_day: Count
    quantity: Count
    population: Count
    unit_price: int = Field(strict=True, gt=0)
    quote_day: Count
    event_id: Identity


class DiplomaticNotice(SocietyValue):
    id: Identity
    proposal_id: Identity
    recipient_ref: EntityRef
    event_id: Identity
    learned_day: Count
    channel: Literal['direct_diplomacy'] = 'direct_diplomacy'


class Objective(SocietyValue):
    id: Identity
    actor_ref: EntityRef
    settlement_id: Identity
    stock_id: Identity
    resource_id: Identity = "food"
    kind: Literal["maintain_food_reserve", "maintain_production_inputs"] = "maintain_food_reserve"
    reserve_months: int = Field(default=2, strict=True, ge=1, le=12)
    motivation: Identity = "Proteger o abastecimento dos habitantes."


class StrategicPlan(SocietyValue):
    id: Identity
    objective_id: Identity
    stage: Literal["acquire", "await_delivery", "satisfied", "blocked"]
    order_ids: tuple[Identity, ...] = ()
    blocker: Identity | None = None
    last_review_day: Count
    last_event_id: Identity
