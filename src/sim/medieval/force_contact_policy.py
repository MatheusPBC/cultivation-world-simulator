"""One bounded provider turn after a force physically recognizes a rival.

Contact creates knowledge, not an automatic campaign. The only material option
is to stand down one's own detachment through the existing Society owner.
"""

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .events import record_event, record_no_action_decision
from .force import (STAND_DOWN_ACTION, WITHDRAW_ACTION, stand_down_from_standoff,
                    standoff_options, withdraw_detachment, withdrawal_options,
                    PREPARE_POSITION_ACTION, force_position_options, prepare_force_position,
                    REROUTE_ACTION, detachment_reroute_options, reroute_detachment,
                    detachment_retreat_options, retreat_detachment,
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
from .campaign_ceasefire import (
    FULFILL_ACTION as CAMPAIGN_CEASEFIRE_FULFILL_ACTION,
    OFFER_ACTION as CAMPAIGN_CEASEFIRE_OFFER_ACTION,
    REMEDIATE_ACTION as CAMPAIGN_CEASEFIRE_REMEDIATE_ACTION,
    RESPONSE_ACTION as CAMPAIGN_CEASEFIRE_RESPONSE_ACTION,
    campaign_ceasefire_fulfillment_options, campaign_ceasefire_offer_options,
    campaign_ceasefire_response_options, campaign_withdrawal_remediation_options,
    fulfill_campaign_ceasefire, offer_campaign_ceasefire, remediate_campaign_withdrawal,
    respond_campaign_ceasefire)
from .campaign_ordnance import (BOMBARD_ACTION, DISPATCH_ACTION, campaign_ordnance_options,
                               execute_campaign_ordnance_option)
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
                            command_is_current, detachment_command_options,
                            execute_detachment_command_option)


REVIEW_KIND = "force_contact_review"
_PREFIX = "force-contact-review:"
COMMAND_REVIEW_KIND = "detachment_command_review"
_COMMAND_PREFIX = "detachment-command-review:"
MARCH_COMMAND_REVIEW_KIND = "detachment_march_command_review"
_MARCH_COMMAND_PREFIX = "detachment-march-review:"
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


def _campaign_ceasefire_options(world, notice, options_fn):
    """Keep a contact turn scoped to the campaign involving its own column."""
    own_detachment_id = notice.own_detachment_id
    matching_campaign_ids = {
        campaign.id for campaign in world.society.siege_campaigns.values()
        if campaign.settlement_id == notice.settlement_id
        and campaign.attacker_detachment_id == own_detachment_id
    }
    for campaign in world.society.siege_campaigns.values():
        garrison = world.society.garrisons.get(campaign.defender_garrison_id)
        if (campaign.settlement_id == notice.settlement_id and garrison is not None
                and garrison.detachment_id == own_detachment_id):
            matching_campaign_ids.add(campaign.id)
    options = []
    for option in options_fn(world, notice.recipient_ref):
        campaign_id = getattr(option, "campaign_id", None)
        if campaign_id is None:
            proposal = world.relations.proposals.get(getattr(option, "proposal_id", None))
            campaign_id = next((clause.campaign_id for clause in proposal.clauses
                                if clause.kind == "campaign_withdrawal"), None) if proposal else None
        if campaign_id in matching_campaign_ids:
            options.append(option)
    return tuple(options)


def _campaign_ceasefire_options_for_notice(world, notice):
    return (
        *_campaign_ceasefire_options(world, notice, campaign_ceasefire_offer_options),
        *_campaign_ceasefire_options(world, notice, campaign_ceasefire_response_options),
        *_campaign_ceasefire_options(world, notice, campaign_ceasefire_fulfillment_options),
        *_campaign_ceasefire_options(world, notice, campaign_withdrawal_remediation_options),
    )


def _campaign_ordnance_options_for_notice(world, notice):
    return _campaign_ceasefire_options(world, notice, campaign_ordnance_options)


