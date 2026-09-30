"""Prepared actors use shared runtime menus; no real provider or drama quota."""

import json
import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.actor_dossier import build_actor_dossier
from src.sim.medieval.character_rite_policy import review_character_rites
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import validate_history
from src.sim.medieval.institutional_agenda import (monthly_actors, monthly_adapters,
                                                   review_daily_institutional_turn)
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn_with_provider
from src.sim.medieval.persistence import load_world, save_world
from tests.test_medieval_religion import prepared, ORDER, CULT, invite, join
from tests.test_medieval_rites import totals


def provider(monkeypatch, world, choose):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 50, "ai_max_calls": 50})
    prompts = []
    async def call(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        return {"selected_id": choose(payload)}
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call)
    return prompts


@pytest.mark.parametrize("recipient_kind,accept", [("character", True), ("population_group", True),
                                                     ("character", False), ("population_group", False)])
async def test_shared_turn_invites_then_recipient_decides_next_day(monkeypatch, tmp_path, recipient_kind, accept):
    world, person = prepared()
    recipient = person if recipient_kind == "character" else EntityRef(
        "population_group", world.society.characters[person.id].population_group_id)
    target = f"religious-invite:{ORDER.id}:{recipient.kind}:{recipient.id}:"
    def choose(payload):
        ids = [o["id"] for o in payload["choices"]]
        if any(identity.startswith(target) for identity in ids):
            return next(identity for identity in ids if identity.startswith(target))
        return next(identity for identity in ids if identity.startswith("religious-join:")) if accept else ai_decider.NO_ACTION
    prompts = provider(monkeypatch, world, choose)
    before = totals(world)
    assert ORDER in monthly_actors(world)
    await review_institutional_decision_turn_with_provider(world, monthly_adapters(), actors=(ORDER,))
    assert not world.society.religious_adherences
    assert len(prompts) == 1
    notice = next(iter(world.knowledge.religious_invitation_notices.values()))
    path = tmp_path / "awaiting-faith.mws"
    save_world(world, path)
    world = load_world(path)
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    await review_character_rites(world, due)
    await review_daily_institutional_turn(world, due)
    assert len(prompts) == 2
    # Same actual runtime wake-up path, distinct recipient consultation and date.
    assert prompts[1]["situation"]["religious_identity"]["received_invitations"][0]["event_id"] == notice.event_id
    assert bool(world.society.religious_adherences) is accept
    if accept:
        affiliation = next(iter(world.society.religious_adherences.values()))
        assert affiliation.actor_ref == recipient and affiliation.joined_day == notice.offered_day + 1
        assert (world.event_index()[affiliation.last_event_id].causal_payload["decision_event_id"]
                != world.event_index()[notice.event_id].causal_payload["decision_event_id"])
    else:
        decline = next(e for e in reversed(world.events) if (e.decision or {}).get("action") == "no_action")
        assert decline.decision["actor_ref"] == recipient.to_dict() and not decline.deltas
    assert totals(world) == before
    validate_history(world.events, world.clock.absolute_day)
    world.society.validate(set(world.map.regions), world)
    world.knowledge.validate(world)
    assert all(not e.deltas for e in world.events if e.causal_origin.value == "llm_interpretation")


async def test_own_prior_faith_influences_later_choice_without_foreign_beliefs(monkeypatch):
    world, actor = prepared()
    prior = join(world, actor, ORDER)
    # Another resident's allegiance is not in this actor's dossier.
    other = next(EntityRef("character", c.id) for c in world.society.characters.values()
                 if c.location_id == "pedraclara" and c.id != actor.id)
    own = build_actor_dossier(world, actor)["religious_identity"]
    assert own["own_affiliation"]["event_id"] == prior.last_event_id
    assert build_actor_dossier(world, other)["religious_identity"]["own_affiliation"] is None
    before = totals(world)
    def choose(payload):
        faith = payload["situation"]["religious_identity"]
        compassionate = (faith["own_affiliation"] is not None
                         and "amparar os vulneráveis" in faith["own_affiliation"]["doctrine"])
        return ai_decider.NO_ACTION if compassionate else next(
            item["id"] for item in payload["choices"] if item["id"].startswith("religious-join:"))
    prompts = provider(monkeypatch, world, choose)
    invite(world, CULT, actor)
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    await review_character_rites(world, due)
    assert len(prompts) == 1
    assert next(iter(world.society.religious_adherences.values())).organization_id == ORDER.id
    refusal = next(e for e in reversed(world.events) if (e.decision or {}).get("action") == "no_action")
    assert prior.last_event_id in {link.cause_event_id for link in refusal.causal_links}
    assert totals(world) == before

    uncommitted, counterpart = prepared()
    counter_prompts = provider(monkeypatch, uncommitted, choose)
    invite(uncommitted, CULT, counterpart)
    uncommitted.clock = uncommitted.clock.advance(1)
    await review_character_rites(uncommitted, uncommitted.agenda.pop_due(uncommitted.clock.absolute_day))
    assert len(counter_prompts) == 1
    assert next(iter(uncommitted.society.religious_adherences.values())).organization_id == CULT.id
