"""Negotiated intentions and obligations; never an owner of the pledged assets."""
from dataclasses import dataclass, field
import json
from typing import Annotated, Literal
from pydantic import Field, model_validator
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count
from src.classes.economy.models import Positive
from .serialization import RegistrySerialization, validate_actor
from .models import AuthorityRecognition


class ClauseBase(SocietyValue):
    debtor_ref: EntityRef
    creditor_ref: EntityRef
    due_day: Count
    depends_on: tuple[Count, ...] = ()


class PaymentClause(ClauseBase):
    kind: Literal['payment'] = 'payment'
    source_account_id: Identity
    target_account_id: Identity
    amount: Positive


class TeachingClause(ClauseBase):
    kind: Literal['teaching'] = 'teaching'
    technology_id: Identity


class ResourceTransferClause(ClauseBase):
    """An engine-derived freight obligation; Relations never owns its cargo."""
    kind: Literal['resource_transfer'] = 'resource_transfer'
    source_stock_id: Identity
    destination_stock_id: Identity
    resource_id: Identity
    quantity: Positive
    route_ids: tuple[Identity, ...]


class WithdrawalClause(ClauseBase):
    """A promise to withdraw one already-known own detachment.

    Relations owns only this obligation.  Society still owns the column and
    executes the later withdrawal from a current, owner-known route.
    """
    kind: Literal['withdrawal'] = 'withdrawal'
    standoff_id: Identity
    detachment_id: Identity


class AdministrationTransferClause(ClauseBase):
    """A current administrator's promise to cede administration of one settlement.

    Relations records the term only.  Society remains the sole owner that can
    later change ``Settlement.administrator_id`` after a new, current decision.
    """
    kind: Literal['administration_transfer'] = 'administration_transfer'
    settlement_id: Identity


Clause = Annotated[PaymentClause | TeachingClause | ResourceTransferClause | WithdrawalClause
                   | AdministrationTransferClause,
                   Field(discriminator='kind')]


class DiplomaticProposal(SocietyValue):
    id: Identity
    proposer_ref: EntityRef
    counterparty_ref: EntityRef
    clauses: tuple[Clause, ...] = Field(min_length=1, max_length=8)
    offered_day: Count
    expires_day: Count
    parent_id: Identity | None = None
    decision_event_id: Identity
    status: Literal['offered', 'accepted', 'rejected', 'superseded', 'expired'] = 'offered'
    last_event_id: Identity
    proposal_kind: Literal['negotiated', 'institutional_aid', 'reciprocal_supply', 'force_deescalation',
                           'administration_concession'] = 'negotiated'
    request_affordance_id: Identity | None = None

    @model_validator(mode='after')
    def valid_terms(self):
        if self.proposer_ref == self.counterparty_ref or self.expires_day <= self.offered_day:
            raise ValueError('proposal needs distinct parties and future expiration')
        parties = {self.proposer_ref, self.counterparty_ref}
        for index, clause in enumerate(self.clauses):
            if {clause.debtor_ref, clause.creditor_ref} != parties or clause.due_day <= self.expires_day:
                raise ValueError('clause requires the proposal parties and a later deadline')
            if len(set(clause.depends_on)) != len(clause.depends_on) or any(
                    dependency >= index or self.clauses[dependency].due_day > clause.due_day for dependency in clause.depends_on):
                raise ValueError('clause dependencies must refer to earlier terms and deadlines')
        return self


class Obligation(SocietyValue):
    id: Identity
    proposal_id: Identity
    clause_index: Count
    status: Literal['active', 'fulfilled', 'breached', 'excused', 'remediated'] = 'active'
    material_event_id: Identity | None = None
    breach_event_id: Identity | None = None
    remediation_material_event_id: Identity | None = None
    last_event_id: Identity


def institutional_memory_id(institution_ref, event_id):
    return f'memory:{institution_ref.kind}:{institution_ref.id}:{event_id}'


class InstitutionalMemory(SocietyValue):
    """How much a known canonical fact still matters to one institution.

    KnowledgeState remains the only owner of whether the institution knows the
    fact. This registry keeps relevance alone: it copies no content, holds no
    score and no weight, and every memory points at the canonical event it
    remembers. Salience is derived on read, never stored.
    """
    id: Identity
    institution_ref: EntityRef
    event_id: Identity
    recorded_day: Count
    last_reinforced_day: Count


