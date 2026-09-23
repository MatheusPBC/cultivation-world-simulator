"""One institutional response to a known occupied settlement.

Strategy keeps the intent and its factual source.  Force remains the only
owner of soldiers, food, wages, routes and movement; this module merely gives
an institution two bounded provider turns over options those owners already
enumerate.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.models import Objective, StrategicPlan
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .actor_dossier import provider_strategic_capacity
from .economy import _causes, _delta
from .events import record_event
from .force import raise_detachment, raise_options, recruitment_capacity
from .institutional_memory import institutional_views
from .institutional_decision_turn import (DiscretionaryAdapter, _rotated,
                                          review_institutional_decision_turn_with_provider)


ADOPT_ACTION = "adopt_occupied_settlement_defense"
REPORT_MAX_AGE_DAYS = 31
REVIEW_KIND = "strategy_response_review"
_REVIEW_PREFIX = "strategy-response-review:"


@dataclass(frozen=True)
class DefenseAdoptionOption:
    id: str
    actor_ref: EntityRef
    settlement_id: str
    report_event_id: str

    def decision(self):
        return {"action": ADOPT_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _objective_id(actor, settlement_id):
    return f"objective:defend-occupied:{actor.kind}:{actor.id}:{settlement_id}"


def _plan_id(objective_id):
    return f"plan:{objective_id}"


def _review_id(plan_id):
    return f"{_REVIEW_PREFIX}{plan_id}"


def _authority_interest(world, actor, settlement):
    return (actor.kind == "polity" and (settlement.administrator_id == actor.id or actor.id in settlement.claimant_ids)
            and can_actor_act_for(world, actor, actor, "military"))


def _current_occupied_report(world, actor, settlement_id):
    settlement = world.society.settlements.get(settlement_id)
    report = world.knowledge.settlement_report(actor, settlement_id)
    if (settlement is None or report is None or report.recipient_ref != actor or report.publisher_ref != actor
            or report.channel != "local_settlement_report" or report.settlement_id != settlement_id
            or not 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE_DAYS
            or not _authority_interest(world, actor, settlement)
            or report.occupier_id in {None, actor.id}
            or report.occupier_id != settlement.occupier_id):
        return None
    return report


def defense_adoption_options(world, actor):
    """An institution may adopt only an occupied place it directly observed."""
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    options = []
    for report in world.knowledge.settlements_for_actor(actor):
        if _current_occupied_report(world, actor, report.settlement_id) is None:
            continue
        objective_id = _objective_id(actor, report.settlement_id)
        if objective_id in world.strategy.objectives:
            continue
        options.append(DefenseAdoptionOption(
            id=f"strategy-defense-adopt:{actor.id}:{report.settlement_id}:{report.event_id}:{report.occupier_id}",
            actor_ref=actor, settlement_id=report.settlement_id, report_event_id=report.event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def adopt_occupied_settlement_defense(world, actor, option_id, decision_event_id):
    """Persist only intent and its receipt; no force or resource is created."""
    candidate = deepcopy(world)
    option = next((item for item in defense_adoption_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("strategy defense option is stale or unknown")
    from .force import _decision
    decision, decided_by = _decision(candidate, decision_event_id, ADOPT_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("strategy defense has the wrong decision")
    require_authority(candidate, actor, "military")
    report = _current_occupied_report(candidate, actor, option.settlement_id)
    if report is None or report.event_id != option.report_event_id:
        raise ValueError("strategy defense report is no longer current")
    objective = Objective(
        id=_objective_id(actor, option.settlement_id), actor_ref=actor, settlement_id=option.settlement_id,
        stock_id=candidate.economy.needs[option.settlement_id].stock_id, resource_id="food",
        kind="defend_occupied_settlement", motivation="Responder à ocupação observada de um assentamento próprio.")
    plan = StrategicPlan(id=_plan_id(objective.id), objective_id=objective.id, stage="adopted",
                         last_review_day=candidate.clock.absolute_day, last_event_id="pending")
    event = record_event(
        candidate, "strategy_defense_adopted", "Uma instituição adotou uma resposta defensiva a uma ocupação observada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("strategy_objective", objective.id, "kind", None, objective.kind),
                _delta("strategy_plan", plan.id, "stage", None, plan.stage)),
        cause_ids=_causes(decision.id, report.event_id))
    candidate.strategy.objectives[objective.id] = objective
    candidate.strategy.plans[plan.id] = plan.model_copy(update={"last_event_id": event.id})
    candidate.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND, candidate.clock.absolute_day + 1))
    candidate.strategy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.strategy.plans[plan.id]


def _plan_status(world, objective):
    settlement = world.society.settlements.get(objective.settlement_id)
    if settlement is None or not _authority_interest(world, objective.actor_ref, settlement):
        return "blocked", "sem autoridade militar sobre o assentamento"
    report = world.knowledge.settlement_report(objective.actor_ref, objective.settlement_id)
    if report is None or not 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE_DAYS:
        return "blocked", "relatório do assentamento expirou"
    if report.occupier_id != settlement.occupier_id:
        return "blocked", "relatório local contradito; aguardar nova observação"
    if report.occupier_id in {None, objective.actor_ref.id}:
        return "closed", "relatório local confirmou o fim da ocupação estrangeira"
    if _current_occupied_report(world, objective.actor_ref, objective.settlement_id) is None:
        return "blocked", "relatório local não permite resposta atual"
    return None, None


def _set_plan(world, plan, stage, *, blocker=None, causes=(), detachment_id=None,
              recruitment_source=None):
    changed = [_delta("strategy_plan", plan.id, "stage", plan.stage, stage)]
    if detachment_id != plan.detachment_id:
        changed.append(_delta("strategy_plan", plan.id, "detachment_id", plan.detachment_id, detachment_id))
    if recruitment_source is not None:
        source_id, _, count = recruitment_source
        changed.extend((_delta("military_recruitment", source_id, "plan_id", None, plan.id),
                        _delta("military_recruitment", source_id, "labor_shortfall", 0, count)))
    event = record_event(
        world, "strategy_defense_plan_updated", "O plano defensivo foi reavaliado contra a situação atual.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(changed),
        cause_ids=_causes(plan.last_event_id, *causes))
    updated = plan.model_copy(update={"stage": stage, "blocker": blocker,
                                       "detachment_id": detachment_id,
                                       "last_review_day": world.clock.absolute_day, "last_event_id": event.id})
    world.strategy.plans[plan.id] = updated
    return updated


def defense_action_options(world, actor, plan_id):
    """Offer ordinary or sustained expeditions from the same material force owner."""
    plan = world.strategy.plans.get(plan_id)
    if plan is None or plan.stage not in {"adopted", "blocked"} or plan.detachment_id is not None:
        return ()
    objective = world.strategy.objectives.get(plan.objective_id)
    if objective is None or objective.actor_ref != actor or _plan_status(world, objective)[0] is not None:
        return ()
    return tuple(item for days in (10, 40) for item in raise_options(world, actor, days=days)
                 if item.destination_id == objective.settlement_id)


def _review_plan_id(situation):
    if situation.kind != REVIEW_KIND or not situation.id.startswith(_REVIEW_PREFIX):
        return None
    return situation.id[len(_REVIEW_PREFIX):] or None


def _schedule_review(world, plan_id, days=30):
    review_id = _review_id(plan_id)
    if world.agenda.get(review_id) is None:
        world.agenda.schedule(ScheduledSituation(review_id, REVIEW_KIND,
                                                 world.clock.absolute_day + days))


def _adoption_situation(world, actor, options):
    return {"you_are": actor.to_dict(), "occupied_settlements": [
        {"settlement_id": option.settlement_id, "report_event_id": option.report_event_id}
        for option in options], "strategic_capacity": provider_strategic_capacity(world, actor),
        "known_institutional_views": [
            {"subject_ref": subject.to_dict(), "reading": value, "evidence_event_ids": list(event_ids)}
            for subject, value, event_ids in institutional_views(world, actor)
        ],
        "today": world.clock.absolute_day}


GARRISON_SUPPLY_ACTION = "maintain_garrison_supply"


class GarrisonSupplyOption(SocietyValue):
    """Transient choice to sustain, or stop sustaining, one own standing duty."""
    id: Identity
    actor_ref: EntityRef
    garrison_id: Identity
    settlement_id: Identity
    stock_id: Identity
    kind: str = "adopt"

    def decision(self):
        return {"action": GARRISON_SUPPLY_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _garrison_objective_id(actor, garrison_id):
    return f"garrison-supply:{actor.kind}:{actor.id}:{garrison_id}"


def garrison_supply_blocker(world, actor, garrison, *, kind):
    """Every material term, recomposed identically by the owner."""
    if not isinstance(actor, EntityRef) or garrison is None or garrison.stage != "active":
        return "garrison"
    detachment = world.society.detachments.get(garrison.detachment_id)
    account = world.economy.accounts.get(garrison.account_id)
    settlement = world.society.settlements.get(garrison.settlement_id)
    need = world.economy.needs.get(garrison.settlement_id) if settlement is not None else None
    if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
            or detachment.location_id != garrison.settlement_id):
        return "column"
    if account is None or account.owner_ref != actor:
        return "account"
    if settlement is None or settlement.occupier_id != actor.id:
        return "occupation"
    if need is None or world.economy.stocks.get(need.stock_id) is None:
        return "stock"
    if not can_actor_act_for(world, actor, actor, "military"):
        return "authority"
    exists = _garrison_objective_id(actor, garrison.id) in world.strategy.objectives
    if exists == (kind == "adopt"):
        return "already_current"
    return None


def garrison_supply_options(world, actor):
    """Adopt or abandon the standing duty's ration reserve; nothing else."""
    if not isinstance(actor, EntityRef):
        return ()
    options = []
    for garrison in sorted(world.society.garrisons.values(), key=lambda item: item.id):
        for kind in ("adopt", "abandon"):
            if garrison_supply_blocker(world, actor, garrison, kind=kind) is not None:
                continue
            need = world.economy.needs[garrison.settlement_id]
            options.append(GarrisonSupplyOption(
                id=(f"garrison-supply-{kind}:{actor.kind}:{actor.id}:{garrison.id}:"
                    f"{garrison.last_event_id}"),
                actor_ref=actor, garrison_id=garrison.id, settlement_id=garrison.settlement_id,
                stock_id=need.stock_id, kind=kind))
    return tuple(options)


