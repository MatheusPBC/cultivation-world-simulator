"""Damage and repair are material: prepared facts, own stock, paid local work."""

import sqlite3

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta, monthly_workforce
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.infrastructure import damage_site, progress_repairs, review_maintenance
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.site_services import service_options, set_site_service

SITE = "docas-de-portovelho"


def damage(world, site_id, integrity, content="Tempestade danificou a instalação."):
    site = world.map.infrastructure_sites[site_id]
    fact = record_event(world, "storm_damaged_site", content, fact_kind=FactKind.STATE_TRANSITION,
                        deltas=(_delta("site", site_id, "integrity", site.integrity, integrity),))
    return fact, damage_site(world, site_id, event_id=fact.id)


def provisioned(world, site_id=SITE):
    """Prepared fixture: the maintainer already holds the repair materials.

    The blueprint cost is not calibrated to the bootstrap holdings; when a
    maintainer lacks them the missing material must be bought, which is what
    the supply test exercises.
    """
    site = world.map.infrastructure_sites[site_id]
    stock = next(s for _, s in sorted(world.economy.stocks.items())
                 if s.owner_ref == site.maintainer_ref
                 and world.society.settlements[s.location_id].region_id in site.region_ids)
    blueprint = next(b for _, b in sorted(world.economy.repair_blueprints.items()) if b.site_kind == site.kind)
    goods = {**stock.goods, **{rid: stock.goods.get(rid, 0) + amount * 10 for rid, amount in blueprint.inputs.items()}}
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": goods})
    return world.economy.stocks[stock.id], blueprint


def month(world):
    world.clock = world.clock.advance(30)
    refresh_reports(world)
    progress_repairs(world, monthly_workforce(world))


def test_damage_is_observed_repaired_gradually_and_the_route_recovers():
    world = create_medieval_world(73)
    provisioned(world)
    site = world.map.infrastructure_sites[SITE]
    route_id = site.route_ids[0]
    maintainer = site.maintainer_ref
    intact = world.map.get_route_operational_capacity(route_id)
    fact, site = damage(world, SITE, 0.8)
    assert site.integrity == 0.8 and site.last_event_id == fact.id and site.enabled
    damaged = world.map.get_route_operational_capacity(route_id)
    assert damaged < intact

    refresh_reports(world)
    report = world.knowledge.site_report(maintainer, SITE)
    assert report.integrity == 0.8 and report.publisher_ref == maintainer == report.recipient_ref
    review_maintenance(world)
    project = next(iter(world.economy.repairs.values()))
    assert project.site_id == SITE and project.stage == "waiting" and project.restored_permille == 0
    assert site.integrity == 0.8, "authorizing work repairs nothing by itself"
    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    goods = dict(world.economy.stocks[project.stock_id].goods)
    money = sum(a.balance for a in world.economy.accounts.values())

    capacities = []
    for _ in range(2):
        month(world)
        capacities.append(world.map.get_route_operational_capacity(route_id))
    assert damaged < capacities[0] < capacities[1] == intact
    assert site.integrity == 1.0
    project = world.economy.repairs[project.id]
    assert project.stage == "completed" and project.restored_permille == 200
    after = world.economy.stocks[project.stock_id]
    assert all(after.goods[rid] == goods[rid] - 2 * amount for rid, amount in blueprint.inputs.items())
    assert sum(a.balance for a in world.economy.accounts.values()) == money
    assert world.economy.payrolls[project.id].gross > 0
    receipt = next(e for e in world.events if e.id == project.last_event_id)
    assert any(d.owner_kind == "site" and d.owner_id == SITE and d.after == str(site.integrity)
               for d in receipt.deltas)
    # Knowledge lags the physical state: the last observation preceded the last batch.
    assert world.knowledge.site_report(maintainer, SITE).integrity == pytest.approx(0.9)


def authorized(world):
    """Damaged, observed and authorized: the obligation exists, no work done yet."""
    provisioned(world)
    damage(world, SITE, 0.8)
    refresh_reports(world)
    review_maintenance(world)
    return next(iter(world.economy.repairs.values()))


