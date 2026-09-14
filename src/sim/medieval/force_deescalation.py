"""A narrow bilateral promise to leave an armed contact without combat."""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.governance.authority import require_authority
from src.classes.governance.diplomacy import (WithdrawalClause, force_deescalation_intent,
                                              force_deescalation_response_intent)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .commitments import conclude_obligation
from .diplomacy import offer_proposal, require_decision, respond_proposal
from .events import record_event
from .force import _active_pair, _begin_withdrawal, withdrawal_options


OFFER_ACTION = "offer_force_deescalation"
RESPONSE_ACTION = "respond_force_deescalation"
FULFILL_ACTION = "fulfill_force_withdrawal"
OFFER_WINDOW_DAYS = 1
WITHDRAWAL_DUE_DAYS = 3


@dataclass(frozen=True)
class ForceDeescalationOffer:
    id: Identity
    actor_ref: EntityRef
    notice_id: Identity
    standoff_id: Identity
    kind: str

    def decision(self):
        return force_deescalation_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class ForceDeescalationResponse:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    response: str

    def decision(self):
        return force_deescalation_response_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class ForceWithdrawalFulfillment:
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity
    withdrawal_option_id: Identity

    def decision(self):
        return {"action": FULFILL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _known_notice(world, actor, proposal_id):
    return any(notice.recipient_ref == actor and notice.proposal_id == proposal_id
               for notice in world.knowledge.notices.values())


def _open_offer(world, actor, standoff_id):
    return any(proposal.proposal_kind == "force_deescalation" and proposal.status == "offered"
               and proposal.proposer_ref == actor
               and any(clause.kind == "withdrawal" and clause.standoff_id == standoff_id
                       for clause in proposal.clauses)
               for proposal in world.relations.proposals.values())


def force_deescalation_offer_options(world, actor, *, notice_id=None):
    """A contact participant may bind itself, or both current columns, to leave.

    The provider gets no rival route, bag, stock or ability reading.  The
    engine only enumerates a promise when the proposer itself has a current
    withdrawal path; the other party is deliberately not pre-judged.
    """
    options = []
    for notice in world.knowledge.force_contacts_for_actor(actor):
        if notice_id is not None and notice.id != notice_id:
            continue
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        if (standoff is None or standoff.stage != "active" or _open_offer(world, actor, standoff.id)
                or _active_pair(world, standoff) is None):
            continue
        if not withdrawal_options(world, actor, detachment_id=notice.own_detachment_id):
            continue
        base = f"force-deescalation:{notice.id}:{standoff.last_event_id}"
        options.extend((
            ForceDeescalationOffer(f"{base}:mutual", actor, notice.id, standoff.id, "mutual"),
            ForceDeescalationOffer(f"{base}:unilateral-self", actor, notice.id, standoff.id, "unilateral_self"),
        ))
    return tuple(sorted(options, key=lambda item: item.id))


def offer_force_deescalation(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in force_deescalation_offer_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("force deescalation option is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "military")
    notice = candidate.knowledge.force_contact_notices[option.notice_id]
    standoff = candidate.society.force_standoffs[option.standoff_id]
    pair = _active_pair(candidate, standoff)
    if pair is None:
        raise ValueError("armed contact is no longer current")
    own = candidate.society.detachments[notice.own_detachment_id]
    other = next(item for item in pair if item.id != own.id)
    due_day = candidate.clock.absolute_day + WITHDRAWAL_DUE_DAYS
    clauses = [WithdrawalClause(debtor_ref=actor, creditor_ref=other.owner_ref, due_day=due_day,
                                standoff_id=standoff.id, detachment_id=own.id)]
    if option.kind == "mutual":
        clauses.append(WithdrawalClause(debtor_ref=other.owner_ref, creditor_ref=actor, due_day=due_day,
                                        standoff_id=standoff.id, detachment_id=other.id))
    proposal = offer_proposal(
        candidate, actor, other.owner_ref, tuple(clauses), candidate.clock.absolute_day + OFFER_WINDOW_DAYS,
        decision_event_id=decision_event_id, intent=option.decision(), proposal_kind="force_deescalation",
        request_affordance_id=option.id)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def force_deescalation_response_options(world, actor, *, notice_id=None):
    options = []
    notices = {notice.standoff_id for notice in world.knowledge.force_contacts_for_actor(actor)
               if notice_id is None or notice.id == notice_id}
    for proposal in world.relations.proposals.values():
        standoff = next((world.society.force_standoffs.get(clause.standoff_id) for clause in proposal.clauses
                         if clause.kind == "withdrawal"), None)
        if (proposal.proposal_kind != "force_deescalation" or proposal.status != "offered"
                or proposal.counterparty_ref != actor or proposal.expires_day <= world.clock.absolute_day
                or not _known_notice(world, actor, proposal.id)
                or standoff is None or standoff.stage != "active" or _active_pair(world, standoff) is None
                or not any(clause.standoff_id in notices for clause in proposal.clauses if clause.kind == "withdrawal")):
            continue
        base = f"force-deescalation-response:{proposal.id}:{proposal.last_event_id}"
        options.extend((ForceDeescalationResponse(f"{base}:accept", actor, proposal.id, "accept"),
                        ForceDeescalationResponse(f"{base}:reject", actor, proposal.id, "reject")))
    return tuple(sorted(options, key=lambda item: item.id))


def respond_force_deescalation(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in force_deescalation_response_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("force deescalation response is stale or unknown")
    proposal = respond_proposal(candidate, option.proposal_id, option.response, decision_event_id=decision_event_id,
                                intent=option.decision())
    if option.response == "accept":
        from .force_contact_policy import schedule_contact_review
        standoff_id = next(clause.standoff_id for clause in proposal.clauses if clause.kind == "withdrawal")
        for notice in candidate.knowledge.force_contact_notices.values():
            if notice.standoff_id == standoff_id:
                schedule_contact_review(candidate, notice, candidate.clock.absolute_day + 1)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def force_withdrawal_fulfillment_options(world, actor, *, notice_id=None):
    notice_standoffs = {notice.standoff_id for notice in world.knowledge.force_contacts_for_actor(actor)
                        if notice_id is None or notice.id == notice_id}
    options = []
    for obligation in world.relations.obligations.values():
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if proposal is None or obligation.status != "active" or not _known_notice(world, actor, proposal.id):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if (clause.kind != "withdrawal" or clause.debtor_ref != actor or clause.standoff_id not in notice_standoffs
                or world.clock.absolute_day > clause.due_day):
            continue
        for withdrawal in withdrawal_options(world, actor, detachment_id=clause.detachment_id):
            options.append(ForceWithdrawalFulfillment(
                id=f"force-withdrawal-fulfillment:{obligation.id}:{obligation.last_event_id}:{withdrawal.id}",
                actor_ref=actor, obligation_id=obligation.id, withdrawal_option_id=withdrawal.id))
    return tuple(sorted(options, key=lambda item: item.id))


def fulfill_force_withdrawal(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in force_withdrawal_fulfillment_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("force withdrawal fulfillment is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "military")
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    withdrawal = next((item for item in withdrawal_options(candidate, actor, detachment_id=clause.detachment_id)
                       if item.id == option.withdrawal_option_id), None)
    if withdrawal is None:
        raise ValueError("force withdrawal fulfillment is stale or unknown")
    material = _begin_withdrawal(candidate, actor, withdrawal, decision_event_id)
    conclude_obligation(candidate, obligation, "fulfilled", material.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.obligations[option.obligation_id]


__all__ = ["FULFILL_ACTION", "OFFER_ACTION", "RESPONSE_ACTION", "force_deescalation_offer_options",
           "force_deescalation_response_options", "force_withdrawal_fulfillment_options",
           "fulfill_force_withdrawal", "offer_force_deescalation", "respond_force_deescalation"]
