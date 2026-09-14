"""Critical causal coverage for the deliberately small civic-demand vertical."""

from pathlib import Path

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.civic_protest import (civic_protest_options, civic_refusal_options,
                                            open_civic_protest, refuse_civic_demand)
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.logistics import queue_freight
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


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


def _tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def test_opening_requires_own_reading_reserves_only_work_and_notifies_admin_privately():
    world = create_medieval_world(73)
    group = _pressured(world)
    assert not civic_protest_options(world, group.id), "canonical distress alone never starts a protest"
    refresh_settlement_reports(world)
    option = civic_protest_options(world, group.id)[0]
    original_available = world.society.available_count(group.id)
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
    assert sum(account.balance for account in world.economy.accounts.values()) == money
    assert {stock.id: dict(stock.goods) for stock in world.economy.stocks.values()} == stocks
    assert world.society.settlements[PLACE].administrator_id == government


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
    assert world.society.available_count(group.id) == before
    close = next(event for event in world.events if event.id == closed.last_event_id)
    delivery = next(event for event in world.events if event.event_type == "cargo_delivered")
    assert delivery.id in {link.cause_event_id for link in close.causal_links}
    assert world.knowledge.settlement_report(EntityRef("population_group", group.id), PLACE).protest_underway is False
    path = Path(tmp_path) / "civic-protest.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
