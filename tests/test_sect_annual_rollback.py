"""The annual sect treasury path remains atomic when finalization fails."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.causal_link import CausalRelation
from src.classes.event import FactKind
from src.classes.sect_decider import SectDecider, SectDecisionPlan
from src.classes.sect_ranks import SectRank
from src.sim.managers.event_manager import EventManager
from src.sim.simulator import Simulator
from src.sim.simulator_engine.finalizer import EventPersistenceError, finalize_step
from src.sim.simulator_engine.phase_registry import SimulationPhase, annual_maintenance
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.sect_decision_context import SectDecisionContext
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, *, avatar_id: str, name: str) -> Avatar:
    return Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )


def _decision_context(rogue: Avatar) -> SectDecisionContext:
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
        recruitment_candidates=[
            {
                "avatar_id": rogue.id,
                "alignment_recruitable": True,
                "race_recruitable": True,
            }
        ],
        member_candidates=[],
    )


@pytest.mark.asyncio
async def test_failed_annual_commit_restores_authorized_sect_recruitment(
    base_world, monkeypatch, tmp_path
) -> None:
    """The real annual phase spends, then its failed finalizer restores all owners."""
    base_world.month_stamp = create_month_stamp(Year(100), Month.JANUARY)
    base_world.start_year = 100
    base_world.run_config_snapshot = {"test_mode": True}
    base_world.event_manager = EventManager.create_with_db(tmp_path / "annual-events.db")

    sect = Sect(
        id=91,
        name="Treasury Sect",
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="Hall", desc="", image=Path()),
        technique_names=[],
        magic_stone=1000,
    )
    patriarch = _avatar(base_world, avatar_id="patriarch", name="Patriarch")
    rogue = _avatar(base_world, avatar_id="rogue", name="Rogue")
    patriarch.join_sect(sect, SectRank.Patriarch)
    base_world.avatar_manager.register_avatar(patriarch)
    base_world.avatar_manager.register_avatar(rogue)
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    bootstrap_institutional_authority(base_world)

    treasury_before = sect.magic_stone
    month_before = base_world.month_stamp
    event_count_before = base_world.event_manager.count()
    authority_before = base_world.institutional_authority.to_dict()
    knowledge_before = base_world.institutional_knowledge.to_dict()
    relations_before = base_world.institutional_relations.to_dict()
    random_before = random.getstate()
    attempted: list = []

    def fail_commit(events, _chapter):
        attempted.extend(events)
        assert rogue.sect is sect
        assert rogue.id in sect.members
        assert sect.magic_stone < treasury_before
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

    with (
        patch(
            "src.classes.core.sect.get_sect_decision_context",
            return_value=_decision_context(rogue),
        ),
        patch.object(
            SectDecider,
            "_plan",
            new=AsyncMock(
                return_value=SectDecisionPlan(recruit_avatar_ids=[rogue.id])
            ),
        ),
        patch(
            "src.classes.sect_decider.resolve_sect_recruitment",
            new=AsyncMock(
                return_value=type(
                    "RecruitmentOutcome",
                    (),
                    {"accepted": True, "result_text": "Rogue accepted."},
                )()
            ),
        ),
    ):
        with pytest.raises(EventPersistenceError):
            await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    decision_ids = {
        event.id
        for event in attempted
        if event.fact_kind is FactKind.DECISION and int(sect.id) in event.related_sects
    }
    assert decision_ids
    recruitment = next(
        event
        for event in attempted
        if event.fact_kind is FactKind.STATE_TRANSITION
        and rogue.id in event.related_avatars
        and int(sect.id) in event.related_sects
    )
    assert {
        (delta["owner_kind"], delta["owner_id"], delta["aspect"])
        for delta in recruitment.causal_payload["deltas"]
    } >= {
        ("sect", str(sect.id), "magic_stone"),
        ("avatar", rogue.id, "sect_membership"),
    }
    assert any(
        link.relation is CausalRelation.MOTIVATED_BY
        and link.cause_event_id in decision_ids
        for link in recruitment.causal_links
    )
    assert sect.magic_stone == treasury_before
    assert rogue.sect is None
    assert rogue.sect_rank is None
    assert rogue.id not in sect.members
    assert base_world.event_manager.count() == event_count_before
    assert base_world.month_stamp == month_before
    assert base_world.institutional_authority.to_dict() == authority_before
    assert base_world.institutional_knowledge.to_dict() == knowledge_before
    assert base_world.institutional_relations.to_dict() == relations_before
    assert random.getstate() == random_before
