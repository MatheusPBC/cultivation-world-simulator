"""A small, explicit institutional food-aid commitment vertical.

Affordances are deliberately transient.  The requester's affordance only says
which institution may be asked; the provider's stock, quantity and route are
recomposed privately by the engine at request/response time.
"""

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Literal

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.diplomacy import (
    DiplomaticProposal,
    Obligation,
    ResourceTransferClause,
    aid_request_intent,
)
from src.classes.governance.knowledge import institutional_aid_notice_id
from src.classes.governance.models import InstitutionalAidNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .demand import reserve_quantity
from .diplomacy import disclose
from .economy import _causes, _delta
from .events import record_event
from .institutional_memory import (apply_memory_creation, apply_reinforcement, memories_of,
                                   memory_creation_deltas, reinforcement_deltas)
from .logistics import check_freight, open_order
from .routing import fiscal_route_options, validate_fiscal_route_option


REQUEST_ACTION = "request_institutional_aid"
RESPONSE_ACTION = "respond_institutional_aid"
FULFILL_ACTION = "fulfill_institutional_aid"
REMEDIATE_ACTION = "remediate_institutional_aid"
REQUEST_WINDOW = 30
AID_DUE_DAYS = 31


@dataclass(frozen=True)
class AidRequestOption:
    id: Identity
    actor_ref: EntityRef
    provider_ref: EntityRef
    requester_settlement_id: Identity
    report_id: Identity

    def decision(self):
        return {"action": REQUEST_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class AidResponseOption:
    id: Identity
    actor_ref: EntityRef
    request_event_id: Identity
    requester_ref: EntityRef
    kind: Literal["accept", "reject"]
    source_stock_id: Identity | None = None
    destination_stock_id: Identity | None = None
    resource_id: Identity = "food"
    quantity: int | None = None
    route_ids: tuple[Identity, ...] = ()
    route_option_id: Identity | None = None

    def decision(self):
        return {"action": RESPONSE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class AidFulfillmentOption:
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity
    source_stock_id: Identity
    destination_stock_id: Identity
    resource_id: Identity
    quantity: int
    route_ids: tuple[Identity, ...]
    route_option_id: Identity

    def decision(self):
        return {"action": FULFILL_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class AidRemediationOption:
    id: Identity
    actor_ref: EntityRef
    obligation_id: Identity
    source_stock_id: Identity
    destination_stock_id: Identity
    resource_id: Identity
    quantity: int
    route_ids: tuple[Identity, ...]
    breach_event_id: Identity
    route_option_id: Identity

    def decision(self):
        return {"action": REMEDIATE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    return world.event_index().get(event_id)


def _actor(value):
    if isinstance(value, EntityRef):
        return value
    return None


def _actor_key(actor):
    return json.dumps(actor.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION
            or event.day != world.clock.absolute_day or event.decision is None
            or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("institutional aid requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("institutional aid decision has an invalid actor") from exc
    return event, actor


def _material_authorship(world, decision, actor, option):
    """Keep routine aid deterministic while preserving a provider's choice."""
    if decision.causal_origin is not CausalOrigin.ACTOR_DECISION:
        return CausalOrigin.DETERMINISTIC, None
    return CausalOrigin.ACTOR_DECISION, {
        "decision_event_id": decision.id,
        "actor_ref": actor.to_dict(),
        "selected_affordance_id": option.id,
    }


def _own_reports(world, actor):
    day = world.clock.absolute_day
    return tuple(report for report in world.knowledge.settlements_for_actor(actor)
                 if report.recipient_ref == actor and report.publisher_ref == actor
                 and report.observed_day == day
                 and world.society.settlements.get(report.settlement_id) is not None
                 and world.society.settlements[report.settlement_id].administrator_id == actor.id)


def _source_candidates(world, provider):
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        if settlement.administrator_id != provider.id:
            continue
        stock_id = world.economy.needs.get(settlement.id).stock_id if settlement.id in world.economy.needs else None
        stock = world.economy.stocks.get(stock_id) if stock_id else None
        if stock is None or stock.owner_ref != provider:
            continue
        surplus = stock.goods.get("food", 0) - reserve_quantity(world, stock.id, "food")
        if surplus > 0:
            yield settlement, stock, surplus


def _provider_terms(world, provider, notice):
    """Recompose terms from the provider's own holdings and dated readings.

    The requester's settlement report is never read here: the only thing that
    travelled is the need stated in the direct notice.
    """
    settlement_id = notice.requester_settlement_id
    if settlement_id not in world.economy.needs or notice.requested_food <= 0:
        return None
    destination_id = world.economy.needs[settlement_id].stock_id
    for settlement, source, surplus in _source_candidates(world, provider):
        routes = fiscal_route_options(world, provider, source.id, destination_id,
                                      "food", min(notice.requested_food, surplus))
        if not routes:
            continue
        route = routes[0]
        if route.quantity > 0:
            return source.id, destination_id, route.quantity, tuple(route.route_ids), notice, route
    return None


def _answered_request_ids(world):
    return {link.cause_event_id
            for event_type in ("institutional_aid_accepted", "institutional_aid_rejected")
            for event in world.events_of_type(event_type)
            for link in event.causal_links}


def _answered(world, request_event_id):
    return request_event_id in _answered_request_ids(world)


def _request_providers_with_pending_aid(world):
    answered = _answered_request_ids(world)
    events = world.event_index()
    pending = set()
    for event in world.events_of_type("institutional_aid_requested"):
        if event.id in answered or event.fact_kind != FactKind.STATE_TRANSITION:
            continue
        # Only the receipt written by request_institutional_aid is canonical.
        # A matching event name or a provider_ref delta alone is insufficient:
        # unrelated/partial facts must not hide a real option from the actor.
        decision = next((events.get(link.cause_event_id) for link in event.causal_links
                         if events.get(link.cause_event_id) is not None
                         and events[link.cause_event_id].fact_kind == FactKind.DECISION), None)
        if (decision is None or decision.day > event.day or decision.decision is None
                or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}
                or decision.decision.get("action") != REQUEST_ACTION):
            continue
        try:
            requester = EntityRef.from_dict(decision.decision["actor_ref"])
        except (KeyError, TypeError, ValueError):
            continue
        if requester.kind != "polity":
            continue

        owner_id = f"aid-request:{decision.id}"
        receipt = {delta.aspect: delta for delta in event.deltas
                   if delta.owner_kind == "aid_request" and delta.owner_id == owner_id}
        expected_aspects = {"status", "option_id", "requester_settlement_id", "report_id",
                            "requested_food", "provider_ref"}
        if (len(receipt) != len(event.deltas) or set(receipt) != expected_aspects
                or receipt["status"].before != "None"
                or receipt["status"].after != "requested"
                or receipt["option_id"].after != decision.decision.get("selected_affordance_id")):
            continue
        try:
            provider_data = json.loads(receipt["provider_ref"].after)
            provider = EntityRef.from_dict(provider_data)
            requested_food = int(receipt["requested_food"].after)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if provider.kind != "polity" or provider == requester or requested_food <= 0:
            continue

        report_id = receipt["report_id"].after
        settlement_id = receipt["requester_settlement_id"].after
        report_causes = [events.get(link.cause_event_id) for link in event.causal_links
                         if link.cause_event_id != decision.id]
        if len(report_causes) != 1 or report_causes[0] is None:
            continue
        report_event = report_causes[0]
        if (report_event.event_type != "settlement_observed"
                or not any(delta.owner_kind == "settlement_report" and delta.owner_id == report_id
                           and delta.aspect == "observation" for delta in report_event.deltas)):
            continue
        expected_option_id = (
            f"institutional-aid-request:{requester.kind}:{requester.id}:{provider.id}:"
            f"{report_id}:{report_event.id}"
        )
        if (receipt["option_id"].after != expected_option_id
                or _actor_key(provider) != receipt["provider_ref"].after
                or not settlement_id):
            continue
        pending.add(_actor_key(provider))
    return pending


def aid_request_options(world, requester):
    requester = _actor(requester)
    if (requester is None or not can_actor_act_for(world, requester, requester, "diplomacy")
            or not can_actor_act_for(world, requester, requester, "supply")):
        return ()
    reports = [report for report in _own_reports(world, requester) if report.missing_food > 0]
    options = []
    pending_provider_keys = _request_providers_with_pending_aid(world)
    for report in reports:
        for provider_id in sorted(world.society.polities):
            provider = EntityRef("polity", provider_id)
            if provider == requester:
                continue
            option_id = f"institutional-aid-request:{requester.kind}:{requester.id}:{provider.id}:{report.id}:{report.event_id}"
            option = AidRequestOption(option_id, requester, provider, report.settlement_id, report.id)
            if _actor_key(provider) in pending_provider_keys:
                continue
            options.append(option)
    return tuple(options)


def request_institutional_aid(world, requester, option_id, decision_event_id):
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, REQUEST_ACTION)
    if actor != _actor(requester):
        raise ValueError("institutional aid request has the wrong actor")
    option = next((item for item in aid_request_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("institutional aid request option is stale or unknown")
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "supply")
    event = record_event(candidate, "institutional_aid_requested",
                         "Uma instituição solicitou ajuda alimentar.", fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("aid_request", f"aid-request:{decision.id}", "status", None, "requested"),
                                 _delta("aid_request", f"aid-request:{decision.id}", "option_id", None, option.id),
                                 _delta("aid_request", f"aid-request:{decision.id}", "requester_settlement_id", None,
                                        option.requester_settlement_id),
                                 _delta("aid_request", f"aid-request:{decision.id}", "report_id", None, option.report_id),
                                 _delta("aid_request", f"aid-request:{decision.id}", "requested_food", None,
                                        candidate.knowledge.settlement_report(actor, option.requester_settlement_id).missing_food),
                                 _delta("aid_request", f"aid-request:{decision.id}", "provider_ref", None,
                                        _actor_key(option.provider_ref))),
                         cause_ids=_causes(decision.id, candidate.knowledge.settlement_report(actor, option.requester_settlement_id).event_id))
    notice = InstitutionalAidNotice(
        id=institutional_aid_notice_id(event.id, option.provider_ref), request_event_id=event.id,
        recipient_ref=option.provider_ref, requester_ref=actor,
        requester_settlement_id=option.requester_settlement_id, report_id=option.report_id,
        requested_food=candidate.knowledge.settlement_report(actor, option.requester_settlement_id).missing_food,
        event_id=event.id, learned_day=event.day, kind="request",
    )
    candidate.knowledge.institutional_aid_notices[notice.id] = notice
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def _pending_requests(world, provider):
    events = world.event_index()
    answered = _answered_request_ids(world)
    for notice in world.knowledge.institutional_aid_for_actor(provider):
        if notice.kind != "request":
            continue
        try:
            world.knowledge._validate_institutional_aid_notice(world, events, notice)
        except ValueError:
            continue
        request = events.get(notice.request_event_id)
        if request is None or request.id in answered:
            continue
        decision = next((events[link.cause_event_id] for link in request.causal_links
                         if link.cause_event_id in events and events[link.cause_event_id].fact_kind == FactKind.DECISION), None)
        if decision is None or decision.day + REQUEST_WINDOW < world.clock.absolute_day:
            continue
        option_id = next((delta.after for delta in request.deltas
                          if delta.owner_kind == "aid_request" and delta.owner_id == f"aid-request:{decision.id}"
                          and delta.aspect == "option_id"), None)
        if option_id:
            yield request, decision, AidRequestOption(option_id, notice.requester_ref, provider,
                                                       notice.requester_settlement_id, notice.report_id), notice


def _response_notice(candidate, request, request_option, event, status, requested_food):
    notice = InstitutionalAidNotice(
        id=institutional_aid_notice_id(event.id, request_option.actor_ref), request_event_id=request.id,
        recipient_ref=request_option.actor_ref, requester_ref=request_option.actor_ref,
        requester_settlement_id=request_option.requester_settlement_id, report_id=request_option.report_id,
        requested_food=requested_food,
        event_id=event.id, learned_day=event.day, kind="response", response_status=status,
    )
    candidate.knowledge.institutional_aid_notices[notice.id] = notice


def aid_response_options(world, provider):
    provider = _actor(provider)
    if (provider is None or not can_actor_act_for(world, provider, provider, "diplomacy")
            or not can_actor_act_for(world, provider, provider, "supply")):
        return ()
    result = []
    for request, decision, request_option, notice in _pending_requests(world, provider):
        terms = _provider_terms(world, provider, notice)
        common = f"institutional-aid-response:{request.id}:{provider.id}"
        result.append(AidResponseOption(common + ":reject", provider, request.id,
                                        request_option.actor_ref, "reject"))
        if terms is not None:
            source, destination, quantity, routes, _, route = terms
            result.append(AidResponseOption(common + ":accept", provider, request.id,
                                            request_option.actor_ref, "accept", source, destination,
                                            "food", quantity, routes, route.id))
    return tuple(result)


def respond_institutional_aid(world, provider, option_id, decision_event_id):
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, RESPONSE_ACTION)
    if actor != _actor(provider):
        raise ValueError("institutional aid response has the wrong actor")
    option = next((item for item in aid_response_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("institutional aid response option is stale or unknown")
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "supply")
    request = _event(candidate, option.request_event_id)
    if request is None:
        raise ValueError("institutional aid request is missing")
    if option.kind == "reject":
        request_option, request_notice = next((item, pending) for request_item, _, item, pending
                                              in _pending_requests(candidate, actor)
                                              if request_item.id == request.id)
        event = record_event(candidate, "institutional_aid_rejected", "Ajuda institucional recusada.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("aid_request", f"aid-request:{request.id}", "status", "requested", "rejected"),
                                     *memory_creation_deltas(candidate, (request_option.actor_ref,))),
                             cause_ids=(decision.id, request.id))
        _response_notice(candidate, request, request_option, event, "rejected", request_notice.requested_food)
        apply_memory_creation(candidate, (request_option.actor_ref,), event)
        candidate.knowledge.validate(candidate)
        candidate.relations.validate(candidate)
        world.__dict__.update(candidate.__dict__)
        return event
    request_option, request_notice = next((item, pending) for request_item, _, item, pending
                                          in _pending_requests(candidate, actor)
                                          if request_item.id == request.id)
    terms = _provider_terms(candidate, actor, request_notice)
    if (terms is None or terms[:4] != (option.source_stock_id, option.destination_stock_id,
                                       option.quantity, option.route_ids)
            or terms[5].id != option.route_option_id):
        raise ValueError("institutional aid response is stale")
    source, destination, quantity, routes, _, route = terms
    validate_fiscal_route_option(candidate, route.id, actor, source, destination, "food", quantity)
    due = request.day + AID_DUE_DAYS
    clause = ResourceTransferClause(debtor_ref=actor, creditor_ref=option.requester_ref, due_day=due,
                                    source_stock_id=source, destination_stock_id=destination,
                                    resource_id="food", quantity=quantity, route_ids=routes)
    request_decision = next((item for item in candidate.events
                             if item.fact_kind == FactKind.DECISION
                             and item.id in {link.cause_event_id for link in request.causal_links}), None)
    if request_decision is None:
        raise ValueError("institutional aid request decision is missing")
    proposal = DiplomaticProposal(id=f"proposal:{request_decision.id}",
                                  proposer_ref=option.requester_ref, counterparty_ref=actor,
                                  clauses=(clause,), offered_day=request.day, expires_day=request.day + REQUEST_WINDOW,
                                  decision_event_id=request_decision.id,
                                  last_event_id="pending", proposal_kind="institutional_aid",
                                  request_affordance_id=request_option.id, status="accepted")
    event = record_event(candidate, "institutional_aid_accepted", "Ajuda institucional aceita.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("aid_request", f"aid-request:{request.id}", "status", "requested", "accepted"),
                                 _delta("diplomacy", proposal.id, "status", None, "accepted"),
                                 _delta("obligation", f"{proposal.id}:term:0", "status", None, "active")),
                         cause_ids=(decision.id, request.id))
    proposal = proposal.model_copy(update={"last_event_id": event.id})
    candidate.relations.proposals[proposal.id] = proposal
    obligation = Obligation(id=f"{proposal.id}:term:0", proposal_id=proposal.id, clause_index=0, last_event_id=event.id)
    candidate.relations.obligations[obligation.id] = obligation
    candidate.agenda.schedule(ScheduledSituation(obligation.id, "diplomacy", due + 1))
    from .diplomacy import disclose
    disclose(candidate, proposal, event)
    _response_notice(candidate, request, request_option, event, "accepted", request_notice.requested_food)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return proposal


def aid_fulfillment_options(world, provider):
    provider = _actor(provider)
    if provider is None or not can_actor_act_for(world, provider, provider, "supply"):
        return ()
    options = []
    for obligation in sorted(world.relations.obligations.values(), key=lambda item: item.id):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind != "institutional_aid" or obligation.status != "active"
                or proposal.clauses[obligation.clause_index].debtor_ref != provider):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if clause.kind != "resource_transfer":
            continue
        source = world.economy.stocks.get(clause.source_stock_id)
        if source is None or source.goods.get(clause.resource_id, 0) - reserve_quantity(world, source.id, clause.resource_id) < clause.quantity:
            continue
        route_options = fiscal_route_options(world, provider, clause.source_stock_id,
                                             clause.destination_stock_id, clause.resource_id, clause.quantity)
        route = next((item for item in route_options if item.route_ids == clause.route_ids), None)
        if route is None:
            continue
        options.append(AidFulfillmentOption(
            id=f"institutional-aid-fulfill:{obligation.id}:{obligation.last_event_id}:{source.last_event_ids.get(clause.resource_id)}",
            actor_ref=provider, obligation_id=obligation.id, source_stock_id=clause.source_stock_id,
            destination_stock_id=clause.destination_stock_id, resource_id=clause.resource_id,
            quantity=clause.quantity, route_ids=clause.route_ids, route_option_id=route.id))
    return tuple(options)


def fulfill_institutional_aid(world, provider, option_id, decision_event_id):
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, FULFILL_ACTION)
    if actor != _actor(provider):
        raise ValueError("institutional aid fulfillment has the wrong actor")
    option = next((item for item in aid_fulfillment_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("institutional aid fulfillment option is stale or unknown")
    require_authority(candidate, actor, "supply")
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    validate_fiscal_route_option(candidate, option.route_option_id, actor, option.source_stock_id,
                                 option.destination_stock_id, option.resource_id, option.quantity)
    causal_origin, causal_payload = _material_authorship(candidate, decision, actor, option)
    opened = open_order(candidate, option.source_stock_id, option.destination_stock_id, option.resource_id,
                        option.quantity, option.route_ids, decision_ids=(decision.id,),
                        cause_ids=(obligation.last_event_id, proposal.decision_event_id),
                        causal_origin=causal_origin, causal_payload=causal_payload)
    receipt = record_event(candidate, "institutional_aid_fulfilled", "Remessa de ajuda institucional preparada.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           causal_origin=causal_origin, causal_payload=causal_payload,
                           deltas=(_delta("obligation", obligation.id, "status", "active", "fulfilled"),
                                   _delta("obligation", obligation.id, "material_event_id", None, opened.last_event_id),
                                   *memory_creation_deltas(candidate, (proposal.proposer_ref,
                                                                        proposal.counterparty_ref))),
                           cause_ids=(decision.id, obligation.last_event_id, opened.last_event_id))
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={"status": "fulfilled", "material_event_id": opened.last_event_id, "last_event_id": receipt.id})
    candidate.agenda.cancel(obligation.id)
    apply_memory_creation(candidate, (proposal.proposer_ref, proposal.counterparty_ref), receipt)
    disclose(candidate, proposal, receipt)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return opened


def _remediation_terms(world, provider, clause):
    """Find fresh source and route facts for the clause's original quantity."""
    destination = world.economy.stocks.get(clause.destination_stock_id)
    if (destination is None or destination.owner_ref != clause.creditor_ref
            or clause.resource_id != "food"):
        return None
    for settlement, source, surplus in _source_candidates(world, provider):
        if surplus < clause.quantity:
            continue
        routes = fiscal_route_options(world, provider, source.id, destination.id,
                                      clause.resource_id, clause.quantity)
        if routes:
            route = routes[0]
            return source.id, destination.id, clause.quantity, tuple(route.route_ids), route
    return None


def _has_breach_notice(world, proposal_id, provider, breach_event_id):
    return any(notice.proposal_id == proposal_id and notice.recipient_ref == provider
               and notice.event_id == breach_event_id for notice in world.knowledge.notices.values())


def aid_remediation_options(world, provider):
    provider = _actor(provider)
    if (provider is None or not can_actor_act_for(world, provider, provider, "diplomacy")
            or not can_actor_act_for(world, provider, provider, "supply")):
        return ()
    options = []
    for obligation in sorted(world.relations.obligations.values(), key=lambda item: item.id):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind != "institutional_aid"
                or obligation.status != "breached" or obligation.breach_event_id is None):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if (clause.kind != "resource_transfer" or clause.debtor_ref != provider
                or not _has_breach_notice(world, proposal.id, provider, obligation.breach_event_id)):
            continue
        terms = _remediation_terms(world, provider, clause)
        if terms is None:
            continue
        source, destination, quantity, routes, route_option = terms
        try:
            check_freight(world, source, destination, clause.resource_id, quantity, routes)
            if any(world.map.get_route_operational_capacity(route_id) < world.economy.resources[clause.resource_id].bulk
                   for route_id in routes):
                continue
        except (KeyError, ValueError):
            continue
        source_stamp = world.economy.stocks[source].last_event_ids.get(clause.resource_id)
        option_id = (f"institutional-aid-remediate:{obligation.id}:{obligation.breach_event_id}:"
                     f"{source}:{source_stamp}:{route_option.id}")
        options.append(AidRemediationOption(option_id, provider, obligation.id, source, destination,
                                            clause.resource_id, quantity, routes, obligation.breach_event_id,
                                            route_option.id))
    return tuple(options)


