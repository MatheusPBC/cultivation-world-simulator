"""A narrow, persistent siege built from existing force and garrison owners."""

from copy import deepcopy
import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment, Garrison
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (disband_detachment, establish_garrison, force_options,
                                    detect_force_standoffs, force_position_options,
                                    garrison_options, prepare_force_position)
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
    campaign_ceasefire_adapters,
    campaign_withdrawal_remediation_options,
    fulfill_campaign_ceasefire,
    offer_campaign_ceasefire,
    remediate_campaign_withdrawal,
    respond_campaign_ceasefire,
)
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.administration_concession import administration_concession_offer_options
from src.sim.medieval.research import learn_technology
from src.sim.medieval.territorial_control import (establish_territorial_control,
                                                   territorial_control_options, withdraw_territorial_control)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import defense_adoption_options
from src.systems.calendar_agenda import ScheduledSituation


ATTACKER = EntityRef("polity", "auren")
DEFENDER = EntityRef("polity", "escarlia")
TARGET = "ferroalto"
ROAD = "road-pontenegro-ferroalto"
OTHER_EXIT = "road-brumafria-ferroalto"


def decide(world, option):
    return record_event(world, "siege_campaign_decided", "Decisão militar institucional.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(),
                        causal_payload={"decision_source": {"kind": "api"}})


def tick(world):
    world.clock = world.clock.advance(1)
    resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))


