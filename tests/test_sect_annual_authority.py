"""The annual sect round spends only when the sect really can.

Recruiting and supporting both move `sect.magic_stone`, and neither asked
`can_actor_act_for` before. An unauthorized sect must not even be planned for:
no provider is consulted about a spend nobody could make, and the round still
leaves an honest audit record instead of a fabricated choice.

No material control is required: a treasury is not territorial.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.items.magic_stone import MagicStone
from src.classes.root import Root
from src.classes.sect_decider import SectDecider, SectDecisionPlan
from src.classes.sect_ranks import SectRank
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.sect_decision_context import SectDecisionContext
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, avatar_id: str, name: str) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.weapon = None
    avatar.technique = None
    avatar.magic_stone = MagicStone(0)
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _context(candidate: Avatar) -> SectDecisionContext:
    return SectDecisionContext(
        basic_structured={},
        basic_text="",
        power={},
        territory={},
        self_assessment={},
        economy={},
        relations=[],
        relations_summary="",
        history={},
        recruitment_candidates=[
            {
                "avatar_id": candidate.id,
                "name": candidate.name,
                "alignment_recruitable": True,
                "race_recruitable": True,
            }
        ],
        member_candidates=[],
    )


@pytest.fixture
def annual(base_world):
    """A sect with a living patriarch, a poor member, and one candidate."""
    base_world.run_config_snapshot = {"test_mode": True}
    sect = Sect(
        id=1, name="Test Sect", desc="", member_act_style="",
        alignment=Alignment.RIGHTEOUS,
        headquarter=SectHeadQuarter(name="HQ", desc="", image=Path("")),
        technique_names=[], magic_stone=5000,
    )
    patriarch = _avatar(base_world, "patriarch", "Patriarch")
    patriarch.join_sect(sect, SectRank.Patriarch)
    candidate = _avatar(base_world, "candidate", "Candidate")
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    bootstrap_institutional_authority(base_world)
    return sect, patriarch, candidate


def _accepting():
    return patch(
        "src.classes.sect_decider.resolve_sect_recruitment",
        new=AsyncMock(
            return_value=type(
                "Outcome", (), {"accepted": True, "result_text": "accepted"}
            )()
        ),
    )


def _recruit_only(candidate: Avatar):
    """An enumerated plan: recruit this one, support nobody.

    Isolates the recruitment path, so the treasury delta's `after` really is
    the balance and no later support muddies it.
    """
    return patch.object(
        SectDecider,
        "_plan",
        AsyncMock(
            return_value=SectDecisionPlan(
                recruit_avatar_ids=[candidate.id],
                expel_avatar_ids=[],
                reward_avatar_ids=[],
                support_avatar_ids=[],
            )
        ),
    )


def _kill_the_holder(world, sect) -> None:
    from src.systems.institutional_diplomacy import sect_institution_id

    institution_id = sect_institution_id(str(sect.id))
    office = next(
        item
        for item in world.institutional_authority.offices.values()
        if item.institution_id == institution_id and item.holder_ref is not None
    )
    world.avatar_manager.get_avatar(str(office.holder_ref.id)).is_dead = True


@pytest.mark.asyncio
async def test_an_authorized_sect_recruits_with_real_deltas(base_world, annual):
    """The baseline: the treasury really falls and the avatar really joins."""
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone)

    # This path tests the canonical mutation after a concrete selection.
    with _accepting(), _recruit_only(candidate):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    assert result.recruitment_count == 1
    assert candidate.sect is sect
    assert int(sect.magic_stone) < before
    recruit_event = next(
        event
        for event in result.events
        if any(
            delta.get("aspect") == "sect_membership"
            for delta in (event.causal_payload or {}).get("deltas", [])
        )
    )
    assert recruit_event.fact_kind.value == "state_transition"
    deltas = {
        (delta["owner_kind"], delta["aspect"]): delta
        for delta in recruit_event.causal_payload["deltas"]
    }
    assert set(deltas) == {("sect", "magic_stone"), ("avatar", "sect_membership")}
    treasury = deltas[("sect", "magic_stone")]
    assert float(treasury["magnitude"]) < 0
    assert float(treasury["before"]) - float(treasury["after"]) == -float(
        treasury["magnitude"]
    )
    membership = deltas[("avatar", "sect_membership")]
    assert (membership["before"], membership["after"]) == ("none", str(sect.id))
    assert membership["owner_id"] == str(candidate.id)
    # With support planned away, the recorded `after` really is the balance.
    assert float(treasury["after"]) == float(sect.magic_stone)
    # Cited to the round's own audited decision.
    assert {link.cause_event_id for link in recruit_event.causal_links} == {
        result.decision_event.id
    }
    # The round's audit really records the step it took.
    audit = result.decision_event.causal_payload["decision"]
    assert any("recruit" in str(step) for step in audit["chosen_chain"])


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_absence", ("unavailable", "failure", "malformed"))
async def test_absent_plan_selects_nobody_and_spends_nothing(
    base_world, annual, plan_absence
):
    """A live authority still needs a valid plan for every treasury action."""
    sect, patriarch, candidate = annual
    base_world.run_config_snapshot = {}
    before_sect = int(sect.magic_stone)
    before_member = int(patriarch.magic_stone.value)
    resolver = AsyncMock(side_effect=AssertionError("resolved without a plan"))
    provider = AsyncMock(
        side_effect=(
            RuntimeError("provider down")
            if plan_absence == "failure"
            else ["malformed"]
        )
    )

    with (
        patch.object(
            SectDecider, "_llm_available", return_value=plan_absence != "unavailable"
        ),
        patch("src.classes.sect_decider.call_llm_with_task_name", new=provider),
        patch("src.classes.sect_decider.resolve_sect_recruitment", new=resolver),
    ):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    resolver.assert_not_awaited()
    if plan_absence == "unavailable":
        provider.assert_not_awaited()
    else:
        provider.assert_awaited_once()
    assert result.recruitment_count == result.support_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before_sect
    assert int(patriarch.magic_stone.value) == before_member
    assert result.decision_event.causal_payload["decision"]["chosen_chain"] == []
    assert result.decision_event in result.events
    assert not [
        event
        for event in result.events
        if event.fact_kind.value == "state_transition"
        or (event.causal_payload or {}).get("deltas")
    ]


@pytest.mark.asyncio
async def test_a_sect_with_no_office_neither_plans_nor_spends(base_world, annual):
    """No holder, no provider call, no debit -- and still an audit record."""
    sect, patriarch, candidate = annual
    base_world.institutional_authority.offices.clear()
    before = int(sect.magic_stone)
    planner = AsyncMock(side_effect=AssertionError("planned an unauthorized round"))

    with patch.object(SectDecider, "_plan", planner), _accepting():
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    planner.assert_not_awaited()
    assert result.recruitment_count == 0
    assert result.support_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before
    # The round is still auditable, and claims no choice it did not make.
    assert result.decision_event is not None
    audit = result.decision_event.causal_payload["decision"]
    assert audit["subject_kind"] == "sect"
    assert audit["chosen_chain"] == []


@pytest.mark.asyncio
async def test_an_office_without_the_treasury_scope_cannot_spend(base_world, annual):
    """An office that exists but does not carry the scope authorizes nothing."""
    from dataclasses import replace

    from src.classes.institution import AuthorityScope

    sect, patriarch, candidate = annual
    state = base_world.institutional_authority
    for key, office in list(state.offices.items()):
        state.offices[key] = replace(
            office,
            scopes=tuple(
                scope
                for scope in office.scopes
                if scope is not AuthorityScope.TREASURY_DISPOSITION
            ),
        )
    before = int(sect.magic_stone)
    planner = AsyncMock(
        return_value=SectDecisionPlan(recruit_avatar_ids=[candidate.id])
    )

    with patch.object(SectDecider, "_plan", planner), _accepting():
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    planner.assert_awaited_once()
    assert result.recruitment_count == 0
    assert result.support_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_authority_lost_before_the_invitation_never_invites(base_world, annual):
    """Lost while planning: no candidate is even asked."""
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone)
    resolver = AsyncMock(side_effect=AssertionError("invited without authority"))

    async def plan_then_lose_authority(*_args, **_kwargs):
        _kill_the_holder(base_world, sect)
        return SectDecisionPlan(recruit_avatar_ids=[candidate.id])

    with patch.object(
        SectDecider, "_plan", plan_then_lose_authority
    ), patch("src.classes.sect_decider.resolve_sect_recruitment", new=resolver):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    resolver.assert_not_awaited()
    assert result.recruitment_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_authority_lost_during_recruitment_blocks_the_join(base_world, annual):
    """Lost between the invitation and the join: no debit, no membership."""
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone)

    async def accept_then_lose_authority(*_args, **_kwargs):
        _kill_the_holder(base_world, sect)
        return type("Outcome", (), {"accepted": True, "result_text": "accepted"})()

    with patch(
        "src.classes.sect_decider.resolve_sect_recruitment",
        new=accept_then_lose_authority,
    ), _recruit_only(candidate):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    assert result.recruitment_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before
    assert not [
        event
        for event in result.events
        if any(
            delta.get("aspect") == "sect_membership"
            for delta in (event.causal_payload or {}).get("deltas", [])
        )
    ]


@pytest.mark.asyncio
async def test_a_candidate_who_became_ineligible_during_the_await_is_refused(
    base_world, annual
):
    """`join_sect` refuses silently, so nothing may be debited for it."""
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone)

    async def accept_then_join_elsewhere(*_args, **_kwargs):
        other = Sect(
            id=2, name="Other", desc="", member_act_style="",
            alignment=Alignment.RIGHTEOUS,
            headquarter=SectHeadQuarter(name="HQ", desc="", image=Path("")),
            technique_names=[],
        )
        candidate.join_sect(other, SectRank.OuterDisciple)
        return type("Outcome", (), {"accepted": True, "result_text": "accepted"})()

    with patch(
        "src.classes.sect_decider.resolve_sect_recruitment",
        new=accept_then_join_elsewhere,
    ), _recruit_only(candidate):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    assert result.recruitment_count == 0
    assert candidate.sect is not sect
    assert int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_a_race_the_sect_stopped_accepting_debits_nothing(base_world, annual):
    """`join_sect` refuses a race silently; no coin may move for that."""
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone)

    async def accept_then_close_the_gate(*_args, **_kwargs):
        # The sect stops accepting this candidate's race mid-await.
        object.__setattr__(
            sect, "accepts_avatar_race", lambda avatar: avatar is not candidate
        )
        return type("Outcome", (), {"accepted": True, "result_text": "accepted"})()

    with patch(
        "src.classes.sect_decider.resolve_sect_recruitment",
        new=accept_then_close_the_gate,
    ), _recruit_only(candidate):
        result = await SectDecider.decide(sect, _context(candidate), base_world)

    assert result.recruitment_count == 0
    assert candidate.sect is None
    assert int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_support_is_refused_when_the_office_is_empty(base_world, annual):
    """Support spends too, and is gated at the mutation point."""
    sect, patriarch, candidate = annual
    poor = _avatar(base_world, "poor", "Poor Member")
    poor.join_sect(sect, SectRank.OuterDisciple)
    base_world.institutional_authority.offices.clear()
    before_sect = int(sect.magic_stone)
    before_member = int(poor.magic_stone.value)

    result = await SectDecider.decide(sect, _context(candidate), base_world)

    assert result.support_count == 0
    assert int(sect.magic_stone) == before_sect
    assert int(poor.magic_stone.value) == before_member
