"""Provider selections can finish a bilateral armed-contact de-escalation.

This is deliberately a policy-level integration test: the mocked provider only
selects IDs from the menu the contact policy exposed.  It never constructs the
offer, terms, routes, or material withdrawal itself.
"""

import asyncio
import json

from src.classes.causal_origin import CausalOrigin
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import validate_history
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.persistence import load_world, save_world, world_snapshot

from tests.test_medieval_force_deescalation import contact_world


def _choose_deescalation(prompt, calls):
    payload = json.loads(prompt[prompt.index("{"):])
    choices = payload["choices"]
    calls.append(tuple(choice["id"] for choice in choices))

    def selected(prefix):
        return next((choice["id"] for choice in choices if choice["id"].startswith(prefix)), None)

    # The response and fulfilment options are only offered after their real
    # predecessor exists.  Prefer them over a fresh offer whenever present.
    return (selected("force-deescalation-response:") or
            selected("force-withdrawal-fulfillment:") or
            next(choice["id"] for choice in choices
                 if choice["id"].startswith("force-deescalation:") and choice["id"].endswith(":mutual")))


async def _advance_and_review(world, days, own_id, rival_id):
    stages_when_withdrawals_begin = None
    for _ in range(days):
        world.clock = world.clock.advance(1)
        due = world.agenda.pop_due(world.clock.absolute_day)
        resolve_dated(world, due)
        await review_force_contacts(world, due)
        if (stages_when_withdrawals_begin is None
                and world.relations.obligations
                and {item.status for item in world.relations.obligations.values()} == {"fulfilled"}):
            stages_when_withdrawals_begin = (world.society.detachments[own_id].stage,
                                             world.society.detachments[rival_id].stage)
    return stages_when_withdrawals_begin


async def test_provider_contact_policy_completes_bilateral_deescalation_round_trip(tmp_path, monkeypatch):
    world, own_id, rival_id, standoff_id = contact_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 2,
                                                   "ai_max_calls": 4})
    calls = []

    async def call_llm_json(prompt, *args, **kwargs):
        return {"selected_id": _choose_deescalation(prompt, calls)}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)

    stages_when_withdrawals_begin = await _advance_and_review(world, 6, own_id, rival_id)

    decisions = [event for event in world.events if event.event_type == "force_standoff_decided"]
    assert len(decisions) == 4
    assert len(calls) == 4
    assert {item.status for item in world.relations.obligations.values()} == {"fulfilled"}
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert stages_when_withdrawals_begin == ("marching", "marching")

    receipts = [event for event in world.events if event.causal_origin == CausalOrigin.LLM_INTERPRETATION]
    assert len(receipts) == 4
    assert all(not event.deltas for event in receipts)
    validate_history(world.events, world.clock.absolute_day)

    path = tmp_path / "campaign-deescalation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
