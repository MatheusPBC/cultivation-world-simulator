"""One institutional response to a known occupied settlement.

Strategy keeps the intent and its factual source.  Force remains the only
owner of soldiers, food, wages, routes and movement; this module merely gives
an institution two bounded provider turns over options those owners already
enumerate.
"""

from copy import deepcopy
from dataclasses import dataclass
import json

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.authority import (can_actor_act_for, headquarters_holder,
                                              political_holder, require_authority)
from src.classes.governance.models import Objective, StrategicPlan
from src.classes.governance.knowledge import settlement_report_id
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity, SocietyValue
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .actor_dossier import provider_strategic_capacity
from .economy import _causes, _delta
from .events import record_event
from .force import (detachment_reroute_options, detachment_retreat_options, raise_detachment,
                    raise_options, recruitment_capacity, reroute_detachment, retreat_detachment,
                    campaign_logistics_withdrawal_options, withdraw_campaign_after_supply_delay)
from .force_command import (APPOINT_ACTION, detachment_command_options,
                            execute_detachment_command_option)
from .institutional_memory import institutional_views
from .institutional_decision_turn import (DiscretionaryAdapter, _rotated,
                                          review_institutional_decision_turn_with_provider)


ADOPT_ACTION = "adopt_occupied_settlement_defense"
REPORT_MAX_AGE_DAYS = 31
REVIEW_KIND = "strategy_response_review"
POLITICAL_RESULT_REVIEW_KIND = "strategy_political_result_review"
POLITICAL_MANDATE_SUSPENDED = "titular político suspendeu o mandato da campanha"
_REVIEW_PREFIX = "strategy-response-review:"
_POLITICAL_RESULT_PREFIX = "strategy-political-result-review:"
_STANDALONE_LOGISTICS_REVIEW_PREFIX = "campaign-logistics-review:"


