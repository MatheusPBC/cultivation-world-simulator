"""Critical causal coverage for the deliberately small civic-demand vertical."""

from pathlib import Path

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.civic_protest import (civic_protest_options, civic_refusal_options,
                                            open_civic_protest, refuse_civic_demand)
from src.sim.medieval.civic_tumult import civic_tumult_options, execute_civic_tumult
from src.sim.medieval.civic_movement import (civic_movement_dissolve_options,
                                             civic_movement_options,
                                             civic_movement_join_options,
                                             dissolve_civic_movement,
                                             form_civic_movement,
                                             join_civic_movement,
                                             civic_rebellion_options,
                                             declare_civic_rebellion,
                                             civic_revolution_options,
                                             declare_civic_revolution,
                                             civic_rebellion_response_options,
                                             suppress_civic_rebellion,
                                             respond_civic_rebellion)
from src.sim.medieval.civic_strike import (civic_general_strike_options,
                                           start_general_strike)
from src.sim.medieval.civic_amnesty import civic_amnesty_options, grant_civic_amnesty
from src.sim.medieval.civic_protest_policy import _admin_situation
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.logistics import queue_freight
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_institutional_aid import _breached_aid_world


PLACE = "pedraclara"
ADMIN = EntityRef("polity", "auren")
ROAD = "road-campomanso-pedraclara"


