"""Reciprocal supply commitments negotiated through the canonical proposal flow.

A settlement whose own food objective is blocked may offer a counterpart a
concession it actually owns: deliver food to me, and I deliver a resource of
mine afterwards. Every option here is recomposed from the requester's own
settlement report, its own stocks and accounts, and its own dated route
knowledge; the counterparty's holdings are never read. Settlement and stock
identities are public addresses, their contents are not.

Accepting binds intentions only. Each delivery is a separate current decision
executed by the canonical freight owner, and an unmet term breaches with the
same grounded evidence as institutional aid.
"""

from copy import deepcopy
from dataclasses import dataclass
import math

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.diplomacy import ResourceTransferClause
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .demand import reserve_quantity
from .diplomacy import disclose, offer_proposal, respond_proposal
from .economy import _causes, _delta
from .events import record_event
from .institutional_memory import (apply_memory_creation, apply_reinforcement,
                                    institutional_view, memories_of,
                                    memory_creation_deltas, reinforcement_deltas)
from .logistics import check_freight, open_order
from .routing import fiscal_route_options, known_supply_path, validate_fiscal_route_option


OFFER_ACTION = "offer_reciprocal_supply"
RESPONSE_ACTION = "respond_reciprocal_supply"
FULFILL_ACTION = "fulfill_resource_transfer"
REMEDIATE_ACTION = "remediate_resource_transfer"
OFFER_WINDOW = 10
FOOD_DUE_DAYS = 20
PLEDGE_DUE_DAYS = 40


