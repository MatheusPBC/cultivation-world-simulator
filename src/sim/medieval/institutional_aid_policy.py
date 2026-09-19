"""Deterministic fallback policy for the institutional food-aid vertical.

No AI, no prose and no randomness: every choice here is a selection among
options the engine already enumerated, and every material effect goes through
the existing aid executors. Each institution performs at most one
state-changing action per invocation, so a chain advances one step per day
instead of waiting for a month and breaching by inaction.
"""

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from .diplomacy_policy import schedule_review
from .events import record_event
from .institutional_aid import (REQUEST_ACTION, _answered, aid_fulfillment_options, aid_remediation_options,
                                aid_request_options, aid_response_options, fulfill_institutional_aid,
                                remediate_institutional_aid, request_institutional_aid, respond_institutional_aid)
from .ai_decider import NO_ACTION, select_option
from .institutional_memory import institutional_view


def _decide(world, option, event_type, content):
    """The current-day decision, recorded immediately before its executor."""
    return record_event(world, event_type, content, fact_kind=FactKind.DECISION, decision=option.decision())


def _event_day(world, event_id):
    event = next((item for item in world.events if item.id == event_id), None)
    return event.day if event is not None else None


def _known_before_today(world, provider, request_event_id):
    day = world.clock.absolute_day
    return any(notice.kind == "request" and notice.request_event_id == request_event_id
               and notice.recipient_ref == provider and notice.learned_day < day
               for notice in world.knowledge.institutional_aid_for_actor(provider))


def _response_candidates(world, actor):
    """The answerable request of the day and the routine's own choice for it."""
    options = aid_response_options(world, actor)
    if not options:
        return (), None, None
    requests = sorted({option.request_event_id for option in options
                       if _known_before_today(world, actor, option.request_event_id)})
    if not requests:
        return (), None, None
    request_event_id = requests[0]
    answerable = tuple(option for option in options if option.request_event_id == request_event_id)
    accept = next((option for option in answerable if option.kind == "accept"), None)
    reject = next((option for option in answerable if option.kind == "reject"), None)
    requester = (accept or reject).requester_ref
    routine = accept if accept is not None and institutional_view(world, actor, requester) >= 0 else reject
    return answerable, routine, request_event_id


def _apply_response(world, actor, chosen):
    decision = _decide(world, chosen, "aid_response_decided", "A instituição respondeu a um pedido de ajuda.")
    respond_institutional_aid(world, actor, chosen.id, decision.id)
    # A direct review may consume a due review without going through the
    # calendar resolver (as the engine does).  Remove that already-resolved
    # agenda item so a valid snapshot cannot retain current work.
    world.agenda.cancel(f"diplomatic-review:{world.clock.absolute_day}")
    if chosen.kind == "accept":
        schedule_review(world)
    return True


def _respond(world, actor):
    """Routine rules only. This is not AI and must never be presented as such."""
    _, routine, _ = _response_candidates(world, actor)
    if routine is None:
        return False
    return _apply_response(world, actor, routine)


async def _respond_with_provider(world, actor):
    """Consult the provider for a response; failure means no response.

    In provider mode a technical failure is deliberately not converted into a
    strategic routine choice.  The caller keeps the routine policy only for
    deterministic/test mode.
    """
    answerable, routine, request_event_id = _response_candidates(world, actor)
    if routine is None:
        return False
    notice = next((item for item in world.knowledge.institutional_aid_for_actor(actor)
                   if item.kind == "request" and item.request_event_id == request_event_id), None)
    # Strictly the actor's own knowledge: who asked, where, how much was asked,
    # by when, and what this institution already remembers about that party.
    situation = {"requester": routine.requester_ref.to_dict(),
                 "settlement_id": notice.requester_settlement_id if notice else None,
                 "requested_food": notice.requested_food if notice else None,
                 "your_reading_of_them": institutional_view(world, actor, routine.requester_ref),
                 "today": world.clock.absolute_day}
    labels = {"accept": "Aceitar o pedido e assumir a obrigação de entregar.",
              "reject": "Recusar o pedido."}
    choices = [{"id": option.id, "label": labels[option.kind]} for option in answerable]
    selected = await select_option(world, actor, situation, choices,
                                   causes=(notice.event_id,) if notice else ())
    if selected in (None, NO_ACTION):
        return False
    chosen = next((option for option in _response_candidates(world, actor)[0] if option.id == selected), None)
    return _apply_response(world, actor, chosen) if chosen is not None else False


