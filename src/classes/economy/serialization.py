"""Strict save boundary: catalogs travel with economic state, never reload on resume."""

from .models import (FreightRecoveryCase, Market, MoneyAccount, Payroll, ProductionFacility, Recipe, Resource,
                     SettlementNeeds, Stock)
from .logistics import FreightOrder, CargoParcel, RouteFlow
from .expansion import ExpansionBlueprint, ExpansionProject
from .maintenance import RepairBlueprint, RepairProject
from .investigation import Investigation
from .migration import MigrationProvision
from .customs import CargoManifest, CustomsCheckpoint

REGISTRIES = {"resources": Resource, "recipes": Recipe, "stocks": Stock,
              "accounts": MoneyAccount, "facilities": ProductionFacility, "payrolls": Payroll, "needs": SettlementNeeds,
              "freight_orders": FreightOrder, "parcels": CargoParcel, "route_flows": RouteFlow, "markets": Market,
              "expansion_blueprints": ExpansionBlueprint, "expansions": ExpansionProject,
              "repair_blueprints": RepairBlueprint, "repairs": RepairProject,
              "migration_provisions": MigrationProvision}
REGISTRIES["customs_checkpoints"] = CustomsCheckpoint
REGISTRIES["cargo_manifests"] = CargoManifest
REGISTRIES["freight_recovery_cases"] = FreightRecoveryCase
REGISTRIES["investigations"] = Investigation


class EconomySerialization:
    def to_dict(self) -> dict:
        self.validate()
        return {"schema_version": 12, "payments": dict(sorted(self.payments.items())), **{
            name: {key: value.model_dump(mode="json") for key, value in sorted(getattr(self, name).items())}
            for name in REGISTRIES}}

    @classmethod
    def from_dict(cls, data):
        if (not isinstance(data, dict) or set(data) != {"schema_version", "payments", *REGISTRIES}
                or type(data["schema_version"]) is not int or data["schema_version"] != 12):
            raise ValueError("invalid economy schema")
        parsed = {}
        for name, model in REGISTRIES.items():
            if not isinstance(data[name], dict):
                raise ValueError(f"{name} must be a registry")
            parsed[name] = {}
            for key, raw in data[name].items():
                if not isinstance(raw, dict) or set(raw) != set(model.model_fields):
                    raise ValueError(f"invalid saved {name} fields")
                parsed[name][key] = model.model_validate(raw)
        state = cls(**parsed, payments=data["payments"])
        state.validate()
        return state
