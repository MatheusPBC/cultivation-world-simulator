"""Public petitions: an aggregate population addressing the city that governs it.

Wave 10's civil slice, protest only. A population under grounded, detrimental
pressure may address the institution that governs its region instead of only
migrating away from it. Filing is one option among the existing ones and never
a forced outcome: migrating and doing nothing stay valid.

This owns exactly one thing -- the petition fact and what the addressed
institution comes to know from it. It creates no organization, no named
leader, no faction, no prestige or hostility, no obligation, and no planner.
Nothing here compels a repair: the government answers through its own existing
`_city_options` menu, on its own decision, and may maintain.
"""

from __future__ import annotations

import json
from typing import Any

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.causal_origin import CausalOrigin
from src.classes.event import Event, FactKind
from src.classes.institution import KnowledgeChannel
from src.classes.mechanical_language import DomainReactionReceipt, EntityRef
from src.classes.mechanical_language.models import PrimitiveDimension
from src.classes.regional_economy import MAX_STOPPAGE_PARTICIPATION
from src.classes.state_delta import StateDelta

PETITION_ACTION = "file_public_petition"
PETITION_EVENT_TYPE = "civil_public_petition"
PETITION_RECEIPT_DOMAIN = "civil_petition"
RESPONSE_RECEIPT_DOMAIN = "civil_petition_response"
STOPPAGE_ACTION = "declare_work_stoppage"
STOPPAGE_EVENT_TYPE = "civil_work_stoppage_started"
STOPPAGE_ENDED_EVENT_TYPE = "civil_work_stoppage_ended"
STOPPAGE_RECEIPT_DOMAIN = "civil_work_stoppage"
STOPPAGE_RESPONSE_RECEIPT_DOMAIN = "civil_work_stoppage_response"
# How far back a government still recognises an unanswered petition.
PETITION_RESPONSE_WINDOW_MONTHS = 12
# A high reading on these dimensions is a burden being borne, not a benefit.
# Polarity is read from the mechanical grammar itself, never from an event
# type or a disaster's name.
DETRIMENTAL_DIMENSIONS = frozenset({PrimitiveDimension.RISK, PrimitiveDimension.LOAD})


def condition_metric(world: Any, condition: Any):
    """The derived metric a condition is defined on, or nothing."""
    language = getattr(world, "mechanical_language", None)
    if language is None or condition is None:
        return None
    definition = language.condition_definitions.get(condition.definition_id)
    if definition is None:
        return None
    return language.derived_definitions.get(definition.metric_definition_id)


def is_detrimental_condition(world: Any, condition: Any) -> bool:
    """Whether this active condition is pressure being suffered.

    An active condition is not automatically a grievance: a high `access` or
    `quality` reading is a good thing. Only a load or a risk is something a
    population could reasonably petition about.
    """
    metric = condition_metric(world, condition)
    return metric is not None and metric.dimension in DETRIMENTAL_DIMENSIONS


def petition_receipt_id(region_id: str, condition_instance_id: str) -> str:
    """One petition per region per condition instance.

    Keyed by the condition instance, so the same grievance is not filed every
    month, while a genuinely new instance -- the pressure resolved and
    returned -- may be petitioned again. It closes only this reaction: other
    domains keep reacting to the same unresolved pressure through their own
    receipts.
    """
    return DomainReactionReceipt.create(
        f"civil-petition:{region_id}:{condition_instance_id}",
        PETITION_RECEIPT_DOMAIN,
        str(condition_instance_id),
        # Only the derived ID matters here; an acting receipt would require an
        # affordance that this lookup does not have.
        decision="maintain",
        affordance_id=None,
    ).id


def already_petitioned(world: Any, region_id: str, condition_instance_id: str) -> bool:
    return (
        petition_receipt_id(region_id, condition_instance_id)
        in world.mechanical_language.reaction_receipts
    )


def governing_institution_ref(world: Any, region: Any) -> EntityRef | None:
    """The institution that governs this region, as an institution.

    An `EntityRef` to the institution, never a stand-in for whoever currently
    holds its office: a petition is addressed to the office, and it survives
    the holder changing.
    """
    governance = getattr(getattr(region, "city_state", None), "governance", None)
    controller_kind = str(getattr(governance, "controller_kind", "") or "")
    controller_id = str(getattr(governance, "controller_id", "") or "")
    if controller_kind != "dynasty" or not controller_id:
        return None
    return EntityRef("dynasty", controller_id)


