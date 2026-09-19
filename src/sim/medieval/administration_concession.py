"""A bounded bilateral concession of settlement administration under real pressure.

An armed occupier may offer terms only while its own prepared, supplied column
still creates the existing investment and faces the current administrator's
column.  Acceptance creates obligations only.  Society changes administration
later, and only when that still-current administrator makes a new decision.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.diplomacy import (AdministrationTransferClause, WithdrawalClause,
                                              administration_concession_intent,
                                              administration_concession_response_intent)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .commitments import conclude_obligation
from .diplomacy import offer_proposal, require_decision, respond_proposal
from .economy import _causes, _delta
from .events import record_event
from .force import _active_pair


OFFER_ACTION = "offer_administration_concession"
RESPONSE_ACTION = "respond_administration_concession"
FULFILL_ACTION = "fulfill_administration_transfer"
OFFER_WINDOW_DAYS = 1
TRANSFER_DUE_DAYS = 2
WITHDRAWAL_DUE_DAYS = 3


@dataclass(frozen=True)
class AdministrationConcessionOffer:
    id: Identity
    actor_ref: EntityRef
    notice_id: Identity
    settlement_id: Identity
    investment_id: Identity
    standoff_id: Identity
    detachment_id: Identity
    report_event_id: Identity
    kind: str = "contact"
    breach_event_id: Identity | None = None

    def decision(self):
        return administration_concession_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class AdministrationConcessionResponse:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    response: str

    def decision(self):
        return administration_concession_response_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class AdministrationTransferFulfillment:
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity

    def decision(self):
        return {"action": FULFILL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _own_current_report(world, actor, settlement_id):
    report = world.knowledge.settlement_report(actor, settlement_id)
    return (report if report is not None and report.recipient_ref == actor and report.publisher_ref == actor
            and report.channel == "local_settlement_report"
            and report.observed_day == world.clock.absolute_day else None)


def _active_investment(world, actor, detachment_id, settlement_id):
    return next((item for _, item in sorted(world.society.settlement_investments.items())
                 if item.actor_ref == actor and item.detachment_id == detachment_id
                 and item.settlement_id == settlement_id and item.stage == "active"), None)


def _duplicate(world, settlement_id):
    return any(proposal.proposal_kind == "administration_concession"
               and proposal.status in {"offered", "accepted"}
               and any(clause.kind == "administration_transfer" and clause.settlement_id == settlement_id
                       for clause in proposal.clauses)
               for proposal in world.relations.proposals.values())


def _active_postwar_transfer(world, settlement_id):
    """Whether an open/current transfer already binds this settlement."""
    for proposal in world.relations.proposals.values():
        if proposal.proposal_kind != "administration_concession" or proposal.status not in {"offered", "accepted"}:
            continue
        for index, clause in enumerate(proposal.clauses):
            if clause.kind != "administration_transfer" or clause.settlement_id != settlement_id:
                continue
            obligation = world.relations.obligations.get(f"{proposal.id}:term:{index}")
            if obligation is None or obligation.status in {"active"}:
                return True
    return False


def _breached_postwar_transfer(world, settlement_id):
    """Return the latest concluded transfer breach for a possible repair."""
    candidates = []
    for proposal in world.relations.proposals.values():
        if proposal.proposal_kind != "administration_concession":
            continue
        for index, clause in enumerate(proposal.clauses):
            if clause.kind != "administration_transfer" or clause.settlement_id != settlement_id:
                continue
            obligation = world.relations.obligations.get(f"{proposal.id}:term:{index}")
            if obligation is not None and obligation.status == "breached" and obligation.breach_event_id:
                candidates.append((obligation.breach_event_id, obligation))
    return max(candidates, key=lambda item: item[0]) if candidates else None


def _postwar_state(world, actor, settlement_id):
    """Current occupation/control can open a political transfer without a standoff.

    This is deliberately a single administration term.  It does not grant
    control, troops, stock or ownership; those facts must already exist and
    remain valid until the administrator later fulfils the obligation.
    """
    settlement = world.society.settlements.get(settlement_id)
    control = world.society.territorial_controls.get(f"territorial-control:{settlement_id}")
    if (settlement is None or settlement.occupier_id != actor.id
            or settlement.administrator_id in {None, actor.id}
            or control is None or control.stage != "active" or control.controller_id != actor.id):
        return None
    detachment = None
    garrison = None
    for candidate in sorted(world.society.garrisons.values(), key=lambda item: item.id):
        current = world.society.detachments.get(candidate.detachment_id)
        if (candidate.stage == "active" and candidate.settlement_id == settlement_id
                and current is not None and current.owner_ref == actor
                and current.stage == "present" and current.location_id == settlement_id
                and current.provisions >= current.count):
            garrison, detachment = candidate, current
            break
    report = _own_current_report(world, actor, settlement_id)
    if (garrison is None or detachment is None or report is None
            or any(item.phase in {"sieging", "breached"} and item.settlement_id == settlement_id
                   for item in world.society.siege_campaigns.values())):
        return None
    counterparty = EntityRef("polity", settlement.administrator_id)
    return settlement, control, garrison, detachment, report, counterparty


def _offer_state(world, actor, notice, *, ignore_duplicate=False):
    standoff = world.society.force_standoffs.get(notice.standoff_id)
    if standoff is None or standoff.stage != "active" or _active_pair(world, standoff) is None:
        return None
    detachment = world.society.detachments.get(notice.own_detachment_id)
    if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
            or detachment.location_id != notice.settlement_id or detachment.provisions < detachment.count):
        return None
    settlement = world.society.settlements.get(notice.settlement_id)
    report = _own_current_report(world, actor, notice.settlement_id)
    if (settlement is None or settlement.occupier_id != actor.id
            or settlement.administrator_id is None
            or notice.counterparty_ref != EntityRef("polity", settlement.administrator_id)
            or report is None
            or (not ignore_duplicate and _duplicate(world, settlement.id))):
        return None
    investment = _active_investment(world, actor, detachment.id, settlement.id)
    if investment is None:
        return None
    return settlement, detachment, standoff, investment, report


def administration_concession_offer_options(world, actor, *, notice_id=None):
    """Only a current force-contact review can enumerate this narrow offer."""
    if not (can_actor_act_for(world, actor, actor, "diplomacy")
            and can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for notice in world.knowledge.force_contacts_for_actor(actor):
        if notice_id is not None and notice.id != notice_id:
            continue
        state = _offer_state(world, actor, notice)
        if state is None:
            continue
        settlement, detachment, standoff, investment, report = state
        options.append(AdministrationConcessionOffer(
            id=(f"administration-concession:{notice.id}:{investment.last_event_id}:{standoff.last_event_id}:"
                f"{detachment.last_event_id}:{report.event_id}"),
            actor_ref=actor, notice_id=notice.id, settlement_id=settlement.id, investment_id=investment.id,
            standoff_id=standoff.id, detachment_id=detachment.id, report_event_id=report.event_id))
    # A sustained occupation may also seek a political settlement after the
    # immediate contact path is no longer the only material basis.  This uses
    # the same proposal/obligation owner, but contains no automatic withdrawal.
    if notice_id is None:
        for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
            state = _postwar_state(world, actor, settlement.id)
            if state is None or _active_postwar_transfer(world, settlement.id):
                continue
            current, control, garrison, detachment, report, _counterparty = state
            breached = _breached_postwar_transfer(world, settlement.id)
            kind = "postwar_remediation" if breached is not None else "postwar"
            breach_event_id = breached[0] if breached is not None else None
            options.append(AdministrationConcessionOffer(
                id=(f"administration-settlement:{settlement.id}:{control.last_event_id}:"
                    f"{garrison.last_event_id}:{detachment.last_event_id}:{report.event_id}:{breach_event_id or '-'}"),
                actor_ref=actor, notice_id="-", settlement_id=settlement.id,
                investment_id="-", standoff_id="-", detachment_id=detachment.id,
                report_event_id=report.event_id, kind=kind, breach_event_id=breach_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def offer_administration_concession(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in administration_concession_offer_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("administration concession option is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "military")
    if option.kind in {"postwar", "postwar_remediation"}:
        state = _postwar_state(candidate, actor, option.settlement_id)
        if state is None:
            raise ValueError("political settlement is no longer materially possible")
        settlement, _control, _garrison, detachment, _report, counterparty = state
        transfer_due = candidate.clock.absolute_day + TRANSFER_DUE_DAYS
        clauses = (AdministrationTransferClause(
            debtor_ref=counterparty, creditor_ref=actor, due_day=transfer_due,
            settlement_id=settlement.id),)
    else:
        notice = candidate.knowledge.force_contact_notices[option.notice_id]
        state = _offer_state(candidate, actor, notice)
        if state is None:
            raise ValueError("administration concession is no longer possible")
        settlement, detachment, standoff, investment, report = state
        counterparty = EntityRef("polity", settlement.administrator_id)
        transfer_due = candidate.clock.absolute_day + TRANSFER_DUE_DAYS
        clauses = (
            AdministrationTransferClause(debtor_ref=counterparty, creditor_ref=actor, due_day=transfer_due,
                                        settlement_id=settlement.id),
            WithdrawalClause(debtor_ref=actor, creditor_ref=counterparty,
                             due_day=candidate.clock.absolute_day + WITHDRAWAL_DUE_DAYS, depends_on=(0,),
                             standoff_id=standoff.id, detachment_id=detachment.id),
        )
    proposal = offer_proposal(
        candidate, actor, counterparty, clauses, candidate.clock.absolute_day + OFFER_WINDOW_DAYS,
        decision_event_id=decision_event_id, intent=option.decision(), proposal_kind="administration_concession",
        request_affordance_id=option.id,
        extra_cause_ids=((option.breach_event_id,) if option.breach_event_id else ()))
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def _proposal_still_current(world, proposal):
    if proposal.proposal_kind != "administration_concession":
        return False
    if len(proposal.clauses) == 1 and proposal.clauses[0].kind == "administration_transfer":
        return _postwar_state(world, proposal.proposer_ref, proposal.clauses[0].settlement_id) is not None
    if len(proposal.clauses) != 2:
        return False
    transfer, withdrawal = proposal.clauses
    if transfer.kind != "administration_transfer" or withdrawal.kind != "withdrawal":
        return False
    notice = next((notice for notice in world.knowledge.force_contacts_for_actor(proposal.proposer_ref)
                   if (notice.standoff_id == withdrawal.standoff_id and notice.own_detachment_id == withdrawal.detachment_id
                       and notice.counterparty_ref == proposal.counterparty_ref)), None)
    return notice is not None and _offer_state(world, proposal.proposer_ref, notice, ignore_duplicate=True) is not None


def administration_concession_response_options(world, actor, *, notice_id=None):
    options = []
    known = tuple(notice for notice in world.knowledge.force_contacts_for_actor(actor)
                  if notice_id is None or notice.id == notice_id)
    for proposal in world.relations.proposals.values():
        postwar = len(proposal.clauses) == 1 and proposal.clauses[0].kind == "administration_transfer"
        known_proposal = any(notice.recipient_ref == actor and notice.proposal_id == proposal.id
                             for notice in world.knowledge.notices.values())
        if (proposal.proposal_kind != "administration_concession" or proposal.status != "offered"
                or proposal.counterparty_ref != actor or proposal.expires_day <= world.clock.absolute_day
                or not _proposal_still_current(world, proposal)
                or (not postwar and not any(notice.standoff_id == next((clause.standoff_id for clause in proposal.clauses
                                                                        if clause.kind == "withdrawal"), None)
                                             and notice.settlement_id == next((clause.settlement_id for clause in proposal.clauses
                                                                               if clause.kind == "administration_transfer"), None)
                                             and notice.counterparty_ref == proposal.proposer_ref for notice in known))
                or (postwar and not known_proposal)):
            continue
        base = f"administration-concession-response:{proposal.id}:{proposal.last_event_id}"
        options.extend((AdministrationConcessionResponse(f"{base}:accept", actor, proposal.id, "accept"),
                        AdministrationConcessionResponse(f"{base}:reject", actor, proposal.id, "reject")))
    return tuple(sorted(options, key=lambda item: item.id))


def respond_administration_concession(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in administration_concession_response_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("administration concession response is stale or unknown")
    proposal = respond_proposal(candidate, option.proposal_id, option.response, decision_event_id=decision_event_id,
                                intent=option.decision())
    if option.response == "accept":
        withdrawal = next((clause for clause in proposal.clauses if clause.kind == "withdrawal"), None)
        if withdrawal is not None:
            from .force_contact_policy import schedule_contact_review
            for notice in candidate.knowledge.force_contact_notices.values():
                if notice.standoff_id == withdrawal.standoff_id:
                    schedule_contact_review(candidate, notice, candidate.clock.absolute_day + 1)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def administration_transfer_fulfillment_options(world, actor):
    if not can_actor_act_for(world, actor, actor, "diplomacy"):
        return ()
    options = []
    for obligation in world.relations.obligations.values():
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if proposal is None or proposal.proposal_kind != "administration_concession" or obligation.status != "active":
            continue
        clause = proposal.clauses[obligation.clause_index]
        if (clause.kind != "administration_transfer" or clause.debtor_ref != actor
                or world.clock.absolute_day > clause.due_day):
            continue
        settlement = world.society.settlements.get(clause.settlement_id)
        if settlement is None or settlement.administrator_id != actor.id:
            continue
        options.append(AdministrationTransferFulfillment(
            id=f"administration-transfer-fulfillment:{obligation.id}:{obligation.last_event_id}:{settlement.administrator_id}",
            actor_ref=actor, obligation_id=obligation.id))
    return tuple(sorted(options, key=lambda item: item.id))


def fulfill_administration_transfer(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in administration_transfer_fulfillment_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("administration transfer fulfillment is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    settlement = candidate.society.settlements[clause.settlement_id]
    before = settlement.administrator_id
    candidate.society.transfer_administration(clause.settlement_id, actor.id, clause.creditor_ref.id)
    material = record_event(
        candidate, "settlement_administration_transferred",
        "A administração do assentamento foi cedida por decisão atual de seu administrador.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("settlement", settlement.id, "administrator_id", before, clause.creditor_ref.id),),
        cause_ids=_causes(decision_event_id, obligation.last_event_id, proposal.last_event_id),
    )
    conclude_obligation(candidate, obligation, "fulfilled", material.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.obligations[option.obligation_id]


__all__ = ["FULFILL_ACTION", "OFFER_ACTION", "RESPONSE_ACTION",
           "administration_concession_offer_options", "administration_concession_response_options",
           "administration_transfer_fulfillment_options", "fulfill_administration_transfer",
           "offer_administration_concession", "respond_administration_concession"]
