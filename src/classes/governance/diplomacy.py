"""Negotiated intentions and obligations; never an owner of the pledged assets."""
from dataclasses import dataclass, field
from typing import Annotated, Literal
from pydantic import Field, model_validator
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count
from src.classes.economy.models import Positive
from .serialization import RegistrySerialization, validate_actor


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


Clause = Annotated[PaymentClause | TeachingClause, Field(discriminator='kind')]


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
    status: Literal['active', 'fulfilled', 'breached', 'excused'] = 'active'
    material_event_id: Identity | None = None
    last_event_id: Identity


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
        elif clause.technology_id not in world.research.technologies:
            raise ValueError('unknown negotiated technology')


@dataclass
class RelationsState(RegistrySerialization):
    proposals: dict[str, DiplomaticProposal] = field(default_factory=dict)
    obligations: dict[str, Obligation] = field(default_factory=dict)
    registries = {'proposals': DiplomaticProposal, 'obligations': Obligation}

    def validate(self, world=None):
        super().validate(world)
        if world is None:
            return
        events = {e.id: e for e in world.events}
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
            validate_clause_assets(world, p)
            decision = events.get(p.decision_event_id)
            if (p.id != f'proposal:{p.decision_event_id}' or decision is None or decision.day != p.offered_day
                    or decision.decision != offer_intent(p.proposer_ref, p.counterparty_ref, p.clauses, p.expires_day, p.parent_id)):
                raise ValueError('proposal conditions require original decision provenance')
            receipt(p.last_event_id, 'diplomacy', p.id, p.status)
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
            if (obligation.material_event_id is not None) != (obligation.status == 'fulfilled'):
                raise ValueError('fulfillment requires a material receipt')
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
                elif material.event_type != 'technology_taught' or not any(
                        k.event_id == material.id and k.owner_ref == clause.creditor_ref and k.technology_id == clause.technology_id
                        for k in world.knowledge.technologies.values()):
                    raise ValueError('fulfillment requires the negotiated teaching receipt')
