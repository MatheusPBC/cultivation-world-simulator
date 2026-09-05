"""Reciprocal city-to-city barter over canonical regional economies.

A city facing a grounded shortage may offer a partner city an exchange: the
partner ships what this city lacks, and this city ships back a different
resource the partner itself lacks.  The two legs are enumerated from actual
deficits and actual surplus over declared routes; each leg is bounded on its
own.  Nothing here prices one resource in another, reserves stock, or moves
anything: acceptance only opens two ordinary transfer terms, and each obligor
later decides its own shipment through the shared commitment lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.institution import (
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    InstitutionalCommitment,
)
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
)
from src.systems.institutional_resource_commitment import (
    REQUEST_DOMAIN,
    RESPONSE_DOMAIN,
    city_institution_id,
    city_region,
    grounded_trigger,
    has_open_transfer_commitment,
    negotiating_city,
    proposal_already_answered,
    record_institutional_fact,
    register_proposal_handler,
    specified_shipment_is_possible,
    transfer_memory_factors,
)
from src.systems.resource_transfer import find_canonical_route

PROPOSE_ACTION = "request_reciprocal_trade"
ACCEPT_ACTION = "accept_reciprocal_trade"
PROPOSAL_EVENT_TYPE = "institutional_trade_proposed"
OFFER_PAYLOAD_KEY = "institutional_trade_offer"
TERM_DUE_OFFSET = 2
LEG_KEYS = (
    "amount",
    "destination_region_id",
    "resource_id",
    "route_id",
    "source_region_id",
)


def _known_resource(region: CityRegion, resource_id: str) -> bool:
    economy = region.economy
    return (
        resource_id in economy.stocks
        and resource_id in economy.capacities
        and float(economy.access.get(resource_id, 0.0)) > 0
    )


def _deficit(region: CityRegion, resource_id: str) -> float:
    """Unmet monthly demand this city itself declares, bounded by headroom."""

    if not _known_resource(region, resource_id):
        return 0.0
    economy = region.economy
    available = economy.available_stock(resource_id)
    if available is None:
        return 0.0
    need = float(economy.demand_rates.get(resource_id, 0.0)) - float(available)
    headroom = float(economy.capacities[resource_id]) - float(
        economy.stocks[resource_id]
    )
    return max(0.0, min(need, headroom))


def _surplus(region: CityRegion, resource_id: str) -> float:
    """Available stock a city can ship while retaining its own demand stock.

    A city that declares no demand rate for a resource has an unknown need,
    not a zero one, so it exports nothing.
    """

    if (
        not _known_resource(region, resource_id)
        or resource_id not in region.economy.demand_rates
    ):
        return 0.0
    available = region.economy.available_stock(resource_id)
    if available is None:
        return 0.0
    return max(
        0.0,
        float(available) - float(region.economy.demand_rates[resource_id]),
    )


def _leg(
    world: Any,
    source: CityRegion,
    destination: CityRegion,
    resource_id: str,
) -> dict[str, Any] | None:
    """One independently bounded shipment, or nothing when unfounded."""

    if has_open_transfer_commitment(
        world,
        source_region_id=str(source.id),
        destination_region_id=str(destination.id),
        resource_id=resource_id,
    ) or has_open_transfer_commitment(
        world,
        source_region_id=str(destination.id),
        destination_region_id=str(source.id),
        resource_id=resource_id,
    ):
        return None
    route = find_canonical_route(world, source, destination, resource_id)
    if route is None:
        return None
    amount = min(
        _surplus(source, resource_id),
        _deficit(destination, resource_id),
        float(route["effective_capacity"]),
    )
    if amount <= 0:
        return None
    return {
        "amount": amount,
        "destination_region_id": str(destination.id),
        "resource_id": resource_id,
        "route_id": str(route["route_id"]),
        "source_region_id": str(source.id),
    }


def trade_offer_affordances(context: AffordanceContext):
    """Enumerate every mutually useful exchange; unknown stays unknown.

    Each feasible pair of a reachable partner and a reciprocal resource is one
    affordance.  The engine never ranks one resource against another: the two
    legs are in different units and no exchange rate exists in this world.
    """

    if context.actor_ref.kind != "region" or not grounded_trigger(
        context.trigger_event
    ):
        return ()
    params = context.trigger_event.render_params or {}
    inbound_resource_id = str(params.get("resource_id", "")).strip()
    if str(params.get("region_id", "")) != str(context.actor_ref.id):
        return ()
    proposer = city_region(context.world, context.actor_ref.id)
    if (
        proposer is None
        or not inbound_resource_id
        or not negotiating_city(context.world, proposer.id)
    ):
        return ()
    inbound_need = _deficit(proposer, inbound_resource_id)
    if inbound_need <= 0:
        return ()
    urgency = max(
        0.0,
        min(
            1.0,
            inbound_need
            / max(
                float(proposer.economy.demand_rates.get(inbound_resource_id, 0.0)),
                1e-9,
            ),
        ),
    )
    options: list[DomainAffordance] = []
    for partner in sorted(
        (
            region
            for region in context.world.map.regions.values()
            if isinstance(region, CityRegion) and region.id != proposer.id
        ),
        key=lambda item: int(item.id),
    ):
        if not negotiating_city(context.world, partner.id):
            continue
        inbound = _leg(context.world, partner, proposer, inbound_resource_id)
        if inbound is None:
            continue
        for candidate_resource in sorted(partner.economy.demand_rates):
            if candidate_resource == inbound_resource_id:
                continue
            outbound = _leg(context.world, proposer, partner, candidate_resource)
            if outbound is None:
                continue
            options.append(
                DomainAffordance(
                    domain=context.domain,
                    actor_ref=context.actor_ref,
                    action_kind=PROPOSE_ACTION,
                    target_refs=(EntityRef("region", str(partner.id)),),
                    parameters={
                        "proposer_institution_id": city_institution_id(proposer.id),
                        "counterparty_institution_id": city_institution_id(partner.id),
                        "legs": [inbound, outbound],
                    },
                    urgency=urgency,
                    motivation_event_ids=(context.trigger_event.id,),
                )
            )
    return tuple(options)


def trade_offer_payload(event: Event) -> dict[str, Any] | None:
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    offer = payload.get(OFFER_PAYLOAD_KEY)
    if not isinstance(offer, Mapping):
        return None
    required = {
        "proposer_institution_id",
        "counterparty_institution_id",
        "legs",
        "urgency",
    }
    if set(offer) != required:
        return None
    legs = offer["legs"]
    if not isinstance(legs, (list, tuple)) or len(legs) != 2:
        return None
    normalized: list[dict[str, Any]] = []
    for leg in legs:
        if not isinstance(leg, Mapping) or set(leg) != set(LEG_KEYS):
            return None
        normalized.append(dict(leg))
    if normalized[0]["resource_id"] == normalized[1]["resource_id"]:
        return None
    if (
        normalized[0]["source_region_id"] != normalized[1]["destination_region_id"]
        or normalized[0]["destination_region_id"] != normalized[1]["source_region_id"]
    ):
        return None
    return {**dict(offer), "legs": normalized}


def _counterparty_region_id(_world: Any, proposal_event: Event) -> str | None:
    offer = trade_offer_payload(proposal_event)
    return None if offer is None else str(offer["legs"][0]["source_region_id"])


def _offer_is_executable(world: Any, offer: Mapping[str, Any]) -> bool:
    inbound, outbound = offer["legs"]
    counterparty_id = str(inbound["source_region_id"])
    proposer_id = str(inbound["destination_region_id"])
    if (
        str(offer["counterparty_institution_id"]) != city_institution_id(counterparty_id)
        or str(offer["proposer_institution_id"]) != city_institution_id(proposer_id)
        or not negotiating_city(world, counterparty_id)
        or not negotiating_city(world, proposer_id)
    ):
        return False
    for leg in (inbound, outbound):
        if not specified_shipment_is_possible(world, leg):
            return False
        donor = city_region(world, str(leg["source_region_id"]))
        # The agreed amount is never recomputed here; it is only rejected when
        # the donor can no longer ship it while retaining its own demand stock.
        if donor is None or _surplus(donor, str(leg["resource_id"])) < float(
            leg["amount"]
        ):
            return False
        if has_open_transfer_commitment(
            world,
            source_region_id=str(leg["source_region_id"]),
            destination_region_id=str(leg["destination_region_id"]),
            resource_id=str(leg["resource_id"]),
        ):
            return False
    return True


def trade_response_affordances(context: AffordanceContext):
    offer = trade_offer_payload(context.trigger_event)
    if (
        offer is None
        or not grounded_trigger(context.trigger_event)
        or proposal_already_answered(context.world, context.trigger_event.id)
    ):
        return ()
    counterparty_id = str(offer["legs"][0]["source_region_id"])
    if context.actor_ref != EntityRef("region", counterparty_id):
        return ()
    if not _offer_is_executable(context.world, offer):
        return ()
    return (
        DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind=ACCEPT_ACTION,
            target_refs=(
                EntityRef("region", str(offer["legs"][0]["destination_region_id"])),
            ),
            parameters={
                **{
                    key: offer[key]
                    for key in (
                        "proposer_institution_id",
                        "counterparty_institution_id",
                        "legs",
                    )
                },
                "proposal_event_id": context.trigger_event.id,
            },
            urgency=float(offer["urgency"]),
            motivation_event_ids=(context.trigger_event.id,),
        ),
    )


def _execute_proposal(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    **_: Any,
) -> Event:
    legs = [dict(leg) for leg in option.parameters["legs"]]
    inbound, outbound = legs
    proposer_id = str(inbound["destination_region_id"])
    if not negotiating_city(context.world, proposer_id):
        raise StaleAffordanceError("proposing city authority changed")
    event = Event(
        context.world.month_stamp,
        "A city offered a reciprocal resource exchange to another city.",
        event_type=PROPOSAL_EVENT_TYPE,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "proposer_region_id": proposer_id,
            "counterparty_region_id": str(inbound["source_region_id"]),
            "inbound_resource_id": str(inbound["resource_id"]),
            "inbound_amount": float(inbound["amount"]),
            "outbound_resource_id": str(outbound["resource_id"]),
            "outbound_amount": float(outbound["amount"]),
            "affordance_id": option.id,
        },
        causal_payload={
            "deltas": [],
            OFFER_PAYLOAD_KEY: {
                "proposer_institution_id": str(
                    option.parameters["proposer_institution_id"]
                ),
                "counterparty_institution_id": str(
                    option.parameters["counterparty_institution_id"]
                ),
                "legs": legs,
                "urgency": option.urgency,
            },
        },
    )
    event.causal_links.extend(
        (
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            ),
            CausalLink(
                event_id=event.id,
                cause_event_id=context.trigger_event.id,
                relation=CausalRelation.TRIGGERED_BY,
            ),
        )
    )
    record_institutional_fact(
        context.world,
        event,
        (
            str(option.parameters["proposer_institution_id"]),
            str(option.parameters["counterparty_institution_id"]),
        ),
    )
    return event


def _execute_acceptance(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    **_: Any,
) -> Event:
    legs = [dict(leg) for leg in option.parameters["legs"]]
    inbound, outbound = legs
    counterparty_id = str(inbound["source_region_id"])
    proposer_id = str(inbound["destination_region_id"])
    if not negotiating_city(context.world, counterparty_id) or not negotiating_city(
        context.world, proposer_id
    ):
        raise StaleAffordanceError("trade party authority changed")
    proposer_institution_id = str(option.parameters["proposer_institution_id"])
    counterparty_institution_id = str(option.parameters["counterparty_institution_id"])
    event = Event(
        context.world.month_stamp,
        "A city accepted a reciprocal resource exchange.",
        event_type="institutional_trade_accepted",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "proposer_region_id": proposer_id,
            "counterparty_region_id": counterparty_id,
            "inbound_resource_id": str(inbound["resource_id"]),
            "inbound_amount": float(inbound["amount"]),
            "outbound_resource_id": str(outbound["resource_id"]),
            "outbound_amount": float(outbound["amount"]),
            "affordance_id": option.id,
        },
    )
    evidence = (str(option.parameters["proposal_event_id"]), event.id)
    terms = tuple(
        CommitmentTerm(
            id=f"term:{event.id}:{index}",
            index=index,
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id=(
                counterparty_institution_id if index == 0 else proposer_institution_id
            ),
            beneficiary_institution_id=(
                proposer_institution_id if index == 0 else counterparty_institution_id
            ),
            subject=EntityRef("resource", str(leg["resource_id"])),
            status=CommitmentTermStatus.ACTIVE,
            proposed_month=int(context.world.month_stamp),
            due_month=int(context.world.month_stamp) + TERM_DUE_OFFSET,
            parameters=(
                ("amount", float(leg["amount"])),
                ("destination_region_id", str(leg["destination_region_id"])),
                ("route_id", str(leg["route_id"])),
                ("source_region_id", str(leg["source_region_id"])),
            ),
            evidence_event_ids=evidence,
        )
        for index, leg in enumerate(legs)
    )
    commitment = InstitutionalCommitment(
        party_ids=(proposer_institution_id, counterparty_institution_id),
        opened_month=int(context.world.month_stamp),
        terms=terms,
        origin_event_id=event.id,
    )
    context.world.institutional_relations.add_commitment(
        commitment,
        context.world.institutional_authority,
    )
    event.causal_payload = {
        "deltas": [
            StateDelta(
                event_id=event.id,
                owner_kind="institutional_commitment",
                owner_id=commitment.id,
                aspect="aggregate_status",
                before="none",
                after=commitment.aggregate_status.value,
            ).to_dict()
        ],
        "commitment_id": commitment.id,
        "term_ids": [term.id for term in terms],
        "affordance_id": option.id,
    }
    event.causal_links.extend(
        (
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            ),
            CausalLink(
                event_id=event.id,
                cause_event_id=str(option.parameters["proposal_event_id"]),
                relation=CausalRelation.TRIGGERED_BY,
            ),
        )
    )
    record_institutional_fact(
        context.world,
        event,
        commitment.party_ids,
        memory_factors=transfer_memory_factors(
            context.world,
            inbound,
            institutional_change=1.0,
            commitment_breach=0.0,
        ),
    )
    return event


def refusal_event(
    world: Any,
    proposal_event: Event,
    decision_event_id: str,
) -> Event:
    offer = trade_offer_payload(proposal_event)
    render_params: dict[str, Any] = {}
    if offer is not None:
        inbound, outbound = offer["legs"]
        # Read back from the refused proposal only: a later reader must see who
        # declined what without re-deriving anything.
        render_params = {
            "proposer_region_id": str(inbound["destination_region_id"]),
            "counterparty_region_id": str(inbound["source_region_id"]),
            "inbound_resource_id": str(inbound["resource_id"]),
            "inbound_amount": float(inbound["amount"]),
            "outbound_resource_id": str(outbound["resource_id"]),
            "outbound_amount": float(outbound["amount"]),
        }
    event = Event(
        world.month_stamp,
        "A city declined a reciprocal resource exchange.",
        event_type="institutional_trade_refused",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params=render_params,
        causal_payload={"deltas": [], "outcome": "refused"},
    )
    event.causal_links.extend(
        (
            CausalLink(
                event_id=event.id,
                cause_event_id=decision_event_id,
                relation=CausalRelation.MOTIVATED_BY,
            ),
            CausalLink(
                event_id=event.id,
                cause_event_id=proposal_event.id,
                relation=CausalRelation.RESPONSE_TO,
            ),
        )
    )
    if offer is not None:
        record_institutional_fact(
            world,
            event,
            (
                str(offer["proposer_institution_id"]),
                str(offer["counterparty_institution_id"]),
            ),
            memory_factors=transfer_memory_factors(
                world,
                offer["legs"][0],
                institutional_change=0.0,
                commitment_breach=0.0,
            ),
        )
    return event


for _domain, _provider in (
    (REQUEST_DOMAIN, trade_offer_affordances),
    (RESPONSE_DOMAIN, trade_response_affordances),
):
    DOMAIN_AFFORDANCES.register_provider(_domain, _provider)

for _action, _executor in (
    (PROPOSE_ACTION, _execute_proposal),
    (ACCEPT_ACTION, _execute_acceptance),
):
    DOMAIN_AFFORDANCES.register_executor(_action, _executor)

register_proposal_handler(
    PROPOSAL_EVENT_TYPE,
    counterparty_region_id=_counterparty_region_id,
    refusal_event=refusal_event,
    outcome_event_types=frozenset(
        {"institutional_trade_accepted", "institutional_trade_refused"}
    ),
)


__all__ = [
    "ACCEPT_ACTION",
    "OFFER_PAYLOAD_KEY",
    "PROPOSAL_EVENT_TYPE",
    "PROPOSE_ACTION",
    "refusal_event",
    "trade_offer_affordances",
    "trade_offer_payload",
    "trade_response_affordances",
]
