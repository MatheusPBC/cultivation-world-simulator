"""The composed daily turn: one consultation per actor over daily families.

Only recourse currently qualifies; the other daily verticals keep their own
owners and are deliberately not merged here.
"""

import json

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.institutional_agenda import daily_actors, review_daily_institutional_turn
from src.sim.medieval.recourse_policy import REVIEW_KIND, _turn, recourse_adapters, review_id
from tests.test_medieval_creature_autonomy import choose, provider
from tests.test_medieval_recourse import breached, observe, wronged_world


AUREN = EntityRef("polity", "auren")


def _provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def _world_with_due_review(monkeypatch, answer):
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    observe(world)
    prompts = []
    _provider(monkeypatch, answer, prompts)
    review = next((item for item in world.agenda.pop_due(world.clock.absolute_day + 1)
                   if item.kind == REVIEW_KIND), None)
    assert review is not None
    return world, review, prompts


async def test_a_scheduled_recourse_review_is_one_consultation_with_its_own_situation(monkeypatch):
    world, review, prompts = await _world_with_due_review(monkeypatch, ai_decider.NO_ACTION)

    claims, covered = await review_daily_institutional_turn(world, [review])

    assert covered == {AUREN} and claims == {}
    assert len(prompts) == 1
    situation = json.loads(prompts[0][prompts[0].index("{"):])["situation"]
    fragment = situation["recourse"]
    assert sorted(fragment) == ["broken_promise", "places_you_currently_observe",
                                "today", "your_reading_of_them"]
    assert "known_settlement_reports" not in fragment


async def test_a_provider_answer_executes_through_the_own_executor(monkeypatch):
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    observe(world)
    prompts = provider(monkeypatch, choose("marchar até Ferroalto"))
    review = next((item for item in world.agenda.pop_due(world.clock.absolute_day + 1)
                   if item.kind == REVIEW_KIND), None)
    assert review is not None

    claims, covered = await review_daily_institutional_turn(world, [review])

    assert covered == {AUREN}
    detachment = next(iter(world.society.detachments.values()))
    assert detachment.stage == "marching" and detachment.destination_id == "ferroalto"


async def test_a_pending_creditor_is_rescheduled_for_tomorrow(monkeypatch):
    world, review, prompts = await _world_with_due_review(monkeypatch, ai_decider.NO_ACTION)
    day = world.clock.absolute_day
    await review_daily_institutional_turn(world, [review])

    assert world.agenda.get(review_id(day + 1)) is not None


async def test_without_a_real_provider_nothing_is_claimed_or_consumed(monkeypatch):
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    review = None
    for item in world.agenda.pop_due(world.clock.absolute_day + 1):
        if item.kind == REVIEW_KIND:
            review = item
    assert review is not None

    claims, covered = await review_daily_institutional_turn(world, [review])

    assert claims == {} and covered == set()


async def test_an_unavailable_provider_still_leaves_a_causal_receipt(monkeypatch):
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    before = sum(1 for item in world.events if item.event_type == ai_decider.FAILED_EVENT)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    review = next((item for item in world.agenda.pop_due(world.clock.absolute_day + 1)
                   if item.kind == REVIEW_KIND), None)
    assert review is not None

    await review_daily_institutional_turn(world, [review])

    receipts = [item for item in world.events if item.event_type == ai_decider.FAILED_EVENT]
    assert len(receipts) == before + 1, "an un-asked day must still be visible in the causal record"
    assert "indisponível" in receipts[-1].content


async def test_the_standalone_turn_also_records_the_failed_receipt(monkeypatch):
    world = wronged_world(due_day=28, expires_day=20)
    engine = MedievalSimulator(world)
    await breached(world, engine)
    before = sum(1 for item in world.events if item.event_type == ai_decider.FAILED_EVENT)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)

    changed = await _turn(world, AUREN)

    assert changed is False
    assert sum(1 for item in world.events if item.event_type == ai_decider.FAILED_EVENT) == before + 1


async def test_non_recourse_situations_start_no_daily_menu():
    world = wronged_world(due_day=28, expires_day=20)
    claims, covered = await review_daily_institutional_turn(world, ())
    assert claims == {} and covered == set()
    assert daily_actors(world, ()) == ()


async def test_labels_come_from_the_option_itself_not_from_adapter_state(monkeypatch):
    world, review, prompts = await _world_with_due_review(monkeypatch, ai_decider.NO_ACTION)

    adapter = recourse_adapters()[0]
    by_id = {option.id: option for option in adapter.options_fn(world, AUREN)}
    assert by_id

    fresh_adapter = recourse_adapters()[0]
    for option in by_id.values():
        assert fresh_adapter.label_fn(option) == adapter.label_fn(option) == option.label