def execute_garrison_supply(world, actor, option_id, decision_event_id):
    """Recompose the duty and persist only the strategic priority."""
    option = next((item for item in garrison_supply_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("garrison supply option is stale or unknown")
    garrison = world.society.garrisons[option.garrison_id]
    objective_id = _garrison_objective_id(actor, garrison.id)
    if option.kind == "adopt":
        event = record_event(
            world, "garrison_supply_adopted",
            "A instituição assumiu sustentar as rações desta guarnição como objetivo permanente.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("strategy_objective", objective_id, "kind", None, GARRISON_SUPPLY_ACTION),),
            cause_ids=_causes(decision_event_id, garrison.last_event_id))
        world.strategy.objectives[objective_id] = Objective(
            id=objective_id, actor_ref=actor, settlement_id=option.settlement_id,
            stock_id=option.stock_id, resource_id="food", kind="maintain_garrison_supply",
            garrison_id=garrison.id,
            motivation="Sustentar o dever militar assumido sem tirar comida de quem não a tem.")
    else:
        event = record_event(
            world, "garrison_supply_abandoned",
            "A instituição deixou de reservar rações para esta guarnição; o dever segue por conta própria.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("strategy_objective", objective_id, "kind", GARRISON_SUPPLY_ACTION, None),),
            cause_ids=_causes(decision_event_id, garrison.last_event_id))
        world.strategy.objectives.pop(objective_id, None)
    world.strategy.validate(world)
    return event


def garrison_supply_adapters():
    return (DiscretionaryAdapter(
        name="garrison_supply", family="strategy", options_fn=garrison_supply_options,
        label_fn=lambda option: (
            f"Sustentar as rações da guarnição {option.garrison_id} como objetivo permanente."
            if option.kind == "adopt"
            else f"Deixar de reservar rações para a guarnição {option.garrison_id}."),
        causes_fn=lambda world, option: _causes(
            world.society.garrisons[option.garrison_id].last_event_id),
        execute_fn=execute_garrison_supply),)


def strategy_adoption_actors(world):
    return sorted({report.recipient_ref for report in world.knowledge.settlement_reports.values()
                   if report.recipient_ref.kind == "polity"}, key=lambda item: item.id)


def strategy_adoption_adapters(on_executed=None):
    """The family's adapters; ``on_executed`` only reports that an adoption
    actually persisted, for the standalone caller's boolean contract."""
    def _execute(world, actor, option_id, decision_event_id):
        adopt_occupied_settlement_defense(world, actor, option_id, decision_event_id)
        if on_executed is not None:
            on_executed()

    return (DiscretionaryAdapter(
        name="defense_adoption", family="strategy", options_fn=defense_adoption_options,
        label_fn=lambda option: "Adotar resposta defensiva ao assentamento ocupado observado.",
        causes_fn=lambda world, option: (option.report_event_id,), execute_fn=_execute,
        situation_fn=_adoption_situation),)


async def _review_adoptions(world):
    """Adoption is discretionary and monthly, so it runs through the shared
    InstitutionalDecisionTurn; the scheduled material turn below stays out of
    it, being both daily and a plan already in course."""
    changed = {"value": False}
    adapters = strategy_adoption_adapters(on_executed=lambda: changed.__setitem__("value", True))
    await review_institutional_decision_turn_with_provider(
        world, adapters, actors=_rotated(world, strategy_adoption_actors(world)),
        situation_fn=_adoption_situation)
    return changed["value"]


async def _review_material_turn(world, plan):
    objective = world.strategy.objectives[plan.objective_id]
    status, blocker = _plan_status(world, objective)
    if status is not None:
        changed = plan.stage != status or plan.blocker != blocker
        if changed:
            _set_plan(world, plan, status, blocker=blocker)
        if status == "blocked":
            _schedule_review(world, plan.id)
        return changed
    if not world.config.ai_enabled:
        _schedule_review(world, plan.id)
        return False
    options = defense_action_options(world, objective.actor_ref, plan.id)
    if not options:
        blocker = "nenhuma coluna pode ser erguida para o assentamento conhecido"
        recruitment = recruitment_capacity(world, objective.actor_ref, objective.settlement_id)
        source = recruitment[0] if recruitment else None
        changed = plan.stage != "blocked" or plan.blocker != blocker or source is not None
        if changed:
            report = world.knowledge.settlement_report(objective.actor_ref, objective.settlement_id)
            _set_plan(world, plan, "blocked", blocker=blocker,
                      causes=(report.event_id,), recruitment_source=source)
        _schedule_review(world, plan.id)
        return changed
    report = world.knowledge.settlement_report(objective.actor_ref, objective.settlement_id)
    selected = await ai_decider.select_option(
        world, objective.actor_ref,
        {"you_are": objective.actor_ref.to_dict(), "settlement_id": objective.settlement_id,
         "report_event_id": report.event_id, "today": world.clock.absolute_day},
        [{"id": item.id, "label": (f"Erguer {item.count} soldados com {item.provisions} rações "
                                 f"para até {item.days} dias e marchar ao assentamento conhecido.")}
         for item in options], causes=(plan.last_event_id, report.event_id))
    if selected in (None, ai_decider.NO_ACTION):
        _schedule_review(world, plan.id)
        return False
    option = next((item for item in options if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        )
    decision = record_event(world, "strategy_defense_force_decided",
                            "A instituição selecionou uma coluna material possível para responder à ocupação.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=_causes(plan.last_event_id, report.event_id))
    status, blocker = _plan_status(world, objective)
    if status is not None:
        _set_plan(world, plan, status, blocker=blocker, causes=(decision.id,))
        return True
    if not any(item.id == option.id for item in defense_action_options(world, objective.actor_ref, plan.id)):
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        )
    try:
        detachment = raise_detachment(world, objective.actor_ref, option.id, decision.id, days=option.days)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        ) from exc
    _set_plan(world, world.strategy.plans[plan.id], "mobilized", detachment_id=detachment.id,
              causes=(decision.id, detachment.last_event_id))
    _schedule_review(world, plan.id)
    return True


def _review_mobilized_plan(world, plan):
    """Observe the same objective after mobilization; never command a force."""
    objective = world.strategy.objectives[plan.objective_id]
    status, blocker = _plan_status(world, objective)
    detachment = world.society.detachments.get(plan.detachment_id)
    if status == "closed":
        _set_plan(world, plan, "closed", blocker=blocker,
                  causes=(world.knowledge.settlement_report(objective.actor_ref,
                                                              objective.settlement_id).event_id,))
        return True
    if status == "blocked":
        if plan.stage != "blocked" or plan.blocker != blocker:
            _set_plan(world, plan, "blocked", blocker=blocker,
                      detachment_id=plan.detachment_id,
                      causes=(detachment.last_event_id if detachment else None,))
        world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                                 world.clock.absolute_day + 30))
        return True
    if detachment is None or detachment.stage == "disbanded":
        _set_plan(world, plan, "adopted", blocker="coluna indisponível; reconsiderar meios",
                  causes=(detachment.last_event_id if detachment else None,))
        world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                                 world.clock.absolute_day + 1))
        return True
    if plan.stage == "blocked":
        _set_plan(world, plan, "mobilized", detachment_id=detachment.id,
                  causes=(detachment.last_event_id,))
    world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                             world.clock.absolute_day + 30))
    return True


async def review_strategy_responses_with_provider(world, situations=(), *, allow_adoptions=False):
    """A scheduled material turn is separate from adoption and never automatic."""
    changed = False
    for situation in sorted(situations, key=lambda item: item.id):
        plan_id = _review_plan_id(situation)
        plan = world.strategy.plans.get(plan_id) if plan_id is not None else None
        if plan is not None and plan.stage in {"adopted", "blocked"} and plan.detachment_id is None:
            changed |= await _review_material_turn(world, plan)
        elif plan is not None and plan.stage in {"mobilized", "blocked"} and plan.detachment_id is not None:
            changed |= _review_mobilized_plan(world, plan)
    if allow_adoptions:
        changed |= await _review_adoptions(world)
    return changed


__all__ = ["ADOPT_ACTION", "DefenseAdoptionOption", "REVIEW_KIND", "adopt_occupied_settlement_defense",
           "defense_action_options", "defense_adoption_options", "review_strategy_responses_with_provider"]
