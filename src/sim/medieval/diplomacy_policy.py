"""Conservative teaching bargains; separate actors decide from their own context."""
from src.classes.event import FactKind
from src.classes.governance.diplomacy import PaymentClause, TeachingClause, offer_intent
from src.systems.calendar_agenda import ScheduledSituation
from .events import record_event
from .diplomacy import offer_proposal, respond_proposal
from .diplomacy_context import diplomatic_context
from .commitments import fulfill_obligation


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


def respond(world, ctx, proposal):
    bargain = teaching_bargain(proposal)
    if bargain is None or not {'diplomacy','research','trade'} <= ctx.authority:
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
            offer_proposal(world,ctx.actor,proposal.proposer_ref,terms,proposal.expires_day,
                           decision_event_id=event.id,parent_id=proposal.id)
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
    if bargain is None: return
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
            event = decision(world,offer_intent(ctx.actor,other,terms,day+15,None),
                'Oferecer ensino de técnica própria como fonte de receita.')
            offer_proposal(world,ctx.actor,other,terms,day+15,decision_event_id=event.id)
            schedule_review(world)


def review_diplomacy(world, *, allow_offers=False):
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