def _decide(world, option):
    return record_event(world, "civic_protest_decided", "Decisão cívica delimitada.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def _pressured(world):
    need = world.economy.needs[PLACE]
    world.economy.needs[PLACE] = need.model_copy(update={"missing_food": 8, "unrest": 350})
    group = next(item for item in world.society.population.values()
                 if item.settlement_id == PLACE and item.count >= 5)
    return group


def _join_second_group(world, movement):
    candidate = next(
        group for group in sorted(world.society.population.values(), key=lambda item: item.id)
        if group.settlement_id == movement.settlement_id
        and group.id not in movement.member_group_ids
        and civic_movement_join_options(world, group.id)
    )
    option = civic_movement_join_options(world, candidate.id)[0]
    decision = record_event(world, "civic_movement_join_decided", "Um grupo consentiu em entrar.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(movement.last_event_id, option.report_event_id))
    return join_civic_movement(world, candidate.id, option.id, decision.id)


def _tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def test_protest_does_not_reserve_a_group_already_committed_elsewhere(monkeypatch):
    world = create_medieval_world(73)
    group = _pressured(world)
    original = world.society.available_count

    def partially_reserved(group_id):
        return (group.count - 1 if group_id == group.id else original(group_id))

    monkeypatch.setattr(world.society, "available_count", partially_reserved)
    assert civic_protest_options(world, group.id) == ()


def test_administrator_civic_context_contains_only_known_institutional_memory():
    world, _ = _breached_aid_world()
    situation = _admin_situation(world, ADMIN, ())
    # The breach helper uses Auren as the creditor and creates its canonical
    # notice.  The context must expose the derived reading only after that
    # notice is addressed to this administrator; no raw obligation/private
    # balance is copied into the civic prompt.
    assert situation["institutional_memory"]
    assert all(set(item) == {"institution_ref", "reading", "event_ids"}
               for item in situation["institutional_memory"])
    assert all("balance" not in item and "stock" not in item
               for item in situation["institutional_memory"])


def test_opening_requires_own_reading_reserves_only_work_and_notifies_admin_privately():
    world = create_medieval_world(73)
    group = _pressured(world)
    assert not civic_protest_options(world, group.id), "canonical distress alone never starts a protest"
    refresh_settlement_reports(world)
    option = civic_protest_options(world, group.id)[0]
    original_available = world.society.available_count(group.id)
    original_unrest = world.economy.needs[PLACE].unrest
    money = sum(account.balance for account in world.economy.accounts.values())
    stocks = {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()}
    government = world.society.settlements[PLACE].administrator_id

    decision = _decide(world, option)
    with pytest.raises(ValueError, match="stale|unknown"):
        open_civic_protest(world, group.id, option.id + ":forged", decision.id)
    protest = open_civic_protest(world, group.id, option.id, decision.id)
    assert protest.participants == 5 and protest.stage == "open"
    assert world.society.available_count(group.id) == original_available - protest.participants
    assert sum(account.balance for account in world.economy.accounts.values()) == money
    assert {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()} == stocks
    assert world.society.settlements[PLACE].administrator_id == government

    notice = next(iter(world.knowledge.civic_demand_notices.values()))
    assert notice.recipient_ref == ADMIN and notice.group_id == group.id and notice.food_quantity == 8
    assert set(notice.model_dump()) == {"id", "recipient_ref", "protest_id", "group_id", "settlement_id",
                                        "demand_kind", "food_quantity", "site_id", "due_day", "learned_day",
                                        "event_id", "channel"}
    local = world.knowledge.settlement_report(EntityRef("population_group", group.id), PLACE)
    assert local.protest_underway and "civic-protest" not in local.observation() and "food_relief" not in local.observation(), \
        "the public report leaks only a boolean"

    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    assert world.society.civic_protests[protest.id].stage == "refused"
    assert world.society.available_count(group.id) == original_available
    assert world.economy.needs[PLACE].unrest == original_unrest + 50
    refusal_event = next(event for event in world.events if event.event_type == "civic_protest_refused")
    pressure = next(event for event in world.events if event.event_type == "civic_refusal_pressure")
    assert refusal_event.id in {link.cause_event_id for link in pressure.causal_links}
    assert any(delta.owner_kind == "subsistence" and delta.owner_id == PLACE
               and delta.aspect == "unrest" and delta.before == str(original_unrest)
               and delta.after == str(original_unrest + 50) for delta in pressure.deltas)
    assert sum(account.balance for account in world.economy.accounts.values()) == money
    assert {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()} == stocks
    assert world.society.settlements[PLACE].administrator_id == government

    # The participation count remains historical after closure. A later
    # workforce/migration change may shrink the same cohort below five without
    # making the closed protest invalid.
    closed_group = world.society.population[group.id]
    world.society.population[group.id] = closed_group.model_copy(update={"count": 4})
    world.society.validate(set(world.map.regions), world)


def test_high_unrest_exposes_a_bounded_organized_strike_without_creating_authority():
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(update={"unrest": 650})
    refresh_settlement_reports(world)
    option = next(item for item in civic_protest_options(world, group.id)
                  if item.demand_kind == "organized_strike")
    assert option.participants >= 10
    available = world.society.available_count(group.id)
    decision = _decide(world, option)
    protest = open_civic_protest(world, group.id, option.id, decision.id)
    assert protest.demand_kind == "organized_strike"
    assert protest.participants == option.participants
    assert world.society.available_count(group.id) == available - option.participants
    assert not world.society.settlements[PLACE].claimant_ids
    opened = next(event for event in world.events if event.id == protest.last_event_id)
    assert opened.event_type == "civic_demand_received"


def test_high_unrest_can_expose_strike_even_after_food_shortage_is_resolved():
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 0, "health": 900, "unrest": 650})
    refresh_settlement_reports(world)
    options = civic_protest_options(world, group.id)
    assert [item.demand_kind for item in options] == ["organized_strike"]


