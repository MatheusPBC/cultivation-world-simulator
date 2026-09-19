"""A bounded bribe: one enumerated payment offer, no authority effect.

Relations owns the proposal and its payment obligation.  The Economy remains
the only owner that can move money, and Authority remains the only owner that
can grant a scope or office; accepting this proposal does neither.
"""
from dataclasses import dataclass
from hashlib import sha256

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.diplomacy import (PaymentClause, bribery_offer_intent,
                                               bribery_response_intent)
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .commitments import fulfill_obligation
from .diplomacy import offer_proposal, respond_proposal
from .events import record_event
from .institutional_decision_turn import DiscretionaryAdapter


OFFER_ACTION = "offer_bribery"
RESPONSE_ACTION = "respond_bribery"
PAYMENT_ACTION = "fulfill_bribery_payment"


def _opaque_id(prefix, *private_terms):
    """Keep account identities out of actor/provider-facing affordance IDs."""
    digest = sha256("|".join(str(term) for term in private_terms).encode()).hexdigest()[:12]
    return f"{prefix}:{digest}"


@dataclass(frozen=True)
class BriberyOfferOption:
    id: Identity
    actor_ref: EntityRef
    counterparty_ref: EntityRef
    source_account_id: Identity
    target_account_id: Identity
    amount: int

    def decision(self):
        return bribery_offer_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class BriberyResponseOption:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    response: str

    def decision(self):
        return bribery_response_intent(self.actor_ref, self.id)


@dataclass(frozen=True)
class BriberyPaymentOption:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    obligation_id: Identity
    source_account_id: Identity
    target_account_id: Identity
    amount: int

    def decision(self):
        return {"action": PAYMENT_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    return next((item for item in world.events if item.id == event_id), None)


def _old_enough(world, event_id):
    event = _event(world, event_id)
    return event is not None and event.day < world.clock.absolute_day


def _institution_accounts(world, owner_ref):
    return tuple(sorted((account for account in world.economy.accounts.values()
                         if account.owner_ref == owner_ref), key=lambda item: item.id))


def _recent_bribe(world, actor, counterparty):
    day = world.clock.absolute_day
    return any(proposal.proposal_kind == "bribery"
               and proposal.proposer_ref == actor and proposal.counterparty_ref == counterparty
               and (proposal.status in {"offered", "accepted"} or day - proposal.offered_day < 180)
               for proposal in world.relations.proposals.values())


def bribery_offer_options(world, actor):
    """Enumerate one amount from the actor's own current account only."""
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "diplomacy")
            or not can_actor_act_for(world, actor, actor, "trade")):
        return ()
    options = []
    for source in _institution_accounts(world, actor):
        amount = max(1, source.balance // 10)
        if source.balance < amount:
            continue
        for target in sorted(world.economy.accounts.values(), key=lambda item: item.id):
            other = target.owner_ref
            if (other == actor or other.kind not in {"polity", "organization"}
                    or not can_actor_act_for(world, other, other, "diplomacy")
                    or _recent_bribe(world, actor, other)):
                continue
            options.append(BriberyOfferOption(
                id=_opaque_id(
                    f"bribery:{actor.kind}:{actor.id}:{other.kind}:{other.id}:{amount}:{world.clock.absolute_day}",
                    source.id, target.id, source.last_event_id, target.last_event_id),
                actor_ref=actor, counterparty_ref=other, source_account_id=source.id,
                target_account_id=target.id, amount=amount))
    return tuple(options)


def bribery_response_options(world, actor):
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "diplomacy")):
        return ()
    known = {notice.proposal_id for notice in world.knowledge.notices.values()
             if notice.recipient_ref == actor}
    options = []
    for proposal in sorted(world.relations.proposals.values(), key=lambda item: item.id):
        if (proposal.id not in known or proposal.proposal_kind != "bribery"
                or proposal.status != "offered" or proposal.counterparty_ref != actor
                or not proposal.offered_day < world.clock.absolute_day < proposal.expires_day):
            continue
        base = f"bribery-response:{proposal.id}:{proposal.last_event_id}"
        options.extend((BriberyResponseOption(f"{base}:reject", actor, proposal.id, "reject"),
                        BriberyResponseOption(f"{base}:accept", actor, proposal.id, "accept")))
    return tuple(options)


