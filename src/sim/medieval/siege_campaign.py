"""A small persistent siege vertical over the existing military owners.

This does not resolve a battle or transfer a city.  A campaign is available
only after a prepared, supplied column has already created the existing
all-exit settlement investment against an active enemy garrison.  Daily
progress is a material fact contingent on that same force, its rations and
the existing route causes remaining current.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import (MAX_SIEGE_GARRISON_ENDURANCE,
                                       SIEGE_GARRISON_ENDURANCE, SiegeCampaign)
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event
from .force import (_begin_withdrawal, _decision as force_decision, collapse_garrison_for_siege,
                    withdrawal_options)
from .campaign_supply import _lapse_campaign_notices
from .settlement_investment import revoke_settlement_investments_for


BEGIN_ACTION = "begin_siege_campaign"
PROGRESS_KIND = "siege_campaign"
# The campaign already consumes the ordinary daily ration through the force
# owner.  A sustained investment also creates a second, bounded pressure on
# the besieged column: the blockade makes one additional ration per soldier
# unavailable each progress day.  This is deliberately a material reading,
# not a combat multiplier or an automatic victory rule.
SIEGE_BLOCKADE_RATION_PER_SOLDIER = 1


@dataclass(frozen=True)
class SiegeCampaignOption:
    id: Identity
    actor_ref: EntityRef
    investment_id: Identity
    attacker_detachment_id: Identity
    defender_garrison_id: Identity
    settlement_id: Identity

    def decision(self):
        return {"action": BEGIN_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


OCCUPY_AFTER_BREACH_ACTION = "occupy_after_siege_breach"
WITHDRAW_SIEGE_ACTION = "withdraw_siege_campaign"


@dataclass(frozen=True)
class SiegeOccupationOption:
    """A separate post-breach choice; a breach never grants occupation."""
    id: Identity
    actor_ref: EntityRef
    campaign_id: Identity
    settlement_id: Identity
    campaign_event_id: Identity

    def decision(self):
        return {"action": OCCUPY_AFTER_BREACH_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class SiegeWithdrawalOption:
    """A voluntary campaign withdrawal; the force owner still moves the column."""
    id: Identity
    actor_ref: EntityRef
    campaign_id: Identity
    detachment_id: Identity
    destination_id: Identity
    route_ids: tuple[Identity, ...]

    def decision(self):
        return {"action": WITHDRAW_SIEGE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def siege_campaign_adapters():
    """Expose campaign starts to the single institutional monthly turn."""
    from .institutional_decision_turn import DiscretionaryAdapter

    def causes(world, option):
        investment = world.society.settlement_investments.get(option.investment_id)
        attacker = world.society.detachments.get(option.attacker_detachment_id)
        garrison = world.society.garrisons.get(option.defender_garrison_id)
        return _causes(
            investment.last_event_id if investment else None,
            attacker.last_event_id if attacker else None,
            garrison.last_event_id if garrison else None)

    def execute(world, actor, option_id, decision_event_id):
        begin_siege_campaign(world, actor, option_id, decision_event_id)

    def withdrawal_causes(world, option):
        campaign = world.society.siege_campaigns.get(option.campaign_id)
        detachment = world.society.detachments.get(option.detachment_id)
        return _causes(campaign.last_event_id if campaign else None,
                       detachment.last_event_id if detachment else None)

    def execute_withdrawal(world, actor, option_id, decision_event_id):
        withdraw_siege_campaign(world, actor, option_id, decision_event_id)

    def occupation_causes(world, option):
        campaign = world.society.siege_campaigns.get(option.campaign_id)
        report = world.knowledge.settlement_report(option.actor_ref, option.settlement_id)
        return _causes(campaign.last_event_id if campaign else None,
                       report.event_id if report else None)

    def execute_occupation(world, actor, option_id, decision_event_id):
        occupy_after_siege_breach(world, actor, option_id, decision_event_id)

    def control_adapters():
        from .territorial_control import (CONTROL_ACTION, WITHDRAW_CONTROL_ACTION,
                                          establish_territorial_control,
                                          territorial_control_options,
                                          withdraw_territorial_control)

        def causes(world, option):
            control = world.society.territorial_controls.get(
                f"territorial-control:{option.settlement_id}")
            garrison = world.society.garrisons.get(option.garrison_id)
            return _causes(control.last_event_id if control else None,
                           garrison.last_event_id if garrison else None,
                           option.report_event_id)

        def execute(world, actor, option_id, decision_event_id):
            option = next((item for item in territorial_control_options(world, actor)
                           if item.id == option_id), None)
            if option is None:
                raise ValueError("territorial control option is stale or unknown")
            if option.kind == "withdraw":
                withdraw_territorial_control(world, actor, option_id, decision_event_id)
            else:
                establish_territorial_control(world, actor, option_id, decision_event_id)

        return DiscretionaryAdapter(
            name="territorial_control", family="campaign",
            options_fn=territorial_control_options,
            label_fn=lambda option: (
                "Retirar o mandato de controle territorial."
                if option.kind == "withdraw"
                else "Formalizar controle territorial sustentado pela guarnição."),
            causes_fn=causes, execute_fn=execute,
            claim_fn=lambda option: ("territorial-control", option.settlement_id))

    return (
        DiscretionaryAdapter(
            name="siege_campaign", family="campaign", options_fn=siege_campaign_options,
            label_fn=lambda option: f"Iniciar cerco material em {option.settlement_id}.",
            causes_fn=causes, execute_fn=execute),
        DiscretionaryAdapter(
            name="siege_campaign_withdrawal", family="campaign",
            options_fn=siege_campaign_withdrawal_options,
            label_fn=lambda option: f"Retirar o cerco de {option.campaign_id}.",
            causes_fn=withdrawal_causes, execute_fn=execute_withdrawal),
        DiscretionaryAdapter(
            name="siege_occupation", family="campaign",
            options_fn=siege_occupation_options,
            label_fn=lambda option: f"Ocupar materialmente {option.settlement_id} após a brecha.",
            causes_fn=occupation_causes, execute_fn=execute_occupation,
            claim_fn=lambda option: ("occupation", option.settlement_id)),
        control_adapters(),
    )


def _current_parts(world, campaign):
    attacker = world.society.detachments.get(campaign.attacker_detachment_id)
    garrison = world.society.garrisons.get(campaign.defender_garrison_id)
    investment = world.society.settlement_investments.get(campaign.investment_id)
    defender = world.society.detachments.get(garrison.detachment_id) if garrison is not None else None
    if (attacker is None or garrison is None or investment is None or defender is None
            or attacker.owner_ref != campaign.attacker_ref
            or attacker.stage != "present" or attacker.location_id != campaign.settlement_id
            or attacker.provisions < attacker.count or investment.stage != "active"
            or investment.detachment_id != attacker.id or investment.settlement_id != campaign.settlement_id
            or garrison.stage != "active" or defender.stage != "present"
            or defender.location_id != campaign.settlement_id or defender.owner_ref == campaign.attacker_ref):
        return None
    return attacker, garrison, investment, defender


def _garrison_wear(campaign, attacker, defender):
    """One bounded material reading; no general morale or combat subsystem.

    A column can only keep applying pressure while it remains supplied.  The
    defender's current ration reserve gives a small concrete resistance, and
    uninterrupted pressure becomes harder to absorb with time.  Every input
    is an existing canonical force fact, never an LLM estimate.
    """
    force_pressure = max(1, min(5, (attacker.count * 4) // max(1, defender.count)))
    supply_pressure = 1 if attacker.provisions >= attacker.count * 2 else 0
    elapsed_pressure = min(2, campaign.progress_days)
    defender_relief = 1 if defender.provisions >= defender.count * 4 else 0
    return max(1, min(7, force_pressure + supply_pressure + elapsed_pressure - defender_relief))


def siege_campaign_options(world, actor, *, detachment_id=None):
    """Enumerate only owner-visible starts bound to current material facts."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for investment in sorted(world.society.settlement_investments.values(), key=lambda item: item.id):
        if investment.stage != "active" or investment.actor_ref != actor:
            continue
        if any(item.investment_id == investment.id for item in world.society.siege_campaigns.values()):
            continue
        attacker = world.society.detachments.get(investment.detachment_id)
        if attacker is None or (detachment_id is not None and attacker.id != detachment_id):
            continue
        for garrison in sorted(world.society.garrisons.values(), key=lambda item: item.id):
            campaign = SiegeCampaign(
                id="siege-campaign:preview", attacker_ref=actor, attacker_detachment_id=attacker.id,
                defender_garrison_id=garrison.id, settlement_id=investment.settlement_id,
                investment_id=investment.id, decision_event_id="preview", started_day=world.clock.absolute_day,
                next_progress_day=world.clock.absolute_day + 1, last_event_id="preview")
            if garrison.settlement_id != investment.settlement_id or _current_parts(world, campaign) is None:
                continue
            options.append(SiegeCampaignOption(
                id=(f"siege-campaign:{investment.id}:{investment.last_event_id}:{attacker.last_event_id}:"
                    f"{garrison.id}:{garrison.last_event_id}"), actor_ref=actor, investment_id=investment.id,
                attacker_detachment_id=attacker.id, defender_garrison_id=garrison.id,
                settlement_id=investment.settlement_id))
    return tuple(options)