@dataclass(frozen=True)
class ReciprocalSupplyOption:
    """Transient engine option; a decider only selects this ID."""
    id: Identity
    actor_ref: EntityRef
    counterparty_ref: EntityRef
    settlement_id: Identity
    food_source_stock_id: Identity
    food_destination_stock_id: Identity
    food_quantity: int
    food_route_ids: tuple[Identity, ...]
    pledge_source_stock_id: Identity
    pledge_destination_stock_id: Identity
    pledge_resource_id: Identity
    pledge_quantity: int
    pledge_route_ids: tuple[Identity, ...]
    expires_day: int
    food_due_day: int
    pledge_due_day: int
    parent_id: Identity | None = None

    def clauses(self):
        """Delivery first, concession afterwards and dependent on it."""
        return (ResourceTransferClause(debtor_ref=self.counterparty_ref, creditor_ref=self.actor_ref,
                                       due_day=self.food_due_day, source_stock_id=self.food_source_stock_id,
                                       destination_stock_id=self.food_destination_stock_id,
                                       resource_id="food", quantity=self.food_quantity,
                                       route_ids=self.food_route_ids),
                ResourceTransferClause(debtor_ref=self.actor_ref, creditor_ref=self.counterparty_ref,
                                       due_day=self.pledge_due_day, depends_on=(0,),
                                       source_stock_id=self.pledge_source_stock_id,
                                       destination_stock_id=self.pledge_destination_stock_id,
                                       resource_id=self.pledge_resource_id, quantity=self.pledge_quantity,
                                       route_ids=self.pledge_route_ids))

    def decision(self):
        return {"action": OFFER_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ReciprocalResponseOption:
    id: Identity
    actor_ref: EntityRef
    proposal_id: Identity
    kind: str
    source_stock_id: Identity | None = None
    route_ids: tuple[Identity, ...] = ()

    def decision(self):
        return {"action": RESPONSE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ResourceTransferFulfillmentOption:
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
class ResourceTransferRemediationOption:
    """A debtor's current, material repair of a breached freight term.

    The original source stock and route are historical terms.  A repair is a
    new owner decision and therefore recomposes a currently owned stock and a
    currently known fiscal route; it never edits the old clause.
    """
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
    return next((item for item in world.events if item.id == event_id), None)


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("reciprocal supply requires a current actor decision")
    try:
        actor = EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("reciprocal supply decision has an invalid actor") from exc
    return event, actor


def _can_negotiate(world, actor):
    return (isinstance(actor, EntityRef) and can_actor_act_for(world, actor, actor, "diplomacy")
            and can_actor_act_for(world, actor, actor, "supply"))


def _own_public_stock(world, actor, settlement_id):
    need = world.economy.needs.get(settlement_id)
    stock = world.economy.stocks.get(need.stock_id) if need is not None else None
    return stock if stock is not None and stock.owner_ref == actor else None


def _pressured_places(world, actor):
    """Own blocked food objectives whose own current report still shows need."""
    day = world.clock.absolute_day
    places = []
    for objective in sorted(world.strategy.objectives.values(), key=lambda item: item.id):
        plan = world.strategy.plans.get(f"plan:{objective.id}")
        report = world.knowledge.settlement_report(actor, objective.settlement_id)
        if (objective.actor_ref != actor or objective.resource_id != "food"
                or plan is None or plan.stage != "blocked"
                or report is None or report.observed_day != day or report.missing_food <= 0
                or _own_public_stock(world, actor, objective.settlement_id) is None):
            continue
        places.append((objective.settlement_id, report))
    return tuple(places)


def _own_pledge(world, actor, settlement_id, food_quantity):
    """A concession the requester actually holds, priced by the public catalog."""
    food_price = world.economy.resources["food"].base_price
    for stock in sorted((item for item in world.economy.stocks.values() if item.owner_ref == actor),
                        key=lambda item: item.id):
        for resource_id in sorted(stock.goods):
            if resource_id == "food":
                continue
            free = stock.goods.get(resource_id, 0) - reserve_quantity(world, stock.id, resource_id)
            price = world.economy.resources[resource_id].base_price
            quantity = math.ceil(food_quantity * food_price / price)
            if quantity > 0 and free >= quantity:
                return stock, resource_id, quantity
    return None, None, 0


def _counterpart_settlements(world, counterparty):
    """Public identities only: which settlements this institution administers."""
    return tuple(settlement.id for settlement in sorted(world.society.settlements.values(), key=lambda s: s.id)
                 if settlement.administrator_id == counterparty.id)


def reciprocal_supply_options(world, requester, counterparty=None):
    """Offers the requester can compose from its own reports, goods and routes."""
    if not _can_negotiate(world, requester):
        return ()
    day = world.clock.absolute_day
    options = []
    for settlement_id, report in _pressured_places(world, requester):
        destination = _own_public_stock(world, requester, settlement_id)
        candidates = [EntityRef("polity", identity) for identity in sorted(world.society.polities)]
        for candidate in candidates:
            if (candidate == requester or (counterparty is not None and candidate != counterparty)
                    # Remembered breaches close the door on this counterpart.
                    or institutional_view(world, requester, candidate) < 0):
                continue
            pledge_stock, pledge_resource, pledge_quantity = _own_pledge(world, requester, settlement_id,
                                                                        report.missing_food)
            if pledge_stock is None:
                continue
            for place in _counterpart_settlements(world, candidate):
                # A requester may name a public settlement, but cannot read
                # the provider stock or route behind it. The provider fills
                # those terms independently when responding.
                public_source_id = f"stock:{place}"
                pledge_route = known_supply_path(world, requester, pledge_stock.location_id, place, pledge_resource)
                if pledge_route is None:
                    continue
                option = ReciprocalSupplyOption(
                    id=(f"reciprocal-supply:{requester.id}:{candidate.id}:{settlement_id}:{place}:"
                        f"{report.missing_food}:{pledge_resource}:{pledge_quantity}:{report.event_id}"),
                    actor_ref=requester, counterparty_ref=candidate, settlement_id=settlement_id,
                    food_source_stock_id=public_source_id, food_destination_stock_id=destination.id,
                    food_quantity=report.missing_food, food_route_ids=(),
                    pledge_source_stock_id=pledge_stock.id, pledge_destination_stock_id=public_source_id,
                    pledge_resource_id=pledge_resource, pledge_quantity=pledge_quantity,
                    pledge_route_ids=tuple(pledge_route), expires_day=day + OFFER_WINDOW,
                    food_due_day=day + FOOD_DUE_DAYS, pledge_due_day=day + PLEDGE_DUE_DAYS)
                options.append(option)
    return tuple(sorted(options, key=lambda item: item.id))


def offer_reciprocal_supply(world, requester, option_id, decision_event_id):
    """Deliver the offer through the canonical proposal owner; nothing moves."""
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, OFFER_ACTION)
    if actor != requester:
        raise ValueError("reciprocal supply offer has the wrong actor")
    option = next((item for item in reciprocal_supply_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("reciprocal supply option is stale or unknown")
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "supply")
    proposal = offer_proposal(candidate, actor, option.counterparty_ref, option.clauses(), option.expires_day,
                              decision_event_id=decision.id, intent=option.decision(),
                              proposal_kind="reciprocal_supply")
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.proposals[proposal.id]


def _open_reciprocal_proposals(world, actor):
    day = world.clock.absolute_day
    for _, proposal in sorted(world.relations.proposals.items()):
        if (proposal.status != "offered" or proposal.counterparty_ref != actor
                or proposal.expires_day <= day or proposal.proposal_kind != "reciprocal_supply"
                or any(clause.kind != "resource_transfer" for clause in proposal.clauses)):
            continue
        yield proposal


def reciprocal_response_options(world, counterparty):
    """Accept, refuse, or counter with terms of the counterpart's own holdings."""
    if not _can_negotiate(world, counterparty):
        return ()
    options = []
    for proposal in _open_reciprocal_proposals(world, counterparty):
        options.append(ReciprocalResponseOption(f"reciprocal-response:{proposal.id}:reject",
                                                counterparty, proposal.id, "reject"))
        # Feasibility is judged on the term this actor would owe, never on the
        # other side's holdings.
        owed = next((clause for clause in proposal.clauses if clause.debtor_ref == counterparty), None)
        if owed is None or institutional_view(world, counterparty, proposal.proposer_ref) < 0:
            continue
        destination = world.economy.stocks.get(owed.destination_stock_id)
        if destination is None or destination.owner_ref != proposal.proposer_ref:
            continue
        own_settlements = _counterpart_settlements(world, counterparty)
        for source in sorted((item for item in world.economy.stocks.values()
                              if item.owner_ref == counterparty and item.location_id in own_settlements),
                             key=lambda item: item.id):
            free = source.goods.get(owed.resource_id, 0) - reserve_quantity(world, source.id, owed.resource_id)
            route = known_supply_path(world, counterparty, source.location_id, destination.location_id, owed.resource_id)
            if route is None:
                continue
            if free >= owed.quantity:
                options.append(ReciprocalResponseOption(
                    f"reciprocal-response:{proposal.id}:accept:{source.id}:{':'.join(route)}",
                    counterparty, proposal.id, "accept", source.id, tuple(route)))
            elif free > 0 and owed.resource_id == "food" and proposal.clauses[0] is owed:
                options.append(ReciprocalResponseOption(
                    f"reciprocal-response:{proposal.id}:counter:{source.id}:{free}:{':'.join(route)}",
                    counterparty, proposal.id, "counter", source.id, tuple(route)))
    return tuple(options)


def _counter_option(world, proposal, counterparty, source_id, route_ids):
    """The counterpart's own smaller delivery, keeping the agreed price ratio."""
    delivery, pledge = proposal.clauses
    source = world.economy.stocks[source_id]
    free = source.goods.get("food", 0) - reserve_quantity(world, source.id, "food")
    quantity = min(delivery.quantity, max(0, free))
    if quantity <= 0:
        return None
    food_price = world.economy.resources["food"].base_price
    price = world.economy.resources[pledge.resource_id].base_price
    pledge_quantity = math.ceil(quantity * food_price / price)
    day = world.clock.absolute_day
    return ReciprocalSupplyOption(
        id=(f"reciprocal-supply:{counterparty.id}:{proposal.proposer_ref.id}:{proposal.id}:{quantity}:"
            f"{pledge.resource_id}:{pledge_quantity}"),
        # The counterproposal is authored by ``counterparty`` but preserves
        # the original delivery roles: provider still owes food first, while
        # the original requester still owes the concession.
        actor_ref=proposal.proposer_ref, counterparty_ref=counterparty, settlement_id=source.location_id,
        food_source_stock_id=source.id, food_destination_stock_id=delivery.destination_stock_id,
        food_quantity=quantity, food_route_ids=route_ids,
        # Only the delivery this counterpart owes is rebuilt from its own stock
        # and its own route. The concession keeps the address the requester
        # routed to, so neither side rewrites the other's material term.
        pledge_source_stock_id=pledge.source_stock_id, pledge_destination_stock_id=pledge.destination_stock_id,
        pledge_resource_id=pledge.resource_id, pledge_quantity=pledge_quantity, pledge_route_ids=pledge.route_ids,
        expires_day=day + OFFER_WINDOW, food_due_day=day + FOOD_DUE_DAYS, pledge_due_day=day + PLEDGE_DUE_DAYS,
        parent_id=proposal.id)


def respond_reciprocal_supply(world, counterparty, option_id, decision_event_id):
    """One independent response: refusal, acceptance, or a counterproposal."""
    candidate = deepcopy(world)
    decision, actor = _decision(candidate, decision_event_id, RESPONSE_ACTION)
    if actor != counterparty:
        raise ValueError("reciprocal supply response has the wrong actor")
    option = next((item for item in reciprocal_response_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("reciprocal supply response option is stale or unknown")
    require_authority(candidate, actor, "diplomacy")
    require_authority(candidate, actor, "supply")
    proposal = candidate.relations.proposals[option.proposal_id]
    if option.kind == "counter":
        counter = _counter_option(candidate, proposal, actor, option.source_stock_id, option.route_ids)
        if counter is None:
            raise ValueError("reciprocal supply counterproposal is stale")
        result = offer_proposal(candidate, actor, proposal.proposer_ref, counter.clauses(), counter.expires_day,
                                decision_event_id=decision.id, parent_id=proposal.id, intent=option.decision(),
                                proposal_kind="reciprocal_supply")
    else:
        if option.kind == "accept":
            if option.source_stock_id is None or not option.route_ids:
                raise ValueError("reciprocal supply acceptance lacks its own delivery terms")
            # An actor materializes only the term it owes, from its own stock and
            # its own dated route. The other side's clause is never rewritten.
            owed = next((index for index, clause in enumerate(proposal.clauses)
                         if clause.debtor_ref == actor), None)
            if owed is None:
                raise ValueError("reciprocal supply acceptance owes no term")
            clauses = list(proposal.clauses)
            clauses[owed] = clauses[owed].model_copy(update={"source_stock_id": option.source_stock_id,
                                                             "route_ids": option.route_ids})
            candidate.relations.proposals[proposal.id] = proposal.model_copy(update={"clauses": tuple(clauses)})
        result = respond_proposal(candidate, proposal.id, "accept" if option.kind == "accept" else "reject",
                                  decision_event_id=decision.id, intent=option.decision())
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.relations.proposals[result.id]


def resource_transfer_options(world, actor):
    """Deliveries this debtor can execute today, on its own current holdings."""
    if not can_actor_act_for(world, actor, actor, "supply"):
        return ()
    options = []
    for _, obligation in sorted(world.relations.obligations.items()):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind == "institutional_aid"
                or obligation.status != "active"):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if clause.kind != "resource_transfer" or clause.debtor_ref != actor:
            continue
        dependencies = [world.relations.obligations.get(f"{proposal.id}:term:{index}")
                        for index in clause.depends_on]
        if any(item is None or item.status != "fulfilled" for item in dependencies):
            continue
        source = world.economy.stocks.get(clause.source_stock_id)
        if source is None or source.owner_ref != actor:
            continue
        if source.goods.get(clause.resource_id, 0) - reserve_quantity(world, source.id, clause.resource_id) < clause.quantity:
            continue
        route = next((item for item in fiscal_route_options(world, actor, clause.source_stock_id,
                                                            clause.destination_stock_id, clause.resource_id,
                                                            clause.quantity)
                      if tuple(item.route_ids) == tuple(clause.route_ids)), None)
        if route is None:
            continue
        try:
            check_freight(world, clause.source_stock_id, clause.destination_stock_id, clause.resource_id,
                          clause.quantity, clause.route_ids)
        except (KeyError, ValueError):
            continue
        options.append(ResourceTransferFulfillmentOption(
            id=(f"resource-transfer-fulfill:{obligation.id}:{obligation.last_event_id}:"
                f"{source.last_event_ids.get(clause.resource_id)}"),
            actor_ref=actor, obligation_id=obligation.id, source_stock_id=clause.source_stock_id,
            destination_stock_id=clause.destination_stock_id, resource_id=clause.resource_id,
            quantity=clause.quantity, route_ids=tuple(clause.route_ids), route_option_id=route.id))
    return tuple(options)


def fulfill_resource_transfer(world, actor, option_id, decision_event_id):
    """Execute one promised delivery through the canonical freight owner."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, FULFILL_ACTION)
    if decided_by != actor:
        raise ValueError("resource transfer fulfillment has the wrong actor")
    option = next((item for item in resource_transfer_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("resource transfer option is stale or unknown")
    require_authority(candidate, actor, "supply")
    validate_fiscal_route_option(candidate, option.route_option_id, actor, option.source_stock_id,
                                 option.destination_stock_id, option.resource_id, option.quantity)
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    opened = open_order(candidate, option.source_stock_id, option.destination_stock_id, option.resource_id,
                        option.quantity, option.route_ids, decision_ids=(decision.id,),
                        cause_ids=(obligation.last_event_id, proposal.decision_event_id))
    receipt = record_event(candidate, "resource_transfer_fulfilled",
                           "Entrega prometida despachada pelo dono canônico da carga.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("obligation", obligation.id, "status", "active", "fulfilled"),
                                   _delta("obligation", obligation.id, "material_event_id", None,
                                          opened.last_event_id)),
                           cause_ids=_causes(decision.id, obligation.last_event_id, opened.last_event_id))
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={"status": "fulfilled", "material_event_id": opened.last_event_id, "last_event_id": receipt.id})
    candidate.agenda.cancel(obligation.id)
    from .diplomacy import disclose
    disclose(candidate, proposal, receipt)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return opened


def resource_transfer_remediation_options(world, actor):
    """Enumerate repairs for non-aid resource-transfer breaches.

    Institutional aid keeps its narrower owner because its source candidates
    are tied to the aid request. Reciprocal and negotiated freight terms use
    this general path, still bounded by the debtor's own stock, notice and
    route knowledge.
    """
    if not (isinstance(actor, EntityRef)
            and can_actor_act_for(world, actor, actor, "supply")
            and can_actor_act_for(world, actor, actor, "diplomacy")):
        return ()
    notices = tuple(world.knowledge.notices.values())
    options = []
    for obligation in sorted(world.relations.obligations.values(), key=lambda item: item.id):
        proposal = world.relations.proposals.get(obligation.proposal_id)
        if (proposal is None or proposal.proposal_kind == "institutional_aid"
                or obligation.status != "breached" or obligation.breach_event_id is None):
            continue
        clause = proposal.clauses[obligation.clause_index]
        if (clause.kind != "resource_transfer" or clause.debtor_ref != actor
                or not any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
                           for notice in notices)):
            continue
        destination = world.economy.stocks.get(clause.destination_stock_id)
        if destination is None or destination.owner_ref != clause.creditor_ref:
            continue
        for source in sorted(world.economy.stocks.values(), key=lambda item: item.id):
            if source.owner_ref != actor or source.id == destination.id:
                continue
            available = source.goods.get(clause.resource_id, 0) - reserve_quantity(
                world, source.id, clause.resource_id)
            if available < clause.quantity:
                continue
            routes = fiscal_route_options(world, actor, source.id, destination.id,
                                          clause.resource_id, clause.quantity)
            route = next(iter(routes), None)
            if route is None:
                continue
            try:
                check_freight(world, source.id, destination.id, clause.resource_id,
                              clause.quantity, route.route_ids)
            except (KeyError, ValueError):
                continue
            stamp = source.last_event_ids.get(clause.resource_id)
            options.append(ResourceTransferRemediationOption(
                id=(f"resource-transfer-remediate:{obligation.id}:{obligation.breach_event_id}:"
                    f"{source.id}:{stamp}:{route.id}"), actor_ref=actor,
                obligation_id=obligation.id, source_stock_id=source.id,
                destination_stock_id=destination.id, resource_id=clause.resource_id,
                quantity=clause.quantity, route_ids=tuple(route.route_ids),
                breach_event_id=obligation.breach_event_id, route_option_id=route.id))
    return tuple(options)


def remediate_resource_transfer(world, actor, option_id, decision_event_id):
    """Dispatch a fresh freight term and close only the current obligation."""
    candidate = deepcopy(world)
    decision, decided_by = _decision(candidate, decision_event_id, REMEDIATE_ACTION)
    if decided_by != actor:
        raise ValueError("resource transfer remediation has the wrong actor")
    option = next((item for item in resource_transfer_remediation_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("resource transfer remediation option is stale or unknown")
    require_authority(candidate, actor, "supply")
    require_authority(candidate, actor, "diplomacy")
    obligation = candidate.relations.obligations[option.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    clause = proposal.clauses[obligation.clause_index]
    if obligation.breach_event_id != option.breach_event_id or clause.kind != "resource_transfer":
        raise ValueError("resource transfer remediation breach is stale")
    route = validate_fiscal_route_option(candidate, option.route_option_id, actor,
                                         option.source_stock_id, option.destination_stock_id,
                                         option.resource_id, option.quantity)
    if tuple(route.route_ids) != tuple(option.route_ids):
        raise ValueError("resource transfer remediation route is stale")
    opened = open_order(candidate, option.source_stock_id, option.destination_stock_id,
                        option.resource_id, option.quantity, option.route_ids,
                        decision_ids=(decision.id,), cause_ids=(option.breach_event_id,))
    parties = (proposal.proposer_ref, proposal.counterparty_ref)
    reinforced = tuple(memory for memory in
                       (memories_of(candidate, party, option.breach_event_id) for party in parties)
                       if memory is not None)
    receipt = record_event(
        candidate, "resource_transfer_remediated",
        "Uma remessa material reparou uma obrigação de recurso descumprida.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("obligation", obligation.id, "status", "breached", "remediated"),
                _delta("obligation", obligation.id, "remediation_material_event_id", None,
                       opened.last_event_id),
                *memory_creation_deltas(candidate, parties),
                *reinforcement_deltas(candidate, reinforced)),
        cause_ids=(decision.id, option.breach_event_id, opened.last_event_id))
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={"status": "remediated", "material_event_id": None,
                "remediation_material_event_id": opened.last_event_id,
                "last_event_id": receipt.id})
    candidate.agenda.cancel(obligation.id)
    apply_memory_creation(candidate, parties, receipt)
    apply_reinforcement(candidate, reinforced, receipt)
    disclose(candidate, proposal, receipt)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return opened
