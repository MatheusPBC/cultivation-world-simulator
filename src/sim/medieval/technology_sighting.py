"""Voluntary, dated evidence that a reachable institution holds a technique.

This is not an espionage system and it is not teaching.  The holder may tell a
reachable peer about one of its own existing TechnicalKnowledge facts.  The
recipient gains only an expiring TechnologySighting, which can justify asking
that holder for a teaching bargain; the Research and Economy owners remain
unchanged.
"""

from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.knowledge import technology_sighting_id
from src.classes.governance.models import TechnologySighting
from src.classes.mechanical_language import EntityRef

from .economy import _delta
from .events import record_event
from .routing import supply_path


DISCLOSE_TECHNOLOGY_ACTION = "disclose_technology_sighting"
SIGHTING_DAYS = 180


@dataclass(frozen=True)
class TechnologySightingOption:
    id: str
    actor_ref: EntityRef
    recipient_ref: EntityRef
    technology_id: str
    source_event_id: str
    action: str = DISCLOSE_TECHNOLOGY_ACTION

    def decision(self):
        return {"action": self.action, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}

    def causes(self):
        return (self.source_event_id,)


def _institutions_with_stock(world):
    return tuple(sorted({stock.owner_ref for stock in world.economy.stocks.values()
                         if stock.owner_ref.kind in {"polity", "organization"}},
                        key=lambda ref: (ref.kind, ref.id)))


def _reachable(world, holder_ref, recipient_ref):
    """A disclosure can travel only between actual current stock locations.

    The check is engine-owned and reads the Map's live route state.  It does
    not add route knowledge to either party and does not let a remote office
    communicate merely because both names exist in the world.
    """
    origins = sorted(stock.location_id for stock in world.economy.stocks.values()
                     if stock.owner_ref == holder_ref)
    targets = sorted(stock.location_id for stock in world.economy.stocks.values()
                     if stock.owner_ref == recipient_ref)
    return any(supply_path(world, origin, target, "food") is not None
               for origin in origins for target in targets)


def disclosure_options(world, actor_ref):
    if not (can_actor_act_for(world, actor_ref, actor_ref, "research")
            and can_actor_act_for(world, actor_ref, actor_ref, "diplomacy")):
        return ()
    recipients = tuple(recipient for recipient in _institutions_with_stock(world)
                       if recipient != actor_ref
                       and can_actor_act_for(world, recipient, recipient, "research")
                       and can_actor_act_for(world, recipient, recipient, "diplomacy")
                       and _reachable(world, actor_ref, recipient))
    options = []
    for knowledge in sorted((item for item in world.knowledge.technologies.values()
                             if item.owner_ref == actor_ref), key=lambda item: item.technology_id):
        for recipient in recipients:
            if world.knowledge.has_current_technology_sighting(
                    recipient, actor_ref, knowledge.technology_id, world.clock.absolute_day):
                continue
            options.append(TechnologySightingOption(
                id=(f"technology-disclosure:{actor_ref.kind}:{actor_ref.id}:"
                    f"{recipient.kind}:{recipient.id}:{knowledge.technology_id}:{knowledge.event_id}"),
                actor_ref=actor_ref, recipient_ref=recipient, technology_id=knowledge.technology_id,
                source_event_id=knowledge.event_id))
    return tuple(options)


def execute_disclosure(world, option, decision_event_id, *, authorized_by_teaching_offer=False):
    """Publish a technical sighting atomically in the Knowledge owner."""
    candidate = world.transaction_copy()
    result = _execute_disclosure_in_place(
        candidate, option, decision_event_id,
        authorized_by_teaching_offer=authorized_by_teaching_offer)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.knowledge.technology_sightings[result.id]


def _execute_disclosure_in_place(world, option, decision_event_id, *, authorized_by_teaching_offer=False):
    """Recompose the selection and persist only its factual, expiring receipt."""
    current = next((candidate for candidate in disclosure_options(world, option.actor_ref)
                    if candidate.id == option.id), None)
    if current is None:
        raise ValueError("technology disclosure option is absent or stale")
    decision_event = next((event for event in world.events if event.id == decision_event_id), None)
    direct_disclosure = decision_event is not None and decision_event.decision == current.decision()
    intent = decision_event.decision if decision_event is not None else None
    teaching_offer = False
    if authorized_by_teaching_offer and intent is not None:
        teaching_offer = (
            intent.get("action") == "offer_proposal"
            and intent.get("actor_ref") == current.actor_ref.to_dict()
            and intent.get("counterparty_ref") == current.recipient_ref.to_dict()
            and any(clause.get("kind") == "teaching"
                    and clause.get("technology_id") == current.technology_id
                    and clause.get("debtor_ref") == current.actor_ref.to_dict()
                    and clause.get("creditor_ref") == current.recipient_ref.to_dict()
                    for clause in intent.get("clauses", ()))
        ) or (
            intent.get("action") == "offer_teaching_bargain"
            and intent.get("actor_ref") == current.actor_ref.to_dict()
            and str(intent.get("selected_affordance_id", "")).startswith(
                f"teaching-offer:{current.actor_ref.kind}:{current.actor_ref.id}:"
                f"{current.recipient_ref.kind}:{current.recipient_ref.id}:{current.technology_id}:"
            )
        )
    if (decision_event is None or decision_event.fact_kind != FactKind.DECISION
            or decision_event.causal_origin != CausalOrigin.ACTOR_DECISION
            or decision_event.day != world.clock.absolute_day
            or not (direct_disclosure or teaching_offer)):
        raise ValueError("technology disclosure requires its exact current decision")
    knowledge = next((item for item in world.knowledge.technologies.values()
                      if item.owner_ref == current.actor_ref
                      and item.technology_id == current.technology_id
                      and item.event_id == current.source_event_id), None)
    if knowledge is None:
        raise ValueError("technology disclosure requires current owned knowledge")
    sighting_id = technology_sighting_id(current.recipient_ref, current.actor_ref, current.technology_id)
    previous = world.knowledge.technology_sightings.get(sighting_id)
    if previous is not None and previous.expires_day > world.clock.absolute_day:
        raise ValueError("technology disclosure is already current")
    event = record_event(
        world, "technology_sighting_received",
        "Uma instituição recebeu indício factual de técnica mantida por outra instituição.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=(decision_event.causal_origin
                       if direct_disclosure else CausalOrigin.DETERMINISTIC),
        causal_payload=({"decision_event_id": decision_event.id,
                         "actor_ref": decision_event.decision["actor_ref"],
                         "selected_affordance_id": decision_event.decision["selected_affordance_id"]}
                        if (direct_disclosure
                            and decision_event.causal_origin is CausalOrigin.ACTOR_DECISION) else None),
        deltas=(_delta("technology_sighting", sighting_id, "source_event_id",
                       previous.source_event_id if previous else None, knowledge.event_id),),
        cause_ids=(decision_event_id, knowledge.event_id),
    )
    world.knowledge.technology_sightings[sighting_id] = TechnologySighting(
        id=sighting_id, recipient_ref=current.recipient_ref, holder_ref=current.actor_ref,
        technology_id=current.technology_id, source_event_id=knowledge.event_id,
        observed_day=world.clock.absolute_day, expires_day=world.clock.absolute_day + SIGHTING_DAYS,
        event_id=event.id,
    )
    return world.knowledge.technology_sightings[sighting_id]