def test_real_food_arrival_answers_and_releases_the_group_across_save_load(tmp_path):
    world = create_medieval_world(73)
    # Dispatch is an existing material action.  The group opens only after the
    # parcel is genuinely in transit, so its fixed three-day deadline can see
    # the later unloading receipt rather than a scripted relief effect.
    freight_decision = record_event(
        world, "freight_decided", "Frete interno real.", fact_kind=FactKind.DECISION,
        decision={"action": "freight", "source_id": "stock:campomanso", "destination_id": "stock:pedraclara",
                  "resource_id": "food", "quantity": 8, "route_ids": [ROAD], "actor_ref": ADMIN.to_dict()})
    queue_freight(world, "stock:campomanso", "stock:pedraclara", "food", 8, (ROAD,),
                  decision_event_id=freight_decision.id)
    _tick(world)
    _tick(world)
    group = _pressured(world)
    refresh_settlement_reports(world)
    option = civic_protest_options(world, group.id)[0]
    before = world.society.available_count(group.id)
    protest = open_civic_protest(world, group.id, option.id, _decide(world, option).id)
    while world.clock.absolute_day < protest.due_day:
        _tick(world)

    closed = world.society.civic_protests[protest.id]
    assert closed.stage == "answered"
    assert world.economy.needs[PLACE].unrest == 310
    assert world.society.available_count(group.id) == before
    close = next(event for event in world.events if event.id == closed.last_event_id)
    delivery = next(event for event in world.events if event.event_type == "cargo_delivered")
    assert delivery.id in {link.cause_event_id for link in close.causal_links}
    relief = next(event for event in world.events if event.event_type == "civic_resolution_relief")
    assert close.id in {link.cause_event_id for link in relief.causal_links}
    assert any(delta.owner_kind == "subsistence" and delta.owner_id == PLACE
               and delta.aspect == "unrest" and delta.before == "350" and delta.after == "310"
               for delta in relief.deltas)
    assert world.knowledge.settlement_report(EntityRef("population_group", group.id), PLACE).protest_underway is False
    path = Path(tmp_path) / "civic-protest.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_refused_high_unrest_can_choose_one_material_tumult_target():
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(update={"unrest": 450})
    refresh_settlement_reports(world)
    protest_option = civic_protest_options(world, group.id)[0]
    protest = open_civic_protest(world, group.id, protest_option.id, _decide(world, protest_option).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)
    refresh_site_reports(world)

    options = civic_tumult_options(world, group.id)
    assert options
    option = options[0]
    site_before = world.map.infrastructure_sites[option.site_id].integrity
    decision = record_event(world, "civic_tumult_decided", "O grupo escolheu um alvo local observado.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    event = execute_civic_tumult(world, group.id, option.id, decision.id)

    assert event.event_type == "civic_tumult_occurred"
    assert world.map.infrastructure_sites[option.site_id].integrity == pytest.approx(site_before - 0.08)
    assert option.refusal_event_id in {link.cause_event_id for link in event.causal_links}
    assert any(delta.owner_kind == "site" and delta.owner_id == option.site_id
               and delta.before == str(site_before) for delta in event.deltas)
    assert not civic_tumult_options(world, group.id), "one refusal cannot authorize a second tumult"


def test_refusal_and_multiple_local_groups_form_a_limited_civic_movement(tmp_path):
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 8, "unrest": 700})
    refresh_settlement_reports(world)
    protest_option = civic_protest_options(world, group.id)[0]
    protest = open_civic_protest(world, group.id, protest_option.id, _decide(world, protest_option).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)

    option = civic_movement_options(world, group.id)[0]
    available = {group_id: world.society.available_count(group_id)
                 for group_id in option.member_group_ids}
    decision = record_event(world, "civic_movement_decided", "Os grupos escolheram uma organização cívica limitada.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(option.catalyst_event_id, *option.report_event_ids))
    movement = form_civic_movement(world, group.id, option.id, decision.id)
    assert len(movement.member_group_ids) == 1
    movement = _join_second_group(world, movement)
    available.update({group_id: world.society.available_count(group_id)
                      + movement.participants_by_group[group_id]
                      for group_id in movement.member_group_ids
                      if group_id not in available})

    assert movement.stage == "active"
    assert len(movement.member_group_ids) == 2
    assert movement.leader_character_id == "character:005"
    assert all(world.society.available_count(group_id)
               == available[group_id] - movement.participants_by_group[group_id]
               for group_id in movement.member_group_ids)
    formed = next(event for event in world.events if event.event_type == "civic_movement_formed")
    assert formed.event_type == "civic_movement_formed"
    assert formed.causal_payload["movement_id"] == movement.id
    assert formed.causal_payload["initial_participant_count"] == movement.participants_by_group[movement.initiator_group_id]
    assert option.catalyst_event_id in {link.cause_event_id for link in formed.causal_links}
    assert any(delta.owner_kind == "civic_movement" and delta.owner_id == movement.id
               and delta.aspect == "stage" and delta.after == "active" for delta in formed.deltas)
    assert protest.id in world.society.civic_protests
    path = Path(tmp_path) / "civic-movement.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)

    world.clock = world.clock.advance(3)
    release = civic_movement_dissolve_options(world, group.id)[0]
    release_decision = record_event(world, "civic_movement_dissolve_decided", "A liderança encerrou a organização.",
                                    fact_kind=FactKind.DECISION, decision=release.decision())
    dissolved = dissolve_civic_movement(world, group.id, release.id, release_decision.id)
    assert dissolved.stage == "dissolved"
    assert all(world.society.available_count(group_id) == available[group_id]
               for group_id in movement.member_group_ids)
    assert world.events[-1].event_type == "civic_movement_dissolved"


def test_civic_movement_can_start_and_materially_end_a_bounded_general_strike(tmp_path):
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 8, "unrest": 700})
    refresh_settlement_reports(world)
    protest_option = civic_protest_options(world, group.id)[0]
    protest = open_civic_protest(world, group.id, protest_option.id, _decide(world, protest_option).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)
    movement_option = civic_movement_options(world, group.id)[0]
    movement_decision = record_event(world, "civic_movement_decided", "Movimento organizado.",
                                     fact_kind=FactKind.DECISION, decision=movement_option.decision(),
                                     cause_ids=(movement_option.catalyst_event_id, *movement_option.report_event_ids))
    movement = form_civic_movement(world, group.id, movement_option.id, movement_decision.id)
    movement = _join_second_group(world, movement)

    world.clock = world.clock.advance(3)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(update={"unrest": 700})
    refresh_settlement_reports(world)
    strike_option = civic_general_strike_options(world, group.id)[0]
    available_before = {group_id: world.society.available_count(group_id)
                        for group_id in strike_option.participants_by_group}
    strike_decision = record_event(world, "civic_general_strike_decided", "Greve geral delimitada.",
                                   fact_kind=FactKind.DECISION, decision=strike_option.decision(),
                                   cause_ids=(movement.last_event_id, *strike_option.report_event_ids))
    strike = start_general_strike(world, group.id, strike_option.id, strike_decision.id)
    assert strike.stage == "active"
    assert all(world.society.available_count(group_id)
               == available_before[group_id] - strike.participants_by_group[group_id]
               for group_id in strike.participants_by_group)
    assert world.agenda.get(strike.id).kind == "civic_general_strike"
    path = Path(tmp_path) / "civic-strike.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    while world.clock.absolute_day < strike.due_day:
        _tick(world)
    completed = world.society.civic_strikes[strike.id]
    assert completed.stage == "completed"
    assert all(world.society.available_count(group_id) == available_before[group_id]
               for group_id in strike.participants_by_group)
    assert world.events[-1].event_type == "civic_general_strike_ended"
    assert protest.id in world.society.civic_protests


