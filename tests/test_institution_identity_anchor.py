"""Declared sect headquarters become identity anchors, once, at genesis.

The only source is the map's own declaration: a `SectRegion` names its owner
through `sect_id`. A dynasty declares no capital and no founder anywhere, so
none is inferred, and no city is ever created for a `SectRegion`.

The producer runs only during new-world initialization. Neither an ordinary
load nor the monthly reconciliation may add an anchor, because that would
invent a past.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.classes.alignment import Alignment
from src.classes.causal_origin import CausalOrigin
from src.classes.core.dynasty import Dynasty
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.environment.sect_region import SectRegion
from src.classes.event import FactKind
from src.classes.institution import IdentityAnchorKind
from src.classes.mechanical_language import EntityRef
from src.systems.institution_bootstrap import (
    bootstrap_institutional_authority,
    establish_genesis_identity_anchors,
    synchronize_institutional_authority,
)

ANCHOR_EVENT_TYPE = "institution_identity_anchored"


def _sect(sect_id: int, name: str, *, active: bool = True) -> Sect:
    sect = Sect(
        sect_id, name, "", "", Alignment.RIGHTEOUS,
        SectHeadQuarter(f"{name} Hall", "", Path("")), [], magic_stone=100,
    )
    sect.is_active = active
    return sect


def _seat(region_id: int, sect_id: int, name: str = "Seat") -> SectRegion:
    return SectRegion(
        id=region_id, name=name, desc="", cors=[(0, 0)], sect_id=sect_id
    )


@pytest.fixture
def anchored(base_world):
    """One active sect whose seat the map really declares.

    The region id differs from the sect id, so confusing the two fails.
    """
    base_world.dynasty = Dynasty(1, "Test Dynasty", "", current_emperor_id=None)
    sect = _sect(401, "Azure Peak")
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    seat = _seat(901, sect.id, "Azure Peak")
    base_world.map.regions[seat.id] = seat
    bootstrap_institutional_authority(base_world)
    return sect, seat


def _anchors(world):
    return world.institutional_authority.identity_anchors


def _institution_id(world, sect_id: int) -> str:
    institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("sect", str(sect_id))
    )
    assert institution is not None
    return institution.id


# --------------------------------------------------------------------------
# The anchor and its premise
# --------------------------------------------------------------------------


def test_a_declared_seat_becomes_an_anchor_citing_a_persisted_premise(
    base_world, anchored
):
    sect, seat = anchored
    genesis = int(base_world.month_stamp)

    produced = establish_genesis_identity_anchors(base_world)

    assert len(produced) == 1
    event = produced[0]
    assert len(_anchors(base_world)) == 1
    anchor = next(iter(_anchors(base_world).values()))

    assert anchor.institution_id == _institution_id(base_world, sect.id)
    assert anchor.kind is IdentityAnchorKind.HEADQUARTERS
    # The subject is the region, and the region id is not the sect id.
    assert anchor.subject == EntityRef("region", str(seat.id))
    assert anchor.subject.id != str(sect.id)
    assert anchor.established_month == genesis

    # The evidence is a fact the store really holds.
    assert anchor.evidence_event_ids == (event.id,)
    stored = base_world.event_manager.get_event_by_id(event.id)
    assert stored is not None
    assert event.event_type == ANCHOR_EVENT_TYPE
    assert event.fact_kind is FactKind.STATE_TRANSITION
    assert event.causal_origin is CausalOrigin.DETERMINISTIC
    assert int(event.month_stamp) == genesis

    params = event.render_params
    assert params["institution_id"] == anchor.institution_id
    assert params["anchor_id"] == anchor.id
    assert params["anchor_kind"] == IdentityAnchorKind.HEADQUARTERS.value
    assert params["region_id"] == str(seat.id)
    assert params["institution_name"] == sect.name
    assert params["region_name"] == seat.name
    assert params["premise"] == "world_genesis"

    delta = event.causal_payload["deltas"][0]
    assert delta["event_id"] == event.id
    assert delta["owner_kind"] == "institutional_authority"
    assert delta["owner_id"] == anchor.institution_id
    assert delta["aspect"] == f"identity_anchor:{anchor.id}"
    assert delta["before"] == "absent"
    assert delta["after"] == "established"
    # A declared pre-existing seat, not a founding act.
    assert "found" not in event.content.lower()


def test_running_twice_adds_no_second_anchor_or_fact(base_world, anchored):
    """Idempotent by deterministic id, not by luck."""
    first = establish_genesis_identity_anchors(base_world)
    before = base_world.event_manager.count()

    second = establish_genesis_identity_anchors(base_world)

    assert len(first) == 1 and second == []
    assert len(_anchors(base_world)) == 1
    assert base_world.event_manager.count() == before


# --------------------------------------------------------------------------
# What is not anchored
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arrange,reason",
    (
        pytest.param(
            lambda world, sect, seat: world.map.regions.__setitem__(
                seat.id, _seat(seat.id, -1)
            ),
            "undeclared sect_id",
            id="sect-id-minus-one",
        ),
        pytest.param(
            lambda world, sect, seat: world.map.regions.__setitem__(
                seat.id, _seat(seat.id, 999)
            ),
            "sect that does not exist",
            id="missing-sect",
        ),
        pytest.param(
            lambda world, sect, seat: (
                setattr(sect, "is_active", False),
                world.sect_context.from_existed_sects([sect]),
            ),
            "inactive sect",
            id="inactive-sect",
        ),
    ),
)
def test_nothing_is_anchored_without_a_declaration(
    base_world, anchored, arrange, reason
):
    sect, seat = anchored
    arrange(base_world, sect, seat)

    assert establish_genesis_identity_anchors(base_world) == [], reason
    assert _anchors(base_world) == {}


def test_a_dynasty_and_a_city_are_never_anchored(base_world, anchored):
    """No capital and no founder is declared anywhere, so none is invented."""
    from src.classes.environment.region import CityRegion

    sect, _seat_region = anchored
    city = CityRegion(id=311, name="Plain City", desc="", cors=[(2, 2)])
    base_world.map.regions[city.id] = city
    bootstrap_institutional_authority(base_world)

    establish_genesis_identity_anchors(base_world)

    kinds = {anchor.subject.id for anchor in _anchors(base_world).values()}
    assert kinds == {"901"}
    assert all(
        anchor.institution_id.startswith("inst:sect:")
        for anchor in _anchors(base_world).values()
    )
    # And the sect region did not become a city.
    assert not isinstance(base_world.map.regions[901], CityRegion)


def test_two_sects_get_distinct_anchors_and_distinct_facts(base_world, anchored):
    sect, seat = anchored
    other = _sect(402, "Cloud Vale")
    base_world.existed_sects = [sect, other]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    other_seat = _seat(902, other.id, "Cloud Vale")
    base_world.map.regions[other_seat.id] = other_seat
    bootstrap_institutional_authority(base_world)

    produced = establish_genesis_identity_anchors(base_world)

    assert len(produced) == 2
    anchors = _anchors(base_world)
    assert len(anchors) == 2
    assert len({anchor.id for anchor in anchors.values()}) == 2
    assert len({event.id for event in produced}) == 2
    by_institution = {
        anchor.institution_id: anchor.subject.id for anchor in anchors.values()
    }
    assert by_institution[_institution_id(base_world, sect.id)] == str(seat.id)
    assert by_institution[_institution_id(base_world, other.id)] == str(
        other_seat.id
    )


# --------------------------------------------------------------------------
# Never retroactive
# --------------------------------------------------------------------------


def test_bootstrap_and_sync_never_create_an_anchor(base_world, anchored):
    """A load or a monthly reconciliation must not invent a past."""
    bootstrap_institutional_authority(base_world)
    assert _anchors(base_world) == {}

    synchronize_institutional_authority(base_world)
    assert _anchors(base_world) == {}

    base_world.month_stamp = type(base_world.month_stamp)(
        int(base_world.month_stamp) + 12
    )
    synchronize_institutional_authority(base_world)
    assert _anchors(base_world) == {}
    assert not [
        event
        for event in base_world.event_manager.get_recent_events(limit=200)
        if event.event_type == ANCHOR_EVENT_TYPE
    ]


# --------------------------------------------------------------------------
# Persistence and the evidence guarantee
# --------------------------------------------------------------------------


def test_a_real_save_load_roundtrip_keeps_the_anchor_and_its_evidence(
    base_world, anchored, tmp_path
):
    """And the save would refuse outright if the evidence were missing."""
    from unittest.mock import patch

    from src.sim.load.load_game import get_events_db_path, load_game
    from src.sim.save.save_game import (
        _validate_institutional_evidence,
        save_game,
    )
    from src.sim.simulator import Simulator

    sect, seat = anchored
    produced = establish_genesis_identity_anchors(base_world)
    anchor = next(iter(_anchors(base_world).values()))
    original_map = base_world.map

    save_path = tmp_path / "anchor.json"
    success, _message = save_game(
        # The active sect round-trips too, not an empty list.
        base_world, Simulator(base_world), [sect], save_path
    )
    assert success
    base_world.event_manager.close()

    with patch(
        "src.run.load_map.load_cultivation_world_map", return_value=original_map
    ):
        loaded, _simulator, _sects = load_game(save_path)

    restored = loaded.institutional_authority.identity_anchors
    assert len(restored) == 1
    back = next(iter(restored.values()))
    assert back == anchor
    assert loaded.event_manager.get_event_by_id(produced[0].id) is not None
    assert loaded.sect_context.get_active_sects()

    # The guarantee itself: an anchor whose evidence is absent cannot be
    # saved, so evidence can never be pruned out from under an anchor.
    from src.classes.institution import InstitutionalIdentityAnchor

    events_db = get_events_db_path(save_path)
    _validate_institutional_evidence(loaded, events_db)  # passes as it stands
    loaded.institutional_authority.add_identity_anchor(
        InstitutionalIdentityAnchor(
            institution_id=back.institution_id,
            kind=IdentityAnchorKind.SACRED_SITE,
            subject=EntityRef("region", "902"),
            established_month=int(loaded.month_stamp),
            evidence_event_ids=("never-stored",),
        )
    )
    with pytest.raises(ValueError, match="canonical causal evidence"):
        _validate_institutional_evidence(loaded, events_db)


# No month-rollback test lives here on purpose. This producer runs once
# during new-world initialization, outside any month transaction, and neither
# `bootstrap_institutional_authority` nor `synchronize_institutional_authority`
# calls it -- `test_bootstrap_and_sync_never_create_an_anchor` above is the
# invariant that matters. A failed initialization discards the candidate world
# entirely, and the shared month-rollback behaviour is covered by the existing
# month-transaction suite.


# --------------------------------------------------------------------------
# The dormant factor wakes up
# --------------------------------------------------------------------------


def test_the_sponsorship_factor_reads_the_generated_anchor(base_world, anchored):
    """The consumer that was structurally dead now sees a real anchor.

    `_identity_anchor_impact` matches the sponsor's institution against the
    rite's own region, so it answers 1.0 only at the seat itself.
    """
    from src.systems.celestial_dao_service import _identity_anchor_impact

    sect, seat = anchored
    institution_id = _institution_id(base_world, sect.id)
    assert _identity_anchor_impact(base_world, institution_id, seat.id) == 0.0

    establish_genesis_identity_anchors(base_world)

    assert _identity_anchor_impact(base_world, institution_id, seat.id) == 1.0
    # Elsewhere, and for another institution, it stays zero.
    assert _identity_anchor_impact(base_world, institution_id, 999) == 0.0
    assert _identity_anchor_impact(base_world, "inst:dynasty:1", seat.id) == 0.0


@pytest.mark.asyncio
async def test_a_real_sponsorship_at_the_seat_weighs_the_anchor(
    base_world, anchored
):
    """The whole point: the real owner path now records a non-zero factor.

    Not the reader in isolation -- `record_dao_rite_sponsorship` itself, whose
    `identity_anchor_impact` was structurally zero in every world because no
    engine ever produced an anchor.
    """
    from src.classes.event import Event
    from src.classes.sect_ranks import SectRank
    from src.systems.celestial_dao_service import record_dao_rite_sponsorship
    from src.systems.institution_bootstrap import (
        synchronize_institutional_authority,
    )
    from tests.test_sponsor_dao_rite_authorship import (
        _decide_to_sponsor,
        _plain_avatar,
    )

    sect, seat = anchored
    establish_genesis_identity_anchors(base_world)
    institution_id = _institution_id(base_world, sect.id)

    # A living patriarch standing at the seat, so the sect really can sponsor.
    patriarch = _plain_avatar(base_world, "Patriarch")
    patriarch.tile.region = seat
    patriarch.join_sect(sect, SectRank.Patriarch)
    synchronize_institutional_authority(base_world)

    rite = Event(
        base_world.month_stamp,
        "A popular rite",
        event_type="dao_rite",
        causal_payload={"dao_rite": {"is_popular": True, "region_id": seat.id}},
    )
    base_world.event_manager.add_event(rite)
    decision = _decide_to_sponsor(base_world, patriarch, rite.id)
    assert decision is not None

    # Through the real action lifecycle, not only the owner: the engine
    # installs `action_origin` after `start`, which is what authorship needs.
    from tests.test_sponsor_dao_rite_authorship import _run_committed_action

    events = await _run_committed_action(patriarch)
    sponsorships = [
        item
        for item in events
        if (item.causal_payload or {}).get("dao_rite", {}).get("is_sponsorship")
    ]
    assert sponsorships, "the real action lifecycle produced no sponsorship"
    memory = next(
        item
        for item in base_world.institutional_relations.memories_for(institution_id)
        if item.event_id == sponsorships[0].id
    )
    # The dormant factor is awake, and only because a real anchor exists.
    assert dict(memory.factors)["identity_anchor_impact"] == 1.0

    # The owner path agrees, and refuses a second sponsorship of the same rite.
    from src.classes.action_runtime import ActionOrigin

    assert record_dao_rite_sponsorship(
        base_world, patriarch, rite.id, action_origin=ActionOrigin.ACTOR_CHOICE
    ) is None


def test_the_anchor_premise_is_reachable_from_the_state(base_world, anchored):
    """Navigable: institution -> anchor -> its own persisted premise fact."""
    sect, _seat_region = anchored
    establish_genesis_identity_anchors(base_world)
    institution_id = _institution_id(base_world, sect.id)

    anchors = [
        anchor
        for anchor in _anchors(base_world).values()
        if anchor.institution_id == institution_id
    ]
    assert len(anchors) == 1
    premise_ids = anchors[0].evidence_event_ids
    assert premise_ids
    for event_id in premise_ids:
        premise = base_world.event_manager.get_event_by_id(event_id)
        assert premise is not None
        assert premise.event_type == ANCHOR_EVENT_TYPE
        assert premise.render_params["anchor_id"] == anchors[0].id
