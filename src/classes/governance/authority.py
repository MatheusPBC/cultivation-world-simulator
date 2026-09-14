"""Authority is computed from live offices, never titles, wealth or narration."""

from dataclasses import dataclass, field

from .models import AuthorityClaim, AuthorityOffice, TaxPolicy
from .serialization import RegistrySerialization, validate_actor


@dataclass
class AuthorityState(RegistrySerialization):
    offices: dict[str, AuthorityOffice] = field(default_factory=dict)
    tax_policies: dict[str, TaxPolicy] = field(default_factory=dict)
    claims: dict[str, AuthorityClaim] = field(default_factory=dict)
    registries = {"offices": AuthorityOffice, "tax_policies": TaxPolicy,
                  "claims": AuthorityClaim}

    def validate(self, world=None):
        super().validate(world)
        if world is None:
            return
        day = world.clock.absolute_day
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
        for claim in self.claims.values():
            validate_actor(world, claim.claimant_ref)
            office = self.offices.get(claim.office_id)
            event = events.get(claim.last_event_id)
            evidence = events.get(claim.evidence_event_id)
            if office is None or event is None or evidence is None or claim.declared_day > day:
                raise ValueError("invalid authority claim reference")
            declared = [item for item in events.values()
                        if item.event_type == "authority_claim_declared"
                        and any(delta.owner_kind == "authority_claim" and delta.owner_id == claim.id
                                and delta.aspect == "stage" and delta.before == "None"
                                and delta.after == "declared" for delta in item.deltas)]
            if len(declared) != 1:
                raise ValueError("authority claim requires one declaration receipt")
            declared_event = declared[0]
            declared_decisions = [events.get(link.cause_event_id) for link in declared_event.causal_links]
            if (declared_event.day != claim.declared_day
                    or claim.evidence_event_id not in {link.cause_event_id for link in declared_event.causal_links}
                    or not any(decision is not None and decision.fact_kind.name == "DECISION"
                               and decision.decision == {"action": "declare_authority_claim",
                                                        "actor_ref": claim.claimant_ref.to_dict(),
                                                        "selected_affordance_id": decision.decision.get("selected_affordance_id")}
                               and str(decision.decision.get("selected_affordance_id", "")).startswith(
                                   f"authority-claim-declare:{claim.claimant_ref.kind}:{claim.claimant_ref.id}:{claim.office_id}:{claim.evidence_kind}:{claim.evidence_event_id}:{claim.evidence_subject_id}")
                               for decision in declared_decisions)):
                raise ValueError("authority claim declaration lacks exact decision provenance")
            expected_evidence_type = {"standing_claimant": "settlement_observed",
                                      "unremedied_breach": "commitment_breached",
                                      "held_occupation": "settlement_occupied"}[claim.evidence_kind]
            if evidence.event_type != expected_evidence_type:
                raise ValueError("authority claim evidence has the wrong factual kind")
            decision_events = [events.get(link.cause_event_id) for link in event.causal_links]
            if claim.stage == "declared":
                if (event.event_type != "authority_claim_declared"
                        or not any(delta.owner_kind == "authority_claim" and delta.owner_id == claim.id
                                   and delta.aspect == "stage" and delta.before == "None"
                                   and delta.after == "declared" for delta in event.deltas)):
                    raise ValueError("declared authority claim lacks receipt")
                expected_action = "declare_authority_claim"
            elif claim.stage == "withdrawn":
                if (event.event_type != "authority_claim_withdrawn"
                        or not any(delta.owner_kind == "authority_claim" and delta.owner_id == claim.id
                                   and delta.aspect == "stage" and delta.before == "declared"
                                   and delta.after == "withdrawn" for delta in event.deltas)):
                    raise ValueError("withdrawn authority claim lacks receipt")
                expected_action = "withdraw_authority_claim"
            else:
                if (event.event_type != "authority_claim_lapsed"
                        or not any(delta.owner_kind == "authority_claim" and delta.owner_id == claim.id
                                   and delta.aspect == "stage" and delta.before == "declared"
                                   and delta.after == "lapsed" for delta in event.deltas)):
                    raise ValueError("lapsed authority claim lacks receipt")
                expected_action = None
            if expected_action is not None and not any(
                    decision is not None and decision.decision is not None
                    and decision.decision.get("action") == expected_action
                    and decision.decision.get("actor_ref") == claim.claimant_ref.to_dict()
                    for decision in decision_events):
                raise ValueError("authority claim lifecycle lacks its actor decision")


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
