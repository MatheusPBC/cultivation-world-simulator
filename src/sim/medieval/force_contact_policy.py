"""One bounded provider turn after a force physically recognizes a rival.

Contact creates knowledge, not an automatic campaign. The only material option
is to stand down one's own detachment through the existing Society owner.
"""

from src.classes.event import FactKind
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .events import record_event
from .force import (STAND_DOWN_ACTION, WITHDRAW_ACTION, stand_down_from_standoff,
                    standoff_options, withdraw_detachment, withdrawal_options,
                    PREPARE_POSITION_ACTION, force_position_options, prepare_force_position,
                    GARRISON_ACTION, WITHDRAW_GARRISON_ACTION, ROTATE_GARRISON_ACTION, garrison_options,
                    establish_garrison, withdraw_garrison, rotate_garrison)
from .force_deescalation import (FULFILL_ACTION, OFFER_ACTION, RESPONSE_ACTION,
                                 force_deescalation_offer_options,
                                 force_deescalation_response_options,
                                 force_withdrawal_fulfillment_options,
                                 fulfill_force_withdrawal, offer_force_deescalation,
                                 respond_force_deescalation)
from .administration_concession import (
    FULFILL_ACTION as ADMINISTRATION_TRANSFER_FULFILL_ACTION,
    OFFER_ACTION as ADMINISTRATION_CONCESSION_OFFER_ACTION,
    RESPONSE_ACTION as ADMINISTRATION_CONCESSION_RESPONSE_ACTION,
    administration_concession_offer_options, administration_concession_response_options,
    administration_transfer_fulfillment_options, fulfill_administration_transfer,
    offer_administration_concession, respond_administration_concession)
from .siege_campaign import (OCCUPY_AFTER_BREACH_ACTION, occupy_after_siege_breach,
                              siege_occupation_options)
from .territorial_control import (CONTROL_ACTION, WITHDRAW_CONTROL_ACTION,
                                  establish_territorial_control, territorial_control_options,
                                  withdraw_territorial_control)
from .field_engagement import (JOIN_ACTION, OFFER_ACTION as FIELD_ENGAGEMENT_OFFER_ACTION,
                               field_engagement_join_options, field_engagement_offer_options,
                               join_field_engagement, offer_field_engagement)
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


REVIEW_KIND = "force_contact_review"
_PREFIX = "force-contact-review:"
SIGHTING_MAX_AGE_DAYS = 3


def review_id(notice_id):
    return f"{_PREFIX}{notice_id}"


def schedule_contact_review(world, notice, day):
    """A future turn is not a command to act, even when no provider exists."""
    identity = review_id(notice.id)
    if day > world.clock.absolute_day and world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity, REVIEW_KIND, day))


def _notice_id(situation):
    if situation.kind != REVIEW_KIND or not situation.id.startswith(_PREFIX):
        return None
    identity = situation.id[len(_PREFIX):]
    return identity or None


def _turn_available(world):
    # select_option records a failed receipt if called unavailable. This V1
    # deliberately grants no receipt and no fallback action in that case.
    return ai_decider.provider_available() and ai_decider.within_budget(world)


def contact_sighting_for_provider(world, notice):
    """A frozen historical notice never becomes a current rival reading."""
    standoff = world.society.force_standoffs.get(notice.standoff_id)
    if (standoff is None or standoff.stage != "active"
            or world.clock.absolute_day - notice.learned_day >= SIGHTING_MAX_AGE_DAYS):
        return {"counterparty_strength_band": None, "counterparty_posture": None}
    return {"counterparty_strength_band": notice.counterparty_strength_band,
            "counterparty_posture": notice.counterparty_posture}


