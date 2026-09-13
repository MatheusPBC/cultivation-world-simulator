"""Route operability is learned by dated report; the Map remains its only owner."""

import sqlite3

import pytest

from src.classes.governance.knowledge import route_report_id
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, restore_snapshot, save_world, world_snapshot
from src.sim.medieval.routing import known_supply_path, supply_path

ROUTE = "road-campomanso-pedraclara"
ENDS = ("campomanso", "pedraclara")


def endpoint_settlements(world, route_id):
    route = world.map.routes[route_id]
    return {s.id for s in world.society.settlements.values() if s.region_id in route.endpoint_region_ids}


def administrators(world, route_id):
    places = endpoint_settlements(world, route_id)
    return sorted({world.society.settlements[p].administrator_id for p in places
                   if world.society.settlements[p].administrator_id})


def objective_places(world):
    places = {}
    for objective in world.strategy.objectives.values():
        places.setdefault(objective.actor_ref, set()).add(objective.settlement_id)
    return places


def observer(world, route_id=ROUTE):
    return EntityRef("polity", administrators(world, route_id)[0])


def test_a_closure_changes_no_plan_until_it_is_observed_again():
    world = create_medieval_world(73)
    refresh_reports(world)
    actor = observer(world)
    report = world.knowledge.route_report(actor, ROUTE)
    assert report.channel == "administrative_route_report" and report.publisher_ref == actor
    assert report.travel_days is not None and report.operational_capacity > 0
    assert known_supply_path(world, actor, *ENDS) == (ROUTE,)

    world.map.routes[ROUTE].update_runtime(enabled=False)
    # Physical truth changed; nobody was told, so no affordance changed.
    assert supply_path(world, *ENDS) != (ROUTE,)
    assert world.knowledge.route_report(actor, ROUTE) == report
    assert known_supply_path(world, actor, *ENDS) == (ROUTE,)

    world.clock = world.clock.advance(1)
    refresh_reports(world)
    updated = world.knowledge.route_report(actor, ROUTE)
    assert updated.travel_days is None and updated.operational_capacity == 0.0
    assert updated.observed_day == world.clock.absolute_day and updated.event_id != report.event_id
    assert ROUTE not in (known_supply_path(world, actor, *ENDS) or ())
    receipt = next(e for e in world.events if e.id == updated.event_id)
    assert receipt.event_type == "route_observed"
    assert any(d.owner_kind == "route_report" and d.owner_id == updated.id
               and d.after == updated.observation() for d in receipt.deltas)


def test_recovery_is_communicated_by_a_later_observation():
    world = create_medieval_world(73)
    world.map.routes[ROUTE].update_runtime(enabled=False)
    refresh_reports(world)
    actor = observer(world)
    assert world.knowledge.route_report(actor, ROUTE).travel_days is None
    world.map.routes[ROUTE].update_runtime(enabled=True)
    world.clock = world.clock.advance(1)
    refresh_reports(world)
    assert world.knowledge.route_report(actor, ROUTE).travel_days is not None
    assert known_supply_path(world, actor, *ENDS) == (ROUTE,)


def local_and_remote_case(world):
    """A route whose endpoints host another institution, plus a disconnected one."""
    places = objective_places(world)
    for route_id in sorted(world.map.routes):
        endpoints = endpoint_settlements(world, route_id)
        publishers = {EntityRef("polity", identity) for identity in administrators(world, route_id)}
        for publisher in sorted(publishers, key=lambda r: r.id):
            # A local recipient sits in the observed settlement itself and does
            # not administer any endpoint, so it is told instead of observing.
            observed = {s for s in endpoints if world.society.settlements[s].administrator_id == publisher.id}
            local = [a for a, targets in places.items() if a not in publishers and targets & observed]
            remote = [a for a, targets in places.items() if a not in publishers and not targets & endpoints]
            if local and remote:
                return route_id, publisher, sorted(local, key=lambda r: (r.kind != "organization", r.id))[0], \
                    sorted(remote, key=lambda r: (r.kind, r.id))[0]
    return None


