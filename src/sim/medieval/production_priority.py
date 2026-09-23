"""Actor-selected ordering for facilities competing for one local workforce.

This module only enumerates and revalidates a production-priority decision.  It
does not change production, stock, payroll, or the economy schema.  The root
integration is expected to persist the returned :class:`ProductionPriorityDraft`
and let ``produce_monthly`` consume that record at the next boundary.

The important boundary is deliberate: a priority is offered only where two or
more facilities actually compete for the same owner, payroll account,
settlement, and occupation.  Food deficit, prices, and prose are not hidden
triggers for this actor decision.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.economy.models import ProductionPriority
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue

from .economy import _causes, _delta
from .events import record_event
from .institutional_decision_turn import DiscretionaryAdapter


ACTION = "set_production_priority"
SCOPE = "trade"


class ProductionPriorityOption(SocietyValue):
    """One facility an owner may place first in a real payroll conflict."""

    id: str
    actor_ref: EntityRef
    facility_id: str
    owner_ref: EntityRef
    payroll_account_id: str
    settlement_id: str
    occupation: str

    def decision(self):
        # Keep the decision contract intentionally closed.  The engine derives
        # the facility and all allocation terms by recomposing this ID.
        return {"action": ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ProductionPriorityDraft:
    """Validated hand-off for the Economy owner, not a persisted model.

    Root integration should turn this draft into the versioned Economy-owned
    ``ProductionPriority`` record.  Keeping the bridge local prevents this
    vertical from inventing a second persistence or planner system.
    """

    id: str
    owner_ref: EntityRef
    payroll_account_id: str
    settlement_id: str
    occupation: str
    facility_id: str
    decision_event_id: str
    selected_affordance_id: str
    created_day: int
    effective_day: int


def _facility_context(world, facility):
    economy = world.economy
    stock = economy.stocks.get(facility.stock_id)
    recipe = economy.recipes.get(facility.recipe_id)
    if stock is None or recipe is None:
        return None
    return stock, recipe


def _conflict_key(facility, stock, recipe):
    return (stock.owner_ref, facility.payroll_account_id,
            stock.location_id, recipe.occupation)


def production_priority_options(world, actor_ref):
    """Recompose every currently valid facility-priority affordance.

    ``actor_ref`` must be the facility owner's institutional reference.  A
    facility with no valid stock/recipe is not an option, and a solitary line
    never creates a choice merely because it is under-producing.
    """
    if not isinstance(actor_ref, EntityRef) or not can_actor_act_for(world, actor_ref, actor_ref, SCOPE):
        return ()
    grouped = {}
    contexts = {}
    for facility in world.economy.facilities.values():
        context = _facility_context(world, facility)
        if context is None:
            continue
        stock, recipe = context
        key = _conflict_key(facility, stock, recipe)
        contexts[facility.id] = (facility, stock, recipe, key)
        if stock.owner_ref == actor_ref:
            grouped.setdefault(key, []).append(facility.id)

    options = []
    for key, facility_ids in sorted(grouped.items(), key=lambda item: repr(item[0])):
        if len(facility_ids) < 2:
            continue
        owner_ref, payroll_account_id, settlement_id, occupation = key
        for facility_id in sorted(facility_ids):
            facility, _stock, _recipe, _ = contexts[facility_id]
            option_id = (f"production-priority:{owner_ref.kind}:{owner_ref.id}:"
                         f"{payroll_account_id}:{settlement_id}:{occupation}:{facility_id}")
            options.append(ProductionPriorityOption(
                id=option_id, actor_ref=actor_ref, facility_id=facility_id,
                owner_ref=owner_ref, payroll_account_id=payroll_account_id,
                settlement_id=settlement_id, occupation=occupation))
    return tuple(options)


def _decision_event(world, decision_event_id, expected):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION
            or event.day != world.clock.absolute_day
            or event.decision != expected):
        raise ValueError("production priority requires the exact current actor decision")
    return event


def execute_production_priority(world, actor_ref, option_id, decision_event_id):
    """Validate a selected option and return an Economy-owned draft.

    No state is mutated here.  The caller must persist the draft through the
    Economy owner, which can then be consumed by the next production boundary.
    """
    options = production_priority_options(world, actor_ref)
    option = next((item for item in options if item.id == option_id), None)
    if option is None:
        raise ValueError("stale production priority affordance")
    if not can_actor_act_for(world, actor_ref, option.owner_ref, SCOPE):
        raise ValueError("current trade authority no longer permits production priority")
    decision = _decision_event(world, decision_event_id, option.decision())
    next_boundary = ((world.clock.absolute_day // 30) + 1) * 30
    return ProductionPriorityDraft(
        id=f"production-priority:{option.owner_ref.kind}:{option.owner_ref.id}:"
           f"{option.payroll_account_id}:{option.settlement_id}:{option.occupation}",
        owner_ref=option.owner_ref,
        payroll_account_id=option.payroll_account_id,
        settlement_id=option.settlement_id,
        occupation=option.occupation,
        facility_id=option.facility_id,
        decision_event_id=decision.id,
        selected_affordance_id=option.id,
        created_day=world.clock.absolute_day,
        effective_day=next_boundary,
    )


def _provenance(world, draft):
    """Only canonical facts that informed this local scheduling choice."""
    facilities = tuple(
        facility for facility in world.economy.facilities.values()
        if _conflict_key(facility, *_facility_context(world, facility))
        == (draft.owner_ref, draft.payroll_account_id, draft.settlement_id, draft.occupation)
    )
    account = world.economy.accounts[draft.payroll_account_id]
    return _causes(
        account.last_event_id,
        *(facility.last_event_id for facility in facilities),
        *(world.economy.stocks[facility.stock_id].last_event_ids.get(resource)
          for facility in facilities
          for resource in world.economy.recipes[facility.recipe_id].inputs),
    )


def set_production_priority(world, actor_ref, option_id, *, decision_event_id):
    """Persist one decision-backed priority for the next monthly production.

    The caller has already made the actor decision.  Economy stores only the
    validated local ordering intent; it neither produces goods nor reserves
    workers here.  A defensive candidate keeps direct owner calls atomic.
    """
    candidate = deepcopy(world)
    draft = execute_production_priority(candidate, actor_ref, option_id, decision_event_id)
    previous = candidate.economy.production_priorities.get(draft.id)
    causes = _causes(draft.decision_event_id, previous.last_event_id if previous else None,
                     *_provenance(candidate, draft))
    event = record_event(
        candidate, "production_priority_selected",
        "A instituição definiu a precedência de uma linha produtiva para o próximo ciclo.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": draft.decision_event_id,
                        "actor_ref": draft.owner_ref.to_dict(),
                        "selected_affordance_id": draft.selected_affordance_id},
        deltas=(_delta("production_priority", draft.id, "selected_affordance_id",
                       previous.selected_affordance_id if previous else None,
                       draft.selected_affordance_id),),
        cause_ids=causes,
    )
    candidate.economy.production_priorities[draft.id] = ProductionPriority(
        id=draft.id, owner_ref=draft.owner_ref,
        payroll_account_id=draft.payroll_account_id, settlement_id=draft.settlement_id,
        occupation=draft.occupation, facility_id=draft.facility_id,
        effective_day=draft.effective_day, decision_event_id=draft.decision_event_id,
        selected_affordance_id=draft.selected_affordance_id, last_event_id=event.id,
    )
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.economy.production_priorities[draft.id]


def _option_causes(world, option):
    draft = ProductionPriorityDraft(
        id=f"production-priority:{option.owner_ref.kind}:{option.owner_ref.id}:"
           f"{option.payroll_account_id}:{option.settlement_id}:{option.occupation}",
        owner_ref=option.owner_ref, payroll_account_id=option.payroll_account_id,
        settlement_id=option.settlement_id, occupation=option.occupation,
        facility_id=option.facility_id, decision_event_id="pending",
        selected_affordance_id=option.id, created_day=world.clock.absolute_day,
        effective_day=((world.clock.absolute_day // 30) + 1) * 30,
    )
    return _provenance(world, draft)


def production_priority_adapters():
    return (DiscretionaryAdapter(
        name="production_priority", family="production",
        options_fn=production_priority_options,
        label_fn=lambda option: f"Dar precedência produtiva a {option.facility_id} no próximo ciclo.",
        causes_fn=_option_causes,
        execute_fn=lambda world, actor, option_id, decision_event_id:
            set_production_priority(world, actor, option_id, decision_event_id=decision_event_id),
    ),)
