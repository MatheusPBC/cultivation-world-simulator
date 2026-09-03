from pathlib import Path

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.environment.region import CityRegion
from src.classes.sect_ranks import get_rank_from_realm
from src.classes.root import Root
from src.classes.state_delta import StateDelta
from src.systems.cultivation import Realm
from src.systems.sect_member_support import (
    eligible_member_ids,
    execute_sect_member_support,
    is_eligible_support_member,
    transfer_sect_member_support,
)
from src.systems.time import Month, Year, create_month_stamp


def _sect() -> Sect:
    return Sect(
        1,
        "Azure Sect",
        "",
        "",
        Alignment.RIGHTEOUS,
        SectHeadQuarter("HQ", "", Path("")),
        [],
    )


def _avatar(world, avatar_id: str) -> Avatar:
    avatar = Avatar(
        world,
        avatar_id,
        avatar_id,
        create_month_stamp(Year(1), Month.JANUARY),
        Age(20, Realm.Qi_Refinement),
        Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    avatar.recalc_effects()
    return avatar


def _ground(world, sect, avatar):
    region = CityRegion(11, "Border City", "", cors=[(0, 0)])
    world.map.regions[region.id] = region
    avatar.tile.region = region
    avatar.join_sect(sect, get_rank_from_realm(avatar.cultivation_progress.realm))
    sect.magic_stone = 1000
    avatar.magic_stone.value = 0
    return region


def test_support_owner_requires_current_presence_and_need(base_world):
    sect = _sect()
    avatar = _avatar(base_world, "member")
    region = _ground(base_world, sect, avatar)

    assert eligible_member_ids(sect, region_id=str(region.id)) == ("member",)
    assert is_eligible_support_member(sect, avatar, region_id=str(region.id))
    avatar.tile.region = None
    assert eligible_member_ids(sect, region_id=str(region.id)) == ()


def test_execute_support_mutates_both_canonical_owners_and_records_deltas(base_world):
    sect = _sect()
    avatar = _avatar(base_world, "member")
    region = _ground(base_world, sect, avatar)

    event = execute_sect_member_support(
        base_world,
        sect,
        member_id=avatar.id,
        region_id=str(region.id),
        decision_event_id="decision-1",
        condition_event_id="condition-1",
    )

    assert event.event_type == "sect_member_support_completed"
    assert sect.magic_stone == 700
    assert avatar.magic_stone.value == 300
    deltas = [StateDelta.from_dict(item) for item in event.causal_payload["deltas"]]
    assert {
        (item.owner_kind, item.owner_id, item.before, item.after) for item in deltas
    } == {
        ("sect", "1", "1000", "700"),
        ("avatar", "member", "0", "300"),
    }
    assert {link.cause_event_id for link in event.causal_links} == {
        "decision-1",
        "condition-1",
    }


def test_support_owner_rejects_stale_membership_without_mutation(base_world):
    sect = _sect()
    avatar = _avatar(base_world, "member")
    _ground(base_world, sect, avatar)
    avatar.leave_sect()

    assert not transfer_sect_member_support(sect, avatar)
    assert sect.magic_stone == 1000
    assert avatar.magic_stone.value == 0
