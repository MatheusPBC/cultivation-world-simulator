"""Validated economic values, using integer goods and currency units."""

from typing import Annotated

from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, Occupation, SocietyValue

Positive = Annotated[int, Field(strict=True, gt=0)]
Permille = Annotated[int, Field(strict=True, ge=0, le=1000)]


class Resource(SocietyValue):
    id: Identity
    name: Identity
    unit: Identity
    bulk: Positive
    base_price: Positive


class Recipe(SocietyValue):
    id: Identity
    capability_id: Identity
    occupation: Occupation
    workers: Positive
    inputs: dict[Identity, Positive]
    outputs: dict[Identity, Positive]
    required_technology_id: Identity | None = None

    @model_validator(mode="after")
    def require_product(self):
        if not self.outputs:
            raise ValueError("recipe must produce a resource")
        return self


class Stock(SocietyValue):
    id: Identity
    owner_ref: EntityRef
    location_id: Identity
    capacity: Count
    goods: dict[Identity, Count] = Field(default_factory=dict)
    last_event_ids: dict[Identity, Identity] = Field(default_factory=dict)


class MoneyAccount(SocietyValue):
    id: Identity
    owner_ref: EntityRef
    balance: Count
    last_event_id: Identity | None = None


class ProductionFacility(SocietyValue):
    id: Identity
    site_id: Identity
    stock_id: Identity
    recipe_id: Identity
    max_batches: Count
    payroll_account_id: Identity
    wage_per_worker: Positive = 1
    last_batches: Count = 0
    last_limitations: tuple[Identity, ...] = ()
    last_event_id: Identity | None = None


class Payroll(SocietyValue):
    """Last settled period, not an additional balance or workforce owner."""
    id: Identity  # facility ID
    day: Count
    wage_per_worker: Positive
    workers_by_group: dict[Identity, Positive]
    gross: Count
    tax: Count
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_amounts(self):
        if self.gross != sum(self.workers_by_group.values()) * self.wage_per_worker or self.tax > self.gross:
            raise ValueError("inconsistent payroll amounts")
        return self


class SettlementNeeds(SocietyValue):
    id: Identity
    stock_id: Identity
    health: Permille = 1000
    unrest: Permille = 0
    missing_food: Count = 0
    last_event_id: Identity | None = None


class Market(SocietyValue):
    id: Identity  # settlement ID
    prices: dict[Identity, Positive]
    updated_day: Count = 0
    last_event_id: Identity | None = None