def test_completed_mobilization_exposes_rebellion_without_transferring_administration():
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 8, "unrest": 700})
    refresh_settlement_reports(world)
    protest_option = civic_protest_options(world, group.id)[0]
    open_civic_protest(world, group.id, protest_option.id, _decide(world, protest_option).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)
    movement_option = civic_movement_options(world, group.id)[0]
    movement_decision = record_event(world, "civic_movement_decided", "Movimento organizado.",
                                     fact_kind=FactKind.DECISION, decision=movement_option.decision(),
                                     cause_ids=(movement_option.catalyst_event_id, *movement_option.report_event_ids))
    movement = form_civic_movement(world, group.id, movement_option.id, movement_decision.id)
    movement = _join_second_group(world, movement)
    world.clock = world.clock.advance(3)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(update={"unrest": 850})
    refresh_settlement_reports(world)
    strike_option = civic_general_strike_options(world, group.id)[0]
    strike_decision = record_event(world, "civic_general_strike_decided", "Mobilização geral.",
                                   fact_kind=FactKind.DECISION, decision=strike_option.decision(),
                                   cause_ids=(movement.last_event_id, *strike_option.report_event_ids))
    strike = start_general_strike(world, group.id, strike_option.id, strike_decision.id)
    while world.clock.absolute_day < strike.due_day:
        _tick(world)
    refresh_settlement_reports(world)
    option = civic_rebellion_options(world, group.id)[0]
    declaration = record_event(world, "civic_rebellion_decided", "O movimento decidiu contestar a administração.",
                               fact_kind=FactKind.DECISION, decision=option.decision(),
                               cause_ids=(option.report_event_id, option.mobilization_event_id))
    administrator = world.society.settlements[PLACE].administrator_id
    result = declare_civic_rebellion(world, group.id, option.id, declaration.id)
    assert result.stage == "rebellion"
    assert world.society.settlements[PLACE].administrator_id == administrator
    assert world.economy.needs[PLACE].unrest == 950
    event = next(item for item in world.events if item.id == result.last_event_id)
    assert event.event_type == "civic_rebellion_declared"
    pressure = next(item for item in world.events if item.event_type == "civic_rebellion_pressure")
    assert event.id in {link.cause_event_id for link in pressure.causal_links}
    refresh_settlement_reports(world)
    soldier_group = next(item for item in world.society.population.values()
                         if item.settlement_id == PLACE and item.count >= 5)
    soldiers = soldier_group.model_copy(update={
        "id": "pop:pedraclara:civic-suppression:soldier",
        "occupation": "soldier", "count": 5,
    })
    world.society.population[soldiers.id] = soldiers
    fixture_event = record_event(world, "suppression_force_fixture",
                                 "Premissa material da força de repressão.")
    world.society.detachments["detachment:civic-suppression"] = Detachment(
        id="detachment:civic-suppression", owner_ref=ADMIN,
        source_group_id=soldiers.id, count=5, location_id=PLACE,
        destination_id=PLACE, provisions=3, stage="present", started_day=world.clock.absolute_day,
        due_day=world.clock.absolute_day + 30, decision_event_id=fixture_event.id,
        last_event_id=fixture_event.id)
    response = civic_rebellion_response_options(world, ADMIN)[0]
    response_decision = record_event(world, "civic_rebellion_response_decided", "A administração decidiu reprimir a rebelião.",
                                     fact_kind=FactKind.DECISION, decision=response.decision(),
                                     cause_ids=(response.report_event_id, result.last_event_id))
    before_suppression_unrest = world.economy.needs[PLACE].unrest
    suppressed = suppress_civic_rebellion(world, ADMIN, response.id, response_decision.id)
    assert suppressed.stage == "suppressed"
    assert all(world.society.available_count(group_id) == world.society.population[group_id].count
               for group_id in suppressed.member_group_ids)
    assert world.economy.needs[PLACE].unrest == min(1000, before_suppression_unrest + 120)
    pressure = next(item for item in world.events if item.event_type == "civic_suppression_pressure")
    suppression = next(item for item in world.events if item.event_type == "civic_movement_suppressed")
    assert pressure.id in {link.cause_event_id for link in suppression.causal_links}
    assert suppression.causal_payload == {
        "decision_event_id": response_decision.id,
        "actor_ref": ADMIN.to_dict(),
        "selected_affordance_id": response.id,
        "movement_id": result.id,
        "suppression_detachment_id": "detachment:civic-suppression",
        "provisions_consumed": 1,
    }
    assert world.events[-1].event_type == "civic_movement_suppressed"


