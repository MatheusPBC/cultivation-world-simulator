"""
Unit tests for the passive `CausalRecorder` seam (Task 3).

See docs/specs/causal-world-kernel.md section 4.2 and
.superpowers/sdd/2026-08-20-causal-world-kernel/task-3-brief.md.
"""
from src.classes.causal_link import CausalLink, CausalRelation, MAX_CAUSAL_LINKS_PER_EVENT
from src.classes.event import Event, FactKind
from src.classes.state_delta import StateDelta
from src.sim.simulator_engine.causal_recorder import CausalRecorder, get_causal_recorder
from src.systems.time import Month, Year, create_month_stamp


def make_event(content: str = "test") -> Event:
    return Event(create_month_stamp(Year(1), Month.JANUARY), content)


class TestCausalRecorderNeutrality:
    def test_empty_recorder_leaves_events_untouched(self):
        recorder = CausalRecorder()
        events = [make_event("a"), make_event("b")]

        recorder.attach_to(events)

        for event in events:
            assert event.causal_links == []
            assert event.causal_payload is None

    def test_attach_to_only_touches_events_with_recorded_ids(self):
        recorder = CausalRecorder()
        recorded_event = make_event("recorded")
        untouched_event = make_event("untouched")
        cause_event = make_event("cause")

        recorder.record_link(
            recorded_event.id,
            CausalLink(cause_event_id=cause_event.id, relation=CausalRelation.TRIGGERED_BY),
        )

        recorder.attach_to([recorded_event, untouched_event])

        assert len(recorded_event.causal_links) == 1
        assert recorded_event.causal_links[0].cause_event_id == cause_event.id
        assert untouched_event.causal_links == []
        assert untouched_event.causal_payload is None


class TestCausalRecorderLinks:
    def test_record_link_sets_event_id_on_the_link(self):
        recorder = CausalRecorder()
        event = make_event()
        link = CausalLink(cause_event_id="cause-1", relation=CausalRelation.ENABLED_BY)

        recorder.record_link(event.id, link)
        recorder.attach_to([event])

        assert event.causal_links[0].event_id == event.id

    def test_caps_links_per_event_at_max_by_priority(self):
        recorder = CausalRecorder()
        event = make_event()

        for i in range(MAX_CAUSAL_LINKS_PER_EVENT + 5):
            recorder.record_link(
                event.id,
                CausalLink(cause_event_id=f"cause-{i}", relation=CausalRelation.CONTRIBUTED_TO),
                priority=i,
            )

        recorder.attach_to([event])

        assert len(event.causal_links) == MAX_CAUSAL_LINKS_PER_EVENT
        # highest-priority links survive, not just the first N inserted
        surviving_causes = {link.cause_event_id for link in event.causal_links}
        expected_causes = {f"cause-{i}" for i in range(5, MAX_CAUSAL_LINKS_PER_EVENT + 5)}
        assert surviving_causes == expected_causes

    def test_low_priority_link_is_dropped_in_favor_of_high_priority(self):
        recorder = CausalRecorder()
        event = make_event()

        for i in range(MAX_CAUSAL_LINKS_PER_EVENT):
            recorder.record_link(
                event.id,
                CausalLink(cause_event_id=f"filler-{i}", relation=CausalRelation.CONTRIBUTED_TO),
                priority=0,
            )
        recorder.record_link(
            event.id,
            CausalLink(cause_event_id="important-cause", relation=CausalRelation.TRIGGERED_BY),
            priority=100,
        )

        recorder.attach_to([event])

        causes = {link.cause_event_id for link in event.causal_links}
        assert "important-cause" in causes
        assert len(event.causal_links) == MAX_CAUSAL_LINKS_PER_EVENT


class TestCausalRecorderDeltas:
    def test_record_delta_sets_event_id_and_attaches_payload(self):
        recorder = CausalRecorder()
        event = make_event()
        delta = StateDelta(owner_kind="region", owner_id="1", aspect="population", before="80.0", after="81.0")

        recorder.record_delta(event.id, delta)
        recorder.attach_to([event])

        assert delta.event_id == event.id
        assert event.causal_payload["deltas"] == [delta.to_dict()]

    def test_multiple_deltas_on_one_event_all_survive(self):
        recorder = CausalRecorder()
        event = make_event()
        delta_a = StateDelta(owner_kind="avatar", owner_id="a1", aspect="realm", before="qi", after="foundation")
        delta_b = StateDelta(owner_kind="avatar", owner_id="a1", aspect="hp_max", before="100", after="150")

        recorder.record_delta(event.id, delta_a)
        recorder.record_delta(event.id, delta_b)
        recorder.attach_to([event])

        assert event.causal_payload["deltas"] == [delta_a.to_dict(), delta_b.to_dict()]

    def test_links_and_deltas_coexist_on_the_same_event(self):
        recorder = CausalRecorder()
        event = make_event()
        recorder.record_link(event.id, CausalLink(cause_event_id="cause-1"))
        recorder.record_delta(event.id, StateDelta(owner_kind="region", owner_id="1", aspect="population"))

        recorder.attach_to([event])

        assert len(event.causal_links) == 1
        assert event.causal_payload["deltas"]


class TestGetCausalRecorder:
    def test_returns_none_when_world_has_no_recorder_attached(self):
        class FakeWorld:
            pass

        assert get_causal_recorder(FakeWorld()) is None

    def test_returns_the_bridged_recorder(self):
        class FakeWorld:
            pass

        world = FakeWorld()
        recorder = CausalRecorder()
        world.step_causal_recorder = recorder

        assert get_causal_recorder(world) is recorder
