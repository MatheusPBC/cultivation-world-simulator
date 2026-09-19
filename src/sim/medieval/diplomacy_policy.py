"""Conservative teaching bargains; separate actors decide from their own context."""
from dataclasses import dataclass
from copy import deepcopy

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.diplomacy import PaymentClause, TeachingClause, offer_intent
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation
from .events import record_event
from .diplomacy import disclose, offer_proposal, respond_proposal
from .diplomacy_context import diplomatic_context
from .commitments import fulfill_obligation, repudiate_obligation
from .economy import _delta, transfer_money
from .institutional_memory import (apply_memory_creation, apply_reinforcement,
                                   memory_creation_deltas, memories_of, reinforcement_deltas)
from . import ai_decider
from .ai_decider import NO_ACTION, select_option
from .institutional_decision_turn import (DiscretionaryAdapter, _rotated,
                                          review_institutional_decision_turn_with_provider)
from .technology_sighting import (DISCLOSE_TECHNOLOGY_ACTION, disclosure_options,
                                  execute_disclosure)


OFFER_ACTION = 'offer_teaching_bargain'
REQUEST_ACTION = 'request_teaching_bargain'
RESPONSE_ACTION = 'respond_teaching_bargain'
BARGAIN_ATTEMPT_EVENT_TYPE = 'diplomatic_bargain_attempted'
PAY_ACTION = 'fulfill_teaching_payment'
TEACH_ACTION = 'fulfill_promised_teaching'
LEARN_ACTION = 'accept_promised_teaching'
REPUDIATE_ACTION = 'repudiate_obligation'
RENEGOTIATE_ACTION = 'renegotiate_breached_obligation'
REMEDIATE_PAYMENT_ACTION = 'remediate_payment_obligation'
REMEDIATE_TEACHING_ACTION = 'remediate_teaching_obligation'
RENEGOTIATION_DAYS = 45
RENEGOTIATION_EXPIRES_DAYS = 30
PERSUADE_ACTION = 'persuade_proposal'


@dataclass(frozen=True)
class TeachingDiplomacyOption:
    """A transient, engine-derived choice.  Its terms never reach a provider."""
    id: str
    actor_ref: EntityRef
    action: str
    counterparty_ref: EntityRef | None = None
    proposal_id: str | None = None
    response: str | None = None
    technology_id: str | None = None
    amount: int | None = None
    obligation_id: str | None = None
    parent_id: str | None = None
    evidence_event_id: str | None = None

    def decision(self):
        return {'action': self.action, 'actor_ref': self.actor_ref.to_dict(),
                'selected_affordance_id': self.id}

    def causes(self):
        return (self.evidence_event_id,) if self.evidence_event_id else ()


@dataclass(frozen=True)
class RenegotiationOption:
    """A creditor's one bounded attempt to reopen a breached payment term.

    The original obligation is terminal history.  Accepting this new offer,
    if the debtor chooses to do so later, creates a separate obligation.
    """
    id: str
    actor_ref: EntityRef
    obligation_id: str
    proposal_id: str
    counterparty_ref: EntityRef
    clause: PaymentClause | TeachingClause
    expires_day: int
    breach_event_id: str

    def decision(self):
        return {'action': RENEGOTIATE_ACTION, 'actor_ref': self.actor_ref.to_dict(),
                'selected_affordance_id': self.id}

    def causes(self):
        return (self.breach_event_id,)


@dataclass(frozen=True)
class PaymentRemediationOption:
    """A debtor's bounded, material answer to a known payment breach."""
    id: str
    actor_ref: EntityRef
    obligation_id: str
    source_account_id: str
    target_account_id: str
    amount: int
    breach_event_id: str

    def decision(self):
        return {'action': REMEDIATE_PAYMENT_ACTION, 'actor_ref': self.actor_ref.to_dict(),
                'selected_affordance_id': self.id}

    def causes(self):
        return (self.breach_event_id,)


@dataclass(frozen=True)
class PersuasionOption:
    """A dated attempt to keep an open proposal salient for its counterparty."""
    id: str
    actor_ref: EntityRef
    proposal_id: str
    counterparty_ref: EntityRef
    proposal_event_id: str

    @property
    def action(self):
        return PERSUADE_ACTION

    def decision(self):
        return {'action': PERSUADE_ACTION, 'actor_ref': self.actor_ref.to_dict(),
                'selected_affordance_id': self.id}

    def causes(self):
        return (self.proposal_event_id,)


def schedule_review(world):
    day = world.clock.absolute_day + 1
    identity = f'diplomatic-review:{day}'
    if world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity,'diplomatic_review',day))


def decision(world, intent, reason, causes=()):
    return record_event(world,'diplomatic_decision',reason,fact_kind=FactKind.DECISION,
                        decision=intent,cause_ids=causes)


def teaching_bargain(proposal):
    if len(proposal.clauses) != 2:
        return None
    payment, lesson = proposal.clauses
    if (payment.kind != 'payment' or lesson.kind != 'teaching' or payment.depends_on
            or lesson.depends_on != (0,) or payment.debtor_ref != lesson.creditor_ref
            or payment.creditor_ref != lesson.debtor_ref):
        return None
    return payment, lesson


def teaching_only_term(proposal):
    """Return the standalone teaching term used by a remediation proposal."""
    if (proposal.proposal_kind == 'renegotiation' and len(proposal.clauses) == 1
            and proposal.clauses[0].kind == 'teaching' and not proposal.clauses[0].depends_on):
        return proposal.clauses[0]
    return None