def can_file_public_petition_basis(
    world: Any, region: Any, condition: Any, *, overlays: Any = None
) -> bool:
    """The grounding both civil options share, without the petition receipt.

    A real population, this region's own live detrimental condition, a real
    non-Story cause, and an institution that actually governs here.
    """
    if region is None or condition is None:
        return False
    try:
        if float(region.population) <= 0:
            return False
    except (TypeError, ValueError):
        return False
    if (
        str(getattr(condition, "target_kind", "")) != "region"
        or str(getattr(condition, "target_id", "")) != str(region.id)
    ):
        return False
    if not condition.is_active(int(world.month_stamp)):
        return False
    language = getattr(world, "mechanical_language", None)
    if language is None or language.condition_instances.get(condition.id) is not condition:
        return False
    if not is_detrimental_condition(world, condition):
        return False
    cause = _cause_event(world, condition, overlays)
    if cause is None or bool(getattr(cause, "is_story", False)):
        return False
    institution_ref = governing_institution_ref(world, region)
    if institution_ref is None:
        return False
    authority = getattr(world, "institutional_authority", None)
    return authority is not None and (
        authority.get_institution_for_owner(institution_ref) is not None
    )


def can_file_public_petition(
    world: Any, region: Any, condition: Any, *, overlays: Any = None
) -> bool:
    """Whether a grounded petition is even available to this population.

    Every clause is read from current canonical state: a real population that
    could petition, a condition that is this region's, still active, resting
    on a real non-Story cause, and an institution that actually governs here
    now. A free-standing object that merely looks like a condition qualifies
    for nothing.
    """
    if not can_file_public_petition_basis(world, region, condition, overlays=overlays):
        return False
    return not already_petitioned(world, str(region.id), str(condition.id))


def _cause_event(world: Any, condition: Any, overlays: Any = None):
    """The condition's own cause, from this step's events or the store."""
    cause_id = str(getattr(condition, "cause_event_id", "") or "")
    if not cause_id:
        return None
    for event in overlays or ():
        if getattr(event, "id", None) == cause_id:
            return event
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    return getter(cause_id) if callable(getter) else None


def record_public_petition(
    world: Any,
    *,
    region: Any,
    condition: Any,
    decision_event_id: str,
    affordance_id: str,
    source_event: Event | None,
) -> Event:
    """The petition fact, and what the addressed institution learns from it.

    The fact cites the canonical evidence it rests on -- the condition's own
    cause event and the population's decision -- and carries no obligation:
    it changes no material owner, so its only delta is the knowledge one its
    owner appends.
    """
    from src.i18n import t
    from src.systems.institutional_memory import record_known_fact

    institution_ref = governing_institution_ref(world, region)
    assert institution_ref is not None
    metric = condition_metric(world, condition)
    institution = world.institutional_authority.get_institution_for_owner(
        institution_ref
    )

    event = Event(
        world.month_stamp,
        t(
            "The people of {region} publicly petition their government over {label}.",
            region=getattr(region, "name", str(region.id)),
            label=str(getattr(condition, "label", "") or condition.definition_id),
        ),
        event_type=PETITION_EVENT_TYPE,
        # A public act by an aggregate population, decided by that population.
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={"region_id": str(region.id)},
        causal_payload={
            "deltas": [],
            "civil_petition": {
                "region_id": str(region.id),
                "condition_instance_id": str(condition.id),
                "condition_definition_id": str(condition.definition_id),
                "metric_definition_id": (
                    str(metric.id) if metric is not None else None
                ),
                "metric_dimension": (
                    str(metric.dimension.value) if metric is not None else None
                ),
                "intensity": float(getattr(condition, "intensity", 0.0) or 0.0),
                "addressed_institution_id": (
                    institution.id if institution is not None else None
                ),
                "addressed_institution_ref": institution_ref.to_dict(),
                "evidence_event_ids": [str(condition.cause_event_id)],
            },
        },
    )
    links = [CausalLink(
        event_id=event.id,
        cause_event_id=str(condition.cause_event_id),
        relation=CausalRelation.MOTIVATED_BY,
    )]
    if decision_event_id:
        links.append(CausalLink(
            event_id=event.id,
            cause_event_id=str(decision_event_id),
            relation=CausalRelation.TRIGGERED_BY,
        ))
    if source_event is not None and source_event.id != str(condition.cause_event_id):
        links.append(CausalLink(
            event_id=event.id,
            cause_event_id=source_event.id,
            relation=CausalRelation.ENABLED_BY,
        ))
    event.causal_links.extend(links)

    # Only the institution actually addressed learns it, through the channel
    # a petition really is. No memory is fabricated: what a protest is worth
    # to a government has no engine-owned weight.
    if institution is not None:
        record_known_fact(
            world,
            event,
            (institution.id,),
            channel=KnowledgeChannel.FORMAL_NOTICE,
        )

    receipt = DomainReactionReceipt.create(
        f"civil-petition:{region.id}:{condition.id}",
        PETITION_RECEIPT_DOMAIN,
        str(condition.id),
        decision="act",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,) if decision_event_id else (),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt
    return event