@pytest.mark.parametrize("rejection", ["stale_observation", "forged_observation", "replayed_decision", "forged_intent",
                                       "revoked_mandate", "foreign_stock"])
def test_the_owner_refuses_an_authorization_it_cannot_revalidate(rejection):
    from src.classes.economy.maintenance import repair_intent
    from src.sim.medieval.infrastructure import start_repair
    world = create_medieval_world(73)
    provisioned(world)
    damage(world, SITE, 0.8)
    refresh_reports(world)
    site = world.map.infrastructure_sites[SITE]
    maintainer = site.maintainer_ref
    stock = next(s for _, s in sorted(world.economy.stocks.items()) if s.owner_ref == maintainer
                 and world.society.settlements[s.location_id].region_id in site.region_ids)
    account = next(a for _, a in sorted(world.economy.accounts.items()) if a.owner_ref == maintainer)
    blueprint = next(b for _, b in sorted(world.economy.repair_blueprints.items()) if b.site_kind == site.kind)
    intent = repair_intent(maintainer, SITE, blueprint.id, stock.id, account.id)
    if rejection == "replayed_decision":
        review_maintenance(world)
        decision_id = world.economy.repairs[next(iter(world.economy.repairs))].decision_event_id
    else:
        if rejection == "stale_observation":
            world.clock = world.clock.advance(30)
        if rejection == "forged_observation":
            report = world.knowledge.site_report(maintainer, SITE)
            world.knowledge.site_reports[report.id] = report.model_copy(update={"integrity": 0.4})
        if rejection == "forged_intent":
            intent = {**intent, "stock_id": "stock:campomanso"}
        if rejection == "foreign_stock":
            intent = repair_intent(maintainer, SITE, blueprint.id, "stock:campomanso", account.id)
        if rejection == "revoked_mandate":
            office = world.authority.offices[f"office:{maintainer.kind}:{maintainer.id}"]
            world.authority.offices[office.id] = office.model_copy(update={"ends_day": 0})
        decision_id = record_event(world, "repair_decided", "Autorizar reparo.",
                                   fact_kind=FactKind.DECISION, decision=intent).id
    projects = dict(world.economy.repairs)
    with pytest.raises(ValueError, match="repair|decision|authority|observation"):
        start_repair(world, SITE, blueprint.id, decision_event_id=decision_id)
    assert world.economy.repairs == projects
    assert world.map.infrastructure_sites[SITE].integrity == 0.8


