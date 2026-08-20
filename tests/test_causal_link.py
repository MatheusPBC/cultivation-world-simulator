import pytest

from src.classes.causal_link import CausalLink, CausalRelation, MAX_CAUSAL_LINKS_PER_EVENT


class TestCausalRelation:
    def test_all_relations_from_spec_are_present(self):
        expected = {
            "triggered_by",
            "enabled_by",
            "motivated_by",
            "response_to",
            "resolves",
            "prevented_by",
            "contributed_to",
        }

        assert {relation.value for relation in CausalRelation} == expected


class TestCausalLink:
    def test_defaults(self):
        link = CausalLink()

        assert link.event_id == ""
        assert link.cause_event_id == ""
        assert link.relation == CausalRelation.TRIGGERED_BY
        assert link.weight == 1.0
        assert link.note_key is None
        assert link.note_params is None
        assert link.id

    def test_to_dict_and_from_dict_round_trip(self):
        link = CausalLink(
            event_id="effect-1",
            cause_event_id="cause-1",
            relation=CausalRelation.ENABLED_BY,
            weight=0.6,
            note_key="causal.some_key",
            note_params={"foo": "bar"},
        )

        data = link.to_dict()
        restored = CausalLink.from_dict(data)

        assert data["relation"] == "enabled_by"
        assert restored.event_id == "effect-1"
        assert restored.cause_event_id == "cause-1"
        assert restored.relation == CausalRelation.ENABLED_BY
        assert restored.weight == 0.6
        assert restored.note_key == "causal.some_key"
        assert restored.note_params == {"foo": "bar"}

    def test_max_causal_links_per_event_is_a_small_constant(self):
        assert MAX_CAUSAL_LINKS_PER_EVENT == 8