async def _fulfill_with_provider(world, actor):
    options = aid_fulfillment_options(world, actor)
    if not options:
        return False
    choices = [{"id": option.id,
                "label": f"Cumprir a obrigação {option.obligation_id} enviando {option.quantity} {option.resource_id}."}
               for option in options]
    causes = tuple(sorted({world.relations.obligations[option.obligation_id].last_event_id
                           for option in options}))
    selected = await select_option(
        world, actor,
        {"obligations": [option.obligation_id for option in options],
         "today": world.clock.absolute_day},
        choices, causes=causes)
    if selected in (None, NO_ACTION):
        return False
    option = next((item for item in aid_fulfillment_options(world, actor) if item.id == selected), None)
    if option is None:
        return False
    decision = _decide(world, option, "aid_fulfillment_decided", "A instituição cumpriu a ajuda acordada.")
    try:
        fulfill_institutional_aid(world, actor, option.id, decision.id)
    except ValueError:
        # Same technical-failure boundary as the routine path: a route the
        # provider chose in good faith may have closed since it was offered.
        return False
    return True


def _fulfill(world, actor):
    day = world.clock.absolute_day
    for option in aid_fulfillment_options(world, actor):
        obligation = world.relations.obligations[option.obligation_id]
        accepted_day = _event_day(world, obligation.last_event_id)
        if accepted_day is None or accepted_day >= day:
            continue
        decision = _decide(world, option, "aid_fulfillment_decided", "A instituição cumpriu a ajuda acordada.")
        try:
            fulfill_institutional_aid(world, actor, option.id, decision.id)
        except ValueError:
            # A route the actor still believes valid may have closed since (a
            # restriction, a lost checkpoint reading). The obligation stays
            # active for a later attempt or remediation; this is a technical
            # failure, never a strategic choice to withhold the shipment.
            continue
        return True
    return False


async def _remediate_with_provider(world, actor):
    options = aid_remediation_options(world, actor)
    if not options:
        return False
    choices = [{"id": option.id,
                "label": f"Reparar a obrigação {option.obligation_id} enviando {option.quantity} {option.resource_id}."}
               for option in options]
    selected = await select_option(
        world, actor,
        {"breaches": [option.breach_event_id for option in options],
         "today": world.clock.absolute_day},
        choices, causes=tuple(sorted({option.breach_event_id for option in options})))
    if selected in (None, NO_ACTION):
        return False
    option = next((item for item in aid_remediation_options(world, actor) if item.id == selected), None)
    if option is None:
        return False
    decision = _decide(world, option, "aid_remediation_decided", "A instituição reparou uma ajuda descumprida.")
    remediate_institutional_aid(world, actor, option.id, decision.id)
    return True


def _remediate(world, actor):
    day = world.clock.absolute_day
    for option in aid_remediation_options(world, actor):
        breach_day = _event_day(world, option.breach_event_id)
        if breach_day is None or breach_day >= day:
            continue
        decision = _decide(world, option, "aid_remediation_decided", "A instituição reparou uma ajuda descumprida.")
        remediate_institutional_aid(world, actor, option.id, decision.id)
        return True
    return False


def _pressured_settlements(world, actor):
    """Own administered settlements whose current report shows real need.

    A food objective may add useful context, but it is not a prerequisite for
    asking for help.  The material trigger is the institution's own dated
    settlement report; otherwise a polity could watch its population starve
    simply because no strategic objective happened to mention that settlement.
    """
    day = world.clock.absolute_day
    settlements = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        report = world.knowledge.settlement_report(actor, settlement.id)
        if (settlement.administrator_id != actor.id or report is None
                or report.observed_day != day or report.missing_food <= 0):
            continue
        settlements.append(settlement.id)
    return tuple(dict.fromkeys(settlements))


