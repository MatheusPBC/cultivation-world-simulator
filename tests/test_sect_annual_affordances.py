"""Focused public-contract tests for annual sect affordances."""

from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.causal_link import CausalRelation
from src.classes.domain_affordance import DomainDecisionKind
from src.classes.event import Event
from src.classes.items.magic_stone import MagicStone
from src.classes.mechanical_language import EntityRef
from src.classes.sect_decider import SectDecider
from src.classes.technique import (
    Technique,
    TechniqueAttribute,
    TechniqueGrade,
    techniques_by_name,
)
from src.sim.managers.event_manager import EventManager
from src.sim.simulator import Simulator
from src.sim.simulator_engine.phase_registry import SimulationPhase, annual_maintenance
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner
from src.systems.domain_affordance_registry import (
    AffordanceContext,
    DOMAIN_AFFORDANCES,
    StaleAffordanceError,
)
from src.systems.domain_decision_interpreter import interpret_domain_affordances
from src.systems.single_choice.models import ChoiceSource, SingleChoiceDecision
from src.systems.single_choice.sect_recruitment import SectRecruitmentOutcome
from src.systems.time import Month, Year, create_month_stamp
from src.utils.llm.exceptions import LLMError
from tests.test_sect_decider import _avatar, _ctx, _select, _setup


def _select_invented(*_args, **_kwargs):
    return {
        "decision": "act",
        "reason": "invented id must not become an action",
        "selected_affordance_id": "aff-not-offered",
    }


def _accepting(avatar_id: str) -> SectRecruitmentOutcome:
    return SectRecruitmentOutcome(
        decision=SingleChoiceDecision("ACCEPT", "accept", ChoiceSource.LLM, None, False),
        result_text="accepted",
        accepted=True,
        sect_id=1,
        avatar_id=avatar_id,
    )


@pytest.mark.asyncio
async def test_invented_annual_affordance_id_maintains_without_mutating(base_world):
    sect, patriarch, breaker, rogue = _setup(base_world)
    before = int(sect.magic_stone)

    result = await SectDecider.decide(
        sect, _ctx(patriarch, breaker, recruit=rogue), base_world, llm_call=_select_invented
    )

    assert rogue.sect is None
    assert int(sect.magic_stone) == before
    assert result.recruitment_count == result.expulsion_count == 0
    assert result.decision_event.causal_payload["interpretation"]["decision"] == "maintain"


@pytest.mark.asyncio
async def test_stale_reward_selection_after_llm_await_is_blocked(base_world):
    sect, patriarch, _breaker, _rogue = _setup(base_world)
    reward = Technique(100, "Annual Upper", TechniqueAttribute.GOLD, TechniqueGrade.UPPER, "", 1.0, "", sect_id=sect.id)
    current = Technique(99, "Annual Lower", TechniqueAttribute.GOLD, TechniqueGrade.LOWER, "", 1.0, "", sect_id=sect.id)
    replacement = Technique(98, "Changed During Await", TechniqueAttribute.GOLD, TechniqueGrade.MIDDLE, "", 1.0, "", sect_id=sect.id)
    prior = {item.name: techniques_by_name.get(item.name) for item in (reward, current, replacement)}
    techniques_by_name.update({item.name: item for item in (reward, current, replacement)})
    sect.technique_names = [reward.name]
    patriarch.technique = current

    async def select_then_change(_task, _template, context, **_kwargs):
        option = next(item for item in context["affordances"] if item["action_kind"] == "sect_annual_reward")
        patriarch.technique = replacement
        return {"decision": "act", "reason": "stale reward probe", "selected_affordance_id": option["id"]}

    try:
        result = await SectDecider.decide(sect, _ctx(patriarch), base_world, llm_call=select_then_change)
    finally:
        for name, old in prior.items():
            if old is None:
                techniques_by_name.pop(name, None)
            else:
                techniques_by_name[name] = old

    assert patriarch.technique is replacement
    assert result.technique_reward_count == 0
    assert any(event.event_type == "domain_affordance_blocked" for event in result.events)


@pytest.mark.asyncio
async def test_registered_executor_rejects_absent_or_other_option_decision(base_world):
    sect, _patriarch, breaker, rogue = _setup(base_world)
    trigger = Event(base_world.month_stamp, "annual trigger")
    context = AffordanceContext(base_world, "sect_annual", EntityRef("sect", str(sect.id)), trigger)
    options = DOMAIN_AFFORDANCES.compose(context)
    target = next(item for item in options if item.action_kind == "sect_annual_expel")
    other = next(item for item in options if item.id != target.id)

    with pytest.raises(StaleAffordanceError, match="decision is absent"):
        await DOMAIN_AFFORDANCES.execute_async(context, target.id, result=None, decision_event=None)

    async def choose_other(*_args, **_kwargs):
        return {
            "decision": DomainDecisionKind.ACT.value,
            "reason": "a different canonical option was selected",
            "selected_affordance_id": other.id,
        }

    _decision, decision_event = await interpret_domain_affordances(
        base_world,
        domain=context.domain,
        actor_ref=context.actor_ref,
        actor_label=sect.name,
        trigger_event=trigger,
        affordances=options,
        task_name="test",
        template_name="sect_annual_interpreter.txt",
        llm_call=choose_other,
    )
    with pytest.raises(StaleAffordanceError, match="decision is not canonical"):
        await DOMAIN_AFFORDANCES.execute_async(context, target.id, result=None, decision_event=decision_event)
    assert rogue.sect is None and breaker.sect is sect


