from types import SimpleNamespace

import pytest

from src.classes.core.dynasty import Dynasty, ImperialClaim, ImperialCrisis
from src.classes.relation.relation import Relation
from src.server.assemblers.dynasty_detail import build_dynasty_detail
from src.server.assemblers.dynasty_overview import build_dynasty_overview
from src.systems.imperial_crisis_service import (
    ensure_succession_crisis,
    get_imperial_opposition_blocker,
    get_imperial_support_blocker,
    open_imperial_claim,
    oppose_imperial_claim,
    resolve_imperial_crisis,
    sync_royal_membership,
    support_imperial_claim,
)


class _Avatar:
    def __init__(self, avatar_id, *, age=30, rank="none", reputation=0):
        self.id = avatar_id
        self.name = avatar_id
        self.is_dead = False
        self.age = SimpleNamespace(age=age)
        self.race = SimpleNamespace(id="human")
        self.official_rank = rank
        self.court_reputation = reputation
        self.cultivation_progress = SimpleNamespace(realm=None)
        self.relations = {}


class _AvatarManager:
    def __init__(self, avatars):
        self.avatars = {avatar.id: avatar for avatar in avatars}

    def get_avatar(self, avatar_id):
        return self.avatars.get(str(avatar_id))

    def get_living_avatars(self):
        return [avatar for avatar in self.avatars.values() if not avatar.is_dead]


def _world(avatars, dynasty):
    return SimpleNamespace(
        month_stamp=0,
        dynasty=dynasty,
        avatar_manager=_AvatarManager(avatars),
    )


def test_old_imperial_crisis_schema_is_rejected():
    with pytest.raises(ValueError, match="Legacy imperial crisis schema"):
        ImperialCrisis.from_dict(
            {"emperor_avatar_id": "emperor", "claimant_avatar_id": "claimant"}
        )


def test_multiple_claims_keep_independent_positions_and_evidence():
    emperor = _Avatar("emperor")
    first = _Avatar("first")
    second = _Avatar("second")
    supporters = [_Avatar(f"official-{index}", rank="minister") for index in range(3)]
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id, first.id, second.id],
        royal_blood_member_ids=[emperor.id, first.id, second.id],
    )
    world = _world([emperor, first, second, *supporters], dynasty)

    first_event = open_imperial_claim(world, first.id)
    second_event = open_imperial_claim(world, second.id)
    support_imperial_claim(world, supporters[0].id, first.id)
    oppose_imperial_claim(world, supporters[1].id, first.id)
    oppose_imperial_claim(world, supporters[2].id, second.id)

    assert [claim.candidate_id for claim in dynasty.imperial_crisis.claims] == [
        first.id,
        second.id,
    ]
    first_claim, second_claim = dynasty.imperial_crisis.claims
    assert first_claim.political_positions == {
        supporters[0].id: "support",
        supporters[1].id: "oppose",
    }
    assert second_claim.political_positions == {supporters[2].id: "oppose"}
    assert first_event.id in first_claim.evidence_event_ids
    assert second_event.id in second_claim.evidence_event_ids


def test_vacancy_prefers_blood_adults_and_tie_or_insufficient_remains_active():
    blood_one = _Avatar("blood-one")
    blood_two = _Avatar("blood-two")
    common_official = _Avatar("official", rank="minister", reputation=1000)
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=None,
        royal_house_member_ids=[blood_one.id, blood_two.id],
        royal_blood_member_ids=[blood_one.id, blood_two.id],
    )
    world = _world([blood_one, blood_two, common_official], dynasty)

    crisis = ensure_succession_crisis(world)
    assert crisis.kind == "succession"
    assert crisis.claims == []
    open_imperial_claim(world, blood_one.id)
    open_imperial_claim(world, blood_two.id)
    assert {claim.candidate_id for claim in crisis.claims} == {blood_one.id, blood_two.id}
    world.month_stamp = 12
    resolve_imperial_crisis(world)
    assert crisis.status == "active"
    assert dynasty.current_emperor_id is None


def test_claims_fail_independently_when_one_candidate_dies():
    emperor = _Avatar("emperor")
    dead = _Avatar("dead")
    living = _Avatar("living", reputation=1000)
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id, dead.id, living.id],
        royal_blood_member_ids=[emperor.id, dead.id, living.id],
    )
    world = _world([emperor, dead, living], dynasty)
    open_imperial_claim(world, dead.id)
    open_imperial_claim(world, living.id)
    dead.is_dead = True
    world.month_stamp = 12

    resolve_imperial_crisis(world)

    claims = {claim.candidate_id: claim for claim in dynasty.imperial_crisis.claims}
    assert claims[dead.id].status == "failed"
    assert claims[living.id].status == "ascended"
    assert dynasty.current_emperor_id == living.id


