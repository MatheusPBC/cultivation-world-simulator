"""Strict JSON boundary for society state; all cross-domain references are IDs."""

from .models import Character, Organization, Polity, PopulationGroup, Settlement
from .force import (AssemblyDenial, Detachment, DetachmentCommand, FieldEngagement, ForcePosition, ForceStandoff,
                    RouteInterdiction, SettlementInvestment)
from .civic import CivicProtest
from .demography import BirthCohort
from .migration import MigrationJourney
from .workforce import WorkforceTransition


REGISTRIES = {
    "characters": Character,
    "organizations": Organization,
    "polities": Polity,
    "population": PopulationGroup,
    "settlements": Settlement,
    "migrations": MigrationJourney,
    "workforce_transitions": WorkforceTransition,
    "detachments": Detachment,
    "force_standoffs": ForceStandoff,
    "force_positions": ForcePosition,
    "detachment_commands": DetachmentCommand,
    "field_engagements": FieldEngagement,
    "route_interdictions": RouteInterdiction,
    "settlement_investments": SettlementInvestment,
    "assembly_denials": AssemblyDenial,
    "civic_protests": CivicProtest,
    "birth_cohorts": BirthCohort,
}


class SocietySerialization:
    def to_dict(self) -> dict:
        self.validate()
        return {
            "schema_version": 13,
            **{
                name: {
                    key: value.model_dump(mode="json")
                    for key, value in sorted(getattr(self, name).items())
                }
                for name in REGISTRIES
            },
        }

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict) or set(data) != {"schema_version", *REGISTRIES}:
            raise ValueError("invalid society fields")
        if type(data["schema_version"]) is not int or data["schema_version"] != 13:
            raise ValueError("unsupported society schema")
        parsed = {}
        for name, model in REGISTRIES.items():
            if not isinstance(data[name], dict):
                raise ValueError(f"{name} must be a registry keyed by ID")
            parsed[name] = {}
            for key, raw in data[name].items():
                if not isinstance(raw, dict) or set(raw) != set(model.model_fields):
                    raise ValueError(f"invalid saved {name} fields")
                parsed[name][key] = model.model_validate(raw)
        society = cls(**parsed)
        society.validate()
        return society
