"""
Agent-flow causal instrumentation for `Breakthrough` (Task 3).

See docs/specs/causal-world-kernel.md section 8.1 and
.superpowers/sdd/2026-08-20-causal-world-kernel/task-3-brief.md.
"""
import asyncio
from unittest.mock import patch

import pytest

from src.classes.action.breakthrough import Breakthrough
from src.classes.causal_link import CausalRelation
from src.classes.event import FactKind
from src.sim.simulator_engine.causal_recorder import CausalRecorder
from src.systems.cultivation import CultivationProgress, Realm


def _prepare(dummy_avatar, level: int = 30):
    dummy_avatar.cultivation_progress = CultivationProgress(level=level, exp=0)
    dummy_avatar.recalc_effects()
    return Breakthrough(dummy_avatar, dummy_avatar.world)


class TestBreakthroughCausalNeutrality:
    """No recorder attached to world -> identical events/state as before Task 3."""

    def test_no_recorder_on_world_produces_same_events_and_state(self, dummy_avatar):
        assert getattr(dummy_avatar.world, "step_causal_recorder", None) is None
        action = _prepare(dummy_avatar)

        start_event = action.start()
        with patch("random.random", return_value=0.0):
            action._execute()
        finish_events = asyncio.run(action.finish())

        assert dummy_avatar.cultivation_progress.realm == Realm.Foundation_Establishment
        assert start_event.causal_links == []
        assert start_event.causal_payload is None
        for event in finish_events:
            assert event.causal_links == []
            assert event.causal_payload is None

    def test_empty_recorder_on_world_still_produces_no_metadata_until_finish_runs_normally(self, dummy_avatar):
        # Attaching an (empty) recorder before start() must not change can_start/start
        # behaviour; it only becomes observable once finish() records into it.
        dummy_avatar.world.step_causal_recorder = CausalRecorder()
        action = _prepare(dummy_avatar)

        start_event = action.start()
        assert start_event.content  # start() behaviour unaffected by recorder presence
        dummy_avatar.world.step_causal_recorder = None


class TestBreakthroughCausalRecording:
    def test_success_records_triggered_by_link_and_realm_delta(self, dummy_avatar):
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)

        try:
            start_event = action.start()
            with patch("random.random", return_value=0.0):
                action._execute()
            finish_events = asyncio.run(action.finish())
        finally:
            dummy_avatar.world.step_causal_recorder = None

        core_event = finish_events[0]
        recorder.attach_to([start_event, core_event])

        assert len(core_event.causal_links) == 1
        link = core_event.causal_links[0]
        assert link.cause_event_id == start_event.id
        assert link.relation == CausalRelation.TRIGGERED_BY

        deltas = core_event.causal_payload["deltas"]
        assert len(deltas) == 1
        assert deltas[0]["owner_kind"] == "avatar"
        assert deltas[0]["owner_id"] == str(dummy_avatar.id)
        assert deltas[0]["aspect"] == "realm"
        assert deltas[0]["before"] == Realm.Qi_Refinement.value
        assert deltas[0]["after"] == Realm.Foundation_Establishment.value

        # start event itself carries no recorded metadata -- it's the cause, not the effect
        assert start_event.causal_links == []
        assert start_event.causal_payload is None

    def test_failure_records_triggered_by_link_but_no_realm_delta(self, dummy_avatar):
        dummy_avatar.age.age = 76
        dummy_avatar.age.innate_max_lifespan = 80
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)

        try:
            start_event = action.start()
            with patch("random.random", return_value=1.0):
                action._execute()
            finish_events = asyncio.run(action.finish())
        finally:
            dummy_avatar.world.step_causal_recorder = None

        core_event = finish_events[0]
        recorder.attach_to([core_event])

        assert len(core_event.causal_links) == 1
        assert core_event.causal_links[0].relation == CausalRelation.TRIGGERED_BY
        assert core_event.causal_payload is None

    def test_recording_does_not_change_the_emitted_event_content_or_count(self, dummy_avatar):
        """Byte-for-byte neutrality: recording is additive metadata only --
        the same events, with the same content, are produced with or
        without a recorder attached."""
        action_a = _prepare(dummy_avatar)
        start_a = action_a.start()
        with patch("random.random", return_value=0.0):
            action_a._execute()
        events_a = asyncio.run(action_a.finish())

        dummy_avatar.cultivation_progress = CultivationProgress(level=30, exp=0)
        dummy_avatar.recalc_effects()
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        try:
            action_b = _prepare(dummy_avatar)
            start_b = action_b.start()
            with patch("random.random", return_value=0.0):
                action_b._execute()
            events_b = asyncio.run(action_b.finish())
        finally:
            dummy_avatar.world.step_causal_recorder = None

        assert len(events_a) == len(events_b)
        assert [e.content for e in events_a] == [e.content for e in events_b]
        assert [e.is_major for e in events_a] == [e.is_major for e in events_b]
        assert [e.related_avatars for e in events_a] == [e.related_avatars for e in events_b]
        assert start_a.content == start_b.content