@pytest.mark.parametrize("impediment", ["materials", "funds", "workforce", "observation", "authority"])
def test_a_batch_without_its_real_conditions_spends_nothing(impediment):
    world = create_medieval_world(73)
    project = authorized(world)
    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    stock = world.economy.stocks[project.stock_id]
    resource_id = sorted(blueprint.inputs)[0]
    world.clock = world.clock.advance(30)
    if impediment != "observation":
        refresh_reports(world)
    if impediment == "materials":
        world.economy.stocks[stock.id] = world.economy.stocks[stock.id].model_copy(
            update={"goods": {**world.economy.stocks[stock.id].goods, resource_id: 0}})
    if impediment == "funds":
        account = world.economy.accounts[project.account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    if impediment == "authority":
        office = world.authority.offices[f"office:{project.maintainer_ref.kind}:{project.maintainer_ref.id}"]
        world.authority.offices[office.id] = office.model_copy(update={"ends_day": world.clock.absolute_day})
    available = monthly_workforce(world)
    if impediment == "workforce":
        available = {group_id: 0 for group_id in available}
    goods = dict(world.economy.stocks[project.stock_id].goods)
    money = sum(a.balance for a in world.economy.accounts.values())
    progress_repairs(world, available)
    blocked = world.economy.repairs[project.id]
    expected = {"materials": f"input:{resource_id}", "funds": "payroll_funds",
                "workforce": "labor", "observation": "observation", "authority": "authority"}[impediment]
    assert blocked.stage == "blocked" and blocked.blocker == expected
    assert blocked.restored_permille == 0, "a blocked obligation is neither paid nor forgiven"
    assert world.map.infrastructure_sites[SITE].integrity == 0.8
    assert world.economy.stocks[project.stock_id].goods == goods
    assert sum(a.balance for a in world.economy.accounts.values()) == money
    assert project.id not in world.economy.payrolls
    # Idempotence: a second pass on the same day repeats no work and no event.
    events = len(world.events)
    progress_repairs(world, available)
    assert len(world.events) == events


def test_an_expired_observation_keeps_the_committed_reserve():
    from src.sim.medieval.demand import repair_demand
    world = create_medieval_world(73)
    project = authorized(world)
    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    reserved = repair_demand(world, project.stock_id, "tools")
    assert reserved == blueprint.inputs["tools"] * 2
    world.clock = world.clock.advance(90)
    assert repair_demand(world, project.stock_id, "tools") == reserved, "the commitment outlives the report"
    progress_repairs(world, monthly_workforce(world))
    assert world.economy.repairs[project.id].blocker == "observation"


def test_repair_restores_integrity_without_lifting_an_interdiction():
    world = create_medieval_world(73)
    provisioned(world)
    site = world.map.infrastructure_sites[SITE]
    fact = record_event(world, "storm_damaged_site", "Docas interditadas pela tempestade.",
                        fact_kind=FactKind.STATE_TRANSITION,
                        deltas=(_delta("site", SITE, "integrity", site.integrity, 0.8),
                                _delta("site", SITE, "enabled", site.enabled, False)))
    damage_site(world, SITE, event_id=fact.id)
    refresh_reports(world)
    review_maintenance(world)
    project = next(iter(world.economy.repairs.values()))

    month(world)
    month(world)

    assert world.economy.repairs[project.id].stage == "completed"
    assert world.map.infrastructure_sites[SITE].integrity == 1.0
    assert world.map.infrastructure_sites[SITE].enabled is False


def test_an_active_repair_cannot_invent_demand_without_its_typed_observation():
    from src.sim.medieval.demand import repair_demand

    world = create_medieval_world(73)
    project = authorized(world)
    report = world.knowledge.site_report(project.maintainer_ref, SITE)
    del world.knowledge.site_reports[report.id]

    with pytest.raises(ValueError, match="typed site report"):
        world.economy.validate(world)
    with pytest.raises(ValueError, match="typed site report"):
        repair_demand(world, project.stock_id, "tools")


def test_missing_material_becomes_a_standing_supply_objective_not_a_stalled_project():
    world = create_medieval_world(73)
    damage(world, SITE, 0.8)
    refresh_reports(world)
    review_maintenance(world)
    project = next(iter(world.economy.repairs.values()))
    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    stock = world.economy.stocks[project.stock_id]
    # The guild holds no tools at all: the cost stands and the need must be sought.
    assert not stock.goods.get("tools")
    from src.sim.medieval.demand import objective_target, repair_demand
    from src.sim.medieval.procurement import review_supply
    objective = world.strategy.objectives[f"inputs:{stock.id}:tools"]
    assert objective.actor_ref == project.maintainer_ref and objective.resource_id == "tools"
    assert repair_demand(world, stock.id, "tools") == blueprint.inputs["tools"] * 2
    assert objective_target(world, objective) >= repair_demand(world, stock.id, "tools")

    world.clock = world.clock.advance(30)
    refresh_reports(world)
    assert any(r.stock_id == stock.id and r.kind == "inventory" and r.observed_day == world.clock.absolute_day
               for r in world.knowledge.for_actor(project.maintainer_ref))
    review_supply(world)
    plan = world.strategy.plans[f"plan:{objective.id}"]
    assert plan.stage in {"acquire", "await_delivery", "blocked"} and plan.last_review_day == world.clock.absolute_day
    assert plan.stage != "satisfied", "an unmet repair need must stay visibly unmet"


def test_damage_only_applies_a_prepared_material_fact():
    world = create_medieval_world(73)
    site = world.map.infrastructure_sites[SITE]
    prose = record_event(world, "rumor", "Dizem que as docas estão arruinadas.")
    decision = record_event(world, "repair_decided", "Intenção.", fact_kind=FactKind.DECISION,
                            decision={"action": "repair_site", "site_id": SITE})
    wrong = record_event(world, "storm_damaged_site", "Fato com valor anterior errado.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("site", SITE, "integrity", 0.4, 0.3),))
    raised = record_event(world, "storm_damaged_site", "Fato que aumentaria a integridade.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("site", SITE, "integrity", site.integrity, 1.0),))
    other = record_event(world, "storm_damaged_site", "Fato sobre outra instalação.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("site", "campos-do-lume", "integrity", 1.0, 0.5),))
    for event_id in (prose.id, decision.id, wrong.id, raised.id, other.id, "event:9999"):
        with pytest.raises(ValueError, match="site|fact|damage"):
            damage_site(world, SITE, event_id=event_id)
    assert site.integrity == 1.0 and site.last_event_id is None

    prepared = record_event(world, "storm_damaged_site", "Fato material antigo.",
                            fact_kind=FactKind.STATE_TRANSITION,
                            deltas=(_delta("site", SITE, "integrity", 1.0, 0.8),))
    world.clock = world.clock.advance(1)
    with pytest.raises(ValueError, match="site damage"):
        damage_site(world, SITE, event_id=prepared.id)

    fresh = create_medieval_world(73)
    fact, _ = damage(fresh, SITE, 0.8)
    with pytest.raises(ValueError, match="site delta|site damage"):
        damage_site(fresh, SITE, event_id=fact.id)


def test_an_interpretation_never_carries_or_causes_a_state_change():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="interpretation"):
        record_event(world, "storm_damaged_site", "Narrativa com efeito material.",
                     fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.LLM_INTERPRETATION,
                     deltas=(_delta("site", SITE, "integrity", 1.0, 0.5),))
    story = record_event(world, "story", "Interpretação narrativa.",
                         causal_origin=CausalOrigin.LLM_INTERPRETATION)
    with pytest.raises(ValueError, match="interpretation"):
        record_event(world, "storm_damaged_site", "Dano derivado da narrativa.",
                     fact_kind=FactKind.STATE_TRANSITION,
                     deltas=(_delta("site", SITE, "integrity", 1.0, 0.5),), cause_ids=(story.id,))
    validate_history(world.events, world.clock.absolute_day)


RIVER = "river-pedraclara-portovelho"


async def run_to(world, day):
    while world.clock.absolute_day < day:
        await MedievalSimulator(world).step()


def importing_world():
    """Prepared scarcity: Portovelho has no food of its own and must import."""
    from src.classes.mechanical_language import EntityRef
    world = create_medieval_world(73)
    provisioned(world)
    for key, stock in list(world.economy.stocks.items()):
        if stock.owner_ref == EntityRef("polity", "valedouro"):
            world.economy.stocks[key] = stock.model_copy(update={"goods": {**stock.goods, "food": 0}})
    return world


@pytest.mark.asyncio
async def test_a_damaged_crossing_delays_cargo_and_the_repaired_one_delivers_again():
    world = importing_world()
    await run_to(world, 30)
    crossing = [o for o in world.economy.freight_orders.values() if RIVER in o.route_ids]
    assert crossing, "the prepared scarcity must produce a shipment across the river"
    order = sorted(crossing, key=lambda o: o.id)[0]
    site = world.map.infrastructure_sites[SITE]
    assert site.id in {s.id for s in world.map.get_route_dependency_sites(RIVER)}

    # The road leg reaches Pedraclara on day 35; the river departure is due on
    # day 36, so damage must land between those two physical resolutions.
    await run_to(world, 35)
    fact, site = damage(world, SITE, 0.002)
    assert world.map.get_route_operational_capacity(RIVER) < 1
    await run_to(world, 36)
    delayed = [e for e in world.events if e.event_type == "cargo_delayed" and e.sequence > fact.sequence]
    assert delayed and any(fact.id in {link.cause_event_id for link in e.causal_links} for e in delayed)
    assert world.economy.freight_orders[order.id].delivered_quantity == 0

    await run_to(world, 60)
    project = next(p for p in world.economy.repairs.values() if p.site_id == SITE)
    assert project.stage == "waiting" and world.economy.needs["portovelho"].missing_food > 0
    money = sum(a.balance for a in world.economy.accounts.values())
    materials = dict(world.economy.stocks[project.stock_id].goods)
    blueprint = world.economy.repair_blueprints[project.blueprint_id]

    await run_to(world, 90)
    project = world.economy.repairs[project.id]
    assert project.restored_permille == 100 and project.stage == "repairing"
    # Material repair does not silently reopen the proprietor's own service.
    # The conservative policy only resumes after the observed 70% threshold.
    assert world.map.get_route_operational_capacity(RIVER) == 0
    repaired = next(e for e in world.events if e.id == project.last_event_id)
    repaired_stock = world.economy.stocks[project.stock_id]
    assert all(repaired_stock.goods[resource_id] == materials[resource_id] - amount
               for resource_id, amount in blueprint.inputs.items())
    assert world.economy.payrolls[project.id].gross > 0

    # Repair changes no service decision.  The actual owner must observe the
    # new condition and elect to reopen before the held parcel can move.
    refresh_reports(world)
    owner = world.map.infrastructure_sites[SITE].owner_ref
    option, = service_options(world, SITE, owner)
    decision = record_event(world, "site_service_decided", "Retomar serviço das docas.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    set_site_service(world, option.id, decision_event_id=decision.id)
    assert world.map.get_route_operational_capacity(RIVER) >= 1

    await run_to(world, 120)
    assert world.economy.freight_orders[order.id].delivered_quantity > 0
    deliveries = [e for e in world.events if e.event_type == "cargo_delivered"
                  and any(d.owner_kind == "freight" and d.owner_id == order.id for d in e.deltas)]
    assert deliveries and deliveries[-1].sequence > repaired.sequence
    assert sum(a.balance for a in world.economy.accounts.values()) == money


@pytest.mark.asyncio
async def test_a_failed_save_on_the_repairing_jump_restores_work_money_and_the_site(tmp_path, monkeypatch):
    world = importing_world()
    await run_to(world, 30)
    damage(world, SITE, 0.5)
    await run_to(world, 60)
    project = next(p for p in world.economy.repairs.values() if p.site_id == SITE)
    assert project.stage == "waiting" and project.restored_permille == 0
    # Stop before the monthly jump that will execute the first batch.  Other
    # dated work may make this a day before the boundary, so do not hard-code it.
    from src.systems.calendar_scheduler import CalendarScheduler
    while CalendarScheduler.next_jump(world.clock, world.agenda.due_days).to_day != 90:
        await MedievalSimulator(world).step()
    path = tmp_path / "repair.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert resumed.economy.repairs == world.economy.repairs
    assert resumed.map.infrastructure_sites[SITE].integrity == 0.5

    # Prove the next candidate actually contains repair work before testing the
    # failed durable commit; this is not merely a rollback of an idle jump.
    control = load_world(path)
    await MedievalSimulator(control).step()
    assert control.economy.repairs[project.id].restored_permille == 100
    assert control.map.infrastructure_sites[SITE].integrity == pytest.approx(0.6)

    before, history = world_snapshot(world), list(world.events)
    rng_state, knowledge = world.rng.getstate(), world.knowledge.to_dict()
    from src.sim.medieval import engine

    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="disk"):
        await MedievalSimulator(world, save_path=tmp_path / "failed.mws").step()
    assert world.clock.absolute_day == resumed.clock.absolute_day
    assert world_snapshot(world) == before and world.events == history
    assert world.rng.getstate() == rng_state and world.knowledge.to_dict() == knowledge
    assert world.economy.repairs[project.id].restored_permille == 0
    assert world.map.infrastructure_sites[SITE].integrity == 0.5
    monkeypatch.undo()

    await MedievalSimulator(world).step()
    assert world.economy.repairs[project.id].restored_permille == 100
    assert world.map.infrastructure_sites[SITE].integrity == pytest.approx(0.6)
    assert world_snapshot(world) == world_snapshot(control)

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=12")
    saved = path.read_bytes()
    with pytest.raises(ValueError, match="Unsupported"):
        load_world(path)
    assert path.read_bytes() == saved
