"""Public annual sect decisions select one current, composed affordance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.sect import Sect, SectHeadQuarter
from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.items.magic_stone import MagicStone
from src.classes.root import Root
from src.classes.sect_decider import SectDecider
from src.classes.sect_ranks import SectRank, get_rank_from_realm
from src.classes.technique import Technique, TechniqueAttribute, TechniqueGrade, techniques_by_name
from src.systems.cultivation import Realm
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.sect_decision_context import SectDecisionContext
from src.systems.single_choice.models import ChoiceSource, SingleChoiceDecision
from src.systems.single_choice.sect_recruitment import SectRecruitmentOutcome
from src.systems.time import Month, Year, create_month_stamp


def _avatar(world, avatar_id, alignment):
    avatar = Avatar(world=world, name=avatar_id.title(), id=avatar_id,
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY), age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE, pos_x=0, pos_y=0, root=Root.GOLD, personas=[], alignment=alignment)
    avatar.personas = []
    avatar.weapon = avatar.technique = None
    avatar.magic_stone = MagicStone(0)
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _ctx(*members, recruit=None):
    return SectDecisionContext(basic_structured={}, basic_text="", power={}, territory={}, self_assessment={}, economy={},
        relations=[], relations_summary="", history={}, member_candidates=[{"avatar_id": item.id} for item in members],
        recruitment_candidates=[] if recruit is None else [{"avatar_id": recruit.id, "alignment_recruitable": True, "race_recruitable": True}])


def _select(action, avatar_id):
    async def llm_call(_task, _template, context, **_kwargs):
        option = next(item for item in context["affordances"] if item["action_kind"] == action and item["parameters"].get("avatar_id") == avatar_id)
        return {"decision": "act", "reason": "select a real current option", "selected_affordance_id": option["id"]}
    return llm_call


def _setup(world):
    sect = Sect(1, "Test Sect", "", "", Alignment.RIGHTEOUS, SectHeadQuarter("HQ", "", Path()), ["Upper"],
        rule_id="righteous_orthodoxy", magic_stone=1000)
    patriarch = _avatar(world, "patriarch", Alignment.RIGHTEOUS)
    breaker = _avatar(world, "breaker", Alignment.EVIL)
    rogue = _avatar(world, "rogue", Alignment.RIGHTEOUS)
    patriarch.join_sect(sect, SectRank.Patriarch)
    breaker.join_sect(sect, get_rank_from_realm(breaker.cultivation_progress.realm))
    world.existed_sects = [sect]
    world.sect_context.from_existed_sects([sect])
    bootstrap_institutional_authority(world)
    return sect, patriarch, breaker, rogue


def test_serializes_read_only_context_evidence():
    ctx = SectDecisionContext(basic_structured={}, basic_text="", power={}, territory={}, self_assessment={}, economy={},
        relations=[], relations_summary="", history={}, celestial_dao=[{"kind": "omen"}], regional_semantics=[{"region_id": 7}],
        imperial_crisis={"emperor": {"id": "e"}})
    serialized = SectDecider._serialize_context(ctx)
    assert serialized["celestial_dao"] == ctx.celestial_dao
    assert serialized["regional_semantics"] == ctx.regional_semantics
    assert serialized["imperial_crisis"] == ctx.imperial_crisis


@pytest.mark.asyncio
async def test_each_annual_action_is_a_separate_composed_public_selection(base_world):
    sect, patriarch, breaker, rogue = _setup(base_world)
    reward = Technique(100, "Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    old = techniques_by_name.get(reward.name)
    techniques_by_name[reward.name] = reward
    try:
        with patch("src.classes.sect_decider.resolve_sect_recruitment", new=AsyncMock(return_value=SectRecruitmentOutcome(
            decision=SingleChoiceDecision("ACCEPT", "accept", ChoiceSource.LLM, None, False),
            result_text="accepted", accepted=True, sect_id=int(sect.id), avatar_id=rogue.id))):
            recruited = await SectDecider.decide(sect, _ctx(patriarch, breaker, recruit=rogue), base_world, llm_call=_select("sect_annual_recruit", rogue.id))
        expelled = await SectDecider.decide(sect, _ctx(patriarch, breaker), base_world, llm_call=_select("sect_annual_expel", breaker.id))
        rewarded = await SectDecider.decide(sect, _ctx(patriarch), base_world, llm_call=_select("sect_annual_reward", patriarch.id))
        supported = await SectDecider.decide(sect, _ctx(patriarch), base_world, llm_call=_select("sect_annual_support", patriarch.id))
        assert (recruited.recruitment_count, expelled.expulsion_count, rewarded.technique_reward_count, supported.support_count) == (1, 1, 1, 1)
        assert rogue.sect is sect and breaker.sect is None and patriarch.technique is reward and patriarch.magic_stone.value == 300
        for result in (recruited, expelled, rewarded, supported):
            assert result.decision_event.causal_payload["decision"]["chosen_chain"]
    finally:
        if old is None:
            techniques_by_name.pop(reward.name, None)
        else:
            techniques_by_name[reward.name] = old


@pytest.mark.asyncio
async def test_explicit_maintain_is_a_real_audited_noop(base_world):
    sect, patriarch, breaker, rogue = _setup(base_world)
    result = await SectDecider.decide(sect, _ctx(patriarch, breaker, recruit=rogue), base_world,
        injected_decision=DomainDecision(DomainDecisionKind.MAINTAIN, "No action selected."))
    assert result.decision_event.causal_payload["decision"]["chosen_chain"] == []
    assert (result.recruitment_count, result.expulsion_count, result.technique_reward_count, result.support_count) == (0, 0, 0, 0)
