"""Typed public DTOs. Domain objects are serialized under the runtime lock."""

import re
from typing import Any, Generic, Literal, TypeVar

from pydantic import Field, field_validator

from src.classes.core.medieval_config import MedievalRunConfig
from src.classes.economy.models import (Market, MoneyAccount, Payroll, PermanentEmploymentContract,
                                         ProductionFacility, Recipe, Resource, SettlementNeeds, Stock)
from src.classes.economy.logistics import CargoParcel, FreightOrder, RouteFlow
from src.classes.economy.expansion import ExpansionBlueprint, ExpansionProject
from src.classes.economy.maintenance import RepairBlueprint, RepairProject
from src.classes.research.models import (ResearchProject, RiteBlueprintMetadata, Technology,
                                         TechnicalKnowledge)
from src.classes.governance.diplomacy import DiplomaticProposal, InstitutionalMemory, Obligation
from src.classes.governance.models import (AuthorityClaim, AuthorityRecognition, CreatureTributeNotice, CustomsNotice, DiplomaticNotice, FiscalRouteReport,
                                            InstitutionalAidNotice, RouteReport,
                                            SettlementReport, SiteReport, WorkforceDemandReport, WorkforceOfferNotice)
from src.classes.mechanical_language import EntityRef
from src.classes.environment.creature import Creature, CreatureDemand
from src.classes.environment.geography import GeographyLayer
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.regional_overflow import RegionalOverflowOccurrence
from src.classes.environment.route import Route
from src.classes.society.models import Character, Organization, Polity, PopulationGroup, Settlement, SocietyValue
from src.classes.society.migration import MigrationJourney
from src.classes.society.workforce import WorkforceTransition
from src.classes.society.movement import CivicMovement
from src.classes.society.strike import CivicStrike
from src.classes.society.amnesty import CivicAmnesty
from src.classes.society.force import (AssemblyDenial, Detachment, DetachmentCommand, FieldEngagement, ForcePosition,
                                       ForceStandoff, RouteInterdiction, SettlementInvestment, SiegeCampaign, Garrison)
from src.classes.society.control import TerritorialControl
from src.classes.society.civic import CivicProtest
from src.classes.economy.migration import MigrationProvision
from src.classes.economy.customs import CargoManifest, CustomsCheckpoint
from src.sim.medieval.activities import Activity
from src.sim.medieval.events import WorldEvent

T = TypeVar("T")


class Envelope(SocietyValue, Generic[T]):
    ok: Literal[True] = True
    data: T
    revision: int


class ErrorView(SocietyValue):
    code: str
    message: str


class CalendarView(SocietyValue):
    year: int
    month: int
    day: int


class StatusView(SocietyValue):
    product: Literal["medieval-world-simulator"] = "medieval-world-simulator"
    ready: bool
    paused: bool
    jumps_per_second: int
    day: int | None
    run_id: str | None
    last_error: ErrorView | None


class OptionsView(SocietyValue):
    defaults: MedievalRunConfig = Field(default_factory=MedievalRunConfig)
    map_id: str = "vale-das-tres-coroas"
    map_name: str = "Vale das Três Coroas"
    ai_available: bool = False


class DecisionSourceView(SocietyValue):
    """Derived from canonical receipts: consultations versus routine fallback.

    It never carries a prompt, an answer or any provider setting.
    """
    provider_consultations: int
    provider_declines: int
    provider_failures: int
    no_affordance_receipts: int
    stale_affordance_receipts: int
    ai_enabled: bool


class WorldView(SocietyValue):
    day: int
    calendar: CalendarView
    config: MedievalRunConfig
    decision_sources: DecisionSourceView
    population: int
    living_characters: int
    settlements: int
    polities: int
    organizations: int
    events: int
    next_scheduled_day: int | None
    regional_overflows: list[RegionalOverflowOccurrence]


class CharacterView(Character):
    age_years: int


class SettlementView(Settlement):
    population: int
    present_population: int
    center: tuple[int, int]
    health: int
    unrest: int
    missing_food: int


class SocietyView(SocietyValue):
    characters: list[CharacterView]
    settlements: list[SettlementView]
    polities: list[Polity]
    organizations: list[Organization]
    population_groups: list[PopulationGroup]
    activities: list[Activity]
    migrations: list[MigrationJourney]
    workforce_transitions: list[WorkforceTransition]
    civic_protests: list[CivicProtest]
    civic_movements: list[CivicMovement]
    civic_strikes: list[CivicStrike]
    civic_amnesties: list[CivicAmnesty]


