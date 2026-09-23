import copy
import json

import pytest

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.migration import _resolve, consume_travel_provisions, recover_migration, start_migration
from src.sim.medieval.migration_policy import migration_options, recovery_options, review_migration
from src.sim.medieval.institutional_agenda import review_monthly_institutional_turn
from src.sim.medieval import ai_decider
from src.sim.medieval.persistence import load_world, restore_snapshot, save_world, world_snapshot
from src.systems.calendar_agenda import ScheduledSituation
from src.systems.calendar_scheduler import CalendarScheduler
from tools.medieval_autonomy_smoke import ledger_resource_effects, resource_totals


def pressured_household():
    world = create_medieval_world(73)
    group = next(group for group in world.society.population.values()
                 if group.id == "pop:pedraclara:human:artisan")
    account = world.economy.accounts[f"household:{group.id}"]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 10_000})
    world.economy.stocks[f"household-stock:{group.id}"] = Stock(
        id=f"household-stock:{group.id}", owner_ref=EntityRef("population_group", group.id),
        location_id=group.settlement_id, capacity=100_000, goods={"food": 10_000})
    need = world.economy.needs[group.settlement_id]
    world.economy.needs[need.id] = need.model_copy(update={"health": 600, "missing_food": 50})
    refresh_reports(world)
    return world, group, account


def decide(world, option):
    evidence = {world.knowledge.settlement_reports[option.source_report_id].event_id,
                world.knowledge.settlement_reports[option.destination_report_id].event_id,
                *(world.knowledge.route_reports[report_id].event_id for report_id in option.route_report_ids)}
    return record_event(world, "migration_decided", "Escolha datada.", fact_kind=FactKind.DECISION,
                        decision=option.decision(), cause_ids=tuple(sorted(evidence)))


def decide_recovery(world, journey, option):
    evidence = {world.knowledge.settlement_reports[report_id].event_id
                if report_id in world.knowledge.settlement_reports else world.knowledge.route_reports[report_id].event_id
                for report_id in option.report_ids}
    return record_event(world, "migration_recovery_decided", "Escolha de recuperação.", fact_kind=FactKind.DECISION,
                        decision=option.decision(journey.source_group_id), cause_ids=tuple(sorted(evidence)))


def test_migration_menu_requires_the_household_account_used_by_the_owner():
    world, group, _ = pressured_household()
    assert migration_options(world, group.id)

    del world.economy.accounts[f"household:{group.id}"]
    assert migration_options(world, group.id) == ()


@pytest.mark.asyncio
async def test_known_pressure_moves_household_with_its_own_cash_and_rations(tmp_path):
    world, group, source_account = pressured_household()
    options = migration_options(world, group.id)
    total_money = sum(account.balance for account in world.economy.accounts.values())
    total_food = sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
    source_balance = world.economy.accounts[source_account.id].balance

    review_migration(world)
    journey = next(iter(world.society.migrations.values()))
    option = next(item for item in options if item.id == world.events[-2].decision["option_id"])
    assert journey.source_group_id == group.id
    assert world.society.population[group.id].count == group.count
    assert world.society.available_count(group.id) == group.count - journey.count
    assert world.economy.accounts[source_account.id].balance == source_balance - source_balance * journey.count // group.count
    assert sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values()) == total_food - option.food
    assert {link.cause_event_id for link in world.events[-2].causal_links}  # decision cites dated reports

    path = tmp_path / "migration.mws"
    save_world(world, path)
    resumed = load_world(path)
    simulator = MedievalSimulator(resumed)
    for _ in range(30):
        if journey.id not in resumed.society.migrations:
            break
        await simulator.step()
    assert journey.id not in resumed.society.migrations
    target = next(item for item in resumed.society.population.values()
                  if item.settlement_id == option.destination_id and item.people == group.people
                  and item.occupation == group.occupation)
    assert target.count >= journey.count
    assert resumed.economy.accounts[f"migration-account:{journey.id}"].balance == 0
    assert resumed.economy.accounts[f"household:{target.id}"].balance >= source_balance * journey.count // group.count
    assert resumed.economy.stocks[f"household-stock:{target.id}"].goods["food"] == option.food
    assert sum(account.balance for account in resumed.economy.accounts.values()) == total_money