def test_bulletin_reaches_the_observed_place_but_not_a_disconnected_holder():
    world = create_medieval_world(73)
    case = local_and_remote_case(world)
    assert case is not None, "bootstrap has no local and disconnected pair to exercise the channel"
    route_id, publisher, local, remote = case
    for route in world.map.routes.values():
        route.update_runtime(enabled=False)
    refresh_reports(world)
    # Every passage is closed: only the observed place still hears the observer.
    assert world.knowledge.route_report(publisher, route_id).channel == "administrative_route_report"
    received = world.knowledge.route_report(local, route_id)
    assert received is not None and received.channel == "route_bulletin"
    assert received.publisher_ref in {EntityRef("polity", i) for i in administrators(world, route_id)}
    assert received.recipient_ref == local
    delivery = next(e for e in world.events if e.id == received.event_id)
    assert delivery.event_type == "route_report_received"
    decision = next(e for e in world.events for link in delivery.causal_links if e.id == link.cause_event_id
                    and e.event_type == "route_report_published")
    assert decision.decision["action"] == "publish_route_report"
    assert local.to_dict() in decision.decision["recipients"]
    assert world.knowledge.route_report(remote, route_id) is None


def test_planner_uses_its_own_reports_and_cites_them_in_the_decision():
    world = create_medieval_world(73)
    from src.sim.medieval.procurement import review_supply
    refresh_reports(world)
    review_supply(world)
    assert world.economy.freight_orders
    for order in world.economy.freight_orders.values():
        decision = next(e for e in world.events if e.id == order.decision_ids[0])
        cited = {link.cause_event_id for link in decision.causal_links}
        evidence = {world.knowledge.route_report(order.owner_ref, route_id).event_id
                    for route_id in order.route_ids}
        assert evidence <= cited


def test_closed_passages_block_plans_and_their_own_reports_explain_it():
    world = create_medieval_world(73)
    from src.sim.medieval.procurement import review_supply
    for route in world.map.routes.values():
        route.update_runtime(enabled=False)
    refresh_reports(world)
    review_supply(world)
    # Only same-place transfers remain possible; no passage is invented.
    assert all(not order.route_ids for order in world.economy.freight_orders.values())
    blocked = [p for p in world.strategy.plans.values()
               if p.stage == "blocked" and "rota conhecida" in (p.blocker or "")]
    assert blocked
    events = {e.id: e for e in world.events}
    for plan in blocked:
        actor = world.strategy.objectives[plan.objective_id].actor_ref
        cited = {link.cause_event_id for link in events[plan.last_event_id].causal_links}
        closed = {r.event_id for r in world.knowledge.routes_for_actor(actor) if r.travel_days is None}
        assert closed and cited & closed


def test_absent_route_reports_stay_absent_without_inventing_a_cause():
    world = create_medieval_world(73)
    from src.sim.medieval.procurement import review_supply
    refresh_reports(world)
    world.knowledge.route_reports.clear()
    review_supply(world)
    assert all(not order.route_ids for order in world.economy.freight_orders.values())
    blocked = [p for p in world.strategy.plans.values()
               if p.stage == "blocked" and "rota conhecida" in (p.blocker or "")]
    assert blocked
    events = {e.id: e for e in world.events}
    for plan in blocked:
        assert not any(events[link.cause_event_id].event_type in {"route_observed", "route_report_received"}
                       for link in events[plan.last_event_id].causal_links)


@pytest.mark.asyncio
async def test_failed_first_jump_rolls_back_the_route_knowledge_it_created(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    assert not world.knowledge.route_reports
    before, history = world_snapshot(world), list(world.events)
    from src.sim.medieval import engine

    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="disk"):
        await MedievalSimulator(world, save_path=tmp_path / "failed.mws").step()
    assert not world.knowledge.route_reports
    assert world_snapshot(world) == before
    assert world.events == history
    monkeypatch.undo()
    await MedievalSimulator(world).step()
    assert world.knowledge.route_reports and world.economy.freight_orders
    money = sum(a.balance for a in world.economy.accounts.values())
    path = tmp_path / "routes.mws"
    save_world(world, path)
    resumed = load_world(path)
    for value in (world, resumed):
        await MedievalSimulator(value).step()
    assert world_snapshot(world) == world_snapshot(resumed)
    assert sum(a.balance for a in world.economy.accounts.values()) == money


def carried(world, resource_id):
    total = sum(stock.goods.get(resource_id, 0) for stock in world.economy.stocks.values())
    return total + sum(parcel.quantity for parcel in world.economy.parcels.values()
                       if world.economy.freight_orders[parcel.order_id].resource_id == resource_id)


