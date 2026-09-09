"""Annual sect administration is atomic across member owners and the event log."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalRelation
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.event import FactKind
from src.classes.root import Root
from src.classes.sect_decider import SectDecider
from src.classes.sect_ranks import SectRank, get_rank_from_realm
from src.classes.technique import (
    Technique,
    TechniqueAttribute,
    TechniqueGrade,
    techniques_by_name,
)
from src.sim.managers.event_manager import EventManager
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
from src.sim.simulator_engine.phase_registry import SimulationPhase, annual_maintenance
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.sect_decision_context import SectDecisionContext
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, *, avatar_id: str, name: str, alignment: Alignment) -> Avatar:
    return Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=alignment,
    )


def _member_context(*members: Avatar) -> SectDecisionContext:
    return SectDecisionContext(
        basic_structured={},
        basic_text="",
        power={},
        territory={},
        self_assessment={},
        economy={},
        relations=[],
        relations_summary="",
        history={},
        recruitment_candidates=[],
        member_candidates=[{"avatar_id": member.id} for member in members],
    )


def _select(action: str, avatar_id: str):
    async def llm_call(_task, _template, context, **_kwargs):
        option = next(item for item in context["affordances"] if item["action_kind"] == action and item["parameters"].get("avatar_id") == avatar_id)
        return {"decision": "act", "reason": "rollback probe", "selected_affordance_id": option["id"]}
    return llm_call


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ("expel", "reward"))
async def test_failed_annual_commit_restores_administration_action(
    base_world, monkeypatch, tmp_path, action
) -> None:
    base_world.month_stamp = create_month_stamp(Year(100), Month.JANUARY)
    base_world.start_year = 100
    base_world.run_config_snapshot = {}
    base_world.event_manager = EventManager.create_with_db(tmp_path / "administration.db")

    sect = Sect(
        id=92,
        name="Administration Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="Hall", desc="", image=Path()),
        technique_names=["Canonical Upper Gold Art"],
        rule_id="righteous_orthodoxy",
    )
    patriarch = _avatar(
        base_world,
        avatar_id="patriarch",
        name="Patriarch",
        alignment=Alignment.RIGHTEOUS,
    )
    breaker = _avatar(
        base_world, avatar_id="breaker", name="Breaker", alignment=Alignment.EVIL
    )
    patriarch.join_sect(sect, SectRank.Patriarch)
    breaker.join_sect(sect, get_rank_from_realm(breaker.cultivation_progress.realm))
    base_world.avatar_manager.register_avatar(patriarch)
    base_world.avatar_manager.register_avatar(breaker)
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    bootstrap_institutional_authority(base_world)

    reward = Technique(
        id=99201,
        name="Canonical Upper Gold Art",
        attribute=TechniqueAttribute.GOLD,
        grade=TechniqueGrade.UPPER,
        desc="",
        weight=1.0,
        condition="",
        sect_id=sect.id,
    )
    old = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    try:
        membership_before = dict(sect.members)
        patriarch_rank_before = patriarch.sect_rank
        breaker_rank_before = breaker.sect_rank
        patriarch_technique_before = patriarch.technique
        breaker_technique_before = breaker.technique
        event_count_before = base_world.event_manager.count()
        month_before = base_world.month_stamp
        random_before = random.getstate()
        attempted: list = []

        def fail_commit(events, _chapter):
            attempted.extend(events)
            if action == "expel":
                assert breaker.sect is None
            else:
                assert patriarch.technique is reward
            return False

        phases = (
            SimulationPhase("annual_maintenance", 1, "annual_maintenance", annual_maintenance),
            SimulationPhase(
                "finalize_step",
                2,
                "finalize_step",
                lambda _simulator, ctx: finalize_step(ctx),
                reset_check_after=False,
            ),
        )
        monkeypatch.setattr(base_world.event_manager, "commit_step", fail_commit)
        original_decide = SectDecider.decide.__func__

        selected_action = f"sect_annual_{action}"
        selected_id = breaker.id if action == "expel" else patriarch.id
        async def decide_selected(cls, chosen_sect, ctx, world, **_kwargs):
            return await original_decide(cls, chosen_sect, ctx, world, llm_call=_select(selected_action, selected_id))

        with (
                patch(
                    "src.classes.core.sect.get_sect_decision_context",
                    return_value=_member_context(patriarch, breaker),
                ),
                patch.object(SectDecider, "decide", classmethod(decide_selected)),
        ):
            with pytest.raises(EventPersistenceError):
                await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

        decision_ids = {
            event.id for event in attempted if event.fact_kind is FactKind.DECISION
        }
        mutation = next(
            event
            for event in attempted
            if any(
                delta["owner_kind"] == "avatar"
                and delta["owner_id"] == selected_id
                and delta["aspect"] == ("sect_membership" if action == "expel" else "technique")
                for delta in (event.causal_payload or {}).get("deltas", [])
            )
        )
        assert decision_ids
        assert any(link.relation is CausalRelation.MOTIVATED_BY and link.cause_event_id in decision_ids for link in mutation.causal_links)

        assert sect.members == membership_before
        assert patriarch.sect is sect
        assert patriarch.sect_rank is patriarch_rank_before
        assert breaker.sect is sect
        assert breaker.sect_rank is breaker_rank_before
        assert patriarch.technique is patriarch_technique_before
        assert breaker.technique is breaker_technique_before
        assert base_world.event_manager.count() == event_count_before
        assert base_world.month_stamp == month_before
        assert random.getstate() == random_before
    finally:
        if old is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = old
