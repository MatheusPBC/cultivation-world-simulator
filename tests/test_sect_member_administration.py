"""Focused authority and no-op contracts for annual sect administration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.alignment import Alignment
from src.classes.core.dynasty import Dynasty
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.institution import (
    AuthorityScope,
    InstitutionalAuthorityState,
    InstitutionKind,
)
from src.classes.sect_decider import SectDecider, SectDecisionPlan
from src.classes.sect_ranks import SectRank, get_rank_from_realm
from src.classes.technique import Technique, TechniqueAttribute, TechniqueGrade, techniques_by_name
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.test_sect_member_administration_rollback import _avatar, _member_context


def _sect_with_members(world):
    sect = Sect(7, "Admin Sect", "", "", Alignment.RIGHTEOUS, SectHeadQuarter("HQ", "", Path()), ["Upper"], rule_id="righteous_orthodoxy")
    patriarch = _avatar(world, avatar_id="patriarch", name="Patriarch", alignment=Alignment.RIGHTEOUS)
    breaker = _avatar(world, avatar_id="breaker", name="Breaker", alignment=Alignment.EVIL)
    patriarch.join_sect(sect, SectRank.Patriarch)
    breaker.join_sect(sect, get_rank_from_realm(breaker.cultivation_progress.realm))
    world.avatar_manager.register_avatar(patriarch)
    world.avatar_manager.register_avatar(breaker)
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects([sect])
    bootstrap_institutional_authority(world)
    return sect, patriarch, breaker


@pytest.mark.asyncio
async def test_no_plan_never_expels_or_rewards(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    technique_before = patriarch.technique
    reward = Technique(71, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    try:
        with patch.object(SectDecider, "_plan", new=AsyncMock(return_value=None)):
            result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world)
        assert result.expulsion_count == result.technique_reward_count == 0
        assert breaker.sect is sect
        assert patriarch.technique is technique_before
        assert not [
            event
            for event in result.events
            if any(
                delta["aspect"] == "technique"
                for delta in (event.causal_payload or {}).get("deltas", [])
            )
        ]
    finally:
        if previous is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = previous


@pytest.mark.asyncio
async def test_administration_scope_is_independent_from_treasury(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    state = base_world.institutional_authority
    reward = Technique(70, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    plan = SectDecisionPlan(expel_avatar_ids=[breaker.id], reward_avatar_ids=[patriarch.id])
    try:
        for key, office in list(state.offices.items()):
            state.offices[key] = replace(office, scopes=(AuthorityScope.SECT_ADMINISTRATION,))
        with patch.object(SectDecider, "_plan", new=AsyncMock(return_value=plan)):
            result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world)
        assert (result.expulsion_count, result.technique_reward_count) == (1, 1)
        assert breaker.sect is None and patriarch.technique is reward
    finally:
        if previous is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = previous


@pytest.mark.asyncio
async def test_treasury_and_recognition_scopes_do_not_administer_members(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(72, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    plan = SectDecisionPlan(
        expel_avatar_ids=[breaker.id], reward_avatar_ids=[patriarch.id], support_avatar_ids=[]
    )
    technique_before = patriarch.technique
    try:
        for key, office in list(base_world.institutional_authority.offices.items()):
            base_world.institutional_authority.offices[key] = replace(
                office,
                scopes=(AuthorityScope.TREASURY_DISPOSITION, AuthorityScope.RECOGNITION),
            )
        with patch.object(SectDecider, "_plan", new=AsyncMock(return_value=plan)):
            result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world)
        assert result.expulsion_count == result.technique_reward_count == 0
        assert breaker.sect is sect and patriarch.technique is technique_before
    finally:
        if previous is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = previous


@pytest.mark.asyncio
@pytest.mark.parametrize("authority_loss", ("scope", "holder"))
async def test_authority_lost_while_planning_blocks_member_mutations(
    base_world, authority_loss
):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(73, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    plan = SectDecisionPlan(
        expel_avatar_ids=[breaker.id], reward_avatar_ids=[patriarch.id], support_avatar_ids=[]
    )
    technique_before = patriarch.technique

    async def plan_after_authority_loss(*_args, **_kwargs):
        if authority_loss == "scope":
            for key, office in list(base_world.institutional_authority.offices.items()):
                base_world.institutional_authority.offices[key] = replace(
                    office,
                    scopes=tuple(
                        scope
                        for scope in office.scopes
                        if scope is not AuthorityScope.SECT_ADMINISTRATION
                    ),
                )
        else:
            patriarch.is_dead = True
        return plan

    try:
        with patch.object(SectDecider, "_plan", new=AsyncMock(side_effect=plan_after_authority_loss)):
            result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world)
        assert result.expulsion_count == result.technique_reward_count == 0
        assert breaker.sect is sect and patriarch.technique is technique_before
    finally:
        if previous is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = previous


@pytest.mark.asyncio
async def test_stale_membership_at_the_administration_gate_is_not_mutated(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)

    def stale_rule_read(avatar):
        if avatar is breaker:
            breaker.leave_sect()
            return True
        return False

    with (
        patch.object(
            SectDecider,
            "_plan",
            new=AsyncMock(
                return_value=SectDecisionPlan(
                    expel_avatar_ids=[breaker.id], support_avatar_ids=[]
                )
            ),
        ),
        patch.object(sect, "is_member_rule_breaker", side_effect=stale_rule_read),
    ):
        result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world)

    assert result.expulsion_count == 0
    assert not [event for event in result.events if event.fact_kind.value == "state_transition"]


@pytest.mark.asyncio
async def test_current_best_technique_is_a_deterministic_noop(base_world):
    sect, patriarch, _ = _sect_with_members(base_world)
    current = Technique(5, "Current", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "")
    tied = Technique(6, "Tied", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "")
    patriarch.technique = current
    sect.technique_names = [tied.name]
    previous = techniques_by_name.get(tied.name)
    techniques_by_name[tied.name] = tied
    try:
        assert SectDecider._pick_reward_technique(sect, patriarch) is None
        with patch.object(
            SectDecider,
            "_plan",
            new=AsyncMock(
                return_value=SectDecisionPlan(
                    reward_avatar_ids=[patriarch.id], support_avatar_ids=[]
                )
            ),
        ):
            result = await SectDecider.decide(sect, _member_context(patriarch), base_world)
        assert result.technique_reward_count == 0
        assert patriarch.technique is current
        assert not [
            event
            for event in result.events
            if any(
                delta["aspect"] == "technique"
                for delta in (event.causal_payload or {}).get("deltas", [])
            )
        ]
    finally:
        if previous is None:
            techniques_by_name.pop(tied.name, None)
        else:
            techniques_by_name[tied.name] = previous


def test_administration_scope_round_trips_without_granting_it_to_dynasty(base_world):
    sect, patriarch, _ = _sect_with_members(base_world)
    base_world.dynasty = Dynasty(11, "Dynasty", "", current_emperor_id=patriarch.id)
    state = bootstrap_institutional_authority(base_world)

    restored = InstitutionalAuthorityState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()

    sect_institution = next(
        institution
        for institution in restored.institutions.values()
        if institution.kind is InstitutionKind.SECT and institution.owner_ref.id == str(sect.id)
    )
    dynasty_institution = next(
        institution
        for institution in restored.institutions.values()
        if institution.kind is InstitutionKind.DYNASTY
    )
    sect_scopes = [
        office.scopes
        for office in restored.offices.values()
        if office.institution_id == sect_institution.id
    ]
    dynasty_scopes = [
        office.scopes
        for office in restored.offices.values()
        if office.institution_id == dynasty_institution.id
    ]
    assert any(AuthorityScope.SECT_ADMINISTRATION in scopes for scopes in sect_scopes)
    assert all(AuthorityScope.SECT_ADMINISTRATION not in scopes for scopes in dynasty_scopes)
