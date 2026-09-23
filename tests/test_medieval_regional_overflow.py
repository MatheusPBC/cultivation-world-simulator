"""Focused proof for the bounded medieval regional-overflow vertical."""

from __future__ import annotations

import sqlite3

import pytest

from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world
from src.sim.medieval import regional_overflow


SITE_ID = "docas-de-portovelho"
REGION_ID = 802


async def _advance_to(world, day: int) -> None:
    simulator = MedievalSimulator(world)
    while world.clock.absolute_day < day:
        await simulator.step()


def _force_load(monkeypatch, *, high: bool) -> None:
    monkeypatch.setattr(
        regional_overflow,
        "regional_hydrologic_load",
        lambda _world, region_id: 100 if high and region_id == REGION_ID else 0,
    )


def _provision_repair(world):
    site = world.map.infrastructure_sites[SITE_ID]
    stock = next(
        stock
        for _, stock in sorted(world.economy.stocks.items())
        if stock.owner_ref == site.maintainer_ref
        and world.society.settlements[stock.location_id].region_id in site.region_ids
    )
    blueprint = next(
        blueprint
        for _, blueprint in sorted(world.economy.repair_blueprints.items())
        if blueprint.site_kind == site.kind
    )
    world.economy.stocks[stock.id] = stock.model_copy(
        update={
            "goods": {
                **stock.goods,
                **{
                    resource_id: stock.goods.get(resource_id, 0) + amount * 10
                    for resource_id, amount in blueprint.inputs.items()
                },
            }
        }
    )


def test_site_overflow_reading_is_geography_only_before_any_assessment():
    world = create_medieval_world(73)
    reading = regional_overflow.site_overflow_reading(world, SITE_ID)

    assert reading["site_id"] == SITE_ID
    assert reading["vulnerability"] == regional_overflow.site_overflow_vulnerability(
        world, world.map.infrastructure_sites[SITE_ID])
    region = next(item for item in reading["regions"] if item["region_id"] == REGION_ID)
    assert region["last_assessed_load"] is None
    assert region["last_assessed_streak"] is None
    assert region["last_assessed_day"] is None
    assert region["assessment_event_id"] is None
    assert region["open_occurrence"] is None


def test_site_overflow_reading_of_an_unknown_site_is_none():
    world = create_medieval_world(73)
    assert regional_overflow.site_overflow_reading(world, "not-a-real-site") is None


@pytest.mark.asyncio
async def test_site_overflow_reading_projects_the_last_assessment_and_open_occurrence(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)

    await _advance_to(world, 60)

    reading = regional_overflow.site_overflow_reading(world, SITE_ID)
    region = next(item for item in reading["regions"] if item["region_id"] == REGION_ID)
    assessment = world.regional_overflow.assessment(REGION_ID)
    occurrence = world.regional_overflow.occurrence(REGION_ID)

    assert region["last_assessed_load"] == assessment.load
    assert region["last_assessed_streak"] == assessment.streak
    assert assessment.streak >= regional_overflow.OVERFLOW_CONSECUTIVE_MONTHS
    assert region["last_assessed_day"] == 60
    assessment_event = next(item for item in world.events if item.id == region["assessment_event_id"])
    assert assessment_event.event_type == "regional_hydrologic_load_assessed"

    assert occurrence is not None
    assert region["open_occurrence"] == {
        "started_day": occurrence.started_day, "load": occurrence.load,
        "assessment_event_id": occurrence.assessment_event_id,
        "started_event_id": occurrence.started_event_id,
    }
    started_event = next(item for item in world.events if item.id == occurrence.started_event_id)
    assert started_event.event_type == "regional_overflow_started"
    # Only this site's own regions are read; nothing foreign or predicted.
    assert {item["region_id"] for item in reading["regions"]} == set(
        world.map.infrastructure_sites[SITE_ID].region_ids)


@pytest.mark.asyncio
async def test_nonrecurring_water_load_never_opens_an_overflow(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=False)

    await _advance_to(world, 60)

    assert world.regional_overflow.active_occurrences == {}
    # A real cargo departure of 90 crossed this route, but ordinary operating
    # wear has an explicit 100-bulk monthly threshold.  Neither low activity
    # nor the absence of an overflow may manufacture physical damage.
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(1.0)
    assert not any(
        event.event_type == "site_worn"
        and any(delta.owner_kind == "site" and delta.owner_id == SITE_ID for delta in event.deltas)
        for event in world.events
    )
    assert not any(event.event_type == "regional_overflow_started" for event in world.events)


@pytest.mark.asyncio
async def test_later_hydrologic_assessment_retains_the_prior_month_receipt(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=False)
    await _advance_to(world, 30)
    first = world.regional_overflow.assessment(REGION_ID).evidence_event_id

    await _advance_to(world, 60)
    second = next(event for event in world.events
                  if event.id == world.regional_overflow.assessment(REGION_ID).evidence_event_id)

    assert first in {link.cause_event_id for link in second.causal_links}