@pytest.mark.asyncio
async def test_ai_turn_selects_migration_affordance_instead_of_dated_fallback(monkeypatch):
    world, group, _ = pressured_household()
    world.config = world.config.model_copy(update={"ai_enabled": True,
                                                   "ai_calls_per_step": 256,
                                                   "ai_max_calls": 1000})
    selected = []

    async def choose_migration(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        migration = next((item["id"] for item in payload.get("choices", ())
                          if item.get("label", "").startswith("Migrar ")), None)
        if migration is not None:
            selected.append(migration)
            return {"selected_id": migration}
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_migration)

    await review_monthly_institutional_turn(world)

    assert selected
    journey = next(item for item in world.society.migrations.values()
                   if item.source_group_id == group.id)
    assert journey.count > 0
    assert any(event.event_type == "migration_started" and journey.id in {
        delta.owner_id for delta in event.deltas
    } for event in world.events)


@pytest.mark.asyncio
async def test_arrival_transfers_observed_social_pressure_without_erasing_its_cause():
    world, group, _ = pressured_household()
    source_need = world.economy.needs[group.settlement_id]
    world.economy.needs[source_need.id] = source_need.model_copy(update={"unrest": 600})
    option = migration_options(world, group.id)[0]
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    simulator = MedievalSimulator(world)
    for _ in range(30):
        if journey.id not in world.society.migrations:
            break
        await simulator.step()

    assert journey.id not in world.society.migrations
    source_after = world.economy.needs[group.settlement_id]
    destination_after = world.economy.needs[option.destination_id]
    assert source_after.unrest < 600
    assert destination_after.unrest > 0
    arrival = next(event for event in world.events if event.event_type == "migration_arrived"
                   and any(delta.owner_kind == "migration" and delta.owner_id == journey.id
                           for delta in event.deltas))
    assert any(delta.owner_kind == "subsistence" and delta.owner_id == group.settlement_id
               and delta.aspect == "unrest" and delta.before == "600"
               for delta in arrival.deltas)
    assert any(link.cause_event_id == journey.last_event_id for link in arrival.causal_links)


def test_migration_option_expires_without_mutating_the_household():
    world, group, _ = pressured_household()
    option = migration_options(world, group.id)[0]
    evidence = {world.knowledge.settlement_reports[option.source_report_id].event_id,
                world.knowledge.settlement_reports[option.destination_report_id].event_id,
                *(world.knowledge.route_reports[report_id].event_id for report_id in option.route_report_ids)}
    decision = record_event(world, "migration_decided", "Escolha datada.", fact_kind=FactKind.DECISION,
                            decision=option.decision(), cause_ids=tuple(sorted(evidence)))
    before = (dict(world.society.migrations), dict(world.economy.accounts), dict(world.economy.migration_provisions))
    world.clock = world.clock.advance(31)
    with pytest.raises(ValueError, match="stale"):
        start_migration(world, option.id, decision_event_id=decision.id)
    assert (world.society.migrations, world.economy.accounts, world.economy.migration_provisions) == before


def test_travel_rations_are_not_consumed_twice_on_one_monthly_boundary():
    world, group, _ = pressured_household()
    option = migration_options(world, group.id)[0]
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    provision = world.economy.migration_provisions[journey.provision_id]
    consume_travel_provisions(world)
    once = world.economy.migration_provisions[provision.id]
    intervening = record_event(world, "migration_return_note", "Recibo intermediário.", fact_kind=FactKind.OCCURRENCE)
    world.economy.migration_provisions[provision.id] = once.model_copy(update={"last_event_id": intervening.id})
    consume_travel_provisions(world)
    assert world.economy.migration_provisions[provision.id].food == once.food


def test_repeated_route_blockage_adds_bounded_origin_pressure_with_causal_delta():
    world, group, _ = pressured_household()
    option = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    route = world.map.routes[journey.route_ids[0]]
    route.quality = 0
    need = world.economy.needs[group.settlement_id]
    before = need.unrest

    for _ in range(7):
        journey = world.society.migrations[journey.id]
        world.clock = type(world.clock)(journey.due_day)
        world.agenda.cancel(journey.id)
        _resolve(world, journey)

    delays = [event for event in world.events if event.event_type == "migration_delayed"
              and any(delta.owner_kind == "migration" and delta.owner_id == journey.id for delta in event.deltas)]
    pressure = delays[-1]
    assert len(delays) == 7
    assert world.economy.needs[group.settlement_id].unrest == before + 5
    assert any(delta.owner_kind == "subsistence" and delta.owner_id == group.settlement_id
               and delta.aspect == "unrest" and delta.after == str(before + 5)
               for delta in pressure.deltas)


