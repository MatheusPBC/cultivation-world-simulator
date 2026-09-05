"""Unilateral institutional aid over canonical regional economies.

This module owns only how a shortage becomes an aid request and how the
provider city answers it.  Terms, deadlines, fulfillment and remediation are
the shared material commitment lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance
from src.classes.event import Event, FactKind
from src.classes.institution import (
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    InstitutionalCommitment,
)
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.systems.collective_affordances import economy_affordances
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

REQUEST_ACTION = "request_institutional_aid"
ACCEPT_ACTION = "accept_institutional_aid"
REQUEST_EVENT_TYPE = "institutional_aid_requested"
INSTALLMENT_DUE_OFFSETS = (1, 2)


def _installments(total: float) -> list[dict[str, float | int]]:
    first = total / 2.0
    return [
        {"index": 0, "amount": first, "due_offset": INSTALLMENT_DUE_OFFSETS[0]},
        {
            "index": 1,
            "amount": total - first,
            "due_offset": INSTALLMENT_DUE_OFFSETS[1],
        },
    ]


def request_affordances(context: AffordanceContext):
    if context.actor_ref.kind != "region" or not grounded_trigger(
        context.trigger_event
    ):
        return ()
    destination = city_region(context.world, context.actor_ref.id)
    if destination is None or not negotiating_city(context.world, destination.id):
        return ()
    economy_context = AffordanceContext(
        context.world,
        "economy",
        EntityRef("regional_economy", f"region:{destination.id}"),
        context.trigger_event,
    )
    options: list[DomainAffordance] = []
    for transfer in economy_affordances(economy_context):
        params = dict(transfer.parameters)
        source_id = str(params["source_region_id"])
        if not negotiating_city(context.world, source_id):
            continue
        if has_open_transfer_commitment(
            context.world,
            source_region_id=source_id,
            destination_region_id=str(destination.id),
            resource_id=str(params["resource_id"]),
        ):
            continue
        total = float(params["amount"])
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind=REQUEST_ACTION,
                target_refs=(EntityRef("region", source_id),),
                parameters={
                    **params,
                    "requester_institution_id": city_institution_id(destination.id),
                    "provider_institution_id": city_institution_id(source_id),
                    "installments": _installments(total),
                },
                urgency=transfer.urgency,
                motivation_event_ids=transfer.motivation_event_ids,
            )
        )
    return tuple(options)


def aid_request_payload(event: Event) -> dict[str, Any] | None:
    payload = event.causal_payload
    if not isinstance(payload, Mapping):
        return None
    request = payload.get("institutional_aid_request")
    if not isinstance(request, Mapping):
        return None
    required = {
        "resource_id",
        "source_region_id",
        "destination_region_id",
        "route_id",
        "amount",
        "requester_institution_id",
        "provider_institution_id",
        "installments",
        "urgency",
    }
    if set(request) != required:
        return None
    return dict(request)


def response_affordances(context: AffordanceContext):
    request = aid_request_payload(context.trigger_event)
    if (
        request is None
        or not grounded_trigger(context.trigger_event)
        or proposal_already_answered(context.world, context.trigger_event.id)
    ):
        return ()
    source_id = str(request["source_region_id"])
    destination_id = str(request["destination_region_id"])
    resource_id = str(request["resource_id"])
    if (
        context.actor_ref != EntityRef("region", source_id)
        or str(request["provider_institution_id"]) != city_institution_id(source_id)
        or str(request["requester_institution_id"])
        != city_institution_id(destination_id)
        or not negotiating_city(context.world, source_id)
        or not specified_shipment_is_possible(
            context.world,
            {**request, "amount": float(request["amount"])},
        )
        or has_open_transfer_commitment(
            context.world,
            source_region_id=source_id,
            destination_region_id=destination_id,
            resource_id=resource_id,
        )
    ):
        return ()
    return (
        DomainAffordance(
            domain=context.domain,
            actor_ref=context.actor_ref,
            action_kind=ACCEPT_ACTION,
            target_refs=(EntityRef("region", destination_id),),
            parameters={**request, "request_event_id": context.trigger_event.id},
            urgency=float(request["urgency"]),
            motivation_event_ids=(context.trigger_event.id,),
        ),
    )


def _execute_request(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    **_: Any,
) -> Event:
    destination_id = str(option.parameters["destination_region_id"])
    if not negotiating_city(context.world, destination_id):
        raise StaleAffordanceError("requesting city authority changed")
    event = Event(
        context.world.month_stamp,
        "A city requested material aid from another city.",
        event_type=REQUEST_EVENT_TYPE,
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "source_region_id": str(option.parameters["source_region_id"]),
            "destination_region_id": destination_id,
            "resource_id": str(option.parameters["resource_id"]),
            "amount": float(option.parameters["amount"]),
            "affordance_id": option.id,
        },
        causal_payload={
            "deltas": [],
            "institutional_aid_request": {
                **dict(option.parameters),
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
            str(option.parameters["requester_institution_id"]),
            str(option.parameters["provider_institution_id"]),
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
    params = dict(option.parameters)
    source_id = str(params["source_region_id"])
    if not negotiating_city(context.world, source_id):
        raise StaleAffordanceError("provider authority changed")
    event = Event(
        context.world.month_stamp,
        "A provider city accepted an institutional aid request.",
        event_type="institutional_aid_accepted",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={
            "source_region_id": source_id,
            "destination_region_id": str(params["destination_region_id"]),
            "resource_id": str(params["resource_id"]),
            "amount": float(params["amount"]),
            "affordance_id": option.id,
        },
    )
    evidence = (str(params["request_event_id"]), event.id)
    terms = tuple(
        CommitmentTerm(
            id=f"term:{event.id}:{int(item['index'])}",
            index=int(item["index"]),
            kind=CommitmentTermKind.RESOURCE_TRANSFER,
            obligor_institution_id=str(params["provider_institution_id"]),
            beneficiary_institution_id=str(params["requester_institution_id"]),
            subject=EntityRef("resource", str(params["resource_id"])),
            status=CommitmentTermStatus.ACTIVE,
            proposed_month=int(context.world.month_stamp),
            due_month=int(context.world.month_stamp) + int(item["due_offset"]),
            parameters=(
                ("amount", float(item["amount"])),
                ("destination_region_id", str(params["destination_region_id"])),
                ("route_id", str(params["route_id"])),
                ("source_region_id", source_id),
            ),
            evidence_event_ids=evidence,
        )
        for item in params["installments"]
    )
    commitment = InstitutionalCommitment(
        party_ids=(
            str(params["requester_institution_id"]),
            str(params["provider_institution_id"]),
        ),
        opened_month=int(context.world.month_stamp),
        terms=terms,
        origin_event_id=event.id,
    )
    context.world.institutional_relations.add_commitment(
        commitment,
        context.world.institutional_authority,
    )
    delta = StateDelta(
        event_id=event.id,
        owner_kind="institutional_commitment",
        owner_id=commitment.id,
        aspect="aggregate_status",
        before="none",
        after=commitment.aggregate_status.value,
    )
    event.causal_payload = {
        "deltas": [delta.to_dict()],
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
                cause_event_id=str(params["request_event_id"]),
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
            params,
            institutional_change=1.0,
            commitment_breach=0.0,
        ),
    )
    return event


def _provider_region_id(_world: Any, request_event: Event) -> str | None:
    request = aid_request_payload(request_event)
    return None if request is None else str(request["source_region_id"])


def refusal_event(
    world: Any,
    request_event: Event,
    decision_event_id: str,
) -> Event:
    request = aid_request_payload(request_event)
    event = Event(
        world.month_stamp,
        "A provider city declined an institutional aid request.",
        event_type="institutional_aid_refused",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params=(
            {}
            if request is None
            else {
                "source_region_id": str(request["source_region_id"]),
                "destination_region_id": str(request["destination_region_id"]),
                "resource_id": str(request["resource_id"]),
                "amount": float(request["amount"]),
            }
        ),
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
                cause_event_id=request_event.id,
                relation=CausalRelation.RESPONSE_TO,
            ),
        )
    )
    if request is not None:
        record_institutional_fact(
            world,
            event,
            (
                str(request["requester_institution_id"]),
                str(request["provider_institution_id"]),
            ),
            memory_factors=transfer_memory_factors(
                world,
                request,
                institutional_change=0.0,
                commitment_breach=0.0,
            ),
        )
    return event


for _domain, _provider in (
    (REQUEST_DOMAIN, request_affordances),
    (RESPONSE_DOMAIN, response_affordances),
):
    DOMAIN_AFFORDANCES.register_provider(_domain, _provider)

for _action, _executor in (
    (REQUEST_ACTION, _execute_request),
    (ACCEPT_ACTION, _execute_acceptance),
):
    DOMAIN_AFFORDANCES.register_executor(_action, _executor)

register_proposal_handler(
    REQUEST_EVENT_TYPE,
    counterparty_region_id=_provider_region_id,
    refusal_event=refusal_event,
    outcome_event_types=frozenset(
        {"institutional_aid_accepted", "institutional_aid_refused"}
    ),
)


__all__ = [
    "ACCEPT_ACTION",
    "REQUEST_ACTION",
    "REQUEST_EVENT_TYPE",
    "aid_request_payload",
    "refusal_event",
    "request_affordances",
    "response_affordances",
]
