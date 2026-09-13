"""Owner suspension of a port/pass service, without inventing a blockade."""

import pytest

from src.classes.economy.models import Stock
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.infrastructure import damage_site
from src.sim.medieval.persistence import load_world, restore_snapshot, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.site_services import review_site_services, service_options, set_site_service
from src.systems.time import WorldClock


SITE = "docas-de-portovelho"
RIVER = "river-pedraclara-portovelho"


def _world():
    world = create_medieval_world(73)
    refresh_site_reports(world, site_ids=(SITE,))
    return world


def _decide(world, site_id=SITE):
    owner = world.map.infrastructure_sites[site_id].owner_ref
    option, = service_options(world, site_id, owner)
    decision = record_event(world, "site_service_decided", "Decisão do proprietário.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(world.knowledge.site_report(owner, site_id).event_id,))
    return set_site_service(world, option.id, decision_event_id=decision.id)


async def test_suspension_holds_the_same_parcel_then_resumption_delivers(tmp_path):
    world = _world()
    _decide(world)
    assert world.map.get_route_operational_capacity(RIVER) == 0
    source = world.economy.stocks["stock:pedraclara"]
    world.economy.stocks["depot:auren-portovelho"] = Stock(
        id="depot:auren-portovelho", owner_ref=source.owner_ref,
        location_id="portovelho", capacity=1000,
    )
    from src.sim.medieval.logistics import queue_freight
    choice = record_event(world, "freight_decided", "Remessa própria autorizada.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "freight", "source_id": source.id,
                                    "destination_id": "depot:auren-portovelho", "resource_id": "food",
                                    "quantity": 50, "route_ids": [RIVER],
                                    "actor_ref": source.owner_ref.to_dict()})
    order = queue_freight(world, source.id, "depot:auren-portovelho", "food", 50, (RIVER,),
                          decision_event_id=choice.id)
    engine = MedievalSimulator(world)
    await engine.step()
    assert next(iter(world.economy.parcels.values())).stage == "waiting"
    assert world.economy.freight_orders[order.id].delivered_quantity == 0

    refresh_site_reports(world, site_ids=(SITE,))
    _decide(world)
    assert world.map.get_route_operational_capacity(RIVER) > 0
    path = tmp_path / "service.mws"
    save_world(world, path)
    resumed = load_world(path)
    while world.economy.parcels:
        await engine.step()
        await MedievalSimulator(resumed).step()
    assert world.economy.stocks["depot:auren-portovelho"].goods["food"] == 50
    assert world_snapshot(world) == world_snapshot(resumed)


def test_maintainer_cannot_suspend_another_owners_port_and_stale_or_forged_choice_is_atomic():
    world = _world()
    site = world.map.infrastructure_sites[SITE]
    world.map.infrastructure_sites[SITE] = type(site).from_dict({
        **site.to_dict(), "maintainer_ref": EntityRef("polity", "auren").to_dict(),
    })
    refresh_site_reports(world, site_ids=(SITE,))
    maintainer = EntityRef("polity", "auren")
    assert service_options(world, SITE, maintainer) == ()
    forged = record_event(world, "site_service_decided", "Imitação sem posse.",
                          fact_kind=FactKind.DECISION,
                          decision={"action": "suspend_site_service", "actor_ref": maintainer.to_dict(),
                                    "option_id": "invented", "site_id": SITE,
                                    "report_id": "invented"})
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale"):
        set_site_service(world, "invented", decision_event_id=forged.id)
    assert world_snapshot(world) == before

    owner = world.map.infrastructure_sites[SITE].owner_ref
    option, = service_options(world, SITE, owner)
    stale = record_event(world, "site_service_decided", "Escolha atrasada.",
                         fact_kind=FactKind.DECISION, decision=option.decision())
    world.clock = WorldClock(1)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale"):
        set_site_service(world, option.id, decision_event_id=stale.id)
    assert world_snapshot(world) == before


def test_owner_change_invalidates_a_current_option_without_mutation():
    world = _world()
    site = world.map.infrastructure_sites[SITE]
    owner = site.owner_ref
    option, = service_options(world, SITE, owner)
    decision = record_event(world, "site_service_decided", "Escolha sob a posse anterior.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    world.map.infrastructure_sites[SITE] = type(site).from_dict({
        **site.to_dict(), "owner_ref": EntityRef("polity", "auren").to_dict(),
    })
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale"):
        set_site_service(world, option.id, decision_event_id=decision.id)
    assert world_snapshot(world) == before


def test_disabled_site_never_reenables_when_service_is_resumed():
    world = _world()
    world.map.update_infrastructure_site_runtime(SITE, enabled=False, service_suspended=True)
    refresh_site_reports(world, site_ids=(SITE,))
    _decide(world)
    site = world.map.infrastructure_sites[SITE]
    assert site.service_suspended is False and site.enabled is False
    assert world.map.get_route_operational_capacity(RIVER) == 0


async def test_monthly_policy_suspends_from_own_report_and_failed_commit_is_rollback(tmp_path, monkeypatch):
    world = _world()
    world.clock = WorldClock(29)
    site = world.map.infrastructure_sites[SITE]
    fact = record_event(world, "storm_damaged_site", "Tempestade danificou as docas.",
                        fact_kind=FactKind.STATE_TRANSITION,
                        deltas=(_delta("site", SITE, "integrity", site.integrity, 0.3),))
    damage_site(world, SITE, event_id=fact.id)
    path = tmp_path / "rollback.mws"
    save_world(world, path)
    before = world_snapshot(world)
    monkeypatch.setattr("src.sim.medieval.engine.save_world", lambda *_: (_ for _ in ()).throw(OSError("disk failure")))
    with pytest.raises(OSError, match="disk failure"):
        await MedievalSimulator(world, save_path=path).step()
    assert world_snapshot(world) == world_snapshot(load_world(path)) == before
    monkeypatch.undo()
    await MedievalSimulator(world, save_path=path).step()
    assert world.map.infrastructure_sites[SITE].service_suspended is True
    assert world.map.get_route_operational_capacity(RIVER) == 0


def test_policy_requires_current_observed_thresholds_and_persistence_requires_service_state():
    world = _world()
    assert review_site_services(world) == ()
    snapshot = world_snapshot(world)
    del snapshot["map"]["infrastructure_sites"][0]["service_suspended"]
    with pytest.raises(ValueError, match="service state"):
        restore_snapshot(snapshot, world.events)