def _prepared_attacker(world, *, count=40, provisions=160, actor=ATTACKER, location=TARGET):
    # The campaign fixture premise is a column already deployed here from its
    # source cohort, which remains separate from the target's local garrison.
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == "campomanso")
    soldier_id = f"pop:campomanso:{group.people}:soldier"
    world.society.population[soldier_id] = group.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": count})
    arrival = record_event(
        world, "test_siege_attacker_present", "Fixture factual de uma coluna atacante presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "test_force_presence",
            "source_refs": [{"kind": "scenario", "id": "siege_fixture"},
                            {"kind": "population_group", "id": soldier_id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("detachment", f"detachment:test-siege-attacker:{actor.id}:{location}",
                       "stage", None, "present"),))
    detachment = Detachment(
        id=f"detachment:test-siege-attacker:{actor.id}:{location}", owner_ref=actor,
        source_group_id=soldier_id, count=count,
        location_id=location, destination_id=location, route_ids=(), route_index=0, provisions=provisions,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=arrival.id, last_event_id=arrival.id)
    world.society.detachments[detachment.id] = detachment
    position = next(item for item in force_position_options(world, actor, detachment_id=detachment.id)
                    if item.anchor_site_id is None)
    prepare_force_position(world, actor, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    world.agenda.cancel(detachment.id)
    current = world.society.detachments[detachment.id].model_copy(
        update={"due_day": world.clock.absolute_day + 1})
    world.society.detachments[detachment.id] = current
    world.agenda.schedule(ScheduledSituation(current.id, "force", current.due_day))
    location_region = world.society.settlements[location].region_id
    route_ids = tuple(sorted(route.id for route in world.map.routes.values()
                             if location_region in route.endpoint_region_ids))
    refresh_route_reports(world, route_ids=route_ids)
    return current.id


def _defending_garrison(world, *, count=20, provisions=160, owner=DEFENDER, location=TARGET):
    group = next(item for item in world.society.population.values() if item.settlement_id == location)
    soldier_id = f"pop:{location}:{group.people}:soldier"
    world.society.population[soldier_id] = group.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": count})
    detachment_id = f"detachment:test-siege-defender:{owner.id}:{location}"
    arrival = record_event(
        world, "test_siege_defender_present", "Fixture factual de uma guarnição defensora presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "test_force_presence",
            "source_refs": [{"kind": "scenario", "id": "siege_fixture"},
                            {"kind": "population_group", "id": soldier_id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("detachment", detachment_id, "stage", None, "present"),))
    detachment = Detachment(
        id=detachment_id, owner_ref=owner, source_group_id=soldier_id, count=count,
        location_id=location, destination_id=location, route_ids=(), route_index=0, provisions=provisions,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 1,
        decision_event_id=arrival.id, last_event_id=arrival.id)
    world.society.detachments[detachment.id] = detachment
    world.agenda.schedule(ScheduledSituation(detachment.id, "force", detachment.due_day))
    settlement = world.society.settlements[location]
    world.society.settlements[location] = settlement.model_copy(update={"occupier_id": owner.id})
    account = next(item for item in world.economy.accounts.values() if item.owner_ref == owner)
    garrison_id = f"garrison:{detachment.id}"
    decision = record_event(
        world, "garrison_decided", "Decisão defensiva do fixture.", fact_kind=FactKind.DECISION,
        decision={"action": "establish_garrison", "actor_ref": owner.to_dict(),
                  "selected_affordance_id": f"garrison:{detachment.id}:fixture"})
    garrison = Garrison(id=garrison_id, detachment_id=detachment.id, settlement_id=location,
                        account_id=account.id, decision_event_id=decision.id,
                        started_day=world.clock.absolute_day, last_event_id="pending")
    established = record_event(
        world, "garrison_established", "Fixture material de guarnição ativa.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("garrison", garrison.id, "stage", None, "active"),
                _delta("garrison", garrison.id, "settlement_id", None, location),
                _delta("garrison", garrison.id, "detachment_id", None, detachment.id)),
        cause_ids=(decision.id, arrival.id))
    world.society.garrisons[garrison.id] = garrison.model_copy(update={"last_event_id": established.id})
    return garrison.id


def siege_world(*, attacker_count=40, attacker_provisions=160, defender_count=20, defender_provisions=160,
                defender_prepared=False, invest=True):
    world = create_medieval_world(211)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    attacker_id = _prepared_attacker(world, count=attacker_count, provisions=attacker_provisions)
    garrison_id = _defending_garrison(world, count=defender_count, provisions=defender_provisions)
    if defender_prepared:
        defender_id = world.society.garrisons[garrison_id].detachment_id
        position = next(item for item in force_position_options(world, DEFENDER, detachment_id=defender_id)
                        if item.anchor_site_id is None)
        prepare_force_position(world, DEFENDER, position.id, decide(world, position).id)
        for _ in range(3):
            tick(world)
    if not invest:
        return world, attacker_id, garrison_id, None
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


def test_own_administered_city_can_pressure_foreign_occupier_then_retake_it(tmp_path):
    world = create_medieval_world(211)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    attacker_id = _prepared_attacker(world)
    settlement = world.society.settlements[TARGET]
    assert settlement.administrator_id == DEFENDER.id and settlement.occupier_id is None
    record_event(world, "test_city_administration_premise", "Fixture factual de administração própria.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "test_settlement_administration",
                     "source_refs": [{"kind": "scenario", "id": "siege_fixture"},
                                     {"kind": "settlement", "id": TARGET},
                                     {"kind": "polity", "id": ATTACKER.id}],
                     "observed_day": world.clock.absolute_day,
                 }},
                 deltas=(_delta("settlement", TARGET, "administrator_id", DEFENDER.id, ATTACKER.id),))
    world.society.settlements[TARGET] = settlement.model_copy(update={"administrator_id": ATTACKER.id})
    refresh_settlement_reports(world)
    assert not settlement_investment_options(world, ATTACKER, detachment_id=attacker_id)

    occupation = record_event(
        world, "test_foreign_occupation_premise", "Fixture factual de ocupação estrangeira.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "test_settlement_occupation",
            "source_refs": [{"kind": "scenario", "id": "siege_fixture"},
                            {"kind": "settlement", "id": TARGET},
                            {"kind": "polity", "id": DEFENDER.id}],
            "observed_day": world.clock.absolute_day,
        }},
        deltas=(_delta("settlement", TARGET, "occupier_id", None, DEFENDER.id),))
    garrison_id = _defending_garrison(world)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    report = world.knowledge.settlement_report(ATTACKER, TARGET)
    assert report.occupier_id == DEFENDER.id
    assert occupation.id in {link.cause_event_id
                             for link in world.event_index()[report.event_id].causal_links}
    option = next(item for item in settlement_investment_options(world, ATTACKER,
                                                                  detachment_id=attacker_id)
                  if item.kind == "invest")
    stale = deepcopy(world)
    stale_decision = decide(stale, option)
    stand_down = next(item for item in force_options(stale, DEFENDER)
                      if item.kind == "disband" and item.detachment_id ==
                      stale.society.garrisons[garrison_id].detachment_id)
    disband_detachment(stale, DEFENDER, stand_down.id, decide(stale, stand_down).id)
    assert stale.society.settlements[TARGET].occupier_id is None
    before_refusal = world_snapshot(stale)
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_settlement_investment_option(stale, ATTACKER, option.id, stale_decision.id)
    assert world_snapshot(stale) == before_refusal
    assert not stale.society.settlement_investments

    investment = execute_settlement_investment_option(world, ATTACKER, option.id,
                                                      decide(world, option).id)
    investment_event = world.event_index()[investment.last_event_id]
    assert report.event_id in {link.cause_event_id for link in investment_event.causal_links}
    notice = next(item for item in world.knowledge.settlement_pressures_for_actor(DEFENDER)
                  if item.investment_id == investment.id)
    assert notice.recipient_ref == DEFENDER
    assert not any(item.investment_id == investment.id
                   for item in world.knowledge.settlement_pressures_for_actor(ATTACKER))
    siege = next(item for item in siege_campaign_options(world, ATTACKER)
                 if item.investment_id == investment.id and item.defender_garrison_id == garrison_id)
    campaign = begin_siege_campaign(world, ATTACKER, siege.id, decide(world, siege).id)
    for _ in range(8):
        if world.society.siege_campaigns[campaign.id].phase == "breached":
            break
        tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "breached"
    refresh_settlement_reports(world)
    recovery = next(item for item in siege_occupation_options(world, ATTACKER)
                    if item.campaign_id == campaign.id)
    deterministic_copy = record_event(
        world, "siege_occupation_interpreted", "Payload idêntico sem escolha do ator.",
        fact_kind=FactKind.DECISION, decision=recovery.decision(),
        cause_ids=(recovery.campaign_event_id,))
    before_rejected_occupation = world_snapshot(world)
    with pytest.raises(ValueError, match="current actor decision"):
        occupy_after_siege_breach(world, ATTACKER, recovery.id, deterministic_copy.id)
    assert world_snapshot(world) == before_rejected_occupation

    occupied = occupy_after_siege_breach(world, ATTACKER, recovery.id,
                                         decide(world, recovery).id)
    assert world.society.settlements[TARGET].occupier_id == ATTACKER.id
    assert any(link.cause_event_id == world.society.siege_campaigns[campaign.id].last_event_id
               for link in occupied.causal_links)
    refresh_settlement_reports(world)
    assert not defense_adoption_options(world, ATTACKER)
    path = tmp_path / "recaptured-own-city.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def _teach_fortification(world):
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
        root = ({"root_premise": {
            "kind": "scenario_bootstrap", "domain": "test_technology_premise",
            "source_refs": [{"kind": "scenario", "id": "siege_fixture"},
                            {"kind": "polity", "id": DEFENDER.id}],
            "observed_day": world.clock.absolute_day,
        }} if not causes else None)
        learn_technology(world, DEFENDER, technology_id, "teaching", causes,
                         causal_payload=root)


