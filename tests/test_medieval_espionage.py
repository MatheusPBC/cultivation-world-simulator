import copy

import pytest

from src.classes.event import FactKind
from src.classes.governance.models import AuthorityOffice
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.espionage import execute_espionage, espionage_options
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import (
    refresh_existing_local_settlement_reports,
    refresh_settlement_reports,
)
from src.systems.time import WorldClock


OWNER = EntityRef("polity", "auren")
TARGET = "portovelho"


def prepared_world(skill=60):
    world = create_medieval_world(73)
    refresh_settlement_reports(world)
    agent = next(item for item in world.society.characters.values()
                 if item.death_day is None and item.location_id == TARGET)
    agent = agent.model_copy(update={"skills": agent.skills.model_copy(update={"investigation": skill})})
    world.society.characters[agent.id] = agent
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = AuthorityOffice(
        id=office.id, institution_ref=OWNER, holder_ref=EntityRef("character", agent.id),
        scopes=office.scopes, starts_day=office.starts_day, ends_day=office.ends_day)
    option = next(item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET)
    return world, agent, option


def decide(world, option):
    return record_event(world, "espionage_decided", "A instituição selecionou uma missão de espionagem.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def test_espionage_success_brings_home_its_own_local_observation_and_survives_save(tmp_path):
    world, agent, option = prepared_world()
    before = copy.deepcopy(world.society.settlements)
    assert world.knowledge.settlement_report(OWNER, TARGET) is None
    decision = decide(world, option)

    finding = execute_espionage(world, OWNER, option.id, decision.id)

    # What the mission brings home is the dated local observation its own
    # agent could make standing there, not a pointer to the target's bulletin.
    assert finding.result == "success"
    learned = world.knowledge.settlement_report(OWNER, TARGET)
    assert learned is not None
    assert learned.channel == "local_settlement_report"
    assert learned.recipient_ref == learned.publisher_ref == OWNER
    assert learned.observed_day == world.clock.absolute_day
    assert finding.evidence_event_id == learned.event_id
    assert finding.evidence_event_id != option.evidence_event_id

    # The observation is a receipt of its own, recorded before the resolution
    # and cited by it together with the canonical evidence the mission targeted.
    resolution = world.events[-1]
    assert resolution.event_type == "espionage_resolved"
    assert not resolution.decision
    causes = {link.cause_event_id for link in resolution.causal_links}
    assert {learned.event_id, option.evidence_event_id, decision.id} <= causes
    observation = next(event for event in world.events if event.id == learned.event_id)
    assert observation.event_type == "settlement_observed"
    assert decision.id in {link.cause_event_id for link in observation.causal_links}

    # Knowledge only: the target settlement itself is untouched.
    assert world.society.settlements == before
    world.knowledge.validate(world)
    path = tmp_path / "espionage.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_a_mission_that_learns_nothing_publishes_no_report(monkeypatch):
    for outcome, skill, detected in (("failure", 10, False), ("discovered", 60, True)):
        world, _agent, option = prepared_world(skill=skill)
        if detected:
            monkeypatch.setattr("src.sim.medieval.espionage._target_detects", lambda *_args: True)
        finding = execute_espionage(world, OWNER, option.id, decide(world, option).id)
        assert finding.result == outcome
        assert finding.evidence_event_id is None
        assert world.knowledge.settlement_report(OWNER, TARGET) is None
        world.knowledge.validate(world)


def test_a_past_mission_is_not_a_standing_watch_over_the_target():
    """The agent leaves; the local reading stops being renewed for its owner."""
    world, agent, option = prepared_world()
    execute_espionage(world, OWNER, option.id, decide(world, option).id)
    learned = world.knowledge.settlement_report(OWNER, TARGET)
    assert learned is not None

    world.clock = WorldClock(world.clock.absolute_day + 1)
    world.society.characters[agent.id] = world.society.characters[agent.id].model_copy(
        update={"location_id": "auren-alta"})
    refresh_existing_local_settlement_reports(world, TARGET)

    assert world.knowledge.settlement_report(OWNER, TARGET) == learned
    world.knowledge.validate(world)


def test_local_report_refresh_matches_after_save_load(tmp_path):
    world = create_medieval_world(73)
    refresh_settlement_reports(world)
    target = next(
        settlement_id
        for settlement_id in sorted(world.society.settlements)
        if sum(
            report.settlement_id == settlement_id
            and report.channel == "local_settlement_report"
            and report.recipient_ref == report.publisher_ref
            and report.recipient_ref.kind == "character"
            for report in world.knowledge.settlement_reports.values()
        ) >= 2
    )
    path = tmp_path / "local-reports.mws"
    save_world(world, path)
    resumed = load_world(path)
    next_day = WorldClock(world.clock.absolute_day + 1)
    world.clock = next_day
    resumed.clock = next_day

    refresh_existing_local_settlement_reports(world, target)
    refresh_existing_local_settlement_reports(resumed, target)

    assert world_snapshot(resumed) == world_snapshot(world)


def test_low_capability_is_a_factual_failure_without_evidence():
    world, _agent, option = prepared_world(skill=10)
    decision = decide(world, option)

    finding = execute_espionage(world, OWNER, option.id, decision.id)

    assert finding.result == "failure"
    assert finding.evidence_event_id is None
    assert not any(event.event_type == "story" for event in world.events)


def test_owner_revalidates_agent_before_materializing_finding():
    world, agent, option = prepared_world()
    decision = decide(world, option)
    world.society.characters[agent.id] = agent.model_copy(update={"death_day": 0, "population_group_id": None})

    with pytest.raises(ValueError, match="stale|unknown|agent"):
        execute_espionage(world, OWNER, option.id, decision.id)
    assert not world.knowledge.espionage_findings
