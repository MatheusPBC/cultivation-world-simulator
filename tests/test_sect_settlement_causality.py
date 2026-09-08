"""Causal coverage for the annual sect settlement.

The settlement's economics are deliberately untouched here: the incomes,
estimated upkeep, cadence and the war-weariness rule are exactly what they
were. What is asserted is that the mutations it already performed are now
visible as canonical evidence -- one typed fact per sect, one delta per field
that really changed, and nothing invented for a field that did not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.classes.alignment import Alignment
from src.classes.causal_origin import CausalOrigin
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.environment.sect_region import SectRegion
from src.classes.event import FactKind
from src.classes.sect_ranks import SectRank
from src.sim.managers.sect_manager import (
    SECT_SETTLEMENT_EVENT_TYPE,
    WAR_WEARINESS_YEARLY_RECOVERY,
    SectManager,
)


def _avatar(world, name: str, *, pos=(0, 0), stones: int = 0):
    from src.classes.age import Age
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.items.magic_stone import MagicStone
    from src.classes.root import Root
    from src.systems.cultivation import Realm
    from src.systems.time import Month, Year, create_month_stamp
    from src.utils.id_generator import get_avatar_id

    avatar = Avatar(
        world=world,
        name=name,
        id=get_avatar_id(),
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        pos_x=pos[0],
        pos_y=pos[1],
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    avatar.magic_stone = MagicStone(stones)
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _sect(world, sect_id: int, name: str, members: dict, *, cors) -> Sect:
    """A sect with a real territory, which is what gives it a center.

    `update_sects` derives every sect's center from the map's `SectRegion`s,
    not from the headquarters object, and returns early when no center exists.
    """
    region_id = 1000 + sect_id
    region = SectRegion(
        id=region_id, name=f"{name} Region", desc="", sect_id=sect_id,
        sect_name=name, cors=list(cors),
    )
    world.map.regions[region_id] = region
    world.map.region_cors[region_id] = list(cors)
    world.map.update_sect_regions()

    sect = Sect(
        id=sect_id,
        name=name,
        desc="",
        member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="HQ", desc="", image=Path("")),
        technique_names=[],
        orthodoxy_id="dao",
    )
    sect.members = dict(members)
    for avatar in members.values():
        avatar.sect = sect
    existing = list(getattr(world, "existed_sects", None) or [])
    world.existed_sects = [*existing, sect]
    world.sect_context.from_existed_sects(world.existed_sects)
    return sect


@pytest.fixture
def settled(base_world):
    """One sect with a living patriarch and a dead member, at its HQ tile."""
    patriarch = _avatar(base_world, "Patriarch", pos=(2, 2), stones=100)
    patriarch.sect_rank = SectRank.Patriarch
    corpse = _avatar(base_world, "Departed", pos=(2, 3), stones=50)
    corpse.sect_rank = SectRank.Elder
    corpse.is_dead = True
    sect = _sect(
        base_world,
        1,
        "Settlement Sect",
        {str(patriarch.id): patriarch, str(corpse.id): corpse},
        cors=[(2, 2), (2, 3), (3, 2)],
    )
    sect.magic_stone = 500
    return base_world, sect, patriarch, corpse


def _settlement_for(events, sect_id: int):
    return next(
        event
        for event in events
        if event.event_type == SECT_SETTLEMENT_EVENT_TYPE
        and sect_id in (event.related_sects or [])
    )


def _deltas_by(event, owner_kind: str, aspect: str) -> list[dict]:
    return [
        delta
        for delta in event.causal_payload["deltas"]
        if delta["owner_kind"] == owner_kind and delta["aspect"] == aspect
    ]


def _stones(avatar) -> int:
    """The canonical amount an Avatar holds: the field the save layer writes."""
    return int(avatar.magic_stone.value)


def test_settlement_records_one_typed_fact_with_real_before_and_after(settled):
    world, sect, patriarch, corpse = settled
    treasury_before = sect.magic_stone
    patriarch_before = _stones(patriarch)
    # This settlement really pays and really costs; asserted up front so the
    # evidence checks below can never pass by simply not happening.
    upkeep = sect.get_member_upkeep_for_avatar(patriarch)
    assert upkeep > 0

    events = SectManager(world).update_sects()

    event = _settlement_for(events, sect.id)
    assert event.event_type == SECT_SETTLEMENT_EVENT_TYPE
    assert event.causal_origin is CausalOrigin.DETERMINISTIC
    # Nobody chose a settlement; it is not a decision and carries no audit.
    assert "decision" not in event.causal_payload
    assert event.fact_kind in {FactKind.STATE_TRANSITION, FactKind.OCCURRENCE}

    payload = event.causal_payload["sect_annual_settlement"]
    assert payload["sect_id"] == sect.id
    assert payload["net_change"] == payload["income"] - payload["upkeep_total"]
    assert payload["war_weariness_yearly_recovery"] == WAR_WEARINESS_YEARLY_RECOVERY
    assert isinstance(payload["upkeep_breakdown"], dict)

    assert event.fact_kind is FactKind.STATE_TRANSITION

    # Exactly one treasury delta, stating the owner's real transition.
    treasury_deltas = _deltas_by(event, "sect", "magic_stone")
    assert len(treasury_deltas) == 1
    delta = treasury_deltas[0]
    assert sect.magic_stone == treasury_before + payload["net_change"]
    assert delta["before"] == str(treasury_before)
    assert delta["after"] == str(sect.magic_stone)
    assert delta["magnitude"] == float(sect.magic_stone - treasury_before)
    assert delta["event_id"] == event.id

    # Exactly one member delta: the living patriarch, really paid.
    member_deltas = _deltas_by(event, "avatar", "magic_stone")
    assert [item["owner_id"] for item in member_deltas] == [str(patriarch.id)]
    assert _stones(patriarch) == patriarch_before + upkeep
    assert member_deltas[0]["before"] == str(patriarch_before)
    assert member_deltas[0]["after"] == str(patriarch_before + upkeep)
    assert member_deltas[0]["magnitude"] == float(upkeep)
    assert payload["paid_member_count"] == 1
    assert event.related_avatars == [str(patriarch.id)]
    # A dead member is never paid and never appears as evidence.
    assert str(corpse.id) not in {delta["owner_id"] for delta in member_deltas}
    assert _stones(corpse) == 50
    assert str(corpse.id) not in (event.related_avatars or [])


def test_in_place_stone_growth_has_a_single_numeric_truth(settled):
    """A wallet grown with `+=` reports one amount, however it is read.

    `MagicStone` used to keep a second number in `.value` that its in-place
    operators updated while the `int` base stayed frozen, so `int(wallet)` and
    `wallet.value` could disagree and a delta could be built from the stale
    one. The amount is now derived from the object itself.
    """
    world, sect, patriarch, _corpse = settled
    patriarch.magic_stone += 50
    assert patriarch.magic_stone.value == 150
    assert int(patriarch.magic_stone) == 150
    assert int.__int__(patriarch.magic_stone) == 150

    upkeep = sect.get_member_upkeep_for_avatar(patriarch)
    event = _settlement_for(SectManager(world).update_sects(), sect.id)

    assert upkeep > 0
    member_deltas = _deltas_by(event, "avatar", "magic_stone")
    delta = next(item for item in member_deltas if item["owner_id"] == str(patriarch.id))
    assert delta["before"] == "150"
    assert delta["after"] == str(150 + upkeep)
    assert delta["magnitude"] == float(upkeep)
    assert _stones(patriarch) == 150 + upkeep


def test_a_negative_net_change_is_recorded_as_a_real_decrease(settled):
    world, sect, _patriarch, _corpse = settled
    sect.magic_stone = 500
    manager = SectManager(world)
    # The upkeep this settlement will actually charge, from the owner itself.
    upkeep_total, _breakdown = sect.estimate_yearly_member_upkeep()

    event = _settlement_for(manager.update_sects(), sect.id)

    payload = event.causal_payload["sect_annual_settlement"]
    assert payload["upkeep_total"] == upkeep_total
    # This fixture's upkeep really exceeds its income, so the decrease below
    # is asserted outright rather than only if it happened to occur.
    assert payload["net_change"] < 0
    delta = _deltas_by(event, "sect", "magic_stone")[0]
    assert delta["magnitude"] == float(payload["net_change"])
    assert int(delta["after"]) < int(delta["before"])
    assert int(delta["after"]) == sect.magic_stone
    assert sect.magic_stone == 500 + payload["net_change"]


def test_war_weariness_clamp_produces_no_delta_when_it_cannot_move(settled):
    world, sect, _patriarch, _corpse = settled
    # Already at the floor, and this settlement only ever subtracts here.
    sect.set_war_weariness(0)

    event = _settlement_for(SectManager(world).update_sects(), sect.id)

    payload = event.causal_payload["sect_annual_settlement"]
    assert payload["war_weariness_before"] == 0
    assert payload["war_weariness_after"] == 0
    # The clamp means nothing changed, so nothing is claimed to have changed.
    assert _deltas_by(event, "sect", "war_weariness") == []


def test_a_memberless_sect_records_only_its_treasury_change(base_world):
    """No members to pay, but its territory still earns: one delta, no avatars."""
    empty = _sect(base_world, 2, "Hermit Sect", {}, cors=[(7, 7)])
    empty.magic_stone = 0
    empty.set_war_weariness(0)

    event = _settlement_for(SectManager(base_world).update_sects(), empty.id)

    payload = event.causal_payload["sect_annual_settlement"]
    assert payload["upkeep_total"] == 0
    assert payload["paid_member_count"] == 0
    assert payload["net_change"] == payload["income"]
    assert _deltas_by(event, "avatar", "magic_stone") == []
    assert event.related_avatars in (None, [])
    assert len(_deltas_by(event, "sect", "magic_stone")) == 1
    assert event.fact_kind is FactKind.STATE_TRANSITION


def test_a_settlement_that_changes_nothing_is_an_occurrence(base_world, monkeypatch):
    """Zero income, zero members, weariness already at the floor.

    Only the income input is fixtured here -- the settlement's own arithmetic,
    cadence and clamp are untouched -- so this exercises the real "nothing
    moved" branch instead of asserting it conditionally.
    """
    empty = _sect(base_world, 2, "Hermit Sect", {}, cors=[(7, 7)])
    empty.magic_stone = 0
    empty.set_war_weariness(0)
    monkeypatch.setattr(
        SectManager, "calculate_income_by_sect", lambda self, snapshot: {}
    )

    event = _settlement_for(SectManager(base_world).update_sects(), empty.id)

    payload = event.causal_payload["sect_annual_settlement"]
    assert payload["income"] == 0
    assert payload["upkeep_total"] == 0
    assert payload["net_change"] == 0
    assert payload["war_weariness_before"] == payload["war_weariness_after"] == 0
    assert event.causal_payload["deltas"] == []
    assert event.fact_kind is FactKind.OCCURRENCE
    assert event.related_avatars in (None, [])
    assert payload["paid_member_count"] == 0
    assert empty.magic_stone == 0


def test_every_delta_names_its_own_event_and_passes_causal_integrity(settled):
    from src.sim.simulator_engine.context import SimulationStepContext
    from src.sim.simulator_engine.finalizer import validate_causal_integrity

    world, sect, _patriarch, _corpse = settled
    events = SectManager(world).update_sects()

    for event in events:
        for delta in event.causal_payload["deltas"]:
            assert delta["event_id"] == event.id
            assert delta["owner_kind"] in {"sect", "avatar"}
            # Never localized prose from MagicStone.__str__.
            assert str(int(delta["before"])) == delta["before"]
            assert str(int(delta["after"])) == delta["after"]

    ctx = SimulationStepContext.create(world)
    ctx.add_events(events)
    validate_causal_integrity(ctx, ctx.events)


def test_the_settlement_fact_survives_a_sqlite_round_trip(settled, tmp_path):
    from src.classes.event_storage import EventStorage

    world, sect, _patriarch, _corpse = settled
    event = _settlement_for(SectManager(world).update_sects(), sect.id)

    storage = EventStorage(tmp_path / "events.db")
    try:
        assert storage.add_event(event) is True
        restored = storage.get_event_by_id(event.id)
    finally:
        storage.close()

    assert restored is not None
    assert restored.event_type == SECT_SETTLEMENT_EVENT_TYPE
    assert restored.fact_kind is event.fact_kind
    assert restored.causal_origin is CausalOrigin.DETERMINISTIC
    assert restored.causal_payload["deltas"] == event.causal_payload["deltas"]
    assert (
        restored.causal_payload["sect_annual_settlement"]
        == event.causal_payload["sect_annual_settlement"]
    )


def test_a_rollback_restores_the_owners_the_settlement_moved(settled):
    from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint

    world, sect, patriarch, _corpse = settled
    checkpoint = SimulationMonthCheckpoint.capture(world)
    treasury_before = sect.magic_stone
    stones_before = _stones(patriarch)
    weariness_before = sect.war_weariness

    SectManager(world).update_sects()
    checkpoint.restore()

    assert sect.magic_stone == treasury_before
    assert _stones(patriarch) == stones_before
    assert sect.war_weariness == weariness_before


def test_the_settlement_is_deterministic_for_the_same_state(settled):
    """No RNG participates: the same state settles to the same figures."""
    world, sect, _patriarch, _corpse = settled
    treasury = sect.magic_stone
    weariness = sect.war_weariness

    first = _settlement_for(SectManager(world).update_sects(), sect.id)

    sect.magic_stone = treasury
    sect.set_war_weariness(weariness)
    second = _settlement_for(SectManager(world).update_sects(), sect.id)

    assert (
        first.causal_payload["sect_annual_settlement"]
        == second.causal_payload["sect_annual_settlement"]
    )