def _own_open_chain(world, requester, settlement_id):
    """One chain per settlement: any unanswered request or running aid blocks it.

    Only the requester's own request facts and its own accepted commitments are
    inspected, whoever the provider is. No foreign holding is read.
    """
    events = {item.id: item for item in world.events}
    for event in world.events:
        if event.event_type != "institutional_aid_requested":
            continue
        decision = next((events[link.cause_event_id] for link in event.causal_links
                         if link.cause_event_id in events
                         and events[link.cause_event_id].fact_kind == FactKind.DECISION
                         and (events[link.cause_event_id].decision or {}).get("action") == REQUEST_ACTION), None)
        if (decision is None or (decision.decision or {}).get("actor_ref") != requester.to_dict()
                or not any(delta.owner_kind == "aid_request" and delta.aspect == "requester_settlement_id"
                           and delta.after == settlement_id for delta in event.deltas)):
            continue
        if not _answered(world, event.id):
            return True
    destination_id = world.economy.needs[settlement_id].stock_id
    for obligation in world.relations.obligations.values():
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind != "institutional_aid"
                or obligation.status != "active" or proposal.proposer_ref != requester):
            continue
        if proposal.clauses[obligation.clause_index].destination_stock_id == destination_id:
            return True
    return False


def _request(world, actor):
    pressured = _pressured_settlements(world, actor)
    if not pressured:
        return False
    settlement_id = pressured[0]
    if _own_open_chain(world, actor, settlement_id):
        return False
    candidates = []
    for option in aid_request_options(world, actor):
        if option.requester_settlement_id != settlement_id:
            continue
        view = institutional_view(world, actor, option.provider_ref)
        if view < 0:
            continue
        candidates.append((-view, option.id, option))
    if not candidates:
        return False
    option = sorted(candidates, key=lambda item: item[:2])[0][2]
    decision = _decide(world, option, "aid_request_decided", "A instituição pediu ajuda alimentar.")
    request_institutional_aid(world, actor, option.id, decision.id)
    schedule_review(world)
    return True


async def _request_with_provider(world, actor):
    pressured = _pressured_settlements(world, actor)
    if not pressured:
        return False
    options = tuple(option for option in aid_request_options(world, actor)
                    if option.requester_settlement_id in pressured
                    and not _own_open_chain(world, actor, option.requester_settlement_id))
    if not options:
        return False
    choices = [{"id": option.id,
                "label": f"Pedir ajuda alimentar para {option.requester_settlement_id} a {option.provider_ref.id}."}
               for option in options]
    report_causes = tuple(sorted({option.report_id for option in options}))
    report_events = tuple(sorted({report.event_id for report in world.knowledge.settlements_for_actor(actor)
                                  if report.id in report_causes}))
    selected = await select_option(
        world, actor,
        {"settlements_with_current_need": list(pressured),
         "today": world.clock.absolute_day},
        choices, causes=report_events)
    if selected in (None, NO_ACTION):
        return False
    option = next((item for item in aid_request_options(world, actor) if item.id == selected), None)
    if option is None or option.requester_settlement_id not in pressured or _own_open_chain(
            world, actor, option.requester_settlement_id):
        return False
    decision = _decide(world, option, "aid_request_decided", "A instituição pediu ajuda alimentar.")
    request_institutional_aid(world, actor, option.id, decision.id)
    schedule_review(world)
    return True


def review_institutional_aid(world, allow_requests=False):
    """One bounded institutional step per actor, by routine rules alone."""
    for identity in sorted(world.society.polities):
        actor = EntityRef("polity", identity)
        if _respond(world, actor) or _fulfill(world, actor) or _remediate(world, actor):
            continue
        if allow_requests:
            _request(world, actor)


async def review_institutional_aid_with_provider(world, allow_requests=False, excluded_requesters=()):
    """Run one aid action per polity using either routine rules or a provider.

    ``ai_enabled`` is the explicit boundary: provider mode never falls back to
    a routine material action after unavailable/error/invalid/NO_ACTION.
    ``excluded_requesters`` only narrows the *request* branch: an actor whose
    request decision was already deferred to a concurrent menu this same
    boundary must not be asked to request again, but it still independently
    answers, fulfils or remediates like any other institution.
    """
    for identity in sorted(world.society.polities):
        actor = EntityRef("polity", identity)
        if world.config.ai_enabled:
            if (await _respond_with_provider(world, actor)
                    or await _fulfill_with_provider(world, actor)
                    or await _remediate_with_provider(world, actor)):
                continue
            if allow_requests and actor not in excluded_requesters:
                await _request_with_provider(world, actor)
        elif (_respond(world, actor) or _fulfill(world, actor) or _remediate(world, actor)):
            continue
        elif allow_requests and actor not in excluded_requesters:
            _request(world, actor)