def test_fortification_requires_prepared_supplied_position_for_bounded_defensive_step(tmp_path):
    world, _, _, option = siege_world()
    _teach_fortification(world)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    assert campaign.garrison_endurance == 12

    world, _, _, option = siege_world(defender_prepared=True)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    assert campaign.garrison_endurance == 12

    world, _, garrison_id, option = siege_world(defender_prepared=True)
    position_id = f"force-position:{world.society.garrisons[garrison_id].detachment_id}"
    position = world.society.force_positions[position_id]
    assert position.stage == "prepared"
    _teach_fortification(world)
    knowledge = next(item for item in world.knowledge.technologies.values()
                     if item.owner_ref == DEFENDER and item.technology_id == "fortification")
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    assert campaign.garrison_endurance == 14
    start = next(item for item in world.events if item.id == campaign.last_event_id)
    assert any(delta.aspect == "garrison_endurance" and delta.after == "14" for delta in start.deltas)
    causes = {link.cause_event_id for link in start.causal_links}
    assert {position.last_event_id, knowledge.event_id} <= causes
    path = tmp_path / "fortified-siege.mws"
    save_world(world, path)
    loaded = load_world(path)
    assert loaded.society.siege_campaigns[campaign.id].garrison_endurance == 14


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


def test_breach_lapses_defender_territorial_control_without_transferring_occupation():
    world, _, garrison_id, siege_option = siege_world()
    refresh_settlement_reports(world)
    control_option = next(item for item in territorial_control_options(world, DEFENDER)
                          if item.settlement_id == TARGET)
    control = establish_territorial_control(
        world, DEFENDER, control_option.id, decide(world, control_option).id)
    administrator = world.society.settlements[TARGET].administrator_id

    begin_siege_campaign(world, ATTACKER, siege_option.id, decide(world, siege_option).id)
    for _ in range(3):
        tick(world)

    collapsed = world.society.garrisons[garrison_id]
    current_control = world.society.territorial_controls[control.id]
    assert collapsed.stage == "collapsed"
    assert current_control.stage == "lapsed"
    assert world.society.settlements[TARGET].occupier_id == DEFENDER.id
    assert world.society.settlements[TARGET].administrator_id == administrator
    lapse = world.event_index()[current_control.last_event_id]
    collapse = world.event_index()[collapsed.last_event_id]
    assert lapse.event_type == "territorial_control_lapsed"
    assert collapse.event_type == "garrison_collapsed"
    assert collapse.id in {link.cause_event_id for link in lapse.causal_links}
    world.society.validate(set(world.map.regions), world)


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
    begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
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


