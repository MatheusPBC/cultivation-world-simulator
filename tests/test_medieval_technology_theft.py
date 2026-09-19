"""Focused causal tests for institutional technology theft."""

import copy

import pytest

from src.classes.event import FactKind
from src.classes.governance.models import AuthorityOffice
from src.classes.mechanical_language import EntityRef
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.technology_theft import execute_technology_theft, technology_theft_options
from tests.test_medieval_technology_sale import researched_world


OWNER = EntityRef("polity", "auren")


def prepared_world(skill=60):
    world = researched_world()
    agent = world.society.characters["character:004"].model_copy(
        update={"skills": world.society.characters["character:004"].skills.model_copy(
            update={"investigation": skill})})
    world.society.characters[agent.id] = agent
    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = AuthorityOffice(
        id=office.id, institution_ref=OWNER, holder_ref=EntityRef("character", agent.id),
        scopes=office.scopes, starts_day=office.starts_day, ends_day=office.ends_day)
    refresh_site_reports(world, site_ids=["minas-de-ferroalto"])
    return world, agent


def decide(world, option):
    return record_event(world, "technology_theft_decided", "A instituição selecionou uma tentativa de obtenção técnica.",
                        fact_kind=FactKind.DECISION, decision=option.decision(),
                        cause_ids=(option.observation_event_id, option.source_knowledge_event_id))


def test_success_copies_only_sighted_canonical_technology_and_round_trips(tmp_path):
    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    before = copy.deepcopy(world.map.infrastructure_sites)
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)

    assert finding.result == "success"
    assert world.knowledge.knows(OWNER, "metallurgy")
    assert world.map.infrastructure_sites == before
    assert world.knowledge.technologies[f"technology:{OWNER.kind}:{OWNER.id}:metallurgy"].channel == "stolen"
    world.knowledge.validate(world)
    path = tmp_path / "technology-theft.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_low_skill_is_failure_and_discovery_does_not_grant_knowledge(monkeypatch):
    world, _agent = prepared_world(skill=10)
    option = technology_theft_options(world, OWNER)[0]
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "failure"
    assert not world.knowledge.knows(OWNER, "metallurgy")

    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    monkeypatch.setattr("src.sim.medieval.technology_theft._target_detects", lambda *_args: True)
    finding = execute_technology_theft(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "discovered"
    assert not world.knowledge.knows(OWNER, "metallurgy")


def test_stale_selection_cannot_mutate_knowledge():
    world, _agent = prepared_world()
    option = technology_theft_options(world, OWNER)[0]
    decision = decide(world, option)
    events_before = list(world.events)
    knowledge_before = dict(world.knowledge.technologies)
    world.knowledge.technology_sightings.clear()
    with pytest.raises(ValueError, match="absent or stale"):
        execute_technology_theft(world, OWNER, option.id, decision.id)
    assert world.events == events_before
    assert world.knowledge.technologies == knowledge_before
    assert not world.knowledge.knows(OWNER, "metallurgy")