async def _contact_turn(world, notice_id):
    notice = world.knowledge.force_contact_notices.get(notice_id)
    if notice is None or not _turn_available(world):
        return False
    # A received offer must be answered independently before this actor opens
    # another one.  An accepted own promise similarly gets a later, separate
    # material turn.  Neither path is forced by the calendar.
    response = force_deescalation_response_options(world, notice.recipient_ref, notice_id=notice.id)
    concession_response = administration_concession_response_options(world, notice.recipient_ref, notice_id=notice.id)
    fulfill = force_withdrawal_fulfillment_options(world, notice.recipient_ref, notice_id=notice.id)
    administration_fulfill = administration_transfer_fulfillment_options(world, notice.recipient_ref)
    engagement_join = field_engagement_join_options(world, notice.recipient_ref, notice_id=notice.id)
    if response or concession_response:
        options = (*response, *concession_response)
    elif engagement_join:
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id
                           and option.detachment_id == notice.own_detachment_id)
        withdraw = withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id)
        options = (*engagement_join, *stand_down, *withdraw,
                   *route_interdiction_options(world, notice.recipient_ref,
                                               detachment_id=notice.own_detachment_id),
                   *settlement_investment_options(world, notice.recipient_ref,
                                                   detachment_id=notice.own_detachment_id),
                   *assembly_denial_options(world, notice.recipient_ref,
                                             detachment_id=notice.own_detachment_id),
                   *detachment_command_options(world, notice.recipient_ref,
                                                detachment_id=notice.own_detachment_id),
                   *sabotage_options(world, notice.recipient_ref))
    elif administration_fulfill or fulfill:
        options = (*administration_fulfill, *fulfill)
    else:
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id
                           and option.detachment_id == notice.own_detachment_id)
        withdraw = withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id)
        offers = force_deescalation_offer_options(world, notice.recipient_ref, notice_id=notice.id)
        concessions = administration_concession_offer_options(world, notice.recipient_ref, notice_id=notice.id)
        siege_occupations = tuple(option for option in siege_occupation_options(world, notice.recipient_ref)
                                  if option.settlement_id == notice.settlement_id)
        controls = tuple(option for option in territorial_control_options(world, notice.recipient_ref)
                         if option.settlement_id == notice.settlement_id)
        garrisons = tuple(option for option in garrison_options(world, notice.recipient_ref)
                           if option.settlement_id == notice.settlement_id)
        positions = force_position_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id)
        engagements = field_engagement_offer_options(world, notice.recipient_ref, notice_id=notice.id)
        interdictions = route_interdiction_options(world, notice.recipient_ref,
                                                    detachment_id=notice.own_detachment_id)
        investments = settlement_investment_options(world, notice.recipient_ref,
                                                     detachment_id=notice.own_detachment_id)
        denials = assembly_denial_options(world, notice.recipient_ref,
                                          detachment_id=notice.own_detachment_id)
        commands = detachment_command_options(world, notice.recipient_ref,
                                               detachment_id=notice.own_detachment_id)
        options = (*stand_down, *withdraw, *offers, *concessions, *siege_occupations, *controls, *garrisons, *positions, *engagements, *interdictions, *investments, *denials,
                   *commands,
                   *sabotage_options(world, notice.recipient_ref))
    if not options:
        return False
    detachment = world.society.detachments[notice.own_detachment_id]
    situation = {
        "today": world.clock.absolute_day,
        "your_detachment": {
            "id": detachment.id,
            "settlement_id": detachment.location_id,
            "count": detachment.count,
        },
        "armed_contact": {
            "settlement_id": notice.settlement_id,
            "rival_identity": notice.counterparty_ref.to_dict(),
            **contact_sighting_for_provider(world, notice),
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
        world, "force_standoff_decided", "A instituição escolheu uma opção diante do contato armado.",
        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(notice.event_id,),
    )
    try:
        action = option.decision()["action"]
        if action == STAND_DOWN_ACTION:
            stand_down_from_standoff(world, notice.recipient_ref, option.id, decision.id)
        elif action == WITHDRAW_ACTION:
            withdraw_detachment(world, notice.recipient_ref, option.id, decision.id)
        elif action == OFFER_ACTION:
            offer_force_deescalation(world, notice.recipient_ref, option.id, decision.id)
        elif action == RESPONSE_ACTION:
            respond_force_deescalation(world, notice.recipient_ref, option.id, decision.id)
        elif action == FULFILL_ACTION:
            fulfill_force_withdrawal(world, notice.recipient_ref, option.id, decision.id)
        elif action == ADMINISTRATION_CONCESSION_OFFER_ACTION:
            offer_administration_concession(world, notice.recipient_ref, option.id, decision.id)
        elif action == ADMINISTRATION_CONCESSION_RESPONSE_ACTION:
            respond_administration_concession(world, notice.recipient_ref, option.id, decision.id)
        elif action == ADMINISTRATION_TRANSFER_FULFILL_ACTION:
            fulfill_administration_transfer(world, notice.recipient_ref, option.id, decision.id)
        elif action == OCCUPY_AFTER_BREACH_ACTION:
            occupy_after_siege_breach(world, notice.recipient_ref, option.id, decision.id)
        elif action == GARRISON_ACTION:
            establish_garrison(world, notice.recipient_ref, option.id, decision.id)
        elif action == WITHDRAW_GARRISON_ACTION:
            withdraw_garrison(world, notice.recipient_ref, option.id, decision.id)
        elif action == ROTATE_GARRISON_ACTION:
            rotate_garrison(world, notice.recipient_ref, option.id, decision.id)
        elif action == CONTROL_ACTION:
            establish_territorial_control(world, notice.recipient_ref, option.id, decision.id)
        elif action == WITHDRAW_CONTROL_ACTION:
            withdraw_territorial_control(world, notice.recipient_ref, option.id, decision.id)
        elif action == PREPARE_POSITION_ACTION:
            prepare_force_position(world, notice.recipient_ref, option.id, decision.id)
        elif action == FIELD_ENGAGEMENT_OFFER_ACTION:
            offer_field_engagement(world, notice.recipient_ref, option.id, decision.id)
        elif action == JOIN_ACTION:
            join_field_engagement(world, notice.recipient_ref, option.id, decision.id)
        elif action in {INTERDICT_ACTION, LIFT_ACTION}:
            execute_route_interdiction_option(world, notice.recipient_ref, option.id, decision.id)
        elif action in {INVEST_ACTION, LIFT_INVESTMENT_ACTION}:
            execute_settlement_investment_option(world, notice.recipient_ref, option.id, decision.id)
        elif action in {DENY_ACTION, LIFT_ASSEMBLY_DENIAL_ACTION}:
            execute_assembly_denial_option(world, notice.recipient_ref, option.id, decision.id)
        elif action == SABOTAGE_ACTION:
            execute_sabotage_option(world, notice.recipient_ref, option.id, decision.id)
        elif action in {COMMAND_APPOINT_ACTION, COMMAND_DOCTRINE_ACTION, COMMAND_RELEASE_ACTION}:
            execute_detachment_command_option(world, notice.recipient_ref, option.id, decision.id)
        else:
            return False
    except ValueError:
        # The decision remains factual history, but an obsolete affordance can
        # never turn into a material mutation.
        return False
    return True


def _current_options(world, notice):
    response = force_deescalation_response_options(world, notice.recipient_ref, notice_id=notice.id)
    concession_response = administration_concession_response_options(world, notice.recipient_ref, notice_id=notice.id)
    if response or concession_response:
        return (*response, *concession_response)
    engagement_join = field_engagement_join_options(world, notice.recipient_ref, notice_id=notice.id)
    if engagement_join:
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id and option.detachment_id == notice.own_detachment_id)
        return (*engagement_join, *stand_down,
                *withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
                *route_interdiction_options(world, notice.recipient_ref,
                                            detachment_id=notice.own_detachment_id),
                *settlement_investment_options(world, notice.recipient_ref,
                                                detachment_id=notice.own_detachment_id),
                *assembly_denial_options(world, notice.recipient_ref,
                                          detachment_id=notice.own_detachment_id),
                *detachment_command_options(world, notice.recipient_ref,
                                             detachment_id=notice.own_detachment_id),
                *sabotage_options(world, notice.recipient_ref))
    fulfill = force_withdrawal_fulfillment_options(world, notice.recipient_ref, notice_id=notice.id)
    administration_fulfill = administration_transfer_fulfillment_options(world, notice.recipient_ref)
    if administration_fulfill or fulfill:
        return (*administration_fulfill, *fulfill)
    stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                       if option.standoff_id == notice.standoff_id and option.detachment_id == notice.own_detachment_id)
    return (*stand_down,
            *withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *force_deescalation_offer_options(world, notice.recipient_ref, notice_id=notice.id),
            *administration_concession_offer_options(world, notice.recipient_ref, notice_id=notice.id),
            *(option for option in siege_occupation_options(world, notice.recipient_ref)
              if option.settlement_id == notice.settlement_id),
            *(option for option in territorial_control_options(world, notice.recipient_ref)
              if option.settlement_id == notice.settlement_id),
            *(option for option in garrison_options(world, notice.recipient_ref)
              if option.settlement_id == notice.settlement_id),
            *force_position_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *field_engagement_offer_options(world, notice.recipient_ref, notice_id=notice.id),
            *route_interdiction_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *settlement_investment_options(world, notice.recipient_ref,
                                            detachment_id=notice.own_detachment_id),
            *assembly_denial_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *detachment_command_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *sabotage_options(world, notice.recipient_ref))