def offer_intent(proposer, counterparty, clauses, expires_day, parent_id):
    return {'action': 'offer_proposal', 'actor_ref': proposer.to_dict(),
        'counterparty_ref': counterparty.to_dict(), 'clauses': [c.model_dump(mode='json') for c in clauses],
        'expires_day': expires_day, 'parent_id': parent_id}


def validate_clause_assets(world, proposal):
    for clause in proposal.clauses:
        if clause.kind == 'payment':
            source = world.economy.accounts.get(clause.source_account_id)
            target = world.economy.accounts.get(clause.target_account_id)
            if source is None or target is None or source.owner_ref != clause.debtor_ref or target.owner_ref != clause.creditor_ref:
                raise ValueError('pledged accounts must belong to the respective parties')
        elif clause.kind == 'teaching' and clause.technology_id not in world.research.technologies:
            raise ValueError('unknown negotiated technology')
        elif clause.kind == 'resource_transfer':
            source = world.economy.stocks.get(clause.source_stock_id)
            destination = world.economy.stocks.get(clause.destination_stock_id)
            if (source is None or destination is None or source.owner_ref != clause.debtor_ref
                    or destination.owner_ref != clause.creditor_ref
                    or clause.resource_id not in world.economy.resources):
                raise ValueError('resource transfer requires the parties current stocks')
            from src.classes.economy.logistics import path_regions
            path_regions(world, source.id, destination.id, clause.route_ids, clause.resource_id)
        elif clause.kind == 'withdrawal':
            standoff = world.society.force_standoffs.get(clause.standoff_id)
            detachment = world.society.detachments.get(clause.detachment_id)
            if (standoff is None or detachment is None or clause.detachment_id not in standoff.detachment_ids
                    or detachment.owner_ref != clause.debtor_ref):
                raise ValueError('withdrawal obligation requires its own known detachment and contact')
        elif clause.kind == 'administration_transfer':
            settlement = world.society.settlements.get(clause.settlement_id)
            if settlement is None:
                raise ValueError('administration transfer requires an existing settlement')


def validate_teaching_request_sightings(world, proposal):
    """Creation gate only; old proposals remain historical after sighting expiry."""
    for clause in proposal.clauses:
        if clause.kind != 'teaching' or proposal.proposer_ref == clause.debtor_ref:
            continue
        if (proposal.proposer_ref != clause.creditor_ref
                or not world.knowledge.has_current_technology_sighting(
                    proposal.proposer_ref, clause.debtor_ref, clause.technology_id,
                    world.clock.absolute_day)):
            raise ValueError('teaching request requires a current factual technology sighting')


def aid_request_intent(proposer, selected_affordance_id):
    """Minimal decision wire shape for engine-derived institutional food aid."""
    return {'action': 'request_institutional_aid', 'actor_ref': proposer.to_dict(),
            'selected_affordance_id': selected_affordance_id}


def force_deescalation_intent(proposer, selected_affordance_id):
    return {'action': 'offer_force_deescalation', 'actor_ref': proposer.to_dict(),
            'selected_affordance_id': selected_affordance_id}


def force_deescalation_response_intent(responder, selected_affordance_id):
    return {'action': 'respond_force_deescalation', 'actor_ref': responder.to_dict(),
            'selected_affordance_id': selected_affordance_id}


def administration_concession_intent(proposer, selected_affordance_id):
    return {'action': 'offer_administration_concession', 'actor_ref': proposer.to_dict(),
            'selected_affordance_id': selected_affordance_id}


def administration_concession_response_intent(responder, selected_affordance_id):
    return {'action': 'respond_administration_concession', 'actor_ref': responder.to_dict(),
            'selected_affordance_id': selected_affordance_id}