@dataclass(frozen=True)
class DefenseAdoptionOption:
    id: str
    actor_ref: EntityRef
    settlement_id: str
    report_event_id: str

    def decision(self):
        return {"action": ADOPT_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class PoliticalCampaignReviewOption:
    id: str
    actor_ref: EntityRef
    institution_ref: EntityRef
    plan_id: str
    engagement_id: str
    report_event_id: str
    disposition: str

    def decision(self):
        return {"action": "review_defense_campaign", "actor_ref": self.actor_ref.to_dict(),
                "institution_ref": self.institution_ref.to_dict(), "operational_plan_id": self.plan_id,
                "engagement_id": self.engagement_id, "report_event_id": self.report_event_id,
                "disposition": self.disposition, "selected_affordance_id": self.id}


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
    if (decision.causal_origin is not CausalOrigin.ACTOR_DECISION
            or decided_by != actor or decision.decision != option.decision()):
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


def _office_briefing(world, objective, holder):
    """A named officer needs their own dated reading of the political target."""
    institution_report = world.knowledge.settlement_report(objective.actor_ref, objective.settlement_id)
    report = world.knowledge.settlement_report(holder, objective.settlement_id) if holder else None
    if (report is None or institution_report is None or report.recipient_ref != holder
            or report.observed_day != institution_report.observed_day
            or report.occupier_id != institution_report.occupier_id
            or not 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE_DAYS):
        return holder, None
    try:
        world.knowledge._validate_settlement_report(world, world.event_index(), report)
    except ValueError:
        return holder, None
    return holder, report


def _headquarters_briefing(world, objective):
    return _office_briefing(world, objective, headquarters_holder(world, objective.actor_ref))


def _political_briefing(world, objective):
    return _office_briefing(world, objective, political_holder(world, objective.actor_ref))


def _political_order(world, plan, objective):
    """Only the current principal's sourced order can reach HQ on a later day."""
    principal = political_holder(world, objective.actor_ref)
    institution_report = world.knowledge.settlement_report(objective.actor_ref, objective.settlement_id)
    if principal is None or institution_report is None:
        return None
    events = world.event_index()
    report_owner_id = settlement_report_id(principal, objective.settlement_id)
    for event in reversed(world.events_of_type("strategy_defense_political_ordered")):
        decision = event.decision or {}
        sources = {link.cause_event_id for link in event.causal_links}
        briefing_id = decision.get("report_event_id")
        receipt = events.get(briefing_id)
        supported_reading = (receipt is not None and receipt.event_type in {
            "settlement_observed", "settlement_report_received"}
            and any(delta.owner_kind == "settlement_report" and delta.owner_id == report_owner_id
                    and delta.aspect == "observation"
                    and json.loads(delta.after).get("occupier_id") == institution_report.occupier_id
                    for delta in receipt.deltas))
        expected = {
            "action": "authorize_defense_plan", "actor_ref": principal.to_dict(),
            "institution_ref": objective.actor_ref.to_dict(), "operational_plan_id": plan.id,
            "selected_affordance_id": f"strategy-defense-authorize:{plan.id}:{briefing_id}",
            "report_event_id": briefing_id,
            "observed_occupier_id": institution_report.occupier_id,
        }
        if (event.fact_kind == FactKind.DECISION and event.day < world.clock.absolute_day
                and decision == expected and supported_reading and briefing_id in sources
                and any((source := events.get(source_id)) is not None
                        and source.event_type in {"strategy_defense_adopted", "strategy_defense_plan_updated"}
                        and any(delta.owner_kind == "strategy_plan" and delta.owner_id == plan.id
                                for delta in source.deltas)
                        for source_id in sources)):
            return event
    return None


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


def _political_result_review_id(report, engagement_id):
    return f"{_POLITICAL_RESULT_PREFIX}{report.event_id}::{engagement_id}"


def _political_result_has_decision(world, plan_id, engagement_id):
    return any(item.decision and item.decision.get("operational_plan_id") == plan_id
               and item.decision.get("engagement_id") == engagement_id
               for item in world.events_of_type("strategy_defense_political_result_decided"))


def schedule_political_campaign_result_review(world, report):
    """A political holder reviews a campaign result only after receiving its bulletin."""
    principal = political_holder(world, report.publisher_ref)
    if (report.channel != "settlement_bulletin" or report.recipient_ref != principal
            or report.publisher_ref.kind != "polity"):
        return
    detachment_by_engagement = {}
    for reading in report.field_engagements:
        engagement = world.society.field_engagements.get(reading.engagement_id)
        if (engagement is None or engagement.status != "resolved"
                or report.publisher_ref not in {engagement.challenger_ref, engagement.defender_ref}
                or reading.event_id != engagement.last_event_id):
            continue
        detachment_by_engagement[reading.engagement_id] = (
            engagement.challenger_detachment_id if engagement.challenger_ref == report.publisher_ref
            else engagement.defender_detachment_id)
    active_detachments = {plan.detachment_id for plan in world.strategy.plans.values()
                          if (plan.stage == "mobilized"
                              or plan.stage == "blocked" and plan.blocker == POLITICAL_MANDATE_SUSPENDED)
                          and plan.detachment_id is not None
                          and world.strategy.objectives[plan.objective_id].actor_ref == report.publisher_ref
                          and world.strategy.objectives[plan.objective_id].kind == "defend_occupied_settlement"}
    for engagement_id, detachment_id in sorted(detachment_by_engagement.items()):
        if detachment_id not in active_detachments:
            continue
        if any(_political_result_has_decision(world, plan.id, engagement_id)
               for plan in world.strategy.plans.values() if plan.detachment_id == detachment_id):
            continue
        identity = _political_result_review_id(report, engagement_id)
        if world.agenda.get(identity) is None:
            world.agenda.schedule(ScheduledSituation(
                identity, POLITICAL_RESULT_REVIEW_KIND, world.clock.absolute_day + 1))


def political_campaign_review_options(world, report, *, engagement_id=None):
    """Offer maintain/suspend (or restore) for plans proven by the received battle report."""
    if (report is None or report.channel != "settlement_bulletin" or report.publisher_ref.kind != "polity"
            or report.recipient_ref != political_holder(world, report.publisher_ref)
            or not 0 <= world.clock.absolute_day - report.observed_day < REPORT_MAX_AGE_DAYS
            or not can_actor_act_for(world, report.recipient_ref, report.publisher_ref, "policy")):
        return ()
    try:
        world.knowledge._validate_settlement_report(world, world.event_index(), report)
    except ValueError:
        return ()
    events = world.event_index()
    options = []
    for reading in report.field_engagements:
        if engagement_id is not None and reading.engagement_id != engagement_id:
            continue
        engagement = world.society.field_engagements.get(reading.engagement_id)
        event = events.get(reading.event_id)
        if (engagement is None or event is None or engagement.status != "resolved"
                or report.publisher_ref not in {engagement.challenger_ref, engagement.defender_ref}
                or engagement.settlement_id != report.settlement_id
                or engagement.last_event_id != reading.event_id or event.event_type != "field_engagement_resolved"):
            continue
        detachment_id = (engagement.challenger_detachment_id if engagement.challenger_ref == report.publisher_ref
                         else engagement.defender_detachment_id)
        for plan in sorted(world.strategy.plans.values(), key=lambda item: item.id):
            objective = world.strategy.objectives.get(plan.objective_id)
            if (objective is None or objective.actor_ref != report.publisher_ref
                    or objective.kind != "defend_occupied_settlement" or plan.detachment_id != detachment_id
                    or plan.stage not in {"mobilized", "blocked"}
                    or (plan.stage == "blocked" and plan.blocker != POLITICAL_MANDATE_SUSPENDED)):
                continue
            if _political_result_has_decision(world, plan.id, engagement.id):
                continue
            dispositions = ("maintain", "suspend") if plan.stage == "mobilized" else ("maintain_suspension", "restore")
            for disposition in dispositions:
                identity = (f"strategy-political-result:{plan.id}:{engagement.id}:"
                            f"{report.event_id}:{disposition}")
                options.append(PoliticalCampaignReviewOption(
                    id=identity, actor_ref=report.recipient_ref, institution_ref=report.publisher_ref,
                    plan_id=plan.id, engagement_id=engagement.id, report_event_id=report.event_id,
                    disposition=disposition))
    return tuple(sorted(options, key=lambda item: item.id))


def _political_result_report_for_situation(world, situation):
    if (situation.kind != POLITICAL_RESULT_REVIEW_KIND
            or not situation.id.startswith(_POLITICAL_RESULT_PREFIX)):
        return None
    report_event_id, separator, engagement_id = situation.id[len(_POLITICAL_RESULT_PREFIX):].rpartition("::")
    if not separator:
        return None
    principal_report = next((item for item in world.knowledge.settlement_reports.values()
                             if item.event_id == report_event_id
                             and item.recipient_ref == political_holder(world, item.publisher_ref)), None)
    if principal_report is None or not any(item.engagement_id == engagement_id
                                           for item in principal_report.field_engagements):
        return None
    return principal_report


async def _review_political_campaign_result(world, situation):
    report = _political_result_report_for_situation(world, situation)
    engagement_id = situation.id.rpartition("::")[2]
    options = political_campaign_review_options(world, report, engagement_id=engagement_id)
    if report is None or not options or not world.config.ai_enabled:
        return False
    actor = report.recipient_ref
    reading = next(item for item in report.field_engagements
                   if situation.id.endswith(f"::{item.engagement_id}"))
    plans = sorted({item.plan_id for item in options})
    selected = await ai_decider.select_option(
        world, actor,
        {"you_are": actor.to_dict(), "institution_ref": report.publisher_ref.to_dict(),
         "report_event_id": report.event_id,
         "field_result": {"engagement_id": reading.engagement_id, "event_id": reading.event_id,
                          "settlement_id": report.settlement_id,
                          "outcome": ("draw" if reading.winner_ref is None else
                                      "won" if reading.winner_ref == report.publisher_ref else "lost"),
                          "winner_ref": reading.winner_ref.to_dict() if reading.winner_ref else None,
                          "own_casualties": (reading.challenger_casualties
                                              if reading.challenger_ref == report.publisher_ref
                                              else reading.defender_casualties),
                          "opponent_casualties": (reading.defender_casualties
                                                  if reading.challenger_ref == report.publisher_ref
                                                  else reading.challenger_casualties)},
         "campaign_plans": [{"plan_id": plan_id,
                             "stage": world.strategy.plans[plan_id].stage,
                             "blocker": world.strategy.plans[plan_id].blocker}
                            for plan_id in plans],
         "today": world.clock.absolute_day},
        [{"id": item.id, "label": {
            "maintain": f"Manter o mandato político do plano {item.plan_id}.",
            "suspend": f"Suspender o mandato político do plano {item.plan_id}; o QG ainda decide o destino da coluna.",
            "maintain_suspension": f"Manter suspenso o plano {item.plan_id}.",
            "restore": f"Restaurar o mandato político do plano {item.plan_id}."}[item.disposition]}
         for item in options], causes=(report.event_id, reading.event_id,
                                       *(world.strategy.plans[plan_id].last_event_id for plan_id in plans)))
    if selected is None:
        return False
    if selected == ai_decider.NO_ACTION:
        plan = world.strategy.plans[options[0].plan_id]
        record_event(
            world, "strategy_defense_political_result_decided",
            "O titular político decidiu não revisar o mandato da campanha neste turno.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "no_action", "actor_ref": actor.to_dict(),
                      "institution_ref": report.publisher_ref.to_dict(),
                      "operational_plan_id": plan.id, "engagement_id": engagement_id,
                      "report_event_id": report.event_id,
                      "selected_affordance_id": ai_decider.NO_ACTION},
            cause_ids=_causes(report.event_id, reading.event_id, plan.last_event_id))
        return True
    option = next((item for item in political_campaign_review_options(
        world, report, engagement_id=engagement_id) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired("political campaign result affordance became stale")
    decision = record_event(
        world, "strategy_defense_political_result_decided",
        "O titular político decidiu como manter o mandato da campanha após receber o resultado de combate.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(),
        cause_ids=_causes(report.event_id, reading.event_id, world.strategy.plans[option.plan_id].last_event_id))
    plan = world.strategy.plans[option.plan_id]
    if option.disposition == "suspend":
        _set_plan(world, plan, "blocked", blocker=POLITICAL_MANDATE_SUSPENDED,
                  causes=(decision.id, report.event_id), detachment_id=plan.detachment_id)
    elif option.disposition == "restore":
        _set_plan(world, plan, "mobilized", causes=(decision.id, report.event_id),
                  detachment_id=plan.detachment_id)
    world.strategy.validate(world)
    return True


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


def schedule_headquarters_route_review(world, report):
    """Bring forward an active plan review when HQ receives new route evidence.

    A monthly route bulletin is not an order to reroute. It only schedules the
    QG's next decision turn, where existing options are rebuilt from that
    holder's own current reports and the Force owner revalidates any choice.
    """
    if (report is None or report.channel != "route_bulletin"
            or report.recipient_ref.kind != "character"
            or world.knowledge.route_report(report.recipient_ref, report.route_id) != report):
        return ()
    events = world.event_index()
    due_day = world.clock.absolute_day + 1
    scheduled = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if (detachment.stage != "marching"
                or headquarters_holder(world, detachment.owner_ref) != report.recipient_ref
                or not 0 <= detachment.route_index < len(detachment.route_ids)
                or detachment.route_ids[detachment.route_index] != report.route_id):
            continue
        held = events.get(detachment.last_event_id)
        if held is None or held.event_type != "detachment_held":
            continue
        for plan in sorted(world.strategy.plans.values(), key=lambda item: item.id):
            if (plan.detachment_id != detachment.id or plan.stage not in {"mobilized", "blocked"}
                    or world.strategy.objectives.get(plan.objective_id) is None
                    or world.strategy.objectives[plan.objective_id].actor_ref != detachment.owner_ref):
                continue
            situation_id = _review_id(plan.id)
            pending = world.agenda.get(situation_id)
            if pending is not None and pending.due_day <= due_day:
                continue
            if pending is not None:
                world.agenda.cancel(situation_id)
            world.agenda.schedule(ScheduledSituation(situation_id, REVIEW_KIND, due_day))
            scheduled.append(situation_id)
    return tuple(scheduled)


def schedule_campaign_logistics_review(world, detachment_id):
    """Bring forward the QG turn after delayed campaign freight is resolved."""
    due_day = world.clock.absolute_day + 1
    scheduled = []
    for plan in sorted(world.strategy.plans.values(), key=lambda item: item.id):
        if (plan.detachment_id != detachment_id or plan.stage != "mobilized"
                or (detachment := world.society.detachments.get(detachment_id)) is None
                or detachment.stage != "present"):
            continue
        situation_id = _review_id(plan.id)
        pending = world.agenda.get(situation_id)
        if pending is not None and pending.due_day <= due_day:
            continue
        if pending is not None:
            world.agenda.cancel(situation_id)
        world.agenda.schedule(ScheduledSituation(situation_id, REVIEW_KIND, due_day))
        scheduled.append(situation_id)
    detachment = world.society.detachments.get(detachment_id)
    has_plan = any(plan.detachment_id == detachment_id for plan in world.strategy.plans.values())
    if detachment is not None and detachment.stage == "present" and not has_plan:
        situation_id = f"{_STANDALONE_LOGISTICS_REVIEW_PREFIX}{detachment_id}"
        pending = world.agenda.get(situation_id)
        if pending is None or pending.due_day > due_day:
            if pending is not None:
                world.agenda.cancel(situation_id)
            world.agenda.schedule(ScheduledSituation(situation_id, REVIEW_KIND, due_day))
            scheduled.append(situation_id)
    return tuple(scheduled)


async def _review_unplanned_campaign_logistics(world, detachment_id):
    """Give the QG a bounded response to delayed freight for a direct raise."""
    detachment = world.society.detachments.get(detachment_id)
    if detachment is None or detachment.stage != "present":
        return False
    institution_ref = detachment.owner_ref
    choices = campaign_logistics_withdrawal_options(
        world, institution_ref, detachment_id=detachment.id)
    headquarters = headquarters_holder(world, institution_ref)
    if headquarters is None or not can_actor_act_for(world, headquarters, institution_ref, "operations"):
        return False
    selection_causes = _causes(detachment.decision_event_id, detachment.last_event_id,
                               *(event_id for item in choices
                                 for event_id in (*item.delay_event_ids, *item.delay_notice_event_ids,
                                                  item.position_report_id, *item.route_report_ids)))
    if not choices:
        world.agenda.schedule(ScheduledSituation(
            f"{_STANDALONE_LOGISTICS_REVIEW_PREFIX}{detachment.id}", REVIEW_KIND,
            world.clock.absolute_day + 30))
        return False
    notices_by_option = {
        item.id: tuple(sorted(
            notice_id for notice_id in item.delay_notice_ids
            if (notice := world.knowledge.campaign_supply_notices.get(notice_id)) is not None
            and notice.state == "open"
        ))
        for item in choices
    }
    selected = await ai_decider.select_option(
        world, headquarters,
        {"you_are": headquarters.to_dict(), "serving_institution": institution_ref.to_dict(),
         "detachment_id": detachment.id,
         "reported_freight_delays": [
             {"notice_id": notice_id, "event_ids": list(item.delay_event_ids)}
             for item in choices for notice_id in item.delay_notice_ids],
         "withdrawal_routes": [{"affordance_id": item.id, "destination_id": item.destination_id,
                                 "route_ids": list(item.route_ids),
                                 "route_report_event_ids": list(item.route_report_ids),
                                 "lapsed_supply_notice_ids": list(notices_by_option[item.id])}
                                for item in choices],
         "today": world.clock.absolute_day},
        [{"id": item.id,
          "label": (f"Retornar a {item.destination_id} pela rota conhecida."
                    + (" Avisos abertos serão encerrados: " + ", ".join(notices_by_option[item.id]) + "."
                       if notices_by_option[item.id] else "")),
          "lapsed_supply_notice_ids": list(notices_by_option[item.id])}
         for item in choices],
        causes=selection_causes)
    if selected is None:
        world.agenda.schedule(ScheduledSituation(
            f"{_STANDALONE_LOGISTICS_REVIEW_PREFIX}{detachment.id}", REVIEW_KIND,
            world.clock.absolute_day + 30))
        return False
    if selected == ai_decider.NO_ACTION:
        record_event(
            world, "campaign_logistics_review_decided",
            "O QG decidiu manter a coluna após revisar o atraso material de abastecimento.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "no_action", "actor_ref": headquarters.to_dict(),
                      "selected_affordance_id": ai_decider.NO_ACTION,
                      "declined_option_ids": tuple(sorted(item.id for item in choices))},
            cause_ids=selection_causes)
        world.agenda.schedule(ScheduledSituation(
            f"{_STANDALONE_LOGISTICS_REVIEW_PREFIX}{detachment.id}", REVIEW_KIND,
            world.clock.absolute_day + 30))
        return True
    option = next((item for item in campaign_logistics_withdrawal_options(
        world, institution_ref, detachment_id=detachment.id) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired("standalone campaign withdrawal affordance became stale")
    decision = record_event(
        world, "campaign_logistics_review_decided",
        "O QG decidiu retirar a coluna após revisar o atraso material de abastecimento.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(),
        cause_ids=_causes(detachment.decision_event_id, detachment.last_event_id,
                          *option.delay_event_ids, *option.delay_notice_event_ids,
                          option.position_report_id, *option.route_report_ids))
    try:
        withdraw_campaign_after_supply_delay(
            world, institution_ref, None, option.id, decision.id, detachment_id=detachment.id)
    except ValueError as exc:
        raise ProviderDecisionRequired("standalone campaign withdrawal affordance became stale") from exc
    return True


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
    from .force import _decision

    decision, decided_by = _decision(world, decision_event_id, GARRISON_SUPPLY_ACTION)
    if (decision.causal_origin is not CausalOrigin.ACTOR_DECISION
            or decided_by != actor or decision.decision != option.decision()):
        raise ValueError("garrison supply has the wrong actor decision")
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
    order = _political_order(world, plan, objective)
    principal, political_briefing = _political_briefing(world, objective)
    if order is None and political_briefing is None:
        blocker = ("sem titular político atual" if principal is None
                   else "titular político não recebeu observação atual do assentamento")
        changed = plan.stage != "blocked" or plan.blocker != blocker
        if changed:
            _set_plan(world, plan, "blocked", blocker=blocker)
        _schedule_review(world, plan.id)
        return changed
    if order is None:
        option_id = f"strategy-defense-authorize:{plan.id}:{political_briefing.event_id}"
        selected = await ai_decider.select_option(
            world, principal,
            {"you_are": principal.to_dict(), "serving_institution": objective.actor_ref.to_dict(),
             "settlement_id": objective.settlement_id,
             "report_event_id": political_briefing.event_id, "today": world.clock.absolute_day},
            [{"id": option_id, "label": "Autorizar o QG a preparar uma resposta material à ocupação observada."}],
            causes=(plan.last_event_id, political_briefing.event_id))
        if selected is None:
            _schedule_review(world, plan.id)
            return False
        if (_political_briefing(world, objective) != (principal, political_briefing)
                or world.strategy.plans.get(plan.id) != plan
                or _plan_status(world, objective)[0] is not None
                or not defense_action_options(world, objective.actor_ref, plan.id)):
            raise ProviderDecisionRequired(
                f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
                "political authorization became stale"
            )
        if selected == ai_decider.NO_ACTION:
            record_event(world, "strategy_defense_political_declined",
                         "O titular político decidiu não autorizar a resposta defensiva agora.",
                         fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                         decision={"action": "no_action", "actor_ref": principal.to_dict(),
                                   "operational_plan_id": plan.id, "declined_option_ids": (option_id,),
                                   "selected_affordance_id": ai_decider.NO_ACTION},
                         cause_ids=_causes(plan.last_event_id, political_briefing.event_id))
            _schedule_review(world, plan.id)
            return False
        if selected != option_id:
            raise ProviderDecisionRequired(
                f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
                "political authorization became stale"
            )
        record_event(world, "strategy_defense_political_ordered",
                     "O titular político autorizou o QG a preparar a defesa observada.",
                     fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                     decision={"action": "authorize_defense_plan", "actor_ref": principal.to_dict(),
                               "institution_ref": objective.actor_ref.to_dict(),
                               "operational_plan_id": plan.id, "selected_affordance_id": option_id,
                               "report_event_id": political_briefing.event_id,
                               "observed_occupier_id": political_briefing.occupier_id},
                     cause_ids=_causes(plan.last_event_id, political_briefing.event_id))
        _schedule_review(world, plan.id, days=1)
        return True
    headquarters, briefing = _headquarters_briefing(world, objective)
    if briefing is None:
        blocker = ("sem titular atual do QG" if headquarters is None
                   else "QG não recebeu observação atual do assentamento")
        changed = plan.stage != "blocked" or plan.blocker != blocker
        if changed:
            _set_plan(world, plan, "blocked", blocker=blocker)
        _schedule_review(world, plan.id)
        return changed
    selected = await ai_decider.select_option(
        world, headquarters,
        {"you_are": headquarters.to_dict(), "serving_institution": objective.actor_ref.to_dict(),
         "settlement_id": objective.settlement_id, "report_event_id": briefing.event_id,
         "observed_occupier_id": briefing.occupier_id,
         "political_order": {
             "event_id": order.id,
             "issued_day": order.day,
             "issuer_ref": (order.decision or {}).get("actor_ref"),
             "authorized_action": "prepare_defense",
             "operational_plan_id": plan.id,
         },
         "today": world.clock.absolute_day},
        [{"id": item.id, "label": (f"Erguer {item.count} soldados com {item.provisions} rações "
                                 f"para até {item.days} dias e marchar ao assentamento conhecido.")}
         for item in options], causes=(plan.last_event_id, order.id, briefing.event_id))
    if selected == ai_decider.NO_ACTION:
        record_event(world, "strategy_defense_operational_declined",
                     "O titular do QG decidiu não mobilizar uma das colunas disponíveis.",
                     fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                     decision={"action": "no_action", "actor_ref": headquarters.to_dict(),
                               "operational_plan_id": plan.id,
                               "selected_affordance_id": ai_decider.NO_ACTION,
                               "declined_option_ids": tuple(sorted(item.id for item in options))},
                     cause_ids=_causes(plan.last_event_id, order.id, briefing.event_id))
        _schedule_review(world, plan.id)
        return False
    if selected is None:
        _schedule_review(world, plan.id)
        return False
    option = next((item for item in options if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        )
    decision = record_event(
        world, "strategy_defense_force_decided",
        "O titular do QG escolheu uma coluna material possível para responder à ocupação.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision={"action": "raise_detachment", "actor_ref": headquarters.to_dict(),
                  "institution_ref": objective.actor_ref.to_dict(), "operational_plan_id": plan.id,
                  "selected_affordance_id": option.id},
        cause_ids=_causes(plan.last_event_id, order.id, briefing.event_id))
    status, blocker = _plan_status(world, objective)
    if status is not None:
        _set_plan(world, plan, status, blocker=blocker, causes=(decision.id,))
        return True
    if (_headquarters_briefing(world, objective) != (headquarters, briefing)
            or not any(item.id == option.id for item in defense_action_options(
                world, objective.actor_ref, plan.id))):
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        )
    try:
        detachment = raise_detachment(world, objective.actor_ref, option.id, decision.id,
                                      days=option.days, operational_plan_id=plan.id)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
            "strategy affordance became stale"
        ) from exc
    _set_plan(world, world.strategy.plans[plan.id], "mobilized", detachment_id=detachment.id,
              causes=(decision.id, detachment.last_event_id))
    appointments = tuple(item for item in detachment_command_options(
        world, objective.actor_ref, detachment_id=detachment.id)
        if item.decision()["action"] == APPOINT_ACTION)
    if appointments:
        command_causes = _causes(decision.id, detachment.last_event_id, briefing.event_id)
        chosen = await ai_decider.select_option(
            world, objective.actor_ref,
            {"headquarters_holder": headquarters.to_dict(),
             "serving_institution": objective.actor_ref.to_dict(),
             "detachment_id": detachment.id, "today": world.clock.absolute_day},
            [{"id": item.id, "label": f"Nomear {item.character_id} para comandar a coluna."}
             for item in appointments], causes=command_causes)
        if chosen == ai_decider.NO_ACTION:
            record_event(
                world, "strategy_defense_command_declined",
                "O QG decidiu não nomear comandante para a coluna neste turno.",
                fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                decision={"action": "no_action", "actor_ref": objective.actor_ref.to_dict(),
                          "headquarters_holder": headquarters.to_dict(),
                          "selected_affordance_id": ai_decider.NO_ACTION,
                          "declined_option_ids": tuple(item.id for item in appointments)},
                cause_ids=command_causes)
        elif chosen is not None:
            appointment = next((item for item in detachment_command_options(
                world, objective.actor_ref, detachment_id=detachment.id)
                if item.id == chosen and item.decision()["action"] == APPOINT_ACTION), None)
            if appointment is None:
                raise ProviderDecisionRequired("detachment command appointment became stale")
            command_decision = record_event(
                world, "strategy_defense_command_decided",
                "O QG escolheu um comandante elegível para a coluna.",
                fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                decision=appointment.decision(), cause_ids=command_causes)
            try:
                execute_detachment_command_option(
                    world, objective.actor_ref, appointment.id, command_decision.id)
            except ValueError as exc:
                raise ProviderDecisionRequired("detachment command appointment became stale") from exc
    _schedule_review(world, plan.id)
    return True


async def _review_mobilized_plan(world, plan):
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
        if (plan.stage != "blocked" or plan.blocker != blocker) and not (
                plan.stage == "blocked" and plan.blocker == POLITICAL_MANDATE_SUSPENDED):
            _set_plan(world, plan, "blocked", blocker=blocker,
                      detachment_id=plan.detachment_id,
                      causes=(detachment.last_event_id if detachment else None,))
        world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                                 world.clock.absolute_day + 30))
        return True
    if detachment is None or detachment.stage == "disbanded":
        if plan.stage == "blocked" and plan.blocker == POLITICAL_MANDATE_SUSPENDED:
            _schedule_review(world, plan.id)
            return False
        _set_plan(world, plan, "adopted", blocker="coluna indisponível; reconsiderar meios",
                  causes=(detachment.last_event_id if detachment else None,))
        world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                                 world.clock.absolute_day + 1))
        return True
    if world.config.ai_enabled and detachment.stage == "marching":
        reroutes = (() if plan.stage == "blocked" and plan.blocker == POLITICAL_MANDATE_SUSPENDED
                    else detachment_reroute_options(world, objective.actor_ref, plan.id))
        retreats = detachment_retreat_options(world, objective.actor_ref, plan.id)
        choices = (*reroutes, *retreats)
        if choices:
            headquarters = choices[0].actor_ref
            labels = {item.id: "Reencaminhar a coluna pela rota alternativa observada."
                      for item in reroutes}
            labels.update({item.id: f"Encerrar a missão e retornar a {item.destination_id} pela rota observada."
                           for item in retreats})
            selected = await ai_decider.select_option(
                world, headquarters,
                {"you_are": headquarters.to_dict(),
                 "serving_institution": objective.actor_ref.to_dict(),
                 "operational_plan_id": plan.id,
                 "detachment_id": detachment.id,
                 "blocked_route_id": choices[0].blocked_route_id,
                 "blocked_report_event_id": choices[0].blocked_report_id,
                 "alternative_routes": [{"affordance_id": item.id,
                                          "route_ids": list(item.route_ids),
                                          "route_report_event_ids": list(item.route_report_ids)}
                                         for item in reroutes],
                 "retreat_routes": [{"affordance_id": item.id, "destination_id": item.destination_id,
                                     "route_ids": list(item.route_ids),
                                     "route_report_event_ids": list(item.route_report_ids)}
                                    for item in retreats],
                 "today": world.clock.absolute_day},
                [{"id": item.id, "label": labels[item.id]} for item in choices],
                causes=_causes(plan.last_event_id, detachment.last_event_id,
                               *(item.blocked_report_id for item in choices),
                               *(event_id for item in choices for event_id in item.route_report_ids)))
            if selected == ai_decider.NO_ACTION:
                record_event(
                    world, "strategy_defense_reroute_declined",
                    "O QG decidiu aguardar em vez de reencaminhar ou retirar a coluna.",
                    fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                    decision={"action": "no_action", "actor_ref": headquarters.to_dict(),
                              "operational_plan_id": plan.id,
                              "selected_affordance_id": ai_decider.NO_ACTION,
                              "declined_option_ids": tuple(sorted(item.id for item in choices))},
                    cause_ids=_causes(plan.last_event_id, detachment.last_event_id,
                                      *(item.blocked_report_id for item in choices)))
            elif selected is not None:
                reroute = next((item for item in detachment_reroute_options(
                    world, objective.actor_ref, plan.id) if item.id == selected), None)
                retreat = next((item for item in detachment_retreat_options(
                    world, objective.actor_ref, plan.id) if item.id == selected), None)
                option = reroute or retreat
                if option is None:
                    raise ProviderDecisionRequired(
                        f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
                        "detachment movement affordance became stale"
                    )
                event_type = "strategy_defense_reroute_decided" if reroute else "strategy_defense_retreat_decided"
                content = ("O QG escolheu a rota alternativa entre as leituras atuais da instituição."
                           if reroute else "O QG decidiu encerrar a missão e retirar a coluna por rota conhecida.")
                decision = record_event(world, event_type, content, fact_kind=FactKind.DECISION,
                                        causal_origin=CausalOrigin.ACTOR_DECISION,
                                        decision=option.decision(),
                                        cause_ids=_causes(plan.last_event_id, detachment.last_event_id,
                                                          option.blocked_report_id, *option.route_report_ids))
                if reroute:
                    reroute_detachment(world, objective.actor_ref, plan.id, option.id, decision.id)
                    _schedule_review(world, plan.id)
                else:
                    movement = retreat_detachment(world, objective.actor_ref, plan.id, option.id, decision.id)
                    current = world.strategy.plans[plan.id]
                    _set_plan(world, current, "withdrawn", blocker="missão encerrada; coluna em retorno",
                              detachment_id=detachment.id, causes=(decision.id, movement.id))
                return True
            if selected is None:
                _schedule_review(world, plan.id)
                return False
    if world.config.ai_enabled and detachment.stage == "present":
        choices = campaign_logistics_withdrawal_options(world, objective.actor_ref, plan.id)
        if choices:
            headquarters = choices[0].actor_ref
            lapsed_notices_by_option = {
                item.id: tuple(sorted(
                    notice_id for notice_id in item.delay_notice_ids
                    if (notice := world.knowledge.campaign_supply_notices.get(notice_id)) is not None
                    and notice.state == "open"
                ))
                for item in choices
            }
            selection_causes = _causes(plan.last_event_id, detachment.last_event_id,
                                       *(event_id for item in choices
                                         for event_id in (*item.delay_event_ids, *item.delay_notice_event_ids,
                                                          item.position_report_id, *item.route_report_ids)))
            selected = await ai_decider.select_option(
                world, headquarters,
                {"you_are": headquarters.to_dict(),
                 "serving_institution": objective.actor_ref.to_dict(),
                 "operational_plan_id": plan.id, "detachment_id": detachment.id,
                "reported_freight_delays": [
                     {"notice_id": notice_id, "event_ids": list(item.delay_event_ids)}
                     for item in choices for notice_id in item.delay_notice_ids],
                 "withdrawal_routes": [{"affordance_id": item.id,
                                         "destination_id": item.destination_id,
                                         "route_ids": list(item.route_ids),
                                         "route_report_event_ids": list(item.route_report_ids),
                                         "lapsed_supply_notice_ids": list(lapsed_notices_by_option[item.id])}
                                        for item in choices],
                 "today": world.clock.absolute_day},
                [{"id": item.id,
                  "label": (
                      f"Encerrar a campanha e retornar a {item.destination_id} pela rota conhecida."
                      + (" Avisos abertos de suprimento serão encerrados: "
                         + ", ".join(lapsed_notices_by_option[item.id]) + "."
                         if lapsed_notices_by_option[item.id] else "")
                  ),
                  "lapsed_supply_notice_ids": list(lapsed_notices_by_option[item.id])}
                 for item in choices],
                causes=selection_causes)
            if selected == ai_decider.NO_ACTION:
                record_event(
                    world, "strategy_defense_logistics_review_decided",
                    "O QG decidiu manter a coluna no local após revisar o atraso de abastecimento resolvido.",
                    fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                    decision={"action": "no_action", "actor_ref": headquarters.to_dict(),
                              "operational_plan_id": plan.id,
                              "selected_affordance_id": ai_decider.NO_ACTION,
                              "declined_option_ids": tuple(sorted(item.id for item in choices))},
                    cause_ids=selection_causes)
            elif selected is not None:
                option = next((item for item in campaign_logistics_withdrawal_options(
                    world, objective.actor_ref, plan.id) if item.id == selected), None)
                if option is None:
                    raise ProviderDecisionRequired(
                        f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
                        "campaign logistics withdrawal affordance became stale"
                    )
                decision = record_event(
                    world, "strategy_defense_logistics_review_decided",
                    "O QG decidiu encerrar a campanha após revisar o atraso material de abastecimento.",
                    fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                    decision=option.decision(),
                    cause_ids=_causes(plan.last_event_id, detachment.last_event_id,
                                      *option.delay_event_ids, *option.delay_notice_event_ids,
                                      option.position_report_id, *option.route_report_ids))
                try:
                    withdraw_campaign_after_supply_delay(
                        world, objective.actor_ref, plan.id, option.id, decision.id)
                except ValueError as exc:
                    raise ProviderDecisionRequired(
                        f"provider decision required for {objective.actor_ref.kind}:{objective.actor_ref.id}: "
                        "campaign logistics withdrawal affordance became stale"
                    ) from exc
                return True
            else:
                _schedule_review(world, plan.id)
                return False
    if plan.stage == "blocked" and plan.blocker != POLITICAL_MANDATE_SUSPENDED:
        _set_plan(world, plan, "mobilized", detachment_id=detachment.id,
                  causes=(detachment.last_event_id,))
    world.agenda.schedule(ScheduledSituation(_review_id(plan.id), REVIEW_KIND,
                                             world.clock.absolute_day + 30))
    return True


