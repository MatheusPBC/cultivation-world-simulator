from src.classes.state_delta import StateDelta


class TestStateDelta:
    def test_defaults(self):
        delta = StateDelta()

        assert delta.event_id == ""
        assert delta.owner_kind == ""
        assert delta.owner_id == ""
        assert delta.aspect == ""
        assert delta.before is None
        assert delta.after is None
        assert delta.magnitude is None
        assert delta.id

    def test_to_dict_and_from_dict_round_trip(self):
        delta = StateDelta(
            event_id="event-1",
            owner_kind="region",
            owner_id="12",
            aspect="population",
            before="80.0",
            after="78.4",
            magnitude=-1.6,
        )

        data = delta.to_dict()
        restored = StateDelta.from_dict(data)

        assert restored.event_id == "event-1"
        assert restored.owner_kind == "region"
        assert restored.owner_id == "12"
        assert restored.aspect == "population"
        assert restored.before == "80.0"
        assert restored.after == "78.4"
        assert restored.magnitude == -1.6

    def test_before_after_are_strings_not_parsed_back(self):
        delta = StateDelta(before="80.0", after="78.4")

        assert isinstance(delta.before, str)
        assert isinstance(delta.after, str)