@pytest.mark.asyncio
async def test_a_stale_report_commits_real_cargo_that_the_closure_later_delays():
    from src.classes.event import FactKind
    from src.sim.medieval.economy import _delta
    from src.sim.medieval.events import record_event
    from src.sim.medieval.procurement import review_supply
    world = create_medieval_world(73)
    refresh_reports(world)
    # Material closure recorded as a fact between observation and planning:
    # every passage is shut and nobody has observed it yet.
    closure = record_event(world, "route_closed", "Passagens interditadas por obra.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=tuple(_delta("route", route_id, "enabled", True, False)
                                        for route_id in sorted(world.map.routes)))
    for route in world.map.routes.values():
        route.update_runtime(enabled=False)
    review_supply(world)
    order = next(o for _, o in sorted(world.economy.freight_orders.items()) if o.route_ids)
    route_id = order.route_ids[0]
    known = world.knowledge.route_report(order.owner_ref, route_id)
    assert known.travel_days is not None
    decision = next(e for e in world.events if e.id == order.decision_ids[0])
    cited = {link.cause_event_id for link in decision.causal_links}
    # The commitment was decided after the closure, on the old report alone.
    assert decision.sequence > closure.sequence
    assert known.event_id in cited and closure.id not in cited
    goods = carried(world, order.resource_id)
    await MedievalSimulator(world).step()
    delayed = [e for e in world.events if e.event_type == "cargo_delayed" and e.sequence > closure.sequence]
    assert delayed
    assert any(closure.id in {link.cause_event_id for link in e.causal_links} for e in delayed)
    assert carried(world, order.resource_id) == goods
    # The commitment stands and knowledge did not update itself.
    assert world.economy.freight_orders[order.id].delivered_quantity == 0
    assert world.knowledge.route_report(order.owner_ref, route_id) == known


def test_a_saved_bulletin_keeps_its_historical_receipt_after_a_newer_observation(tmp_path):
    world = create_medieval_world(73)
    case = local_and_remote_case(world)
    assert case is not None, "bootstrap has no local and disconnected pair to exercise the channel"
    route_id, publisher, local, _ = case
    refresh_reports(world)
    received = world.knowledge.route_report(local, route_id)
    assert received is not None and received.channel == "route_bulletin" and received.travel_days is not None
    world.map.routes[route_id].update_runtime(enabled=False)
    for office in list(world.authority.offices.values()):
        world.authority.offices[office.id] = office.model_copy(
            update={"scopes": tuple(s for s in office.scopes if s != "trade")})
    world.clock = world.clock.advance(1)
    refresh_reports(world)
    # The publisher's own entry was replaced; the delivered bulletin was not.
    assert world.knowledge.route_report(publisher, route_id).travel_days is None
    assert world.knowledge.route_report(local, route_id) == received
    path = tmp_path / "bulletin.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.knowledge.route_report(local, route_id) == received
    assert known_supply_path(resumed, local, *ENDS) == known_supply_path(world, local, *ENDS)


def test_saved_stale_knowledge_stays_stale_after_resume(tmp_path):
    world = create_medieval_world(73)
    refresh_reports(world)
    actor = observer(world)
    world.map.routes[ROUTE].update_runtime(enabled=False)
    path = tmp_path / "stale.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.knowledge.route_report(actor, ROUTE).travel_days is not None
    assert known_supply_path(resumed, actor, *ENDS) == (ROUTE,)
    assert supply_path(resumed, *ENDS) != (ROUTE,)


@pytest.mark.parametrize("forgery", ["capacity", "travel_days", "future_day", "orphan_event", "third_party"])
def test_save_rejects_route_knowledge_without_its_own_receipt(forgery):
    world = create_medieval_world(73)
    refresh_reports(world)
    actor = observer(world)
    key = route_report_id(actor, ROUTE)
    snapshot = world_snapshot(world)
    report = snapshot["knowledge"]["route_reports"][key]
    if forgery == "capacity":
        report["operational_capacity"] = report["operational_capacity"] + 1000.0
    elif forgery == "travel_days":
        report["travel_days"] = (report["travel_days"] or 1) + 5
    elif forgery == "future_day":
        report["observed_day"] = world.clock.absolute_day + 10
    elif forgery == "orphan_event":
        report["event_id"] = f"event:{len(world.events) + 50}"
    else:
        stranger = EntityRef("polity", next(p for p in sorted(world.society.polities) if p != actor.id))
        moved = route_report_id(stranger, ROUTE)
        snapshot["knowledge"]["route_reports"][moved] = {**report, "id": moved,
                                                         "recipient_ref": stranger.to_dict()}
    with pytest.raises(ValueError, match="route|provenance|receipt"):
        restore_snapshot(snapshot, world.events)


def test_schema_twelve_rejects_the_previous_save_without_migrating(tmp_path):
    world = create_medieval_world(73)
    refresh_reports(world)
    path = tmp_path / "old.mws"
    save_world(world, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=11")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    with pytest.raises(ValueError, match="Unsupported"):
        save_world(world, path)
    assert path.read_bytes() == before
