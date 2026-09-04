"""Actor-driven institutional aid over canonical regional economies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.domain_affordance import DomainAffordance, DomainDecisionKind
from src.classes.environment.region import CityRegion
from src.classes.event import Event, FactKind
from src.classes.institution import (
    AuthorityScope,
    CommitmentTerm,
    CommitmentTermKind,
    CommitmentTermStatus,
    Institution,
    InstitutionalCommitment,
    InstitutionKind,
)
from src.classes.mechanical_language import EntityRef
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.collective_affordances import economy_affordances
from src.systems.domain_affordance_registry import (
    DOMAIN_AFFORDANCES,
    AffordanceContext,
    StaleAffordanceError,
    stale_affordance_blocked_event,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.institution_authority import can_actor_act_for
from src.systems.institutional_memory import (
    decision_context as institutional_decision_context,
    record_known_fact,
    reinforce_from_evidence,
)
from src.systems.resource_transfer import resolve_specified_resource_transfer

REQUEST_DOMAIN = "institutional_aid_request"
RESPONSE_DOMAIN = "institutional_aid_response"
FULFILLMENT_DOMAIN = "institutional_aid_fulfillment"
REMEDIATION_DOMAIN = "institutional_aid_remediation"
REQUEST_ACTION = "request_institutional_aid"
ACCEPT_ACTION = "accept_institutional_aid"
FULFILL_ACTION = "fulfill_institutional_aid_term"
REMEDIATE_ACTION = "propose_institutional_aid_remediation"
INTERPRETER_TEMPLATE = "institutional_aid_interpreter.txt"
INSTALLMENT_DUE_OFFSETS = (1, 2)


def city_institution_id(region_id: int | str) -> str:
    return Institution.id_for(
        InstitutionKind.CITY,
        EntityRef("region", str(region_id)),
    )


def _city(world: Any, region_id: int | str) -> CityRegion | None:
    try:
        region = world.map.regions.get(int(region_id))
    except (AttributeError, TypeError, ValueError):
        return None
    return region if isinstance(region, CityRegion) else None


def _active_city_institution(world: Any, region_id: int | str) -> bool:
    institution = world.institutional_authority.get_institution(
        city_institution_id(region_id)
    )
    return institution is not None and institution.is_active(int(world.month_stamp))


def has_institutional_aid_requester(world: Any, region_id: int | str) -> bool:
    return _active_city_institution(world, region_id) and _city_authorized(
        world,
        region_id,
        AuthorityScope.COMMITMENT_NEGOTIATION,
    )


def has_institutional_aid_request_option(world: Any, shortage_event: Event) -> bool:
    params = shortage_event.render_params or {}
    destination = _city(world, str(params.get("region_id", "")))
    if destination is None:
        return False
    context = AffordanceContext(
        world,
        REQUEST_DOMAIN,
        EntityRef("region", str(destination.id)),
        shortage_event,
    )
    return bool(DOMAIN_AFFORDANCES.compose(context))


def _city_authorized(
    world: Any,
    region_id: int | str,
    scope: AuthorityScope,
    *,
    material: bool = False,
) -> bool:
    region_ref = EntityRef("region", str(region_id))
    return can_actor_act_for(
        world,
        region_ref,
        region_ref,
        scope,
        current_month=int(world.month_stamp),
        require_material_control=material,
        material_target_ref=region_ref if material else None,
    ).allowed


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


def _has_open_aid_commitment(
    world: Any,
    *,
    source_region_id: str,
    destination_region_id: str,
    resource_id: str,
) -> bool:
    for commitment in world.institutional_relations.commitments.values():
        for term in commitment.terms:
            params = dict(term.parameters)
            if (
                term.kind is CommitmentTermKind.RESOURCE_TRANSFER
                and term.status
                in {
                    CommitmentTermStatus.PROPOSED,
                    CommitmentTermStatus.ACTIVE,
                    CommitmentTermStatus.REMEDIATION_PROPOSED,
                }
                and term.subject.id == resource_id
                and str(params.get("source_region_id", "")) == source_region_id
                and str(params.get("destination_region_id", ""))
                == destination_region_id
            ):
                return True
    return False


def request_affordances(context: AffordanceContext):
    if context.actor_ref.kind != "region":
        return ()
    destination = _city(context.world, context.actor_ref.id)
    if (
        destination is None
        or not _active_city_institution(context.world, destination.id)
        or not _city_authorized(
            context.world,
            destination.id,
            AuthorityScope.COMMITMENT_NEGOTIATION,
        )
    ):
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
        if not _active_city_institution(
            context.world, source_id
        ) or not _city_authorized(
            context.world,
            source_id,
            AuthorityScope.COMMITMENT_NEGOTIATION,
        ):
            continue
        if _has_open_aid_commitment(
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


def _aid_request_payload(event: Event) -> dict[str, Any] | None:
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


def _specified_shipment_is_possible(world: Any, params: Mapping[str, Any]) -> bool:
    source = _city(world, params.get("source_region_id", ""))
    destination = _city(world, params.get("destination_region_id", ""))
    resource_id = str(params.get("resource_id", ""))
    route_id = str(params.get("route_id", ""))
    try:
        amount = float(params.get("amount", 0.0))
    except (TypeError, ValueError):
        return False
    if source is None or destination is None or amount <= 0:
        return False
    route = world.map.routes.get(route_id)
    if (
        route is None
        or not route.enabled
        or not route.connects(source.id, destination.id)
        or not route.allows_resource(resource_id)
        or world.map.get_route_operational_capacity(route_id) < amount
    ):
        return False
    source_stock = source.economy.available_stock(resource_id)
    if source_stock is None or source_stock < amount:
        return False
    if (
        resource_id not in source.economy.access
        or resource_id not in destination.economy.access
        or source.economy.access[resource_id] <= 0
        or destination.economy.access[resource_id] <= 0
        or resource_id not in destination.economy.stocks
        or resource_id not in destination.economy.capacities
    ):
        return False
    return (
        destination.economy.capacities[resource_id]
        - destination.economy.stocks[resource_id]
        >= amount
    )


def _transfer_memory_factors(
    world: Any,
    params: Mapping[str, Any],
    *,
    institutional_change: float,
    commitment_breach: float,
) -> tuple[tuple[str, float], ...]:
    source = _city(world, str(params.get("source_region_id", "")))
    resource_id = str(params.get("resource_id", ""))
    amount = float(params.get("amount", 0.0))
    capacity = (
        float(source.economy.capacities.get(resource_id, 0.0))
        if source is not None
        else 0.0
    )
    relative_scale = min(1.0, amount / max(capacity, amount, 1.0))
    return (
        ("relative_scale", relative_scale),
        ("institutional_change", institutional_change),
        ("commitment_breach", commitment_breach),
        ("identity_anchor_impact", 0.0),
    )


def response_affordances(context: AffordanceContext):
    request = _aid_request_payload(context.trigger_event)
    if request is None:
        return ()
    source_id = str(request["source_region_id"])
    destination_id = str(request["destination_region_id"])
    resource_id = str(request["resource_id"])
    if (
        context.actor_ref != EntityRef("region", source_id)
        or str(request["provider_institution_id"]) != city_institution_id(source_id)
        or str(request["requester_institution_id"])
        != city_institution_id(destination_id)
        or not _active_city_institution(context.world, source_id)
        or not _city_authorized(
            context.world,
            source_id,
            AuthorityScope.COMMITMENT_NEGOTIATION,
        )
        or not _specified_shipment_is_possible(
            context.world,
            {**request, "amount": float(request["amount"])},
        )
        or _has_open_aid_commitment(
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
            target_refs=(EntityRef("region", str(request["destination_region_id"])),),
            parameters={**request, "request_event_id": context.trigger_event.id},
            urgency=float(request["urgency"]),
            motivation_event_ids=(context.trigger_event.id,),
        ),
    )


def _commitment_for_origin(world: Any, event_id: str) -> InstitutionalCommitment | None:
    return next(
        (
            commitment
            for commitment in world.institutional_relations.commitments.values()
            if commitment.origin_event_id == event_id
        ),
        None,
    )


def fulfillment_affordances(context: AffordanceContext):
    commitment = _commitment_for_origin(context.world, context.trigger_event.id)
    if commitment is None or int(context.world.month_stamp) <= commitment.opened_month:
        return ()
    options: list[DomainAffordance] = []
    current_month = int(context.world.month_stamp)
    for term in commitment.terms:
        if term.status not in {
            CommitmentTermStatus.ACTIVE,
            CommitmentTermStatus.REMEDIATION_PROPOSED,
        }:
            continue
        if (
            term.status is CommitmentTermStatus.ACTIVE
            and term.due_month is not None
            and current_month > term.due_month
        ):
            continue
        params = dict(term.parameters)
        params["resource_id"] = term.subject.id
        source_id = str(params.get("source_region_id", ""))
        if (
            context.actor_ref != EntityRef("region", source_id)
            or not _city_authorized(
                context.world,
                source_id,
                AuthorityScope.RESOURCE_DISPOSITION,
                material=True,
            )
            or not _specified_shipment_is_possible(context.world, params)
        ):
            continue
        due = (
            term.due_month
            if term.due_month is not None
            else int(context.world.month_stamp)
        )
        month_distance = int(context.world.month_stamp) - due
        urgency = (
            min(1.0, 0.9 + month_distance * 0.1)
            if month_distance >= 0
            else max(0.65, 0.9 + month_distance * 0.1)
        )
        options.append(
            DomainAffordance(
                domain=context.domain,
                actor_ref=context.actor_ref,
                action_kind=FULFILL_ACTION,
                target_refs=(
                    EntityRef("region", str(params["destination_region_id"])),
                ),
                parameters={
                    **params,
                    "commitment_id": commitment.id,
                    "term_id": term.id,
                },
                urgency=urgency,
                motivation_event_ids=tuple(
                    dict.fromkeys(
                        (commitment.origin_event_id, *term.evidence_event_ids)
                    )
                ),
            )
        )
    return tuple(options)


def remediation_affordances(context: AffordanceContext):
    options: list[DomainAffordance] = []
    for commitment in context.world.institutional_relations.commitments.values():
        for term in commitment.terms:
            if (
                term.status is not CommitmentTermStatus.BREACHED
                or context.trigger_event.id not in term.breach_event_ids
            ):
                continue
            params = dict(term.parameters)
            params["resource_id"] = term.subject.id
            source_id = str(params.get("source_region_id", ""))
            if (
                context.actor_ref != EntityRef("region", source_id)
                or not _city_authorized(
                    context.world,
                    source_id,
                    AuthorityScope.COMMITMENT_NEGOTIATION,
                )
                or not _specified_shipment_is_possible(context.world, params)
            ):
                continue
            options.append(
                DomainAffordance(
                    domain=context.domain,
                    actor_ref=context.actor_ref,
                    action_kind=REMEDIATE_ACTION,
                    target_refs=(
                        EntityRef("region", str(params["destination_region_id"])),
                    ),
                    parameters={
                        **params,
                        "commitment_id": commitment.id,
                        "term_id": term.id,
                    },
                    urgency=0.9,
                    motivation_event_ids=(context.trigger_event.id,),
                )
            )
    return tuple(options)


def _execute_request(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    **_: Any,
) -> Event:
    destination_id = str(option.parameters["destination_region_id"])
    if not _city_authorized(
        context.world,
        destination_id,
        AuthorityScope.COMMITMENT_NEGOTIATION,
    ):
        raise StaleAffordanceError("requesting city authority changed")
    event = Event(
        context.world.month_stamp,
        "A city requested material aid from another city.",
        event_type="institutional_aid_requested",
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
    _record_institutional_fact(
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
    if not _city_authorized(
        context.world,
        source_id,
        AuthorityScope.COMMITMENT_NEGOTIATION,
    ):
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
    _record_institutional_fact(
        context.world,
        event,
        commitment.party_ids,
        memory_factors=_transfer_memory_factors(
            context.world,
            params,
            institutional_change=1.0,
            commitment_breach=0.0,
        ),
    )
    return event


def _execute_fulfillment(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    invalidations: DomainInvalidationQueue | None = None,
    **_: Any,
) -> Event:
    params = option.parameters
    source = _city(context.world, str(params["source_region_id"]))
    destination = _city(context.world, str(params["destination_region_id"]))
    if source is None or destination is None:
        raise StaleAffordanceError("committed city disappeared")
    event = resolve_specified_resource_transfer(
        context.world,
        source=source,
        destination=destination,
        resource_id=str(params["resource_id"]),
        route_id=str(params["route_id"]),
        amount=float(params["amount"]),
        decision_event_id=decision_event_id,
        invalidations=invalidations,
    )
    event.causal_payload["affordance_id"] = option.id
    event.causal_payload["commitment_id"] = str(params["commitment_id"])
    event.causal_payload["term_id"] = str(params["term_id"])
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=context.trigger_event.id,
            relation=CausalRelation.CONTRIBUTED_TO,
        )
    )
    return event


def _execute_remediation_proposal(
    context: AffordanceContext,
    option: DomainAffordance,
    *,
    decision_event_id: str,
    **_: Any,
) -> Event:
    params = option.parameters
    source_id = str(params["source_region_id"])
    if not _city_authorized(
        context.world,
        source_id,
        AuthorityScope.COMMITMENT_NEGOTIATION,
    ):
        raise StaleAffordanceError("remediation authority changed")
    event = Event(
        context.world.month_stamp,
        "The obligor proposed material remediation for a breached aid term.",
        event_type="institutional_commitment_remediation_proposed",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "deltas": [],
            "commitment_id": str(params["commitment_id"]),
            "term_id": str(params["term_id"]),
            "affordance_id": option.id,
        },
    )
    context.world.institutional_relations.propose_remediation(
        str(params["commitment_id"]),
        str(params["term_id"]),
        proposed_month=int(context.world.month_stamp),
        event_id=event.id,
        authority_state=context.world.institutional_authority,
    )
    event.causal_payload["deltas"] = [
        StateDelta(
            event_id=event.id,
            owner_kind="institutional_commitment",
            owner_id=str(params["commitment_id"]),
            aspect=f"term:{params['term_id']}:status",
            before=CommitmentTermStatus.BREACHED.value,
            after=CommitmentTermStatus.REMEDIATION_PROPOSED.value,
        ).to_dict()
    ]
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
                relation=CausalRelation.RESPONSE_TO,
            ),
        )
    )
    commitment = context.world.institutional_relations.commitments[
        str(params["commitment_id"])
    ]
    _record_institutional_fact(
        context.world,
        event,
        commitment.party_ids,
        memory_factors=_transfer_memory_factors(
            context.world,
            params,
            institutional_change=1.0,
            commitment_breach=1.0,
        ),
    )
    return event


def _refusal_event(
    world: Any,
    request_event: Event,
    decision_event_id: str,
) -> Event:
    event = Event(
        world.month_stamp,
        "A provider city declined an institutional aid request.",
        event_type="institutional_aid_refused",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
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
    request = _aid_request_payload(request_event)
    if request is not None:
        _record_institutional_fact(
            world,
            event,
            (
                str(request["requester_institution_id"]),
                str(request["provider_institution_id"]),
            ),
            memory_factors=_transfer_memory_factors(
                world,
                request,
                institutional_change=0.0,
                commitment_breach=0.0,
            ),
        )
    return event


def _record_institutional_fact(
    world: Any,
    event: Event,
    institution_ids: tuple[str, ...],
    *,
    memory_factors: tuple[tuple[str, float], ...] = (),
) -> None:
    record_known_fact(
        world,
        event,
        institution_ids,
        factors=dict(memory_factors) if memory_factors else None,
    )


def _mark_term_fulfilled(
    world: Any,
    commitment_id: str,
    term_id: str,
    transfer_event: Event,
) -> Event:
    commitment = world.institutional_relations.commitments[commitment_id]
    current_term = next(term for term in commitment.terms if term.id == term_id)
    before_status = current_term.status
    if before_status is CommitmentTermStatus.REMEDIATION_PROPOSED:
        after_status = CommitmentTermStatus.REMEDIATED
        world.institutional_relations.remediate_term(
            commitment_id,
            term_id,
            settled_month=int(world.month_stamp),
            event_id=transfer_event.id,
            authority_state=world.institutional_authority,
        )
        event_type = "institutional_commitment_term_remediated"
        content = "A breached institutional aid term was materially remediated."
    else:
        after_status = CommitmentTermStatus.FULFILLED
        world.institutional_relations.fulfill_term(
            commitment_id,
            term_id,
            settled_month=int(world.month_stamp),
            event_id=transfer_event.id,
            authority_state=world.institutional_authority,
        )
        event_type = "institutional_commitment_term_fulfilled"
        content = "An institutional aid term was fulfilled."
    event = Event(
        world.month_stamp,
        content,
        event_type=event_type,
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.DETERMINISTIC,
        causal_payload={
            "deltas": [
                StateDelta(
                    event_id="pending",
                    owner_kind="institutional_commitment",
                    owner_id=commitment_id,
                    aspect=f"term:{term_id}:status",
                    before=before_status.value,
                    after=after_status.value,
                ).to_dict()
            ],
            "commitment_id": commitment_id,
            "term_id": term_id,
        },
    )
    event.causal_payload["deltas"][0]["event_id"] = event.id
    event.causal_links.append(
        CausalLink(
            event_id=event.id,
            cause_event_id=transfer_event.id,
            relation=CausalRelation.TRIGGERED_BY,
        )
    )
    if before_status is CommitmentTermStatus.REMEDIATION_PROPOSED:
        # The newest breach points to its predecessor, so one RESOLVES edge to
        # the newest breach keeps the complete history navigable without
        # crowding out the material transfer edge under the global cap of 8.
        event.causal_links.append(
            CausalLink(
                event_id=event.id,
                cause_event_id=current_term.breach_event_ids[-1],
                relation=CausalRelation.RESOLVES,
            )
        )
    params = {**dict(current_term.parameters), "resource_id": current_term.subject.id}
    _record_institutional_fact(
        world,
        event,
        commitment.party_ids,
        memory_factors=_transfer_memory_factors(
            world,
            params,
            institutional_change=1.0,
            commitment_breach=(
                1.0
                if before_status is CommitmentTermStatus.REMEDIATION_PROPOSED
                else 0.0
            ),
        ),
    )
    return event


def process_institutional_aid_deadlines(
    world: Any,
    *,
    budget: CausalBudget | None = None,
    evaluation_budget: int = 4,
) -> list[Event]:
    produced: list[Event] = []
    month = int(world.month_stamp)
    evaluated = 0
    for commitment in sorted(
        world.institutional_relations.commitments.values(),
        key=lambda item: item.id,
    ):
        for term in commitment.terms:
            if evaluated >= max(0, int(evaluation_budget)):
                return produced
            cause_event_id = commitment.origin_event_id
            if term.status is CommitmentTermStatus.ACTIVE:
                if term.due_month is None or month <= term.due_month:
                    continue
            elif term.status is CommitmentTermStatus.REMEDIATION_PROPOSED:
                proposal_event = world.event_manager.get_event_by_id(
                    term.evidence_event_ids[-1]
                )
                if proposal_event is None or month <= int(proposal_event.month_stamp):
                    continue
                cause_event_id = proposal_event.id
            else:
                continue
            evaluated += 1
            if budget is not None and not budget.consume_domain_mutation():
                return produced
            before_status = term.status
            event = Event(
                world.month_stamp,
                "An institutional aid term passed its deadline unfulfilled.",
                event_type="institutional_commitment_term_breached",
                fact_kind=FactKind.STATE_TRANSITION,
                causal_origin=CausalOrigin.DETERMINISTIC,
                causal_payload={
                    "deltas": [],
                    "commitment_id": commitment.id,
                    "term_id": term.id,
                },
            )
            world.institutional_relations.breach_term(
                commitment.id,
                term.id,
                breached_month=month,
                event_id=event.id,
                authority_state=world.institutional_authority,
            )
            event.causal_payload["deltas"] = [
                StateDelta(
                    event_id=event.id,
                    owner_kind="institutional_commitment",
                    owner_id=commitment.id,
                    aspect=f"term:{term.id}:status",
                    before=before_status.value,
                    after=CommitmentTermStatus.BREACHED.value,
                ).to_dict()
            ]
            event.causal_links.append(
                CausalLink(
                    event_id=event.id,
                    cause_event_id=cause_event_id,
                    relation=CausalRelation.TRIGGERED_BY,
                )
            )
            if term.breach_event_ids:
                event.causal_links.append(
                    CausalLink(
                        event_id=event.id,
                        cause_event_id=term.breach_event_ids[-1],
                        relation=CausalRelation.RESPONSE_TO,
                    )
                )
            params = {**dict(term.parameters), "resource_id": term.subject.id}
            _record_institutional_fact(
                world,
                event,
                commitment.party_ids,
                memory_factors=_transfer_memory_factors(
                    world,
                    params,
                    institutional_change=1.0,
                    commitment_breach=1.0,
                ),
            )
            # The latest predecessor is sufficient: breach events themselves
            # form a navigable chain, while memory work remains bounded.
            if term.breach_event_ids:
                for institution_id in commitment.party_ids:
                    reinforce_from_evidence(
                        world,
                        institution_id=institution_id,
                        remembered_event_id=term.breach_event_ids[-1],
                        evidence_event=event,
                    )
            produced.append(event)
    return produced


async def process_institutional_aid_shortage(
    world: Any,
    shortage_event: Event,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    request_force_rule: bool = False,
    response_force_rule: bool = False,
    budget: CausalBudget | None = None,
) -> list[Event]:
    params = shortage_event.render_params or {}
    destination = _city(world, str(params.get("region_id", "")))
    if destination is None:
        return []
    request_context = AffordanceContext(
        world,
        REQUEST_DOMAIN,
        EntityRef("region", str(destination.id)),
        shortage_event,
    )
    request_options = DOMAIN_AFFORDANCES.compose(request_context)
    request_decision, request_decision_event = await interpret_domain_affordances(
        world,
        domain=REQUEST_DOMAIN,
        actor_ref=request_context.actor_ref,
        actor_label=destination.name,
        trigger_event=shortage_event,
        affordances=request_options,
        task_name="institutional_aid_request_interpreter",
        template_name=INTERPRETER_TEMPLATE,
        extra_context={
            "role": "requester",
            "institution": institutional_decision_context(
                world,
                city_institution_id(destination.id),
                event_overlays=(shortage_event,),
            ),
        },
        llm_call=llm_call,
        force_rule=request_force_rule,
    )
    events = [request_decision_event]
    if request_decision.decision is not DomainDecisionKind.ACT:
        return events
    try:
        request_event = DOMAIN_AFFORDANCES.execute(
            request_context,
            request_decision.selected_affordance_id or "",
            decision_event_id=request_decision_event.id,
        )
    except StaleAffordanceError:
        events.append(
            stale_affordance_blocked_event(
                request_context,
                decision_event_id=request_decision_event.id,
                selected_affordance_id=request_decision.selected_affordance_id or "",
            )
        )
        return events
    events.append(request_event)
    request = _aid_request_payload(request_event)
    if request is None:
        return events
    provider = _city(world, str(request["source_region_id"]))
    if provider is None:
        return events
    response_context = AffordanceContext(
        world,
        RESPONSE_DOMAIN,
        EntityRef("region", str(provider.id)),
        request_event,
    )
    response_options = DOMAIN_AFFORDANCES.compose(response_context)
    response_decision, response_decision_event = await interpret_domain_affordances(
        world,
        domain=RESPONSE_DOMAIN,
        actor_ref=response_context.actor_ref,
        actor_label=provider.name,
        trigger_event=request_event,
        affordances=response_options,
        task_name="institutional_aid_response_interpreter",
        template_name=INTERPRETER_TEMPLATE,
        extra_context={
            "role": "provider",
            "institution": institutional_decision_context(
                world,
                city_institution_id(provider.id),
                event_overlays=(request_event,),
            ),
        },
        llm_call=llm_call,
        force_rule=response_force_rule,
    )
    events.append(response_decision_event)
    if response_decision.decision is not DomainDecisionKind.ACT:
        events.append(_refusal_event(world, request_event, response_decision_event.id))
        return events
    if budget is not None and not budget.consume_domain_mutation():
        return events
    try:
        events.append(
            DOMAIN_AFFORDANCES.execute(
                response_context,
                response_decision.selected_affordance_id or "",
                decision_event_id=response_decision_event.id,
            )
        )
    except StaleAffordanceError:
        events.append(
            stale_affordance_blocked_event(
                response_context,
                decision_event_id=response_decision_event.id,
                selected_affordance_id=response_decision.selected_affordance_id or "",
            )
        )
    return events


async def process_institutional_aid_fulfillment(
    world: Any,
    *,
    invalidations: DomainInvalidationQueue,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
    evaluation_budget: int = 8,
    llm_budget: int = 2,
) -> list[Event]:
    produced: list[Event] = []
    evaluations = 0
    llm_calls = 0
    for commitment in sorted(
        world.institutional_relations.commitments.values(),
        key=lambda item: item.id,
    ):
        trigger = world.event_manager.get_event_by_id(commitment.origin_event_id)
        if trigger is None:
            continue
        source_ids = {
            str(dict(term.parameters).get("source_region_id", ""))
            for term in commitment.terms
            if term.status
            in {
                CommitmentTermStatus.ACTIVE,
                CommitmentTermStatus.REMEDIATION_PROPOSED,
            }
        }
        for source_id in sorted(item for item in source_ids if item):
            if evaluations >= max(0, int(evaluation_budget)):
                return produced
            if budget is not None and not budget.consume_propagation_step():
                return produced
            source = _city(world, source_id)
            if source is None:
                continue
            context = AffordanceContext(
                world,
                FULFILLMENT_DOMAIN,
                EntityRef("region", source_id),
                trigger,
            )
            options = DOMAIN_AFFORDANCES.compose(context)
            if not options:
                continue
            evaluations += 1
            use_llm = llm_calls < max(0, int(llm_budget)) and (
                budget is None or budget.consume_interpreter_call()
            )
            if use_llm:
                llm_calls += 1
            decision, decision_event = await interpret_domain_affordances(
                world,
                domain=FULFILLMENT_DOMAIN,
                actor_ref=context.actor_ref,
                actor_label=source.name,
                trigger_event=trigger,
                affordances=options,
                task_name="institutional_aid_fulfillment_interpreter",
                template_name=INTERPRETER_TEMPLATE,
                extra_context={
                    "role": "obligor",
                    "commitment_id": commitment.id,
                    "institution": institutional_decision_context(
                        world,
                        city_institution_id(source.id),
                        event_overlays=(trigger,),
                    ),
                },
                llm_call=llm_call,
                force_rule=not use_llm,
            )
            produced.append(decision_event)
            if decision.decision is not DomainDecisionKind.ACT:
                continue
            if budget is not None and not budget.consume_domain_mutation():
                continue
            try:
                transfer = DOMAIN_AFFORDANCES.execute(
                    context,
                    decision.selected_affordance_id or "",
                    decision_event_id=decision_event.id,
                    invalidations=invalidations,
                )
            except StaleAffordanceError:
                produced.append(
                    stale_affordance_blocked_event(
                        context,
                        decision_event_id=decision_event.id,
                        selected_affordance_id=decision.selected_affordance_id or "",
                    )
                )
                continue
            produced.append(transfer)
            if transfer.event_type == "regional_resource_transfer_completed":
                selected = next(
                    option
                    for option in options
                    if option.id == decision.selected_affordance_id
                )
                produced.append(
                    _mark_term_fulfilled(
                        world,
                        str(selected.parameters["commitment_id"]),
                        str(selected.parameters["term_id"]),
                        transfer,
                    )
                )
    return produced


async def process_institutional_aid_remediation(
    world: Any,
    *,
    llm_call: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    budget: CausalBudget | None = None,
    evaluation_budget: int = 8,
    llm_budget: int = 2,
) -> list[Event]:
    """Let obligors decide whether to reopen a materially viable breached term."""

    produced: list[Event] = []
    evaluations = 0
    llm_calls = 0
    candidates: list[tuple[InstitutionalCommitment, CommitmentTerm, Event]] = []
    for commitment in world.institutional_relations.commitments.values():
        for term in commitment.terms:
            if (
                term.status is not CommitmentTermStatus.BREACHED
                or not term.breach_event_ids
            ):
                continue
            breach = world.event_manager.get_event_by_id(term.breach_event_ids[-1])
            if breach is not None:
                candidates.append((commitment, term, breach))

    for commitment, term, breach in sorted(
        candidates,
        key=lambda item: (item[0].id, item[1].id),
    ):
        if evaluations >= max(0, int(evaluation_budget)):
            break
        if budget is not None and not budget.consume_propagation_step():
            break
        source_id = str(dict(term.parameters).get("source_region_id", ""))
        source = _city(world, source_id)
        if source is None:
            continue
        context = AffordanceContext(
            world,
            REMEDIATION_DOMAIN,
            EntityRef("region", source_id),
            breach,
        )
        options = DOMAIN_AFFORDANCES.compose(context)
        if not options:
            continue
        evaluations += 1
        use_llm = llm_calls < max(0, int(llm_budget)) and (
            budget is None or budget.consume_interpreter_call()
        )
        if use_llm:
            llm_calls += 1
        decision, decision_event = await interpret_domain_affordances(
            world,
            domain=REMEDIATION_DOMAIN,
            actor_ref=context.actor_ref,
            actor_label=source.name,
            trigger_event=breach,
            affordances=options,
            task_name="institutional_aid_remediation_interpreter",
            template_name=INTERPRETER_TEMPLATE,
            extra_context={
                "role": "obligor",
                "commitment_id": commitment.id,
                "institution": institutional_decision_context(
                    world,
                    city_institution_id(source.id),
                    event_overlays=(breach,),
                ),
            },
            llm_call=llm_call,
            force_rule=not use_llm,
        )
        produced.append(decision_event)
        if decision.decision is not DomainDecisionKind.ACT:
            continue
        if budget is not None and not budget.consume_domain_mutation():
            continue
        try:
            produced.append(
                DOMAIN_AFFORDANCES.execute(
                    context,
                    decision.selected_affordance_id or "",
                    decision_event_id=decision_event.id,
                )
            )
        except StaleAffordanceError:
            produced.append(
                stale_affordance_blocked_event(
                    context,
                    decision_event_id=decision_event.id,
                    selected_affordance_id=decision.selected_affordance_id or "",
                )
            )
    return produced


for _domain, _provider in (
    (REQUEST_DOMAIN, request_affordances),
    (RESPONSE_DOMAIN, response_affordances),
    (FULFILLMENT_DOMAIN, fulfillment_affordances),
    (REMEDIATION_DOMAIN, remediation_affordances),
):
    DOMAIN_AFFORDANCES.register_provider(_domain, _provider)

for _action, _executor in (
    (REQUEST_ACTION, _execute_request),
    (ACCEPT_ACTION, _execute_acceptance),
    (FULFILL_ACTION, _execute_fulfillment),
    (REMEDIATE_ACTION, _execute_remediation_proposal),
):
    DOMAIN_AFFORDANCES.register_executor(_action, _executor)


__all__ = [
    "FULFILLMENT_DOMAIN",
    "REMEDIATION_DOMAIN",
    "REQUEST_DOMAIN",
    "RESPONSE_DOMAIN",
    "city_institution_id",
    "fulfillment_affordances",
    "has_institutional_aid_request_option",
    "has_institutional_aid_requester",
    "process_institutional_aid_deadlines",
    "process_institutional_aid_fulfillment",
    "process_institutional_aid_remediation",
    "process_institutional_aid_shortage",
    "request_affordances",
    "response_affordances",
]
