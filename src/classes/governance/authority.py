"""Authority is computed from live offices, never titles, wealth or narration."""

from dataclasses import dataclass, field

from .models import AuthorityOffice, TaxPolicy
from .serialization import RegistrySerialization, validate_actor


@dataclass
class AuthorityState(RegistrySerialization):
    offices: dict[str, AuthorityOffice] = field(default_factory=dict)
    tax_policies: dict[str, TaxPolicy] = field(default_factory=dict)
    registries = {"offices": AuthorityOffice, "tax_policies": TaxPolicy}

    def validate(self, world=None):
        super().validate(world)
        if world is None:
            return
        for office in self.offices.values():
            validate_actor(world, office.institution_ref)
            validate_actor(world, office.holder_ref)
            if office.institution_ref.kind not in {"polity", "organization"}:
                raise ValueError("office institution must be a polity or organization")
            if office.holder_ref.kind != "character" and office.holder_ref != office.institution_ref:
                raise ValueError("collective office holder must be its institution")
        events = {e.id: e for e in world.events}
        for policy in self.tax_policies.values():
            account = world.economy.accounts.get(policy.account_id)
            if (policy.id not in world.society.polities or account is None
                    or account.owner_ref.kind != "polity" or account.owner_ref.id != policy.id
                    or (policy.last_event_id is not None and policy.last_event_id not in events)
                    or (policy.export_policy_event_id is not None and (
                        policy.export_policy_event_id not in events
                        or not any(delta.owner_kind == "tax_policy" and delta.owner_id == policy.id
                                   and delta.aspect == "export_rate_permille"
                                   and delta.after == str(policy.export_rate_permille)
                                   for delta in events[policy.export_policy_event_id].deltas)))
                    or (policy.export_rate_permille != 0 and policy.export_policy_event_id is None)):
                raise ValueError("invalid tax policy owner or provenance")


def can_actor_act_for(world, actor_ref, institution_ref, scope):
    day = world.clock.absolute_day
    for office in world.authority.offices.values():
        if (office.institution_ref != institution_ref or scope not in office.scopes
                or office.starts_day > day or (office.ends_day is not None and day >= office.ends_day)
                or actor_ref not in (office.holder_ref, institution_ref)):
            continue
        if office.holder_ref.kind == "character":
            person = world.society.characters.get(office.holder_ref.id)
            if person is None or person.death_day is not None:
                continue
        return True
    return False


def require_authority(world, owner_ref, scope):
    # Individuals can dispose of their own assets, but cannot represent institutions
    # merely because an institutional decision names them in prose.
    if owner_ref.kind == "character":
        person = world.society.characters.get(owner_ref.id)
        if person is not None and person.death_day is None:
            return
    elif can_actor_act_for(world, owner_ref, owner_ref, scope):
        return
    raise ValueError("current authority does not permit this operation")