@pytest.mark.asyncio
async def test_test_mode_isolated_and_provider_failure_maintains(base_world):
    sect, patriarch, breaker, rogue = _setup(base_world)
    breaker.alignment = patriarch.alignment
    patriarch.magic_stone = MagicStone(300)
    breaker.magic_stone = MagicStone(300)
    base_world.run_config_snapshot = {"test_mode": True}
    provider = AsyncMock(side_effect=AssertionError("provider called in test mode"))

    deterministic = await SectDecider.decide(sect, _ctx(patriarch, recruit=rogue), base_world, llm_call=provider)
    provider.assert_not_awaited()
    assert deterministic.decision_event.causal_payload["interpretation"]["decision"] == "maintain"

    base_world.run_config_snapshot = {}
    failed = await SectDecider.decide(
        sect, _ctx(patriarch, breaker, recruit=rogue), base_world,
        llm_call=AsyncMock(side_effect=LLMError("provider unavailable")),
    )
    assert failed.decision_event.causal_payload["interpretation"]["decision"] == "maintain"
    assert rogue.sect is None and breaker.sect is sect


@pytest.mark.asyncio
async def test_two_recruitments_keep_separate_decisions_and_material_links(base_world):
    sect, patriarch, breaker, rogue = _setup(base_world)
    second = _avatar(base_world, "second-rogue", patriarch.alignment)

    with patch("src.classes.sect_decider.resolve_sect_recruitment", new=AsyncMock(side_effect=[_accepting(rogue.id), _accepting(second.id)])):
        first = await SectDecider.decide(sect, _ctx(patriarch, breaker, recruit=rogue), base_world, llm_call=_select("sect_annual_recruit", rogue.id))
        second_result = await SectDecider.decide(sect, _ctx(patriarch, recruit=second), base_world, llm_call=_select("sect_annual_recruit", second.id))

    for result, avatar in ((first, rogue), (second_result, second)):
        material = next(event for event in result.events if any(delta.get("aspect") == "sect_membership" for delta in (event.causal_payload or {}).get("deltas", [])))
        causes = {link.cause_event_id for link in material.causal_links if link.relation is CausalRelation.MOTIVATED_BY}
        avatar_decision = next(
            event
            for event in result.events
            if event.fact_kind.value == "decision"
            and (event.causal_payload or {}).get("decision", {}).get("subject_id") == avatar.id
        )
        assert result.decision_event.id in causes
        assert avatar_decision.id in causes
        assert avatar.sect is sect
    assert first.decision_event.id != second_result.decision_event.id


@pytest.mark.asyncio
async def test_unexpected_executor_failure_after_mutation_rolls_back_annual_step(base_world, tmp_path):
    sect, _patriarch, breaker, rogue = _setup(base_world)
    base_world.month_stamp = create_month_stamp(Year(100), Month.JANUARY)
    base_world.start_year = 100
    base_world.event_manager = EventManager.create_with_db(tmp_path / "annual-events.db")
    treasury_before = sect.magic_stone
    month_before = base_world.month_stamp
    event_count_before = base_world.event_manager.count()
    random_before = random.getstate()
    original_decide = SectDecider.decide.__func__
    original_execute = SectDecider._execute_option.__func__

    async def decide_recruit(cls, chosen_sect, ctx, world, **_kwargs):
        return await original_decide(cls, chosen_sect, ctx, world, llm_call=_select("sect_annual_recruit", rogue.id))

    async def mutate_then_fail(cls, *args, **kwargs):
        await original_execute(cls, *args, **kwargs)
        assert rogue.sect is sect
        assert rogue.id in sect.members
        assert sect.magic_stone < treasury_before
        raise RuntimeError("unexpected failure after canonical mutation")

    phases = (SimulationPhase("annual_maintenance", 1, "annual_maintenance", annual_maintenance),)
    with (
        patch.object(SectDecider, "decide", classmethod(decide_recruit)),
        patch.object(SectDecider, "_execute_option", classmethod(mutate_then_fail)),
        patch("src.classes.sect_decider.resolve_sect_recruitment", new=AsyncMock(return_value=_accepting(rogue.id))),
    ):
        with pytest.raises(RuntimeError, match="after canonical mutation"):
            await SimulationPhaseRunner(Simulator(base_world), phases=phases).run()

    assert sect.magic_stone == treasury_before
    assert rogue.sect is None and rogue.id not in sect.members
    assert breaker.sect is sect
    assert base_world.event_manager.count() == event_count_before
    assert base_world.month_stamp == month_before
    assert random.getstate() == random_before
