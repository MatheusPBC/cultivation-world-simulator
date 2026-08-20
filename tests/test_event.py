import pytest

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.event import Event, FactKind
from src.sim.simulator_engine.phases import social
from src.systems.time import Month, MonthStamp


class TestEventLogic:
    @pytest.fixture
    def avatar_a(self, dummy_avatar):
        dummy_avatar.id = "avatar_a"
        dummy_avatar.name = "角色A"
        return dummy_avatar

    @pytest.fixture
    def avatar_b(self, base_world):
        from src.classes.core.avatar.core import Avatar, Gender
        from src.classes.age import Age
        from src.systems.cultivation import Realm
        from src.classes.root import Root
        from src.classes.alignment import Alignment
        from src.systems.time import MonthStamp

        return Avatar(
            world=base_world,
            name="角色B",
            id="avatar_b",
            birth_month_stamp=MonthStamp(0),
            age=Age(20, Realm.Qi_Refinement),
            gender=Gender.FEMALE,
            pos_x=0,
            pos_y=0,
            root=Root.WATER,
            personas=[],
            alignment=Alignment.RIGHTEOUS,
        )

    def test_process_interaction_from_event_is_noop(self, avatar_a, avatar_b):
        event = Event(
            month_stamp=avatar_a.world.month_stamp,
            content="A与B发生了互动",
            related_avatars=[avatar_a.id, avatar_b.id],
        )

        avatar_a.process_interaction_from_event(event)
        avatar_b.process_interaction_from_event(event)

        assert avatar_a.relation_interaction_states[avatar_b.id]["count"] == 0
        assert avatar_b.relation_interaction_states[avatar_a.id]["count"] == 0

    def test_phase_handle_interactions_only_marks_processed_ids(self, base_world, avatar_a, avatar_b):
        base_world.avatar_manager.register_avatar(avatar_a)
        base_world.avatar_manager.register_avatar(avatar_b)

        processed_ids = set()
        event = Event(base_world.month_stamp, "事件1", related_avatars=[avatar_a.id, avatar_b.id])

        social.phase_handle_interactions(base_world.avatar_manager, [event], processed_ids)

        assert event.id in processed_ids
        assert avatar_a.relation_interaction_states[avatar_b.id]["count"] == 0

    @pytest.mark.asyncio
    async def test_phase_evolve_relations_now_only_normalizes_state(self, base_world, avatar_a, avatar_b):
        base_world.avatar_manager.register_avatar(avatar_a)
        base_world.avatar_manager.register_avatar(avatar_b)
        avatar_a.make_friend_with(avatar_b)

        events = await social.phase_evolve_relations(base_world.avatar_manager, [avatar_a, avatar_b])

        assert events == []
        assert avatar_a.get_friendliness(avatar_b) == 35
        assert avatar_b.get_friendliness(avatar_a) == 35

    def test_phase_update_calculated_relations_also_regresses_friendliness(self, base_world, avatar_a, avatar_b):
        from src.systems.time import Year, create_month_stamp

        base_world.month_stamp = create_month_stamp(Year(2), Month.JANUARY)
        avatar_a.make_friend_with(avatar_b)

        social.phase_update_calculated_relations(base_world, [avatar_a, avatar_b])

        assert avatar_a.get_friendliness(avatar_b) == 33
        assert avatar_b.get_friendliness(avatar_a) == 33


class TestEventCausalMetadata:
    """Task 2: Event gains fact_kind, causal_payload and a runtime causal_links mirror."""

    def test_fact_kind_defaults_to_occurrence(self):
        event = Event(month_stamp=MonthStamp(1), content="something happened")

        assert event.fact_kind == FactKind.OCCURRENCE

    def test_causal_payload_defaults_to_none(self):
        event = Event(month_stamp=MonthStamp(1), content="something happened")

        assert event.causal_payload is None

    def test_causal_links_defaults_to_empty_list(self):
        event = Event(month_stamp=MonthStamp(1), content="something happened")

        assert event.causal_links == []

    def test_to_dict_round_trips_fact_kind_and_causal_payload(self):
        event = Event(
            month_stamp=MonthStamp(1),
            content="a region's population fell",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_payload={"deltas": [{"aspect": "population"}], "decision": None},
        )

        data = event.to_dict()
        restored = Event.from_dict(data)

        assert data["fact_kind"] == "state_transition"
        assert restored.fact_kind == FactKind.STATE_TRANSITION
        assert restored.causal_payload == {"deltas": [{"aspect": "population"}], "decision": None}

    def test_from_dict_defaults_fact_kind_and_causal_payload_when_absent(self):
        event = Event(month_stamp=MonthStamp(1), content="legacy event")
        data = event.to_dict()
        del data["fact_kind"]
        del data["causal_payload"]

        restored = Event.from_dict(data)

        assert restored.fact_kind == FactKind.OCCURRENCE
        assert restored.causal_payload is None

    def test_to_dict_round_trips_causal_links(self):
        event = Event(month_stamp=MonthStamp(1), content="a breakthrough happened")
        event.causal_links = [
            CausalLink(
                event_id=event.id,
                cause_event_id="cause-1",
                relation=CausalRelation.MOTIVATED_BY,
                weight=0.5,
            )
        ]

        data = event.to_dict()
        restored = Event.from_dict(data)

        assert data["causal_links"][0]["relation"] == "motivated_by"
        assert len(restored.causal_links) == 1
        assert restored.causal_links[0].cause_event_id == "cause-1"
        assert restored.causal_links[0].relation == CausalRelation.MOTIVATED_BY
        assert restored.causal_links[0].weight == 0.5

    def test_from_dict_defaults_causal_links_when_absent(self):
        event = Event(month_stamp=MonthStamp(1), content="legacy event")
        data = event.to_dict()
        del data["causal_links"]

        restored = Event.from_dict(data)

        assert restored.causal_links == []
