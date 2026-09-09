"""The smoke's anchor auditor must reject what it is there to catch.

A green audit has to mean something: a missing evidence event, a Story fact, a
mismatched field, a broken delta or an anchor that quietly disappeared after
genesis all have to be findings, not silence. Zero anchors is a valid starting
result; losing one is not.
"""

from __future__ import annotations

import pytest

from src.classes.institution import (
    IdentityAnchorKind,
    InstitutionalIdentityAnchor,
)
from src.classes.mechanical_language import EntityRef
from src.systems.institution_bootstrap import (
    bootstrap_institutional_authority,
    establish_genesis_identity_anchors,
)
from tools.institutional_smoke import audit_identity_anchors
from tests.test_institution_identity_anchor import anchored  # noqa: F401


def _reasons(report: dict) -> set[str]:
    return {violation["reason"] for violation in report["violations"]}


def _only_anchor(world):
    return next(iter(world.institutional_authority.identity_anchors.values()))


def test_a_real_genesis_world_audits_clean(base_world, anchored):  # noqa: F811
    establish_genesis_identity_anchors(base_world)

    report = audit_identity_anchors(base_world, stage="genesis")

    assert report["anchor_count"] == 1
    assert report["violations"] == []
    assert report["anchor_ids"] == [_only_anchor(base_world).id]


def test_no_declared_seat_is_a_clean_zero(base_world):
    """A config that declares nothing is not a failure."""
    from src.classes.core.dynasty import Dynasty

    base_world.dynasty = Dynasty(1, "Test", "", current_emperor_id=None)
    bootstrap_institutional_authority(base_world)

    assert establish_genesis_identity_anchors(base_world) == []
    report = audit_identity_anchors(base_world, stage="genesis")
    assert report["anchor_count"] == 0
    assert report["violations"] == []


def test_an_anchor_lost_after_genesis_is_a_violation(base_world, anchored):  # noqa: F811
    """The case a naive auditor would call clean."""
    establish_genesis_identity_anchors(base_world)
    genesis = audit_identity_anchors(base_world, stage="genesis")
    expected = genesis["anchor_ids"]

    base_world.institutional_authority.identity_anchors.clear()

    report = audit_identity_anchors(
        base_world, stage="month:5", expected_anchor_ids=expected
    )
    assert report["anchor_count"] == 0
    assert _reasons(report) == {"anchor_lost"}
    # The finding carries its stage, so the evidence is usable.
    assert report["violations"][0]["stage"] == "month:5"
    assert report["violations"][0]["anchor_id"] == expected[0]


@pytest.mark.parametrize(
    "corrupt,reason",
    (
        pytest.param(
            lambda world, event: setattr(event, "is_story", True),
            "story_evidence",
            id="story-evidence",
        ),
        pytest.param(
            lambda world, event: setattr(event, "event_type", "something_else"),
            "wrong_event_type",
            id="wrong-type",
        ),
        pytest.param(
            lambda world, event: event.render_params.update({"anchor_id": "other"}),
            "anchor_id_mismatch",
            id="anchor-id-mismatch",
        ),
        pytest.param(
            lambda world, event: event.render_params.update({"region_id": "999"}),
            "region_mismatch",
            id="region-mismatch",
        ),
        pytest.param(
            lambda world, event: event.render_params.update({"premise": "invented"}),
            "premise_mismatch",
            id="premise-mismatch",
        ),
        pytest.param(
            lambda world, event: event.render_params.update(
                {"anchor_kind": "sacred_site"}
            ),
            "anchor_kind_mismatch",
            id="anchor-kind-mismatch",
        ),
        pytest.param(
            lambda world, event: event.causal_payload["deltas"].clear(),
            "delta_missing_or_ambiguous",
            id="delta-missing",
        ),
        pytest.param(
            lambda world, event: event.causal_payload["deltas"][0].update(
                {"event_id": "another-event"}
            ),
            "delta_cites_another_event",
            id="delta-cites-another",
        ),
        pytest.param(
            lambda world, event: event.causal_payload["deltas"][0].update(
                {"after": "removed"}
            ),
            "delta_after_not_established",
            id="delta-after-wrong",
        ),
    ),
)
def test_the_auditor_rejects_broken_evidence(
    base_world, anchored, corrupt, reason  # noqa: F811
):
    produced = establish_genesis_identity_anchors(base_world)
    assert audit_identity_anchors(base_world)["violations"] == []
    # Corrupt the stored fact the anchor cites, in place.
    stored = base_world.event_manager.get_event_by_id(produced[0].id)
    assert stored is not None
    corrupt(base_world, stored)

    report = audit_identity_anchors(base_world, stage="month:1")

    assert reason in _reasons(report)
    assert all(item["stage"] == "month:1" for item in report["violations"])


def test_evidence_the_store_never_held_is_a_violation(base_world, anchored):  # noqa: F811
    """The guarantee that matters most: an anchor citing nothing real."""
    from dataclasses import replace

    establish_genesis_identity_anchors(base_world)
    anchor = _only_anchor(base_world)
    # The same anchor, pointed at evidence the store never received.
    state = base_world.institutional_authority
    state.identity_anchors[anchor.id] = replace(
        anchor, evidence_event_ids=("never-stored",)
    )

    report = audit_identity_anchors(base_world, stage="genesis")

    assert _reasons(report) == {"missing_evidence"}
    assert report["violations"][0]["event_id"] == "never-stored"
    assert report["violations"][0]["anchor_id"] == anchor.id


def test_a_non_region_subject_is_a_violation(base_world, anchored):  # noqa: F811
    """The genesis contract is a headquarters region, and only that."""
    sect, _seat = anchored
    establish_genesis_identity_anchors(base_world)
    anchor = _only_anchor(base_world)
    # A founder anchor is a valid model object and an invalid genesis product.
    base_world.institutional_authority.add_identity_anchor(
        InstitutionalIdentityAnchor(
            institution_id=anchor.institution_id,
            kind=IdentityAnchorKind.FOUNDER,
            subject=EntityRef("avatar", "someone"),
            established_month=int(base_world.month_stamp),
            evidence_event_ids=(anchor.evidence_event_ids[0],),
        )
    )

    report = audit_identity_anchors(base_world, stage="genesis")

    assert "subject_is_not_a_region" in _reasons(report)
