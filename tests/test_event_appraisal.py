import dataclasses

import pytest

from src.classes.emotions import EmotionType
from src.classes.event_appraisal import AppraisalSource, EventAppraisal


def make_appraisal(**overrides) -> EventAppraisal:
    defaults = dict(
        event_id="event-1",
        appraiser_avatar_id="avatar-a",
        focus_avatar_id="avatar-b",
        personal_importance=0.8,
        valence=-0.6,
        persistence=0.5,
        primary_emotion=EmotionType.ANGRY,
        summary="Betrayed during the ambush.",
        source=AppraisalSource.LLM,
    )
    defaults.update(overrides)
    return EventAppraisal(**defaults)


def test_event_appraisal_defaults_and_id():
    appraisal = make_appraisal()
    assert appraisal.id
    assert appraisal.event_id == "event-1"
    assert appraisal.appraiser_avatar_id == "avatar-a"
    assert appraisal.focus_avatar_id == "avatar-b"
    assert appraisal.primary_emotion is EmotionType.ANGRY
    assert appraisal.source is AppraisalSource.LLM


def test_event_appraisal_round_trips_through_to_dict_from_dict():
    appraisal = make_appraisal()
    restored = EventAppraisal.from_dict(appraisal.to_dict())
    assert restored == appraisal


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("personal_importance", 1.5),
        ("personal_importance", -0.1),
        ("valence", 1.1),
        ("valence", -1.1),
        ("persistence", 1.5),
        ("persistence", -0.5),
    ],
)
def test_event_appraisal_rejects_out_of_range_values(field_name, bad_value):
    with pytest.raises(ValueError):
        make_appraisal(**{field_name: bad_value})


def test_event_appraisal_rejects_summary_over_240_characters():
    with pytest.raises(ValueError):
        make_appraisal(summary="x" * 241)


def test_event_appraisal_effective_weight_at_zero_age_equals_importance():
    appraisal = make_appraisal(personal_importance=0.8, persistence=0.3)
    assert appraisal.effective_weight(0) == pytest.approx(0.8)


def test_event_appraisal_effective_weight_decays_over_time():
    appraisal = make_appraisal(personal_importance=1.0, persistence=0.0)
    ten_years = appraisal.effective_weight(120)
    forty_years = appraisal.effective_weight(480)
    hundred_years = appraisal.effective_weight(1200)
    assert ten_years == pytest.approx(0.5)
    assert forty_years == pytest.approx(0.0625)
    assert hundred_years == pytest.approx(2 ** -10)


def test_event_appraisal_persistence_floors_decay():
    appraisal = make_appraisal(personal_importance=1.0, persistence=1.0)
    assert appraisal.effective_weight(1200) == pytest.approx(1.0)


def test_event_appraisal_effective_weight_rejects_negative_age():
    appraisal = make_appraisal()
    with pytest.raises(ValueError):
        appraisal.effective_weight(-1)


def test_event_appraisal_is_frozen():
    appraisal = make_appraisal()
    with pytest.raises(dataclasses.FrozenInstanceError):
        appraisal.valence = 0.9