def _campaign_ordnance_causes(world, options):
    causes = []
    for option in options:
        campaign = world.society.siege_campaigns.get(option.campaign_id)
        if campaign is None:
            continue
        causes.append(campaign.last_event_id)
        detachment = world.society.detachments.get(campaign.attacker_detachment_id)
        if detachment is not None:
            causes.append(detachment.last_event_id)
            bag = world.economy.stocks.get(f"stock:camp:{detachment.id}")
            if bag is not None:
                resource_ids = ((option.resource_id,) if option.resource_id else
                                ("artillery", "gunpowder"))
                causes.extend(bag.last_event_ids.get(resource_id) for resource_id in resource_ids)
        if option.source_stock_id is not None and option.resource_id is not None:
            source = world.economy.stocks.get(option.source_stock_id)
            if source is not None:
                causes.append(source.last_event_ids.get(option.resource_id))
        causes.extend(option.route_report_event_ids)
    causes.extend(item.event_id for item in world.knowledge.technologies.values()
                  if item.technology_id == "gunpowder"
                  and any(item.owner_ref == option.actor_ref for option in options))
    return tuple(dict.fromkeys(event_id for event_id in causes if event_id))


def _campaign_ceasefire_causes(world, options):
    causes = []
    for option in options:
        campaign = world.society.siege_campaigns.get(getattr(option, "campaign_id", None))
        if campaign is not None and campaign.last_event_id:
            causes.append(campaign.last_event_id)
        proposal = world.relations.proposals.get(getattr(option, "proposal_id", None))
        if proposal is not None and proposal.last_event_id:
            causes.append(proposal.last_event_id)
        obligation = world.relations.obligations.get(getattr(option, "obligation_id", None))
        if obligation is not None and obligation.last_event_id:
            causes.append(obligation.last_event_id)
        breach_event_id = getattr(option, "breach_event_id", None)
        if breach_event_id:
            causes.append(breach_event_id)
    return tuple(dict.fromkeys(causes))


def _command_notice_id(situation):
    if situation.kind != COMMAND_REVIEW_KIND or not situation.id.startswith(_COMMAND_PREFIX):
        return None
    return situation.id[len(_COMMAND_PREFIX):] or None


def _march_review_ids(situation):
    if situation.kind != MARCH_COMMAND_REVIEW_KIND or not situation.id.startswith(_MARCH_COMMAND_PREFIX):
        return None
    detachment_id, separator, sequence = situation.id[len(_MARCH_COMMAND_PREFIX):].rpartition(":event:")
    if not separator or not detachment_id or not sequence.isdecimal():
        return None
    return detachment_id, f"event:{sequence}"