async def review_strategy_responses_with_provider(world, situations=(), *, allow_adoptions=False):
    """A scheduled material turn is separate from adoption and never automatic."""
    changed = False
    for situation in sorted(situations, key=lambda item: item.id):
        if (situation.kind == REVIEW_KIND
                and situation.id.startswith(_STANDALONE_LOGISTICS_REVIEW_PREFIX)):
            if world.config.ai_enabled:
                detachment_id = situation.id[len(_STANDALONE_LOGISTICS_REVIEW_PREFIX):]
                changed |= await _review_unplanned_campaign_logistics(world, detachment_id)
            continue
        if situation.kind == POLITICAL_RESULT_REVIEW_KIND:
            changed |= await _review_political_campaign_result(world, situation)
            continue
        plan_id = _review_plan_id(situation)
        plan = world.strategy.plans.get(plan_id) if plan_id is not None else None
        if plan is not None and plan.stage in {"adopted", "blocked"} and plan.detachment_id is None:
            changed |= await _review_material_turn(world, plan)
        elif plan is not None and plan.stage in {"mobilized", "blocked"} and plan.detachment_id is not None:
            changed |= await _review_mobilized_plan(world, plan)
    if allow_adoptions:
        changed |= await _review_adoptions(world)
    return changed


__all__ = ["ADOPT_ACTION", "DefenseAdoptionOption", "POLITICAL_RESULT_REVIEW_KIND", "REVIEW_KIND",
           "adopt_occupied_settlement_defense", "defense_action_options", "defense_adoption_options",
           "political_campaign_review_options", "review_strategy_responses_with_provider",
           "schedule_campaign_logistics_review", "schedule_headquarters_route_review",
           "schedule_political_campaign_result_review"]