def bribery_payment_options(world, actor):
    if (not isinstance(actor, EntityRef) or actor.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor, actor, "trade")):
        return ()
    options = []
    for proposal in sorted(world.relations.proposals.values(), key=lambda item: item.id):
        if proposal.proposal_kind != "bribery" or proposal.status != "accepted" or proposal.proposer_ref != actor:
            continue
        clause = proposal.clauses[0]
        obligation_id = f"{proposal.id}:term:0"
        obligation = world.relations.obligations.get(obligation_id)
        source = world.economy.accounts.get(clause.source_account_id)
        if (obligation is None or obligation.status != "active" or not _old_enough(world, obligation.last_event_id)
                or world.clock.absolute_day > clause.due_day or source is None
                or source.owner_ref != actor or source.balance < clause.amount):
            continue
        options.append(BriberyPaymentOption(
            id=_opaque_id(f"bribery-payment:{obligation_id}:{obligation.last_event_id}:{clause.amount}",
                          source.id, source.last_event_id, clause.source_account_id,
                          clause.target_account_id),
            actor_ref=actor, proposal_id=proposal.id, obligation_id=obligation_id,
            source_account_id=clause.source_account_id, target_account_id=clause.target_account_id,
            amount=clause.amount))
    return tuple(options)


def _decision(world, decision_event_id, expected):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision != expected):
        raise ValueError("bribery requires its exact current decision")
    return event


def execute_bribery_offer(world, actor, option_id, decision_event_id):
    option = next((item for item in bribery_offer_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("bribery offer is stale or unknown")
    _decision(world, decision_event_id, option.decision())
    require_authority(world, actor, "diplomacy")
    require_authority(world, actor, "trade")
    source = world.economy.accounts.get(option.source_account_id)
    target = world.economy.accounts.get(option.target_account_id)
    if (source is None or source.owner_ref != actor or source.balance < option.amount
            or target is None or target.owner_ref != option.counterparty_ref):
        raise ValueError("bribery funds or account owner is no longer valid")
    day = world.clock.absolute_day
    clause = PaymentClause(debtor_ref=actor, creditor_ref=option.counterparty_ref, due_day=day + 20,
                           source_account_id=source.id, target_account_id=target.id, amount=option.amount)
    return offer_proposal(world, actor, option.counterparty_ref, (clause,), day + 15,
                          decision_event_id=decision_event_id, intent=option.decision(),
                          proposal_kind="bribery", request_affordance_id=option.id)


def execute_bribery_response(world, actor, option_id, decision_event_id):
    option = next((item for item in bribery_response_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("bribery response is stale or unknown")
    _decision(world, decision_event_id, option.decision())
    return respond_proposal(world, option.proposal_id, option.response,
                            decision_event_id=decision_event_id, intent=option.decision())


def execute_bribery_payment(world, actor, option_id, decision_event_id):
    option = next((item for item in bribery_payment_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("bribery payment is stale or unknown")
    _decision(world, decision_event_id, option.decision())
    authorization_intent = {"action": "pay", "actor_ref": actor.to_dict(),
                            "source_id": option.source_account_id, "target_id": option.target_account_id,
                            "amount": option.amount}
    authorization = record_event(world, "bribery_payment_authorized",
                                 "O owner autorizou o pagamento de suborno escolhido.",
                                 fact_kind=FactKind.DECISION, decision=authorization_intent,
                                 cause_ids=(decision_event_id,))
    fulfill_obligation(world, option.obligation_id, decision_event_id=authorization.id,
                       decision_intent=authorization_intent)
    return world.relations.obligations[option.obligation_id]


def _causes(world, option):
    proposal_id = getattr(option, "proposal_id", None)
    proposal = world.relations.proposals.get(proposal_id) if proposal_id else None
    return (proposal.last_event_id,) if proposal is not None else ()


def _situation(world, _actor, options):
    return {"today": world.clock.absolute_day,
            "known_proposal_ids": sorted({getattr(option, "proposal_id", None) for option in options
                                           if getattr(option, "proposal_id", None)}),
            "own_obligation_ids": sorted({getattr(option, "obligation_id", None) for option in options
                                           if getattr(option, "obligation_id", None)})}


def bribery_adapters():
    return (
        DiscretionaryAdapter(
            name="bribery_offer", family="diplomacy", options_fn=bribery_offer_options,
            label_fn=lambda option: f"Oferecer {option.amount} unidades monetárias à contraparte.",
            causes_fn=_causes, execute_fn=execute_bribery_offer, situation_fn=_situation),
        DiscretionaryAdapter(
            name="bribery_response", family="diplomacy", options_fn=bribery_response_options,
            label_fn=lambda option: f"{('Aceitar' if option.response == 'accept' else 'Recusar')} a oferta material.",
            causes_fn=_causes, execute_fn=execute_bribery_response, situation_fn=_situation),
        DiscretionaryAdapter(
            name="bribery_payment", family="diplomacy", options_fn=bribery_payment_options,
            label_fn=lambda _option: "Cumprir o pagamento material aceito.",
            causes_fn=_causes, execute_fn=execute_bribery_payment, situation_fn=_situation),
    )


__all__ = ["BriberyOfferOption", "BriberyResponseOption", "BriberyPaymentOption",
           "bribery_offer_options", "bribery_response_options", "bribery_payment_options",
           "execute_bribery_offer", "execute_bribery_response", "execute_bribery_payment",
           "bribery_adapters"]