def remediate_institutional_aid(world, provider, option_id, decision_event_id):
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, REMEDIATE_ACTION)
    if actor != _actor(provider):
        raise ValueError("institutional aid remediation has the wrong actor")
    option = next((item for item in aid_remediation_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("institutional aid remediation option is stale or unknown")
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "supply")
    obligation = candidate.relations.obligations.get(option.obligation_id)
    if obligation is None or obligation.status != "breached" or obligation.breach_event_id != option.breach_event_id:
        raise ValueError("institutional aid remediation requires the current breach")
    proposal = candidate.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    terms = _remediation_terms(candidate, actor, clause)
    if (terms is None or terms[:4] != (option.source_stock_id, option.destination_stock_id,
                                       option.quantity, option.route_ids)
            or terms[4].id != option.route_option_id):
        raise ValueError("institutional aid remediation is stale")
    validate_fiscal_route_option(candidate, option.route_option_id, actor, option.source_stock_id,
                                 option.destination_stock_id, option.resource_id, option.quantity)
    try:
        check_freight(candidate, option.source_stock_id, option.destination_stock_id, option.resource_id,
                      option.quantity, option.route_ids)
        if any(candidate.map.get_route_operational_capacity(route_id) < candidate.economy.resources[option.resource_id].bulk
               for route_id in option.route_ids):
            raise ValueError("institutional aid remediation route is stale")
    except (KeyError, ValueError) as exc:
        raise ValueError("institutional aid remediation route is stale") from exc
    if not _has_breach_notice(candidate, proposal.id, actor, obligation.breach_event_id):
        raise ValueError("institutional aid remediation requires the private breach notice")
    causal_origin, causal_payload = _material_authorship(candidate, decision, actor, option)
    opened = open_order(candidate, option.source_stock_id, option.destination_stock_id, option.resource_id,
                        option.quantity, option.route_ids, decision_ids=(decision.id,),
                        cause_ids=(obligation.breach_event_id,), causal_origin=causal_origin,
                        causal_payload=causal_payload)
    # The same receipt declares what each party will remember about the repair
    # and reinforces the breach they already remember; the breach itself stays.
    parties = (proposal.proposer_ref, proposal.counterparty_ref)
    reinforced = tuple(memory for memory in (memories_of(candidate, party, obligation.breach_event_id)
                                             for party in parties) if memory is not None)
    receipt = record_event(candidate, "institutional_aid_remediated",
                           "Remessa de ajuda institucional repara a obrigação descumprida.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           causal_origin=causal_origin, causal_payload=causal_payload,
                           deltas=(_delta("obligation", obligation.id, "status", "breached", "remediated"),
                                   _delta("obligation", obligation.id, "remediation_material_event_id", None,
                                          opened.last_event_id),
                                   *memory_creation_deltas(candidate, parties),
                                   *reinforcement_deltas(candidate, reinforced)),
                           cause_ids=(decision.id, obligation.breach_event_id, opened.last_event_id))
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={"status": "remediated", "material_event_id": None,
                "remediation_material_event_id": opened.last_event_id, "last_event_id": receipt.id})
    apply_memory_creation(candidate, parties, receipt)
    apply_reinforcement(candidate, reinforced, receipt)
    disclose(candidate, proposal, receipt)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return opened


__all__ = ["AidFulfillmentOption", "AidRemediationOption", "AidRequestOption", "AidResponseOption",
           "aid_fulfillment_options", "aid_request_options", "aid_response_options",
           "aid_remediation_options", "fulfill_institutional_aid", "remediate_institutional_aid",
           "request_institutional_aid", "respond_institutional_aid"]