def labor_bearing_resources(region: Any) -> list[str]:
    """Concepts this region really produces with declared collective labour.

    Both halves must be real: labour declared in canonical config, and output
    actually happening. A region with neither is offered no stoppage, so the
    option is never decorative.
    """
    economy = getattr(region, "economy", None)
    if economy is None:
        return []
    bearing = []
    for concept_id, dependence in economy.labor_dependence.items():
        if float(dependence) <= 0.0:
            continue
        if float(economy.production_rates.get(concept_id, 0.0)) <= 0.0:
            continue
        # The monthly balance skips a concept with no stock entry, so output
        # there is not materially possible and stopping it changes nothing.
        if concept_id not in economy.stocks:
            continue
        # A concept with no headroom stores nothing this month either.
        capacity = economy.capacities.get(concept_id)
        if capacity is not None:
            reserved = sum(
                resources.get(concept_id, 0.0)
                for resources in economy.reservations.values()
            )
            headroom = float(capacity) - max(
                float(economy.stocks.get(concept_id, 0.0)), reserved
            )
            if headroom <= 0.0:
                continue
        bearing.append(concept_id)
    return sorted(bearing)


def stoppage_participation(condition: Any) -> float:
    """Engine-owned share, bounded by the pressure's own severity."""
    try:
        intensity = max(0.0, min(1.0, float(getattr(condition, "intensity", 0.0))))
    except (TypeError, ValueError):
        return 0.0
    return round(MAX_STOPPAGE_PARTICIPATION * intensity, 6)


