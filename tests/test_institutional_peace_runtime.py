"""End-to-end transactional witnesses for bilateral institutional peace."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalRelation
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.environment.sect_region import SectRegion
from src.classes.event import Event, FactKind
from src.classes.root import Root
from src.classes.sect_ranks import SectRank
from src.sim.load.load_game import load_game
from src.sim.save.save_game import save_game
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    are_sects_at_war,
    negotiating_sect,
    sect_institution_id,
    set_formal_war,
)
from src.systems.institutional_memory import record_known_fact
from src.systems.cultivation import Realm
from src.systems.time import Month, Year, create_month_stamp


def _peace_world(world):
    """Two active, authorized sects with one persisted, known war fact."""
    hq = SectHeadQuarter(name="Peace HQ", desc="", image=Path(""))
    sects = []
    for sect_id, coordinate in ((1, (0, 0)), (2, (5, 5))):
        region = SectRegion(
            id=5000 + sect_id,
            name=f"Peace Sect {sect_id} HQ",
            desc="",
            sect_id=sect_id,
            sect_name=f"Peace Sect {sect_id}",
            cors=[coordinate],
        )
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = [coordinate]
        sect = Sect(
            id=sect_id,
            name=f"Peace Sect {sect_id}",
            desc="",
            member_act_style="",
            alignment=Alignment.NEUTRAL,
            headquarter=hq,
            technique_names=[],
        )
        patriarch = Avatar(
            world=world,
            name=f"Patriarch {sect_id}",
            id=f"peace-patriarch-{sect_id}",
            birth_month_stamp=create_month_stamp(Year(1), Month.JANUARY),
            age=Age(30, Realm.Qi_Refinement),
            gender=Gender.MALE,
            pos_x=coordinate[0],
            pos_y=coordinate[1],
            root=Root.GOLD,
            alignment=Alignment.NEUTRAL,
            personas=[],
        )
        patriarch.weapon = None
        patriarch.technique = None
        patriarch.join_sect(sect, SectRank.Patriarch)
        world.avatar_manager.register_avatar(patriarch)
        sects.append(sect)
    world.map.update_sect_regions()
    world.existed_sects = sects
    world.sect_context.from_existed_sects(sects)
    world.run_config_snapshot = {
        "test_mode": True,
        "provider": "test",
        "npc_awakening_rate_per_month": 0.0,
        "domain_affordance_action_urgency_threshold": 1.0,
    }
    bootstrap_institutional_authority(world)

    war = Event(
        world.month_stamp,
        "A recorded war began.",
        event_type=WAR_DECLARED_EVENT_TYPE,
        fact_kind=FactKind.STATE_TRANSITION,
        related_sects=[1, 2],
        causal_payload={"deltas": []},
    )
    relation = set_formal_war(
        world, 1, 2, current_month=int(world.month_stamp), evidence_event_ids=(war.id,)
    )
    war.causal_payload["deltas"] = [{
        "event_id": war.id,
        "owner_kind": "institutional_relation",
        "owner_id": relation.id,
        "aspect": "kind",
        "before": "none",
        "after": "at_war",
        "magnitude": None,
    }]
    record_known_fact(world, war, (sect_institution_id(1), sect_institution_id(2)))
    assert world.event_manager.commit_step([war])
    assert negotiating_sect(world, 1)
    assert negotiating_sect(world, 2)
    return war


def _advance_to_next_january(world) -> None:
    world.month_stamp = create_month_stamp(Year(world.month_stamp.get_year() + 1), Month.JANUARY)


def _control_peace_interpreter(monkeypatch, mode: dict[str, bool]):
    import src.systems.institutional_peace as peace

    original = peace.interpret_domain_affordances

    async def controlled(*args, **kwargs):
        selected = next(
            (
                option
                for option in kwargs["affordances"]
                if option.action_kind == "propose_institutional_peace"
                or (mode["accept"] and option.action_kind == "accept_institutional_peace")
            ),
            None,
        )
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "Controlled bilateral peace witness.", selected.id)
            if selected is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "No controlled peace action.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    monkeypatch.setattr(peace, "interpret_domain_affordances", controlled)


def _enable_annual_peace(monkeypatch) -> None:
    """Keep the integration witness independent of the production 3-year cadence."""
    monkeypatch.setattr(
        "src.sim.simulator_engine.phases.annual._should_run_sect_decision_cycle",
        lambda _world: True,
    )


@pytest.mark.asyncio
async def test_annual_peace_proposal_persists_then_next_cycle_accepts_independently(base_world, monkeypatch):
    _peace_world(base_world)
    _enable_annual_peace(monkeypatch)
    mode = {"accept": False}
    _control_peace_interpreter(monkeypatch, mode)
    simulator = Simulator(base_world)

    first_cycle = await simulator.step()
    proposal = next(event for event in first_cycle if event.event_type == "institutional_peace_proposed")
    assert are_sects_at_war(base_world, 1, 2)
    assert not any(event.event_type == "institutional_peace_accepted" for event in first_cycle)

    _advance_to_next_january(base_world)
    mode["accept"] = True
    second_cycle = await simulator.step()
    accepted = next(event for event in second_cycle if event.event_type == "institutional_peace_accepted")
    response = next(event for event in second_cycle if event.event_type == "institutional_peace_response_interpretation_decision")

    assert not are_sects_at_war(base_world, 1, 2)
    assert accepted.fact_kind is FactKind.STATE_TRANSITION
    assert accepted.causal_payload["proposal_event_id"] == proposal.id
    assert any(link.cause_event_id == proposal.id and link.relation is CausalRelation.RESPONSE_TO for link in accepted.causal_links)
    assert any(link.cause_event_id == response.id and link.relation is CausalRelation.MOTIVATED_BY for link in accepted.causal_links)


@pytest.mark.asyncio
async def test_saved_pending_peace_accepts_once_after_load(base_world, monkeypatch, tmp_path):
    _peace_world(base_world)
    _enable_annual_peace(monkeypatch)
    mode = {"accept": False}
    _control_peace_interpreter(monkeypatch, mode)
    first = await Simulator(base_world).step()
    proposal = next(event for event in first if event.event_type == "institutional_peace_proposed")
    save_path = tmp_path / "pending-peace.json"
    success, message = save_game(base_world, Simulator(base_world), base_world.existed_sects, save_path)
    assert success, message

    loaded, simulator, _sects = load_game(save_path)
    _advance_to_next_january(loaded)
    mode["accept"] = True
    accepted_cycle = await simulator.step()
    assert len([event for event in accepted_cycle if event.event_type == "institutional_peace_accepted"]) == 1
    assert not are_sects_at_war(loaded, 1, 2)
    assert loaded.event_manager.get_event_by_id(proposal.id) is not None

    _advance_to_next_january(loaded)
    replay = await simulator.step()
    assert not [event for event in replay if event.event_type == "institutional_peace_accepted"]


@pytest.mark.asyncio
async def test_failed_finalizer_after_peace_acceptance_restores_pending_world(base_world, monkeypatch):
    _peace_world(base_world)
    _enable_annual_peace(monkeypatch)
    mode = {"accept": False}
    _control_peace_interpreter(monkeypatch, mode)
    await Simulator(base_world).step()
    before_relations = base_world.institutional_relations.to_dict()
    before_knowledge = base_world.institutional_knowledge.to_dict()
    before_month = base_world.month_stamp
    before_events = base_world.event_manager.count()
    before_rng = random.getstate()

    _advance_to_next_january(base_world)
    before_month = base_world.month_stamp
    mode["accept"] = True
    attempted = []
    monkeypatch.setattr(base_world.event_manager, "commit_step", lambda events, _chapter: attempted.extend(events) or False)

    with pytest.raises(EventPersistenceError):
        await Simulator(base_world).step()

    assert any(event.event_type == "institutional_peace_accepted" for event in attempted)
    assert base_world.institutional_relations.to_dict() == before_relations
    assert base_world.institutional_knowledge.to_dict() == before_knowledge
    assert base_world.month_stamp == before_month
    assert base_world.event_manager.count() == before_events
    assert random.getstate() == before_rng