def _schedule_commander_review(world, notice):
    command = world.society.detachment_commands.get(notice.own_detachment_id)
    if (command is None or command.institution_ref != notice.recipient_ref
            or not command_is_current(world, command)):
        return
    identity = f"{_COMMAND_PREFIX}{notice.id}"
    if world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity, COMMAND_REVIEW_KIND,
                                                 world.clock.absolute_day + 1))


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
    if notice is None:
        return False
    observation_id = notice.last_event_id or notice.event_id
    campaign_contact_options = _campaign_ceasefire_options_for_notice(world, notice)
    campaign_ordnance = _campaign_ordnance_options_for_notice(world, notice)
    # Offline/test worlds may intentionally leave this optional review
    # inactive.  In AI-enabled worlds, however, an available material menu
    # must reach ``select_option`` so a missing provider or exhausted budget
    # raises the typed pause instead of silently turning an actor decision
    # into no action.
    if not world.config.ai_enabled and not _turn_available(world):
        return False
    # A received offer must be answered independently before this actor opens
    # another one.  An accepted own promise similarly gets a later, separate
    # material turn.  Neither path is forced by the calendar.
    response = force_deescalation_response_options(world, notice.recipient_ref, notice_id=notice.id)
    concession_response = administration_concession_response_options(world, notice.recipient_ref, notice_id=notice.id)
    campaign_responses = tuple(option for option in campaign_contact_options
                               if option.decision()["action"] == CAMPAIGN_CEASEFIRE_RESPONSE_ACTION)
    fulfill = force_withdrawal_fulfillment_options(world, notice.recipient_ref, notice_id=notice.id)
    administration_fulfill = administration_transfer_fulfillment_options(world, notice.recipient_ref)
    campaign_fulfillment = tuple(
        option for option in campaign_contact_options
        if option.decision()["action"] in {CAMPAIGN_CEASEFIRE_FULFILL_ACTION,
                                            CAMPAIGN_CEASEFIRE_REMEDIATE_ACTION})
    engagement_join = field_engagement_join_options(world, notice.recipient_ref, notice_id=notice.id)
    if response or concession_response or campaign_responses:
        options = (*response, *concession_response, *campaign_responses)
    elif engagement_join:
        campaign_options = campaign_contact_options
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id
                           and option.detachment_id == notice.own_detachment_id)
        withdraw = withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id)
        options = (*engagement_join, *stand_down, *withdraw, *campaign_options, *campaign_ordnance,
                   *route_interdiction_options(world, notice.recipient_ref,
                                               detachment_id=notice.own_detachment_id),
                   *settlement_investment_options(world, notice.recipient_ref,
                                                   detachment_id=notice.own_detachment_id),
                   *assembly_denial_options(world, notice.recipient_ref,
                                             detachment_id=notice.own_detachment_id),
                   *detachment_command_options(world, notice.recipient_ref,
                                                detachment_id=notice.own_detachment_id),
                   *sabotage_options(world, notice.recipient_ref))
    elif administration_fulfill or fulfill or campaign_fulfillment:
        options = (*administration_fulfill, *fulfill, *campaign_fulfillment)
    else:
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id
                           and option.detachment_id == notice.own_detachment_id)
        withdraw = withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id)
        offers = force_deescalation_offer_options(world, notice.recipient_ref, notice_id=notice.id)
        concessions = administration_concession_offer_options(world, notice.recipient_ref, notice_id=notice.id)
        campaign_options = _campaign_ceasefire_options_for_notice(world, notice)
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
        options = (*stand_down, *withdraw, *offers, *concessions, *campaign_options, *campaign_ordnance,
                   *siege_occupations, *controls, *garrisons, *positions, *engagements, *interdictions, *investments, *denials,
                   *commands,
                   *sabotage_options(world, notice.recipient_ref))
    if not options:
        return False
    detachment = world.society.detachments[notice.own_detachment_id]
    position = world.society.force_positions.get(f"force-position:{detachment.id}")
    settlement = world.society.settlements.get(detachment.location_id)
    own_garrison = world.society.garrisons.get(f"garrison:{detachment.id}")
    local_route_ids = ({route.id for route in world.map.routes.values()
                        if settlement is not None and settlement.region_id in route.endpoint_region_ids})
    local_observation_ids = tuple(
        report.event_id for report in world.knowledge.route_reports.values()
        if report.recipient_ref == notice.recipient_ref and report.route_id in local_route_ids
        and report.channel == "field_route_observation"
        and 0 <= world.clock.absolute_day - report.observed_day < 30)
    settlement_report = world.knowledge.settlement_report(notice.recipient_ref, notice.settlement_id)
    settlement_observation_id = (settlement_report.event_id
                                if settlement_report is not None
                                and 0 <= world.clock.absolute_day - settlement_report.observed_day < 3
                                else None)
    turn_causes = tuple(dict.fromkeys(
        event_id for event_id in (observation_id, detachment.last_event_id,
                                  position.last_event_id if position is not None else None,
                                  own_garrison.last_event_id if own_garrison is not None else None,
                                  *local_observation_ids, settlement_observation_id,
                                  *_campaign_ceasefire_causes(world, campaign_contact_options),
                                  *_campaign_ordnance_causes(world, campaign_ordnance))
        if event_id))
    situation = {
        "today": world.clock.absolute_day,
        "your_detachment": {
            "id": detachment.id,
            "settlement_id": detachment.location_id,
            "count": detachment.count,
        },
        "your_garrison": ({
            "stage": own_garrison.stage,
            "started_day": own_garrison.started_day,
            "days_active": (max(0, world.clock.absolute_day - own_garrison.started_day)
                            if own_garrison.stage == "active" else 0),
        } if own_garrison is not None else None),
        "armed_contact": {
            "settlement_id": notice.settlement_id,
            "rival_identity": notice.counterparty_ref.to_dict(),
            **contact_sighting_for_provider(world, notice),
        },
        "campaign_ceasefire_options": [
            {
                "campaign_phase": (world.society.siege_campaigns[option.campaign_id].phase
                                   if getattr(option, "campaign_id", None) in world.society.siege_campaigns
                                   else None),
                "progress_days": (world.society.siege_campaigns[option.campaign_id].progress_days
                                  if getattr(option, "campaign_id", None) in world.society.siege_campaigns
                                  else None),
                "proposal_status": (world.relations.proposals[option.proposal_id].status
                                    if getattr(option, "proposal_id", None) in world.relations.proposals
                                    else None),
                "obligation_status": (world.relations.obligations[option.obligation_id].status
                                      if getattr(option, "obligation_id", None) in world.relations.obligations
                                      else None),
                "due_day": (world.relations.proposals[world.relations.obligations[option.obligation_id].proposal_id]
                            .clauses[world.relations.obligations[option.obligation_id].clause_index].due_day
                            if getattr(option, "obligation_id", None) in world.relations.obligations
                            else None),
            }
            for option in campaign_contact_options
        ],
        "campaign_ordnance_options": [
            {"kind": option.kind, "campaign_id": option.campaign_id,
             "resource_id": option.resource_id, "quantity": option.quantity,
             "source_stock_id": option.source_stock_id,
             "route_ids": list(option.route_ids)}
            for option in campaign_ordnance
        ],
    }
    selected = await ai_decider.select_option(
        world, notice.recipient_ref, situation,
        [{"id": option.id, "label": _label(option)} for option in options],
        causes=turn_causes,
    )
    if selected == ai_decider.NO_ACTION:
        record_no_action_decision(
            world, "force_standoff_decided", "A instituição decidiu manter a postura diante do contato armado.",
            notice.recipient_ref, affordance_ids=(option.id for option in options),
            cause_ids=turn_causes,
        )
        return False
    if selected is None:
        return False
    option = next((item for item in _current_options(world, notice) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for {notice.recipient_ref.kind}:{notice.recipient_ref.id}: "
            "force contact affordance became stale"
        )
    decision = record_event(
        world, "force_standoff_decided", "A instituição escolheu uma opção diante do contato armado.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), cause_ids=turn_causes,
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
        elif action == CAMPAIGN_CEASEFIRE_OFFER_ACTION:
            offer_campaign_ceasefire(world, notice.recipient_ref, option.id, decision.id)
        elif action == CAMPAIGN_CEASEFIRE_RESPONSE_ACTION:
            respond_campaign_ceasefire(world, notice.recipient_ref, option.id, decision.id)
        elif action in {CAMPAIGN_CEASEFIRE_FULFILL_ACTION, CAMPAIGN_CEASEFIRE_REMEDIATE_ACTION}:
            if action == CAMPAIGN_CEASEFIRE_FULFILL_ACTION:
                fulfill_campaign_ceasefire(world, notice.recipient_ref, option.id, decision.id)
            else:
                remediate_campaign_withdrawal(world, notice.recipient_ref, option.id, decision.id)
        elif action in {DISPATCH_ACTION, BOMBARD_ACTION}:
            execute_campaign_ordnance_option(world, notice.recipient_ref, option.id, decision.id)
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
        elif action in {COMMAND_APPOINT_ACTION, COMMAND_RELEASE_ACTION}:
            execute_detachment_command_option(world, notice.recipient_ref, option.id, decision.id)
        else:
            return False
    except ValueError as exc:
        # The engine owns rollback; a direct policy call must still expose the
        # stale provider choice instead of silently completing the turn.
        raise ProviderDecisionRequired(
            f"provider decision required for {notice.recipient_ref.kind}:{notice.recipient_ref.id}: "
            f"force contact affordance became stale: {exc}"
        ) from exc
    return True


async def _commander_turn(world, notice_id):
    """The named local commander, not the institution, chooses tactical posture."""
    notice = world.knowledge.force_contact_notices.get(notice_id)
    if notice is None or contact_sighting_for_provider(world, notice)["counterparty_posture"] is None:
        return False
    command = world.society.detachment_commands.get(notice.own_detachment_id)
    if (command is None or command.institution_ref != notice.recipient_ref
            or not command_is_current(world, command)):
        return False
    actor = EntityRef("character", command.character_id)
    options = detachment_command_options(world, actor, detachment_id=command.detachment_id)
    if not options:
        return False
    character = world.society.characters[command.character_id]
    detachment = world.society.detachments[command.detachment_id]
    situation = {
        "today": world.clock.absolute_day,
        "your_command": {"detachment_id": detachment.id, "settlement_id": detachment.location_id,
                         "count": detachment.count, "current_doctrine": command.doctrine,
                         "personality": character.personality.model_dump()},
        "armed_contact": {"settlement_id": notice.settlement_id,
                          "rival_identity": notice.counterparty_ref.to_dict(),
                          **contact_sighting_for_provider(world, notice)},
    }
    selected = await ai_decider.select_option(
        world, actor, situation, [{"id": option.id, "label": _label(option)} for option in options],
        causes=(notice.event_id, command.last_event_id))
    if selected == ai_decider.NO_ACTION:
        record_no_action_decision(
            world, "detachment_commander_declined",
            "O comandante local optou por manter a postura atual diante do contato armado.",
            actor, affordance_ids=(option.id for option in options),
            cause_ids=(notice.event_id, command.last_event_id))
        return False
    if selected is None:
        return False
    option = next((item for item in detachment_command_options(world, actor,
                        detachment_id=command.detachment_id) if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(f"provider decision required for character:{character.id}: stale doctrine")
    decision = record_event(
        world, "detachment_commander_decided",
        "O comandante local escolheu sua postura diante do contato armado.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), cause_ids=(notice.event_id, command.last_event_id))
    try:
        execute_detachment_command_option(world, actor, option.id, decision.id)
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for character:{character.id}: stale doctrine") from exc
    return True


def _current_options(world, notice):
    response = force_deescalation_response_options(world, notice.recipient_ref, notice_id=notice.id)
    concession_response = administration_concession_response_options(world, notice.recipient_ref, notice_id=notice.id)
    campaign_responses = _campaign_ceasefire_options(
        world, notice, campaign_ceasefire_response_options)
    if response or concession_response or campaign_responses:
        return (*response, *concession_response, *campaign_responses)
    engagement_join = field_engagement_join_options(world, notice.recipient_ref, notice_id=notice.id)
    if engagement_join:
        campaign_options = _campaign_ceasefire_options_for_notice(world, notice)
        ordnance_options = _campaign_ordnance_options_for_notice(world, notice)
        stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                           if option.standoff_id == notice.standoff_id and option.detachment_id == notice.own_detachment_id)
        return (*engagement_join, *stand_down, *campaign_options, *ordnance_options,
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
    campaign_fulfillment = (*_campaign_ceasefire_options(
        world, notice, campaign_ceasefire_fulfillment_options),
        *_campaign_ceasefire_options(world, notice, campaign_withdrawal_remediation_options))
    if administration_fulfill or fulfill or campaign_fulfillment:
        return (*administration_fulfill, *fulfill, *campaign_fulfillment)
    stand_down = tuple(option for option in standoff_options(world, notice.recipient_ref)
                       if option.standoff_id == notice.standoff_id and option.detachment_id == notice.own_detachment_id)
    return (*stand_down,
            *withdrawal_options(world, notice.recipient_ref, detachment_id=notice.own_detachment_id),
            *force_deescalation_offer_options(world, notice.recipient_ref, notice_id=notice.id),
            *administration_concession_offer_options(world, notice.recipient_ref, notice_id=notice.id),
            *_campaign_ceasefire_options_for_notice(world, notice),
            *_campaign_ordnance_options_for_notice(world, notice),
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
    if action == CAMPAIGN_CEASEFIRE_OFFER_ACTION:
        return ("Propor cessar-fogo mútuo." if getattr(option, "kind", None) == "mutual"
                else "Propor retirada unilateral da própria coluna.")
    if action == CAMPAIGN_CEASEFIRE_RESPONSE_ACTION:
        return ("Aceitar o cessar-fogo." if getattr(option, "response", None) == "accept"
                else "Recusar o cessar-fogo.")
    if action == CAMPAIGN_CEASEFIRE_FULFILL_ACTION:
        return "Cumprir a retirada material prometida no cessar-fogo."
    if action == CAMPAIGN_CEASEFIRE_REMEDIATE_ACTION:
        return "Reparar a quebra do cessar-fogo retirando materialmente a coluna."
    if action == DISPATCH_ACTION:
        return (f"Despachar {option.quantity} unidade(s) de {option.resource_id} à bagagem "
                f"da coluna pelo frete atual.")
    if action == BOMBARD_ACTION:
        return "Disparar uma peça de cerco e consumir uma carga de pólvora contra a guarnição."
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
    if action == REROUTE_ACTION:
        return "Desviar a coluna por uma rota alternativa observada pessoalmente."
    if action == "retreat_marching_detachment":
        return "Retornar a uma administração própria por rotas observadas pessoalmente."
    return "Nenhuma ação disponível."


async def _commander_march_turn(world, detachment_id, held_event_id):
    """A field commander independently reacts to a personally observed block."""
    command = world.society.detachment_commands.get(detachment_id)
    detachment = world.society.detachments.get(detachment_id)
    events = world.event_index()
    scheduled_hold = events.get(held_event_id)
    held = events.get(detachment.last_event_id) if detachment is not None else None
    if (command is None or detachment is None or scheduled_hold is None or held is None
            or detachment.stage != "marching" or held.event_type != "detachment_held"
            or (scheduled_hold.causal_payload or {}).get("detachment_id") != detachment_id
            or (held.causal_payload or {}).get("detachment_id") != detachment_id
            or not command_is_current(world, command)):
        return False
    # Dated force resolution happens before the review, so a column that waits
    # another day has a newer physical hold receipt. Rebase only across that
    # same column's causal hold chain, never onto a stale or unrelated event.
    pending = [link.cause_event_id for link in held.causal_links]
    ancestry = set()
    while pending:
        cause_id = pending.pop()
        if cause_id in ancestry or cause_id not in events:
            continue
        ancestry.add(cause_id)
        pending.extend(link.cause_event_id for link in events[cause_id].causal_links)
    if held.id != scheduled_hold.id and scheduled_hold.id not in ancestry:
        return False
    held_event_id = held.id
    actor = EntityRef("character", command.character_id)
    plans = tuple(plan for plan in world.strategy.plans.values()
                  if plan.detachment_id == detachment_id and plan.stage in {"mobilized", "blocked"})
    options = tuple(option for plan in plans for option in (
        *detachment_reroute_options(world, command.institution_ref, plan.id, actor_ref=actor),
        *detachment_retreat_options(world, command.institution_ref, plan.id, actor_ref=actor)))
    if not options:
        return False
    if not world.config.ai_enabled and not _turn_available(world):
        return False
    blocked_route_id = (held.causal_payload or {}).get("blocked_route_id")
    report = world.knowledge.route_report(actor, blocked_route_id) if blocked_route_id else None
    character = world.society.characters[command.character_id]
    causes = tuple(dict.fromkeys((held_event_id, command.last_event_id,
                                  *(option.blocked_report_id for option in options),
                                  *(event_id for option in options for event_id in option.route_report_ids))))
    situation = {
        "today": world.clock.absolute_day,
        "your_command": {"detachment_id": detachment_id, "count": detachment.count,
                         "position_region_id": options[0].start_region_id,
                         "personality": character.personality.model_dump()},
        "blocked_route": {"route_id": blocked_route_id,
                          "observed_day": report.observed_day if report else None,
                          "travel_days": report.travel_days if report else None,
                          "capacity": report.operational_capacity if report else None},
    }
    selected = await ai_decider.select_option(
        world, actor, situation,
        [{"id": option.id, "label": _label(option)} for option in options], causes=causes)
    if selected == ai_decider.NO_ACTION:
        record_no_action_decision(
            world, "detachment_commander_declined_reroute",
            "O comandante manteve a espera diante da passagem interrompida.",
            actor, affordance_ids=(option.id for option in options), cause_ids=causes)
        return False
    if selected is None:
        return False
    fresh = tuple(option for plan in plans for option in (
        *detachment_reroute_options(world, command.institution_ref, plan.id, actor_ref=actor),
        *detachment_retreat_options(world, command.institution_ref, plan.id, actor_ref=actor)))
    option = next((item for item in fresh if item.id == selected), None)
    if option is None:
        raise ProviderDecisionRequired(
            f"provider decision required for character:{actor.id}: march reroute became stale")
    decision = record_event(
        world, "detachment_commander_march_decided",
        "O comandante escolheu como responder ao bloqueio da coluna.",
        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
        decision=option.decision(), cause_ids=causes)
    try:
        if option.decision()["action"] == REROUTE_ACTION:
            reroute_detachment(world, command.institution_ref, option.plan_id,
                               option.id, decision.id, actor_ref=actor)
            from .strategy_response import _schedule_review
            _schedule_review(world, option.plan_id)
        else:
            movement = retreat_detachment(world, command.institution_ref, option.plan_id,
                                           option.id, decision.id, actor_ref=actor)
            from .strategy_response import _set_plan
            current_plan = world.strategy.plans[option.plan_id]
            _set_plan(world, current_plan, "withdrawn", blocker="missão encerrada; coluna em retorno",
                      detachment_id=detachment_id, causes=(decision.id, movement.id))
    except ValueError as exc:
        raise ProviderDecisionRequired(
            f"provider decision required for character:{actor.id}: march reroute became stale") from exc
    return True


async def review_force_contacts(world, situations):
    """Institution and named commander receive separate, dated actor turns."""
    reviewed = set()
    for situation in sorted(situations, key=lambda item: item.id):
        notice_id = _notice_id(situation)
        notice = world.knowledge.force_contact_notices.get(notice_id) if notice_id else None
        if notice is None or notice.recipient_ref in reviewed:
            continue
        reviewed.add(notice.recipient_ref)
        await _contact_turn(world, notice_id)
        if world.config.ai_enabled:
            _schedule_commander_review(world, notice)
    reviewed_commanders = set()
    for situation in sorted(situations, key=lambda item: item.id):
        notice_id = _command_notice_id(situation)
        notice = world.knowledge.force_contact_notices.get(notice_id) if notice_id else None
        command = world.society.detachment_commands.get(notice.own_detachment_id) if notice else None
        if command is None or command.character_id in reviewed_commanders:
            continue
        reviewed_commanders.add(command.character_id)
        await _commander_turn(world, notice_id)
    reviewed_marches = set()
    for situation in sorted(situations, key=lambda item: item.id):
        review = _march_review_ids(situation)
        if review is None or review in reviewed_marches:
            continue
        reviewed_marches.add(review)
        detachment_id, held_event_id = review
        await _commander_march_turn(world, detachment_id, held_event_id)


__all__ = ["REVIEW_KIND", "COMMAND_REVIEW_KIND", "MARCH_COMMAND_REVIEW_KIND",
           "contact_sighting_for_provider",
           "review_force_contacts", "schedule_contact_review"]
