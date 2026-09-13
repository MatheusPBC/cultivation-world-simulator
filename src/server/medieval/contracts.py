"""Typed public DTOs. Domain objects are serialized under the runtime lock."""

import re
from typing import Generic, Literal, TypeVar

from pydantic import Field, field_validator

from src.classes.core.medieval_config import MedievalRunConfig
from src.classes.economy.models import Market, MoneyAccount, Payroll, ProductionFacility, Recipe, Resource, SettlementNeeds, Stock
from src.classes.economy.logistics import CargoParcel, FreightOrder, RouteFlow
from src.classes.economy.expansion import ExpansionBlueprint, ExpansionProject
from src.classes.economy.maintenance import RepairBlueprint, RepairProject
from src.classes.research.models import ResearchProject, Technology, TechnicalKnowledge
from src.classes.governance.diplomacy import DiplomaticProposal, Obligation
from src.classes.governance.models import CustomsNotice, DiplomaticNotice, RouteReport, SettlementReport, SiteReport
from src.classes.environment.geography import GeographyLayer
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.environment.route import Route
from src.classes.society.models import Character, Organization, Polity, PopulationGroup, Settlement, SocietyValue
from src.classes.society.migration import MigrationJourney
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


class WorldView(SocietyValue):
    day: int
    calendar: CalendarView
    config: MedievalRunConfig
    population: int
    living_characters: int
    settlements: int
    polities: int
    organizations: int
    events: int
    next_scheduled_day: int | None


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


class GovernanceView(SocietyValue):
    offices: list[AuthorityOffice]
    tax_policies: list[TaxPolicy]
    reports: list[KnowledgeReport]
    objectives: list[ObjectiveView]
    plans: list[StrategicPlan]
    route_reports: list[RouteReport]
    site_reports: list[SiteReport]
    settlement_reports: list[SettlementReport]
    customs_notices: list[CustomsNotice]


class ResearchView(SocietyValue):
    technologies: list[Technology]
    projects: list[ResearchProject]
    knowledge: list[TechnicalKnowledge]


class DiplomacyView(SocietyValue):
    proposals: list[DiplomaticProposal]
    obligations: list[Obligation]
    notices: list[DiplomaticNotice]


class ObservatoryView(SocietyValue):
    status: StatusView
    world: WorldView
    society: SocietyView
    economy: EconomyView
    map: MapView
    governance: GovernanceView
    research: ResearchView
    diplomacy: DiplomacyView


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