@pytest.mark.asyncio
async def test_stranded_household_can_return_over_real_routes():
    world, group, source_account = pressured_household()
    source_capacity = world.economy.stocks[f"household-stock:{group.id}"].capacity
    option = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    destination = world.society.settlements[option.destination_id]
    world.society.settlements[destination.id] = destination.model_copy(
        update={"housing_capacity": world.society.population_at(destination.id)})
    simulator = MedievalSimulator(world)
    for _ in range(12):
        if world.society.migrations[journey.id].stage == "stranded":
            break
        await simulator.step()
    stranded = world.society.migrations[journey.id]
    assert stranded.stage == "stranded"
    from src.server.medieval.queries import campaign_view
    threat = next(item for item in campaign_view(world).threats
                  if item.id == f"migration-blocked:{journey.id}")
    assert threat.kind == "migration_blocked" and threat.status == "blocked"
    assert threat.settlement_id == journey.destination_id
    option = next(item for item in recovery_options(world, journey.id) if item.action == "return_migration")
    recover_migration(world, option.id, decision_event_id=decide_recovery(world, stranded, option).id)
    for _ in range(20):
        if journey.id not in world.society.migrations:
            break
        await simulator.step()
    assert journey.id not in world.society.migrations
    assert world.society.available_count(group.id) == group.count
    assert world.economy.accounts[source_account.id].balance == 10_000
    assert world.economy.stocks[f"household-stock:{group.id}"].capacity == source_capacity


@pytest.mark.asyncio
async def test_blocked_arrival_adds_bounded_destination_pressure_without_forcing_action():
    world, group, _ = pressured_household()
    option = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    destination = world.society.settlements[option.destination_id]
    world.society.settlements[destination.id] = destination.model_copy(
        update={"housing_capacity": world.society.population_at(destination.id)})
    before = world.economy.needs[destination.id].unrest
    simulator = MedievalSimulator(world)
    for _ in range(12):
        if world.society.migrations[journey.id].stage == "stranded":
            break
        await simulator.step()

    assert world.society.migrations[journey.id].stage == "stranded"
    after = world.economy.needs[destination.id].unrest
    assert after > before
    assert after <= before + 40
    blocked = next(event for event in world.events if event.event_type == "migration_arrival_blocked")
    assert any(delta.owner_kind == "subsistence" and delta.owner_id == destination.id
               and delta.aspect == "unrest" and delta.after == str(after)
               for delta in blocked.deltas)
    assert not any(event.event_type in {"civic_tumult_occurred", "civic_movement_formed"}
                   and any(link.cause_event_id == blocked.id for link in event.causal_links)
                   for event in world.events)


@pytest.mark.asyncio
async def test_stranded_household_can_choose_a_second_known_destination():
    world, group, _ = pressured_household()
    initial = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, initial.id, decision_event_id=decide(world, initial).id)
    blocked_destination = world.society.settlements[initial.destination_id]
    world.society.settlements[blocked_destination.id] = blocked_destination.model_copy(
        update={"housing_capacity": world.society.population_at(blocked_destination.id)})
    simulator = MedievalSimulator(world)
    for _ in range(12):
        if world.society.migrations[journey.id].stage == "stranded":
            break
        await simulator.step()
    stranded = world.society.migrations[journey.id]
    reroute = next(item for item in recovery_options(world, journey.id) if item.action == "reroute_migration")
    assert reroute.destination_id not in {group.settlement_id, initial.destination_id}
    before_population = world.society.present_population_at(reroute.destination_id)
    event = recover_migration(world, reroute.id, decision_event_id=decide_recovery(world, stranded, reroute).id)
    assert event.event_type == "migration_reroute_started"
    assert world.society.migrations[journey.id].destination_id == reroute.destination_id
    assert world.society.present_population_at(reroute.destination_id) == before_population
    evidence = {world.knowledge.settlement_reports[item].event_id
                if item in world.knowledge.settlement_reports
                else world.knowledge.route_reports[item].event_id
                for item in reroute.report_ids}
    assert {link.cause_event_id for link in event.causal_links} == evidence | {stranded.last_event_id,
                                                                                next(item.id for item in world.events
                                                                                     if item.event_type == "migration_recovery_decided")}


@pytest.mark.asyncio
async def test_engine_retries_a_stranded_arrival_after_a_fresh_local_observation():
    world, group, _ = pressured_household()
    option = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    destination = world.society.settlements[option.destination_id]
    world.society.settlements[destination.id] = destination.model_copy(
        update={"housing_capacity": world.society.population_at(destination.id)})
    simulator = MedievalSimulator(world)
    for _ in range(12):
        if world.society.migrations[journey.id].stage == "stranded":
            break
        await simulator.step()
    assert world.society.migrations[journey.id].stage == "stranded"
    world.society.settlements[destination.id] = destination
    await simulator.step()  # next monthly policy receives the group\'s local endpoint observation and retries.
    assert journey.id not in world.society.migrations
    assert any(event.event_type == "migration_retry_started" for event in world.events)


