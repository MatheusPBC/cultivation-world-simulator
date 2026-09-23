"""Bilateral ceasefire terms for one active siege campaign.

The proposal layer owns only the promise.  Society/Force still owns each
column and executes each withdrawal independently after an accepted obligation
is selected by its debtor.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.diplomacy import (
    CampaignWithdrawalClause,
    campaign_ceasefire_intent,
    campaign_ceasefire_response_intent,
)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .commitments import conclude_obligation
from .diplomacy import offer_proposal, require_decision, respond_proposal
from .force import GarrisonOption, _begin_withdrawal, _withdraw_garrison, withdrawal_options
from .institutional_decision_turn import DiscretionaryAdapter
from .siege_campaign import (
    _execute_siege_withdrawal,
    siege_campaign_withdrawal_options,
)


OFFER_ACTION = "offer_campaign_ceasefire"
RESPONSE_ACTION = "respond_campaign_ceasefire"
FULFILL_ACTION = "fulfill_campaign_ceasefire"
OFFER_WINDOW_DAYS = 1
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


def _defender_garrison_active(world, campaign):
    """Whether the defender still has an active duty this ceasefire can end.

    A collapsed garrison has no executable withdrawal: ``_withdraw_garrison``
    only ends an ``active`` duty.  The affordance must disappear rather than
    be offered and fail at fulfillment.
    """
    garrison = world.society.garrisons.get(campaign.defender_garrison_id)
    return garrison is not None and garrison.stage == "active"


def _open_offer(world, campaign_id):
    return any(proposal.proposal_kind == "campaign_ceasefire" and proposal.status == "offered"
               and any(clause.kind == "campaign_withdrawal" and clause.campaign_id == campaign_id
                       for clause in proposal.clauses)
               for proposal in world.relations.proposals.values())


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
            if not _defender_garrison_active(world, campaign):
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
        if campaign.phase == "sieging":
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
    due_day = candidate.clock.absolute_day + WITHDRAWAL_DUE_DAYS
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
        elif _defender_garrison_active(world, campaign):
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
        material = _execute_siege_withdrawal(candidate, actor, route, decision_event_id)
        material_event_id = candidate.society.siege_campaigns[clause.campaign_id].last_event_id
    else:
        route = next((item for item in withdrawal_options(
            candidate, actor, detachment_id=clause.detachment_id,
            allow_open_campaign_supply=True, campaign_authorized=True)
                      if item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
        if route is None:
            raise ValueError("campaign ceasefire defender route is stale")
        garrison = next(item for item in candidate.society.garrisons.values()
                        if item.detachment_id == clause.detachment_id)
        _withdraw_garrison(candidate, actor, GarrisonOption(
            id=f"campaign-ceasefire-garrison:{garrison.id}:{garrison.last_event_id}",
            actor_ref=actor, detachment_id=clause.detachment_id,
            settlement_id=garrison.settlement_id, account_id=garrison.account_id,
            daily_wage=0, kind="withdraw"),
            next(item for item in candidate.events if item.id == decision_event_id))
        material_event = _begin_withdrawal(candidate, actor, route, decision_event_id)
        material_event_id = material_event.id
    conclude_obligation(candidate, obligation, "fulfilled", material_event_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.relations.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.obligations[option.obligation_id]


def _options(world, actor):
    """Compose the three existing ceasefire turns without adding state."""
    return (*campaign_ceasefire_offer_options(world, actor),
            *campaign_ceasefire_response_options(world, actor),
            *campaign_ceasefire_fulfillment_options(world, actor))


def _causes(world, option):
    if isinstance(option, CampaignCeasefireOffer):
        campaign = world.society.siege_campaigns.get(option.campaign_id)
        return (campaign.last_event_id,) if campaign and campaign.last_event_id else ()
    if isinstance(option, CampaignCeasefireResponse):
        proposal = world.relations.proposals.get(option.proposal_id)
        return (proposal.last_event_id,) if proposal else ()
    obligation = world.relations.obligations.get(option.obligation_id)
    return (obligation.last_event_id,) if obligation else ()


def _label(option):
    if isinstance(option, CampaignCeasefireOffer):
        return ("Propor cessar-fogo mútuo." if option.kind == "mutual"
                else "Propor retirada unilateral da própria coluna.")
    if isinstance(option, CampaignCeasefireResponse):
        return ("Aceitar o cessar-fogo." if option.response == "accept"
                else "Recusar o cessar-fogo.")
    return "Cumprir a retirada material prometida no cessar-fogo."


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("campaign ceasefire option is stale or unknown")
    if isinstance(option, CampaignCeasefireOffer):
        return offer_campaign_ceasefire(world, actor, option.id, decision_event_id)
    if isinstance(option, CampaignCeasefireResponse):
        return respond_campaign_ceasefire(world, actor, option.id, decision_event_id)
    return fulfill_campaign_ceasefire(world, actor, option.id, decision_event_id)


def campaign_ceasefire_adapters():
    """Expose current ceasefire affordances in the shared monthly turn."""
    return (DiscretionaryAdapter(
        name="campaign_ceasefire", family="campaign", options_fn=_options,
        label_fn=_label, causes_fn=_causes, execute_fn=_execute),)


__all__ = ["FULFILL_ACTION", "OFFER_ACTION", "RESPONSE_ACTION",
           "campaign_ceasefire_offer_options", "campaign_ceasefire_response_options",
           "campaign_ceasefire_fulfillment_options", "offer_campaign_ceasefire",
           "respond_campaign_ceasefire", "fulfill_campaign_ceasefire",
           "campaign_ceasefire_adapters"]
