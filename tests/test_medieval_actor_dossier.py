"""Focused contract for the generic actor decision dossier."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval.actor_dossier import build_actor_dossier
from tests.test_medieval_institutional_aid import REQUESTER, prepared_world

OTHER = EntityRef("polity", "valedouro")


def test_dossier_exposes_only_actors_own_known_reports_objectives_and_scopes():
    world = prepared_world()
    dossier = build_actor_dossier(world, REQUESTER)

    assert dossier["actor"] == REQUESTER.to_dict()
    assert dossier["today"] == world.clock.absolute_day

    own_reports = world.knowledge.settlements_for_actor(REQUESTER)
    assert len(dossier["known_settlement_reports"]) == len(own_reports)
    assert all(report["settlement_id"] in {r.settlement_id for r in own_reports}
              for report in dossier["known_settlement_reports"])

    assert dossier["authority_scopes"]
    assert all(scope in {"trade", "supply", "taxation", "research", "diplomacy", "military"}
              for scope in dossier["authority_scopes"])

    def _signature(objective):
        return (objective.settlement_id, objective.resource_id, objective.kind)

    own_signatures = {_signature(o) for o in world.strategy.objectives.values() if o.actor_ref == REQUESTER}
    dossier_signatures = {(item["settlement_id"], item["resource_id"], item["kind"])
                          for item in dossier["own_objectives"]}
    assert dossier_signatures == own_signatures
    # The objective's own raw id is only an internal basis (it may embed a
    # stock's address); it is not itself information the actor is owed.
    assert not any("objective_id" in item for item in dossier["own_objectives"])

    # A foreign actor's own objectives never leak into this actor's dossier.
    other_signatures = {_signature(o) for o in world.strategy.objectives.values() if o.actor_ref == OTHER}
    assert not (other_signatures & own_signatures)
    assert not (dossier_signatures & other_signatures)


def test_dossier_projects_affordability_from_subsistence_receipt_without_private_balances():
    from src.classes.mechanical_language import EntityRef
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.economy import consume_monthly
    from src.sim.medieval.intelligence import refresh_reports
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.clock = WorldClock(30)
    target = "pedraclara"
    stock = world.economy.stocks[f"stock:{target}"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 1000}})
    consume_monthly(world)
    refresh_reports(world)

    report = next(item for item in build_actor_dossier(world, EntityRef("polity", "auren"))["known_settlement_reports"]
                   if item["settlement_id"] == target)
    assert report["unaffordable_food"] > 0
    assert report["unaffordable_group_count"] > 0
    assert report["affordability_event_id"].startswith("event:")
    assert "household" not in report and "balance" not in report


def test_affordability_waits_for_an_observation_after_the_material_closing():
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.economy import consume_monthly
    from src.sim.medieval.intelligence import refresh_reports
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.clock = WorldClock(30)
    refresh_reports(world)
    local = EntityRef("polity", "auren")
    remote = EntityRef("population_group", "pop:campomanso:human:farmer")
    target = "pedraclara"
    assert world.knowledge.settlement_report(remote, target) is not None

    consume_monthly(world)
    for actor in (local, remote):
        report = next(item for item in build_actor_dossier(world, actor)["known_settlement_reports"]
                      if item["settlement_id"] == target)
        assert report["affordability_event_id"] is None
        assert report["unaffordable_food"] == 0

    refresh_reports(world)
    local_report = next(item for item in build_actor_dossier(world, local)["known_settlement_reports"]
                        if item["settlement_id"] == target)
    remote_report = next(item for item in build_actor_dossier(world, remote)["known_settlement_reports"]
                         if item["settlement_id"] == target)
    assert local_report["affordability_event_id"] is not None
    assert local_report["unaffordable_food"] > 0
    # One bulletin per recipient/day: the already-delivered bulletin does not
    # gain an observation that happened after it was sent.
    assert remote_report["affordability_event_id"] is None

    world.clock = WorldClock(31)
    refresh_reports(world)
    remote_report = next(item for item in build_actor_dossier(world, remote)["known_settlement_reports"]
                         if item["settlement_id"] == target)
    assert remote_report["affordability_event_id"] == local_report["affordability_event_id"]


def test_dossier_projects_only_own_dated_production_limits():
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.economy import produce_monthly
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    world.clock = WorldClock(30)
    produce_monthly(world)

    owner = next(iter(world.economy.facilities.values())).stock_id
    actor = world.economy.stocks[owner].owner_ref
    readings = build_actor_dossier(world, actor)["own_production_readings"]

    assert readings
    assert all(item["event_id"].startswith("event:") for item in readings)
    assert all(item["observed_day"] == 30 for item in readings)
    assert all(set(item) == {
        "settlement_id", "occupation", "batches", "capacity", "limitations",
        "labor_shortfall", "observed_day", "event_id",
    } for item in readings)

    foreign = build_actor_dossier(world, OTHER)["own_production_readings"]
    expected_foreign_events = {
        facility.last_event_id
        for facility in world.economy.facilities.values()
        if facility.last_event_id
        and world.economy.stocks[facility.stock_id].owner_ref == OTHER
    }
    assert {item["event_id"] for item in foreign} == expected_foreign_events


def test_administrator_sees_dated_local_labor_without_foreign_payroll_or_balances():
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.economy import produce_monthly
    from src.sim.medieval.intelligence import refresh_reports
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    actor = EntityRef("polity", "auren")
    assert build_actor_dossier(world, actor)["own_local_livelihood_readings"] == ()

    world.clock = WorldClock(30)
    produce_monthly(world)
    refresh_reports(world)
    readings = build_actor_dossier(world, actor)["own_local_livelihood_readings"]
    local = next(item for item in readings if item["settlement_id"] == "pedraclara")
    assert local["observed_day"] == 30
    assert local["residents_by_occupation"]["artisan"] > 1000
    assert local["own_production_paid_workers_by_occupation"].get("artisan", 0) == 0
    assert local["source_event_ids"]
    assert "balance" not in str(local) and "household:" not in str(local)
    rural = next(item for item in readings if item["settlement_id"] == "campomanso")
    assert rural["own_production_paid_workers_by_occupation"]["farmer"] > 0
    assert len(rural["source_event_ids"]) > 1

    other = build_actor_dossier(world, OTHER)["own_local_livelihood_readings"]
    assert all(item["settlement_id"] != "pedraclara" for item in other)
    report = world.knowledge.settlement_report(actor, "pedraclara")
    world.knowledge.settlement_reports[report.id] = report.model_copy(
        update={"population": report.population + 1})
    assert all(item["settlement_id"] != "pedraclara" for item in
               build_actor_dossier(world, actor)["own_local_livelihood_readings"])
    world.clock = WorldClock(31)
    assert build_actor_dossier(world, actor)["own_local_livelihood_readings"] == ()


def test_workshop_choice_and_local_labor_share_one_provider_menu():
    from src.sim.medieval.economy import produce_monthly
    from src.sim.medieval.expansion import site_construction_adapters
    from src.sim.medieval.institutional_decision_turn import _by_id, _composed_situation
    from src.sim.medieval.intelligence import refresh_reports
    from src.systems.time import WorldClock
    from tests.test_medieval_site_construction import prepared

    world = prepared()
    actor = EntityRef("polity", "auren")
    world.clock = WorldClock(30)
    produce_monthly(world)
    refresh_reports(world)

    options = _by_id(world, actor, site_construction_adapters())
    assert any(option.settlement_id == "pedraclara" for _adapter, option in options.values())
    context = _composed_situation(world, actor, options)
    local = next(item for item in context["own_local_livelihood_readings"]
                 if item["settlement_id"] == "pedraclara")
    assert local["residents_by_occupation"]["artisan"] > 1000
    assert local["own_production_paid_workers_by_occupation"].get("artisan", 0) == 0


def test_dossier_projects_overflow_reading_only_for_a_sited_own_report():
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.route_intelligence import refresh_site_reports

    world = create_medieval_world(73)
    site_id = "docas-de-portovelho"
    owner = EntityRef("organization", "liga-das-barcas")
    refresh_site_reports(world, site_ids=(site_id,))

    dossier = build_actor_dossier(world, owner)
    report = next(item for item in dossier["known_site_overflow_reports"] if item["site_id"] == site_id)
    assert report["observed_day"] == world.clock.absolute_day
    assert 0 <= report["vulnerability"] <= 100
    assert all(region["open_occurrence"] is None for region in report["regions"])
    assert "stock" not in report and "account" not in report and "route" not in report

    # A foreign actor without its own current SiteReport for this site never
    # gets a reading for it, even though the site and its regions still exist.
    foreign = build_actor_dossier(world, OTHER)
    assert not any(item["site_id"] == site_id for item in foreign["known_site_overflow_reports"])


def test_dossier_omits_a_stale_overflow_report():
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.infrastructure import OBSERVATION_DAYS
    from src.sim.medieval.route_intelligence import refresh_site_reports

    world = create_medieval_world(73)
    site_id = "docas-de-portovelho"
    owner = EntityRef("organization", "liga-das-barcas")
    refresh_site_reports(world, site_ids=(site_id,))
    # Still present in Knowledge, but past the same 30-day freshness window
    # the maintenance vertical itself enforces via ``current_observation``.
    world.clock = world.clock.advance(OBSERVATION_DAYS)

    dossier = build_actor_dossier(world, owner)
    assert not any(item["site_id"] == site_id for item in dossier["known_site_overflow_reports"])


def test_dossier_omits_a_forged_overflow_report():
    from src.classes.governance.knowledge import site_report_id
    from src.run.medieval_world import create_medieval_world
    from src.sim.medieval.route_intelligence import refresh_site_reports

    world = create_medieval_world(73)
    site_id = "docas-de-portovelho"
    owner = EntityRef("organization", "liga-das-barcas")
    refresh_site_reports(world, site_ids=(site_id,))
    key = site_report_id(owner, site_id)
    genuine = world.knowledge.site_reports[key]
    # The registered integrity no longer matches its own typed receipt delta:
    # the same provenance check the maintenance vertical revalidates against
    # must reject this, not a second, duplicated check here.
    world.knowledge.site_reports[key] = genuine.model_copy(update={"integrity": 0.01})

    dossier = build_actor_dossier(world, owner)
    assert not any(item["site_id"] == site_id for item in dossier["known_site_overflow_reports"])


def test_dossier_rejects_a_non_entity_ref_actor():
    world = prepared_world()
    with pytest.raises(TypeError):
        build_actor_dossier(world, "auren")


def test_dossier_is_json_safe_for_the_provider_prompt():
    import json

    world = prepared_world()
    dossier = build_actor_dossier(world, REQUESTER)
    json.dumps(dossier, sort_keys=True, ensure_ascii=False)


def test_dossier_carries_known_memory_readings_and_derived_capacity():
    from tests.test_medieval_institutional_memory import breach_event_id
    from tests.test_medieval_institutional_aid import _breached_aid_world, PROVIDER

    world, obligation_id = _breached_aid_world()
    breach = breach_event_id(world, obligation_id)
    dossier = build_actor_dossier(world, REQUESTER)

    assert dossier["known_institutional_views"] == ({
        "subject_ref": PROVIDER.to_dict(), "reading": -4,
        "evidence_event_ids": [breach],
    },)
    assert set(dossier["strategic_capacity"]) == {
        "food_reserves", "productive_inputs", "territorial_defense",
        "administrative_bandwidth", "diplomatic_bandwidth", "military_command",
        "project_capacity", "logistics_capacity",
    }


def test_dossier_exposes_own_plan_lifecycle_without_foreign_handles():
    from src.classes.governance.models import StrategicPlan

    world = prepared_world()
    objective = next(item for item in world.strategy.objectives.values() if item.actor_ref == REQUESTER)
    world.strategy.plans[f"plan:{objective.id}"] = StrategicPlan(
        id=f"plan:{objective.id}", objective_id=objective.id, stage="blocked",
        blocker="sem_rota", last_review_day=world.clock.absolute_day, last_event_id="event:1")

    dossier = build_actor_dossier(world, REQUESTER)
    assert dossier["own_plans"] == ({
        "settlement_id": objective.settlement_id, "resource_id": objective.resource_id,
        "kind": objective.kind, "stage": "blocked", "blocker": "sem_rota",
        "last_review_day": world.clock.absolute_day,
    },)
    assert "objective_id" not in dossier["own_plans"][0]
    assert "order_ids" not in dossier["own_plans"][0]


def test_dossier_carries_only_strategic_findings_known_by_the_actor():
    from src.classes.governance.models import EspionageFinding

    world = prepared_world()
    agent = next(item for item in world.society.characters.values() if item.death_day is None)
    target = next(iter(world.society.settlements))
    known = EspionageFinding(
        id="espionage_finding:dossier-decision-known", mission_id="espionage:dossier-known",
        decision_event_id="dossier-decision-known", recipient_ref=REQUESTER,
        agent_ref=EntityRef("character", agent.id), target_ref=EntityRef("settlement", target),
        target_owner_ref=OTHER, result="failure", learned_day=world.clock.absolute_day,
        event_id="dossier-event-known")
    foreign = known.model_copy(update={
        "id": "espionage_finding:dossier-decision-foreign", "mission_id": "espionage:dossier-foreign",
        "decision_event_id": "dossier-decision-foreign", "recipient_ref": OTHER,
        "event_id": "dossier-event-foreign"})
    world.knowledge.espionage_findings[known.id] = known
    world.knowledge.espionage_findings[foreign.id] = foreign

    evidence = build_actor_dossier(world, REQUESTER)["known_strategic_evidence"]
    assert [item["finding_id"] for item in evidence] == [known.id]
    assert evidence[0]["recipient_ref"] == REQUESTER.to_dict()