def _label(option):
    action = option.decision()["action"]
    if action == STAND_DOWN_ACTION:
        return "Baixar as armas e dissolver sua própria coluna."
    if action == WITHDRAW_ACTION:
        return "Retirar a própria coluna até uma administração conhecida."
    if action == OFFER_ACTION:
        return ("Propor que ambas as colunas se obriguem a retirar-se."
                if option.kind == "mutual"
                else "Propor retirada apenas da própria coluna.")
    if action == RESPONSE_ACTION:
        return ("Aceitar a proposta de desescalada."
                if option.response == "accept"
                else "Recusar a proposta de desescalada.")
    if action == FULFILL_ACTION:
        return "Cumprir a própria obrigação de retirada por rota atual."
    if action == ADMINISTRATION_CONCESSION_OFFER_ACTION:
        return "Oferecer cessão administrativa em troca de retirada posterior da própria coluna."
    if action == ADMINISTRATION_CONCESSION_RESPONSE_ACTION:
        return ("Aceitar a proposta de cessão administrativa."
                if option.response == "accept" else "Recusar a proposta de cessão administrativa.")
    if action == ADMINISTRATION_TRANSFER_FULFILL_ACTION:
        return "Ceder a administração do assentamento conforme a obrigação aceita."
    if action == OCCUPY_AFTER_BREACH_ACTION:
        return "Ocupar o assentamento após a brecha da guarnição; a administração ficará separada."
    if action == GARRISON_ACTION:
        return "Estabelecer uma guarnição paga para sustentar a ocupação atual."
    if action == WITHDRAW_GARRISON_ACTION:
        return "Retirar voluntariamente o dever da guarnição sem mover a coluna."
    if action == ROTATE_GARRISON_ACTION:
        return "Substituir a coluna da guarnição por outra presença abastecida no mesmo assentamento."
    if action == CONTROL_ACTION:
        return "Formalizar controle territorial enquanto a guarnição sustenta a ocupação."
    if action == WITHDRAW_CONTROL_ACTION:
        return "Retirar o mandato de controle territorial sem mover automaticamente a coluna."
    if action == PREPARE_POSITION_ACTION:
        return "Preparar uma posição no assentamento atual por três dias."
    if action == FIELD_ENGAGEMENT_OFFER_ACTION:
        return "Desafiar a coluna rival para um combate de campo voluntário."
    if action == JOIN_ACTION:
        return "Aceitar o combate de campo proposto."
    if action == INTERDICT_ACTION:
        return f"Interditar a rota local {option.route_id} com esta coluna preparada."
    if action == LIFT_ACTION:
        return f"Suspender a própria interdição da rota local {option.route_id}."
    if action == INVEST_ACTION:
        return "Pressionar todos os acessos operacionais deste assentamento com a coluna preparada."
    if action == LIFT_INVESTMENT_ACTION:
        return "Suspender a própria pressão sobre todos os acessos do assentamento."
    if action == DENY_ACTION:
        return "Negar a assembleia do rito local observado com esta coluna preparada."
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


async def review_force_contacts(world, situations):
    """At most one real-provider consultation per institution in this tick."""
    reviewed = set()
    for situation in sorted(situations, key=lambda item: item.id):
        notice_id = _notice_id(situation)
        notice = world.knowledge.force_contact_notices.get(notice_id) if notice_id else None
        if notice is None or notice.recipient_ref in reviewed:
            continue
        reviewed.add(notice.recipient_ref)
        await _contact_turn(world, notice_id)


__all__ = ["REVIEW_KIND", "contact_sighting_for_provider", "review_force_contacts", "schedule_contact_review"]
