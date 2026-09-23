"""Being caught costs the agent that place for a while.

Detection only ever denied one piece of evidence: ``_already_resolved`` blocked
a repeat on the same day and nothing more, so the same agent could try again
tomorrow, and the day after, forever. A defending institution paid its garrison
daily and bought no deterrence at all.

The mark is read from the finding the mission already persisted -- no timer, no
agenda, no record of its own -- and is scoped to the pair: another agent of the
same institution, and the same agent elsewhere, stay free.
"""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval.espionage import (DISCOVERY_MARK_DAYS, agent_is_marked, espionage_options,
                                        execute_espionage)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.technology_theft import execute_technology_theft, technology_theft_options
from src.systems.time import WorldClock

from tests.test_medieval_espionage import OWNER, TARGET, decide, prepared_world
from tests.test_medieval_technology_theft import decide as theft_decide, prepared_world as theft_world


def discovered_espionage(world, option, monkeypatch):
    monkeypatch.setattr("src.sim.medieval.espionage._target_detects", lambda *_args: True)
    finding = execute_espionage(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "discovered"
    return finding


def test_a_caught_agent_loses_that_target_for_the_window(monkeypatch):
    world, agent, option = prepared_world()
    assert espionage_options(world, OWNER)

    discovered_espionage(world, option, monkeypatch)
    agent_ref = EntityRef("character", agent.id)

    # Tomorrow is no longer enough: the mark outlives the day.
    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert agent_is_marked(world, agent_ref, EntityRef("settlement", TARGET),
                           world.knowledge.espionage_findings.values(), lambda item: item.target_ref)
    assert not [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]


def test_an_ordinary_failure_still_only_spends_the_day():
    """Regression: failure and success keep the historical one-day window."""
    world, agent, option = prepared_world(skill=10)
    finding = execute_espionage(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "failure"
    assert not [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]

    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET], (
        "um fracasso comum não marca o agente")

    # A successful mission spends the day in exactly the same way.
    world, agent, option = prepared_world()
    finding = execute_espionage(world, OWNER, option.id, decide(world, option).id)
    assert finding.result == "success"
    assert not [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]
    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert not agent_is_marked(world, EntityRef("character", agent.id), EntityRef("settlement", TARGET),
                               world.knowledge.espionage_findings.values(), lambda item: item.target_ref)
    assert [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]


def test_the_mark_expires_and_the_agent_returns(monkeypatch):
    world, agent, option = prepared_world()
    discovered_espionage(world, option, monkeypatch)
    agent_ref = EntityRef("character", agent.id)
    findings = world.knowledge.espionage_findings.values()
    place = EntityRef("settlement", TARGET)

    world.clock = WorldClock(world.clock.absolute_day + DISCOVERY_MARK_DAYS - 1)
    assert agent_is_marked(world, agent_ref, place, findings, lambda item: item.target_ref)

    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert not agent_is_marked(world, agent_ref, place, findings, lambda item: item.target_ref)
    assert [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]


def test_the_mark_is_scoped_to_the_pair(monkeypatch):
    world, agent, option = prepared_world()
    discovered_espionage(world, option, monkeypatch)
    world.clock = WorldClock(world.clock.absolute_day + 1)
    findings = world.knowledge.espionage_findings.values()

    # Another agent of the same institution, same target: untouched.
    other = next(item for item in world.society.characters.values()
                 if item.id != agent.id and item.death_day is None)
    assert not agent_is_marked(world, EntityRef("character", other.id), EntityRef("settlement", TARGET),
                               findings, lambda item: item.target_ref)

    # The same agent at a different place: untouched.
    assert not agent_is_marked(world, EntityRef("character", agent.id),
                               EntityRef("settlement", "campomanso"),
                               findings, lambda item: item.target_ref)


def test_without_a_garrison_nothing_changes():
    """No detachment of the target means no detection, so no mark ever forms."""
    world, agent, option = prepared_world()
    assert not [item for item in world.society.detachments.values()
                if item.location_id == TARGET and item.stage == "present"]

    finding = execute_espionage(world, OWNER, option.id, decide(world, option).id)
    assert finding.result != "discovered"
    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert [item for item in espionage_options(world, OWNER) if item.target_ref.id == TARGET]


def test_technology_theft_reuses_the_same_reading(monkeypatch):
    world, agent = theft_world()
    agent_ref = EntityRef("character", agent.id)
    option = technology_theft_options(world, OWNER)[0]
    site_id = option.site_id

    monkeypatch.setattr("src.sim.medieval.technology_theft._target_detects", lambda *_args: True)
    finding = execute_technology_theft(world, OWNER, option.id, theft_decide(world, option).id)
    assert finding.result == "discovered"

    findings = world.knowledge.technology_theft_findings.values()
    world.clock = WorldClock(world.clock.absolute_day + 1)
    assert agent_is_marked(world, agent_ref, site_id, findings, lambda item: item.site_id)
    assert not [item for item in technology_theft_options(world, OWNER) if item.site_id == site_id]

    world.clock = WorldClock(world.clock.absolute_day + DISCOVERY_MARK_DAYS)
    assert not agent_is_marked(world, agent_ref, site_id, findings, lambda item: item.site_id)


def test_the_mark_persists_without_any_new_state(tmp_path, monkeypatch):
    world, agent, option = prepared_world()
    discovered_espionage(world, option, monkeypatch)
    world.knowledge.validate(world)

    path = tmp_path / "discovery-mark.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)

    resumed.clock = WorldClock(resumed.clock.absolute_day + 1)
    assert agent_is_marked(resumed, EntityRef("character", agent.id), EntityRef("settlement", TARGET),
                           resumed.knowledge.espionage_findings.values(), lambda item: item.target_ref)
    assert not [item for item in espionage_options(resumed, OWNER) if item.target_ref.id == TARGET]
    resumed.knowledge.validate(resumed)