def begin_siege_campaign(world, actor, option_id, decision_event_id):
    """Revalidate the selected siege start and schedule its first material day."""
    candidate = deepcopy(world)
    decision, decided_by = force_decision(candidate, decision_event_id, BEGIN_ACTION)
    if decided_by != actor:
        raise ValueError("siege campaign has the wrong actor")
    option = next((item for item in siege_campaign_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("siege campaign option is stale or unknown")
    require_authority(candidate, actor, "military")
    identity = f"siege-campaign:{decision.id}"
    initial_endurance = SIEGE_GARRISON_ENDURANCE
    campaign = SiegeCampaign(
        id=identity, attacker_ref=actor, attacker_detachment_id=option.attacker_detachment_id,
        defender_garrison_id=option.defender_garrison_id, settlement_id=option.settlement_id,
        investment_id=option.investment_id, decision_event_id=decision.id,
        started_day=candidate.clock.absolute_day, next_progress_day=candidate.clock.absolute_day + 1,
        garrison_endurance=initial_endurance,
        last_event_id="pending")
    parts = _current_parts(candidate, campaign)
    if parts is None:
        raise ValueError("siege campaign is no longer materially possible")
    attacker, garrison, investment, defender = parts
    initial_endurance = SIEGE_GARRISON_ENDURANCE
    if candidate.knowledge.knows(defender.owner_ref, "fortification"):
        initial_endurance = min(MAX_SIEGE_GARRISON_ENDURANCE,
                                SIEGE_GARRISON_ENDURANCE + 2)
    campaign = campaign.model_copy(update={"garrison_endurance": initial_endurance})
    event = record_event(
        candidate, "siege_campaign_started", "A coluna iniciou o cerco material contra a guarnição cercada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("siege_campaign", identity, "phase", None, "sieging"),
                _delta("siege_campaign", identity, "progress_days", None, 0),
                _delta("siege_campaign", identity, "garrison_endurance", None,
                       initial_endurance),
                _delta("siege_campaign", identity, "settlement_id", None, campaign.settlement_id)),
        cause_ids=_causes(decision.id, attacker.last_event_id, garrison.last_event_id,
                          defender.last_event_id, investment.last_event_id))
    candidate.society.siege_campaigns[identity] = campaign.model_copy(update={"last_event_id": event.id})
    candidate.agenda.schedule(ScheduledSituation(identity, PROGRESS_KIND, campaign.next_progress_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.siege_campaigns[identity]


def siege_campaign_withdrawal_options(world, actor):
    """Enumerate current routes home for an active siege column."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for campaign in sorted(world.society.siege_campaigns.values(), key=lambda item: item.id):
        if campaign.phase not in {"sieging", "breached"} or campaign.attacker_ref != actor:
            continue
        detachment = world.society.detachments.get(campaign.attacker_detachment_id)
        if detachment is None:
            continue
        withdrawals = withdrawal_options(world, actor, detachment_id=detachment.id,
                                         allow_open_campaign_supply=True,
                                         campaign_authorized=True)
        if withdrawals:
            for withdrawal in withdrawals:
                options.append(SiegeWithdrawalOption(
                    id=f"siege-withdrawal:{campaign.id}:{campaign.last_event_id}:{withdrawal.id}",
                    actor_ref=actor, campaign_id=campaign.id, detachment_id=detachment.id,
                    destination_id=withdrawal.destination_id, route_ids=withdrawal.route_ids))
            continue
        # An active investment deliberately closes every exit.  The campaign
        # owner still knows the exact exits it selected, so those exits remain
        # valid withdrawal affordances when the same action first lifts the
        # owner's investment and then starts the dated march.
        investment = world.society.settlement_investments.get(campaign.investment_id)
        if investment is None or investment.stage != "active":
            continue
        settlement = world.society.settlements.get(campaign.settlement_id)
        if settlement is None:
            continue
        for destination in sorted(world.society.settlements.values(), key=lambda item: item.id):
            if destination.id == settlement.id or destination.administrator_id != actor.id:
                continue
            report = world.knowledge.settlement_report(actor, destination.id)
            if report is None or report.observed_day != world.clock.absolute_day:
                continue
            for exit_route_id in investment.route_ids:
                route = world.map.routes.get(exit_route_id)
                if (route is None or not route.enabled or not route.allows_resource("food")
                        or world.map.get_route_operational_capacity(exit_route_id, ignore_force_interdictor=True)
                        < world.economy.resources["food"].bulk
                        or settlement.region_id not in route.endpoint_region_ids
                        or destination.region_id not in route.endpoint_region_ids):
                    continue
                option_id = (f"siege-withdrawal:{campaign.id}:{campaign.last_event_id}:"
                             f"{detachment.last_event_id}:{destination.id}:{exit_route_id}")
                options.append(SiegeWithdrawalOption(
                    id=option_id, actor_ref=actor, campaign_id=campaign.id,
                    detachment_id=detachment.id, destination_id=destination.id,
                    route_ids=(exit_route_id,)))
    return tuple(sorted(options, key=lambda item: item.id))


def _execute_siege_withdrawal(candidate, actor, option, decision_event_id):
    """Execute a current siege withdrawal from any accepted actor decision."""
    require_authority(candidate, actor, "military")
    campaign = candidate.society.siege_campaigns[option.campaign_id]
    # A withdrawal is also a material decision to abandon an outstanding
    # campaign-supply observation.  Pending cargo is not moved or deleted;
    # dispatched cargo still blocks this option until its own owner resolves it.
    supply_lapsed = _lapse_campaign_notices(candidate, option.detachment_id, decision_event_id)
    lifted_investments = revoke_settlement_investments_for(
        candidate, candidate.society.detachments[option.detachment_id], cause_ids=(decision_event_id,))
    withdrawal = next((item for item in withdrawal_options(
                           candidate, actor, detachment_id=option.detachment_id,
                           allow_open_campaign_supply=True, campaign_authorized=True)
                       if item.destination_id == option.destination_id and item.route_ids == option.route_ids), None)
    if withdrawal is None:
        raise ValueError("siege withdrawal route is no longer current")
    material = _begin_withdrawal(candidate, actor, withdrawal, decision_event_id)
    event = record_event(
        candidate, "siege_campaign_withdrawn",
        "A coluna encerrou voluntariamente o cerco e iniciou uma retirada material.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("siege_campaign", campaign.id, "phase", campaign.phase, "withdrawn"),),
        cause_ids=_causes(decision_event_id, campaign.last_event_id, material.id,
                          supply_lapsed.id if supply_lapsed is not None else None,
                          *(item.id for item in lifted_investments)))
    candidate.society.siege_campaigns[campaign.id] = campaign.model_copy(
        update={"phase": "withdrawn", "next_progress_day": None, "last_event_id": event.id})
    candidate.agenda.cancel(campaign.id)
    return candidate.society.siege_campaigns[campaign.id]


def withdraw_siege_campaign(world, actor, option_id, decision_event_id):
    """End the siege and begin a real, dated withdrawal of its attacker."""
    candidate = deepcopy(world)
    decision, decided_by = force_decision(candidate, decision_event_id, WITHDRAW_SIEGE_ACTION)
    if decided_by != actor:
        raise ValueError("siege withdrawal has the wrong actor")
    option = next((item for item in siege_campaign_withdrawal_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("siege withdrawal option is stale or unknown")
    _execute_siege_withdrawal(candidate, actor, option, decision_event_id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.siege_campaigns[option.campaign_id]


def siege_occupation_options(world, actor):
    """Enumerate current occupation choices created by a material breach."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for campaign in sorted(world.society.siege_campaigns.values(), key=lambda item: item.id):
        if campaign.phase != "breached" or campaign.attacker_ref != actor:
            continue
        attacker = world.society.detachments.get(campaign.attacker_detachment_id)
        settlement = world.society.settlements.get(campaign.settlement_id)
        garrison = world.society.garrisons.get(campaign.defender_garrison_id)
        defender = world.society.detachments.get(garrison.detachment_id) if garrison is not None else None
        report = world.knowledge.settlement_report(actor, campaign.settlement_id)
        if (attacker is None or settlement is None or garrison is None or defender is None or report is None
                or attacker.stage != "present" or attacker.location_id != settlement.id
                or defender.owner_ref == actor or defender.stage != "present"
                or attacker.provisions < attacker.count or report.observed_day != world.clock.absolute_day
                or report.occupier_id != settlement.occupier_id or settlement.occupier_id != defender.owner_ref.id
                or settlement.occupier_id == actor.id):
            continue
        # The defender's old occupier is allowed to be physically present, but
        # its garrison duty must already be collapsed by this exact campaign.
        if garrison.stage != "collapsed" or settlement.occupier_id is None:
            continue
        options.append(SiegeOccupationOption(
            id=f"siege-occupation:{campaign.id}:{campaign.last_event_id}:{attacker.last_event_id}:{report.event_id}",
            actor_ref=actor, campaign_id=campaign.id, settlement_id=settlement.id,
            campaign_event_id=campaign.last_event_id))
    return tuple(sorted(options, key=lambda item: item.id))


def occupy_after_siege_breach(world, actor, option_id, decision_event_id):
    """Apply only the occupier field after an explicit post-breach decision."""
    candidate = deepcopy(world)
    decision = next((event for event in candidate.events if event.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != candidate.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != OCCUPY_AFTER_BREACH_ACTION
            or decision.decision.get("actor_ref") != actor.to_dict()):
        raise ValueError("siege occupation requires a current actor decision")
    option = next((item for item in siege_occupation_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("siege occupation option is stale or unknown")
    require_authority(candidate, actor, "military")
    campaign = candidate.society.siege_campaigns[option.campaign_id]
    settlement = candidate.society.settlements[option.settlement_id]
    before = settlement.occupier_id
    candidate.society.set_occupation(settlement.id, actor.id)
    event = record_event(
        candidate, "settlement_occupied_after_siege",
        "Após uma brecha material, a instituição escolheu ocupar o assentamento; a administração não mudou.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("settlement", settlement.id, "occupier_id", before, actor.id),),
        cause_ids=_causes(decision.id, option.campaign_event_id, campaign.decision_event_id),
    )
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return event


def _finish(world, campaign, phase, *, cause_ids=(), progress_days=None,
            garrison_endurance=None, defender=None, defender_provisions=None):
    if (defender is None) != (defender_provisions is None):
        raise ValueError("siege finish provision terms must be complete")
    deltas = [
        _delta("siege_campaign", campaign.id, "phase", "sieging", phase),
        *(() if progress_days is None else
          (_delta("siege_campaign", campaign.id, "progress_days",
                  campaign.progress_days, progress_days),)),
        *(() if garrison_endurance is None else
          (_delta("siege_campaign", campaign.id, "garrison_endurance",
                  campaign.garrison_endurance, garrison_endurance),)),
    ]
    if defender is not None:
        deltas.append(_delta("detachment", defender.id, "provisions",
                             defender.provisions, defender_provisions))
    event = record_event(
        world, f"siege_campaign_{phase}",
        ("A tentativa de cerco cessou porque sua base material deixou de existir."
         if phase == "lapsed" else "O cerco concluiu sua brecha material; nenhuma administração foi transferida."),
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=tuple(deltas),
        cause_ids=_causes(campaign.last_event_id, *cause_ids))
    if defender is not None:
        world.society.detachments[defender.id] = defender.model_copy(
            update={"provisions": defender_provisions, "last_event_id": event.id})
    world.society.siege_campaigns[campaign.id] = campaign.model_copy(
        update={"phase": phase, "next_progress_day": None, "last_event_id": event.id,
                **({} if progress_days is None else {"progress_days": progress_days}),
                **({} if garrison_endurance is None else {"garrison_endurance": garrison_endurance})})
    return event


def resolve_siege_campaigns(world, situations):
    """Advance one dated day only after force upkeep retained the siege basis."""
    for situation in sorted(situations, key=lambda item: item.id):
        campaign = world.society.siege_campaigns.get(situation.id)
        if (situation.kind != PROGRESS_KIND or campaign is None or campaign.phase != "sieging"
                or campaign.next_progress_day != world.clock.absolute_day):
            raise ValueError("unknown or inconsistent siege campaign")
        parts = _current_parts(world, campaign)
        if (parts is None or not can_actor_act_for(world, campaign.attacker_ref,
                                                    campaign.attacker_ref, "military")):
            _finish(world, campaign, "lapsed")
            continue
        attacker, garrison, investment, defender = parts
        progress = campaign.progress_days + 1
        endurance = max(0, campaign.garrison_endurance - _garrison_wear(campaign, attacker, defender))
        blockade_rations = min(
            defender.provisions,
            defender.count * SIEGE_BLOCKADE_RATION_PER_SOLDIER,
        )
        defender_provisions = defender.provisions - blockade_rations
        if endurance == 0:
            breach = _finish(world, campaign, "breached",
                             cause_ids=(attacker.last_event_id, garrison.last_event_id,
                                        defender.last_event_id, investment.last_event_id),
                             progress_days=progress, garrison_endurance=endurance,
                             defender=defender, defender_provisions=defender_provisions)
            collapse_garrison_for_siege(world, garrison.id, campaign_event_id=breach.id)
            continue
        event = record_event(
            world, "siege_campaign_progressed",
            "O cerco desgastou a guarnição pela pressão material sustentada.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("siege_campaign", campaign.id, "progress_days", campaign.progress_days, progress),
                    _delta("siege_campaign", campaign.id, "garrison_endurance",
                           campaign.garrison_endurance, endurance),
                    _delta("detachment", defender.id, "provisions", defender.provisions,
                           defender_provisions)),
            cause_ids=_causes(campaign.last_event_id, attacker.last_event_id, garrison.last_event_id,
                              defender.last_event_id, investment.last_event_id))
        world.society.detachments[defender.id] = defender.model_copy(
            update={"provisions": defender_provisions, "last_event_id": event.id})
        updated = campaign.model_copy(update={"progress_days": progress, "garrison_endurance": endurance,
                                               "next_progress_day": world.clock.absolute_day + 1,
                                               "last_event_id": event.id})
        world.society.siege_campaigns[campaign.id] = updated
        world.agenda.schedule(ScheduledSituation(campaign.id, PROGRESS_KIND, updated.next_progress_day))


__all__ = ["BEGIN_ACTION", "OCCUPY_AFTER_BREACH_ACTION", "WITHDRAW_SIEGE_ACTION", "SiegeCampaignOption",
           "SiegeOccupationOption", "SiegeWithdrawalOption", "begin_siege_campaign", "occupy_after_siege_breach",
           "siege_campaign_withdrawal_options", "withdraw_siege_campaign",
           "resolve_siege_campaigns", "siege_campaign_options", "siege_occupation_options",
           "siege_campaign_adapters"]
