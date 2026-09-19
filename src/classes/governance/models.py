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
    scopes: tuple[Literal["trade", "supply", "taxation", "research", "diplomacy", "military"], ...]
    starts_day: Count = 0
    ends_day: Count | None = None

    @model_validator(mode="after")
    def valid_term(self):
        if not self.scopes or len(set(self.scopes)) != len(self.scopes):
            raise ValueError("office requires unique authority scopes")
        if self.ends_day is not None and self.ends_day < self.starts_day:
            raise ValueError("office cannot end before it starts")
        return self


class AuthorityClaim(SocietyValue):
    """A bounded, factual challenge to an existing office.

    A claim is deliberately not an authority grant.  It is a durable record of
    a polity or organization asserting one office from one enumerated piece of
    evidence; the authority owner continues to answer every material question
    from live offices alone.
    """
    id: Identity
    office_id: Identity
    claimant_ref: EntityRef
    stage: Literal["declared", "withdrawn", "lapsed"] = "declared"
    declared_day: Count
    evidence_kind: Literal["standing_claimant", "unremedied_breach", "held_occupation"]
    evidence_event_id: Identity
    evidence_subject_id: Identity
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_claimant(self):
        if self.claimant_ref.kind not in {"polity", "organization"}:
            raise ValueError("authority claimants must be institutions")
        return self


class AuthorityRecognition(SocietyValue):
    """One non-party institution's current recognition of a known claim."""
    id: Identity
    claim_id: Identity
    recognizer_ref: EntityRef
    stage: Literal["recognized", "withdrawn", "lapsed"] = "recognized"
    declared_day: Count
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_recognizer(self):
        if self.recognizer_ref.kind not in {"polity", "organization"}:
            raise ValueError("authority recognizers must be institutions")
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


