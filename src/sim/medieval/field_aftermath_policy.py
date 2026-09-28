"""One private, optional force turn after a factual field-engagement outcome.

The result notice proves only that the recipient won at this settlement.  It
does not grant territory: every material choice below is recomposed and then
executed by the existing Society force owner.
"""

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.authority import headquarters_holder
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .events import record_event, record_no_action_decision
from .force import (DISBAND_ACTION, OCCUPY_ACTION, PREPARE_POSITION_ACTION, WITHDRAW_ACTION,
                    headquarters_withdrawal_options,
                    force_options, force_position_options, occupy_settlement,
                    disband_detachment, prepare_force_position, withdrawal_options, withdraw_detachment)
from .force import withdraw_detachment_by_headquarters
from .route_interdiction import (INTERDICT_ACTION, LIFT_ACTION, execute_route_interdiction_option,
                                 route_interdiction_options)
from .settlement_investment import (INVEST_ACTION, LIFT_ACTION as LIFT_INVESTMENT_ACTION,
                                    execute_settlement_investment_option, settlement_investment_options)
from .assembly_denial import (DENY_ACTION, LIFT_ACTION as LIFT_ASSEMBLY_DENIAL_ACTION,
                              assembly_denial_options, execute_assembly_denial_option)
from .sabotage import SABOTAGE_ACTION, execute_sabotage_option, sabotage_options
from .force_command import (APPOINT_ACTION as COMMAND_APPOINT_ACTION,
                            RELEASE_ACTION as COMMAND_RELEASE_ACTION,
                            SET_DOCTRINE_ACTION as COMMAND_DOCTRINE_ACTION,
                            detachment_command_options, execute_detachment_command_option)


REVIEW_KIND = "field_aftermath_review"
_PREFIX = "field-aftermath-review:"
HEADQUARTERS_REVIEW_KIND = "headquarters_field_response_review"
_HEADQUARTERS_PREFIX = "headquarters-field-response:"


def review_id(outcome_notice_id):
    return f"{_PREFIX}{outcome_notice_id}"


def schedule_field_aftermath_review(world, notice, day):
    """A factual result permits its side one later choice; time never acts."""
    identity = review_id(notice.id)
    if (notice.outcome in {"won", "lost"} and day > world.clock.absolute_day
            and world.agenda.get(identity) is None):
        world.agenda.schedule(ScheduledSituation(identity, REVIEW_KIND, day))


def _headquarters_review_id(report, engagement_id):
    return f"{_HEADQUARTERS_PREFIX}{report.event_id}::{engagement_id}"


def schedule_headquarters_field_response(world, report):
    """A delivered combat reading creates a later QG turn, never an instant order."""
    if (report.channel != "settlement_bulletin"
            or report.recipient_ref != headquarters_holder(world, report.publisher_ref)):
        return
    for reading in report.field_engagements:
        engagement = world.society.field_engagements.get(reading.engagement_id)
        if (engagement is None or engagement.status != "resolved"
                or report.publisher_ref not in {engagement.challenger_ref, engagement.defender_ref}
                or reading.winner_ref != engagement.winner_ref):
            continue
        identity = _headquarters_review_id(report, reading.engagement_id)
        if world.agenda.get(identity) is None:
            world.agenda.schedule(ScheduledSituation(
                identity, HEADQUARTERS_REVIEW_KIND, world.clock.absolute_day + 1))


def _notice_id(situation):
    if situation.kind != REVIEW_KIND or not situation.id.startswith(_PREFIX):
        return None
    identity = situation.id[len(_PREFIX):]
    return identity or None


def _engaged_detachment_ids(world, notice):
    engagement = world.society.field_engagements.get(notice.engagement_id)
    event = world.event_index().get(notice.event_id)
    if engagement is None or event is None:
        return (notice.own_detachment_id,)
    side = "challenger" if notice.recipient_ref == engagement.challenger_ref else "defender"
    prefix = f"{side}_column:"
    ids = tuple(sorted({delta.aspect[len(prefix):] for delta in event.deltas
                        if delta.owner_kind == "field_engagement" and delta.owner_id == engagement.id
                        and delta.aspect.startswith(prefix)}))
    return ids or (notice.own_detachment_id,)


