from pathlib import Path

import pytest

from src.classes.age import Age
from src.classes.items.magic_stone import MagicStone
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
    avatar.magic_stone = MagicStone(0)
    return region


def test_support_owner_requires_current_presence_and_need(base_world):
    sect = _sect()
    avatar = _avatar(base_world, "member")
    region = _ground(base_world, sect, avatar)

    assert eligible_member_ids(sect, region_id=str(region.id)) == ("member",)
    assert is_eligible_support_member(sect, avatar, region_id=str(region.id))
    avatar.tile.region = None
    assert eligible_member_ids(sect, region_id=str(region.id)) == ()


@pytest.mark.asyncio
async def test_execute_support_mutates_both_canonical_owners_and_records_deltas(
    base_world,
):
    """Through the owner's real boundary: a live offer and a real decision.

    Hand-made ids no longer reach the treasury, so the fixture goes through
    the same door the dispatcher does.
    """
    from tests.test_organization_reactivity_integration import _setup
    from tests.test_sect_support_authority import authorized_support

    sect, avatar, region, trigger, condition = _setup(base_world)
    context, option, decision_event = await authorized_support(
        base_world, sect, region, condition, trigger
    )

    event = execute_sect_member_support(
        context,
        option,
        decision_event_id=decision_event.id,
        decision_event=decision_event,
    )

    assert event.event_type == "sect_member_support_completed"
    assert sect.magic_stone == 700
    assert avatar.magic_stone.value == 300
    deltas = [StateDelta.from_dict(item) for item in event.causal_payload["deltas"]]
    assert {
        (item.owner_kind, item.owner_id, item.before, item.after) for item in deltas
    } == {
        ("sect", str(sect.id), "1000", "700"),
        ("avatar", str(avatar.id), "0", "300"),
    }
    # Both owners really moved, and each delta names this event.
    assert all(item.event_id == event.id for item in deltas)
    # The real decision and the real condition are the cited causes.
    assert {link.cause_event_id for link in event.causal_links} == {
        decision_event.id,
        trigger.id,
    }


def test_support_owner_rejects_stale_membership_without_mutation(base_world):
    sect = _sect()
    avatar = _avatar(base_world, "member")
    _ground(base_world, sect, avatar)
    avatar.leave_sect()

    assert not transfer_sect_member_support(sect, avatar)
    assert sect.magic_stone == 1000
    assert avatar.magic_stone.value == 0
