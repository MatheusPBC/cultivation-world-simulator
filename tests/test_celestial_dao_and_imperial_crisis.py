from copy import copy
from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoPetitionStatus, DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.classes.event import Event
from src.systems.celestial_dao_service import answer_petition, create_petition, get_dao_context, interpret_sign, maybe_create_monthly_petition
from src.utils.llm.runtime_mode import llm_test_mode_scope
from src.systems.imperial_crisis_service import open_imperial_claim, resolve_imperial_crisis


def test_petition_response_is_persistent_causal_fact(base_world, dummy_avatar):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.map.regions[7] = SimpleNamespace(dao_tradition=DaoTradition.MERCY)
    petition = create_petition(base_world, initiator_kind="avatar", initiator_id=dummy_avatar.id, region_id=7, motivated_event_ids=["cause"], content="Help")

    event = answer_petition(base_world, petition.id, "favor")

    assert petition.status is DaoPetitionStatus.FAVORED
    assert petition.response_event_id == event.id
    assert petition.favor_expires_month == int(base_world.month_stamp) + 12
    assert event.causal_payload["deltas"][0]["owner_id"] == petition.id
    assert event.causal_links[0].cause_event_id == "cause"


def test_sect_petition_response_remains_linked_to_its_sect(base_world):
    base_world.map.regions[7] = SimpleNamespace(dao_tradition=DaoTradition.MERCY)
    petition = create_petition(base_world, initiator_kind="sect", initiator_id="9", region_id=7, motivated_event_ids=[])

    event = answer_petition(base_world, petition.id, "sign")

    assert event.related_sects == [9]


def test_same_sign_has_distinct_traditional_readings():
    mercy = interpret_sign(DaoTradition.MERCY, "A red comet")
    mandate = interpret_sign(DaoTradition.MANDATE_AND_ORDER, "A red comet")
    assert mercy != mandate
    assert "护佑" in mercy


def test_public_omen_is_interpreted_by_each_observers_regional_tradition(base_world, dummy_avatar):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.map.regions[7] = SimpleNamespace(dao_tradition=DaoTradition.MERCY)
    base_world.map.regions[8] = SimpleNamespace(dao_tradition=DaoTradition.MANDATE_AND_ORDER)
    petition = create_petition(base_world, initiator_kind="avatar", initiator_id=dummy_avatar.id, region_id=7, motivated_event_ids=[])
    answer_petition(base_world, petition.id, "sign")

    mercy_reading = get_dao_context(base_world, region_id=7)[0]
    mandate_reading = get_dao_context(base_world, region_id=8)[0]

    assert mercy_reading["source_event_id"] == mandate_reading["source_event_id"]
    assert mercy_reading["initiator_id"] == dummy_avatar.id
    assert mercy_reading["source_tradition"] == DaoTradition.MERCY.value
    assert mercy_reading["tradition"] == DaoTradition.MERCY.value
    assert mandate_reading["tradition"] == DaoTradition.MANDATE_AND_ORDER.value
    assert mercy_reading["interpretation"] != mandate_reading["interpretation"]


def test_omen_is_context_not_an_automatic_command(base_world, dummy_avatar):
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.map.regions[7] = SimpleNamespace(dao_tradition=DaoTradition.MERCY)
    petition = create_petition(base_world, initiator_kind="avatar", initiator_id=dummy_avatar.id, region_id=7, motivated_event_ids=[])
    answer_petition(base_world, petition.id, "sign")
    context = get_dao_context(base_world, region_id=7, initiator_id=dummy_avatar.id)
    assert context[0]["kind"] == "omen"
    assert "command" not in context[0]


@pytest.mark.asyncio
async def test_monthly_filter_creates_at_most_one_relevant_petition(base_world, dummy_avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.BALANCE)
    dummy_avatar.tile = SimpleNamespace(region=region)
    base_world.map.regions[7] = region
    base_world.avatar_manager.register_avatar(dummy_avatar)
    cause = Event(base_world.month_stamp, "A major turn", related_avatars=[dummy_avatar.id], is_major=True)
    with llm_test_mode_scope(True):
        assert await maybe_create_monthly_petition(base_world, [cause]) is not None
        assert await maybe_create_monthly_petition(base_world, [cause]) is None
    assert "A major turn" in base_world.dao_petitions[0].content


def test_favor_context_is_limited_to_the_petitioner(base_world, dummy_avatar):
    base_world.map.regions[7] = SimpleNamespace(dao_tradition=DaoTradition.BALANCE)
    petition = create_petition(base_world, initiator_kind="avatar", initiator_id="chosen", region_id=7, motivated_event_ids=[])
    answer_petition(base_world, petition.id, "favor")
    assert get_dao_context(base_world, region_id=7, initiator_id="chosen")[0]["kind"] == "limited_favor"
    assert get_dao_context(base_world, region_id=7, initiator_id=str(dummy_avatar.id)) == []


def test_invalid_claim_preserves_state(base_world, dummy_avatar):
    emperor = dummy_avatar
    base_world.avatar_manager.register_avatar(emperor)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)

    with pytest.raises(ValueError):
        open_imperial_claim(base_world, emperor.id)
    assert base_world.dynasty.imperial_crisis is None


def test_claimant_can_ascend_without_removing_emperor(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 700
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    base_world.avatar_manager.register_avatar(emperor)
    from copy import copy
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    claimant.court_reputation = 1000
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)

    crisis = open_imperial_claim(base_world, claimant.id)
    assert resolve_imperial_crisis(base_world) is None
    assert crisis.status == "active"
    base_world.month_stamp += 12
    event = resolve_imperial_crisis(base_world)

    assert crisis.status == "ascended"
    assert base_world.dynasty.current_emperor_id == claimant.id
    assert base_world.avatar_manager.get_avatar(emperor.id) is emperor
    assert event is not None
    assert crisis.legitimacy_factors["reputation"] == 300
    assert crisis.legitimacy_factors["total"] >= 180
    assert [(delta["owner_kind"], delta["aspect"], delta["before"], delta["after"]) for delta in event.causal_payload["deltas"]] == [
        ("imperial_crisis", "status", "active", "ascended"),
        ("dynasty", "current_emperor_id", emperor.id, claimant.id),
    ]


def test_celestial_sign_influences_but_cannot_win_a_crisis_alone(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 700
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.tile = SimpleNamespace(region=SimpleNamespace(id=8, dao_tradition=DaoTradition.BALANCE))
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    claimant.tile = SimpleNamespace(region=SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY))
    base_world.map.regions[7] = claimant.tile.region
    base_world.map.regions[8] = emperor.tile.region
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)

    petition = create_petition(base_world, initiator_kind="avatar", initiator_id=claimant.id, region_id=7, motivated_event_ids=[])
    answer_petition(base_world, petition.id, "sign")
    crisis = open_imperial_claim(base_world, claimant.id)

    base_world.month_stamp += 12
    resolve_imperial_crisis(base_world)

    assert crisis.status == "stalemate"
    assert crisis.legitimacy_factors["celestial"] > 0
    assert crisis.legitimacy_factors["worldly_total"] == 0


def test_claim_can_fail_publicly_after_a_full_crisis_year(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 1000
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    claimant.court_reputation = 700
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=emperor.id)

    crisis = open_imperial_claim(base_world, claimant.id)
    base_world.month_stamp += 12
    event = resolve_imperial_crisis(base_world)

    assert crisis.status == "failed"
    assert base_world.dynasty.current_emperor_id == emperor.id
    assert event is not None
    assert event.causal_payload["deltas"][0]["after"] == "failed"
    assert len(event.causal_payload["deltas"]) == 1