def prior_local_petition(
    world: Any, region: Any, *, condition: Any = None, current_events: Any = None
) -> Event | None:
    """A real petition this region already filed, answered or not.

    Being ignored is not required: a government that answered still leaves the
    people free to stop working, and one that never answered does too.
    """
    def _is_real(event: Event, payload: dict) -> bool:
        """A petition this region really filed, not merely a matching payload."""
        if str(payload.get("region_id", "")) != str(region.id):
            return False
        if (
            getattr(event, "fact_kind", None) is not FactKind.OCCURRENCE
            or getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION
            or bool(getattr(event, "is_story", False))
        ):
            return False
        # It must concern this same grievance, and name a real institution.
        if condition is not None and str(
            payload.get("condition_instance_id", "")
        ) != str(condition.id):
            return False
        institution_id = str(payload.get("addressed_institution_id") or "")
        authority = getattr(world, "institutional_authority", None)
        if not institution_id or authority is None:
            return False
        if authority.get_institution(institution_id) is None:
            return False
        # The addressed institution must be the one that really owns the ref.
        institution = authority.get_institution(institution_id)
        if institution.owner_ref.to_dict() != payload.get("addressed_institution_ref"):
            return False
        # The evidence must be this grievance's own real cause.
        if condition is not None and str(condition.cause_event_id) not in [
            str(item) for item in (payload.get("evidence_event_ids") or ())
        ]:
            return False
        # And the petition must resolve to a real population decision that
        # actually selected it. A payload alone authorizes nothing.
        return _authoring_decision(world, event, current_events) is not None

    def _authoring_decision(world_: Any, event: Event, overlays: Any):
        from src.classes.agent_decision import AgentDecision

        manager_ = getattr(world_, "event_manager", None)
        resolve = getattr(manager_, "get_event_by_id", None)
        # A windowed scan builds its events without causal links:
        # `EventStorage._row_to_event` never fills them, and only
        # `get_event_by_id` hydrates them from the edge table. Reading links
        # off a scanned row would therefore find none after a real load, and
        # every petition would silently fail its own provenance check. So the
        # candidate is re-resolved by id before provenance is judged -- and
        # only the candidate, so this stays one lookup per petition rather
        # than a hydration of every windowed query.
        provenance = event
        if not getattr(event, "causal_links", None) and callable(resolve):
            resolved = resolve(str(event.id))
            if isinstance(resolved, Event):
                provenance = resolved
        event = provenance
        cited = [
            str(link.cause_event_id) for link in getattr(event, "causal_links", ())
            if link.relation is CausalRelation.TRIGGERED_BY
        ]
        affordance_id = str(
            (getattr(event, "causal_payload", None) or {}).get("affordance_id") or ""
        )
        if not cited or not affordance_id:
            return None
        manager = getattr(world_, "event_manager", None)
        getter = getattr(manager, "get_event_by_id", None)
        for decision_id in cited:
            decision_event = next(
                (item for item in (overlays or ()) if item.id == decision_id), None
            ) or (getter(decision_id) if callable(getter) else None)
            if not isinstance(decision_event, Event):
                continue
            if (
                decision_event.fact_kind is not FactKind.DECISION
                or bool(getattr(decision_event, "is_story", False))
            ):
                continue
            payload_ = decision_event.causal_payload
            if not isinstance(payload_, dict) or payload_.get("deltas") != []:
                continue
            try:
                audit = AgentDecision.from_dict(dict(payload_.get("decision") or {}))
            except (AttributeError, TypeError, ValueError):
                continue
            # The population actor is exactly what the interpreter writes:
            # kind `population`, id `region:<id>`. Nothing else is this
            # region's population.
            if (
                audit.subject_kind != "population"
                or str(audit.subject_id) != f"region:{region.id}"
            ):
                continue
            # Authored when the petition was filed, not merely at some point.
            if int(audit.month_stamp) != int(event.month_stamp):
                continue
            # Exactly one selection, and it is this petition's own affordance.
            if audit.chosen_chain != [{"selected_affordance_id": affordance_id}]:
                continue
            # And it answered this grievance's own cause.
            if condition is not None and not any(
                link.relation is CausalRelation.RESPONSE_TO
                and str(link.cause_event_id) == str(condition.cause_event_id)
                for link in getattr(decision_event, "causal_links", ())
            ):
                continue
            return decision_event
        return None

    for event, payload in pending_petitions(world, current_events=current_events):
        if _is_real(event, payload):
            return event
    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    stored = (
        getter(month - PETITION_RESPONSE_WINDOW_MONTHS + 1, month)
        if callable(getter)
        else []
    )
    for event in [*stored, *(current_events or ())]:
        payload = petition_payload(event)
        if payload is not None and _is_real(event, payload):
            return event
    return None


def can_declare_work_stoppage(
    world: Any, region: Any, condition: Any, *, overlays: Any = None
) -> bool:
    """Whether stopping work is even an option here, right now."""
    if region is None or condition is None:
        return False
    economy = getattr(region, "economy", None)
    if economy is None or economy.work_stoppage is not None:
        return False
    if not can_file_public_petition_basis(world, region, condition, overlays=overlays):
        return False
    if not labor_bearing_resources(region):
        return False
    if stoppage_participation(condition) <= 0.0:
        return False
    # One stoppage per grievance. A receipt already spent means this exact
    # condition instance was answered this way; repeating requires a new
    # instance and therefore a new decision. Nothing renews automatically, and
    # the spent receipt stays as audit rather than being overwritten.
    if already_stopped_work(world, str(region.id), str(condition.id)):
        return False
    return prior_local_petition(
        world, region, condition=condition, current_events=overlays
    ) is not None


