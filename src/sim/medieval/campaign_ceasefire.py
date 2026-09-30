"""Bilateral ceasefire terms for one active siege campaign.

The proposal layer owns only the promise.  Society/Force still owns each
column and executes each withdrawal independently after an accepted obligation
is selected by its debtor.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.diplomacy import (
    CampaignWithdrawalClause,
    campaign_ceasefire_intent,
    campaign_ceasefire_response_intent,
)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .commitments import conclude_obligation
from .diplomacy import disclose, offer_proposal, require_decision, respond_proposal
from .economy import _delta
from .events import record_event
from .force import GarrisonOption, _begin_withdrawal, _withdraw_garrison, withdrawal_options
from .institutional_decision_turn import DiscretionaryAdapter
from .institutional_memory import (apply_memory_creation, apply_reinforcement,
                                   memory_creation_deltas, memories_of, reinforcement_deltas)
from .siege_campaign import (
    _execute_siege_withdrawal,
    siege_campaign_withdrawal_options,
)


OFFER_ACTION = "offer_campaign_ceasefire"
RESPONSE_ACTION = "respond_campaign_ceasefire"
FULFILL_ACTION = "fulfill_campaign_ceasefire"
REMEDIATE_ACTION = "remediate_campaign_withdrawal"
OFFER_WINDOW_DAYS = 3
WITHDRAWAL_DUE_DAYS = 3


@dataclass(frozen=True)
class CampaignCeasefireOffer:
    id: Identity
    actor_ref: EntityRef
    campaign_id: Identity
    kind: str

    def decision(self):
        return campaign_ceasefire_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class CampaignCeasefireResponse:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    response: str

    def decision(self):
        return campaign_ceasefire_response_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class CampaignCeasefireFulfillment:
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity
    campaign_id: Identity
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": FULFILL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CampaignWithdrawalRemediation:
    """A debtor's later material withdrawal repairs, but does not erase, breach."""
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity
    campaign_id: Identity
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]
    breach_event_id: Identity

    def decision(self):
        return {"action": REMEDIATE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _known_notice(world, actor, proposal_id):
    return any(notice.recipient_ref == actor and notice.proposal_id == proposal_id
               for notice in world.knowledge.notices.values())


def _campaign_parts(world, campaign_id):
    campaign = world.society.siege_campaigns.get(campaign_id)
    garrison = world.society.garrisons.get(campaign.defender_garrison_id) if campaign else None
    attacker = world.society.detachments.get(campaign.attacker_detachment_id) if campaign else None
    defender = world.society.detachments.get(garrison.detachment_id) if garrison else None
    if (campaign is None or campaign.phase not in {"sieging", "breached"} or garrison is None
            or attacker is None or defender is None or attacker.stage != "present"
            or defender.stage != "present" or attacker.location_id != campaign.settlement_id
            or defender.location_id != campaign.settlement_id):
        return None
    return campaign, attacker, defender


def _defender_withdrawable(world, campaign):
    """Whether the defender still has a physical presence that can withdraw.

    Siege can collapse the duty while the real detachment remains present.
    A ceasefire can still require that force's independent physical withdrawal;
    fulfillment ends the duty only when it is still active.
    """
    garrison = world.society.garrisons.get(campaign.defender_garrison_id)
    detachment = (world.society.detachments.get(garrison.detachment_id)
                  if garrison is not None else None)
    return (garrison is not None and garrison.stage in {"active", "collapsed"}
            and detachment is not None and detachment.stage == "present"
            and detachment.location_id == campaign.settlement_id)


def _schedule_contact_reviews(world, campaign):
    """Reopen each participant's own contact turn for reply or fulfillment."""
    from .force_contact_policy import schedule_contact_review

    garrison = world.society.garrisons.get(campaign.defender_garrison_id)
    detachment_ids = {campaign.attacker_detachment_id}
    if garrison is not None:
        detachment_ids.add(garrison.detachment_id)
    for notice in world.knowledge.force_contact_notices.values():
        if (notice.own_detachment_id in detachment_ids
                and notice.settlement_id == campaign.settlement_id):
            schedule_contact_review(world, notice, world.clock.absolute_day + 1)


def _open_offer(world, campaign_id):
    for proposal in world.relations.proposals.values():
        if (proposal.proposal_kind != "campaign_ceasefire"
                or proposal.status not in {"offered", "accepted"}):
            continue
        for index, clause in enumerate(proposal.clauses):
            if clause.kind != "campaign_withdrawal" or clause.campaign_id != campaign_id:
                continue
            if proposal.status == "offered":
                return True
            obligation = world.relations.obligations.get(f"{proposal.id}:term:{index}")
            if obligation is not None and obligation.status == "active":
                return True
    return False


def campaign_ceasefire_offer_options(world, actor):
    if not (isinstance(actor, EntityRef)
            and can_actor_act_for(world, actor, actor, "diplomacy")
            and can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for campaign in sorted(world.society.siege_campaigns.values(), key=lambda item: item.id):
        parts = _campaign_parts(world, campaign.id)
        if parts is None or _open_offer(world, campaign.id):
            continue
        _campaign, attacker_detachment, defender_detachment = parts
        if actor == campaign.attacker_ref:
            own_detachment = attacker_detachment
            own_withdrawals = tuple(item for item in siege_campaign_withdrawal_options(world, actor)
                                    if item.campaign_id == campaign.id)
        elif actor == defender_detachment.owner_ref:
            if not _defender_withdrawable(world, campaign):
                continue
            own_detachment = defender_detachment
            own_withdrawals = tuple(item for item in withdrawal_options(
                world, actor, detachment_id=defender_detachment.id,
                allow_open_campaign_supply=True, campaign_authorized=True))
        else:
            continue
        if not own_withdrawals:
            continue
        base = (f"campaign-ceasefire:{campaign.id}:{campaign.last_event_id}:"
                f"{own_detachment.last_event_id}:{own_withdrawals[0].id}")
        options.append(CampaignCeasefireOffer(
            f"{base}:unilateral-self", actor, campaign.id, "unilateral_self"))
        if campaign.phase in {"sieging", "breached"}:
            options.append(CampaignCeasefireOffer(
                f"{base}:mutual", actor, campaign.id, "mutual"))
    return tuple(sorted(options, key=lambda item: item.id))


def offer_campaign_ceasefire(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in campaign_ceasefire_offer_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign ceasefire option is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "military")
    parts = _campaign_parts(candidate, option.campaign_id)
    if parts is None:
        raise ValueError("campaign ceasefire is no longer current")
    campaign, attacker, defender = parts
    if actor == campaign.attacker_ref:
        own_detachment, counterpart_detachment = attacker, defender
    elif actor == defender.owner_ref:
        own_detachment, counterpart_detachment = defender, attacker
    else:
        raise ValueError("campaign ceasefire actor is not a current participant")
    # The withdrawal obligation begins after the proposal window closes; this
    # keeps its material deadline later than the offer's expiry.
    due_day = (candidate.clock.absolute_day + OFFER_WINDOW_DAYS
               + WITHDRAWAL_DUE_DAYS)
    clauses = [CampaignWithdrawalClause(
        debtor_ref=actor, creditor_ref=counterpart_detachment.owner_ref, due_day=due_day,
        campaign_id=campaign.id, detachment_id=own_detachment.id)]
    if option.kind == "mutual":
        clauses.append(CampaignWithdrawalClause(
            debtor_ref=counterpart_detachment.owner_ref, creditor_ref=actor, due_day=due_day,
            campaign_id=campaign.id, detachment_id=counterpart_detachment.id))
    proposal = offer_proposal(
        candidate, actor, counterpart_detachment.owner_ref, tuple(clauses),
        candidate.clock.absolute_day + OFFER_WINDOW_DAYS,
        decision_event_id=decision_event_id, intent=option.decision(),
        proposal_kind="campaign_ceasefire", request_affordance_id=option.id)
    _schedule_contact_reviews(candidate, campaign)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def campaign_ceasefire_response_options(world, actor):
    options = []
    for proposal in sorted(world.relations.proposals.values(), key=lambda item: item.id):
        if (proposal.proposal_kind != "campaign_ceasefire" or proposal.status != "offered"
                or proposal.counterparty_ref != actor or proposal.expires_day <= world.clock.absolute_day
                or not _known_notice(world, actor, proposal.id)):
            continue
        campaign_id = next((clause.campaign_id for clause in proposal.clauses
                            if clause.kind == "campaign_withdrawal"), None)
        if campaign_id is None or _campaign_parts(world, campaign_id) is None:
            continue
        base = f"campaign-ceasefire-response:{proposal.id}:{proposal.last_event_id}"
        options.extend((CampaignCeasefireResponse(f"{base}:accept", actor, proposal.id, "accept"),
                        CampaignCeasefireResponse(f"{base}:reject", actor, proposal.id, "reject")))
    return tuple(sorted(options, key=lambda item: item.id))


def respond_campaign_ceasefire(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in campaign_ceasefire_response_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign ceasefire response is stale or unknown")
    proposal = respond_proposal(candidate, option.proposal_id, option.response,
                                decision_event_id=decision_event_id, intent=option.decision())
    if proposal.status == "accepted":
        campaign_id = next((clause.campaign_id for clause in proposal.clauses
                            if clause.kind == "campaign_withdrawal"), None)
        campaign = candidate.society.siege_campaigns.get(campaign_id)
        if campaign is not None:
            _schedule_contact_reviews(candidate, campaign)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def campaign_ceasefire_fulfillment_options(world, actor):
    if not (isinstance(actor, EntityRef)
            and can_actor_act_for(world, actor, actor, "diplomacy")
            and can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for obligation in sorted(world.relations.obligations.values(), key=lambda item: item.id):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind != "campaign_ceasefire"
                or proposal.status != "accepted" or obligation.status != "active"):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if (clause.kind != "campaign_withdrawal" or clause.debtor_ref != actor
                or world.clock.absolute_day > clause.due_day):
            continue
        campaign = world.society.siege_campaigns.get(clause.campaign_id)
        if campaign is None or campaign.phase not in {"sieging", "breached", "withdrawn"}:
            continue
        if actor == campaign.attacker_ref:
            routes = tuple(item for item in siege_campaign_withdrawal_options(world, actor)
                           if item.campaign_id == clause.campaign_id
                           and item.detachment_id == clause.detachment_id)
        elif _defender_withdrawable(world, campaign):
            routes = tuple(item for item in withdrawal_options(
                world, actor, detachment_id=clause.detachment_id,
                allow_open_campaign_supply=True, campaign_authorized=True))
        else:
            routes = ()
        for route in routes:
            options.append(CampaignCeasefireFulfillment(
                id=f"campaign-ceasefire-fulfillment:{obligation.id}:{obligation.last_event_id}:{route.id}",
                actor_ref=actor, obligation_id=obligation.id, campaign_id=clause.campaign_id,
                detachment_id=clause.detachment_id, destination_id=route.destination_id,
                route_ids=route.route_ids))
    return tuple(sorted(options, key=lambda item: item.id))


def fulfill_campaign_ceasefire(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in campaign_ceasefire_fulfillment_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign ceasefire fulfillment is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "military")
    obligation = candidate.relations.obligations[option.obligation_id]
    clause = candidate.relations.proposals[obligation.proposal_id].clauses[obligation.clause_index]
    if actor == candidate.society.siege_campaigns[clause.campaign_id].attacker_ref:
        route = next((item for item in siege_campaign_withdrawal_options(candidate, actor)
                      if item.campaign_id == clause.campaign_id and item.detachment_id == clause.detachment_id
                      and item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
        if route is None:
            raise ValueError("campaign ceasefire attacker route is stale")
        _execute_siege_withdrawal(candidate, actor, route, decision_event_id,
                                  selected_affordance_id=option.id)
        material_event_id = candidate.society.siege_campaigns[clause.campaign_id].last_event_id
    else:
        route = next((item for item in withdrawal_options(
            candidate, actor, detachment_id=clause.detachment_id,
            allow_open_campaign_supply=True, campaign_authorized=True)
                      if item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
        if route is None:
            raise ValueError("campaign ceasefire defender route is stale")
        # Accepting withdrawal abandons an open supply request, not its cargo.
        # The option has already excluded pending parcels and a stocked bag.
        from .campaign_supply import _lapse_campaign_notices
        _lapse_campaign_notices(candidate, clause.detachment_id, decision_event_id)
        garrison = next(item for item in candidate.society.garrisons.values()
                        if item.detachment_id == clause.detachment_id)
        if garrison.stage == "active":
            _withdraw_garrison(candidate, actor, GarrisonOption(
                id=f"campaign-ceasefire-garrison:{garrison.id}:{garrison.last_event_id}",
                actor_ref=actor, detachment_id=clause.detachment_id,
                settlement_id=garrison.settlement_id, account_id=garrison.account_id,
                daily_wage=0, kind="withdraw"),
                next(item for item in candidate.events if item.id == decision_event_id))
        material_event = _begin_withdrawal(candidate, actor, route, decision_event_id,
                                           selected_affordance_id=option.id)
        material_event_id = material_event.id
    conclude_obligation(candidate, obligation, "fulfilled", material_event_id)
    _schedule_contact_reviews(candidate, candidate.society.siege_campaigns[clause.campaign_id])
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.obligations[option.obligation_id]


def campaign_withdrawal_remediation_options(world, actor):
    """Offer only a noticed debtor's current physical way to repair a breach."""
    if not (isinstance(actor, EntityRef)
            and can_actor_act_for(world, actor, actor, "diplomacy")
            and can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for obligation in sorted(world.relations.obligations.values(), key=lambda item: item.id):
        if obligation.status != "breached" or obligation.breach_event_id is None:
            continue
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if proposal is None or proposal.proposal_kind != "campaign_ceasefire":
            continue
        clause = proposal.clauses[obligation.clause_index]
        if clause.kind != "campaign_withdrawal" or clause.debtor_ref != actor:
            continue
        if not any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
                   for notice in world.knowledge.notices.values()):
            continue
        campaign = world.society.siege_campaigns.get(clause.campaign_id)
        detachment = world.society.detachments.get(clause.detachment_id)
        if (campaign is None or campaign.phase != "breached" or detachment is None
                or detachment.owner_ref != actor or detachment.stage != "present"
                or detachment.location_id != campaign.settlement_id):
            continue
        if actor == campaign.attacker_ref:
            routes = tuple(item for item in siege_campaign_withdrawal_options(world, actor)
                           if item.campaign_id == campaign.id and item.detachment_id == detachment.id)
        else:
            routes = withdrawal_options(world, actor, detachment_id=detachment.id,
                                        allow_open_campaign_supply=True, campaign_authorized=True)
        for route in routes:
            options.append(CampaignWithdrawalRemediation(
                id=(f"campaign-withdrawal-remediation:{obligation.id}:{obligation.breach_event_id}:"
                    f"{campaign.id}:{detachment.id}:{route.id}"),
                actor_ref=actor, obligation_id=obligation.id, campaign_id=campaign.id,
                detachment_id=detachment.id, destination_id=route.destination_id,
                route_ids=route.route_ids, breach_event_id=obligation.breach_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def remediate_campaign_withdrawal(world, actor, option_id, decision_event_id):
    """Execute a current withdrawal and resolve its obligation as remediated."""
    candidate = deepcopy(world)
    option = next((item for item in campaign_withdrawal_remediation_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign withdrawal remediation option is stale or unknown")
    require_decision(candidate, decision_event_id, option.decision())
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "military")
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    if (obligation.breach_event_id != option.breach_event_id
            or clause.kind != "campaign_withdrawal"
            or clause.campaign_id != option.campaign_id or clause.detachment_id != option.detachment_id):
        raise ValueError("campaign withdrawal remediation no longer matches its breached term")

    campaign = candidate.society.siege_campaigns[clause.campaign_id]
    if actor == campaign.attacker_ref:
        route = next((item for item in siege_campaign_withdrawal_options(candidate, actor)
                      if item.campaign_id == clause.campaign_id and item.detachment_id == clause.detachment_id
                      and item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
        if route is None:
            raise ValueError("campaign remediation route is stale")
        _execute_siege_withdrawal(candidate, actor, route, decision_event_id,
                                  selected_affordance_id=option.id)
    else:
        route = next((item for item in withdrawal_options(
            candidate, actor, detachment_id=clause.detachment_id,
            allow_open_campaign_supply=True, campaign_authorized=True)
                      if item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
        if route is None:
            raise ValueError("campaign remediation route is stale")
        from .campaign_supply import _lapse_campaign_notices
        _lapse_campaign_notices(candidate, clause.detachment_id, decision_event_id)
        garrison = next((item for item in candidate.society.garrisons.values()
                         if item.detachment_id == clause.detachment_id and item.stage == "active"), None)
        if garrison is not None:
            _withdraw_garrison(candidate, actor, GarrisonOption(
                id=f"campaign-remediation-garrison:{garrison.id}:{garrison.last_event_id}",
                actor_ref=actor, detachment_id=clause.detachment_id,
                settlement_id=garrison.settlement_id, account_id=garrison.account_id,
                daily_wage=0, kind="withdraw"),
                next(item for item in candidate.events if item.id == decision_event_id))
        _begin_withdrawal(candidate, actor, route, decision_event_id,
                          selected_affordance_id=option.id)

    material = next((event for event in reversed(candidate.events)
                     if event.event_type == "detachment_withdrawal_started"
                     and any(link.cause_event_id == decision_event_id for link in event.causal_links)
                     and any(delta.owner_kind == "detachment" and delta.owner_id == clause.detachment_id
                             and delta.aspect == "stage" and delta.before == "present"
                             and delta.after == "marching" for delta in event.deltas)), None)
    if material is None:
        raise ValueError("campaign remediation did not produce the promised physical withdrawal")
    parties = (proposal.proposer_ref, proposal.counterparty_ref)
    reinforced = tuple(memory for memory in
                       (memories_of(candidate, party, option.breach_event_id) for party in parties)
                       if memory is not None)
    receipt = record_event(
        candidate, "campaign_withdrawal_remediated",
        "A retirada material reparou uma obrigação de cessar-fogo descumprida; a quebra histórica permanece registrada.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision_event_id, "actor_ref": actor.to_dict(),
                        "selected_affordance_id": option.id, "obligation_id": obligation.id,
                        "campaign_id": clause.campaign_id, "detachment_id": clause.detachment_id},
        deltas=(_delta("obligation", obligation.id, "status", "breached", "remediated"),
                _delta("obligation", obligation.id, "remediation_material_event_id", None, material.id),
                *memory_creation_deltas(candidate, parties), *reinforcement_deltas(candidate, reinforced)),
        cause_ids=(decision_event_id, option.breach_event_id, material.id))
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={"status": "remediated", "material_event_id": None,
                "remediation_material_event_id": material.id, "last_event_id": receipt.id})
    candidate.agenda.cancel(obligation.id)
    apply_memory_creation(candidate, parties, receipt)
    apply_reinforcement(candidate, reinforced, receipt)
    disclose(candidate, proposal, receipt)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.obligations[option.obligation_id]


def _options(world, actor):
    """Compose current ceasefire and breach-remediation choices."""
    return (*campaign_ceasefire_offer_options(world, actor),
            *campaign_ceasefire_response_options(world, actor),
            *campaign_ceasefire_fulfillment_options(world, actor),
            *campaign_withdrawal_remediation_options(world, actor))


def _causes(world, option):
    if isinstance(option, CampaignCeasefireOffer):
        campaign = world.society.siege_campaigns.get(option.campaign_id)
        return (campaign.last_event_id,) if campaign and campaign.last_event_id else ()
    if isinstance(option, CampaignCeasefireResponse):
        proposal = world.relations.proposals.get(option.proposal_id)
        return (proposal.last_event_id,) if proposal else ()
    if isinstance(option, CampaignWithdrawalRemediation):
        return (option.breach_event_id,)
    obligation = world.relations.obligations.get(option.obligation_id)
    return (obligation.last_event_id,) if obligation else ()


def _label(option):
    if isinstance(option, CampaignCeasefireOffer):
        return ("Propor cessar-fogo mútuo." if option.kind == "mutual"
                else "Propor retirada unilateral da própria coluna.")
    if isinstance(option, CampaignCeasefireResponse):
        return ("Aceitar o cessar-fogo." if option.response == "accept"
                else "Recusar o cessar-fogo.")
    if isinstance(option, CampaignWithdrawalRemediation):
        return "Reparar a quebra do cessar-fogo retirando materialmente a coluna."
    return "Cumprir a retirada material prometida no cessar-fogo."


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign ceasefire option is stale or unknown")
    if isinstance(option, CampaignCeasefireOffer):
        return offer_campaign_ceasefire(world, actor, option.id, decision_event_id)
    if isinstance(option, CampaignCeasefireResponse):
        return respond_campaign_ceasefire(world, actor, option.id, decision_event_id)
    if isinstance(option, CampaignCeasefireFulfillment):
        return fulfill_campaign_ceasefire(world, actor, option.id, decision_event_id)
    return remediate_campaign_withdrawal(world, actor, option.id, decision_event_id)


def campaign_ceasefire_adapters():
    """Expose current ceasefire affordances in the shared monthly turn."""
    return (DiscretionaryAdapter(
        name="campaign_ceasefire", family="campaign", options_fn=_options,
        label_fn=_label, causes_fn=_causes, execute_fn=_execute),)


__all__ = ["FULFILL_ACTION", "OFFER_ACTION", "RESPONSE_ACTION",
           "campaign_ceasefire_offer_options", "campaign_ceasefire_response_options",
           "campaign_ceasefire_fulfillment_options", "offer_campaign_ceasefire",
           "respond_campaign_ceasefire", "fulfill_campaign_ceasefire",
           "campaign_withdrawal_remediation_options", "remediate_campaign_withdrawal",
           "campaign_ceasefire_adapters"]