def test_administration_can_offer_negotiation_and_leader_can_accept_with_relief(tmp_path):
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 8, "unrest": 700})
    refresh_settlement_reports(world)
    protest_option = civic_protest_options(world, group.id)[0]
    open_civic_protest(world, group.id, protest_option.id, _decide(world, protest_option).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)
    movement_option = civic_movement_options(world, group.id)[0]
    movement_decision = record_event(world, "civic_movement_decided", "Movimento organizado.",
                                     fact_kind=FactKind.DECISION, decision=movement_option.decision(),
                                     cause_ids=(movement_option.catalyst_event_id, *movement_option.report_event_ids))
    movement = form_civic_movement(world, group.id, movement_option.id, movement_decision.id)
    movement = _join_second_group(world, movement)
    world.clock = world.clock.advance(3)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(update={"unrest": 850})
    refresh_settlement_reports(world)
    strike_option = civic_general_strike_options(world, group.id)[0]
    strike_decision = record_event(world, "civic_general_strike_decided", "Mobilização geral.",
                                   fact_kind=FactKind.DECISION, decision=strike_option.decision(),
                                   cause_ids=(movement.last_event_id, *strike_option.report_event_ids))
    strike = start_general_strike(world, group.id, strike_option.id, strike_decision.id)
    while world.clock.absolute_day < strike.due_day:
        _tick(world)
    refresh_settlement_reports(world)
    rebellion = civic_rebellion_options(world, group.id)[0]
    declaration = record_event(world, "civic_rebellion_decided", "Contestação organizada.",
                               fact_kind=FactKind.DECISION, decision=rebellion.decision(),
                               cause_ids=(rebellion.report_event_id, rebellion.mobilization_event_id))
    declared = declare_civic_rebellion(world, group.id, rebellion.id, declaration.id)
    refresh_settlement_reports(world)
    revolution = civic_revolution_options(world, group.id)[0]
    revolution_decision = record_event(world, "civic_revolution_decided", "Revolução declarada.",
                                      fact_kind=FactKind.DECISION, decision=revolution.decision(),
                                      cause_ids=(revolution.rebellion_event_id, revolution.mobilization_event_id,
                                                 revolution.report_event_id))
    declared = declare_civic_revolution(world, group.id, revolution.id, revolution_decision.id)
    assert declared.stage == "revolution"
    assert world.economy.needs[PLACE].unrest == 1000
    refresh_settlement_reports(world)
    negotiation = next(item for item in civic_rebellion_response_options(world, ADMIN)
                       if item.action == "offer_civic_negotiation")
    admin_decision = record_event(world, "civic_rebellion_response_decided", "Negociação oferecida.",
                                  fact_kind=FactKind.DECISION, decision=negotiation.decision(),
                                  cause_ids=(negotiation.report_event_id, declared.last_event_id))
    negotiating = respond_civic_rebellion(world, ADMIN, negotiation.id, admin_decision.id)
    assert negotiating.stage == "negotiating"
    assert world.society.available_count(group.id) < world.society.population[group.id].count
    acceptance = civic_movement_dissolve_options(world, group.id)[0]
    offered_stock = world.economy.stocks[negotiating.negotiation_stock_id]
    offered_goods = dict(offered_stock.goods)
    world.economy.stocks[offered_stock.id] = offered_stock.model_copy(
        update={"goods": {**offered_goods, "food": 0}})
    before_stale_acceptance = len(world.events)
    with pytest.raises(ValueError, match="stale"):
        dissolve_civic_movement(
            world, group.id, acceptance.id,
            record_event(world, "civic_negotiation_stale_decided", "Reserva mudou.",
                         fact_kind=FactKind.DECISION, decision=acceptance.decision(),
                         cause_ids=(negotiating.last_event_id,)).id)
    assert len(world.events) == before_stale_acceptance + 1
    world.economy.stocks[offered_stock.id] = offered_stock
    leader_decision = record_event(world, "civic_negotiation_accepted", "A liderança aceitou negociar.",
                                   fact_kind=FactKind.DECISION, decision=acceptance.decision(),
                                   cause_ids=(negotiating.last_event_id,))
    dissolved = dissolve_civic_movement(world, group.id, acceptance.id, leader_decision.id)
    assert dissolved.stage == "dissolved"
    assert any(event.event_type == "civic_negotiation_food_delivered" for event in world.events)
    assert world.economy.needs[PLACE].unrest == 940
    assert world.events[-1].event_type == "civic_resolution_relief"
    refresh_settlement_reports(world)
    amnesty = civic_amnesty_options(world, ADMIN)[0]
    amnesty_decision = record_event(world, "civic_amnesty_decided", "Anistia formal decidida.",
                                    fact_kind=FactKind.DECISION, decision=amnesty.decision(),
                                    cause_ids=(amnesty.negotiation_event_id, amnesty.report_event_id))
    granted = grant_civic_amnesty(world, ADMIN, amnesty.id, amnesty_decision.id)
    assert granted.movement_id == dissolved.id
    assert world.society.civic_movements[dissolved.id].stage == "dissolved"
    assert world.society.available_count(group.id) == world.society.population[group.id].count
    assert world.events[-1].event_type == "civic_amnesty_granted"
    assert amnesty.negotiation_event_id in {link.cause_event_id for link in world.events[-1].causal_links}
    assert world.events[-1].causal_payload == {
        "decision_event_id": amnesty_decision.id,
        "actor_ref": ADMIN.to_dict(),
        "selected_affordance_id": amnesty.id,
        "amnesty_id": granted.id,
        "movement_id": dissolved.id,
        "negotiation_event_id": amnesty.negotiation_event_id,
    }
    assert world.society.settlements[PLACE].administrator_id == ADMIN.id
    assert not civic_amnesty_options(world, ADMIN)
    path = Path(tmp_path) / "civic-amnesty.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_administration_can_persuade_an_active_movement_before_rebellion():
    world = create_medieval_world(73)
    group = _pressured(world)
    world.economy.needs[PLACE] = world.economy.needs[PLACE].model_copy(
        update={"missing_food": 8, "unrest": 700})
    refresh_settlement_reports(world)
    protest = civic_protest_options(world, group.id)[0]
    open_civic_protest(world, group.id, protest.id, _decide(world, protest).id)
    refusal = civic_refusal_options(world, ADMIN)[0]
    refuse_civic_demand(world, ADMIN, refusal.id, _decide(world, refusal).id)
    refresh_settlement_reports(world)
    movement_option = civic_movement_options(world, group.id)[0]
    movement = form_civic_movement(
        world, group.id, movement_option.id,
        record_event(world, "civic_movement_decided", "Movimento organizado.",
                     fact_kind=FactKind.DECISION, decision=movement_option.decision(),
                     cause_ids=(movement_option.catalyst_event_id, *movement_option.report_event_ids)).id)
    movement = _join_second_group(world, movement)
    refresh_settlement_reports(world)
    negotiation = next(item for item in civic_rebellion_response_options(world, ADMIN)
                       if item.action == "offer_civic_negotiation")
    admin_decision = record_event(world, "civic_rebellion_response_decided", "Negociação preventiva oferecida.",
                                  fact_kind=FactKind.DECISION, decision=negotiation.decision(),
                                  cause_ids=(negotiation.report_event_id, movement.last_event_id))
    negotiating = respond_civic_rebellion(world, ADMIN, negotiation.id, admin_decision.id)
    assert negotiating.stage == "negotiating"
    assert any(delta.aspect == "stage" and delta.before == "active" and delta.after == "negotiating"
               for delta in world.events[-1].deltas)
