"""Bounded institutional authority claims without granting authority.

Claims are factual political assertions.  They compose only from the claimant's
own bounded evidence, and all material authority remains in governance.authority.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import authority_claim_notice_id
from src.classes.governance.models import AuthorityClaim, AuthorityClaimNotice, AuthorityRecognition
from src.classes.mechanical_language import EntityRef

from .economy import _delta
from .events import record_event


DECLARE_ACTION = "declare_authority_claim"
WITHDRAW_ACTION = "withdraw_authority_claim"
RECOGNIZE_ACTION = "recognize_authority_claim"
WITHDRAW_RECOGNITION_ACTION = "withdraw_authority_recognition"


@dataclass(frozen=True)
class AuthorityClaimOption:
    id: str
    actor_ref: EntityRef
    action: str
    claim_id: str | None = None
    office_id: str | None = None
    evidence_kind: str | None = None
    evidence_event_id: str | None = None
    evidence_subject_id: str | None = None

    def decision(self):
        return {"action": self.action, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}

    @property
    def label(self):
        labels = {
            DECLARE_ACTION: "Declarar uma pretensão baseada em evidência própria conhecida.",
            WITHDRAW_ACTION: "Retirar uma pretensão institucional ainda vigente.",
            RECOGNIZE_ACTION: "Reconhecer uma pretensão recebida por aviso direto.",
            WITHDRAW_RECOGNITION_ACTION: "Retirar um reconhecimento institucional atual.",
        }
        return labels[self.action]

    def causes(self):
        return tuple(item for item in (self.evidence_event_id,) if item)


def _actor_is_institution(world, actor):
    return isinstance(actor, EntityRef) and actor.kind in {"polity", "organization"} and (
        actor.id in (world.society.polities if actor.kind == "polity" else world.society.organizations))


def _claim_id(decision_event_id):
    return f"authority-claim:{decision_event_id}"


def _recognition_id(claim_id, actor):
    return f"authority-recognition:{claim_id}:{actor.kind}:{actor.id}"


def _own_settlement_evidence(world, actor, office):
    for report in world.knowledge.settlements_for_actor(actor):
        settlement = world.society.settlements.get(report.settlement_id)
        if (report.publisher_ref == actor and report.channel == "local_settlement_report"
                and settlement is not None and settlement.administrator_id == office.institution_ref.id
                and actor.kind == "polity" and actor.id in settlement.claimant_ids):
            yield "standing_claimant", report.event_id, settlement.id


def _breach_evidence(world, actor, office):
    for obligation in world.relations.obligations.values():
        if obligation.status != "breached" or obligation.breach_event_id is None:
            continue
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if proposal is None or obligation.clause_index >= len(proposal.clauses):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if clause.creditor_ref != actor or clause.debtor_ref != office.institution_ref:
            continue
        if any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
               for notice in world.knowledge.notices.values()):
            yield "unremedied_breach", obligation.breach_event_id, obligation.id


def _occupation_evidence(world, actor, office):
    for settlement in world.society.settlements.values():
        if settlement.administrator_id != office.institution_ref.id or settlement.occupier_id != actor.id:
            continue
        event = next((item for item in reversed(world.events)
                      if item.event_type == "settlement_occupied"
                      and any(delta.owner_kind == "settlement" and delta.owner_id == settlement.id
                              and delta.aspect == "occupier_id" and delta.after == actor.id
                              for delta in item.deltas)), None)
        if event is not None:
            yield "held_occupation", event.id, settlement.id


def _evidence(world, actor, office):
    evidence = (*_own_settlement_evidence(world, actor, office),
                *_breach_evidence(world, actor, office),
                *_occupation_evidence(world, actor, office))
    return tuple(sorted(set(evidence), key=lambda item: (item[0], item[1], item[2])))


def authority_claim_options(world, actor):
    if not _actor_is_institution(world, actor) or not can_actor_act_for(world, actor, actor, "diplomacy"):
        return ()
    options = []
    for office in sorted(world.authority.offices.values(), key=lambda item: item.id):
        if office.institution_ref == actor:
            continue
        for kind, event_id, subject_id in _evidence(world, actor, office):
            if any(claim.stage == "declared" and claim.claimant_ref == actor and claim.office_id == office.id
                   for claim in world.authority.claims.values()):
                continue
            option_id = f"authority-claim-declare:{actor.kind}:{actor.id}:{office.id}:{kind}:{event_id}:{subject_id}"
            options.append(AuthorityClaimOption(option_id, actor, DECLARE_ACTION, office_id=office.id,
                                                evidence_kind=kind, evidence_event_id=event_id,
                                                evidence_subject_id=subject_id))
    for claim in sorted(world.authority.claims.values(), key=lambda item: item.id):
        if claim.claimant_ref == actor and claim.stage == "declared":
            options.append(AuthorityClaimOption(f"authority-claim-withdraw:{claim.id}:{claim.last_event_id}", actor,
                                                WITHDRAW_ACTION, claim_id=claim.id,
                                                evidence_event_id=claim.last_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def authority_recognition_options(world, actor):
    if not _actor_is_institution(world, actor) or not can_actor_act_for(world, actor, actor, "diplomacy"):
        return ()
    known = {notice.claim_id: notice for notice in world.knowledge.authority_claims_for_actor(actor)}
    options = []
    for claim_id, notice in sorted(known.items()):
        claim = world.authority.claims.get(claim_id)
        if claim is None or claim.stage != "declared":
            continue
        office = world.authority.offices.get(claim.office_id)
        if office is None or actor in (claim.claimant_ref, office.institution_ref):
            continue
        recognition_id = _recognition_id(claim.id, actor)
        recognition = world.relations.authority_recognitions.get(recognition_id)
        if recognition is None or recognition.stage != "recognized":
            options.append(AuthorityClaimOption(f"authority-recognition:{claim.id}:{notice.event_id}:{actor.kind}:{actor.id}",
                                                actor, RECOGNIZE_ACTION, claim_id=claim.id,
                                                evidence_event_id=notice.event_id))
        else:
            options.append(AuthorityClaimOption(f"authority-recognition-withdraw:{recognition.id}:{recognition.last_event_id}",
                                                actor, WITHDRAW_RECOGNITION_ACTION, claim_id=claim.id,
                                                evidence_event_id=notice.event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def all_options(world, actor):
    return tuple(sorted((*authority_claim_options(world, actor), *authority_recognition_options(world, actor)),
                        key=lambda item: item.id))


def _decision(world, event_id, action, actor):
    event = next((item for item in world.events if item.id == event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.decision is None
            or event.decision.get("action") != action
            or event.decision.get("actor_ref") != actor.to_dict()):
        raise ValueError("authority claim requires its exact canonical decision")
    return event


def _notice_targets(world, option, office):
    targets = {option.actor_ref, office.institution_ref}
    if option.evidence_kind == "standing_claimant":
        settlement = world.society.settlements.get(option.evidence_subject_id)
        if settlement is not None:
            targets.update(EntityRef("polity", actor_id) for actor_id in settlement.claimant_ids)
    return tuple(sorted(targets, key=lambda item: (item.kind, item.id)))


def _declare(world, option, decision):
    office = world.authority.offices[option.office_id]
    if (option.evidence_kind, option.evidence_event_id, option.evidence_subject_id) not in _evidence(world, option.actor_ref, office):
        raise ValueError("authority claim evidence is stale or unknown")
    if any(item.stage == "declared" and item.office_id == office.id and item.claimant_ref == option.actor_ref
           for item in world.authority.claims.values()):
        raise ValueError("actor already has an active claim to this office")
    claim_id = _claim_id(decision.id)
    claim = AuthorityClaim(id=claim_id, office_id=office.id, claimant_ref=option.actor_ref,
                           declared_day=world.clock.absolute_day, evidence_kind=option.evidence_kind,
                           evidence_event_id=option.evidence_event_id, evidence_subject_id=option.evidence_subject_id,
                           last_event_id="pending")
    targets = _notice_targets(world, option, office)
    notices = tuple(AuthorityClaimNotice(id=authority_claim_notice_id(claim.id, recipient), claim_id=claim.id,
                                         recipient_ref=recipient, event_id="pending",
                                         learned_day=world.clock.absolute_day)
                    for recipient in targets)
    event = record_event(world, "authority_claim_declared", "Uma instituição declarou uma pretensão fundada em evidência canônica.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("authority_claim", claim.id, "stage", None, "declared"),
                                 *(_delta("authority_claim_notice", notice.id, "claim_id", None, claim.id)
                                   for notice in notices)),
                         cause_ids=(decision.id, option.evidence_event_id))
    world.authority.claims[claim.id] = claim.model_copy(update={"last_event_id": event.id})
    for notice in notices:
        world.knowledge.authority_claim_notices[notice.id] = notice.model_copy(update={"event_id": event.id})


def _withdraw(world, option, decision):
    claim = world.authority.claims.get(option.claim_id)
    if claim is None or claim.claimant_ref != option.actor_ref or claim.stage != "declared":
        raise ValueError("authority claim is no longer withdrawable")
    event = record_event(world, "authority_claim_withdrawn", "A instituição retirou sua própria pretensão.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("authority_claim", claim.id, "stage", "declared", "withdrawn"),),
                         cause_ids=(decision.id, claim.last_event_id))
    world.authority.claims[claim.id] = claim.model_copy(update={"stage": "withdrawn", "last_event_id": event.id})
    _lapse_recognitions(world, claim, event.id)


def _recognize(world, option, decision):
    claim = world.authority.claims.get(option.claim_id)
    office = world.authority.offices.get(claim.office_id) if claim is not None else None
    if (claim is None or office is None or claim.stage != "declared" or option.actor_ref in (claim.claimant_ref, office.institution_ref)
            or not any(notice.claim_id == claim.id and notice.recipient_ref == option.actor_ref
                       for notice in world.knowledge.authority_claim_notices.values())):
        raise ValueError("authority recognition is stale or unknown")
    identity = _recognition_id(claim.id, option.actor_ref)
    old = world.relations.authority_recognitions.get(identity)
    if old is not None and old.stage == "recognized":
        raise ValueError("authority recognition already exists")
    recognition = AuthorityRecognition(id=identity, claim_id=claim.id, recognizer_ref=option.actor_ref,
                                       declared_day=world.clock.absolute_day, last_event_id="pending")
    event = record_event(world, "authority_claim_recognized", "Uma instituição reconheceu uma pretensão que recebeu diretamente.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("authority_recognition", identity, "stage",
                                        None if old is None else old.stage, "recognized"),),
                         cause_ids=(decision.id, option.evidence_event_id, claim.last_event_id))
    world.relations.authority_recognitions[identity] = recognition.model_copy(update={"last_event_id": event.id})


def _withdraw_recognition(world, option, decision):
    claim = world.authority.claims.get(option.claim_id)
    identity = _recognition_id(option.claim_id, option.actor_ref)
    recognition = world.relations.authority_recognitions.get(identity)
    if claim is None or recognition is None or recognition.stage != "recognized":
        raise ValueError("authority recognition is no longer withdrawable")
    event = record_event(world, "authority_recognition_withdrawn", "A instituição retirou seu reconhecimento de uma pretensão.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("authority_recognition", identity, "stage", "recognized", "withdrawn"),),
                         cause_ids=(decision.id, recognition.last_event_id))
    world.relations.authority_recognitions[identity] = recognition.model_copy(update={"stage": "withdrawn", "last_event_id": event.id})


def _lapse_recognitions(world, claim, cause_event_id):
    for recognition in tuple(world.relations.authority_recognitions.values()):
        if recognition.claim_id != claim.id or recognition.stage != "recognized":
            continue
        event = record_event(world, "authority_recognition_lapsed", "O reconhecimento terminou porque a pretensão não permanece vigente.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("authority_recognition", recognition.id, "stage", "recognized", "lapsed"),),
                             cause_ids=(cause_event_id, recognition.last_event_id))
        world.relations.authority_recognitions[recognition.id] = recognition.model_copy(update={"stage": "lapsed", "last_event_id": event.id})


def execute_option(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in all_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("authority claim option is stale or unknown")
    decision = _decision(candidate, decision_event_id, option.action, actor)
    if decision.decision != option.decision():
        raise ValueError("authority claim decision selected a different affordance")
    require_authority(candidate, actor, "diplomacy")
    if option.action == DECLARE_ACTION:
        _declare(candidate, option, decision)
    elif option.action == WITHDRAW_ACTION:
        _withdraw(candidate, option, decision)
    elif option.action == RECOGNIZE_ACTION:
        _recognize(candidate, option, decision)
    else:
        _withdraw_recognition(candidate, option, decision)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.authority.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)


def lapse_invalid_claims(world):
    """Monthly closure revokes only claims whose original category stopped being true."""
    for claim in tuple(sorted(world.authority.claims.values(), key=lambda item: item.id)):
        if claim.stage != "declared":
            continue
        office = world.authority.offices.get(claim.office_id)
        valid = office is not None and (claim.evidence_kind, claim.evidence_event_id, claim.evidence_subject_id) in _evidence(world, claim.claimant_ref, office)
        if valid:
            continue
        recognitions = tuple(item for item in world.relations.authority_recognitions.values()
                             if item.claim_id == claim.id and item.stage == "recognized")
        event = record_event(world, "authority_claim_lapsed", "Uma pretensão deixou de ter sua evidência material vigente.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("authority_claim", claim.id, "stage", "declared", "lapsed"),
                                     *(_delta("authority_recognition", item.id, "stage", "recognized", "lapsed")
                                       for item in recognitions)),
                             cause_ids=(claim.last_event_id, claim.evidence_event_id))
        updated = claim.model_copy(update={"stage": "lapsed", "last_event_id": event.id})
        world.authority.claims[claim.id] = updated
        for recognition in recognitions:
            world.relations.authority_recognitions[recognition.id] = recognition.model_copy(
                update={"stage": "lapsed", "last_event_id": event.id})


def provider_actors(world):
    actors = {office.institution_ref for office in world.authority.offices.values()
              if office.institution_ref.kind in {"polity", "organization"}}
    actors.update(item.claimant_ref for item in world.authority.claims.values())
    actors.update(item.recipient_ref for item in world.knowledge.authority_claim_notices.values())
    return tuple(sorted(actors, key=lambda item: (item.kind, item.id)))


__all__ = ["authority_claim_options", "authority_recognition_options", "all_options", "execute_option",
           "lapse_invalid_claims", "provider_actors", "AuthorityClaimOption"]
