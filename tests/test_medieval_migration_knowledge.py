"""Knowledge boundaries for migration: public aggregates, not omniscient cohorts."""

import pytest

from src.classes.governance.knowledge import settlement_report_id
from src.classes.mechanical_language import EntityRef
from src.classes.event import FactKind
from src.classes.society.migration import MigrationJourney
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, restore_snapshot, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


def local_group(world, settlement_id):
    return next(EntityRef("population_group", group.id) for group in world.society.population.values()
                if group.settlement_id == settlement_id and world.society.available_count(group.id) > 0)


def test_a_present_cohort_receives_its_own_aggregate_without_institutional_authority():
    world = create_medieval_world(73)
    group = local_group(world, "campomanso")
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(group, "campomanso")
    assert report is not None
    assert report.channel == "local_settlement_report" and report.publisher_ref == group
    assert report.population == world.society.population_at("campomanso")
    assert report.present_population == world.society.present_population_at("campomanso")
    assert report.housing_capacity == world.society.settlements["campomanso"].housing_capacity
    assert report.health == world.economy.needs["campomanso"].health
    assert report.missing_food == world.economy.needs["campomanso"].missing_food
    receipt = next(event for event in world.events if event.id == report.event_id)
    assert receipt.event_type == "settlement_observed"
    world.knowledge.validate(world)


def test_remote_group_learns_only_after_a_physically_reachable_administrative_bulletin():
    world = create_medieval_world(73)
    source = "campomanso"
    remote = local_group(world, "pedraclara")
    for route in world.map.routes.values():
        route.update_runtime(enabled=False)
    refresh_settlement_reports(world)
    assert world.knowledge.settlement_report(remote, source) is None


def test_administrative_bulletin_reaches_a_connected_foreign_cohort_but_does_not_replace_its_own_report():
    world = create_medieval_world(73)
    source, target = "campomanso", "pedraclara"
    local = local_group(world, source)
    foreign = local_group(world, target)
    refresh_settlement_reports(world)
    own = world.knowledge.settlement_report(local, source)
    delivered = world.knowledge.settlement_report(foreign, source)
    assert own is not None and own.channel == "local_settlement_report" and own.publisher_ref == local
    assert delivered is not None and delivered.channel == "settlement_bulletin"
    assert delivered.recipient_ref == foreign and delivered.publisher_ref.kind == "polity"
    receipt = next(event for event in world.events if event.id == delivered.event_id)
    assert receipt.event_type == "settlement_report_received"


def test_forged_or_stale_settlement_receipt_is_rejected_without_reading_current_truth():
    world = create_medieval_world(73)
    group = local_group(world, "campomanso")
    refresh_settlement_reports(world)
    key = settlement_report_id(group, "campomanso")
    snapshot = world_snapshot(world)
    snapshot["knowledge"]["settlement_reports"][key]["health"] = 0
    with pytest.raises(ValueError, match="settlement|receipt|provenance"):
        restore_snapshot(snapshot, world.events)
    snapshot = world_snapshot(world)
    snapshot["knowledge"]["settlement_reports"][key]["observed_day"] = world.clock.absolute_day + 1
    with pytest.raises(ValueError, match="settlement|receipt|provenance"):
        restore_snapshot(snapshot, world.events)


def test_publication_decision_without_its_delivery_cannot_be_forged_into_knowledge():
    world = create_medieval_world(73)
    refresh_settlement_reports(world)
    original = next(report for report in world.knowledge.settlement_reports.values()
                    if report.channel == "settlement_bulletin")
    publication = next(event for event in world.events if event.event_type == "settlement_report_published"
                       and event.decision["settlement_id"] == original.settlement_id
                       and original.recipient_ref.to_dict() in event.decision["recipients"])
    forged = original.model_copy(update={"event_id": publication.id})
    world.knowledge.settlement_reports[forged.id] = forged
    with pytest.raises(ValueError, match="settlement|delivery|receipt"):
        world.knowledge.validate(world)


def test_resident_and_present_population_diverge_with_the_departure_receipt_as_source():
    world = create_medieval_world(73)
    group = next(group for group in world.society.population.values() if group.settlement_id == "campomanso")
    departure = record_event(world, "migration_started", "Uma parte da coorte partiu.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("population_group", group.id, "present_count", group.count, group.count - 1),))
    world.society.population[group.id] = group.model_copy(update={"last_event_id": departure.id})
    world.society.migrations["journey:test"] = MigrationJourney(
        id="journey:test", source_group_id=group.id, destination_id="pedraclara", count=1,
        character_ids=(), route_ids=("road-campomanso-pedraclara",), initial_destination_id="pedraclara",
        initial_route_ids=("road-campomanso-pedraclara",), due_day=1,
        decision_event_id=departure.id, provision_id="migration-provision:test", last_event_id=departure.id)
    refresh_settlement_reports(world)
    report = world.knowledge.settlement_report(EntityRef("population_group", group.id), "campomanso")
    assert report.population == world.society.population_at("campomanso")
    assert report.present_population == report.population - 1
    receipt = next(event for event in world.events if event.id == report.event_id)
    assert departure.id in {link.cause_event_id for link in receipt.causal_links}


def test_save_load_keeps_the_dated_settlement_dto_and_route_bulletin_for_a_group_without_objectives(tmp_path):
    world = create_medieval_world(73)
    group = local_group(world, "campomanso")
    world.strategy.objectives.clear()
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    own = world.knowledge.settlement_report(group, "campomanso")
    routes = world.knowledge.routes_for_actor(group)
    assert own is not None and own.channel == "local_settlement_report"
    assert routes and all(report.channel == "route_bulletin" for report in routes)
    path = tmp_path / "migration-knowledge.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.knowledge.settlement_report(group, "campomanso") == own
    assert resumed.knowledge.routes_for_actor(group) == routes
