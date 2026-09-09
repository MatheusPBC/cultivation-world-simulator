"""Public annual SectDecider contracts for member administration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.classes.alignment import Alignment
from src.classes.core.dynasty import Dynasty
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.institution import AuthorityScope, InstitutionalAuthorityState, InstitutionKind
from src.classes.sect_decider import SectDecider
from src.classes.sect_ranks import SectRank, get_rank_from_realm
from src.classes.technique import Technique, TechniqueAttribute, TechniqueGrade, techniques_by_name
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from tests.test_sect_member_administration_rollback import _avatar, _member_context


def _sect_with_members(world):
    sect = Sect(7, "Admin Sect", "", "", Alignment.RIGHTEOUS,
        SectHeadQuarter("HQ", "", Path()), ["Upper"], rule_id="righteous_orthodoxy")
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


def _select(action: str, avatar_id: str, *, before=None):
    async def llm_call(_task, _template, context, **_kwargs):
        option = next(item for item in context["affordances"]
            if item["action_kind"] == action and item["parameters"].get("avatar_id") == avatar_id)
        if before is not None:
            before()
        return {"decision": "act", "reason": "focused public API test", "selected_affordance_id": option["id"]}
    return llm_call


def _register(technique):
    previous = techniques_by_name.get(technique.name)
    techniques_by_name[technique.name] = technique
    return previous


def _restore(technique, previous):
    if previous is None:
        techniques_by_name.pop(technique.name, None)
    else:
        techniques_by_name[technique.name] = previous


@pytest.mark.asyncio
async def test_maintain_never_expels_or_rewards(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(71, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = _register(reward)
    try:
        technique_before = patriarch.technique
        result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world,
            injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "No administration action."))
        assert result.expulsion_count == result.technique_reward_count == 0
        assert breaker.sect is sect and patriarch.technique is technique_before
        assert not [event for event in result.events if any(delta["aspect"] == "technique" for delta in (event.causal_payload or {}).get("deltas", []))]
    finally:
        _restore(reward, previous)


@pytest.mark.asyncio
async def test_administration_scope_is_independent_from_treasury(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(70, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = _register(reward)
    try:
        for key, office in list(base_world.institutional_authority.offices.items()):
            base_world.institutional_authority.offices[key] = replace(office, scopes=(AuthorityScope.SECT_ADMINISTRATION,))
        expulsion = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world,
            llm_call=_select("sect_annual_expel", breaker.id))
        reward_result = await SectDecider.decide(sect, _member_context(patriarch), base_world,
            llm_call=_select("sect_annual_reward", patriarch.id))
        assert (expulsion.expulsion_count, reward_result.technique_reward_count) == (1, 1)
        assert breaker.sect is None and patriarch.technique is reward
    finally:
        _restore(reward, previous)


@pytest.mark.asyncio
async def test_treasury_and_recognition_scopes_do_not_administer_members(base_world):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(72, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = _register(reward)
    technique_before = patriarch.technique
    try:
        for key, office in list(base_world.institutional_authority.offices.items()):
            base_world.institutional_authority.offices[key] = replace(office, scopes=(AuthorityScope.TREASURY_DISPOSITION, AuthorityScope.RECOGNITION))
        result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world,
            injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "No administration option was offered."))
        assert result.expulsion_count == result.technique_reward_count == 0
        assert breaker.sect is sect and patriarch.technique is technique_before
    finally:
        _restore(reward, previous)


@pytest.mark.asyncio
@pytest.mark.parametrize("authority_loss", ("scope", "holder"))
async def test_authority_lost_after_option_composition_blocks_member_mutation(base_world, authority_loss):
    sect, patriarch, breaker = _sect_with_members(base_world)
    reward = Technique(73, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    previous = _register(reward)
    technique_before = patriarch.technique
    def lose_authority():
        if authority_loss == "scope":
            for key, office in list(base_world.institutional_authority.offices.items()):
                base_world.institutional_authority.offices[key] = replace(office, scopes=tuple(scope for scope in office.scopes if scope is not AuthorityScope.SECT_ADMINISTRATION))
        else:
            patriarch.is_dead = True
    try:
        result = await SectDecider.decide(sect, _member_context(patriarch, breaker), base_world,
            llm_call=_select("sect_annual_expel", breaker.id, before=lose_authority))
        assert result.expulsion_count == 0 and breaker.sect is sect and patriarch.technique is technique_before
    finally:
        _restore(reward, previous)


@pytest.mark.asyncio
async def test_current_best_technique_selected_is_a_deterministic_noop(base_world):
    sect, patriarch, _ = _sect_with_members(base_world)
    current = Technique(5, "Current", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "")
    tied = Technique(6, "Tied", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "")
    patriarch.technique = current
    sect.technique_names = [tied.name]
    previous = _register(tied)
    try:
        assert SectDecider._pick_reward_technique(sect, patriarch) is None
        # There is no reward affordance, so a maintain decision is the only valid public selection.
        result = await SectDecider.decide(sect, _member_context(patriarch), base_world,
            injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "Already holds the best technique."))
        assert result.technique_reward_count == 0 and patriarch.technique is current
    finally:
        _restore(tied, previous)


def test_administration_scope_round_trips_without_granting_it_to_dynasty(base_world):
    sect, patriarch, _ = _sect_with_members(base_world)
    base_world.dynasty = Dynasty(11, "Dynasty", "", current_emperor_id=patriarch.id)
    state = bootstrap_institutional_authority(base_world)
    restored = InstitutionalAuthorityState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()
    sect_scopes = [office.scopes for office in restored.offices.values() if restored.institutions[office.institution_id].kind is InstitutionKind.SECT]
    dynasty_scopes = [office.scopes for office in restored.offices.values() if restored.institutions[office.institution_id].kind is InstitutionKind.DYNASTY]
    assert any(AuthorityScope.SECT_ADMINISTRATION in scopes for scopes in sect_scopes)
    assert all(AuthorityScope.SECT_ADMINISTRATION not in scopes for scopes in dynasty_scopes)
