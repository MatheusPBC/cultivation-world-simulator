import inspect
from copy import copy
from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoPetition, DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.environment.region import CityRegion
from src.classes.event import Event
from src.classes.mechanical_language import ConditionInstance
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.systems.celestial_dao_service import (
    answer_petition,
    create_petition,
    get_dao_context,
    maybe_create_monthly_petition,
)
from src.systems.imperial_crisis_service import (
    build_legitimacy_factors,
    open_imperial_claim,
    resolve_imperial_crisis,
)
from src.utils.llm.runtime_mode import llm_test_mode_scope


def _court(world, avatar):
    region = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    avatar.tile = SimpleNamespace(region=region)
    world.map.regions[7] = region
    world.avatar_manager.register_avatar(avatar)
    world.dynasty = Dynasty(id=1, name="Test", desc="", current_emperor_id=avatar.id)


def test_common_avatar_cannot_open_a_celestial_audience(base_world, dummy_avatar):
    base_world.map.regions[7] = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    with pytest.raises(ValueError):
        create_petition(
            base_world,
            initiator_kind="avatar",
            initiator_id=dummy_avatar.id,
            region_id=7,
            motivated_event_ids=[],
        )
    assert base_world.dao_petitions == []


def test_actual_sign_keeps_distinct_regional_readings(base_world, dummy_avatar):
    _court(base_world, dummy_avatar)
    base_world.map.regions[8] = SimpleNamespace(
        id=8, dao_tradition=DaoTradition.MANDATE_AND_ORDER
    )
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    answer_petition(base_world, audience.id, "sign")
    mercy = next(
        item
        for item in get_dao_context(base_world, region_id=7)
        if item["kind"] == "omen"
    )
    mandate = next(
        item
        for item in get_dao_context(base_world, region_id=8)
        if item["kind"] == "omen"
    )
    assert mercy["source_event_id"] == mandate["source_event_id"]
    assert mercy["interpretation"] != mandate["interpretation"]


@pytest.mark.asyncio
async def test_rites_are_social_claims_until_three_causes_accumulate(
    base_world, dummy_avatar
):
    _court(base_world, dummy_avatar)
    for month in (12, 16, 20):
        base_world.month_stamp = month
        cause = Event(
            month,
            f"Court crisis {month}",
            related_avatars=[dummy_avatar.id],
            is_major=True,
        )
        with llm_test_mode_scope(True):
            events = await maybe_create_monthly_petition(base_world, [cause])
        for event in events:
            base_world.event_manager.add_event(event)
        if month < 20:
            assert base_world.dao_petitions == []
            assert events[0].event_type == "dao_rite"
    audience = base_world.dao_petitions[0]
    assert audience.initiator_kind == "court"
    assert len(audience.rite_event_ids) == 3
    assert DaoPetition.from_dict(audience.to_dict()).rite_event_ids == audience.rite_event_ids
    assert any(
        item["kind"] == "unconfirmed_rite"
        for item in get_dao_context(base_world, region_id=7)
    )


@pytest.mark.asyncio
async def test_popular_rites_never_accumulate_toward_a_celestial_audience(base_world):
    region = CityRegion(
        id=9,
        name="Crowded City",
        desc="",
        cors=[(0, 0)],
        population=90,
        population_capacity=100,
        dao_tradition=DaoTradition.BALANCE,
    )
    base_world.mechanical_language.add_condition_instance(ConditionInstance(
        id="pressure",
        definition_id="overcrowded_settlement",
        target_kind="region",
        target_id="9",
        label="overcrowded settlement",
        intensity=0.9,
        started_month=12,
        cause_event_id="pressure-source",
    ))
    base_world.map.regions[region.id] = region

    for month in (12, 13, 14):
        base_world.month_stamp = month
        events = await maybe_create_monthly_petition(base_world, [])
        assert [event.event_type for event in events] == ["dao_rite"]
        for event in events:
            base_world.event_manager.add_event(event)

    assert base_world.dao_petitions == []


@pytest.mark.asyncio
async def test_popular_rite_limit_never_discards_institutional_rite(
    base_world,
    monkeypatch,
):
    regions = [
        CityRegion(
            id=region_id,
            name=f"City {region_id}",
            desc="",
            cors=[(region_id, 0)],
            population=90,
            population_capacity=100,
            dao_tradition=DaoTradition.BALANCE,
        )
        for region_id in (7, 8)
    ]
    cause = Event(base_world.month_stamp, "Sect crisis", is_major=True)
    monkeypatch.setattr(
        "src.systems.celestial_dao_service._institution_candidates",
        lambda _world, _cause: [("sect", "5", "Test Sect", regions[0])],
    )
    monkeypatch.setattr(
        "src.systems.celestial_dao_service._popular_rite_regions",
        lambda _world: [(region, cause) for region in regions],
    )

    events = await maybe_create_monthly_petition(base_world, [cause])

    institutional = [event for event in events if not event.causal_payload["dao_rite"].get("is_popular")]
    popular = [event for event in events if event.causal_payload["dao_rite"].get("is_popular")]
    assert len(institutional) == 1
    assert len(popular) == 2


