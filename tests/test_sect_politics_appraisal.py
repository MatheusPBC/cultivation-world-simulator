"""Task 3: sect politics driven by personal appraisals, plus the causal audit trail.

See docs/specs/personal-appraisal-politics.md ("Sect decision context" and
"Causal audit").

Core invariant under test: the sect remains the decision owner. A patriarch's
personal appraisals are optional *evidence* -- they never numerically alter a
sect relation value and never force war or peace.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_origin import CausalOrigin
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.core.world import World
from src.classes.emotions import EmotionType
from src.classes.event import Event, FactKind
from src.classes.event_appraisal import AppraisalSource, EventAppraisal
from src.classes.event_storage import EventStorage
from src.classes.root import Root
from src.classes.sect_decider import SectDecider
from src.systems.sect_decision_context import (
    MIN_APPRAISAL_EFFECTIVE_WEIGHT,
    MAX_APPRAISALS_PER_TARGET,
)
from src.classes.sect_ranks import SectRank
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_diplomacy import (
    are_sects_at_war,
    set_formal_war,
)
from src.systems.sect_decision_context import SectDecisionContext, build_sect_decision_context
from src.systems.time import Month, MonthStamp, Year, create_month_stamp


# --- helpers ---

def _make_avatar(world, *, avatar_id: str, name: str) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.NEUTRAL,
    )
    avatar.personas = []
    avatar.weapon = None
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _make_world_with_two_sects(base_world: World) -> tuple[World, Sect, Sect]:
    from src.classes.environment.sect_region import SectRegion

    world = base_world
    hq = SectHeadQuarter(name="HQ", desc="", image=Path(""))
    for sect_id, cors in ((1, [(0, 0)]), (2, [(5, 5)])):
        region = SectRegion(
            id=1000 + sect_id, name=f"R{sect_id}", desc="",
            sect_id=sect_id, sect_name=f"Sect{sect_id}", cors=cors,
        )
        world.map.regions[region.id] = region
        world.map.region_cors[region.id] = cors
    world.map.update_sect_regions()

    sect_a = Sect(id=1, name="Sect1", desc="", member_act_style="",
                  alignment=Alignment.NEUTRAL, headquarter=hq, technique_names=[], magic_stone=1000)
    sect_b = Sect(id=2, name="Sect2", desc="", member_act_style="",
                  alignment=Alignment.NEUTRAL, headquarter=hq, technique_names=[], magic_stone=1000)
    world.existed_sects = [sect_a, sect_b]
    world.sect_context.from_existed_sects(world.existed_sects)
    bootstrap_institutional_authority(world)
    return world, sect_a, sect_b


def _storage() -> EventStorage:
    tmpdir = tempfile.TemporaryDirectory()
    storage = EventStorage(Path(tmpdir.name) / "events.db")
    storage._tmpdir = tmpdir  # type: ignore[attr-defined]
    return storage


def _close(storage: EventStorage) -> None:
    tmpdir = getattr(storage, "_tmpdir", None)
    storage.close()
    if tmpdir is not None:
        tmpdir.cleanup()


def _write_appraisal(
    storage: EventStorage,
    world: World,
    *,
    appraiser: Avatar,
    focus: Avatar,
    valence: float = -0.8,
    personal_importance: float = 0.9,
    persistence: float = 0.9,
    month_stamp: int | None = None,
    summary: str = "He betrayed me.",
) -> tuple[Event, EventAppraisal]:
    stamp = MonthStamp(int(world.month_stamp) if month_stamp is None else month_stamp)
    event = Event(
        stamp,
        f"{focus.name} fought {appraiser.name}",
        related_avatars=[appraiser.id, focus.id],
        is_major=True,
        event_type="battle_result",
    )
    storage.add_event(event)
    appraisal = EventAppraisal(
        event_id=event.id,
        appraiser_avatar_id=str(appraiser.id),
        focus_avatar_id=str(focus.id),
        personal_importance=personal_importance,
        valence=valence,
        persistence=persistence,
        primary_emotion=EmotionType.ANGRY,
        summary=summary,
        source=AppraisalSource.LLM,
    )
    assert storage.add_event_appraisal(appraisal) is True
    return event, appraisal


def _target_for(ctx: SectDecisionContext, other_sect_id: int) -> dict:
    return next(t for t in ctx.diplomacy_targets if int(t["other_sect_id"]) == other_sect_id)


def _minimal_ctx(diplomacy_targets: list[dict]) -> SectDecisionContext:
    return SectDecisionContext(
        basic_structured={"name": "Sect1"}, basic_text="",
        power={}, territory={}, self_assessment={}, economy={},
        relations=[], relations_summary="",
        history={"recent_events": [], "summary_text": ""},
        diplomacy_targets=diplomacy_targets, active_wars=[],
        rule={}, recruitment_candidates=[], member_candidates=[],
    )


def _target(other_sect_id: int = 2, *, status: str = "peace", appraisals: list[dict] | None = None) -> dict:
    return {
        "other_sect_id": other_sect_id,
        "other_sect_name": f"Sect{other_sect_id}",
        "status": status,
        "war_months": 0,
        "peace_months": 12,
        "relation_value": -40,
        "local_patriarch_id": "patriarch-a",
        "other_patriarch_id": "patriarch-b",
        "personal_appraisals": appraisals if appraisals is not None else [],
    }


def _appraisal_entry(appraisal_id: str = "ap-1", source_event_id: str = "ev-1") -> dict:
    return {
        "appraisal_id": appraisal_id,
        "source_event_id": source_event_id,
        "source_event_month_stamp": 12,
        "source_event_date": "1年1月",
        "primary_emotion": EmotionType.ANGRY.value,
        "summary": "He betrayed me.",
        "valence": -0.8,
        "effective_weight": 0.9,
    }


async def _decide(sect, ctx, world, payload):
    """Run one decision round with a fixed LLM payload."""
    with patch.object(SectDecider, "_llm_available", return_value=True), patch(
        "src.classes.sect_decider.call_llm_with_task_name", new=AsyncMock(return_value=payload)
    ):
        return await SectDecider.decide(sect, ctx, world)


# --- 1. Context ---

class TestPatriarchAppraisalContext:

    def test_only_current_patriarch_appraisals_enter_matching_target_context(self, base_world):
        world, sect_a, sect_b = _make_world_with_two_sects(base_world)
        pa = _make_avatar(world, avatar_id="pa", name="PatriarchA")
        pb = _make_avatar(world, avatar_id="pb", name="PatriarchB")
        other = _make_avatar(world, avatar_id="other", name="Bystander")
        pa.join_sect(sect_a, SectRank.Patriarch)
        pb.join_sect(sect_b, SectRank.Patriarch)
        other.join_sect(sect_a, SectRank.OuterDisciple)

        storage = _storage()
        try:
            _, wanted = _write_appraisal(storage, world, appraiser=pa, focus=pb, summary="About the rival patriarch.")
            # Same appraiser, wrong focus -> must not appear for this target.
            _write_appraisal(storage, world, appraiser=pa, focus=other, summary="About a bystander.")
            # Wrong appraiser (not the patriarch) -> must not appear.
            _write_appraisal(storage, world, appraiser=other, focus=pb, summary="A disciple's view.")

            ctx = build_sect_decision_context(sect_a, world, storage, history_limit=0)
        finally:
            _close(storage)

        target = _target_for(ctx, 2)
        assert [a["appraisal_id"] for a in target["personal_appraisals"]] == [wanted.id]
        entry = target["personal_appraisals"][0]
        assert entry["summary"] == "About the rival patriarch."
        assert entry["valence"] == pytest.approx(-0.8)
        assert entry["primary_emotion"] == EmotionType.ANGRY.value
        assert entry["effective_weight"] > 0
        assert entry["source_event_id"]
        assert entry["source_event_date"]

    def test_absent_or_dead_patriarch_yields_no_personal_context(self, base_world):
        world, sect_a, sect_b = _make_world_with_two_sects(base_world)
        pa = _make_avatar(world, avatar_id="pa", name="PatriarchA")
        pb = _make_avatar(world, avatar_id="pb", name="PatriarchB")
        pa.join_sect(sect_a, SectRank.Patriarch)
        pb.join_sect(sect_b, SectRank.Patriarch)

        storage = _storage()
        try:
            _write_appraisal(storage, world, appraiser=pa, focus=pb)
            pb.is_dead = True  # target sect loses its patriarch

            ctx = build_sect_decision_context(sect_a, world, storage, history_limit=0)
        finally:
            _close(storage)

        target = _target_for(ctx, 2)
        assert target["personal_appraisals"] == []
        assert target["other_patriarch_id"] is None

    def test_weight_threshold_and_top_five_cap_are_applied(self, base_world):
        world, sect_a, sect_b = _make_world_with_two_sects(base_world)
        pa = _make_avatar(world, avatar_id="pa", name="PatriarchA")
        pb = _make_avatar(world, avatar_id="pb", name="PatriarchB")
        pa.join_sect(sect_a, SectRank.Patriarch)
        pb.join_sect(sect_b, SectRank.Patriarch)

        storage = _storage()
        try:
            for index in range(7):
                _write_appraisal(
                    storage, world, appraiser=pa, focus=pb,
                    personal_importance=0.9, persistence=1.0, summary=f"Strong memory {index}.",
                )
            # Far below the 0.15 gate: tiny importance, fully decayable, very old.
            _, faint = _write_appraisal(
                storage, world, appraiser=pa, focus=pb,
                personal_importance=0.05, persistence=0.0, month_stamp=0, summary="Faint memory.",
            )

            ctx = build_sect_decision_context(sect_a, world, storage, history_limit=0)
        finally:
            _close(storage)

        entries = _target_for(ctx, 2)["personal_appraisals"]
        assert len(entries) == MAX_APPRAISALS_PER_TARGET == 5
        assert faint.id not in {e["appraisal_id"] for e in entries}
        assert all(e["effective_weight"] >= MIN_APPRAISAL_EFFECTIVE_WEIGHT for e in entries)

    def test_appraisals_do_not_alter_sect_relation_value(self, base_world):
        """The core invariant: evidence is context, never a numeric modifier."""
        world, sect_a, sect_b = _make_world_with_two_sects(base_world)
        pa = _make_avatar(world, avatar_id="pa", name="PatriarchA")
        pb = _make_avatar(world, avatar_id="pb", name="PatriarchB")
        pa.join_sect(sect_a, SectRank.Patriarch)
        pb.join_sect(sect_b, SectRank.Patriarch)

        storage = _storage()
        try:
            baseline = build_sect_decision_context(sect_a, world, storage, history_limit=0)
            baseline_value = _target_for(baseline, 2)["relation_value"]

            for index in range(5):
                _write_appraisal(storage, world, appraiser=pa, focus=pb, valence=-1.0, summary=f"Hatred {index}.")

            after = build_sect_decision_context(sect_a, world, storage, history_limit=0)
        finally:
            _close(storage)

        assert _target_for(after, 2)["personal_appraisals"], "context must carry the evidence"
        assert _target_for(after, 2)["relation_value"] == baseline_value


# --- 2. Decision contract ---

class TestSectDecisionAudit:

    @pytest.mark.asyncio
    async def test_every_round_emits_one_sect_decision_event(self, base_world):
        _, sect_a, _ = _make_world_with_two_sects(base_world)
        ctx = _minimal_ctx([_target(2)])
        payload = {"thinking": "Hold.", "diplomacy_actions": []}

        result = await _decide(sect_a, ctx, base_world, payload)

        decision_events = [e for e in result.events if e.fact_kind is FactKind.DECISION]
        assert len(decision_events) == 1
        decision = decision_events[0].causal_payload["decision"]
        assert decision["subject_kind"] == "sect"
        assert decision["subject_id"] == "1"
        assert decision["source"] == "llm"
        assert decision_events[0].causal_origin is CausalOrigin.LLM_INTERPRETATION

    @pytest.mark.asyncio
    async def test_rule_fallback_round_is_still_audited_and_never_raises(self, base_world):
        _, sect_a, _ = _make_world_with_two_sects(base_world)
        ctx = _minimal_ctx([_target(2)])

        with patch.object(SectDecider, "_llm_available", return_value=True), patch(
            "src.classes.sect_decider.call_llm_with_task_name",
            new=AsyncMock(side_effect=RuntimeError("provider down")),
        ):
            result = await SectDecider.decide(sect_a, ctx, base_world)

        decision_events = [e for e in result.events if e.fact_kind is FactKind.DECISION]
        assert len(decision_events) == 1
        assert decision_events[0].causal_payload["decision"]["source"] == "rule"
        assert decision_events[0].causal_origin is CausalOrigin.ACTOR_DECISION

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_summary_event_is_causally_linked_to_the_decision_event(self, base_world):
        from src.sim.simulator_engine.phases.annual import phase_sect_periodic_decision

        world, sect_a, sect_b = _make_world_with_two_sects(base_world)
        world.month_stamp = create_month_stamp(Year(1), Month.JANUARY)
        world.start_year = 1
        storage = _storage()
        simulator = MagicMock()
        simulator.world = world
        try:
            world.event_manager = MagicMock()
            world.event_manager._storage = storage
            with patch.object(SectDecider, "_llm_available", return_value=False):
                events = await phase_sect_periodic_decision(simulator)
        finally:
            _close(storage)

        decision_ids = {e.id for e in events if e.fact_kind is FactKind.DECISION}
        assert decision_ids
        summaries = [
            e for e in events
            if e.fact_kind is not FactKind.DECISION
            and any(link.cause_event_id in decision_ids for link in e.causal_links)
        ]
        assert summaries, "each sect's summary event must link back to its decision event"





# --- 4. The periodic sect decision can never touch a war ---


class TestSectDeciderNeverTouchesWar:
    """War is owned elsewhere: no periodic sect plan can start or end one."""

    @pytest.mark.asyncio
    async def test_sect_decider_output_can_never_end_a_war(self, base_world):
        """Peace is a bilateral negotiation; no periodic plan can reach it."""
        _, sect_a, _ = _make_world_with_two_sects(base_world)
        set_formal_war(
            base_world, 1, 2, current_month=int(base_world.month_stamp),
            evidence_event_ids=("event:existing-war",),
        )
        ctx = _minimal_ctx([_target(2, status="war")])
        payload = {
            "thinking": "Peace.",
            "diplomacy_actions": [
                {"action": "seek_peace", "other_sect_id": 2, "appraisal_ids": []}
            ],
        }

        result = await _decide(sect_a, ctx, base_world, payload)

        assert are_sects_at_war(base_world, 1, 2)
        assert [e for e in result.events if e.fact_kind is FactKind.STATE_TRANSITION] == []
        assert not hasattr(result, "peace_made_count")