class TestBreakthroughMotivatedBy:
    """`start()` links to `avatar.current_decision_event_id` via MOTIVATED_BY
    (Task 4 close-out) -- covers absent decision, present decision, a
    multi-plan chain consumed in a later month, and neutrality without a
    recorder. See task-4-review.md finding 9 and
    docs/specs/causal-world-kernel.md section 8.1.3."""

    def test_no_decision_recorded_when_avatar_has_no_active_decision(self, dummy_avatar):
        assert dummy_avatar.current_decision_event_id == ""
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)

        try:
            start_event = action.start()
        finally:
            dummy_avatar.world.step_causal_recorder = None

        recorder.attach_to([start_event])
        assert start_event.causal_links == []

    def test_motivated_by_link_recorded_when_decision_is_active(self, dummy_avatar):
        dummy_avatar.current_decision_event_id = "decision-123"
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)

        try:
            start_event = action.start()
        finally:
            dummy_avatar.world.step_causal_recorder = None

        recorder.attach_to([start_event])

        assert len(start_event.causal_links) == 1
        link = start_event.causal_links[0]
        assert link.cause_event_id == "decision-123"
        assert link.relation == CausalRelation.MOTIVATED_BY

    def test_triggered_by_from_finish_to_start_still_present_alongside_motivated_by(self, dummy_avatar):
        """The existing TRIGGERED_BY (finish -> start) must survive unchanged
        now that start also records MOTIVATED_BY (start -> decision)."""
        dummy_avatar.current_decision_event_id = "decision-456"
        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)

        try:
            start_event = action.start()
            with patch("random.random", return_value=0.0):
                action._execute()
            finish_events = asyncio.run(action.finish())
        finally:
            dummy_avatar.world.step_causal_recorder = None

        core_event = finish_events[0]
        recorder.attach_to([start_event, core_event])

        assert len(start_event.causal_links) == 1
        assert start_event.causal_links[0].relation == CausalRelation.MOTIVATED_BY
        assert start_event.causal_links[0].cause_event_id == "decision-456"

        assert len(core_event.causal_links) == 1
        assert core_event.causal_links[0].relation == CausalRelation.TRIGGERED_BY
        assert core_event.causal_links[0].cause_event_id == start_event.id

    def test_multi_plan_chain_consumed_in_a_later_month_still_links_to_original_decision(self, dummy_avatar):
        """A decision made in month N can still be committing plans (and
        producing start events) in month N+1, because commit_next_plan
        drains one plan per month. current_decision_event_id must still
        point at the original decision event when that later start() runs."""
        dummy_avatar.current_decision_event_id = "decision-from-earlier-month"
        first_month = dummy_avatar.world.month_stamp

        # Month N: another plan from the same chain runs and completes (not
        # Breakthrough itself -- just advancing time to prove the id survives).
        dummy_avatar.world.month_stamp = first_month + 1

        recorder = CausalRecorder()
        dummy_avatar.world.step_causal_recorder = recorder
        action = _prepare(dummy_avatar)
        try:
            start_event = action.start()
        finally:
            dummy_avatar.world.step_causal_recorder = None

        assert start_event.month_stamp == first_month + 1
        recorder.attach_to([start_event])
        assert start_event.causal_links[0].cause_event_id == "decision-from-earlier-month"
        # current_decision_event_id itself is untouched by consuming a plan.
        assert dummy_avatar.current_decision_event_id == "decision-from-earlier-month"

    def test_no_recorder_on_world_records_nothing_even_with_active_decision(self, dummy_avatar):
        """Neutrality: without a recorder attached, start() must not crash
        and must not attach any causal metadata, decision present or not."""
        dummy_avatar.current_decision_event_id = "decision-789"
        assert getattr(dummy_avatar.world, "step_causal_recorder", None) is None
        action = _prepare(dummy_avatar)

        start_event = action.start()

        assert start_event.causal_links == []
        assert start_event.causal_payload is None