def field_aftermath_options(world, actor, *, outcome_notice_id=None):
    """Transient consequences an actor may take with its own surviving force.

    The outcome notice is the only engagement fact consulted here.  Existing
    option providers add only the actor's own reports, authority and current
    detachment; no rival state is recomposed or disclosed.
    """
    options = []
    for notice in world.knowledge.field_engagement_outcome_notices.values():
        if (notice.recipient_ref != actor or notice.outcome not in {"won", "lost"}
                or (outcome_notice_id is not None and notice.id != outcome_notice_id)):
            continue
        for detachment_id in _engaged_detachment_ids(world, notice):
            detachment = world.society.detachments.get(detachment_id)
            if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
                    or detachment.location_id != notice.settlement_id):
                continue
            if notice.outcome == "lost":
                options.extend(option for option in force_options(world, actor)
                               if option.detachment_id == detachment.id and option.kind == "disband")
                options.extend(withdrawal_options(world, actor, detachment_id=detachment.id))
                options.extend(detachment_command_options(world, actor, detachment_id=detachment.id))
                continue
            options.extend(option for option in force_options(world, actor)
                           if option.detachment_id == detachment.id and option.kind == "occupy")
            options.extend(withdrawal_options(world, actor, detachment_id=detachment.id))
            options.extend(force_position_options(world, actor, detachment_id=detachment.id))
            options.extend(route_interdiction_options(world, actor, detachment_id=detachment.id))
            options.extend(settlement_investment_options(world, actor, detachment_id=detachment.id))
            options.extend(assembly_denial_options(world, actor, detachment_id=detachment.id))
            options.extend(detachment_command_options(world, actor, detachment_id=detachment.id))
            options.extend(sabotage_options(world, actor))
    return tuple(sorted(options, key=lambda item: item.id))


def _current_options(world, notice):
    return field_aftermath_options(world, notice.recipient_ref, outcome_notice_id=notice.id)


def _own_engaged_detachments(world, notice):
    """Current surviving own columns represented by this side's battle receipt."""
    return tuple(
        detachment
        for detachment_id in _engaged_detachment_ids(world, notice)
        if (detachment := world.society.detachments.get(detachment_id)) is not None
        and detachment.owner_ref == notice.recipient_ref
        and detachment.stage == "present"
        and detachment.location_id == notice.settlement_id
    )


def execute_field_aftermath_option(world, actor, outcome_notice_id, option_id, decision_event_id):
    """Delegate the selected current affordance to its canonical material owner."""
    notice = world.knowledge.field_engagement_outcome_notices.get(outcome_notice_id)
    if notice is None or notice.recipient_ref != actor or notice.outcome not in {"won", "lost"}:
        raise ValueError("field aftermath outcome is stale or unknown")
    option = next((item for item in _current_options(world, notice) if item.id == option_id), None)
    if option is None:
        raise ValueError("field aftermath option is stale or unknown")
    action = option.decision()["action"]
    if action == DISBAND_ACTION:
        return disband_detachment(world, actor, option.id, decision_event_id)
    if action == OCCUPY_ACTION:
        return occupy_settlement(world, actor, option.id, decision_event_id)
    if action == WITHDRAW_ACTION:
        return withdraw_detachment(world, actor, option.id, decision_event_id)
    if action == PREPARE_POSITION_ACTION:
        return prepare_force_position(world, actor, option.id, decision_event_id)
    if action in {INTERDICT_ACTION, LIFT_ACTION}:
        return execute_route_interdiction_option(world, actor, option.id, decision_event_id)
    if action in {INVEST_ACTION, LIFT_INVESTMENT_ACTION}:
        return execute_settlement_investment_option(world, actor, option.id, decision_event_id)
    if action in {DENY_ACTION, LIFT_ASSEMBLY_DENIAL_ACTION}:
        return execute_assembly_denial_option(world, actor, option.id, decision_event_id)
    if action == SABOTAGE_ACTION:
        return execute_sabotage_option(world, actor, option.id, decision_event_id)
    if action in {COMMAND_APPOINT_ACTION, COMMAND_DOCTRINE_ACTION, COMMAND_RELEASE_ACTION}:
        return execute_detachment_command_option(world, actor, option.id, decision_event_id)
    raise ValueError("field aftermath action is not available")