def test_live_contact_turn_composes_mutual_ceasefire_and_independent_withdrawals(tmp_path, monkeypatch):
    world, attacker_id, garrison_id, option = siege_world()
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 5000,
    })
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    notices = detect_force_standoffs(world, attacker_id)
    assert notices
    assert {notice.recipient_ref for notice in world.knowledge.force_contact_notices.values()
            if notice.settlement_id == TARGET} == {ATTACKER, DEFENDER}
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)

    provider_choices = []

    async def choose_from_current_menu(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        actor = EntityRef(**payload["you_are"])
        labels = [choice["label"] for choice in payload["choices"]]
        campaign_context = payload.get("situation", {}).get("campaign_ceasefire_options", [])
        reported_phase = campaign_context[0]["campaign_phase"] if campaign_context else None
        wanted = None
        if actor == ATTACKER:
            wanted = next((label for label in labels if label == "Propor cessar-fogo mútuo."), None)
        elif actor == DEFENDER:
            wanted = next((label for label in labels if label == "Aceitar o cessar-fogo."), None)
        if reported_phase in {"breached", "withdrawn"}:
            if actor == ATTACKER and any(label.startswith("Cumprir a retirada material") for label in labels):
                wanted = next(label for label in labels if label.startswith("Cumprir a retirada material"))
            elif (actor == DEFENDER
                  and world.society.detachments[attacker_id].stage == "marching"
                  and any(label.startswith("Cumprir a retirada material") for label in labels)):
                wanted = next(label for label in labels if label.startswith("Cumprir a retirada material"))
        selected = next((choice["id"] for choice in payload["choices"]
                         if choice["label"] == wanted), ai_decider.NO_ACTION)
        provider_choices.append((actor, wanted, selected, tuple(labels), reported_phase))
        return {"selected_id": selected}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_from_current_menu)
    engine = MedievalSimulator(world)
    async def advance_until_ceasefire_completes():
        for _ in range(12):
            proposals = [item for item in world.relations.proposals.values()
                         if item.proposal_kind == "campaign_ceasefire" and item.status == "accepted"]
            obligations = [item for item in world.relations.obligations.values()
                           if item.proposal_id in {proposal.id for proposal in proposals}]
            if (proposals and len(obligations) == 2
                    and all(item.status == "fulfilled" for item in obligations)):
                return proposals
            await engine.step()
        pytest.fail(f"bilateral ceasefire did not finish; phase={world.society.siege_campaigns[campaign.id].phase}; "
                    f"selected={[call[:3] for call in provider_choices if call[2] != ai_decider.NO_ACTION]}; "
                    f"proposals={[(item.proposal_kind, item.status) for item in world.relations.proposals.values()]}; "
                    f"recent={[event.event_type for event in world.events[-20:]]}")

    proposals = asyncio.run(advance_until_ceasefire_completes())

    proposal = proposals[0]
    assert proposal.status == "accepted"
    assert world.society.siege_campaigns[campaign.id].phase == "withdrawn"
    assert world.society.garrisons[garrison_id].stage == "collapsed"
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.settlements[TARGET].administrator_id == DEFENDER.id
    defender_id = garrison_id.removeprefix("garrison:")
    for detachment_id in (attacker_id, defender_id):
        detachment = world.society.detachments[detachment_id]
        assert detachment.stage in {"marching", "present"}
        if detachment.stage == "present":
            assert detachment.location_id != TARGET
    decisions = [event for event in world.events if event.event_type == "force_standoff_decided"
                 and event.decision is not None]
    selected_actions = [event.decision.get("action") for event in decisions]
    assert selected_actions.count("offer_campaign_ceasefire") == 1
    assert selected_actions.count("respond_campaign_ceasefire") == 1
    assert selected_actions.count("fulfill_campaign_ceasefire") == 2
    fulfillment_phases = {call[0]: call[4] for call in provider_choices
                          if call[1] is not None and call[1].startswith("Cumprir a retirada material")}
    assert fulfillment_phases == {ATTACKER: "breached", DEFENDER: "withdrawn"}
    withdrawals = [event for event in world.events if event.event_type == "detachment_withdrawal_started"]
    assert {delta.owner_id for event in withdrawals for delta in event.deltas
            if delta.aspect == "stage" and delta.after == "marching"} >= {attacker_id, defender_id}
    breach_event = next(event for event in world.events if event.event_type == "siege_campaign_breached"
                        and event.day <= world.clock.absolute_day)
    assert all(breach_event.sequence < event.sequence for event in withdrawals)
    fulfillment_decisions = {event.decision.get("actor_ref")["id"]: event.id for event in decisions
                             if event.decision.get("action") == "fulfill_campaign_ceasefire"}
    for detachment_id, actor_id in ((attacker_id, ATTACKER.id), (defender_id, DEFENDER.id)):
        withdrawal = next(event for event in withdrawals if any(
            delta.owner_id == detachment_id and delta.aspect == "stage" and delta.after == "marching"
            for delta in event.deltas))
        assert fulfillment_decisions[actor_id] in {
            link.cause_event_id for link in withdrawal.causal_links
        }
    assert not any(event.event_type.startswith("fixture_") for event in world.events)

    path = tmp_path / "live-contact-mutual-ceasefire.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_campaign_ceasefire_withdraws_attacker_garrison_before_moving_its_force(tmp_path):
    world, attacker_id, defender_garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    for _ in range(3):
        tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "breached"
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    occupation = next(item for item in siege_occupation_options(world, ATTACKER)
                     if item.campaign_id == campaign.id)
    occupy_after_siege_breach(world, ATTACKER, occupation.id, decide(world, occupation).id)
    refresh_settlement_reports(world)
    establish = next(item for item in garrison_options(world, ATTACKER)
                     if item.detachment_id == attacker_id and item.kind == "garrison")
    establish_garrison(world, ATTACKER, establish.id, decide(world, establish).id)
    assert world.society.garrisons[f"garrison:{attacker_id}"].stage == "active"

    offer = next(item for item in campaign_ceasefire_offer_options(world, ATTACKER)
                 if item.campaign_id == campaign.id and item.kind == "mutual")
    proposal = offer_campaign_ceasefire(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in campaign_ceasefire_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    respond_campaign_ceasefire(world, DEFENDER, response.id, decide(world, response).id)

    attacker_exit = next(item for item in campaign_ceasefire_fulfillment_options(world, ATTACKER)
                         if item.campaign_id == campaign.id)
    attacker_obligation = fulfill_campaign_ceasefire(
        world, ATTACKER, attacker_exit.id, decide(world, attacker_exit).id)
    assert attacker_obligation.status == "fulfilled"
    attacker_garrison = world.society.garrisons[f"garrison:{attacker_id}"]
    assert attacker_garrison.stage == "withdrawn"
    assert world.society.detachments[attacker_id].stage == "marching"
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.settlements[TARGET].administrator_id == DEFENDER.id
    ceasefire_decision = next(event for event in world.events if event.fact_kind == FactKind.DECISION
                              and event.decision is not None
                              and event.decision.get("selected_affordance_id") == attacker_exit.id)
    garrison_exit = world.event_index()[attacker_garrison.last_event_id]
    assert garrison_exit.causal_payload["decision_event_id"] == ceasefire_decision.id
    assert garrison_exit.causal_payload["selected_affordance_id"] == attacker_exit.id
    campaign_exit = world.event_index()[world.society.siege_campaigns[campaign.id].last_event_id]
    assert garrison_exit.id in {link.cause_event_id for link in campaign_exit.causal_links}

    refresh_route_reports(world)
    refresh_settlement_reports(world)
    defender_id = world.society.garrisons[defender_garrison_id].detachment_id
    defender_exit = next(item for item in campaign_ceasefire_fulfillment_options(world, DEFENDER)
                         if item.campaign_id == campaign.id)
    defender_obligation = fulfill_campaign_ceasefire(
        world, DEFENDER, defender_exit.id, decide(world, defender_exit).id)
    assert defender_obligation.status == "fulfilled"
    assert world.society.garrisons[defender_garrison_id].stage == "collapsed"
    assert world.society.detachments[defender_id].stage == "marching"

    path = tmp_path / "campaign-ceasefire-after-occupation.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True


def test_defender_can_initiate_a_ceasefire_when_its_own_exit_is_current(monkeypatch):
    world, _, garrison_id, option = siege_world()
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    defender_detachment = world.society.garrisons[garrison_id].detachment_id
    from src.sim.medieval.force import WithdrawalOption

    exit_option = WithdrawalOption(
        id=f"withdraw:{defender_detachment}:fixture",
        actor_ref=DEFENDER,
        detachment_id=defender_detachment,
        destination_id="brumafria",
        route_ids=(OTHER_EXIT,),
    )
    monkeypatch.setattr(
        "src.sim.medieval.campaign_ceasefire.withdrawal_options",
        lambda *_args, **_kwargs: (exit_option,),
    )

    offer = next(item for item in campaign_ceasefire_offer_options(world, DEFENDER)
                 if item.kind == "mutual")
    proposal = offer_campaign_ceasefire(world, DEFENDER, offer.id, decide(world, offer).id)

    assert proposal.proposer_ref == DEFENDER
    assert {clause.debtor_ref for clause in proposal.clauses} == {ATTACKER, DEFENDER}
    assert {clause.detachment_id for clause in proposal.clauses} == {
        campaign.attacker_detachment_id, defender_detachment,
    }


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


def test_breached_campaign_can_offer_mutual_ceasefire_before_occupation():
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
    assert any(item.campaign_id == campaign.id and item.kind == "mutual" for item in offers)

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


def test_collapsed_garrison_can_still_fulfill_ceasefire_by_withdrawing_its_force():
    """A collapsed duty does not erase the defender's physically present force."""
    world, _, garrison_id, option = siege_world()
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

    # The siege keeps progressing after acceptance; the garrison collapses
    # under blockade pressure before either owner fulfils its withdrawal.
    for _ in range(3):
        tick(world)
    assert world.society.siege_campaigns[campaign.id].phase == "breached"
    assert world.society.garrisons[garrison_id].stage == "collapsed"

    # The defender's exit becomes physically usable only after the attacker
    # independently fulfills its own withdrawal and lifts the investment.
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    attacker_option = next(item for item in campaign_ceasefire_fulfillment_options(world, ATTACKER)
                           if item.campaign_id == campaign.id)
    attacker_result = fulfill_campaign_ceasefire(
        world, ATTACKER, attacker_option.id, decide(world, attacker_option).id)
    assert attacker_result.status == "fulfilled"
    assert world.society.siege_campaigns[campaign.id].phase == "withdrawn"
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    # The duty collapsed, but the detachment remains present and can choose a
    # valid exit to fulfill its accepted term.
    options = campaign_ceasefire_fulfillment_options(world, DEFENDER)
    assert any(item.campaign_id == campaign.id for item in options)
    obligation = next(item for item in world.relations.obligations.values()
                      if item.proposal_id == proposal.id and item.clause_index == 1)
    assert obligation.status == "active"
    fulfillment = next(item for item in options if item.campaign_id == campaign.id)
    result = fulfill_campaign_ceasefire(
        world, DEFENDER, fulfillment.id, decide(world, fulfillment).id)
    assert result.status == "fulfilled"
    defender_id = garrison_id.removeprefix("garrison:")
    assert world.society.detachments[defender_id].stage == "marching"
    assert world.society.garrisons[garrison_id].stage == "collapsed"
    assert world.society.siege_campaigns[campaign.id].phase == "withdrawn"


def test_breached_campaign_withdrawal_can_be_materially_remediated_without_erasing_breach(tmp_path):
    world, attacker_id, _, option = siege_world(attacker_provisions=1200)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    offer = next(item for item in campaign_ceasefire_offer_options(world, ATTACKER)
                 if item.campaign_id == campaign.id and item.kind == "mutual")
    proposal = offer_campaign_ceasefire(world, ATTACKER, offer.id, decide(world, offer).id)
    response = next(item for item in campaign_ceasefire_response_options(world, DEFENDER)
                    if item.proposal_id == proposal.id and item.response == "accept")
    respond_campaign_ceasefire(world, DEFENDER, response.id, decide(world, response).id)

    # The siege breaches first; neither party fulfills the promised exit by its
    # deadline. The attacker still has its own present, supplied column.
    clause = proposal.clauses[0]
    while world.clock.absolute_day <= clause.due_day:
        tick(world)
    obligation = world.relations.obligations[f"{proposal.id}:term:0"]
    assert obligation.status == "breached"
    breach = obligation.breach_event_id
    refresh_route_reports(world)
    refresh_settlement_reports(world)

    options = campaign_withdrawal_remediation_options(world, ATTACKER)
    selected = next(item for item in options if item.obligation_id == obligation.id)
    adapter = campaign_ceasefire_adapters()[0]
    assert selected.id in {item.id for item in adapter.options_fn(world, ATTACKER)}
    assert selected.id in {item.id for item in concurrent_civil_options(world, ATTACKER)}
    uninformed = deepcopy(world)
    uninformed.knowledge.notices = {
        key: notice for key, notice in uninformed.knowledge.notices.items()
        if not (notice.recipient_ref == ATTACKER and notice.event_id == breach)
    }
    assert not campaign_withdrawal_remediation_options(uninformed, ATTACKER)
    stale = deepcopy(world)
    stale_decision = decide(stale, selected)
    stale.map.routes[selected.route_ids[0]].update_runtime(capacity=0, quality=0)
    with pytest.raises(ValueError, match="stale or unknown"):
        remediate_campaign_withdrawal(stale, ATTACKER, selected.id, stale_decision.id)
    assert stale.relations.obligations[obligation.id].status == "breached"
    assert stale.society.detachments[attacker_id].stage == "present"

    repaired = remediate_campaign_withdrawal(
        world, ATTACKER, selected.id, decide(world, selected).id)

    assert repaired.status == "remediated"
    assert repaired.breach_event_id == breach
    assert repaired.remediation_material_event_id is not None
    assert world.society.detachments[attacker_id].stage == "marching"
    assert any(item.event_type == "commitment_breached" and item.id == breach for item in world.events)
    receipt = next(item for item in world.events if item.id == repaired.last_event_id)
    assert receipt.event_type == "campaign_withdrawal_remediated"
    assert {link.cause_event_id for link in receipt.causal_links} >= {breach, repaired.remediation_material_event_id}

    path = tmp_path / "campaign-withdrawal-remediated.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.relations.obligations[obligation.id].status == "remediated"
    assert restored.relations.obligations[obligation.id].breach_event_id == breach

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
    copied_decision = record_event(world, "copied_control_choice", "Affordance copiada sem autoria.",
                                   fact_kind=FactKind.DECISION, decision=control.decision())
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="current actor decision"):
        establish_territorial_control(world, ATTACKER, control.id, copied_decision.id)
    assert world_snapshot(world) == before

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
    copied_withdrawal = record_event(world, "copied_control_withdrawal", "Affordance copiada sem autoria.",
                                     fact_kind=FactKind.DECISION, decision=withdrawal.decision())
    before_withdrawal = world_snapshot(world)
    with pytest.raises(ValueError, match="current actor decision"):
        withdraw_territorial_control(world, ATTACKER, withdrawal.id, copied_withdrawal.id)
    assert world_snapshot(world) == before_withdrawal

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