class DossierEntry(SocietyValue):
    """One actor-visible read-model entry; it is never a knowledge owner."""
    category: str
    id: str
    event_id: str | None = None
    learned_day: int | None = None
    # Only links whose target event is itself known by this actor are exposed.
    # The complete causal graph remains Dao-only through ``causal_view``.
    cause_event_ids: list[str] = Field(default_factory=list)
    # Distance from a directly known notice/decision in the actor-visible
    # causal graph.  This is only an observability hint; it never expands
    # knowledge or exposes a cause the actor does not already know.
    causal_depth: int = Field(default=0, strict=True, ge=0, le=64)
    payload: dict[str, object]


class DossierView(SocietyValue):
    """Private perspective assembled only from facts already known by an actor."""
    actor_ref: EntityRef
    entries: list[DossierEntry]


class OccupationView(SocietyValue):
    """The Map-independent physical occupation presently held at one settlement."""
    settlement_id: str
    occupier_ref: EntityRef


class PoliticalSettlementView(SocietyValue):
    """A live material campaign settlement proposal, never an instruction."""
    id: str
    proposal_kind: Literal["force_deescalation", "administration_concession"]
    settlement_id: str | None = None
    proposer_ref: EntityRef
    counterparty_ref: EntityRef
    status: Literal["offered", "accepted"]
    offered_day: int
    expires_day: int
    clause_kinds: list[str]
    decision_event_id: str
    last_event_id: str


class ThreatView(SocietyValue):
    """Dao-only projection of a currently active material threat."""
    id: str
    kind: str
    settlement_id: str | None = None
    route_id: str | None = None
    site_id: str | None = None
    severity: str
    status: str
    source_event_id: str


class CampaignView(SocietyValue):
    """Dao-only projection of canonical campaign state; it is not actor knowledge."""
    detachments: list[Detachment]
    commands: list[DetachmentCommand]
    positions: list[ForcePosition]
    standoffs: list[ForceStandoff]
    field_engagements: list[FieldEngagement]
    route_interdictions: list[RouteInterdiction]
    settlement_investments: list[SettlementInvestment]
    garrisons: list[Garrison]
    siege_campaigns: list[SiegeCampaign]
    assembly_denials: list[AssemblyDenial]
    occupations: list[OccupationView]
    territorial_controls: list[TerritorialControl]
    political_settlements: list[PoliticalSettlementView]
    threats: list[ThreatView]


class EconomyView(SocietyValue):
    expansion_blueprints: list[ExpansionBlueprint]
    expansions: list[ExpansionProject]
    repair_blueprints: list[RepairBlueprint]
    repairs: list[RepairProject]
    migration_provisions: list[MigrationProvision]
    resources: list[Resource]
    recipes: list[Recipe]
    stocks: list[Stock]
    accounts: list[MoneyAccount]
    facilities: list[ProductionFacility]
    payrolls: list[Payroll]
    employment_contracts: list[PermanentEmploymentContract]
    needs: list[SettlementNeeds]
    markets: list[Market]
    pending_orders: list[FreightOrder]
    completed_order_count: int
    parcels: list[CargoParcel]
    route_flows: list[RouteFlow]
    customs_checkpoints: list[CustomsCheckpoint]
    cargo_manifests: list[CargoManifest]


class RouteView(SocietyValue):
    route: Route
    operational_capacity: float


class MapView(SocietyValue):
    map_id: str
    name: str
    width: int
    height: int
    region_rows: list[list[int]]
    geography: GeographyLayer
    settlements: list[SettlementView]
    routes: list[RouteView]
    sites: list[InfrastructureSite]


class EventsView(SocietyValue):
    items: list[WorldEvent]
    next_after: int
    has_more: bool


from src.classes.governance.models import AuthorityOffice, KnowledgeReport, Objective, StrategicPlan, TaxPolicy


class ObjectiveView(Objective):
    target_quantity: int


class StrategicCapacityDimensionView(SocietyValue):
    status: str
    objective_ids: list[str]
    plan_ids: list[str]
    source_ids: list[str]


class StrategicCapacityView(SocietyValue):
    actor_ref: EntityRef
    dimensions: dict[str, StrategicCapacityDimensionView]


