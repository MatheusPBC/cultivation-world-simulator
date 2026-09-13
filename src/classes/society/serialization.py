"""Strict JSON boundary for society state; all cross-domain references are IDs."""

from .models import Character, Organization, Polity, PopulationGroup, Settlement
from .migration import MigrationJourney


REGISTRIES = {
    "characters": Character,
    "organizations": Organization,
    "polities": Polity,
    "population": PopulationGroup,
    "settlements": Settlement,
    "migrations": MigrationJourney,
}


class SocietySerialization:
    def to_dict(self) -> dict:
        self.validate()
        return {
            "schema_version": 2,
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
        if type(data["schema_version"]) is not int or data["schema_version"] != 2:
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
