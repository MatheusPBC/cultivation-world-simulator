"""Expose productive-site conveyance through the existing institutional turn."""

from src.classes.mechanical_language import EntityRef

from .institutional_decision_turn import DiscretionaryAdapter
from .productive_conveyance import (
    ProductiveSiteConveyanceAcceptanceOption,
    accept_site_conveyance,
    conveyance_acceptance_options,
    productive_site_conveyance_options,
)


def productive_conveyance_actors(world):
    candidates = {
        *(EntityRef("polity", identity) for identity in world.society.polities),
        *(EntityRef("organization", identity) for identity in world.society.organizations),
    }
    return tuple(sorted(
        (actor for actor in candidates
         if productive_site_conveyance_options(world, actor)
         or conveyance_acceptance_options(world, actor)),
        key=lambda ref: (ref.kind, ref.id),
    ))


def _options(world, actor):
    return (*productive_site_conveyance_options(world, actor),
            *conveyance_acceptance_options(world, actor))


def _causes(_world, option):
    if isinstance(option, ProductiveSiteConveyanceAcceptanceOption):
        return (option.proposal_event_id,)
    return tuple(event_id for event_id in
                 (option.site_last_event_id, option.facility_last_event_id) if event_id)


def _label(option):
    if isinstance(option, ProductiveSiteConveyanceAcceptanceOption):
        return f"Aceitar a oficina {option.site_id} oferecida por {option.seller_ref.id}."
    return f"Oferecer a oficina {option.site_id} a {option.buyer_ref.id}."


def _execute(world, actor, option_id, decision_event_id):
    option = next((item for item in _options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("productive site conveyance option is stale or unknown")
    if isinstance(option, ProductiveSiteConveyanceAcceptanceOption):
        accept_site_conveyance(world, option.id, decision_event_id=decision_event_id)
    # A seller's current ACTOR_DECISION is itself the offer. The buyer's later
    # adapter recomposes that exact dated decision; no second proposal receipt
    # or stateful broker is introduced here.


def productive_conveyance_adapters():
    return (DiscretionaryAdapter(
        name="productive_site_conveyance", family="productive_site_conveyance",
        options_fn=_options, label_fn=_label, causes_fn=_causes,
        execute_fn=_execute),)


def conveyance_response_adapter(proposal_ids):
    """Restrict the post-turn response to offers created in that same turn."""
    proposal_ids = frozenset(proposal_ids)
    return DiscretionaryAdapter(
        name="productive_site_conveyance_response", family="productive_site_conveyance",
        options_fn=lambda world, actor: tuple(
            option for option in conveyance_acceptance_options(world, actor)
            if option.proposal_event_id in proposal_ids),
        label_fn=_label, causes_fn=_causes, execute_fn=_execute,
    )


def newly_offered_conveyance_buyers(world, previous_proposal_ids):
    previous_proposal_ids = frozenset(previous_proposal_ids)
    current = world.clock.absolute_day
    new_offers = {
        event.id for event in world.events
        if event.day == current and event.id not in previous_proposal_ids
        and event.fact_kind.value == "decision"
        and event.causal_origin.value == "actor_decision"
        and (event.decision or {}).get("action") == "propose_productive_site_conveyance"
    }
    candidates = {
        *(EntityRef("polity", identity) for identity in world.society.polities),
        *(EntityRef("organization", identity) for identity in world.society.organizations),
    }
    return tuple(sorted({option.buyer_ref for actor in candidates
                         for option in conveyance_acceptance_options(world, actor)
                         if option.proposal_event_id in new_offers},
                        key=lambda ref: (ref.kind, ref.id)))


__all__ = [
    "conveyance_response_adapter",
    "newly_offered_conveyance_buyers",
    "productive_conveyance_adapters",
    "productive_conveyance_actors",
]