def _label(option):
    action = option.decision()["action"]
    detachment_id = getattr(option, "detachment_id", None)
    column = f"coluna {detachment_id}" if detachment_id is not None else "própria coluna"
    if action == DISBAND_ACTION:
        return f"Dissolver a {column} e devolver os sobreviventes à população de origem."
    if action == OCCUPY_ACTION:
        return f"Ocupar este assentamento com a {column} sobrevivente."
    if action == WITHDRAW_ACTION:
        return (f"Retirar a {column} para {option.destination_id} pela rota "
                f"{', '.join(option.route_ids)}.")
    if action == PREPARE_POSITION_ACTION:
        return f"Preparar a {column} no assentamento {option.settlement_id} por três dias."
    if action == INTERDICT_ACTION:
        return f"Interditar a rota {option.route_id} com a {column} preparada."
    if action == LIFT_ACTION:
        return f"Suspender a interdição da rota {option.route_id} mantida pela {column}."
    if action == INVEST_ACTION:
        return (f"Pressionar os acessos de {option.settlement_id} com a {column} preparada; "
                f"rotas: {', '.join(option.route_ids)}.")
    if action == LIFT_INVESTMENT_ACTION:
        return f"Suspender a pressão da {column} sobre os acessos de {option.settlement_id}."
    if action == DENY_ACTION:
        return (f"Negar a assembleia do rito {option.site_id} em {option.settlement_id} "
                f"com a {column} preparada.")
    if action == LIFT_ASSEMBLY_DENIAL_ACTION:
        return f"Permitir novamente a assembleia do rito {option.site_id} em {option.settlement_id}."
    if action == SABOTAGE_ACTION:
        return f"Danificar a instalação observada {option.site_id} com meios locais próprios."
    if action == COMMAND_APPOINT_ACTION:
        return f"Nomear {option.character_id} como comandante real da {column}."
    if action == COMMAND_DOCTRINE_ACTION:
        return f"Definir doutrina {option.doctrine} para a {column} a partir do próximo dia."
    if action == COMMAND_RELEASE_ACTION:
        return f"Liberar o comandante atual da {column}."
    return "Nenhuma ação disponível."


async def _aftermath_turn(world, outcome_notice_id):
    notice = world.knowledge.field_engagement_outcome_notices.get(outcome_notice_id)
    if notice is None or notice.outcome not in {"won", "lost"}:
        return False
    # Field aftermath is an optional provider-driven decision. Offline worlds
    # leave the review inert; provider mode must reach select_option so its
    # fail-closed ProviderDecisionRequired behavior remains authoritative.
    if not world.config.ai_enabled:
        return False
    options = _current_options(world, notice)
    if not options:
        return False
    situation = {
        "today": world.clock.absolute_day,
        "your_detachments": [
            {"id": item.id, "settlement_id": item.location_id,
             "count": item.count}
            for item in _own_engaged_detachments(world, notice)
        ],
        "field_outcome": {
            "settlement_id": notice.settlement_id,
            "counterparty_identity": notice.counterparty_ref.to_dict(),
            "anchor_detachment_id": notice.own_detachment_id,
            "outcome": notice.outcome,
            "own_casualties": notice.own_casualties,
            "own_prepared": notice.own_prepared,
            "own_supplied": notice.own_supplied,
        },
    }
    selected = await ai_decider.select_option(
        world, notice.recipient_ref, situation,
        [{"id": option.id, "label": _label(option)} for option in options],
        causes=(notice.event_id,),
    )
    if selected == ai_decider.NO_ACTION:
        record_no_action_decision(
            world, "field_aftermath_decided", "A instituição decidiu não alterar a postura da coluna neste turno.",
            notice.recipient_ref, affordance_ids=(option.id for option in options),
            cause_ids=(notice.event_id,),
        )
        return False
    if selected is None:
        return False
    option = next((item for item in _current_options(world, notice) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for {notice.recipient_ref.kind}:{notice.recipient_ref.id}: "
            "field aftermath affordance became stale"
        )
    decision = record_event(
        world, "field_aftermath_decided", "A instituição escolheu uma consequência possível para sua coluna após o combate.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), cause_ids=(notice.event_id,),
    )
    try:
        execute_field_aftermath_option(world, notice.recipient_ref, notice.id, option.id, decision.id)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for {notice.recipient_ref.kind}:{notice.recipient_ref.id}: "
            "field aftermath affordance became stale"
        ) from exc
    if _current_options(world, notice):
        schedule_field_aftermath_review(world, notice, world.clock.absolute_day + 1)
    return True