def test_petition_target_is_not_caller_supplied():
    assert "target_avatar_id" not in inspect.signature(create_petition).parameters


def test_favor_is_limited_to_the_institution(base_world, dummy_avatar):
    _court(base_world, dummy_avatar)
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    answer_petition(base_world, audience.id, "favor")
    assert any(
        item["kind"] == "limited_favor"
        for item in get_dao_context(base_world, region_id=7, initiator_id="1")
    )
    assert not any(
        item["kind"] == "limited_favor"
        for item in get_dao_context(
            base_world, region_id=7, initiator_id=dummy_avatar.id
        )
    )


def test_celestial_evidence_targets_claimant_only_when_source_is_unambiguous(
    base_world, dummy_avatar
):
    _court(base_world, dummy_avatar)
    claimant = copy(dummy_avatar)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    claimant.official_rank = OFFICIAL_GRAND_COUNCILOR
    claimant.court_reputation = 700
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )
    open_imperial_claim(base_world, claimant.id)

    source = Event(
        base_world.month_stamp,
        "A proclamation names the claimant.",
        related_avatars=[claimant.id],
        is_major=True,
    )
    base_world.event_manager.add_event(source)
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[source.id],
        rite_event_ids=["r1", "r2", "r3"],
    )

    assert audience.target_avatar_id == claimant.id
    assert audience.target_evidence_event_ids == [source.id]
    answer = answer_petition(base_world, audience.id, "sign")
    factors, evidence_ids = build_legitimacy_factors(base_world, dummy_avatar, claimant)

    assert factors["celestial"] == 15
    assert source.id in evidence_ids
    assert answer.id in evidence_ids
    assert get_dao_context(base_world, region_id=7)[0]["target_avatar_id"] == claimant.id


def test_ambiguous_celestial_audience_remains_context_without_legitimacy_weight(
    base_world, dummy_avatar
):
    _court(base_world, dummy_avatar)
    claimant = copy(dummy_avatar)
    claimant.id = "claimant"
    claimant.name = "Claimant"
    claimant.official_rank = OFFICIAL_GRAND_COUNCILOR
    claimant.court_reputation = 700
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )
    open_imperial_claim(base_world, claimant.id)

    source = Event(
        base_world.month_stamp,
        "The court receives an ambiguous omen.",
        related_avatars=[dummy_avatar.id, claimant.id],
        is_major=True,
    )
    base_world.event_manager.add_event(source)
    audience = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[source.id],
        rite_event_ids=["r1", "r2", "r3"],
    )
    answer_petition(base_world, audience.id, "sign")
    factors, evidence_ids = build_legitimacy_factors(base_world, dummy_avatar, claimant)

    assert audience.target_avatar_id is None
    assert audience.target_evidence_event_ids == []
    assert factors["celestial"] == 0
    assert evidence_ids == []


def test_claimant_can_ascend_without_removing_emperor(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 700
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    base_world.avatar_manager.register_avatar(emperor)
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.court_reputation = 1000
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=emperor.id
    )
    open_imperial_claim(base_world, claimant.id)
    crisis = base_world.dynasty.imperial_crisis
    base_world.month_stamp += 12
    assert resolve_imperial_crisis(base_world) is not None
    assert crisis.status == "ascended"
    assert base_world.avatar_manager.get_avatar(emperor.id) is emperor


def test_negative_legitimacy_reading_does_not_end_active_crisis(
    base_world, dummy_avatar
):
    emperor = dummy_avatar
    emperor.court_reputation = 1000
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    base_world.avatar_manager.register_avatar(emperor)
    claimant = copy(emperor)
    claimant.id = "claimant"
    claimant.court_reputation = 700
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=emperor.id
    )
    open_imperial_claim(base_world, claimant.id)
    crisis = base_world.dynasty.imperial_crisis

    base_world.month_stamp += 12
    evaluation = resolve_imperial_crisis(base_world)

    assert evaluation is not None
    assert crisis.status == "active"
    assert crisis.legitimacy_factors["worldly_total"] < 0
    assert crisis.evaluations[-1]["status"] == "active"


def test_concrete_loss_of_eligibility_fails_claim(base_world, dummy_avatar):
    emperor = dummy_avatar
    emperor.court_reputation = 700
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    base_world.avatar_manager.register_avatar(emperor)
    claimant = copy(emperor)
    claimant.id = "claimant"
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=emperor.id
    )
    open_imperial_claim(base_world, claimant.id)
    crisis = base_world.dynasty.imperial_crisis
    claimant.official_rank = "none"

    base_world.month_stamp += 12
    evaluation = resolve_imperial_crisis(base_world)

    assert evaluation is not None
    assert crisis.status == "failed"