class GovernanceView(SocietyValue):
    offices: list[AuthorityOffice]
    tax_policies: list[TaxPolicy]
    reports: list[KnowledgeReport]
    objectives: list[ObjectiveView]
    plans: list[StrategicPlan]
    route_reports: list[RouteReport]
    fiscal_route_reports: list[FiscalRouteReport]
    site_reports: list[SiteReport]
    settlement_reports: list[SettlementReport]
    customs_notices: list[CustomsNotice]
    workforce_demand_reports: list[WorkforceDemandReport]
    workforce_offer_notices: list[WorkforceOfferNotice]
    claims: list[AuthorityClaim]
    authority_recognitions: list[AuthorityRecognition]
    strategic_capacity: list[StrategicCapacityView]


class TechnologySaleEvidenceView(SocietyValue):
    """One completed paid transfer with the receipts needed for a Why traversal."""
    receipt_event_id: str
    buyer_ref: EntityRef
    seller_ref: EntityRef
    technology_id: str
    request_event_id: str
    acceptance_event_id: str
    payment_event_id: str
    knowledge_event_id: str


class ResearchView(SocietyValue):
    technologies: list[Technology]
    projects: list[ResearchProject]
    knowledge: list[TechnicalKnowledge]
    technology_sales: list[TechnologySaleEvidenceView]
    rite_blueprints: list[RiteBlueprintMetadata]


class InstitutionalMemoryView(InstitutionalMemory):
    """Relevance only: the derived salience of a fact the institution knows."""
    effective_salience: int
    kind: str = "unknown"


class AidRelationshipView(SocietyValue):
    """One directional reading, evidenced by the observer's own aid memories."""
    observer_ref: EntityRef
    subject_ref: EntityRef
    value: int
    evidence_event_ids: list[str]


class DiplomacyView(SocietyValue):
    proposals: list[DiplomaticProposal]
    obligations: list[Obligation]
    notices: list[DiplomaticNotice]
    aid_notices: list[InstitutionalAidNotice]
    memories: list[InstitutionalMemoryView]
    aid_readings: list[AidRelationshipView]
    strategic_evidence: list[dict[str, Any]]


class CreatureDamageView(SocietyValue):
    """A pending creature damage binding, joined to the current Map-owned site."""
    creature_id: str
    site_id: str
    damage_event_id: str
    integrity: float


class HazardImpactView(SocietyValue):
    """Recorded engine hazard evidence; the observer does not create knowledge."""
    event_id: str
    source_event_id: str
    hazard_kind: str
    target_ref: EntityRef
    effect: str
    magnitude: float
    exposure: float
    resistance: dict[str, bool]


class CreatureView(SocietyValue):
    """Omniscient read-only projection: creatures, demands and private notices."""
    creatures: list[Creature]
    demands: list[CreatureDemand]
    tribute_notices: list[CreatureTributeNotice]
    damaged_sites: list[CreatureDamageView]
    hazard_impacts: list[HazardImpactView]


class ObservatoryView(SocietyValue):
    status: StatusView
    world: WorldView
    society: SocietyView
    economy: EconomyView
    map: MapView
    governance: GovernanceView
    research: ResearchView
    diplomacy: DiplomacyView
    creatures: CreatureView
    campaigns: CampaignView


class CausalView(SocietyValue):
    event: WorldEvent
    causes: list[WorldEvent]
    effects: list[WorldEvent]
    next_after: int
    has_more: bool


class SaveView(SocietyValue):
    save_id: str
    size_bytes: int
    modified_at: str
    compatible: bool
    day: int | None


class EmptyRequest(SocietyValue):
    pass


class CreateRequest(MedievalRunConfig):
    replace: bool = Field(default=False, strict=True)


class SpeedRequest(SocietyValue):
    jumps_per_second: int = Field(strict=True, ge=1, le=20)


def validate_save_id(value: str) -> str:
    if (not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value)
            or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", value, re.IGNORECASE)):
        raise ValueError("Nome de save inválido.")
    return value


class LoadRequest(SocietyValue):
    save_id: str

    @field_validator("save_id")
    @classmethod
    def valid_name(cls, value):
        return validate_save_id(value)


class SaveRequest(LoadRequest):
    overwrite: bool = Field(default=False, strict=True)
