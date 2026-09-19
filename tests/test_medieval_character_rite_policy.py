"""A resident may offer a rite; a separate institution may later sponsor it."""

import json

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.actions import start_practice
from src.sim.medieval.character_rite_policy import (OFFER_REVIEW_KIND, SPONSOR_REVIEW_KIND,
                                                     review_character_rites,
                                                     schedule_character_rite_offers)
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.rites import (HEALTH_THRESHOLD, REPORT_MAX_AGE, record_rite_offer,
                                    rite_offer_options)
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


PLACE = "pedraclara"


def prepared_world():
    """One real local condition and one qualified named resident."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    need = world.economy.needs[PLACE]
    world.economy.needs[need.id] = need.model_copy(update={"health": 700})
    healer = next(character for _, character in sorted(world.society.characters.items())
                  if character.death_day is None and character.location_id == PLACE)
    world.society.characters[healer.id] = healer.model_copy(
        update={"skills": healer.skills.model_copy(update={"restoration_magic": 40})})
    refresh_settlement_reports(world)
    return world, world.society.characters[healer.id]


def enable(world):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    return world


def select_first(monkeypatch, prompts, *, no_action=False):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        if no_action:
            return {"selected_id": ai_decider.NO_ACTION}
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


async def advance_review(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_character_rites(world, due)


async def test_character_offer_then_independent_sponsorship_completes_paid_rite(tmp_path, monkeypatch):
    world, healer = prepared_world()
    enable(world)
    prompts = []
    select_first(monkeypatch, prompts)
    before_health = world.economy.needs[PLACE].health
    blueprint = world.research.rite_blueprints["rite-of-restoration"]
    sponsor = EntityRef("organization", "ordem-da-aurora")
    stock = next(item for item in world.economy.stocks.values()
                 if item.owner_ref == sponsor and item.location_id == PLACE)
    before_inputs = {resource: stock.goods.get(resource, 0) for resource in blueprint.inputs}

    scheduled = schedule_character_rite_offers(world)
    assert scheduled
    assert any(item.startswith("character-rite-offer-review:character:005:") for item in scheduled)
    assert world.agenda.get(scheduled[0]).kind == OFFER_REVIEW_KIND
    await advance_review(world)

    offer = next(event for event in world.events if event.event_type == "rite_offered")
    assert offer.decision["actor_ref"] == EntityRef("character", healer.id).to_dict()
    assert offer.deltas == ()
    assert world.agenda.get(f"character-rite-sponsor-review:{offer.id}").kind == SPONSOR_REVIEW_KIND
    character_prompt = prompts[0]
    for private_material in ("stock", "account", "treasury", "reagent", "balance"):
        assert private_material not in character_prompt

    await advance_review(world)
    rite = next(iter(world.research.rites.values()))
    sponsor_decision = next(event for event in world.events if event.event_type == "rite_sponsorship_decided")
    started = next(event for event in world.events if event.event_type == "rite_started")
    interpretation_ids = {event.id for event in world.events if event.causal_origin.value == "llm_interpretation"}
    assert interpretation_ids
    assert not interpretation_ids & {link.cause_event_id for link in started.causal_links}
    assert {offer.id, sponsor_decision.id} <= {link.cause_event_id for link in started.causal_links}

    while world.clock.absolute_day < rite.due_day:
        world.clock = world.clock.advance(1)
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))

    assert world.research.rites[rite.id].stage == "completed"
    assert world.economy.needs[PLACE].health == before_health + blueprint.health_gain_permille
    for resource, amount in blueprint.inputs.items():
        assert world.economy.stocks[stock.id].goods[resource] == before_inputs[resource] - amount
    path = tmp_path / "character-rite.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_character_offer_refuses_or_rejects_all_invalid_local_states_without_material_mutation(monkeypatch):
    world, healer = prepared_world()
    prompts = []
    select_first(monkeypatch, prompts, no_action=True)
    # Disabled/budget-blocked policy must not call the provider or manufacture
    # a failed receipt merely because a resident could have offered a rite.
    baseline_events = len(world.events)
    assert schedule_character_rite_offers(world) == ()
    assert len(world.events) == baseline_events and not world.agenda.to_dict()

    enable(world)
    schedule_character_rite_offers(world)
    await advance_review(world)
    new_events = world.events[baseline_events:]
    assert not any(event.event_type in {"rite_offered", "rite_started", "rite_completed"} for event in new_events)
    assert new_events and all(not event.deltas for event in new_events)
    assert not world.research.rites

    # A stale observation, a dead resident and a busy resident each produce no
    # offer option; none may turn an old report into a material action.
    stale, stale_healer = prepared_world()
    stale.clock = stale.clock.advance(REPORT_MAX_AGE)
    assert rite_offer_options(stale, stale_healer.id) == ()

    dead, dead_healer = prepared_world()
    dead.society.characters[dead_healer.id] = dead_healer.model_copy(
        update={"death_day": dead.clock.absolute_day, "population_group_id": None})
    assert rite_offer_options(dead, dead_healer.id) == ()

    busy, busy_healer = prepared_world()
    start_practice(busy, busy_healer.id, "combat")
    assert rite_offer_options(busy, busy_healer.id) == ()

    invalid, invalid_healer = prepared_world()
    option = rite_offer_options(invalid, invalid_healer.id)[0]
    before = (len(invalid.events), dict(invalid.economy.needs), dict(invalid.research.rites))
    with pytest.raises(ValueError, match="stale or unknown"):
        record_rite_offer(invalid, invalid_healer.id, option.id + ":forged")
    assert (len(invalid.events), dict(invalid.economy.needs), dict(invalid.research.rites)) == before
    assert invalid.economy.needs[PLACE].health < HEALTH_THRESHOLD