def test_challenge_becomes_succession_without_losing_claims():
    emperor = _Avatar("emperor")
    candidate = _Avatar("candidate")
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id, candidate.id],
        royal_blood_member_ids=[emperor.id, candidate.id],
    )
    world = _world([emperor, candidate], dynasty)
    open_imperial_claim(world, candidate.id)
    original_claim_ids = [claim.candidate_id for claim in dynasty.imperial_crisis.claims]
    emperor.is_dead = True
    world.month_stamp = 12

    resolve_imperial_crisis(world)

    assert dynasty.imperial_crisis.kind == "succession"
    assert dynasty.imperial_crisis.incumbent_id is None
    assert [claim.candidate_id for claim in dynasty.imperial_crisis.claims] == original_claim_ids


def test_dynasty_membership_and_crisis_round_trip_into_dto():
    emperor = _Avatar("emperor")
    child = _Avatar("child", age=20)
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id, child.id],
        royal_blood_member_ids=[emperor.id, child.id],
        imperial_crisis=ImperialCrisis(
            "challenge",
            emperor.id,
            0,
            [ImperialClaim(child.id, 0)],
        ),
    )
    world = _world([emperor, child], dynasty)
    restored = Dynasty.from_dict(dynasty.to_dict())
    assert restored.royal_house_member_ids == [emperor.id, child.id]
    assert restored.royal_blood_member_ids == [emperor.id, child.id]
    assert restored.imperial_crisis.claims[0].candidate_id == child.id
    assert build_dynasty_overview(world)["royal_blood_member_ids"] == [emperor.id, child.id]
    assert build_dynasty_detail(world)["imperial_crisis"]["claims"][0]["candidate"]["id"] == child.id


def test_birth_enters_bloodline_but_marriage_enters_house_only():
    emperor = _Avatar("emperor")
    spouse = _Avatar("spouse")
    child = _Avatar("child")
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id],
        royal_blood_member_ids=[emperor.id],
    )

    dynasty.register_marriage([emperor.id, spouse.id])
    dynasty.register_birth(child.id, [emperor.id, spouse.id])

    assert spouse.id in dynasty.royal_house_member_ids
    assert spouse.id not in dynasty.royal_blood_member_ids
    assert child.id in dynasty.royal_house_member_ids
    assert child.id in dynasty.royal_blood_member_ids


def test_yeqinglian_consort_and_children_sync_to_distinct_membership_sets():
    emperor = _Avatar("emperor")
    ye_qinglian = _Avatar("YeQinglian")
    child_one = _Avatar("YeChildOne")
    child_two = _Avatar("YeChildTwo")
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id],
        royal_blood_member_ids=[emperor.id],
    )

    lover_state = SimpleNamespace(identity_relations={Relation.IS_LOVER_OF}, blood_relation=None)
    child_state = SimpleNamespace(identity_relations=set(), blood_relation=Relation.IS_CHILD_OF)
    parent_state = SimpleNamespace(identity_relations=set(), blood_relation=Relation.IS_PARENT_OF)
    emperor.relations = {ye_qinglian: lover_state, child_one: child_state, child_two: child_state}
    ye_qinglian.relations = {emperor: lover_state, child_one: child_state, child_two: child_state}
    child_one.relations = {
        emperor: parent_state,
        ye_qinglian: parent_state,
    }
    child_two.relations = {
        emperor: parent_state,
        ye_qinglian: parent_state,
    }
    world = _world([emperor, ye_qinglian, child_one, child_two], dynasty)

    sync_royal_membership(world)
    restored = Dynasty.from_dict(dynasty.to_dict())

    assert ye_qinglian.id in restored.royal_house_member_ids
    assert ye_qinglian.id not in restored.royal_blood_member_ids
    assert {child_one.id, child_two.id}.issubset(restored.royal_blood_member_ids)
    assert {child_one.id, child_two.id}.issubset(restored.royal_house_member_ids)


def test_sync_does_not_promote_a_non_blood_emperor_into_the_royal_bloodline():
    appointed_emperor = _Avatar("appointed-emperor")
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=appointed_emperor.id,
    )
    world = _world([appointed_emperor], dynasty)

    sync_royal_membership(world)

    assert dynasty.royal_house_member_ids == [appointed_emperor.id]
    assert dynasty.royal_blood_member_ids == []


def test_positions_require_canonical_candidate_id():
    emperor = _Avatar("emperor")
    candidate = _Avatar("candidate")
    official = _Avatar("official", rank="minister")
    dynasty = Dynasty(
        1,
        "Test",
        "",
        current_emperor_id=emperor.id,
        royal_house_member_ids=[emperor.id, candidate.id],
        royal_blood_member_ids=[emperor.id, candidate.id],
    )
    world = _world([emperor, candidate, official], dynasty)
    open_imperial_claim(world, candidate.id)

    assert get_imperial_support_blocker(world, official.id) is not None
    assert get_imperial_opposition_blocker(world, official.id) is not None
