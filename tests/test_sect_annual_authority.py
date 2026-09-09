"""Annual sect treasury actions must select an actually offered public option."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.institution import AuthorityScope
from src.classes.items.magic_stone import MagicStone
from src.classes.root import Root
from src.classes.sect_decider import SectDecider
from src.classes.sect_ranks import SectRank
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.sect_decision_context import SectDecisionContext
from src.systems.single_choice.models import ChoiceSource, SingleChoiceDecision
from src.systems.single_choice.sect_recruitment import SectRecruitmentOutcome
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, avatar_id: str, name: str) -> Avatar:
    avatar = Avatar(world=world, name=name, id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement), gender=Gender.MALE, pos_x=0, pos_y=0,
        root=Root.GOLD, personas=[], alignment=Alignment.RIGHTEOUS)
    avatar.personas = []
    avatar.weapon = avatar.technique = None
    avatar.magic_stone = MagicStone(0)
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _context(candidate: Avatar) -> SectDecisionContext:
    return SectDecisionContext(basic_structured={}, basic_text="", power={}, territory={},
        self_assessment={}, economy={}, relations=[], relations_summary="", history={},
        recruitment_candidates=[{"avatar_id": candidate.id, "name": candidate.name,
            "alignment_recruitable": True, "race_recruitable": True}], member_candidates=[])


@pytest.fixture
def annual(base_world):
    sect = Sect(id=1, name="Test Sect", desc="", member_act_style="",
        alignment=Alignment.RIGHTEOUS, headquarter=SectHeadQuarter(name="HQ", desc="", image=Path("")),
        technique_names=[], magic_stone=5000)
    patriarch = _avatar(base_world, "patriarch", "Patriarch")
    patriarch.join_sect(sect, SectRank.Patriarch)
    candidate = _avatar(base_world, "candidate", "Candidate")
    base_world.existed_sects = [sect]
    base_world.sect_context.from_existed_sects(base_world.existed_sects)
    bootstrap_institutional_authority(base_world)
    return sect, patriarch, candidate


def _select(action: str, avatar_id: str):
    """Select only an option the public API composed for this very round."""
    async def llm_call(_task, _template, context, **_kwargs):
        option = next(item for item in context["affordances"]
            if item["action_kind"] == action and item["parameters"].get("avatar_id") == avatar_id)
        return {"decision": "act", "reason": "focused public API test", "selected_affordance_id": option["id"]}
    return llm_call


def _accepting():
    return patch("src.classes.sect_decider.resolve_sect_recruitment", new=AsyncMock(
        return_value=SectRecruitmentOutcome(
            decision=SingleChoiceDecision("ACCEPT", "accept", ChoiceSource.LLM, None, False),
            result_text="accepted", accepted=True, sect_id=1, avatar_id="candidate")))


def _kill_the_holder(world) -> None:
    office = next(item for item in world.institutional_authority.offices.values()
        if item.holder_ref is not None and str(item.holder_ref.id) == "patriarch")
    world.avatar_manager.get_avatar(str(office.holder_ref.id)).is_dead = True


@pytest.mark.asyncio
async def test_authorized_sect_recruits_with_real_deltas(base_world, annual):
    sect, _patriarch, candidate = annual
    before = int(sect.magic_stone)
    with _accepting():
        result = await SectDecider.decide(sect, _context(candidate), base_world,
            llm_call=_select("sect_annual_recruit", candidate.id))
    assert result.recruitment_count == 1 and candidate.sect is sect
    recruit_event = next(event for event in result.events if any(
        delta.get("aspect") == "sect_membership" for delta in (event.causal_payload or {}).get("deltas", [])))
    deltas = {(delta["owner_kind"], delta["aspect"]): delta for delta in recruit_event.causal_payload["deltas"]}
    assert set(deltas) == {("sect", "magic_stone"), ("avatar", "sect_membership")}
    assert float(deltas[("sect", "magic_stone")]["before"]) == before
    assert float(deltas[("sect", "magic_stone")]["after"]) == float(sect.magic_stone)
    assert result.decision_event.id in {link.cause_event_id for link in recruit_event.causal_links}


@pytest.mark.asyncio
async def test_maintain_selects_nobody_and_spends_nothing(base_world, annual):
    sect, patriarch, candidate = annual
    before = int(sect.magic_stone), int(patriarch.magic_stone.value)
    resolver = AsyncMock(side_effect=AssertionError("resolved without selection"))
    with patch("src.classes.sect_decider.resolve_sect_recruitment", new=resolver):
        result = await SectDecider.decide(sect, _context(candidate), base_world,
            injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "No annual action."))
    resolver.assert_not_awaited()
    assert (result.recruitment_count, result.support_count) == (0, 0)
    assert candidate.sect is None and (int(sect.magic_stone), int(patriarch.magic_stone.value)) == before
    assert result.decision_event.causal_payload["decision"]["chosen_chain"] == []


@pytest.mark.asyncio
async def test_no_treasury_scope_offers_no_spend(base_world, annual):
    sect, _patriarch, candidate = annual
    for key, office in list(base_world.institutional_authority.offices.items()):
        base_world.institutional_authority.offices[key] = replace(office, scopes=tuple(
            scope for scope in office.scopes if scope is not AuthorityScope.TREASURY_DISPOSITION))
    before = int(sect.magic_stone)
    result = await SectDecider.decide(sect, _context(candidate), base_world,
        injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "No offered treasury action."))
    assert result.recruitment_count == result.support_count == 0
    assert candidate.sect is None and int(sect.magic_stone) == before


@pytest.mark.asyncio
async def test_authority_lost_during_recruitment_blocks_join(base_world, annual):
    sect, _patriarch, candidate = annual
    before = int(sect.magic_stone)
    async def accept_then_lose_authority(*_args, **_kwargs):
        _kill_the_holder(base_world)
        return SectRecruitmentOutcome(
            decision=SingleChoiceDecision("ACCEPT", "accept", ChoiceSource.LLM, None, False),
            result_text="accepted", accepted=True, sect_id=int(sect.id), avatar_id=candidate.id)
    with patch("src.classes.sect_decider.resolve_sect_recruitment", new=accept_then_lose_authority):
        result = await SectDecider.decide(sect, _context(candidate), base_world,
            llm_call=_select("sect_annual_recruit", candidate.id))
    assert result.recruitment_count == 0 and candidate.sect is None and int(sect.magic_stone) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ("authority", "joined", "race", "funds"))
async def test_accepted_recruitment_revalidates_every_mutated_owner(base_world, annual, change):
    """An acceptance never carries stale authority, membership, race, or funds past its await."""
    sect, _patriarch, candidate = annual
    before = int(sect.magic_stone)
    async def accept_then_change(request):
        if change == "authority":
            _kill_the_holder(base_world)
        elif change == "joined":
            other = Sect(2, "Other", "", "", Alignment.RIGHTEOUS,
                SectHeadQuarter("HQ", "", Path()), [])
            candidate.join_sect(other, SectRank.OuterDisciple)
        elif change == "race":
            object.__setattr__(sect, "accepts_avatar_race", lambda avatar: avatar is not candidate)
        else:
            sect.magic_stone = 0
        return SectRecruitmentOutcome(
            decision=SingleChoiceDecision("ACCEPT", "accept", ChoiceSource.LLM, None, False),
            result_text="accepted", accepted=True, sect_id=int(sect.id), avatar_id=candidate.id)
    with patch("src.classes.sect_decider.resolve_sect_recruitment", new=AsyncMock(side_effect=accept_then_change)) as resolver:
        result = await SectDecider.decide(sect, _context(candidate), base_world,
            llm_call=_select("sect_annual_recruit", candidate.id))
    resolver.assert_awaited_once()
    assert result.recruitment_count == 0
    assert candidate.sect is not sect
    assert int(sect.magic_stone) == (0 if change == "funds" else before)
    assert not [event for event in result.events if any(delta.get("aspect") == "sect_membership" for delta in (event.causal_payload or {}).get("deltas", []))]
