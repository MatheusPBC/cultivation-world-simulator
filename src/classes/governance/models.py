"""Intent and authority values contain no material inventories."""

import json
from typing import Annotated, Literal
from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count

Permille = Annotated[int, Field(strict=True, ge=0, le=1000)]


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
    export_rate_permille: Permille = 0
    export_policy_event_id: Identity | None = None
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
    export_rate_permille: Permille
    export_policy_event_id: Identity | None
    export_collector_ref: EntityRef | None
    event_id: Identity


def route_observation(route_id, publisher_ref, observed_day, operational_capacity, travel_days) -> str:
    """Canonical wire shape of one observation, shared by receipts and validation.

    It carries route, observer, date and observed runtime values, so a receipt
    is checkable on its own and cannot be confused with another actor's.
    """
    return json.dumps({"route_id": route_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "operational_capacity": float(operational_capacity),
                       "travel_days": travel_days},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class RouteReport(SocietyValue):
    """Dated observation of one route's operability; Map remains its only owner.

    Topology, mode and allowed resources are public identity read from the Map.
    Capacity and travel time are only known through a dated observation.
    """
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    route_id: Identity
    observed_day: Count
    operational_capacity: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
    travel_days: Annotated[int, Field(strict=True, ge=1)] | None = None
    channel: Literal["administrative_route_report", "route_bulletin"]
    event_id: Identity

    @model_validator(mode="after")
    def valid_observation(self):
        if self.travel_days is not None and self.operational_capacity <= 0:
            raise ValueError("a passable observation requires positive operational capacity")
        return self

    def observation(self) -> str:
        return route_observation(self.route_id, self.publisher_ref, self.observed_day,
                                 self.operational_capacity, self.travel_days)


def settlement_observation(settlement_id, publisher_ref, observed_day, population, present_population, housing_capacity,
                           health, missing_food, unrest) -> str:
    """Stable historical shape for public, aggregate settlement conditions."""
    return json.dumps({"settlement_id": settlement_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "population": population, "present_population": present_population,
                       "housing_capacity": housing_capacity, "health": health,
                       "missing_food": missing_food, "unrest": unrest},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class SettlementReport(SocietyValue):
    """Dated public aggregate observation; it never discloses a stock or balance."""
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    settlement_id: Identity
    observed_day: Count
    population: Count
    present_population: Count
    housing_capacity: Count
    health: Permille
    missing_food: Count
    unrest: Permille
    event_id: Identity
    channel: Literal["local_settlement_report", "settlement_bulletin"]

    def observation(self) -> str:
        return settlement_observation(self.settlement_id, self.publisher_ref, self.observed_day,
                                      self.population, self.present_population, self.housing_capacity, self.health,
                                      self.missing_food, self.unrest)


def site_observation(site_id, publisher_ref, observed_day, integrity, enabled, service_suspended) -> str:
    """Wire shape of one site observation, shared by receipts and validation."""
    return json.dumps({"site_id": site_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "integrity": float(integrity), "enabled": bool(enabled),
                       "service_suspended": bool(service_suspended)},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class SiteReport(SocietyValue):
    """Dated local observation of an installation by an authorized local observer.

    Private installations are never broadcast: this channel only exists for a
    owner or maintainer that has verifiable presence where the site is.
    """
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    site_id: Identity
    observed_day: Count
    integrity: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
    enabled: bool
    service_suspended: bool
    channel: Literal["administrative_site_report"] = "administrative_site_report"
    event_id: Identity

    def observation(self) -> str:
        return site_observation(self.site_id, self.publisher_ref, self.observed_day, self.integrity, self.enabled,
                                self.service_suspended)


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
