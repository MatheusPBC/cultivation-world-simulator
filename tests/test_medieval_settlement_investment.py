"""A foreign prepared column can apply bounded pressure without owning a city."""

from copy import deepcopy

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.force import force_position_options, prepare_force_position
from src.sim.medieval.logistics import queue_freight
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                     settlement_investment_options)
from src.systems.calendar_agenda import ScheduledSituation


ATTACKER = EntityRef("polity", "auren")
DEFENDER = EntityRef("polity", "escarlia")
TARGET = "ferroalto"
ROAD = "road-pontenegro-ferroalto"
OTHER_EXIT = "road-brumafria-ferroalto"


def decide(world, option):
    return record_event(world, "settlement_investment_decided", "Decisão canônica de pressão local.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)


def prepared_foreign_column(*, with_route_reports=True):
    world = create_medieval_world(131)
    refresh_settlement_reports(world)
    if with_route_reports:
        refresh_route_reports(world)
    group = next(item for item in world.society.population.values() if item.settlement_id == "campomanso")
    soldier_id = f"pop:campomanso:{group.people}:soldier"
    world.society.population[soldier_id] = group.model_copy(
        update={"id": soldier_id, "occupation": "soldier", "count": 40})
    arrival = record_event(
        world, "test_column_present", "Fixture factual de uma coluna estrangeira já presente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment", "detachment:test-investment", "stage", None, "present"),),
    )
    detachment = Detachment(
        id="detachment:test-investment", owner_ref=ATTACKER, source_group_id=soldier_id, count=40,
        location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0, provisions=160,
        stage="present", started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 30,
        decision_event_id=arrival.id, last_event_id=arrival.id,
    )
    world.society.detachments[detachment.id] = detachment
    position = force_position_options(world, ATTACKER, detachment_id=detachment.id)[0]
    prepare_force_position(world, ATTACKER, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    if with_route_reports:
        refresh_route_reports(world, route_ids=(ROAD, OTHER_EXIT))
    return world, detachment.id


def queue_existing_cargo(world):
    source = next(item for item in world.economy.stocks.values()
                  if item.owner_ref == DEFENDER and item.location_id == "brumafria"
                  and item.goods.get("food", 0) > 1)
    destination = next(item for item in world.economy.stocks.values()
                       if item.owner_ref == DEFENDER and item.location_id == TARGET)
    decision = record_event(
        world, "freight_decided", "Frete canônico existente para testar o atraso físico.",
        fact_kind=FactKind.DECISION,
        decision={"action": "freight", "source_id": source.id, "destination_id": destination.id,
                  "resource_id": "food", "quantity": 1, "route_ids": [OTHER_EXIT],
                  "actor_ref": DEFENDER.to_dict()},
    )
    return queue_freight(world, source.id, destination.id, "food", 1, (OTHER_EXIT,), decision_event_id=decision.id)


def test_investment_closes_every_exit_delays_existing_cargo_and_hides_column(tmp_path):
    world, detachment_id = prepared_foreign_column()
    option = next(item for item in settlement_investment_options(world, ATTACKER, detachment_id=detachment_id)
                  if item.kind == "invest")
    assert option.route_ids == (OTHER_EXIT, ROAD)
    order = queue_existing_cargo(world)
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    administrator_before = world.society.settlements[TARGET].administrator_id
    assets_before = {key: value.model_dump(mode="json") for key, value in world.economy.stocks.items()}

    investment = execute_settlement_investment_option(world, ATTACKER, option.id, decide(world, option).id)

    assert investment.stage == "active"
    assert all(world.map.get_route_operational_capacity(route_id) == 0 for route_id in investment.route_ids)
    pressure = next(item for item in world.knowledge.settlement_pressures_for_actor(DEFENDER)
                    if item.investment_id == investment.id)
    assert pressure.settlement_id == TARGET and pressure.route_count == 2
    assert not ({"actor_ref", "detachment_id", "location_id", "owner_ref"} & set(pressure.model_dump()))
    assert world.society.settlements[TARGET].administrator_id == administrator_before
    assert {key: value.model_dump(mode="json") for key, value in world.economy.stocks.items()} == assets_before

    tick(world)
    assert world.economy.parcels[parcel.id].quantity == 1
    assert any(event.event_type == "cargo_delayed" for event in world.events)
    path = tmp_path / "settlement-investment.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_too_small_has_no_option_and_lift_preserves_an_external_closure():
    world, detachment_id = prepared_foreign_column()
    small = world.society.detachments[detachment_id]
    world.society.detachments[detachment_id] = small.model_copy(update={"count": 20, "provisions": 80})
    assert not settlement_investment_options(world, ATTACKER, detachment_id=detachment_id)

    world, detachment_id = prepared_foreign_column()
    option = settlement_investment_options(world, ATTACKER, detachment_id=detachment_id)[0]
    execute_settlement_investment_option(world, ATTACKER, option.id, decide(world, option).id)
    world.map.routes[ROAD].update_runtime(enabled=False)
    lift = next(item for item in settlement_investment_options(world, ATTACKER, detachment_id=detachment_id)
                if item.kind == "lift")
    execute_settlement_investment_option(world, ATTACKER, lift.id, decide(world, lift).id)
    assert world.map.get_route_operational_capacity(ROAD) == 0
    assert world.map.get_route_operational_capacity(OTHER_EXIT) > 0
    assert next(item for item in world.society.settlement_investments.values()).stage == "lifted"

    lapsed, detachment_id = prepared_foreign_column()
    option = settlement_investment_options(lapsed, ATTACKER, detachment_id=detachment_id)[0]
    execute_settlement_investment_option(lapsed, ATTACKER, option.id, decide(lapsed, option).id)
    detachment = lapsed.society.detachments[detachment_id]
    lapsed.society.detachments[detachment_id] = detachment.model_copy(
        update={"provisions": detachment.count, "due_day": lapsed.clock.absolute_day + 1})
    lapsed.agenda.schedule(ScheduledSituation(detachment_id, "force", lapsed.clock.absolute_day + 1))
    tick(lapsed)
    assert all(lapsed.map.get_route_operational_capacity(route_id) > 0
               for route_id in (ROAD, OTHER_EXIT))
    assert any(event.event_type == "settlement_investment_lifted" for event in lapsed.events)


def test_missing_route_observation_blocks_pressure_until_new_local_report(tmp_path):
    uninformed, detachment_id = prepared_foreign_column(with_route_reports=False)
    informed = deepcopy(uninformed)
    refresh_route_reports(informed, route_ids=(ROAD, OTHER_EXIT))
    option = next(item for item in settlement_investment_options(informed, ATTACKER,
                       detachment_id=detachment_id) if item.kind == "invest")
    assert uninformed.knowledge.route_report(ATTACKER, ROAD) is None
    assert uninformed.map.get_route_operational_capacity(ROAD) > 0
    assert not any(item.kind == "invest" for item in settlement_investment_options(
        uninformed, ATTACKER, detachment_id=detachment_id))

    stale_decision = decide(uninformed, option)
    before = world_snapshot(uninformed)
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_settlement_investment_option(uninformed, ATTACKER, option.id, stale_decision.id)
    assert world_snapshot(uninformed) == before

    refresh_route_reports(uninformed, route_ids=(ROAD, OTHER_EXIT))
    current = next(item for item in settlement_investment_options(uninformed, ATTACKER,
                   detachment_id=detachment_id) if item.kind == "invest")
    assert current.id != option.id
    assert uninformed.knowledge.route_report(ATTACKER, ROAD).event_id in current.report_event_ids
    investment = execute_settlement_investment_option(
        uninformed, ATTACKER, current.id, decide(uninformed, current).id)
    assert investment.stage == "active"
    assert all(uninformed.map.get_route_operational_capacity(route_id) == 0
               for route_id in investment.route_ids)
    path = tmp_path / "information-bounded-investment.mws"
    save_world(uninformed, path)
    assert world_snapshot(load_world(path)) == world_snapshot(uninformed)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True