def route_observation(route_id, publisher_ref, observed_day, operational_capacity, travel_days,
                      daily_flow_bulk=0) -> str:
    """Canonical wire shape of one observation, shared by receipts and validation.

    It carries route, observer, date and observed runtime values, so a receipt
    is checkable on its own and cannot be confused with another actor's.
    """
    return json.dumps({"route_id": route_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "operational_capacity": float(operational_capacity),
                       "travel_days": travel_days, "daily_flow_bulk": int(daily_flow_bulk)},
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
    # Public aggregate traffic reading; no order, stock or owner identity is
    # exposed through this field.
    daily_flow_bulk: Count = 0
    channel: Literal["administrative_route_report", "route_bulletin"]
    event_id: Identity

    @model_validator(mode="after")
    def valid_observation(self):
        if self.travel_days is not None and self.operational_capacity <= 0:
            raise ValueError("a passable observation requires positive operational capacity")
        return self

    def observation(self) -> str:
        return route_observation(self.route_id, self.publisher_ref, self.observed_day,
                                 self.operational_capacity, self.travel_days, self.daily_flow_bulk)


def fiscal_route_observation(route_id, publisher_ref, observed_day, checkpoint_id, fee_per_bulk) -> str:
    """Public fiscal reading of one route, separate from physical operability.

    A reading says that a staffed civil checkpoint was observed and names its
    published per-bulk fee. It never carries its operator's
    account, staffing ledger, inspection capacity, or any cargo state.
    """
    return json.dumps({"route_id": route_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "checkpoint_id": checkpoint_id,
                       "fee_per_bulk": fee_per_bulk},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class FiscalRouteReport(SocietyValue):
    """Dated knowledge of a civil checkpoint along one canonical route."""
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    route_id: Identity
    observed_day: Count
    checkpoint_id: Identity
    fee_per_bulk: int = Field(strict=True, gt=0)
    channel: Literal["administrative_fiscal_route_report", "fiscal_route_bulletin"]
    event_id: Identity

    def observation(self) -> str:
        return fiscal_route_observation(self.route_id, self.publisher_ref, self.observed_day,
                                        self.checkpoint_id, self.fee_per_bulk)


def workforce_demand_observation(work_kind, work_id, target_occupation, sponsor_ref, observed_day, count,
                                 stipend_per_person) -> str:
    """Private, dated reading of a sponsor's real current labour shortfall."""
    return json.dumps({"work_kind": work_kind, "work_id": work_id, "target_occupation": target_occupation,
                       "sponsor": sponsor_ref.to_dict(), "observed_day": observed_day,
                       "count": count, "stipend_per_person": stipend_per_person},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class WorkforceDemandReport(SocietyValue):
    """A sponsor's own reading; it is neither a labour reservation nor a public feed."""
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    sponsor_ref: EntityRef
    work_kind: Literal["facility", "repair", "customs"]
    work_id: Identity
    # The engine derives this from the material work.  It is never selected by
    # a sponsor or a population group.
    target_occupation: Literal["farmer", "artisan", "merchant"]
    account_id: Identity
    count: Annotated[int, Field(strict=True, gt=0)]
    stipend_per_person: Annotated[int, Field(strict=True, gt=0)]
    observed_day: Count
    source_event_id: Identity
    event_id: Identity
    channel: Literal["administrative_workforce_demand"] = "administrative_workforce_demand"

    def observation(self) -> str:
        return workforce_demand_observation(self.work_kind, self.work_id, self.target_occupation, self.sponsor_ref,
                                            self.observed_day, self.count, self.stipend_per_person)


def workforce_offer_observation(notice_id, demand_id, sponsor_ref, source_group_id, target_occupation, count,
                                stipend_per_person, observed_day) -> str:
    """Wire shape of a direct, local offer; no sponsor balance is disclosed."""
    return json.dumps({"notice_id": notice_id, "demand_id": demand_id,
                       "sponsor": sponsor_ref.to_dict(), "source_group_id": source_group_id,
                       "target_occupation": target_occupation,
                       "count": count, "stipend_per_person": stipend_per_person,
                       "observed_day": observed_day},
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


class WorkforceOfferNotice(SocietyValue):
    """A dated direct offer known only to its named local population group."""
    id: Identity
    recipient_ref: EntityRef
    publisher_ref: EntityRef
    sponsor_ref: EntityRef
    demand_id: Identity
    source_group_id: Identity
    target_occupation: Literal["farmer", "artisan", "merchant"]
    count: Annotated[int, Field(strict=True, gt=0)]
    stipend_per_person: Annotated[int, Field(strict=True, gt=0)]
    observed_day: Count
    event_id: Identity
    channel: Literal["direct_workforce_offer"] = "direct_workforce_offer"

    def observation(self) -> str:
        return workforce_offer_observation(self.id, self.demand_id, self.sponsor_ref, self.source_group_id,
                                           self.target_occupation,
                                           self.count, self.stipend_per_person, self.observed_day)


def settlement_observation(settlement_id, publisher_ref, observed_day, population, present_population, housing_capacity,
                           health, missing_food, unrest, occupier_id=None, rite_underway=False,
                           protest_underway=False, warded=False) -> str:
    """Stable historical shape for public, aggregate settlement conditions.

    ``occupier_id`` is what an observer can see standing in the place: it is a
    canonical settlement fact, never a reading of anyone's detachment record.
    """
    return json.dumps({"settlement_id": settlement_id, "publisher": publisher_ref.to_dict(),
                       "observed_day": observed_day, "population": population, "present_population": present_population,
                       "housing_capacity": housing_capacity, "health": health,
                       "missing_food": missing_food, "unrest": unrest, "occupier_id": occupier_id,
                       "rite_underway": bool(rite_underway), "protest_underway": bool(protest_underway),
                       "warded": bool(warded)},
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
    occupier_id: Identity | None = None
    rite_underway: bool = False
    protest_underway: bool = False
    # Finished protective works are legible where they stand; nothing of the
    # rite that raised them, nor of who paid for it, is disclosed.
    warded: bool = False
    event_id: Identity
    channel: Literal["local_settlement_report", "settlement_bulletin"]

    def observation(self) -> str:
        return settlement_observation(self.settlement_id, self.publisher_ref, self.observed_day,
                                      self.population, self.present_population, self.housing_capacity, self.health,
                                      self.missing_food, self.unrest, self.occupier_id, self.rite_underway,
                                      self.protest_underway, self.warded)


class CivicDemandNotice(SocietyValue):
    """Private, aggregate demand delivered to the current city administration."""

    id: Identity
    recipient_ref: EntityRef
    protest_id: Identity
    group_id: Identity
    settlement_id: Identity
    demand_kind: Literal["food_relief", "site_repair", "organized_strike"]
    food_quantity: Count = 0
    site_id: Identity | None = None
    due_day: Count
    learned_day: Count
    event_id: Identity
    channel: Literal["direct_civic_demand"] = "direct_civic_demand"

    @model_validator(mode="after")
    def valid_shape(self):
        if ((self.demand_kind == "food_relief") != (self.food_quantity > 0 and self.site_id is None)
                or (self.demand_kind == "site_repair") != (self.food_quantity == 0 and self.site_id is not None)
                or (self.demand_kind == "organized_strike") != (self.food_quantity == 0 and self.site_id is None)):
            raise ValueError("civic notice demand shape is inconsistent")
        return self


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
    channel: Literal["administrative_site_report", "local_site_report"] = "administrative_site_report"
    event_id: Identity

    def observation(self) -> str:
        return site_observation(self.site_id, self.publisher_ref, self.observed_day, self.integrity, self.enabled,
                                self.service_suspended)


class InvestigationFinding(SocietyValue):
    """Private result of paid work on one observed site damage event.

    ``subject_ref`` is intentionally absent for an inconclusive examination.
    It may name an institution only when independent prior contact knowledge
    made the attribution deterministic; the damage event itself never teaches
    a victim who acted.
    """
    id: Identity
    investigation_id: Identity
    recipient_ref: EntityRef
    damage_event_id: Identity
    result: Literal["attributed", "inconclusive"]
    subject_ref: EntityRef | None = None
    learned_day: Count
    event_id: Identity
    channel: Literal["direct_investigation"] = "direct_investigation"

    @model_validator(mode="after")
    def valid_result(self):
        if self.id != f"investigation_finding:{self.investigation_id}":
            raise ValueError("investigation finding must be keyed by its investigation")
        if (self.result == "attributed") != (self.subject_ref is not None):
            raise ValueError("only an attributed investigation names a subject")
        return self


class InvestigationAccusationNotice(SocietyValue):
    """A private, factual accusation delivered to an attributed subject."""
    id: Identity
    recipient_ref: EntityRef
    accuser_ref: EntityRef
    investigation_id: Identity
    site_id: Identity
    subject_ref: EntityRef
    finding_event_id: Identity
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_investigation_accusation"] = "direct_investigation_accusation"


class EspionageFinding(SocietyValue):
    """Private result of one bounded espionage mission.

    Espionage never creates a hidden fact.  A successful finding points at an
    existing settlement observation event; failure and discovery deliberately
    carry no evidence reference.
    """
    id: Identity
    mission_id: Identity
    decision_event_id: Identity
    recipient_ref: EntityRef
    agent_ref: EntityRef
    target_ref: EntityRef
    target_owner_ref: EntityRef
    result: Literal["success", "failure", "discovered"]
    evidence_event_id: Identity | None = None
    learned_day: Count
    event_id: Identity
    channel: Literal["institutional_espionage"] = "institutional_espionage"

    @model_validator(mode="after")
    def valid_result(self):
        if self.id != f"espionage_finding:{self.decision_event_id}":
            raise ValueError("espionage finding must be keyed by its decision")
        if self.recipient_ref.kind not in {"polity", "organization"}:
            raise ValueError("espionage recipient must be an institution")
        if self.agent_ref.kind != "character" or self.target_ref.kind != "settlement":
            raise ValueError("espionage requires a character agent and settlement target")
        if (self.result == "success") != (self.evidence_event_id is not None):
            raise ValueError("only a successful mission may carry evidence")
        return self


class TechnologyTheftFinding(SocietyValue):
    """Private result of one material attempt to steal a catalogued technique.

    A theft never invents a technique or an effect.  A successful result names
    only the observed installation, the holder's canonical TechnicalKnowledge
    receipt, and the newly created stolen-knowledge receipt.  Failed and
    discovered attempts retain the observation but do not grant knowledge.
    """
    id: Identity
    mission_id: Identity
    decision_event_id: Identity
    recipient_ref: EntityRef
    agent_ref: EntityRef
    site_id: Identity
    target_owner_ref: EntityRef
    technology_id: Identity
    observation_event_id: Identity
    result: Literal["success", "failure", "discovered"]
    source_knowledge_event_id: Identity | None = None
    learned_knowledge_event_id: Identity | None = None
    learned_day: Count
    event_id: Identity
    channel: Literal["institutional_technology_theft"] = "institutional_technology_theft"

    @model_validator(mode="after")
    def valid_result(self):
        if self.id != f"technology_theft_finding:{self.decision_event_id}":
            raise ValueError("technology theft finding must be keyed by its decision")
        if self.recipient_ref.kind not in {"polity", "organization"}:
            raise ValueError("technology theft recipient must be an institution")
        if self.agent_ref.kind != "character":
            raise ValueError("technology theft requires a character agent")
        if self.result == "success":
            if self.source_knowledge_event_id is None or self.learned_knowledge_event_id is None:
                raise ValueError("successful technology theft requires canonical knowledge receipts")
        elif self.source_knowledge_event_id is not None or self.learned_knowledge_event_id is not None:
            raise ValueError("unsuccessful technology theft cannot grant knowledge")
        return self


class CustomsNotice(SocietyValue):
    """A private customs state receipt for one owned parcel.

    It is knowledge, not the customs ledger.  Its source presentation and any
    later declaration/evasion/payment transitions remain factual events.
    """
    id: Identity
    checkpoint_id: Identity
    parcel_id: Identity
    order_id: Identity
    resource_id: Identity
    quantity: int = Field(strict=True, gt=0)
    classification: Literal["ordinary", "contraband"]
    recipient_ref: EntityRef
    fee: int | None = Field(default=None, strict=True, gt=0)
    learned_day: Count
    event_id: Identity
    state_event_id: Identity
    state: Literal["presented", "fee_due", "detected", "evaded_undetected", "cleared", "returned", "seized"]
    manifest_id: Identity | None = None
    channel: Literal["direct_customs_notice"] = "direct_customs_notice"


class DiplomaticNotice(SocietyValue):
    id: Identity
    proposal_id: Identity
    recipient_ref: EntityRef
    event_id: Identity
    learned_day: Count
    channel: Literal['direct_diplomacy'] = 'direct_diplomacy'


class AuthorityClaimNotice(SocietyValue):
    """Private knowledge that one institution received a claim fact."""
    id: Identity
    claim_id: Identity
    recipient_ref: EntityRef
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_authority_claim"] = "direct_authority_claim"


class TechnologySighting(SocietyValue):
    """A dated private fact that another actor possessed one catalogued technique.

    A sighting is deliberately not TechnicalKnowledge.  It says only that the
    named holder possessed the named technology when its own canonical
    knowledge fact was created; it never unlocks a recipe, prerequisite, rite
    or material capability for the recipient.
    """
    id: Identity
    recipient_ref: EntityRef
    holder_ref: EntityRef
    technology_id: Identity
    source_event_id: Identity
    observed_day: Count
    expires_day: Count
    event_id: Identity
    channel: Literal["voluntary_technical_disclosure"] = "voluntary_technical_disclosure"

    @model_validator(mode="after")
    def valid_sighting(self):
        if self.recipient_ref == self.holder_ref or self.expires_day <= self.observed_day:
            raise ValueError("technology sighting needs distinct parties and a future expiry")
        return self


class InstitutionalAidNotice(SocietyValue):
    """A direct private receipt for one institutional-aid request or response.

    It carries the need that was asked for and nothing else: no inventory, no
    offer, no final quantity and no route. Those are recomposed by the
    responding institution from its own canonical holdings and its own dated
    fiscal readings after it has received the request.
    """
    id: Identity
    request_event_id: Identity
    recipient_ref: EntityRef
    requester_ref: EntityRef
    requester_settlement_id: Identity
    report_id: Identity
    requested_food: Annotated[int, Field(strict=True, gt=0)]
    event_id: Identity
    learned_day: Count
    kind: Literal["request", "response"]
    response_status: Literal["accepted", "rejected"] | None = None
    channel: Literal["direct_institutional_aid"] = "direct_institutional_aid"


class CreatureTributeNotice(SocietyValue):
    """A direct demand delivered to one endpoint administration.

    It states only the crossing, the deadline and the exact food asked for. It
    never carries the creature's condition, threshold, perception history or
    what any other institution was told or offered.
    """
    id: Identity
    recipient_ref: EntityRef
    creature_id: Identity
    demand_id: Identity
    route_id: Identity
    food: Annotated[int, Field(strict=True, gt=0)]
    due_day: Count
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_creature_demand"] = "direct_creature_demand"


class CreatureDamageNotice(SocietyValue):
    """Private material notice sent only to holders of the creature's demand.

    It contains the route/site fact needed by the addressed institution to
    inspect its own SiteReport.  It deliberately carries no creature identity,
    condition, integrity, ownership, maintainer or attribution.
    """
    id: Identity
    recipient_ref: EntityRef
    demand_id: Identity
    route_id: Identity
    site_id: Identity
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_creature_damage"] = "direct_creature_damage"


class ForceContactNotice(SocietyValue):
    """What one force owner physically learned at an armed contact.

    A visible rival banner identifies its institution, but this never copies
    the rival detachment's exact headcount, provisions, source, route or
    plans.  The two readings are engine-owned, bounded observations.
    """
    id: Identity
    recipient_ref: EntityRef
    standoff_id: Identity
    own_detachment_id: Identity
    counterparty_ref: EntityRef
    settlement_id: Identity
    event_id: Identity
    learned_day: Count
    counterparty_strength_band: Literal["1-9", "10-24", "25-49", "50-99", "100+"]
    counterparty_posture: Literal["present", "leaving", "fortified"]
    last_event_id: Identity
    channel: Literal["direct_force_contact"] = "direct_force_contact"


class FieldEngagementOfferNotice(SocietyValue):
    """A direct challenge notice; it exposes neither material means nor terms beyond joining."""
    id: Identity
    recipient_ref: EntityRef
    engagement_id: Identity
    standoff_id: Identity
    challenger_ref: EntityRef
    settlement_id: Identity
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_field_engagement"] = "direct_field_engagement"


class FieldEngagementOutcomeNotice(SocietyValue):
    """A side's bounded result after a resolved field engagement.

    ``own_detachment_id`` is the original contact column retained solely as an
    after-action anchor.  Casualties and the opposing strength band describe
    the participating sides, never that one column alone.
    """
    id: Identity
    recipient_ref: EntityRef
    engagement_id: Identity
    own_detachment_id: Identity
    settlement_id: Identity
    counterparty_ref: EntityRef
    own_casualties: Count
    counterparty_strength_band: Literal["1-9", "10-24", "25-49", "50-99", "100+"]
    outcome: Literal["won", "lost", "indecisive"]
    own_prepared: bool
    own_supplied: bool
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_field_engagement"] = "direct_field_engagement"


class SettlementPressureNotice(SocietyValue):
    """A local administration's bounded, dated reading of closed exits.

    It deliberately names neither the force, its owner, its size nor where the
    column stood.  The canonical investment event is its only source.
    """
    id: Identity
    recipient_ref: EntityRef
    settlement_id: Identity
    investment_id: Identity
    route_count: Annotated[int, Field(strict=True, gt=0)]
    event_id: Identity
    learned_day: Count
    channel: Literal["direct_settlement_pressure"] = "direct_settlement_pressure"


class RiteObservation(SocietyValue):
    """A deliberately narrow local reading of an ongoing public rite.

    The recipient learns only that work is underway at a local site and a
    bounded count of assistants.  The rite contract, officiant, sponsor,
    materials, accounts and eventual effect all remain outside knowledge.
    """
    id: Identity
    recipient_ref: EntityRef
    settlement_id: Identity
    site_id: Identity
    stage: Literal["underway"]
    observed_day: Count
    assistants_band: Literal["1-2", "3-5", "6+"]
    event_id: Identity
    channel: Literal["local_rite_observation"] = "local_rite_observation"


class CampaignSupplyNotice(SocietyValue):
    """One owner's dated reading that its own standing column is running low.

    It names no foreign force or inventory. Freight and the campaign bag stay
    with their respective Economy and Society owners.
    """
    id: Identity
    recipient_ref: EntityRef
    detachment_id: Identity
    settlement_id: Identity
    threshold: Count
    observed_provisions: Count
    event_id: Identity
    learned_day: Count
    state: Literal["open", "dispatched", "fulfilled", "lapsed"] = "open"
    freight_id: Identity | None = None
    last_event_id: Identity
    channel: Literal["direct_campaign_supply"] = "direct_campaign_supply"


class Objective(SocietyValue):
    id: Identity
    actor_ref: EntityRef
    settlement_id: Identity
    stock_id: Identity
    resource_id: Identity = "food"
    kind: Literal["maintain_food_reserve", "maintain_production_inputs", "defend_occupied_settlement"] = "maintain_food_reserve"
    reserve_months: int = Field(default=2, strict=True, ge=1, le=12)
    motivation: Identity = "Proteger o abastecimento dos habitantes."


class StrategicPlan(SocietyValue):
    id: Identity
    objective_id: Identity
    stage: Literal["acquire", "await_delivery", "satisfied", "adopted", "closed", "blocked"]
    order_ids: tuple[Identity, ...] = ()
    blocker: Identity | None = None
    last_review_day: Count
    last_event_id: Identity
