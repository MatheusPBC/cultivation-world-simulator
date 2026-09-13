"""Strict primitive serialization shared by independent governance registries."""


class RegistrySerialization:
    registries = {}

    def to_dict(self):
        self.validate()
        return {"schema_version": 1, **{
            name: {key: item.model_dump(mode="json") for key, item in sorted(getattr(self, name).items())}
            for name in self.registries}}

    @classmethod
    def from_dict(cls, data):
        if (not isinstance(data, dict) or set(data) != {"schema_version", *cls.registries}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1):
            raise ValueError("invalid governance state schema")
        parsed = {}
        for name, model in cls.registries.items():
            if not isinstance(data[name], dict):
                raise ValueError("governance registry must be keyed by ID")
            parsed[name] = {}
            for key, value in data[name].items():
                if not isinstance(value, dict) or set(value) != set(model.model_fields):
                    raise ValueError("invalid saved governance value fields")
                parsed[name][key] = model.model_validate(value)
        state = cls(**parsed)
        state.validate()
        return state

    def validate(self, world=None):
        for name, model in self.registries.items():
            registry = getattr(self, name)
            if not isinstance(registry, dict):
                raise ValueError("invalid governance registry")
            for key, value in registry.items():
                if not isinstance(value, model) or key != value.id:
                    raise ValueError("invalid governance registry identity")
                model.model_validate(value.model_dump(mode="json"))


def validate_actor(world, ref):
    owners = {"polity": world.society.polities, "organization": world.society.organizations,
              "character": world.society.characters}
    if ref.id not in owners.get(ref.kind, {}):
        raise ValueError("unknown governance actor")