@pytest.mark.asyncio
async def test_arrival_expands_existing_private_pantry_with_carried_capacity():
    world, group, _ = pressured_household()
    option = next(item for item in migration_options(world, group.id) if item.destination_id == "ferroalto")
    target = next(item for item in world.society.population.values()
                  if (item.settlement_id, item.people, item.occupation) == ("ferroalto", group.people, group.occupation))
    pantry_id = f"household-stock:{target.id}"
    world.economy.stocks[pantry_id] = Stock(id=pantry_id, owner_ref=EntityRef("population_group", target.id),
                                            location_id=target.settlement_id, capacity=1, goods={"food": 1})
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    simulator = MedievalSimulator(world)
    for _ in range(12):
        if not world.society.migrations:
            break
        await simulator.step()
    pantry = world.economy.stocks[pantry_id]
    assert pantry.goods["food"] == 1 + option.food
    assert pantry.capacity == 2 * (target.count + journey.count) * world.economy.resources["food"].bulk


@pytest.mark.asyncio
async def test_failed_durable_arrival_commit_restores_the_active_journey_once(tmp_path, monkeypatch):
    world, group, _ = pressured_household()
    option = min(migration_options(world, group.id), key=lambda item: (len(item.route_ids), item.id))
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    simulator = MedievalSimulator(world, save_path=tmp_path / "arrival.mws")

    # Reach the exact dated resolution that will perform the material arrival,
    # without assuming a route duration or a monthly-boundary tie.
    while True:
        active = world.society.migrations[journey.id]
        jump = CalendarScheduler.next_jump(world.clock, world.agenda.due_days)
        if jump.agenda_due and active.stage == "traveling" and active.route_index == len(active.route_ids) - 1:
            break
        await simulator.step()

    before_snapshot = world_snapshot(world)
    before_events = list(world.events)
    before_rng = world.rng.getstate()
    before_agenda = world.agenda.to_dict()
    before_accounts = copy.deepcopy(world.economy.accounts)
    before_population = copy.deepcopy(world.society.population)
    before_provisions = copy.deepcopy(world.economy.migration_provisions)
    from src.sim.medieval import engine

    actual_save = engine.save_world

    def fail(*args, **kwargs):
        raise OSError("arrival disk unavailable")

    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="arrival disk"):
        await simulator.step()
    assert world_snapshot(world) == before_snapshot and world.events == before_events
    assert world.rng.getstate() == before_rng and world.agenda.to_dict() == before_agenda
    assert world.economy.accounts == before_accounts and world.society.population == before_population
    assert world.economy.migration_provisions == before_provisions

    monkeypatch.setattr(engine, "save_world", actual_save)
    await simulator.step()
    arrivals = [event for event in world.events if event.event_type == "migration_arrived"
                and any(delta.owner_kind == "migration" and delta.owner_id == journey.id for delta in event.deltas)]
    assert journey.id not in world.society.migrations and len(arrivals) == 1


@pytest.mark.asyncio
async def test_migration_provision_crossing_a_month_is_visible_to_resource_ledger():
    world, group, _ = pressured_household()
    option = migration_options(world, group.id)[0]
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    world.agenda.pop_due(journey.due_day)
    journey = journey.model_copy(update={"due_day": 31})
    world.society.migrations[journey.id] = journey
    world.agenda.schedule(ScheduledSituation(journey.id, "migration", 31))
    before_resources = resource_totals(world)
    before_money = sum(account.balance for account in world.economy.accounts.values())
    event_start = len(world.events)
    await MedievalSimulator(world).step()  # monthly boundary day 30, still in transit
    effects = ledger_resource_effects(world.events[event_start:], world.economy.resources)
    assert resource_totals(world) == {resource: before_resources[resource] + effects[resource]
                                      for resource in before_resources}
    assert sum(account.balance for account in world.economy.accounts.values()) == before_money
    assert world.economy.migration_provisions[journey.provision_id].food == option.food - journey.count


def test_save_rejects_a_future_migration_consumption_marker():
    world, group, _ = pressured_household()
    option = migration_options(world, group.id)[0]
    journey = start_migration(world, option.id, decision_event_id=decide(world, option).id)
    consume_travel_provisions(world)
    snapshot = copy.deepcopy(world_snapshot(world))
    snapshot["economy"]["migration_provisions"][journey.provision_id]["consumed_day"] = 1
    with pytest.raises(ValueError, match="consumption provenance"):
        restore_snapshot(snapshot, world.events)
