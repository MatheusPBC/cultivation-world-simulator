"""One private, optional force turn after a factual field-engagement outcome.

The result notice proves only that the recipient won at this settlement.  It
does not grant territory: every material choice below is recomposed and then
executed by the existing Society force owner.
"""

from src.classes.event import FactKind
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .events import record_event
from .force import (OCCUPY_ACTION, PREPARE_POSITION_ACTION, WITHDRAW_ACTION,
                    force_options, force_position_options, occupy_settlement,
                    prepare_force_position, withdrawal_options, withdraw_detachment)
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


def review_id(outcome_notice_id):
    return f"{_PREFIX}{outcome_notice_id}"


def schedule_field_aftermath_review(world, notice, day):
    """A victory permits one later choice; the calendar never makes it act."""
    identity = review_id(notice.id)
    if (notice.outcome == "won" and day > world.clock.absolute_day
            and world.agenda.get(identity) is None):
        world.agenda.schedule(ScheduledSituation(identity, REVIEW_KIND, day))


def _notice_id(situation):
    if situation.kind != REVIEW_KIND or not situation.id.startswith(_PREFIX):
        return None
    identity = situation.id[len(_PREFIX):]
    return identity or None


def _turn_available(world):
    # Calling select_option while unavailable would write a failed receipt.
    # An unavailable provider is deliberately not a decision in this vertical.
    return ai_decider.provider_available() and ai_decider.within_budget(world)


def field_aftermath_options(world, actor, *, outcome_notice_id=None):
    """Transient consequences a winner can take with its own surviving column.

    The outcome notice is the only engagement fact consulted here.  Existing
    option providers add only the actor's own reports, authority and current
    detachment; no rival state is recomposed or disclosed.
    """
    options = []
    for notice in world.knowledge.field_engagement_outcome_notices.values():
        if (notice.recipient_ref != actor or notice.outcome != "won"
                or (outcome_notice_id is not None and notice.id != outcome_notice_id)):
            continue
        detachment = world.society.detachments.get(notice.own_detachment_id)
        if (detachment is None or detachment.owner_ref != actor or detachment.stage != "present"
                or detachment.location_id != notice.settlement_id):
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


def execute_field_aftermath_option(world, actor, outcome_notice_id, option_id, decision_event_id):
    """Delegate the selected current affordance to its canonical material owner."""
    notice = world.knowledge.field_engagement_outcome_notices.get(outcome_notice_id)
    if notice is None or notice.recipient_ref != actor or notice.outcome != "won":
        raise ValueError("field aftermath outcome is stale or unknown")
    option = next((item for item in _current_options(world, notice) if item.id == option_id), None)
    if option is None:
        raise ValueError("field aftermath option is stale or unknown")
    action = option.decision()["action"]
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
    if action == OCCUPY_ACTION:
        return "Ocupar este assentamento com a própria coluna sobrevivente."
    if action == WITHDRAW_ACTION:
        return "Retirar a própria coluna até uma administração conhecida."
    if action == PREPARE_POSITION_ACTION:
        return "Preparar uma posição no assentamento atual por três dias."
    if action == INTERDICT_ACTION:
        return f"Interditar a rota local {option.route_id} com a própria coluna preparada."
    if action == LIFT_ACTION:
        return f"Suspender a própria interdição de rota local {option.route_id}."
    if action == INVEST_ACTION:
        return "Pressionar todos os acessos operacionais deste assentamento com a própria coluna preparada."
    if action == LIFT_INVESTMENT_ACTION:
        return "Suspender a própria pressão sobre todos os acessos do assentamento."
    if action == DENY_ACTION:
        return "Negar a assembleia do rito local observado com a própria coluna preparada."
    if action == LIFT_ASSEMBLY_DENIAL_ACTION:
        return "Permitir novamente a assembleia do rito local."
    if action == SABOTAGE_ACTION:
        return "Danificar uma instalação estrangeira já observada com meios locais próprios."
    if action == COMMAND_APPOINT_ACTION:
        return f"Nomear {option.character_id} como comandante real desta coluna."
    if action == COMMAND_DOCTRINE_ACTION:
        return f"Definir doutrina {option.doctrine} para vigorar no próximo dia."
    if action == COMMAND_RELEASE_ACTION:
        return "Liberar o comandante atual da própria coluna."
    return "Nenhuma ação disponível."


async def _aftermath_turn(world, outcome_notice_id):
    notice = world.knowledge.field_engagement_outcome_notices.get(outcome_notice_id)
    if notice is None or notice.outcome != "won" or not _turn_available(world):
        return False
    options = _current_options(world, notice)
    if not options:
        return False
    detachment = world.society.detachments.get(notice.own_detachment_id)
    if detachment is None:
        return False
    situation = {
        "today": world.clock.absolute_day,
        "your_detachment": {
            "id": detachment.id,
            "settlement_id": detachment.location_id,
            "count": detachment.count,
        },
        "field_outcome": {
            "settlement_id": notice.settlement_id,
            "counterparty_identity": notice.counterparty_ref.to_dict(),
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
    if selected in (None, ai_decider.NO_ACTION):
        return False
    option = next((item for item in _current_options(world, notice) if item.id == selected), None)
    if option is None:
        return False
    decision = record_event(
        world, "field_aftermath_decided", "O vencedor escolheu uma consequência possível após o combate de campo.",
        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(notice.event_id,),
    )
    try:
        execute_field_aftermath_option(world, notice.recipient_ref, notice.id, option.id, decision.id)
    except ValueError:
        # A material owner rejected a stale situation. The decision itself is
        # still an auditable fact; it never creates an implicit fallback.
        return False
    return True


async def review_field_aftermaths(world, situations):
    """Review each outcome at most once: its dated agenda item is unique."""
    for situation in sorted(situations, key=lambda item: item.id):
        notice_id = _notice_id(situation)
        if notice_id is not None:
            await _aftermath_turn(world, notice_id)


__all__ = ["REVIEW_KIND", "execute_field_aftermath_option", "field_aftermath_options",
           "review_field_aftermaths", "review_id", "schedule_field_aftermath_review"]