def _headquarters_report_for_situation(world, situation):
    if situation.kind != HEADQUARTERS_REVIEW_KIND or not situation.id.startswith(_HEADQUARTERS_PREFIX):
        return None, None
    report_event_id, separator, engagement_id = situation.id[len(_HEADQUARTERS_PREFIX):].rpartition("::")
    if not separator:
        return None, None
    headquarters = next((item.recipient_ref for item in world.knowledge.settlement_reports.values()
                         if item.event_id == report_event_id
                         and item.recipient_ref == headquarters_holder(world, item.publisher_ref)), None)
    if headquarters is None:
        return None, None
    report = next((item for item in world.knowledge.settlement_reports.values()
                   if item.event_id == report_event_id and item.channel == "settlement_bulletin"
                   and item.recipient_ref == headquarters), None)
    if report is None:
        return None, None
    reading = next((item for item in report.field_engagements if item.engagement_id == engagement_id), None)
    if reading is None:
        return None, None
    engagement = world.society.field_engagements.get(reading.engagement_id)
    if (engagement is None or engagement.status != "resolved"
            or report.publisher_ref not in {engagement.challenger_ref, engagement.defender_ref}
            or reading.winner_ref != engagement.winner_ref):
        return None, None
    return report, reading


async def _headquarters_field_response_turn(world, situation):
    report, reading = _headquarters_report_for_situation(world, situation)
    if report is None or reading is None or not world.config.ai_enabled:
        return False
    options = headquarters_withdrawal_options(world, report.publisher_ref, report)
    if not options:
        return False
    actor = report.recipient_ref
    selected = await ai_decider.select_option(
        world, actor,
        {"you_are": actor.to_dict(), "institution_ref": report.publisher_ref.to_dict(),
         "settlement_id": report.settlement_id, "report_event_id": report.event_id,
         "field_engagement": reading.model_dump(mode="json"), "today": world.clock.absolute_day},
        [{"id": item.id,
          "label": f"Retirar a coluna {item.detachment_id} para {item.destination_id} pela rota observada."}
         for item in options],
        causes=tuple(sorted({report.event_id, reading.event_id,
                             *(event_id for option in options for event_id in option.route_report_ids)})))
    if selected is None:
        return False
    if selected == ai_decider.NO_ACTION:
        record_event(
            world, "headquarters_field_response_decided",
            "O QG decidiu manter a campanha após avaliar o boletim de combate.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision={"action": "maintain", "actor_ref": actor.to_dict(),
                      "selected_affordance_id": "NO_ACTION"},
            cause_ids=(report.event_id, reading.event_id))
        return True
    option = next((item for item in headquarters_withdrawal_options(
        world, report.publisher_ref, report) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for {actor.kind}:{actor.id}: headquarters withdrawal became stale"
        )
    decision = record_event(
        world, "headquarters_field_response_decided",
        "O QG decidiu retirar a coluna após avaliar o resultado de combate recebido.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(),
        cause_ids=(report.event_id, reading.event_id, *option.route_report_ids))
    try:
        withdraw_detachment_by_headquarters(
            world, report.publisher_ref, report.event_id, option.id, decision.id)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for {actor.kind}:{actor.id}: headquarters withdrawal became stale"
        ) from exc
    return True


async def review_field_aftermaths(world, situations):
    """Review each outcome at most once: its dated agenda item is unique."""
    for situation in sorted(situations, key=lambda item: item.id):
        if situation.kind == HEADQUARTERS_REVIEW_KIND:
            await _headquarters_field_response_turn(world, situation)
            continue
        notice_id = _notice_id(situation)
        if notice_id is not None:
            await _aftermath_turn(world, notice_id)


__all__ = ["HEADQUARTERS_REVIEW_KIND", "REVIEW_KIND", "execute_field_aftermath_option", "field_aftermath_options",
           "review_field_aftermaths", "review_id", "schedule_field_aftermath_review"]
