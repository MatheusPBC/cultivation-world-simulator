"""The drake acts only when a provider chooses; never by deadline or routine."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.creature_policy import REVIEW_KIND
from src.sim.medieval.creatures import creature_options, tribute_options
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
from tests.test_medieval_creatures import buy_across_the_river, crossed_world
from tests.test_medieval_logistics import total_food

AUREN = EntityRef("polity", "auren")


def enable(world, *, per_step=6, maximum=100):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": per_step,
                                                   "ai_max_calls": maximum})
    return world


def provider(monkeypatch, decide):
    """Local stand-in for the existing client: no network and no key."""
    prompts = []

    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        answer = decide(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    return prompts


def choose(kind_marker):
    """Pick the first offered choice whose label matches, else do nothing."""
    def decide(prompt):
        import json
        payload = json.loads(prompt[prompt.index("{"):])
        for choice in payload["choices"]:
            if kind_marker in choice["label"]:
                return {"selected_id": choice["id"]}
        return {"selected_id": "NO_ACTION"}
    return decide


async def hungry_world():
    """Real crossings made the drake hungry and earned it a dated turn."""
    world = enable(await crossed_world())
    assert not world.creatures.demands, "hunger alone demands nothing"
    assert any(entry["kind"] == REVIEW_KIND for entry in world.agenda.to_dict())
    return world


async def test_a_provider_drives_demand_and_a_tribute_settles_it(tmp_path, monkeypatch):
    world = await hungry_world()
    prompts = provider(monkeypatch, choose("Exigir tributo"))

    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    assert demand.stage == "open" and world.map.routes[ROUTE_ID].enabled
    for prompt in prompts:
        # The drake speaks of its own body only; no institution's holdings.
        assert "treasury:" not in prompt and "stock:" not in prompt

    # The next day the noticed administrations, and only they, may answer.
    prompts = provider(monkeypatch, choose("Entregar"))
    food = total_food(world)
    condition = world.creatures.creatures[DRAKE_ID].condition
    payer = next(EntityRef("polity", key) for key in sorted(world.society.polities)
                 if tribute_options(world, EntityRef("polity", key)))
    stock_id = tribute_options(world, payer)[0].stock_id
    before = world.economy.stocks[stock_id].goods["food"]

    for _ in range(3):
        if world.creatures.demands[demand.id].stage == "satisfied":
            break
        await engine.step()

    settled = world.creatures.demands[demand.id]
    assert settled.stage == "satisfied"
    assert world.creatures.creatures[DRAKE_ID].condition > condition
    assert total_food(world) < food, "the tribute was really eaten"
    assert world.map.routes[ROUTE_ID].enabled
    for prompt in prompts:
        assert "hunger_threshold" not in prompt and "condition" not in prompt
    path = tmp_path / "drake-ai.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_without_a_choice_no_deadline_demands_or_closes_the_river(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))

    # Nobody offers anything: the provider declines every institutional turn.
    provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})
    while world.clock.absolute_day < demand.due_day:
        await engine.step()
    assert world.creatures.demands[demand.id].stage == "open"
    assert world.map.routes[ROUTE_ID].enabled, "a deadline closes nothing by itself"

    # No daily retry is minted by hunger or silence. Disabled/error behaviour
    # is checked on new worlds that each have a real perception-granted turn.
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())
    disabled = await hungry_world()
    disabled.config = disabled.config.model_copy(update={"ai_enabled": False})
    await MedievalSimulator(disabled).step()
    assert not disabled.creatures.demands and disabled.map.routes[ROUTE_ID].enabled
    failed = await hungry_world()
    provider(monkeypatch, lambda prompt: RuntimeError("provider down"))
    await MedievalSimulator(failed).step()
    assert failed.map.routes[ROUTE_ID].enabled
    assert any(item.event_type == "ai_decision_failed" for item in failed.events)

    # A later crossing remains factual, but an ignored open demand does not
    # mint another creature turn just because more cargo passes the river.
    buy_across_the_river(world)
    await engine.step()
    await engine.step()
    pending = sum(item.quantity for item in world.economy.parcels.values())
    assert pending, "the bilateral cargo is still on the water"
    provider(monkeypatch, choose("Fechar a passagem"))
    for _ in range(4):
        await engine.step()
    assert world.map.routes[ROUTE_ID].enabled
    assert world.creatures.creatures[DRAKE_ID].restricted_route_id is None
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())


async def test_many_real_crossings_do_not_fan_out_reviews_while_demand_is_open(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    crossings_before = world.creatures.creatures[DRAKE_ID].perceived_crossings
    prompts = provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})
    for _ in range(8):
        buy_across_the_river(world)

    for _ in range(40):
        await engine.step()
        if (world.clock.absolute_day >= demand.due_day
                and not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())):
            break

    creature_prompts = [prompt for prompt in prompts if '"crossings_you_saw"' in prompt]
    assert world.creatures.creatures[DRAKE_ID].perceived_crossings > crossings_before
    assert len(creature_prompts) == 1, "only the bounded deadline can offer retaliation"
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())


async def test_ignored_expired_demand_stops_reviews_and_keeps_route_open(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    prompts = provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})

    while world.clock.absolute_day < demand.due_day:
        await engine.step()
    creature_calls = len([prompt for prompt in prompts if '"crossings_you_saw"' in prompt])
    assert demand.stage == "open" and demand.due_day <= world.clock.absolute_day
    assert world.map.routes[ROUTE_ID].enabled

    for _ in range(6):
        buy_across_the_river(world)
    for _ in range(10):
        await engine.step()

    assert len([prompt for prompt in prompts if '"crossings_you_saw"' in prompt]) == creature_calls
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())
    assert world.map.routes[ROUTE_ID].enabled
