import copy

import pytest

from src.classes.event import FactKind
from src.classes.governance.models import AuthorityOffice
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.espionage import execute_espionage, espionage_options
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


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


def test_espionage_success_only_records_existing_evidence_and_survives_save(tmp_path):
    world, agent, option = prepared_world()
    before = copy.deepcopy(world.society.settlements)
    decision = decide(world, option)

    finding = execute_espionage(world, OWNER, option.id, decision.id)

    assert finding.result == "success"
    assert finding.evidence_event_id == option.evidence_event_id
    assert world.society.settlements == before
    assert world.events[-1].event_type == "espionage_resolved"
    assert not world.events[-1].decision
    world.knowledge.validate(world)
    path = tmp_path / "espionage.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_low_capability_is_a_factual_failure_without_evidence():
    world, _agent, option = prepared_world(skill=10)
    decision = decide(world, option)

    finding = execute_espionage(world, OWNER, option.id, decision.id)

    assert finding.result == "failure"
    assert finding.evidence_event_id is None
    assert not any(event.event_type == "story" for event in world.events)


def test_target_detection_is_a_distinct_outcome_without_evidence(monkeypatch):
    world, _agent, option = prepared_world()
    decision = decide(world, option)
    monkeypatch.setattr("src.sim.medieval.espionage._target_detects", lambda *_args: True)

    finding = execute_espionage(world, OWNER, option.id, decision.id)

    assert finding.result == "discovered"
    assert finding.evidence_event_id is None


def test_owner_revalidates_agent_before_materializing_finding():
    world, agent, option = prepared_world()
    decision = decide(world, option)
    world.society.characters[agent.id] = agent.model_copy(update={"death_day": 0, "population_group_id": None})

    with pytest.raises(ValueError, match="stale|unknown|agent"):
        execute_espionage(world, OWNER, option.id, decision.id)
    assert not world.knowledge.espionage_findings
