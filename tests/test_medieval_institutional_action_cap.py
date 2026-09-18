"""Explicit per-institution monthly consultation ceiling, on top of the
existing shared daily budget. 0 (the default) is a strict no-op."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.institutional_decision_turn import _rotated_polities

ACTOR = EntityRef("polity", "auren")
OTHER = EntityRef("polity", "valedouro")
CHOICES = [{"id": "opt:1", "label": "Fazer algo."}]


def enable(world, *, cap=0, per_step=8, maximum=1000):
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": per_step, "ai_max_calls": maximum,
        "institutional_actions_per_month": cap})
    return world


def provider(monkeypatch, answer):
    async def call_llm_json(prompt, *args, **kwargs):
        return answer
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def test_zero_cap_is_a_strict_no_op():
    world = enable(create_medieval_world(73), cap=0)
    assert ai_decider.actor_within_monthly_cap(world, ACTOR)
    for _ in range(50):
        assert ai_decider.actor_within_monthly_cap(world, ACTOR)


async def test_cap_blocks_the_actor_only_after_it_is_spent_and_records_a_distinct_failure(monkeypatch):
    world = enable(create_medieval_world(73), cap=2)
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})

    for _ in range(2):
        assert ai_decider.actor_within_monthly_cap(world, ACTOR)
        selected = await ai_decider.select_option(world, ACTOR, {}, CHOICES)
        assert selected == ai_decider.NO_ACTION

    assert not ai_decider.actor_within_monthly_cap(world, ACTOR)
    before = len(world.events)
    selected = await ai_decider.select_option(world, ACTOR, {}, CHOICES)
    assert selected is None
    receipt = world.events[-1]
    assert len(world.events) == before + 1
    assert receipt.event_type == ai_decider.FAILED_EVENT
    assert "teto mensal" in receipt.content


async def test_cap_is_scoped_per_actor_and_per_month(monkeypatch):
    world = enable(create_medieval_world(73), cap=1)
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})

    await ai_decider.select_option(world, ACTOR, {}, CHOICES)
    assert not ai_decider.actor_within_monthly_cap(world, ACTOR)
    # A different actor has its own, independent ceiling this same month.
    assert ai_decider.actor_within_monthly_cap(world, OTHER)

    # A later month resets the ceiling for the original actor.
    world.clock = world.clock.advance(30)
    assert ai_decider.actor_within_monthly_cap(world, ACTOR)


def test_consultable_reflects_the_monthly_ceiling(monkeypatch):
    world = enable(create_medieval_world(73), cap=1)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    assert ai_decider.consultable(world, ACTOR)
    world.config = world.config.model_copy(
        update={"institutional_actions_consumed": {f"polity:auren:{world.clock.absolute_day // 30}": 1}})
    assert not ai_decider.consultable(world, ACTOR)
    assert ai_decider.consultable(world, OTHER)


def test_rotated_polities_starts_a_different_actor_each_month():
    world = create_medieval_world(73)
    identities = sorted(world.society.polities)
    assert list(_rotated_polities(world)) == identities

    world.clock = world.clock.advance(30)
    rotated = _rotated_polities(world)
    assert list(rotated) != identities
    assert sorted(rotated) == identities
    assert set(rotated) == set(identities)
