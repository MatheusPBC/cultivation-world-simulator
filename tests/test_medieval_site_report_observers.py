"""Regression: a same-day expansion payroll must not crash site observation.

``_local_site_observers`` (route_intelligence.py) looks up each paid work item
by ``payroll.id`` across facilities/expansions/repairs/research. An expansion
project is keyed by its own facility, not by a site directly, so it must be
resolved through ``economy.facilities[project.facility_id].site_id`` rather
than a non-existent ``project.site_id``.
"""

from src.classes.event import FactKind
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import progress_expansions, start_expansion
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.run.medieval_world import create_medieval_world
from src.systems.time import WorldClock


def _start_expansion(world):
    facility = world.economy.facilities["works:minas-de-ferroalto"]
    owner = world.economy.stocks[facility.stock_id].owner_ref
    event = record_event(world, "expansion_decided", "Ampliar serraria.", fact_kind=FactKind.DECISION,
                         decision={"action": "expand", "actor_ref": owner.to_dict(),
                                   "facility_id": facility.id, "blueprint_id": "workshop-extension"})
    return start_expansion(world, facility.id, "workshop-extension", decision_event_id=event.id), owner


def test_expansion_payroll_same_day_does_not_crash_site_refresh_and_grants_observation():
    world = create_medieval_world(73)
    project, owner = _start_expansion(world)
    world.clock = WorldClock(30)
    available = {g.id: g.count for g in world.society.population.values()}
    progress_expansions(world, available)
    facility = world.economy.facilities[project.facility_id]

    refresh_site_reports(world, site_ids=(facility.site_id,))

    report = world.knowledge.site_report(owner, facility.site_id)
    assert report is not None
    assert report.observed_day == 30
