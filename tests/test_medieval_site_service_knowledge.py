"""Service suspension is physical knowledge, not authority or a global broadcast."""

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports, refresh_site_reports
from src.sim.medieval.site_services import service_options, set_site_service


SITE = "passagem-negra"


def suspend(world):
    site = world.map.infrastructure_sites[SITE]
    option = service_options(world, SITE, site.owner_ref)[0]
    decision = record_event(world, "site_service_requested", "Suspender serviço próprio.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    event = set_site_service(world, option.id, decision_event_id=decision.id)
    refresh_site_reports(world, site_ids=(SITE,))
    refresh_route_reports(world, route_ids=site.route_ids)
    return event


def test_service_change_replaces_its_own_same_day_observation_and_closes_routes():
    world = create_medieval_world(73)
    refresh_reports(world)
    site = world.map.infrastructure_sites[SITE]
    owner = site.owner_ref
    previous = world.knowledge.site_report(owner, SITE)

    changed = suspend(world)
    report = world.knowledge.site_report(owner, SITE)
    assert report.service_suspended is True and report.event_id != previous.event_id
    receipt = next(event for event in world.events if event.id == report.event_id)
    assert changed.id in {link.cause_event_id for link in receipt.causal_links}
    assert all(world.knowledge.route_report(owner, route_id).operational_capacity == 0
               for route_id in site.route_ids)

    event_count = len(world.events)
    refresh_site_reports(world, site_ids=(SITE,))
    refresh_route_reports(world, route_ids=site.route_ids)
    assert len(world.events) == event_count, "unchanged readings do not duplicate same-day receipts"


def test_stale_observation_cannot_create_a_service_affordance_after_physical_change():
    world = create_medieval_world(73)
    refresh_reports(world)
    site = world.map.infrastructure_sites[SITE]
    owner = site.owner_ref
    assert world.knowledge.site_report(owner, SITE).service_suspended is False

    world.map.update_infrastructure_site_runtime(SITE, service_suspended=True)
    assert service_options(world, SITE, owner) == ()


def test_only_a_present_owner_or_maintainer_receives_private_site_knowledge():
    world = create_medieval_world(73)
    refresh_reports(world)
    site = world.map.infrastructure_sites[SITE]
    present = {site.owner_ref, site.maintainer_ref}
    outsider = next(EntityRef("polity", polity_id) for polity_id in sorted(world.society.polities)
                   if EntityRef("polity", polity_id) not in present)

    assert world.knowledge.site_report(site.owner_ref, SITE) is not None
    assert world.knowledge.site_report(outsider, SITE) is None


def test_service_report_metadata_survives_save_load_and_replay(tmp_path):
    world = create_medieval_world(73)
    refresh_reports(world)
    changed = suspend(world)
    owner = world.map.infrastructure_sites[SITE].owner_ref
    report = world.knowledge.site_report(owner, SITE)
    path = tmp_path / "service-knowledge.mws"
    save_world(world, path)
    resumed = load_world(path)

    restored = resumed.knowledge.site_report(owner, SITE)
    assert restored.service_suspended is True
    assert restored.observation() == report.observation()
    assert restored.event_id == report.event_id
    validate_history(resumed.events, resumed.clock.absolute_day)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert changed.id in {link.cause_event_id for link in resumed.events[int(restored.event_id.split(":")[1]) - 1].causal_links}