@dataclass
class RelationsState(RegistrySerialization):
    proposals: dict[str, DiplomaticProposal] = field(default_factory=dict)
    obligations: dict[str, Obligation] = field(default_factory=dict)
    memories: dict[str, InstitutionalMemory] = field(default_factory=dict)
    authority_recognitions: dict[str, AuthorityRecognition] = field(default_factory=dict)
    registries = {'proposals': DiplomaticProposal, 'obligations': Obligation,
                  'memories': InstitutionalMemory,
                  'authority_recognitions': AuthorityRecognition}

    def memories_for(self, institution_ref):
        return tuple(m for _, m in sorted(self.memories.items()) if m.institution_ref == institution_ref)

    def validate(self, world=None):
        super().validate(world)
        if world is None:
            return
        events = {e.id: e for e in world.events}
        for recognition in self.authority_recognitions.values():
            validate_actor(world, recognition.recognizer_ref)
            claim = world.authority.claims.get(recognition.claim_id)
            event = events.get(recognition.last_event_id)
            if (claim is None or event is None or recognition.declared_day > world.clock.absolute_day
                    or recognition.recognizer_ref in (claim.claimant_ref,
                                                      world.authority.offices[claim.office_id].institution_ref)):
                raise ValueError("invalid authority recognition reference")
            notices = world.knowledge.authority_claim_notices.values()
            known = any(notice.claim_id == claim.id and notice.recipient_ref == recognition.recognizer_ref
                        for notice in notices)
            if not known:
                raise ValueError("authority recognition requires private claim knowledge")
            if recognition.stage == "recognized":
                expected_type, before, after, action = (
                    "authority_claim_recognized", "None", "recognized", "recognize_authority_claim")
            elif recognition.stage == "withdrawn":
                expected_type, before, after, action = (
                    "authority_recognition_withdrawn", "recognized", "withdrawn", "withdraw_authority_recognition")
            else:
                expected_type, before, after, action = (
                    ("authority_recognition_lapsed", "authority_claim_lapsed"), "recognized", "lapsed", None)
            expected_types = {expected_type} if isinstance(expected_type, str) else set(expected_type)
            if (event.event_type not in expected_types
                    or not any(delta.owner_kind == "authority_recognition" and delta.owner_id == recognition.id
                               and delta.aspect == "stage" and delta.before == before and delta.after == after
                               for delta in event.deltas)):
                raise ValueError("authority recognition lacks receipt")
            if action is not None and not any(
                    (decision := events.get(link.cause_event_id)) is not None
                    and decision.decision is not None and decision.decision.get("action") == action
                    and decision.decision.get("actor_ref") == recognition.recognizer_ref.to_dict()
                    for link in event.causal_links):
                raise ValueError("authority recognition lacks its actor decision")
        def deadline(identity, day):
            scheduled = world.agenda.get(identity)
            if day <= world.clock.absolute_day or scheduled is None or scheduled.kind != 'diplomacy' or scheduled.due_day != day:
                raise ValueError('pending diplomacy requires its future agenda deadline')
        def receipt(event_id, owner_kind, owner_id, status):
            event = events.get(event_id)
            if event is None or not any(d.owner_kind == owner_kind and d.owner_id == owner_id
                    and d.aspect == 'status' and d.after == status for d in event.deltas):
                raise ValueError('diplomatic status requires its own receipt')
            return event
        for p in self.proposals.values():
            validate_actor(world, p.proposer_ref); validate_actor(world, p.counterparty_ref)
            if not (p.proposal_kind == 'reciprocal_supply' and p.status in {'offered', 'superseded'}):
                validate_clause_assets(world, p)
            decision = events.get(p.decision_event_id)
            is_aid = p.proposal_kind == 'institutional_aid'
            is_concession = p.proposal_kind == 'administration_concession'
            provider_teaching_offer = (decision is not None and decision.decision is not None
                                       and set(decision.decision) == {'action', 'actor_ref', 'selected_affordance_id'}
                                       and decision.decision.get('actor_ref') == p.proposer_ref.to_dict())
            selection_id = str(decision.decision.get('selected_affordance_id', '')) if provider_teaching_offer else ''
            teaching_offer_decision = provider_teaching_offer and (
                (decision.decision.get('action') == 'offer_teaching_bargain'
                 and selection_id.startswith(f'teaching-offer:{p.proposer_ref.kind}:{p.proposer_ref.id}:')
                 and selection_id.endswith(f':{p.offered_day}'))
                or (decision.decision.get('action') == 'request_teaching_bargain'
                    and selection_id.startswith(f'teaching-request:{p.proposer_ref.kind}:{p.proposer_ref.id}:')
                    and selection_id.endswith(f':{p.offered_day}'))
                or (decision.decision.get('action') == 'respond_teaching_bargain' and p.parent_id is not None
                    and selection_id.startswith(f'teaching-response:{p.parent_id}:')
                    and ':counter:' in selection_id))
            expected_decision = (decision.decision if teaching_offer_decision else
                                 aid_request_intent(p.proposer_ref, p.request_affordance_id)
                                 if is_aid and p.request_affordance_id is not None else
                                 force_deescalation_intent(p.proposer_ref, p.request_affordance_id)
                                 if p.proposal_kind == 'force_deescalation' and p.request_affordance_id is not None else
                                 administration_concession_intent(p.proposer_ref, p.request_affordance_id)
                                 if is_concession and p.request_affordance_id is not None else
                                 decision.decision if p.proposal_kind == 'reciprocal_supply' and decision is not None else
                                 offer_intent(p.proposer_ref, p.counterparty_ref, p.clauses, p.expires_day, p.parent_id))
            if is_aid and (p.request_affordance_id is None or any(clause.kind != 'resource_transfer' for clause in p.clauses)):
                raise ValueError('institutional aid requires resource transfer clauses')
            if p.proposal_kind == 'force_deescalation' and (
                    p.request_affordance_id is None or any(clause.kind != 'withdrawal' for clause in p.clauses)):
                raise ValueError('force deescalation requires withdrawal clauses')
            if p.proposal_kind == 'force_deescalation':
                # This is deliberately not a general treaty language.  A
                # contact offer can bind only the proposer, or one column of
                # each participant, to leave.  In particular it cannot mean
                # "you leave while I remain".
                withdrawals = tuple(p.clauses)
                if len(withdrawals) not in {1, 2}:
                    raise ValueError('force deescalation has one or two withdrawal terms')
                standoff_ids = {clause.standoff_id for clause in withdrawals}
                if len(standoff_ids) != 1:
                    raise ValueError('force deescalation terms require one contact')
                own_terms = [clause for clause in withdrawals if clause.debtor_ref == p.proposer_ref
                             and clause.creditor_ref == p.counterparty_ref]
                counterpart_terms = [clause for clause in withdrawals
                                     if clause.debtor_ref == p.counterparty_ref
                                     and clause.creditor_ref == p.proposer_ref]
                if len(own_terms) != 1 or len(counterpart_terms) != len(withdrawals) - 1:
                    raise ValueError('force deescalation cannot obligate only the counterparty')
            if is_concession:
                if p.request_affordance_id is None or len(p.clauses) != 2:
                    raise ValueError('administration concession requires its selected current terms')
                transfer, withdrawal = p.clauses
                if (transfer.kind != 'administration_transfer' or withdrawal.kind != 'withdrawal'
                        or transfer.debtor_ref != p.counterparty_ref or transfer.creditor_ref != p.proposer_ref
                        or withdrawal.debtor_ref != p.proposer_ref or withdrawal.creditor_ref != p.counterparty_ref
                        or transfer.depends_on or withdrawal.depends_on != (0,)):
                    raise ValueError('administration concession requires transfer before withdrawal')
                settlement = world.society.settlements[transfer.settlement_id]
                transfer_obligation = self.obligations.get(f'{p.id}:term:0')
                if ((transfer_obligation is None and p.status == 'offered')
                        or (transfer_obligation is not None and transfer_obligation.status == 'active')):
                    if settlement.administrator_id != transfer.debtor_ref.id:
                        raise ValueError('active administration transfer requires its current administrator')
                elif transfer_obligation is not None and transfer_obligation.status == 'fulfilled':
                    if settlement.administrator_id != transfer.creditor_ref.id:
                        raise ValueError('fulfilled administration transfer requires its new administrator')
            if is_aid:
                request_events = [item for item in events.values()
                                  if item.event_type == 'institutional_aid_requested'
                                  and p.decision_event_id in {link.cause_event_id for link in item.causal_links}
                                  and any(delta.owner_kind == 'aid_request' and delta.aspect == 'option_id'
                                          and delta.after == p.request_affordance_id for delta in item.deltas)]
                provider_events = [item for item in request_events
                                   if any(delta.owner_kind == 'aid_request' and delta.aspect == 'provider_ref'
                                          and delta.after == json.dumps(p.counterparty_ref.to_dict(), sort_keys=True,
                                                                        separators=(',', ':'), ensure_ascii=False)
                                          for delta in item.deltas)]
                if len(provider_events) != 1:
                    raise ValueError('institutional aid proposal lacks its request provenance')
            if (p.id != f'proposal:{p.decision_event_id}' or decision is None or decision.day != p.offered_day
                    or decision.decision != expected_decision):
                raise ValueError('proposal conditions require original decision provenance')
            receipt(p.last_event_id, 'diplomacy', p.id, p.status)
            if p.proposal_kind == 'force_deescalation' and p.status in {'accepted', 'rejected'}:
                response = events[p.last_event_id]
                decisions = [events.get(link.cause_event_id) for link in response.causal_links]
                decisions = [item for item in decisions if item is not None and item.fact_kind.name == 'DECISION'
                             and item.decision]
                matching = [item for item in decisions
                            if item.decision.get('action') == 'respond_force_deescalation'
                            and item.decision.get('actor_ref') == p.counterparty_ref.to_dict()
                            and str(item.decision.get('selected_affordance_id', '')).startswith(
                                f'force-deescalation-response:{p.id}:')
                            and str(item.decision.get('selected_affordance_id', '')).endswith(
                                ':accept' if p.status == 'accepted' else ':reject')]
                if len(matching) != 1:
                    raise ValueError('force deescalation response requires its exact decision')
            if is_concession and p.status in {'accepted', 'rejected'}:
                response = events[p.last_event_id]
                matching = [events.get(link.cause_event_id) for link in response.causal_links]
                matching = [item for item in matching if item is not None and item.fact_kind.name == 'DECISION'
                            and item.decision
                            and item.decision.get('action') == 'respond_administration_concession'
                            and item.decision.get('actor_ref') == p.counterparty_ref.to_dict()
                            and str(item.decision.get('selected_affordance_id', '')).startswith(
                                f'administration-concession-response:{p.id}:')
                            and str(item.decision.get('selected_affordance_id', '')).endswith(
                                ':accept' if p.status == 'accepted' else ':reject')]
                if len(matching) != 1:
                    raise ValueError('administration concession response requires its exact decision')
            if p.status == 'offered':
                deadline(p.id, p.expires_day)
            if p.parent_id:
                parent = self.proposals.get(p.parent_id)
                if parent is None or parent.status != 'superseded' or parent.counterparty_ref != p.proposer_ref or parent.proposer_ref != p.counterparty_ref:
                    raise ValueError('invalid counteroffer provenance')
            for i in range(len(p.clauses)):
                exists = f'{p.id}:term:{i}' in self.obligations
                if exists != (p.status == 'accepted'):
                    raise ValueError('accepted proposal requires exactly its obligations')
        used = set()
        for obligation in self.obligations.values():
            p = self.proposals.get(obligation.proposal_id)
            if (p is None or p.status != 'accepted' or obligation.clause_index >= len(p.clauses)
                    or obligation.id != f'{p.id}:term:{obligation.clause_index}'):
                raise ValueError('obligation requires an accepted proposal clause')
            receipt(obligation.last_event_id, 'obligation', obligation.id, obligation.status)
            if obligation.status == 'active':
                deadline(obligation.id, p.clauses[obligation.clause_index].due_day + 1)
            elif obligation.status in {'breached', 'remediated'} and world.agenda.get(obligation.id) is not None:
                raise ValueError('concluded obligation cannot remain on the agenda')
            if obligation.status == 'fulfilled':
                if (obligation.material_event_id is None or obligation.breach_event_id is not None
                        or obligation.remediation_material_event_id is not None):
                    raise ValueError('fulfillment requires only its material receipt')
            elif obligation.status == 'breached':
                if (obligation.material_event_id is not None or obligation.remediation_material_event_id is not None
                        or obligation.breach_event_id != obligation.last_event_id):
                    raise ValueError('breach requires its own receipt and no material receipt')
                breach = events.get(obligation.breach_event_id)
                if (breach is None or breach.event_type != 'commitment_breached'
                        or not any(d.owner_kind == 'obligation' and d.owner_id == obligation.id
                                   and d.aspect == 'status' and d.after == 'breached' for d in breach.deltas)):
                    raise ValueError('breached obligation lacks its breach receipt')
            elif obligation.status == 'remediated':
                if (obligation.material_event_id is not None or obligation.breach_event_id is None
                        or obligation.remediation_material_event_id is None):
                    raise ValueError('remediation requires a breach and new material receipt')
                breach = events.get(obligation.breach_event_id)
                material = events.get(obligation.remediation_material_event_id)
                final = events.get(obligation.last_event_id)
                if (breach is None or breach.event_type != 'commitment_breached'
                        or material is None or material.event_type != 'freight_opened'
                        or final is None or final.event_type != 'institutional_aid_remediated'
                        or obligation.breach_event_id not in {link.cause_event_id for link in final.causal_links}
                        or obligation.remediation_material_event_id not in {link.cause_event_id for link in final.causal_links}
                        or not any(d.owner_kind == 'obligation' and d.owner_id == obligation.id
                                   and d.aspect == 'status' and d.after == 'remediated' for d in final.deltas)):
                    raise ValueError('remediation requires a receipt linked to breach and freight')
            elif (obligation.material_event_id is not None or obligation.breach_event_id is not None
                  or obligation.remediation_material_event_id is not None):
                raise ValueError('non-concluded obligation cannot retain material provenance')
            if obligation.material_event_id:
                if obligation.material_event_id in used or obligation.material_event_id not in events:
                    raise ValueError('material receipt cannot fulfill multiple obligations')
                used.add(obligation.material_event_id)
                clause = p.clauses[obligation.clause_index]
                material = events[obligation.material_event_id]
                final = events[obligation.last_event_id]
                if material.id not in {link.cause_event_id for link in final.causal_links} or material.day > clause.due_day:
                    raise ValueError('fulfillment must link its timely material receipt')
                if clause.kind == 'payment':
                    if material.event_type != 'payment_completed' or not all(any(
                            d.owner_kind == 'account' and d.owner_id == account and d.aspect == 'balance'
                            and int(d.after) - int(d.before) == amount for d in material.deltas)
                            for account, amount in ((clause.source_account_id,-clause.amount),(clause.target_account_id,clause.amount))):
                        raise ValueError('fulfillment requires the negotiated payment receipt')
                elif clause.kind == 'teaching' and (material.event_type != 'technology_taught' or not any(
                        k.event_id == material.id and k.owner_ref == clause.creditor_ref and k.technology_id == clause.technology_id
                        for k in world.knowledge.technologies.values())):
                    raise ValueError('fulfillment requires the negotiated teaching receipt')
                elif clause.kind == 'resource_transfer':
                    # Aid and reciprocal commitments deliver through the same
                    # canonical freight owner; only the naming of the debtor's
                    # own fulfillment decision differs.
                    fulfillment_causes = ({link.cause_event_id for link in material.causal_links}
                                          & {link.cause_event_id for link in final.causal_links})
                    decisions = [event for event in events.values()
                                 if event.id in fulfillment_causes
                                 and event.fact_kind.name == 'DECISION'
                                 and event.decision and event.decision.get('action') in {
                                     'fulfill_institutional_aid', 'fulfill_resource_transfer'}
                                 and event.decision.get('actor_ref') == clause.debtor_ref.to_dict()]
                    freight = [order for order in world.economy.freight_orders.values()
                               if (order.source_id == clause.source_stock_id
                                   and order.destination_id == clause.destination_stock_id
                                   and order.resource_id == clause.resource_id
                                   and order.quantity == clause.quantity
                                   and order.route_ids == clause.route_ids
                                   and material.id == f"event:{order.id.split(':', 1)[1]}"
                                   and any(decision.id in order.decision_ids for decision in decisions))]
                    if (material.event_type != 'freight_opened' or len(freight) != 1
                            or not any(delta.owner_kind == 'stock' and delta.owner_id == clause.source_stock_id
                                       and delta.aspect == clause.resource_id
                                       and int(delta.after) - int(delta.before) == -clause.quantity
                                       for delta in material.deltas)):
                        raise ValueError('fulfillment requires the negotiated freight receipt')
                elif clause.kind == 'withdrawal':
                    decisions = [event for event in events.values()
                                 if event.fact_kind.name == 'DECISION' and event.decision
                                 and event.decision.get('action') == 'fulfill_force_withdrawal'
                                 and event.decision.get('actor_ref') == clause.debtor_ref.to_dict()]
                    if (material.event_type != 'detachment_withdrawal_started'
                            or not any(delta.owner_kind == 'detachment' and delta.owner_id == clause.detachment_id
                                       and delta.aspect == 'stage' and delta.after == 'marching'
                                       for delta in material.deltas)
                            or not any(decision.id in {link.cause_event_id for link in material.causal_links}
                                       for decision in decisions)):
                        raise ValueError('fulfillment requires the debtor withdrawal receipt')
                elif clause.kind == 'administration_transfer':
                    decisions = [event for event in events.values()
                                 if event.fact_kind.name == 'DECISION' and event.decision
                                 and event.decision.get('action') == 'fulfill_administration_transfer'
                                 and event.decision.get('actor_ref') == clause.debtor_ref.to_dict()]
                    if (material.event_type != 'settlement_administration_transferred'
                            or not any(delta.owner_kind == 'settlement' and delta.owner_id == clause.settlement_id
                                       and delta.aspect == 'administrator_id'
                                       and delta.before == clause.debtor_ref.id and delta.after == clause.creditor_ref.id
                                       for delta in material.deltas)
                            or not any(decision.id in {link.cause_event_id for link in material.causal_links}
                                       for decision in decisions)):
                        raise ValueError('fulfillment requires the administrator transfer receipt')
            if obligation.status == 'remediated':
                material_id = obligation.remediation_material_event_id
                if material_id in used or material_id not in events:
                    raise ValueError('remediation material receipt cannot be reused')
                used.add(material_id)
                clause = p.clauses[obligation.clause_index]
                if clause.kind != 'resource_transfer':
                    raise ValueError('only resource transfers can be remediated')
                material = events[material_id]
                decisions = [event for event in events.values()
                             if event.fact_kind.name == 'DECISION'
                             and event.decision and event.decision.get('action') == 'remediate_institutional_aid'
                             and event.decision.get('actor_ref') == clause.debtor_ref.to_dict()]
                freight = [order for order in world.economy.freight_orders.values()
                           if (order.destination_id == clause.destination_stock_id
                               and order.resource_id == clause.resource_id
                               and order.quantity == clause.quantity
                               and world.economy.stocks[order.source_id].owner_ref == clause.debtor_ref
                               and any(decision.id in order.decision_ids for decision in decisions)
                               and material.id == f"event:{order.id.split(':', 1)[1]}"
                               )]
                if (len(freight) != 1
                        or not any(delta.owner_kind == 'stock' and delta.owner_id == freight[0].source_id
                                   and delta.aspect == clause.resource_id
                                   and int(delta.after) - int(delta.before) == -clause.quantity
                                   for delta in material.deltas)):
                    raise ValueError('remediation requires the negotiated freight receipt')
        for memory in self.memories.values():
            self._validate_memory(world, events, memory)

    @staticmethod
    def _validate_memory(world, events, memory):
        """Relevance of a fact the institution already knows through Knowledge."""
        validate_actor(world, memory.institution_ref)
        remembered = events.get(memory.event_id)
        if (memory.id != institutional_memory_id(memory.institution_ref, memory.event_id)
                or remembered is None or remembered.fact_kind.name != 'STATE_TRANSITION'
                or remembered.day != memory.recorded_day
                or not memory.recorded_day <= memory.last_reinforced_day <= world.clock.absolute_day
                or not any(d.owner_kind == 'institutional_memory' and d.owner_id == memory.id
                           and d.aspect == 'recorded_day' and d.after == str(memory.recorded_day)
                           for d in remembered.deltas)):
            raise ValueError('institutional memory requires its canonical fact and creation receipt')
        knows_fact = any(notice.recipient_ref == memory.institution_ref and notice.event_id == memory.event_id
                         for notice in world.knowledge.notices.values())
        knows_fact = knows_fact or any(
            finding.recipient_ref == memory.institution_ref and finding.event_id == memory.event_id
            for finding in world.knowledge.investigation_findings.values())
        if not knows_fact:
            raise ValueError('institutional memory requires the knowledge notice of that fact')
        if memory.last_reinforced_day != memory.recorded_day and not any(
                event.day == memory.last_reinforced_day
                and any(d.owner_kind == 'institutional_memory' and d.owner_id == memory.id
                        and d.aspect == 'last_reinforced_day' and d.after == str(memory.last_reinforced_day)
                        for d in event.deltas)
                for event in events.values()):
            raise ValueError('reinforced memory requires its own receipt')
