"""Validated economic values, using integer goods and currency units."""

from typing import Annotated, Literal

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
    trade_class: Literal["ordinary", "contraband"]


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


class ProductionPriority(SocietyValue):
    """A durable, actor-selected ordering for one upcoming production cycle.

    The priority contains no production result or resource quantity.  Economy
    owns the intent and revalidates its causal decision before using it at a
    later monthly boundary.
    """

    id: Identity
    owner_ref: EntityRef
    payroll_account_id: Identity
    settlement_id: Identity
    occupation: Occupation
    facility_id: Identity
    effective_day: Count
    decision_event_id: Identity
    selected_affordance_id: Identity
    last_event_id: Identity


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


class PermanentEmploymentContract(SocietyValue):
    """A standing, local paid-work obligation owned by Economy.

    This deliberately names one existing cohort rather than creating labour,
    income, or a population transfer.  It is an obligation to attempt a real
    payroll each monthly boundary; a missing account balance or unavailable
    workers produces a factual non-payment receipt instead of money.
    """

    id: Identity
    employer_ref: EntityRef
    settlement_id: Identity
    cohort_id: Identity
    work_site_id: Identity
    occupation: Occupation
    stock_id: Identity
    account_id: Identity
    workforce_limit: Positive
    wage_per_worker: Positive
    created_day: Count
    decision_event_id: Identity
    selected_affordance_id: Identity
    created_event_id: Identity
    last_reviewed_day: Count
    last_outcome: Literal["created", "paid", "unpaid_funds", "unpaid_labor", "unavailable"] = "created"
    last_event_id: Identity

    @model_validator(mode="after")
    def names_its_cohort(self):
        if self.id != f"employment:{self.cohort_id}":
            raise ValueError("employment contract ID must name its cohort")
        if self.last_reviewed_day < self.created_day:
            raise ValueError("employment contract review predates creation")
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
    # Canonical, public readings used to derive the quote.  These are not
    # hidden inventories: they describe the most recent local pressure that
    # an actor may inspect before selecting a material affordance.
    observed_supply: dict[Identity, Count] = Field(default_factory=dict)
    observed_demand: dict[Identity, Count] = Field(default_factory=dict)
    updated_day: Count = 0
    last_event_id: Identity | None = None


class FreightRecoveryCase(SocietyValue):
    """Persistent bilateral record for one already-paid blocked purchase.

    The route affordance itself is deliberately absent.  The request stores
    only the selected transient ID and the causal receipts needed to
    reconstruct and audit the case after save/load.
    """

    id: Identity
    order_id: Identity
    source_id: Identity
    destination_id: Identity
    resource_id: Identity
    quantity: Positive
    buyer_ref: EntityRef
    seller_ref: EntityRef
    buy_decision_id: Identity
    sell_decision_id: Identity
    payment_event_id: Identity
    original_freight_event_id: Identity
    original_parcel_id: Identity
    blocked_event_ids: tuple[Identity, ...]
    requested_option_id: Identity
    request_decision_id: Identity
    status: Literal["requested", "rejected", "completed"]
    response_decision_id: Identity | None = None
    successor_order_id: Identity | None = None
    resolution_event_id: Identity | None = None
    last_event_id: Identity | None = None

    @model_validator(mode="after")
    def valid_lifecycle(self):
        if self.id != f"purchase-recovery:{self.order_id}:{self.request_decision_id}":
            raise ValueError("freight recovery case ID must name its request")
        if not self.blocked_event_ids or len(set(self.blocked_event_ids)) != len(self.blocked_event_ids):
            raise ValueError("freight recovery case requires unique blockage evidence")
        if self.status == "requested" and any(
                value is not None for value in (self.response_decision_id, self.successor_order_id,
                                                self.resolution_event_id)):
            raise ValueError("open freight recovery case cannot have a response or successor")
        if self.status == "rejected" and (self.response_decision_id is None or
                                          self.successor_order_id is not None or self.resolution_event_id is not None):
            raise ValueError("rejected freight recovery case has invalid lifecycle")
        if self.status == "completed" and (self.response_decision_id is None or
                                            self.successor_order_id is None or self.resolution_event_id is None):
            raise ValueError("completed freight recovery case has incomplete lifecycle")
        return self
