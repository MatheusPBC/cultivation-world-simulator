"""A religious order uses ordinary bilateral teaching, never conversion as a bonus."""

import json
import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.diplomacy_policy import review_promised_teaching_turns, teaching_offer_options
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import validate_history
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn_with_provider
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.server.medieval.queries import research_view
from tests.test_medieval_diplomacy import world_with_knowledge, BUYER, SELLER
from tests.test_medieval_diplomacy_policy import useful_buyer
from tests.test_medieval_research import teach
from tests.test_medieval_rites import ailing_world, started, tick_to


async def test_religious_order_sells_only_knowledge_it_received_then_teaches_with_two_consents(monkeypatch, tmp_path):
    world = world_with_knowledge()
    order = EntityRef("organization", "ordem-da-aurora")
    assert not world.knowledge.knows(order, "metallurgy")
    # Existing real research -> two API teaching decisions -> the order's own
    # knowledge. Religious identity alone had granted it no technique.
    teach(world, SELLER, order, "metallurgy")
    useful_buyer(world)
    initial_money = sum(a.balance for a in world.economy.accounts.values())
    before_stock = {key: dict(value.goods) for key, value in world.economy.stocks.items()}
    target = next(o.id for o in teaching_offer_options(world, order)
                  if o.counterparty_ref == BUYER and o.technology_id == "metallurgy")
    prompts = []
    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        ids = [o["id"] for o in payload["choices"]]
        payment = next((o["id"] for o in payload["choices"]
                        if o["label"] == "Cumprir o pagamento prometido."), None)
        if payment:
            # The prompt intentionally aliases an ID containing an account;
            # select the offered public token, never the hidden canonical ID.
            return {"selected_id": payment}
        for prefix in ("accept-promised-teaching:", "promised-teaching:", "teaching-payment:"):
            match = next((identity for identity in ids if identity.startswith(prefix)), None)
            if match:
                return {"selected_id": match}
        response = next((identity for identity in ids if identity.startswith("teaching-response:")
                         and (identity.endswith(":accept") or ":counter:" in identity)), None)
        return {"selected_id": response or (target if target in ids else ai_decider.NO_ACTION)}
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20, "ai_max_calls": 20})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    async def turn(actor):
        resolve_dated(world, world.agenda.pop_due(world.clock.absolute_day))
        await review_institutional_decision_turn_with_provider(world, monthly_adapters(), actors=(actor,))
    await turn(order)
    for actor in (BUYER, order, BUYER):
        world.clock = world.clock.advance(1)
        await turn(actor)
        assert not world.knowledge.knows(BUYER, "metallurgy")
    world.clock = world.clock.advance(1)
    await turn(order)
    assert not world.knowledge.knows(BUYER, "metallurgy"), "teacher consent is not learner consent"
    await review_promised_teaching_turns(world, actors=(BUYER,))
    assert world.knowledge.knows(BUYER, "metallurgy")
    assert len(prompts) == 6
    assert prompts[0]["situation"]["religious_identity"]["own_declared_doctrine"]
    assert not world.society.religious_adherences, "instruction never converts the learner or population"
    assert sum(a.balance for a in world.economy.accounts.values()) == initial_money
    assert {key: dict(value.goods) for key, value in world.economy.stocks.items()} == before_stock
    learned = next(k for k in world.knowledge.technologies.values() if k.owner_ref == BUYER and k.technology_id == "metallurgy")
    causes = {link.cause_event_id for link in world.event_index()[learned.event_id].causal_links}
    actors = {(world.event_index()[identity].decision or {}).get("actor_ref", {}).get("id") for identity in causes}
    assert {order.id, BUYER.id} <= actors
    validate_history(world.events, world.clock.absolute_day)
    path = tmp_path / "religious-teaching.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_public_research_projection_exposes_actual_rite_execution_not_only_catalog():
    world, healer = ailing_world()
    _, rite = started(world, healer)
    assert research_view(world).rites == [rite]
    assert research_view(world).rites[0].stage == "officiating"
    tick_to(world, rite.due_day)
    assert research_view(world).rites[0].stage == "completed"
    assert research_view(world).rites[0].last_event_id == world.research.rites[rite.id].last_event_id
