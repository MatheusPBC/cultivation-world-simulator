"""A narrow, persistent siege built from existing force and garrison owners."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment, Garrison
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (establish_garrison, force_position_options, garrison_options,
                                    prepare_force_position)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                     settlement_investment_options)
from src.sim.medieval.siege_campaign import (begin_siege_campaign, occupy_after_siege_breach,
                                              siege_campaign_adapters, siege_campaign_options,
                                              siege_campaign_withdrawal_options,
                                              siege_occupation_options, withdraw_siege_campaign)
from src.sim.medieval.campaign_ceasefire import (
    campaign_ceasefire_fulfillment_options,
    campaign_ceasefire_offer_options,
    campaign_ceasefire_response_options,
    fulfill_campaign_ceasefire,
    offer_campaign_ceasefire,
    respond_campaign_ceasefire,
)
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.administration_concession import administration_concession_offer_options
from src.sim.medieval.research import learn_technology
from src.sim.medieval.territorial_control import (establish_territorial_control,
                                                   territorial_control_options, withdraw_territorial_control)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.systems.calendar_agenda import ScheduledSituation


ATTACKER = EntityRef("polity", "auren")
DEFENDER = EntityRef("polity", "escarlia")
TARGET = "ferroalto"
ROAD = "road-pontenegro-ferroalto"
OTHER_EXIT = "road-brumafria-ferroalto"


def decide(world, option):
    return record_event(world, "siege_campaign_decided", "Decisão militar institucional.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def _prepared_attacker(world, *, count=40):
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    soldier_id = f"pop:campomanso:{group.people}:soldier"
    world.society.population[soldier_id] = group.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": count})
    arrival = record_event(
        world, "test_siege_attacker_present", "Fixture factual de uma coluna atacante presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", "detachment:test-siege-attacker", "stage", None, "present"),))
    detachment = Detachment(
        id="detachment:test-siege-attacker", owner_ref=ATTACKER, source_group_id=soldier_id, count=count,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0, provisions=160,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=arrival.id, last_event_id=arrival.id)
    world.society.detachments[detachment.id] = detachment
    position = force_position_options(world, ATTACKER, detachment_id=detachment.id)[0]
    prepare_force_position(world, ATTACKER, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    world.agenda.cancel(detachment.id)
    current = world.society.detachments[detachment.id].model_copy(
        update={"due_day": world.clock.absolute_day + 1})
    world.society.detachments[detachment.id] = current
    world.agenda.schedule(ScheduledSituation(current.id, "force", current.due_day))
    refresh_route_reports(world, route_ids=(ROAD, OTHER_EXIT))
    return current.id


def _defending_garrison(world, *, count=20, provisions=160):
    group = next(item for item in world.society.population.values() if item.settlement_id == TARGET)
    soldier_id = f"pop:{TARGET}:{group.people}:soldier"
    world.society.population[soldier_id] = group.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": count})
    detachment_id = "detachment:test-siege-defender"
    arrival = record_event(
        world, "test_siege_defender_present", "Fixture factual de uma guarnição defensora presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", detachment_id, "stage", None, "present"),))
    detachment = Detachment(
        id=detachment_id, owner_ref=DEFENDER, source_group_id=soldier_id, count=count,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0, provisions=provisions,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 1,
        decision_event_id=arrival.id, last_event_id=arrival.id)
    world.society.detachments[detachment.id] = detachment
    world.agenda.schedule(ScheduledSituation(detachment.id, "force", detachment.due_day))
    settlement = world.society.settlements[TARGET]
    world.society.settlements[TARGET] = settlement.model_copy(update={"occupier_id": DEFENDER.id})
    account = next(item for item in world.economy.accounts.values() if item.owner_ref == DEFENDER)
    garrison_id = f"garrison:{detachment.id}"
    decision = record_event(
        world, "garrison_decided", "Decisão defensiva do fixture.", fact_kind=FactKind.DECISION,
        decision={"action": "establish_garrison", "actor_ref": DEFENDER.to_dict(),
                  "selected_affordance_id": f"garrison:{detachment.id}:fixture"})
    garrison = Garrison(id=garrison_id, detachment_id=detachment.id, settlement_id=TARGET,
                        account_id=account.id, decision_event_id=decision.id,
                        started_day=world.clock.absolute_day, last_event_id="pending")
    established = record_event(
        world, "garrison_established", "Fixture material de guarnição ativa.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("garrison", garrison.id, "stage", None, "active"),
                _delta("garrison", garrison.id, "settlement_id", None, TARGET),
                _delta("garrison", garrison.id, "detachment_id", None, detachment.id)),
        cause_ids=(decision.id, arrival.id))
    world.society.garrisons[garrison.id] = garrison.model_copy(update={"last_event_id": established.id})
    return garrison.id


def siege_world(*, attacker_count=40, defender_count=20, defender_provisions=160):
    world = create_medieval_world(211)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    attacker_id = _prepared_attacker(world, count=attacker_count)
    garrison_id = _defending_garrison(world, count=defender_count, provisions=defender_provisions)
    investment = next(item for item in settlement_investment_options(world, ATTACKER, detachment_id=attacker_id)
                      if item.kind == "invest")
    execute_settlement_investment_option(world, ATTACKER, investment.id, decide(world, investment).id)
    option = next(item for item in siege_campaign_options(world, ATTACKER)
                  if item.defender_garrison_id == garrison_id)
    return world, attacker_id, garrison_id, option


def test_siege_start_is_registered_in_the_shared_institutional_menu():
    world, _, _, option = siege_world()
    adapter = siege_campaign_adapters()[0]
    offered = tuple(adapter.options_fn(world, ATTACKER))
    assert option.id in {item.id for item in offered}
    assert adapter.family_key() == "campaign"


def test_campaign_ceasefire_is_registered_in_the_shared_institutional_menu():
    names = {adapter.name for adapter in monthly_adapters()}
    assert "campaign_ceasefire" in names


def test_post_breach_occupation_and_control_share_the_campaign_menu():
    names = {adapter.name for adapter in siege_campaign_adapters()}
    assert {"siege_occupation", "territorial_control"} <= names


def test_fortification_knowledge_adds_one_bounded_defensive_siege_step():
    world, _, _, option = siege_world()
    for technology_id, action in (("field_drill", "teach field drill"),
                                  ("siegecraft", "teach siegecraft"),
                                  ("fortification", "teach fortification")):
        decision = record_event(
            world, "technology_training_decided", action,
            fact_kind=FactKind.DECISION,
            decision={"action": "research", "actor_ref": DEFENDER.to_dict(),
                      "technology_id": technology_id})
        causes = (decision.id,) if technology_id == "field_drill" else tuple(
            item.id for item in world.events
            if item.event_type == "technology_discovered" and item.id != decision.id)[-2:]
        learn_technology(world, DEFENDER, technology_id, "teaching", causes)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    assert campaign.garrison_endurance == 14
    start = next(item for item in world.events if item.id == campaign.last_event_id)
    assert any(delta.aspect == "garrison_endurance" and delta.after == "14" for delta in start.deltas)


def test_siege_campaign_persists_daily_progress_and_breach_collapses_garrison_without_control_transfer(tmp_path):
    world, _, garrison_id, option = siege_world()
    administrator = world.society.settlements[TARGET].administrator_id
    occupier = world.society.settlements[TARGET].occupier_id
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)

    tick(world)
    active = world.society.siege_campaigns[campaign.id]
    assert active.phase == "sieging" and active.progress_days == 1
    assert active.garrison_endurance == 7
    path = tmp_path / "siege-campaign.mws"
    save_world(world, path)
    world = load_world(path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    tick(world)
    tick(world)
    finished = world.society.siege_campaigns[campaign.id]
    assert finished.phase == "breached" and finished.progress_days == 3
    collapsed = world.society.garrisons[garrison_id]
    assert collapsed.stage == "collapsed"
    # The breach removes only the defensive duty.  The present defender has
    # not been displaced and the attacker has not acquired occupation or
    # administration merely because the endurance reading reached zero.
    assert world.society.detachments[collapsed.detachment_id].stage == "present"
    assert world.society.detachments[collapsed.detachment_id].location_id == TARGET
    assert world.society.settlements[TARGET].administrator_id == administrator
    assert world.society.settlements[TARGET].occupier_id == occupier
    assert any(event.event_type == "siege_campaign_breached" for event in world.events)
    breach = next(event for event in world.events if event.event_type == "siege_campaign_breached")
    assert any(delta.aspect == "garrison_endurance" and delta.before == "1" and delta.after == "0"
               for delta in breach.deltas)
    collapse = next(event for event in world.events if event.event_type == "garrison_collapsed")
    assert breach.id in {link.cause_event_id for link in collapse.causal_links}
    assert any(delta.owner_id == garrison_id and delta.aspect == "stage"
               and delta.before == "active" and delta.after == "collapsed"
               for delta in collapse.deltas)


def test_siege_breach_follows_force_supply_and_elapsed_pressure_not_a_fixed_day_count():
    world, _, _, option = siege_world(defender_count=60, defender_provisions=400)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)

    for _ in range(3):
        tick(world)

    active = world.society.siege_campaigns[campaign.id]
    assert active.phase == "sieging"
    assert active.progress_days == 3
    # The blockade has consumed the reserve by the third dated progress step,
    # so the defender no longer receives the small ration-reserve relief.
    assert active.garrison_endurance == 2
    progress = next(event for event in reversed(world.events) if event.event_type == "siege_campaign_progressed")
    assert any(delta.aspect == "garrison_endurance" and delta.after == "2"
               for delta in progress.deltas)


def test_siege_progress_consumes_a_bounded_blockade_ration_from_the_defender():
    world, _, garrison_id, option = siege_world(defender_count=20, defender_provisions=160)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    defender_id = world.society.garrisons[garrison_id].detachment_id
    before = world.society.detachments[defender_id].provisions

    tick(world)

    defender = world.society.detachments[defender_id]
    # Daily force upkeep consumed one ration per soldier first; the campaign
    # then applied one additional blockade ration per soldier.
    assert defender.provisions == before - 2 * defender.count
    progress = next(event for event in reversed(world.events)
                    if event.event_type == "siege_campaign_progressed")
    assert any(delta.owner_kind == "detachment" and delta.owner_id == defender_id
               and delta.aspect == "provisions" and delta.before == str(before - defender.count)
               and delta.after == str(defender.provisions)
               for delta in progress.deltas)


def test_active_siege_can_choose_material_withdrawal_without_transferring_control(tmp_path):
    world, attacker_id, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    # The owner must have a currently usable route home; reopen the known road
    # in this fixture so the campaign withdrawal affordance can be observed.
    world.map.routes[ROAD].update_runtime(capacity=80, quality=1)
    refresh_route_reports(world, route_ids=(ROAD,))
    refresh_settlement_reports(world)
    choices = tuple(item for item in siege_campaign_withdrawal_options(world, ATTACKER)
                    if item.campaign_id == campaign.id)
    assert choices
    selected = choices[0]
    withdrawn = withdraw_siege_campaign(world, ATTACKER, selected.id, decide(world, selected).id)
    assert withdrawn.phase == "withdrawn" and withdrawn.next_progress_day is None
    assert world.society.detachments[attacker_id].stage == "marching"
    assert world.society.detachments[attacker_id].destination_id == selected.destination_id
    assert world.society.settlements[TARGET].occupier_id == DEFENDER.id
    event = next(item for item in world.events if item.event_type == "siege_campaign_withdrawn")
    assert any(delta.aspect == "phase" and delta.before == "sieging" and delta.after == "withdrawn"
               for delta in event.deltas)
    withdrawal = next(item for item in world.events if item.event_type == "detachment_withdrawal_started")
    assert withdrawal.id in {link.cause_event_id for link in event.causal_links}
    path = tmp_path / "siege-withdrawal.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.society.siege_campaigns[campaign.id].phase == "withdrawn"
    assert restored.society.detachments[attacker_id].stage == "marching"


def test_campaign_ceasefire_is_accepted_then_each_owner_fulfills_its_own_withdrawal(tmp_path):
    world, attacker_id, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    offer = next(item for item in campaign_ceasefire_offer_options(world, ATTACKER)
                 if item.campaign_id == campaign.id and item.kind == "mutual")
    proposal = offer_campaign_ceasefire(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in campaign_ceasefire_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    proposal = respond_campaign_ceasefire(world, DEFENDER, response.id, decide(world, response).id)
    assert proposal.status == "accepted"

    attacker_fulfillment = next(item for item in campaign_ceasefire_fulfillment_options(world, ATTACKER)
                                if item.campaign_id == campaign.id)
    attacker_obligation = fulfill_campaign_ceasefire(
        world, ATTACKER, attacker_fulfillment.id, decide(world, attacker_fulfillment).id)
    assert attacker_obligation.status == "fulfilled"
    assert world.society.siege_campaigns[campaign.id].phase == "withdrawn"

    # Lifting the attacker's investment reopens the defender's route; its own
    # fulfillment withdraws the duty and then moves only its own detachment.
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    defender_fulfillment = next(item for item in campaign_ceasefire_fulfillment_options(world, DEFENDER)
                                if item.campaign_id == campaign.id)
    defender_obligation = fulfill_campaign_ceasefire(
        world, DEFENDER, defender_fulfillment.id, decide(world, defender_fulfillment).id)
    assert defender_obligation.status == "fulfilled"
    assert world.society.garrisons[garrison_id].stage == "withdrawn"
    assert world.society.detachments[garrison_id.replace("garrison:", "")].stage == "marching"
    assert world.society.settlements[TARGET].administrator_id == DEFENDER.id
    path = tmp_path / "campaign-ceasefire.mws"
    save_world(world, path)
    restored = load_world(path)
    restored_proposal = restored.relations.proposals[proposal.id]
    assert restored_proposal.proposal_kind == "campaign_ceasefire"
    assert all(clause.kind == "campaign_withdrawal" for clause in restored_proposal.clauses)


def test_breach_exposes_a_separate_occupation_choice_without_transferring_administration():
    world, _, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    refresh_settlement_reports(world)
    occupation = next(item for item in siege_occupation_options(world, ATTACKER)
                      if item.campaign_id == campaign.id)
    administrator = world.society.settlements[TARGET].administrator_id
    event = occupy_after_siege_breach(world, ATTACKER, occupation.id, decide(world, occupation).id)
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert world.society.settlements[TARGET].administrator_id == administrator
    breach = next(item for item in world.events if item.event_type == "siege_campaign_breached")
    assert breach.id in {link.cause_event_id for link in event.causal_links}
    assert any(delta.owner_id == TARGET and delta.aspect == "occupier_id"
               and delta.before == DEFENDER.id and delta.after == ATTACKER.id for delta in event.deltas)


def test_breached_campaign_can_still_withdraw_before_occupation():
    world, attacker_id, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "breached"

    world.map.routes[ROAD].update_runtime(capacity=80, quality=1)
    refresh_route_reports(world, route_ids=(ROAD,))
    refresh_settlement_reports(world)
    selected = next(item for item in siege_campaign_withdrawal_options(world, ATTACKER)
                    if item.campaign_id == campaign.id)
    withdrawn = withdraw_siege_campaign(world, ATTACKER, selected.id, decide(world, selected).id)

    assert withdrawn.phase == "withdrawn"
    assert world.society.detachments[attacker_id].stage == "marching"
    event = next(item for item in world.events if item.event_type == "siege_campaign_withdrawn")
    assert any(delta.aspect == "phase" and delta.before == "breached" and delta.after == "withdrawn"
               for delta in event.deltas)


def test_breached_campaign_can_offer_unilateral_ceasefire_before_occupation():
    world, attacker_id, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "breached"

    world.map.routes[ROAD].update_runtime(capacity=80, quality=1)
    refresh_route_reports(world, route_ids=(ROAD,))
    refresh_settlement_reports(world)
    offers = campaign_ceasefire_offer_options(world, ATTACKER)
    assert any(item.campaign_id == campaign.id and item.kind == "unilateral_self" for item in offers)
    assert not any(item.campaign_id == campaign.id and item.kind == "mutual" for item in offers)

    offer = next(item for item in offers if item.campaign_id == campaign.id)
    proposal = offer_campaign_ceasefire(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in campaign_ceasefire_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    proposal = respond_campaign_ceasefire(world, DEFENDER, response.id, decide(world, response).id)
    fulfillment = next(item for item in campaign_ceasefire_fulfillment_options(world, ATTACKER)
                        if item.campaign_id == campaign.id)
    obligation = fulfill_campaign_ceasefire(world, ATTACKER, fulfillment.id, decide(world, fulfillment).id)

    assert proposal.status == "accepted"
    assert obligation.status == "fulfilled"
    assert world.society.siege_campaigns[campaign.id].phase == "withdrawn"
    assert world.society.detachments[attacker_id].stage == "marching"
    assert world.society.settlements[TARGET].administrator_id == DEFENDER.id


def test_post_occupation_administration_concession_remains_a_current_affordance():
    """A breach/occupation opens negotiation; it never transfers governance."""
    world, _, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    refresh_settlement_reports(world)
    occupation = next(item for item in siege_occupation_options(world, ATTACKER)
                      if item.campaign_id == campaign.id)
    occupy_after_siege_breach(world, ATTACKER, occupation.id, decide(world, occupation).id)

    offers = administration_concession_offer_options(world, ATTACKER)
    assert offers and all(item.settlement_id == TARGET for item in offers)
    assert world.society.settlements[TARGET].administrator_id == DEFENDER.id


def test_occupied_settlement_can_acquire_durable_control_only_after_a_paid_garrison(tmp_path):
    world, _, _, option = siege_world()
    administrator = world.society.settlements[TARGET].administrator_id
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    refresh_settlement_reports(world)
    occupation = next(item for item in siege_occupation_options(world, ATTACKER)
                      if item.campaign_id == campaign.id)
    occupy_after_siege_breach(world, ATTACKER, occupation.id, decide(world, occupation).id)
    refresh_settlement_reports(world)
    garrison = next(item for item in garrison_options(world, ATTACKER) if item.settlement_id == TARGET)
    establish_garrison(world, ATTACKER, garrison.id, decide(world, garrison).id)
    refresh_settlement_reports(world)
    control = next(item for item in territorial_control_options(world, ATTACKER) if item.settlement_id == TARGET)
    established = establish_territorial_control(world, ATTACKER, control.id, decide(world, control).id)

    assert established.stage == "active"
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert world.society.settlements[TARGET].administrator_id == administrator
    assert any(item.event_type == "territorial_control_established" for item in world.events)
    path = tmp_path / "territorial-control.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.society.territorial_controls[established.id].stage == "active"
    assert restored.society.settlements[TARGET].administrator_id == administrator

    withdrawal = next(item for item in territorial_control_options(world, ATTACKER)
                      if item.kind == "withdraw" and item.settlement_id == TARGET)
    ended = withdraw_territorial_control(world, ATTACKER, withdrawal.id, decide(world, withdrawal).id)
    assert ended.stage == "withdrawn"
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert world.society.settlements[TARGET].administrator_id == administrator


def test_siege_start_revalidates_the_current_garrison_and_lapses_when_force_fails():
    world, attacker_id, garrison_id, option = siege_world()
    world.society.garrisons[garrison_id] = world.society.garrisons[garrison_id].model_copy(update={"stage": "lapsed"})
    with pytest.raises(ValueError, match="stale or unknown"):
        begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    assert not world.society.siege_campaigns

    world, attacker_id, _, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    attacker = world.society.detachments[attacker_id]
    world.society.detachments[attacker_id] = attacker.model_copy(update={"provisions": 0})
    tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "lapsed"
    assert any(event.event_type == "siege_campaign_lapsed" for event in world.events)