def respond(world, ctx, proposal):
    bargain = teaching_bargain(proposal)
    remediation = teaching_only_term(proposal)
    if bargain is None and remediation is None:
        return
    if remediation is not None:
        if not {'diplomacy', 'research'} <= ctx.authority:
            return
        tech = world.research.technologies[remediation.technology_id]
        response = ('accept' if ctx.actor == remediation.creditor_ref
                    and tech.id not in ctx.techniques
                    and tech.capability_id in ctx.capabilities
                    and set(tech.prerequisites) <= ctx.techniques else 'reject')
        event = decision(world, {'action': 'respond_proposal', 'actor_ref': ctx.actor.to_dict(),
                                 'proposal_id': proposal.id, 'response': response},
                         'Responder à remediação de ensino.', (proposal.last_event_id,))
        if 'diplomacy' not in diplomatic_context(world, proposal.proposer_ref).authority:
            return
        respond_proposal(world, proposal.id, response, decision_event_id=event.id)
        if response == 'accept':
            schedule_review(world)
        return
    if not {'diplomacy','research','trade'} <= ctx.authority:
        return
    payment, lesson = bargain
    cost = dict(ctx.research_costs)[lesson.technology_id]
    response, reason = 'reject', 'Recusar condições sem utilidade ou viabilidade própria.'
    if ctx.actor == lesson.creditor_ref:
        tech = world.research.technologies[lesson.technology_id]  # Public catalog, not foreign knowledge.
        useful = (tech.id not in ctx.techniques and tech.capability_id in ctx.capabilities
                  and set(tech.prerequisites) <= ctx.techniques)
        budget = min(ctx.budget,cost*80//100) if useful else 0
        if budget >= payment.amount:
            response, reason = 'accept', 'Aceitar técnica útil dentro do orçamento reservado.'
        elif budget > 0 and proposal.parent_id is None:
            terms = (payment.model_copy(update={'amount':budget}), lesson)
            event = decision(world,offer_intent(ctx.actor,proposal.proposer_ref,terms,proposal.expires_day,proposal.id),
                'Contrapropor preço compatível com o custo local e o caixa livre.',(proposal.last_event_id,))
            attempt = record_event(
                world, BARGAIN_ATTEMPT_EVENT_TYPE,
                'Uma contraproposta foi tentada sobre uma proposta diplomática aberta.',
                fact_kind=FactKind.OCCURRENCE,
                causal_origin=CausalOrigin.ACTOR_DECISION,
                cause_ids=(event.id, proposal.last_event_id),
            )
            offer_proposal(world,ctx.actor,proposal.proposer_ref,terms,proposal.expires_day,
                           decision_event_id=event.id,parent_id=proposal.id,
                           extra_cause_ids=(attempt.id,))
            schedule_review(world)
            return
    elif lesson.technology_id in ctx.techniques and payment.amount >= max(1,cost*60//100):
        response, reason = 'accept', 'Aceitar receita pelo ensino acima do preço mínimo próprio.'
    event = decision(world,{'action':'respond_proposal','actor_ref':ctx.actor.to_dict(),
        'proposal_id':proposal.id,'response':response},reason,(proposal.last_event_id,))
    # If the original signatory lost authority, acceptance cannot bind either side.
    other = diplomatic_context(world,proposal.proposer_ref)
    if 'diplomacy' not in other.authority:
        return
    respond_proposal(world,proposal.id,response,decision_event_id=event.id)
    if response == 'accept': schedule_review(world)


def fulfill(world, ctx, proposal):
    bargain = teaching_bargain(proposal)
    remediation = teaching_only_term(proposal)
    if bargain is None and remediation is None:
        return
    day = world.clock.absolute_day
    events = {e.id:e for e in world.events}
    for index, clause in enumerate(proposal.clauses):
        if clause.debtor_ref != ctx.actor: continue
        obligation = world.relations.obligations[f'{proposal.id}:term:{index}']
        if obligation.status != 'active' or events[obligation.last_event_id].day >= day or day > clause.due_day:
            continue
        dependencies = [world.relations.obligations[f'{proposal.id}:term:{i}'] for i in clause.depends_on]
        if any(o.status != 'fulfilled' or events[o.last_event_id].day >= day for o in dependencies): continue
        if clause.kind == 'payment':
            if 'trade' not in ctx.authority or ctx.balance < clause.amount or ctx.account_id != clause.source_account_id: continue
            event = decision(world,{'action':'pay','actor_ref':ctx.actor.to_dict(),'source_id':clause.source_account_id,
                'target_id':clause.target_account_id,'amount':clause.amount},'Cumprir pagamento negociado.',(obligation.last_event_id,))
            fulfill_obligation(world,obligation.id,decision_event_id=event.id)
        else:
            learner = diplomatic_context(world,clause.creditor_ref)
            tech = world.research.technologies[clause.technology_id]
            if ('research' not in ctx.authority or 'research' not in learner.authority
                    or tech.id not in ctx.techniques or tech.id in learner.techniques
                    or not set(tech.prerequisites) <= learner.techniques): continue
            terms = {'technology_id':tech.id,'teacher_ref':ctx.actor.to_dict(),'student_ref':learner.actor.to_dict()}
            offered = decision(world,{**terms,'action':'teach','actor_ref':ctx.actor.to_dict()},
                'Cumprir ensino prometido após pagamento.',(obligation.last_event_id,))
            accepted = decision(world,{**terms,'action':'learn','actor_ref':learner.actor.to_dict()},
                'Aceitar o ensino contratado.',(offered.id,))
            fulfill_obligation(world,obligation.id,decision_event_id=offered.id,acceptance_id=accepted.id)
        schedule_review(world)
        ctx = diplomatic_context(world,ctx.actor)


def _disclose_teaching_offer(world, actor, other, technology_id):
    """A teacher's own offer to teach IS a factual disclosure of its
    technique to that exact counterparty: without this, the counterparty's
    later, legitimate counteroffer (still proposer of the same known
    bargain, not a request fabricated from nothing) would fail the causal
    sighting gate on ``offer_proposal`` for want of a fact the teacher's own
    offer already made true. Skipped silently when a current sighting
    already exists or disclosure is not presently possible (unreachable);
    the offer itself still proceeds exactly as before either way."""
    option = next((item for item in disclosure_options(world, actor)
                   if item.recipient_ref == other and item.technology_id == technology_id), None)
    if option is None:
        return
    event = decision(world, option.decision(),
                     'Divulgar indício factual da técnica ofertada ao ensino.', option.causes())
    execute_disclosure(world, option, event.id)


def propose(world, ctx, addresses):
    if not ctx.account_id or not {'diplomacy','research','trade'} <= ctx.authority: return
    for tech_id in sorted(ctx.techniques):
        for other, account_id in addresses:
            if other == ctx.actor: continue
            prior = [world.relations.proposals[i] for i in ctx.proposal_ids]
            known = [p for p in prior if other in (p.proposer_ref,p.counterparty_ref)
                     and any(c.kind == 'teaching' and c.technology_id == tech_id for c in p.clauses)]
            if any(p.status in {'offered','accepted'} or world.clock.absolute_day-p.offered_day < 180 for p in known): continue
            day = world.clock.absolute_day
            terms = (PaymentClause(debtor_ref=other,creditor_ref=ctx.actor,due_day=day+20,
                source_account_id=account_id,target_account_id=ctx.account_id,amount=dict(ctx.research_costs)[tech_id]),
                TeachingClause(debtor_ref=ctx.actor,creditor_ref=other,due_day=day+25,depends_on=(0,),technology_id=tech_id))
            _disclose_teaching_offer(world, ctx.actor, other, tech_id)
            event = decision(world,offer_intent(ctx.actor,other,terms,day+15,None),
                'Oferecer ensino de técnica própria como fonte de receita.')
            offer_proposal(world,ctx.actor,other,terms,day+15,decision_event_id=event.id)
            schedule_review(world)


def review_diplomacy(world, *, allow_offers=False):
    """Deterministic fixture policy.

    Real-provider worlds must use :func:`review_diplomacy_with_provider`; this
    routine is deliberately retained for explicit test mode only.
    """
    # Account identifiers are public payment addresses; no foreign balance is passed to a decider.
    addresses = sorted({(a.owner_ref,a.id) for a in world.economy.accounts.values()
        if a.owner_ref.kind in {'polity','organization'}},key=lambda x:(x[0].kind,x[0].id,x[1]))
    actors = sorted({ref for ref,_ in addresses},key=lambda r:(r.kind,r.id))
    for actor in actors:
        ctx = diplomatic_context(world,actor)
        for identity in ctx.proposal_ids:
            p = world.relations.proposals[identity]
            if p.status == 'offered' and p.counterparty_ref == actor and p.offered_day < world.clock.absolute_day < p.expires_day:
                respond(world,ctx,p)
            elif p.status == 'accepted':
                fulfill(world,ctx,p)
                ctx = diplomatic_context(world,actor)
        if allow_offers: propose(world,diplomatic_context(world,actor),addresses)


def _addresses(world):
    # Account identifiers are public payment addresses.  No balance crosses
    # the policy boundary.
    return tuple(sorted({(a.owner_ref, a.id) for a in world.economy.accounts.values()
                         if a.owner_ref.kind in {'polity', 'organization'}},
                        key=lambda item: (item[0].kind, item[0].id, item[1])))


def _known_proposals(world, ctx):
    return tuple(world.relations.proposals[item] for item in ctx.proposal_ids
                 if item in world.relations.proposals)


def _event(world, event_id):
    return next((item for item in world.events if item.id == event_id), None)


def _old_enough(world, event_id):
    event = _event(world, event_id)
    return event is not None and event.day < world.clock.absolute_day


def teaching_offer_options(world, actor, addresses=None):
    """Offers computed from only the speaker's techniques and public addresses."""
    ctx = diplomatic_context(world, actor)
    if not ctx.account_id or not {'diplomacy', 'research', 'trade'} <= ctx.authority:
        return ()
    addresses = _addresses(world) if addresses is None else addresses
    day = world.clock.absolute_day
    costs = dict(ctx.research_costs)
    options = []
    for tech_id in sorted(ctx.techniques):
        for other, account_id in addresses:
            if other == actor:
                continue
            prior = [proposal for proposal in _known_proposals(world, ctx)
                     if other in (proposal.proposer_ref, proposal.counterparty_ref)
                     and any(clause.kind == 'teaching' and clause.technology_id == tech_id
                             for clause in proposal.clauses)]
            if any(proposal.status in {'offered', 'accepted'} or day - proposal.offered_day < 180
                   for proposal in prior):
                continue
            amount = costs[tech_id]
            options.append(TeachingDiplomacyOption(
                id=f'teaching-offer:{actor.kind}:{actor.id}:{other.kind}:{other.id}:{tech_id}:{amount}:{day}',
                actor_ref=actor, action=OFFER_ACTION, counterparty_ref=other,
                technology_id=tech_id, amount=amount))
    return tuple(options)


def teaching_request_options(world, actor):
    """Ask only a holder the actor was factually told about, while current."""
    ctx = diplomatic_context(world, actor)
    if not ctx.account_id or not {'diplomacy', 'research', 'trade'} <= ctx.authority:
        return ()
    day = world.clock.absolute_day
    costs = dict(ctx.research_costs)
    options = []
    for sighting in world.knowledge.technology_sightings_for_actor(actor, current_day=day):
        if (sighting.holder_ref == actor or sighting.technology_id in ctx.techniques
                or sighting.holder_ref.kind not in {'polity', 'organization'}):
            continue
        target_account = next((account.id for account in sorted(world.economy.accounts.values(), key=lambda item: item.id)
                               if account.owner_ref == sighting.holder_ref), None)
        tech = world.research.technologies.get(sighting.technology_id)
        if (target_account is None or tech is None
                or not set(tech.prerequisites) <= ctx.techniques):
            continue
        prior = [proposal for proposal in _known_proposals(world, ctx)
                 if sighting.holder_ref in (proposal.proposer_ref, proposal.counterparty_ref)
                 and any(clause.kind == 'teaching' and clause.technology_id == sighting.technology_id
                         for clause in proposal.clauses)]
        if any(proposal.status in {'offered', 'accepted'} or day - proposal.offered_day < 180
               for proposal in prior):
            continue
        amount = costs[sighting.technology_id]
        options.append(TeachingDiplomacyOption(
            id=(f'teaching-request:{actor.kind}:{actor.id}:{sighting.holder_ref.kind}:{sighting.holder_ref.id}:'
                f'{sighting.technology_id}:{amount}:{sighting.event_id}:{day}'),
            actor_ref=actor, action=REQUEST_ACTION, counterparty_ref=sighting.holder_ref,
            technology_id=sighting.technology_id, amount=amount, evidence_event_id=sighting.event_id))
    return tuple(options)


def teaching_initiation_options(world, actor):
    return (*teaching_offer_options(world, actor), *teaching_request_options(world, actor))


def _proposal_response_options(world, actor):
    """The responder's actual alternatives for a known open teaching bargain."""
    ctx = diplomatic_context(world, actor)
    if not {'diplomacy', 'research'} <= ctx.authority:
        return ()
    day, costs = world.clock.absolute_day, dict(ctx.research_costs)
    options = []
    for proposal in _known_proposals(world, ctx):
        if (proposal.status != 'offered' or proposal.counterparty_ref != actor
                or not proposal.offered_day < day < proposal.expires_day):
            continue
        bargain = teaching_bargain(proposal)
        remediation = teaching_only_term(proposal)
        if bargain is None and remediation is None:
            continue
        if bargain is not None and 'trade' not in ctx.authority:
            continue
        payment = bargain[0] if bargain is not None else None
        lesson = bargain[1] if bargain is not None else remediation
        base = f'teaching-response:{proposal.id}:{proposal.last_event_id}'
        # A refusal has no material precondition.  Acceptance is enumerated
        # only when the actor can presently bind the exact promise.
        options.append(TeachingDiplomacyOption(f'{base}:reject', actor, RESPONSE_ACTION,
                                               proposal_id=proposal.id, response='reject'))
        if actor == lesson.creditor_ref:
            tech = world.research.technologies[lesson.technology_id]
            useful = (tech.id not in ctx.techniques and tech.capability_id in ctx.capabilities
                      and set(tech.prerequisites) <= ctx.techniques)
            budget = min(ctx.budget, costs[tech.id] * 80 // 100) if useful else 0
            if payment is None or budget >= payment.amount:
                options.append(TeachingDiplomacyOption(f'{base}:accept', actor, RESPONSE_ACTION,
                                                       proposal_id=proposal.id, response='accept'))
            elif budget > 0 and proposal.parent_id is None:
                options.append(TeachingDiplomacyOption(f'{base}:counter:{budget}', actor, RESPONSE_ACTION,
                                                       proposal_id=proposal.id, response='counter', amount=budget,
                                                       parent_id=proposal.id))
        elif (payment is not None and lesson.technology_id in ctx.techniques
              and payment.amount >= max(1, costs[lesson.technology_id] * 60 // 100)):
            options.append(TeachingDiplomacyOption(f'{base}:accept', actor, RESPONSE_ACTION,
                                                   proposal_id=proposal.id, response='accept'))
    return tuple(options)


def _payment_options(world, actor):
    ctx = diplomatic_context(world, actor)
    if 'trade' not in ctx.authority:
        return ()
    options = []
    for proposal in _known_proposals(world, ctx):
        if proposal.status != 'accepted':
            continue
        bargain = teaching_bargain(proposal)
        if bargain is None:
            continue
        for index, clause in enumerate(proposal.clauses):
            obligation = world.relations.obligations.get(f'{proposal.id}:term:{index}')
            if (clause.kind != 'payment' or clause.debtor_ref != actor or obligation is None
                    or obligation.status != 'active' or not _old_enough(world, obligation.last_event_id)
                    or world.clock.absolute_day > clause.due_day or ctx.account_id != clause.source_account_id
                    or ctx.balance < clause.amount):
                continue
            dependencies = [world.relations.obligations.get(f'{proposal.id}:term:{item}') for item in clause.depends_on]
            if any(item is None or item.status != 'fulfilled' or not _old_enough(world, item.last_event_id)
                   for item in dependencies):
                continue
            options.append(TeachingDiplomacyOption(
                f'teaching-payment:{obligation.id}:{obligation.last_event_id}:{ctx.account_id}', actor, PAY_ACTION,
                proposal_id=proposal.id, obligation_id=obligation.id, amount=clause.amount))
    return tuple(options)


def _repudiation_options(world, actor):
    """The debtor's own choice, while still able to honor a term, not to.

    Scoped like every other family option: only obligations from proposals
    this actor already knows of (``_known_proposals``), where it is the
    named debtor, still ``active`` and before the clause's own deadline.
    Once the deadline passes the lapse in ``resolve_diplomacy`` takes over
    instead; this option never reaches past its own deadline."""
    ctx = diplomatic_context(world, actor)
    if 'diplomacy' not in ctx.authority:
        return ()
    day = world.clock.absolute_day
    options = []
    for proposal in _known_proposals(world, ctx):
        for index, clause in enumerate(proposal.clauses):
            if clause.debtor_ref != actor:
                continue
            obligation = world.relations.obligations.get(f'{proposal.id}:term:{index}')
            if obligation is None or obligation.status != 'active' or day > clause.due_day:
                continue
            options.append(TeachingDiplomacyOption(
                f'diplomatic-repudiation:{obligation.id}:{obligation.last_event_id}', actor, REPUDIATE_ACTION,
                proposal_id=proposal.id, obligation_id=obligation.id))
    return tuple(options)


def _renegotiation_options(world, actor):
    """Reopen one known, breached payment as a fresh dated offer.

    This is intentionally narrower than general treaty editing: only the
    creditor may ask for a new deadline, and only a payment clause is eligible.
    A breach notice is required so the option cannot become an omniscient
    strategic planner over another institution's private history.
    """
    ctx = diplomatic_context(world, actor)
    if 'diplomacy' not in ctx.authority:
        return ()
    day = world.clock.absolute_day
    result = []
    notices = world.knowledge.notices.values()
    for proposal in _known_proposals(world, ctx):
        if proposal.status != 'accepted':
            continue
        for index, clause in enumerate(proposal.clauses):
            if clause.kind == 'payment':
                eligible = clause.creditor_ref == actor
            elif clause.kind == 'teaching':
                eligible = clause.debtor_ref == actor and clause.depends_on == (0,)
            else:
                eligible = False
            if not eligible:
                continue
            obligation = world.relations.obligations.get(f'{proposal.id}:term:{index}')
            if (obligation is None or obligation.status != 'breached'
                    or obligation.breach_event_id is None
                    or not any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
                               for notice in notices)):
                continue
            marker = f'renegotiation:{obligation.id}:{obligation.breach_event_id}'
            option_prefix = f'{marker}:'
            if any(str(item.request_affordance_id).startswith(option_prefix)
                   for item in world.relations.proposals.values()):
                continue
            if clause.kind == 'teaching':
                payment = world.relations.obligations.get(f'{proposal.id}:term:{clause.depends_on[0]}')
                learner = diplomatic_context(world, clause.creditor_ref)
                if (payment is None or payment.status != 'fulfilled'
                        or 'research' not in ctx.authority or 'research' not in learner.authority
                        or clause.technology_id not in ctx.techniques
                        or clause.technology_id in learner.techniques
                        or not set(world.research.technologies[clause.technology_id].prerequisites) <= learner.techniques):
                    continue
            expires_day = day + RENEGOTIATION_EXPIRES_DAYS
            revised = clause.model_copy(update={'due_day': day + RENEGOTIATION_DAYS,
                                                'depends_on': ()})
            result.append(RenegotiationOption(
                id=f'{marker}:{proposal.last_event_id}', actor_ref=actor,
                obligation_id=obligation.id, proposal_id=proposal.id,
                counterparty_ref=(clause.debtor_ref if clause.kind == 'payment' else clause.creditor_ref), clause=revised,
                expires_day=expires_day, breach_event_id=obligation.breach_event_id))
    return tuple(sorted(result, key=lambda item: item.id))


def _payment_remediation_options(world, actor):
    """Recompose a debtor's material repair from its own current account.

    A breach remains historical.  This option only exists when the debtor was
    notified of its own concluded term, still controls the source account and
    can pay the exact original amount today.
    """
    ctx = diplomatic_context(world, actor)
    if 'trade' not in ctx.authority:
        return ()
    result = []
    notices = world.knowledge.notices.values()
    for proposal in _known_proposals(world, ctx):
        if proposal.status != 'accepted':
            continue
        for index, clause in enumerate(proposal.clauses):
            if clause.kind != 'payment' or clause.debtor_ref != actor:
                continue
            obligation = world.relations.obligations.get(f'{proposal.id}:term:{index}')
            if (obligation is None or obligation.status != 'breached'
                    or obligation.breach_event_id is None
                    or not any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
                               for notice in notices)):
                continue
            source = world.economy.accounts.get(clause.source_account_id)
            target = world.economy.accounts.get(clause.target_account_id)
            if (source is None or target is None or source.owner_ref != actor
                    or source.balance < clause.amount):
                continue
            result.append(PaymentRemediationOption(
                id=f'payment-remediation:{obligation.id}:{obligation.breach_event_id}:{source.id}:{source.last_event_id}',
                actor_ref=actor, obligation_id=obligation.id,
                source_account_id=source.id, target_account_id=target.id,
                amount=clause.amount, breach_event_id=obligation.breach_event_id))
    return tuple(sorted(result, key=lambda item: item.id))


def _persuasion_options(world, actor):
    """Enumerate one current, non-material follow-up per open proposal.

    Either notified side may keep a live proposal salient.  This is an
    actor-authored diplomatic act, not an acceptance: the proposal owner and
    its clauses remain untouched until the other side makes its own response.
    """
    ctx = diplomatic_context(world, actor)
    if 'diplomacy' not in ctx.authority:
        return ()
    day = world.clock.absolute_day
    options = []
    for proposal in _known_proposals(world, ctx):
        if (actor not in {proposal.proposer_ref, proposal.counterparty_ref}
                or proposal.status != 'offered'
                or not proposal.offered_day < day < proposal.expires_day):
            continue
        already = any(event.event_type == 'diplomatic_persuasion_attempted'
                      and event.day == day
                      and event.decision is not None
                      and event.decision.get('actor_ref') == actor.to_dict()
                      and event.decision.get('proposal_id') == proposal.id
                      for event in world.events)
        if already:
            continue
        options.append(PersuasionOption(
            id=f'persuade-proposal:{proposal.id}:{proposal.last_event_id}:{day}',
            actor_ref=actor, proposal_id=proposal.id,
            counterparty_ref=(proposal.counterparty_ref if actor == proposal.proposer_ref
                              else proposal.proposer_ref),
            proposal_event_id=proposal.last_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def _teaching_options(world, actor):
    ctx = diplomatic_context(world, actor)
    if 'research' not in ctx.authority:
        return ()
    options = []
    for proposal in _known_proposals(world, ctx):
        if proposal.status != 'accepted':
            continue
        bargain = teaching_bargain(proposal)
        remediation = teaching_only_term(proposal)
        if bargain is None and remediation is None:
            continue
        lesson = bargain[1] if bargain is not None else remediation
        index = proposal.clauses.index(lesson)
        obligation = world.relations.obligations.get(f'{proposal.id}:term:{index}')
        learner = diplomatic_context(world, lesson.creditor_ref)
        if (lesson.debtor_ref != actor or obligation is None or obligation.status != 'active'
                or not _old_enough(world, obligation.last_event_id) or world.clock.absolute_day > lesson.due_day
                or lesson.technology_id not in ctx.techniques or lesson.technology_id in learner.techniques
                or 'research' not in learner.authority
                or not set(world.research.technologies[lesson.technology_id].prerequisites) <= learner.techniques):
            continue
        dependencies = [world.relations.obligations.get(f'{proposal.id}:term:{item}') for item in lesson.depends_on]
        if any(item is None or item.status != 'fulfilled' or not _old_enough(world, item.last_event_id)
               for item in dependencies):
            continue
        options.append(TeachingDiplomacyOption(
            f'promised-teaching:{obligation.id}:{obligation.last_event_id}:{lesson.technology_id}', actor,
            TEACH_ACTION, proposal_id=proposal.id, technology_id=lesson.technology_id, obligation_id=obligation.id))
    return tuple(options)


def _teacher_decision(world, option):
    return next((event for event in reversed(world.events)
                 if event.day == world.clock.absolute_day and event.fact_kind == FactKind.DECISION
                 and event.decision == option.decision()), None)


def _learning_options(world, actor):
    ctx = diplomatic_context(world, actor)
    if 'research' not in ctx.authority:
        return ()
    options = []
    for proposal in _known_proposals(world, ctx):
        if proposal.status != 'accepted':
            continue
        bargain = teaching_bargain(proposal)
        remediation = teaching_only_term(proposal)
        if bargain is None and remediation is None:
            continue
        lesson = bargain[1] if bargain is not None else remediation
        if lesson.creditor_ref != actor:
            continue
        for teacher_option in _teaching_options(world, lesson.debtor_ref):
            if teacher_option.obligation_id is None or _teacher_decision(world, teacher_option) is None:
                continue
            if teacher_option.technology_id in ctx.techniques:
                continue
            options.append(TeachingDiplomacyOption(
                f'accept-promised-teaching:{teacher_option.id}', actor, LEARN_ACTION, proposal_id=proposal.id,
                technology_id=teacher_option.technology_id, obligation_id=teacher_option.obligation_id))
    return tuple(options)


def _choice(option):
    if hasattr(option, "label"):
        return {"id": option.id, "label": option.label}
    if option.action == DISCLOSE_TECHNOLOGY_ACTION:
        return {'id': option.id,
                'label': f'Comunicar indício factual da técnica própria {option.technology_id}.'}
    if option.action == PERSUADE_ACTION:
        return {'id': option.id,
                'label': 'Reforçar uma proposta aberta com uma tentativa diplomática explícita.'}
    return {'id': option.id, 'label': {
        OFFER_ACTION: f'Oferecer ensino de {option.technology_id} por pagamento já calculado.',
        REQUEST_ACTION: f'Pedir ensino de {option.technology_id} a partir de indício factual atual.',
        RESPONSE_ACTION: f'Responder {option.response} à proposta recebida.',
        PAY_ACTION: 'Cumprir o pagamento prometido.',
        TEACH_ACTION: f'Oferecer o ensino prometido de {option.technology_id}.',
        LEARN_ACTION: f'Aceitar o ensino prometido de {option.technology_id}.',
        REPUDIATE_ACTION: 'Repudiar a obrigação ainda ativa, em vez de tentar cumpri-la a tempo.',
        RENEGOTIATE_ACTION: 'Propor novo prazo para uma obrigação de pagamento quebrada.',
        PERSUADE_ACTION: 'Reforçar uma proposta aberta com uma tentativa diplomática explícita.',
    }[option.action]}


async def _choose(world, actor, options, causes):
    if not options:
        return None
    # IDs name only proposals/obligations this actor was already notified of;
    # this is enough to distinguish its current turns without exposing another
    # institution's balances, holdings, technique ownership or private reports.
    selected = await select_option(world, actor, {
        'today': world.clock.absolute_day,
        'known_proposal_ids': sorted({option.proposal_id for option in options
                                      if getattr(option, 'proposal_id', None)}),
        'own_obligation_ids': sorted({option.obligation_id for option in options
                                      if getattr(option, 'obligation_id', None)}),
    },
                                   [_choice(option) for option in options], causes=causes)
    if selected in (None, NO_ACTION):
        return None
    return next((option for option in options if option.id == selected), None)


def _record_option_decision(world, option, causes):
    return decision(world, option.decision(), 'A instituição escolheu uma opção diplomática canônica.', causes)


def _execute_response(world, option, decision_event_id):
    current = next((item for item in _proposal_response_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    proposal = world.relations.proposals[current.proposal_id]
    if current.response == 'counter':
        # Keep the actor's attempt as its own causal receipt.  It carries no
        # state delta: the existing proposal owner still creates and validates
        # the successor terms below, while the counterpart remains free to
        # accept or reject that new open proposal on its own turn.
        attempt = record_event(
            world, BARGAIN_ATTEMPT_EVENT_TYPE,
            'A contraproposta foi tentada sobre uma proposta diplomática aberta.',
            fact_kind=FactKind.OCCURRENCE,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            cause_ids=(decision_event_id, proposal.last_event_id),
        )
        bargain = teaching_bargain(proposal)
        if bargain is None:
            return False
        payment, lesson = bargain
        terms = (payment.model_copy(update={'amount': current.amount}), lesson)
        offer_proposal(world, current.actor_ref, proposal.proposer_ref, terms, proposal.expires_day,
                       decision_event_id=decision_event_id, parent_id=proposal.id, intent=current.decision(),
                       extra_cause_ids=(attempt.id,))
    else:
        respond_proposal(world, proposal.id, current.response, decision_event_id=decision_event_id,
                         intent=current.decision())
    schedule_review(world)
    return True


def _execute_offer(world, option, decision_event_id):
    current = next((item for item in teaching_initiation_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    day = world.clock.absolute_day
    addresses = _addresses(world)
    account_id = next((account for actor, account in addresses if actor == current.actor_ref), None)
    other = current.counterparty_ref
    if account_id is None or other is None:
        return False
    target = next((account for actor, account in addresses if actor == other), None)
    if target is None:
        return False
    if current.action == OFFER_ACTION:
        terms = (PaymentClause(debtor_ref=other, creditor_ref=current.actor_ref, due_day=day + 20,
                               source_account_id=target, target_account_id=account_id, amount=current.amount),
                 TeachingClause(debtor_ref=current.actor_ref, creditor_ref=other, due_day=day + 25,
                                depends_on=(0,), technology_id=current.technology_id))
        _disclose_teaching_offer(world, current.actor_ref, other, current.technology_id)
    else:
        terms = (PaymentClause(debtor_ref=current.actor_ref, creditor_ref=other, due_day=day + 20,
                               source_account_id=account_id, target_account_id=target, amount=current.amount),
                 TeachingClause(debtor_ref=other, creditor_ref=current.actor_ref, due_day=day + 25,
                                depends_on=(0,), technology_id=current.technology_id))
    offer_proposal(world, current.actor_ref, other, terms, day + 15, decision_event_id=decision_event_id,
                   intent=current.decision())
    schedule_review(world)
    return True


def _execute_payment(world, option, decision_event_id):
    current = next((item for item in _payment_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    fulfill_obligation(world, current.obligation_id, decision_event_id=decision_event_id,
                       decision_intent=current.decision())
    schedule_review(world)
    return True


def _execute_repudiation(world, option, decision_event_id):
    current = next((item for item in _repudiation_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    repudiate_obligation(world, current.obligation_id, decision_event_id=decision_event_id,
                         decision_intent=current.decision())
    schedule_review(world)
    return True


def _execute_renegotiation(world, option, decision_event_id):
    current = next((item for item in _renegotiation_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    offer_proposal(
        world, current.actor_ref, current.counterparty_ref, (current.clause,), current.expires_day,
        decision_event_id=decision_event_id, intent=current.decision(), proposal_kind='renegotiation',
        request_affordance_id=current.id,
        extra_cause_ids=(current.breach_event_id,))
    schedule_review(world)
    return True


def _execute_payment_remediation(world, option, decision_event_id):
    current = next((item for item in _payment_remediation_options(world, option.actor_ref)
                    if item.id == option.id), None)
    if current is None:
        return False
    candidate = deepcopy(world)
    current = next((item for item in _payment_remediation_options(candidate, option.actor_ref)
                    if item.id == option.id), None)
    if current is None:
        return False
    obligation = candidate.relations.obligations[current.obligation_id]
    proposal = candidate.relations.proposals[obligation.proposal_id]
    if obligation.breach_event_id != current.breach_event_id:
        return False
    transfer_money(candidate, current.source_account_id, current.target_account_id,
                   current.amount, decision_event_id=decision_event_id,
                   decision_intent=current.decision())
    material = candidate.economy.payments[decision_event_id]
    parties = (proposal.proposer_ref, proposal.counterparty_ref)
    reinforced = tuple(memory for memory in
                       (memories_of(candidate, party, current.breach_event_id) for party in parties)
                       if memory is not None)
    receipt = record_event(
        candidate, 'payment_obligation_remediated',
        'O pagamento material reparou uma obrigação anteriormente descumprida.',
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(
            _delta('obligation', obligation.id, 'status', 'breached', 'remediated'),
            _delta('obligation', obligation.id, 'remediation_material_event_id', None, material),
            *memory_creation_deltas(candidate, parties),
            *reinforcement_deltas(candidate, reinforced),
        ),
        cause_ids=(decision_event_id, current.breach_event_id, material),
    )
    candidate.relations.obligations[obligation.id] = obligation.model_copy(
        update={'status': 'remediated', 'material_event_id': None,
                'remediation_material_event_id': material, 'last_event_id': receipt.id})
    apply_memory_creation(candidate, parties, receipt)
    apply_reinforcement(candidate, reinforced, receipt)
    disclose(candidate, proposal, receipt)
    candidate.economy.validate(candidate)
    candidate.relations.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    schedule_review(world)
    return True


def _execute_persuasion(world, option, decision_event_id):
    current = next((item for item in _persuasion_options(world, option.actor_ref)
                    if item.id == option.id), None)
    if current is None:
        return False
    proposal = world.relations.proposals.get(current.proposal_id)
    decision_event = _event(world, decision_event_id)
    if (proposal is None or decision_event is None
            or decision_event.decision != current.decision()
            or proposal.last_event_id != current.proposal_event_id):
        return False
    attempt = record_event(
        world, 'diplomatic_persuasion_attempted',
        'A instituição reforçou uma proposta aberta sem alterar seus termos.',
        fact_kind=FactKind.OCCURRENCE, causal_origin=CausalOrigin.ACTOR_DECISION,
        cause_ids=(decision_event.id, current.proposal_event_id),
    )
    # The counterparty receives a fresh notice of the same proposal, but its
    # status, clauses and obligations remain untouched until that actor answers.
    disclose(world, proposal, attempt)
    schedule_review(world)
    return True


def _execute_learning(world, option, decision_event_id):
    current = next((item for item in _learning_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    proposal = world.relations.proposals[current.proposal_id]
    bargain = teaching_bargain(proposal)
    lesson = bargain[1] if bargain is not None else teaching_only_term(proposal)
    if lesson is None:
        return False
    teacher_options = [item for item in _teaching_options(world, lesson.debtor_ref)
                       if item.obligation_id == current.obligation_id]
    teacher = next(((item, _teacher_decision(world, item)) for item in teacher_options
                    if _teacher_decision(world, item) is not None), None)
    if teacher is None:
        return False
    teacher_option, teacher_event = teacher
    fulfill_obligation(world, current.obligation_id, decision_event_id=teacher_event.id,
                       acceptance_id=decision_event_id, decision_intent=teacher_option.decision(),
                       acceptance_intent=current.decision())
    schedule_review(world)
    return True


def _execute_teaching(world, option, decision_event_id):
    """A teacher's promised-teaching decision is only an offer of consent;
    it never changes knowledge until the learner independently accepts, so
    executing it (once the composed menu's decision event already recorded
    the choice) is only ever a re-validated schedule, never a mutation."""
    current = next((item for item in _teaching_options(world, option.actor_ref) if item.id == option.id), None)
    if current is None:
        return False
    schedule_review(world)
    return True


def _diplomacy_actors(world):
    from .authority_claims import provider_actors
    return tuple(sorted({ref for ref, _ in _addresses(world)} | set(provider_actors(world)),
                        key=lambda ref: (ref.kind, ref.id)))


def _option_causes(world, option):
    """Same aggregation every phase already used: a linked proposal's last
    event plus whatever the option's own ``causes()`` names."""
    causes = set()
    if getattr(option, "proposal_id", None):
        causes.add(world.relations.proposals[option.proposal_id].last_event_id)
    if hasattr(option, "causes"):
        causes.update(option.causes())
    causes.discard(None)
    return tuple(sorted(causes))


def _repudiation_cause(world, event):
    """Whether ``event`` (a breach's own terminal transition) was itself
    caused by the debtor's decision to repudiate, rather than only by the
    deadline lapsing. No score is derived; this is a single dated fact."""
    return any((cause := _event(world, link.cause_event_id)) is not None
               and cause.fact_kind == FactKind.DECISION and cause.decision is not None
               and cause.decision.get('action') == REPUDIATE_ACTION
               for link in event.causal_links)


def _known_counterparty_breaches(world, actor):
    """The counterparty (in)fulfillment history this actor has a right to
    know, over every proposal it was itself a party to.

    Discovery stays causal, not omniscient: a proposal this actor never
    negotiated never contributes an entry, and a breach only counts once the
    same notice-based channel ``authority_claims._breach_evidence`` already
    relies on -- ``world.knowledge.notices`` -- actually reached this actor
    for that exact breach event. Three distinct facts are surfaced, never a
    score: ``repudiated`` (the debtor chose not to honor it), ``breached_by_
    deadline`` (it lapsed unmet) and ``excused`` (its own dependency failed
    first, so the failure was never this debtor's).
    """
    ctx = diplomatic_context(world, actor)
    records = []
    for proposal_id in ctx.proposal_ids:
        proposal = world.relations.proposals.get(proposal_id)
        if proposal is None or actor not in (proposal.proposer_ref, proposal.counterparty_ref):
            continue
        counterparty = proposal.counterparty_ref if proposal.proposer_ref == actor else proposal.proposer_ref
        for index, clause in enumerate(proposal.clauses):
            if clause.debtor_ref != counterparty:
                continue
            obligation = world.relations.obligations.get(f'{proposal_id}:term:{index}')
            if obligation is None or obligation.status not in {'breached', 'excused'}:
                continue
            event = _event(world, obligation.last_event_id)
            if event is None:
                continue
            if obligation.status == 'excused':
                kind = 'excused'
            elif any(notice.recipient_ref == actor and notice.event_id == obligation.breach_event_id
                     for notice in world.knowledge.notices.values()):
                kind = 'repudiated' if _repudiation_cause(world, event) else 'breached_by_deadline'
            else:
                continue
            records.append({'counterparty': counterparty.to_dict(), 'proposal_id': proposal_id,
                            'obligation_id': obligation.id, 'kind': kind, 'day': event.day})
    return tuple(sorted(records, key=lambda item: (item['counterparty']['kind'], item['counterparty']['id'],
                                                    item['obligation_id'])))


def _diplomacy_situation(world, actor, options):
    """Exactly the original per-phase situation, now over every currently
    combined option: only proposal/obligation IDs this actor already knows
    of, never a settlement report, objective or foreign holding. The
    counterparty breach history is likewise bounded to what this specific
    actor was itself notified of -- see ``_known_counterparty_breaches``."""
    context = diplomatic_context(world, actor)
    return {
        "today": world.clock.absolute_day,
        "known_proposal_ids": sorted({option.proposal_id for option in options
                                      if getattr(option, "proposal_id", None)}),
        "own_obligation_ids": sorted({option.obligation_id for option in options
                                      if getattr(option, "obligation_id", None)}),
        "known_institutional_views": tuple({
            "counterparty": subject.to_dict(),
            "value": value,
            "evidence_event_ids": list(event_ids),
        } for subject, value, event_ids in context.institutional_views),
        "own_strategic_capacity": context.strategic_capacity,
        "known_strategic_evidence": context.strategic_evidence,
        "known_counterparty_breaches": _known_counterparty_breaches(world, actor),
    }


def _adapter_execute(options_fn, real_executor, kind):
    """Adapt an existing phase executor (which takes the option object, not a
    bare ID) to InstitutionalDecisionTurn's ``(world, actor, option_id, ...)``
    convention, without changing what it does."""
    def execute(world, actor, option_id, decision_event_id):
        option = next((item for item in options_fn(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError(f"stale or unknown {kind} option")
        real_executor(world, option, decision_event_id)
    return execute


def _diplomacy_adapter(name, options_fn, execute_fn):
    return DiscretionaryAdapter(name=name, family="diplomacy", options_fn=options_fn,
                                label_fn=lambda option: _choice(option)["label"],
                                causes_fn=_option_causes, execute_fn=execute_fn,
                                situation_fn=_diplomacy_situation)


def _authority_claim_adapter():
    from .authority_claims import all_options, execute_option
    return _diplomacy_adapter("authority_claim", all_options, execute_option)


DISCLOSURE_ADAPTER = _diplomacy_adapter(
    "technology_disclosure", disclosure_options,
    _adapter_execute(disclosure_options, execute_disclosure, "technology disclosure"))

PROPOSAL_RESPONSE_ADAPTER = _diplomacy_adapter(
    "proposal_response", _proposal_response_options,
    _adapter_execute(_proposal_response_options, _execute_response, "proposal response"))

PAYMENT_ADAPTER = _diplomacy_adapter(
    "teaching_payment", _payment_options,
    _adapter_execute(_payment_options, _execute_payment, "teaching payment"))

REPUDIATION_ADAPTER = _diplomacy_adapter(
    "obligation_repudiation", _repudiation_options,
    _adapter_execute(_repudiation_options, _execute_repudiation, "obligation repudiation"))

RENEGOTIATION_ADAPTER = _diplomacy_adapter(
    "breached_obligation_renegotiation", _renegotiation_options,
    _adapter_execute(_renegotiation_options, _execute_renegotiation, "breached obligation renegotiation"))

PAYMENT_REMEDIATION_ADAPTER = _diplomacy_adapter(
    "payment_obligation_remediation", _payment_remediation_options,
    _adapter_execute(_payment_remediation_options, _execute_payment_remediation,
                     "payment obligation remediation"))

PERSUASION_ADAPTER = _diplomacy_adapter(
    "proposal_persuasion", _persuasion_options,
    _adapter_execute(_persuasion_options, _execute_persuasion, "proposal persuasion"))

OFFER_ADAPTER = _diplomacy_adapter(
    "teaching_initiation", teaching_initiation_options,
    _adapter_execute(teaching_initiation_options, _execute_offer, "teaching initiation"))

TEACHING_ADAPTER = _diplomacy_adapter(
    "promised_teaching", _teaching_options,
    _adapter_execute(_teaching_options, _execute_teaching, "promised teaching"))


def diplomacy_actors(world):
    return _diplomacy_actors(world)


def diplomacy_adapters(*, allow_offers=False):
    """Every family without a same-boundary counterpart dependency, which
    now includes the teacher's own promised-teaching consent: it depends on
    nothing this boundary decides, only on its own already-fulfilled
    payment dependency. Only the learner's acceptance is deliberately
    absent (see :func:`review_promised_teaching_turns`), since it alone
    depends on the teacher's decision from this exact boundary -- a
    same-boundary dependency a single flat menu cannot safely express.
    Excluding the teacher's option here too, as before, would let any
    unrelated concern (an outstanding disclosure candidate, an obligation it
    could instead repudiate) spend the actor's one consultation for the
    boundary and starve the learner phase of the teacher's consent for a
    reason that has nothing to do with this bargain.
    """
    return (_authority_claim_adapter(), DISCLOSURE_ADAPTER, PROPOSAL_RESPONSE_ADAPTER, PAYMENT_ADAPTER,
            REPUDIATION_ADAPTER, RENEGOTIATION_ADAPTER, PAYMENT_REMEDIATION_ADAPTER,
            PERSUASION_ADAPTER, TEACHING_ADAPTER,
            *((OFFER_ADAPTER,) if allow_offers else ()))


async def review_promised_teaching_turns(world, *, consulted=(), actors=None):
    """Learner acceptance, kept in its own turn after the composed menu.

    A learner's option only exists once its teacher's current consent is
    already on the record; since the teacher's own promised-teaching
    decision is now made inside the composed turn (see
    :func:`diplomacy_adapters`), this phase only ever needs to run after
    that turn has already visited every actor. ``consulted`` names the
    actors the composed turn already spent this boundary; they get no
    second turn here.
    """
    if not world.config.ai_enabled:
        return set(consulted)
    consulted = set(consulted)
    actors = _rotated(world, _diplomacy_actors(world)) if actors is None else actors
    for actor in actors:
        if actor in consulted:
            continue
        options = _learning_options(world, actor)
        if not options:
            continue
        # A never-actually-asked actor (no budget, no provider, monthly cap)
        # must still be told apart from one that got a turn and declined or
        # answered badly; only a real answer spends this boundary's turn.
        was_askable = ai_decider.consultable(world, actor)
        proposal_causes = {world.relations.proposals[option.proposal_id].last_event_id
                           if getattr(option, "proposal_id", None) else None for option in options}
        option_causes = {cause for option in options if hasattr(option, "causes")
                         for cause in option.causes()}
        causes = tuple(sorted((proposal_causes | option_causes) - {None}))
        option = await _choose(world, actor, options, causes)
        if option is None:
            if was_askable:
                consulted.add(actor)
            continue
        consulted.add(actor)
        event = _record_option_decision(world, option, causes)
        _execute_learning(world, option, event.id)
    return consulted


async def review_diplomacy_with_provider(world, *, allow_offers=False):
    """One provider consultation per institution across every safe family.

    Authority claims, technology disclosure, proposal response, teaching
    payment, the teacher's own promised-teaching consent and (when allowed)
    a fresh teaching offer are all shown together; the institution picks
    freely among whichever concerns it currently has, instead of a fixed
    phase priority. The learner's acceptance then runs its own ordered turn
    for whoever this one left untouched.
    """
    actors = _rotated(world, _diplomacy_actors(world))
    _, consulted = await review_institutional_decision_turn_with_provider(
        world, diplomacy_adapters(allow_offers=allow_offers), actors=actors,
        situation_fn=_diplomacy_situation)
    await review_promised_teaching_turns(world, consulted=consulted, actors=actors)