def stoppage_receipt_id(region_id: str, condition_instance_id: str) -> str:
    return DomainReactionReceipt.create(
        f"civil-stoppage:{region_id}:{condition_instance_id}",
        STOPPAGE_RECEIPT_DOMAIN,
        str(condition_instance_id),
        decision="maintain",
        affordance_id=None,
    ).id


def already_stopped_work(
    world: Any, region_id: str, condition_instance_id: str
) -> bool:
    return (
        stoppage_receipt_id(region_id, condition_instance_id)
        in world.mechanical_language.reaction_receipts
    )


def record_work_stoppage(
    world: Any,
    *,
    region: Any,
    condition: Any,
    petition_event: Event,
    decision_event_id: str,
    affordance_id: str,
) -> Event:
    """The stoppage start fact, and the owner record it schedules.

    The record starts on the next productive cycle and covers exactly that
    cycle. Base production rates are never written; only effective output
    changes, and only for the resources whose labour dependence is declared.
    """
    from src.classes.regional_economy import WorkStoppage
    from src.i18n import t

    month = int(world.month_stamp)
    participation = stoppage_participation(condition)
    affected = labor_bearing_resources(region)
    event = Event(
        world.month_stamp,
        t(
            "The people of {region} stop working for one cycle.",
            region=getattr(region, "name", str(region.id)),
        ),
        event_type=STOPPAGE_EVENT_TYPE,
        # The region's economy really gains a record, so this transitions it.
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        render_params={"region_id": str(region.id)},
        causal_payload={
            "deltas": [],
            "civil_work_stoppage": {
                "region_id": str(region.id),
                "condition_instance_id": str(condition.id),
                "petition_event_id": str(petition_event.id),
                "participation": participation,
                "starts_month": month + 1,
                "ends_month": month + 2,
                "affected_resource_ids": affected,
                "labor_dependence": {
                    concept_id: float(region.economy.labor_dependence[concept_id])
                    for concept_id in affected
                },
            },
        },
    )
    event.causal_links.extend((
        CausalLink(
            event_id=event.id,
            cause_event_id=str(petition_event.id),
            relation=CausalRelation.MOTIVATED_BY,
        ),
        CausalLink(
            event_id=event.id,
            cause_event_id=str(condition.cause_event_id),
            relation=CausalRelation.ENABLED_BY,
        ),
        CausalLink(
            event_id=event.id,
            cause_event_id=str(decision_event_id),
            relation=CausalRelation.TRIGGERED_BY,
        ),
    ))
    record = WorkStoppage(
        started_month=month + 1,
        ends_month=month + 2,
        participation=participation,
        source_event_id=str(petition_event.id),
        decision_event_id=str(decision_event_id),
        start_event_id=event.id,
    )
    region.economy.begin_work_stoppage(record)
    event.causal_payload["deltas"] = [StateDelta(
        event_id=event.id,
        owner_kind="region",
        owner_id=str(region.id),
        aspect="work_stoppage",
        before=None,
        after=json.dumps(record.to_dict(), sort_keys=True),
    ).to_dict()]
    # Only the institution that actually administers this region learns it,
    # through the channel a public stoppage really is. No memory is fabricated,
    # and no other institution is told by omniscience.
    from src.systems.institutional_memory import record_known_fact

    institution_ref = governing_institution_ref(world, region)
    institution = (
        world.institutional_authority.get_institution_for_owner(institution_ref)
        if institution_ref is not None
        else None
    )
    if institution is not None:
        event.causal_payload["civil_work_stoppage"]["addressed_institution_id"] = (
            institution.id
        )
        event.causal_payload["civil_work_stoppage"]["addressed_institution_ref"] = (
            institution_ref.to_dict()
        )
        record_known_fact(
            world,
            event,
            (institution.id,),
            channel=KnowledgeChannel.PUBLIC_FACT,
        )
    receipt = DomainReactionReceipt.create(
        f"civil-stoppage:{region.id}:{condition.id}",
        STOPPAGE_RECEIPT_DOMAIN,
        str(condition.id),
        decision="act",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt
    return event


def expire_work_stoppages(world: Any) -> list[Event]:
    """Retire stoppages whose single cycle is over, as a canonical fact.

    Deterministic: the duration itself ends it. Nothing renews automatically,
    and any base rate that really changed meanwhile simply stays changed.
    """
    from src.classes.environment.region import CityRegion
    from src.i18n import t

    month = int(world.month_stamp)
    events: list[Event] = []
    for region in getattr(getattr(world, "map", None), "regions", {}).values():
        if not isinstance(region, CityRegion):
            continue
        stoppage = getattr(getattr(region, "economy", None), "work_stoppage", None)
        if stoppage is None or not stoppage.has_expired(month):
            continue
        region.economy.clear_work_stoppage()
        event = Event(
            world.month_stamp,
            t(
                "Work resumes in {region} as the stoppage ends.",
                region=getattr(region, "name", str(region.id)),
            ),
            event_type=STOPPAGE_ENDED_EVENT_TYPE,
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
            render_params={"region_id": str(region.id)},
            causal_payload={"deltas": []},
        )
        event.causal_payload["deltas"] = [StateDelta(
            event_id=event.id,
            owner_kind="region",
            owner_id=str(region.id),
            aspect="work_stoppage",
            before=json.dumps(stoppage.to_dict(), sort_keys=True),
            after=None,
        ).to_dict()]
        event.causal_links.append(CausalLink(
            event_id=event.id,
            cause_event_id=str(stoppage.start_event_id),
            relation=CausalRelation.RESOLVES,
        ))
        events.append(event)
    return events


def stoppage_payload(event: Event) -> dict | None:
    """The stoppage this event really is, or nothing.

    A matching event type is not authorship. The fact must be the kind of fact
    a stoppage is -- an actor-decided state transition, not a story -- and it
    must carry a complete, internally coherent record of the interruption.
    """
    if (
        str(getattr(event, "event_type", "")) != STOPPAGE_EVENT_TYPE
        or getattr(event, "fact_kind", None) is not FactKind.STATE_TRANSITION
        or getattr(event, "causal_origin", None) is not CausalOrigin.ACTOR_DECISION
        or bool(getattr(event, "is_story", False))
    ):
        return None
    payload = getattr(event, "causal_payload", None)
    if not isinstance(payload, dict):
        return None
    stoppage = payload.get("civil_work_stoppage")
    if not isinstance(stoppage, dict):
        return None
    reference = stoppage.get("addressed_institution_ref")
    try:
        participation = float(stoppage["participation"])
        starts = int(stoppage["starts_month"])
        ends = int(stoppage["ends_month"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not str(stoppage.get("region_id", ""))
        or not str(stoppage.get("condition_instance_id", ""))
        or not str(stoppage.get("petition_event_id", ""))
        or not str(stoppage.get("addressed_institution_id", ""))
        or not isinstance(reference, dict)
        or not 0.0 < participation <= MAX_STOPPAGE_PARTICIPATION
        or starts < 0
        or ends != starts + 1
    ):
        return None
    return stoppage


def canonical_stoppage_payload(world: Any, event: Event) -> dict | None:
    """The same reading, but of the fact the world actually stores.

    A loose object handed to the dispatcher or to the registry authorizes
    nothing: the stoppage is re-read from the event store, so a forged or
    unknown trigger cannot buy an institutional response. The government
    answers on a later cycle than the stoppage, so no overlay is needed.
    """
    event_id = str(getattr(event, "id", ""))
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_event_by_id", None)
    if not event_id or not callable(getter):
        return None
    resolved = getter(event_id)
    return stoppage_payload(resolved) if resolved is not None else None


def stoppage_response_receipt_id(stoppage_event_id: str, institution_id: str) -> str:
    """One government answer per institution per stoppage, ever."""
    return DomainReactionReceipt.create(
        f"civil-stoppage-response:{institution_id}:{stoppage_event_id}",
        STOPPAGE_RESPONSE_RECEIPT_DOMAIN,
        str(stoppage_event_id),
        decision="maintain",
        affordance_id=None,
    ).id


def stoppage_already_answered(
    world: Any, stoppage_event_id: str, institution_id: str
) -> bool:
    return (
        stoppage_response_receipt_id(stoppage_event_id, institution_id)
        in world.mechanical_language.reaction_receipts
    )


def mark_stoppage_answered(
    world: Any,
    stoppage_event_id: str,
    institution_id: str,
    *,
    decision_event_id: str,
    decision: str,
    affordance_id: str | None,
) -> None:
    """Close this stoppage for this institution, whatever it decided."""
    receipt = DomainReactionReceipt.create(
        f"civil-stoppage-response:{institution_id}:{stoppage_event_id}",
        STOPPAGE_RESPONSE_RECEIPT_DOMAIN,
        str(stoppage_event_id),
        decision=decision if affordance_id else "maintain",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,) if decision_event_id else (),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


def pending_stoppages(world: Any) -> list[tuple[Event, dict]]:
    """Stoppages this world's governments have not answered yet.

    A bounded scan of the response window in the event store. An expired
    stoppage still qualifies: its material consequence is real and answerable,
    and answering it never pretends the interruption is still under way.
    """
    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    stored = (
        getter(month - PETITION_RESPONSE_WINDOW_MONTHS + 1, month)
        if callable(getter)
        else []
    )
    seen: set[str] = set()
    pending: list[tuple[Event, dict]] = []
    for event in stored:
        if event.id in seen:
            continue
        seen.add(event.id)
        payload = stoppage_payload(event)
        if payload is None:
            continue
        institution_id = str(payload.get("addressed_institution_id") or "")
        if not institution_id:
            continue
        # A government answers only what it actually knows.
        if not world.institutional_knowledge.contains(institution_id, event.id):
            continue
        if stoppage_already_answered(world, event.id, institution_id):
            continue
        pending.append((event, payload))
    return pending


def civil_response_is_open(
    world: Any, region: Any, source_event: Event, payload: dict, kind: str
) -> bool:
    """Unanswered, still known, and still within this government's authority.

    The single gate for answering a civil fact. The dispatcher asks it on both
    sides of the interpreter's await and the affordance provider asks it while
    composing, so a direct registry call cannot buy a response to a fact the
    institution never learned. It reads canonical state only and owns none.
    """
    from src.systems.civic_endorsement import endorsement_already_answered
    from src.systems.civil_riot import riot_already_answered

    # One dynasty may govern several cities. Authority over this region says
    # nothing about a fact that happened in another one.
    if str(payload.get("region_id", "")) != str(getattr(region, "id", "")):
        return False
    institution_id = str(payload.get("addressed_institution_id", ""))
    if kind == "petition":
        if already_responded(world, source_event.id):
            return False
    else:
        # A stoppage, a riot and an endorsement are all public facts addressed
        # to the institution that administers the region, and each carries its
        # own response receipt. Answering one never closes another.
        answered = {
            "riot": riot_already_answered,
            "endorsement": endorsement_already_answered,
        }.get(kind, stoppage_already_answered)
        if not institution_id or answered(
            world, source_event.id, institution_id
        ):
            return False
        # A government cannot answer a fact it never learned.
        if not world.institutional_knowledge.contains(institution_id, source_event.id):
            return False
    return response_is_authorized(world, region, payload)


def active_condition_for(world: Any, region: Any, payload: dict):
    """The grievance's condition if it is still live, else nothing.

    A resolved pressure is not replaced by a substitute: the response simply
    proceeds without one, and the history stays visible through the stoppage's
    own evidence rather than being restated as a second truth.
    """
    instance_id = str(payload.get("condition_instance_id", ""))
    if not instance_id:
        return None
    return next(
        (
            item
            for item in world.mechanical_language.get_active_conditions(
                EntityRef("region", str(region.id)), int(world.month_stamp)
            )
            if str(item.id) == instance_id
        ),
        None,
    )


def petition_payload(event: Event) -> dict | None:
    """The petition an event really is, or nothing."""
    if str(getattr(event, "event_type", "")) != PETITION_EVENT_TYPE:
        return None
    if bool(getattr(event, "is_story", False)):
        return None
    payload = getattr(event, "causal_payload", None)
    if not isinstance(payload, dict):
        return None
    petition = payload.get("civil_petition")
    return petition if isinstance(petition, dict) else None


def response_receipt_id(petition_event_id: str) -> str:
    """One government response per petition, ever."""
    return DomainReactionReceipt.create(
        f"civil-petition-response:{petition_event_id}",
        RESPONSE_RECEIPT_DOMAIN,
        str(petition_event_id),
        # Only the derived ID matters here; an acting receipt would require an
        # affordance that this lookup does not have.
        decision="maintain",
        affordance_id=None,
    ).id


def already_responded(world: Any, petition_event_id: str) -> bool:
    return (
        response_receipt_id(petition_event_id)
        in world.mechanical_language.reaction_receipts
    )


def mark_petition_responded(
    world: Any,
    petition_event_id: str,
    *,
    decision_event_id: str,
    decision: str,
    affordance_id: str | None,
) -> None:
    """Close this petition for the government, whatever it decided.

    Maintaining is a real answer, so it closes the petition exactly as an
    action does: a rescan must not offer the same grievance again.
    """
    receipt = DomainReactionReceipt.create(
        f"civil-petition-response:{petition_event_id}",
        RESPONSE_RECEIPT_DOMAIN,
        str(petition_event_id),
        # An acting receipt must name the affordance it acted on.
        decision=decision if affordance_id else "maintain",
        affordance_id=affordance_id,
        decision_event_ids=(decision_event_id,) if decision_event_id else (),
        completed=True,
    )
    world.mechanical_language.reaction_receipts[receipt.id] = receipt


def pending_petitions(
    world: Any, *, current_events: Any = None
) -> list[tuple[Event, dict]]:
    """Persisted petitions still awaiting their government's answer.

    A bounded scan of the response window, plus this step's own events, so a
    petition filed after the government phase in the same month is found on
    the next cycle rather than lost. `EventQuery` has no event-type filter, so
    the window itself is the bound; petitions are filtered in memory.
    """
    month = int(world.month_stamp)
    manager = getattr(world, "event_manager", None)
    getter = getattr(manager, "get_events_between_months", None)
    stored = (
        getter(month - PETITION_RESPONSE_WINDOW_MONTHS + 1, month)
        if callable(getter)
        else []
    )
    seen: set[str] = set()
    pending: list[tuple[Event, dict]] = []
    for event in [*stored, *(current_events or ())]:
        if event.id in seen:
            continue
        seen.add(event.id)
        payload = petition_payload(event)
        if payload is None or already_responded(world, event.id):
            continue
        pending.append((event, payload))
    return pending


def response_is_authorized(world: Any, region: Any, payload: dict) -> bool:
    """The addressed institution must still govern here, and still be able to.

    Authority is asked of the institution, not of whoever holds its office,
    and the controller must be the one that was actually addressed: a region
    that changed hands answers nothing on the old controller's behalf.
    """
    from src.classes.institution import AuthorityScope
    from src.systems.institution_authority import can_actor_act_for

    current_ref = governing_institution_ref(world, region)
    addressed = payload.get("addressed_institution_ref")
    if current_ref is None or not isinstance(addressed, dict):
        return False
    if current_ref.kind != str(addressed.get("kind")) or current_ref.id != str(
        addressed.get("id")
    ):
        return False
    return can_actor_act_for(
        world,
        current_ref,
        current_ref,
        AuthorityScope.URBAN_ADMINISTRATION,
        current_month=int(world.month_stamp),
        require_material_control=True,
        material_target_ref=EntityRef("region", str(region.id)),
    ).allowed


__all__ = [
    "DETRIMENTAL_DIMENSIONS",
    "PETITION_ACTION",
    "PETITION_EVENT_TYPE",
    "STOPPAGE_EVENT_TYPE",
    "active_condition_for",
    "already_petitioned",
    "canonical_stoppage_payload",
    "mark_stoppage_answered",
    "pending_stoppages",
    "stoppage_already_answered",
    "stoppage_payload",
    "stoppage_response_receipt_id",
    "can_file_public_petition",
    "condition_metric",
    "governing_institution_ref",
    "is_detrimental_condition",
    "petition_receipt_id",
    "record_public_petition",
]