@pytest.mark.asyncio
async def test_sustained_load_damages_one_water_site_is_observed_and_enters_existing_repair_path(monkeypatch):
    world = create_medieval_world(73)
    _provision_repair(world)
    _force_load(monkeypatch, high=True)
    site = world.map.infrastructure_sites[SITE_ID]
    route = world.map.routes[site.route_ids[0]]
    nominal = route.capacity
    intact_operational = world.map.get_route_operational_capacity(route.id)

    await _advance_to(world, 30)
    assert world.regional_overflow.occurrence(REGION_ID) is None
    await _advance_to(world, 60)

    occurrence = world.regional_overflow.occurrence(REGION_ID)
    assert occurrence is not None and occurrence.damaged_site_id == SITE_ID
    # The registered flood interaction owns the bounded loss (0.075 here).
    # Cargo did traverse the dependent route, but only 90 bulk moved and the
    # independent operating-wear law requires 100, so it contributes no loss.
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)
    assert route.capacity == nominal
    assert world.map.get_route_operational_capacity(route.id) < intact_operational
    start = next(event for event in world.events if event.id == occurrence.started_event_id)
    damage = next(event for event in world.events if event.id == occurrence.damage_event_id)
    assert occurrence.assessment_event_id in {link.cause_event_id for link in start.causal_links}
    assert occurrence.started_event_id in {link.cause_event_id for link in damage.causal_links}
    assert any(delta.owner_kind == "site" and delta.owner_id == SITE_ID
               and delta.aspect == "integrity" for delta in damage.deltas)
    assert damage.causal_payload["hazard_kind"] == "regional_flood"
    assert damage.causal_payload["target_id"] == SITE_ID
    assert damage.causal_payload["magnitude"] == pytest.approx(0.075)

    # Reports were refreshed after the damage in the same boundary. The legacy
    # repair executor is merely offered/authorized by its standing policy; this
    # overflow code itself made neither a decision nor a repair mutation.
    report = world.knowledge.site_report(world.map.infrastructure_sites[SITE_ID].maintainer_ref, SITE_ID)
    assert report is not None and report.observed_day == 60 and report.integrity == pytest.approx(0.925)
    from src.server.medieval.queries import world_view

    observer = world_view(world)
    assert [item.id for item in observer.regional_overflows] == [occurrence.id]
    assert not hasattr(world.knowledge, "regional_overflows")
    project = next(project for project in world.economy.repairs.values() if project.site_id == SITE_ID)
    assert project.stage == "waiting"

    await _advance_to(world, 90)
    assert world.map.infrastructure_sites[SITE_ID].integrity > 0.84
    assert world.regional_overflow.occurrence(REGION_ID).damage_event_id == occurrence.damage_event_id
    assert len([event for event in world.events if event.event_type == "site_overflow_damaged"]) == 1


@pytest.mark.asyncio
async def test_overflow_never_repairs_when_the_maintainer_has_no_current_authority(monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)
    site = world.map.infrastructure_sites[SITE_ID]
    office = world.authority.offices[f"office:{site.maintainer_ref.kind}:{site.maintainer_ref.id}"]
    world.authority.offices[office.id] = office.model_copy(update={"ends_day": 0})

    await _advance_to(world, 60)
    assert world.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)
    assert not any(project.site_id == SITE_ID for project in world.economy.repairs.values())

    # No overflow-specific decision/project was created. A later normal use
    # receipt may still wear the site; that distinct Map law is not a repair.
    from src.sim.medieval.economy import monthly_workforce
    from src.sim.medieval.infrastructure import progress_repairs

    integrity_after_damage = world.map.infrastructure_sites[SITE_ID].integrity
    progress_repairs(world, monthly_workforce(world))
    assert world.map.infrastructure_sites[SITE_ID].integrity == integrity_after_damage
    assert len([event for event in world.events if event.event_type == "site_overflow_damaged"]) == 1


@pytest.mark.asyncio
async def test_overflow_assessment_round_trips_before_the_second_month(tmp_path, monkeypatch):
    world = create_medieval_world(73)
    _force_load(monkeypatch, high=True)

    await _advance_to(world, 30)
    saved_assessment = world.regional_overflow.assessment(REGION_ID)
    assert saved_assessment is not None and saved_assessment.streak == 1
    path = tmp_path / "overflow.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.regional_overflow.to_dict() == world.regional_overflow.to_dict()

    await _advance_to(restored, 60)
    occurrence = restored.regional_overflow.occurrence(REGION_ID)
    assert occurrence is not None and occurrence.damaged_site_id == SITE_ID
    assert restored.map.infrastructure_sites[SITE_ID].integrity == pytest.approx(0.925)


def test_schema_twenty_one_is_explicitly_rejected_without_migration(tmp_path):
    path = tmp_path / "schema-21.mws"
    save_world(create_medieval_world(73), path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET schema_version=21")
    with pytest.raises(ValueError, match="Unsupported Medieval World Simulator save"):
        load_world(path)
