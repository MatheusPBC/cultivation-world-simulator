"""A force contact can create promises to leave, never an automatic retreat."""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.force import (detect_force_standoffs, force_options, occupy_settlement,
                                    raise_detachment, raise_options, withdrawal_options)
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.force_deescalation import (force_deescalation_offer_options,
                                                 force_deescalation_response_options,
                                                 force_withdrawal_fulfillment_options,
                                                 fulfill_force_withdrawal,
                                                 offer_force_deescalation,
                                                 respond_force_deescalation)
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "salgueiro"


def decide(world, option):
    return record_event(world, "force_deescalation_decided", "Decisão canônica sobre contato armado.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def contact_world():
    """Two genuinely present columns, each with a reported path home."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raise_option = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raise_option.id, decide(world, raise_option).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    occupy = next(item for item in force_options(world, OWNER) if item.kind == "occupy")
    occupy_settlement(world, OWNER, occupy.id, decide(world, occupy).id)

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    own = world.society.detachments[own.id]
    rival = Detachment(id="detachment:deescalation-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    standoff = detect_force_standoffs(world, rival.id)[0]
    return world, own.id, rival.id, standoff.id


def accept_mutual_offer(world):
    offer = next(item for item in force_deescalation_offer_options(world, OWNER) if item.kind == "mutual")
    proposal = offer_force_deescalation(world, OWNER, offer.id, decide(world, offer).id)
    response = next(item for item in force_deescalation_response_options(world, RIVAL)
                    if item.proposal_id == proposal.id and item.response == "accept")
    return respond_force_deescalation(world, RIVAL, response.id, decide(world, response).id)


def test_mutual_promise_acceptance_moves_nothing_then_each_owner_withdraws(tmp_path):
    world, own_id, rival_id, standoff_id = contact_world()
    proposal = accept_mutual_offer(world)

    assert proposal.status == "accepted"
    assert len(world.relations.obligations) == 2
    assert {item.status for item in world.relations.obligations.values()} == {"active"}
    assert world.society.detachments[own_id].stage == "present"
    assert world.society.detachments[rival_id].stage == "present"
    assert world.society.settlements[TARGET].occupier_id == OWNER.id

    path = tmp_path / "force-deescalation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)

    for actor in (OWNER, RIVAL):
        option = force_withdrawal_fulfillment_options(world, actor)[0]
        fulfill_force_withdrawal(world, actor, option.id, decide(world, option).id)
    assert {item.status for item in world.relations.obligations.values()} == {"fulfilled"}
    assert world.society.settlements[TARGET].occupier_id is None
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert world.society.detachments[own_id].stage == "marching"
    assert world.society.detachments[rival_id].stage == "marching"

    while any(world.society.detachments[item].stage == "marching" for item in (own_id, rival_id)):
        tick(world)
    assert world.society.detachments[own_id].location_id == HOME
    rival_destination = world.society.settlements[world.society.detachments[rival_id].location_id]
    assert rival_destination.administrator_id == RIVAL.id
    assert not any(event.event_type in {"battle_resolved", "casualties_taken", "loot_taken"}
                   for event in world.events)


def test_unavailable_route_leaves_promise_unfulfilled_and_deadline_records_breach_memory():
    world, own_id, rival_id, _ = contact_world()
    accept_mutual_offer(world)
    world.knowledge.route_reports.clear()

    assert not force_withdrawal_fulfillment_options(world, OWNER)
    assert not force_withdrawal_fulfillment_options(world, RIVAL)
    while any(item.status == "active" for item in world.relations.obligations.values()):
        tick(world)

    assert {item.status for item in world.relations.obligations.values()} == {"breached"}
    assert world.society.detachments[own_id].stage == "present"
    assert world.society.detachments[rival_id].stage == "present"
    breaches = [event for event in world.events if event.event_type == "commitment_breached"]
    assert len(breaches) == 2
    assert {memory.event_id for memory in world.relations.memories.values()} == {event.id for event in breaches}
    assert not any(event.event_type == "detachment_withdrawal_started" for event in world.events)


def test_stale_mandateless_and_provider_off_contact_turn_are_atomic(monkeypatch):
    world, own_id, _, _ = contact_world()
    offer = force_deescalation_offer_options(world, OWNER)[0]
    before = len(world.events)
    with pytest.raises(ValueError, match="stale or unknown"):
        offer_force_deescalation(world, OWNER, offer.id + ":forged", decide(world, offer).id)
    assert not world.relations.proposals and world.society.detachments[own_id].stage == "present"
    assert len(world.events) == before + 1

    office = world.authority.offices["office:polity:auren"]
    world.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "diplomacy")})
    with pytest.raises(ValueError, match="current authority"):
        offer_force_deescalation(world, OWNER, offer.id, decide(world, offer).id)
    assert not world.relations.proposals and world.society.detachments[own_id].stage == "present"
    world.authority.offices[office.id] = office

    notice = world.knowledge.force_contacts_for_actor(OWNER)[0]
    before = world_snapshot(world)
    monkeypatch.setattr("src.sim.medieval.ai_decider.provider_available", lambda: False)
    assert asyncio.run(review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),))) is None
    assert world_snapshot(world) == before

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1,
                                                   "ai_max_calls": 10})
    before_ai = world_snapshot(world)
    with pytest.raises(ProviderDecisionRequired):
        asyncio.run(review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),)))
    assert len(world.events) == before_ai["event_count"]
    assert world.society.detachments[own_id].stage == "present"


async def test_provider_turns_require_independent_offer_response_and_withdrawal(monkeypatch, tmp_path):
    """A provider may choose each current turn, but never moves both columns at once."""
    world, own_id, rival_id, standoff_id = contact_world()
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 2, "ai_max_calls": 8}
    )
    selected_ids = []

    async def choose_deescalation(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        choices = [choice["id"] for choice in payload["choices"]]
        selected = "NO_ACTION"
        for option_id in choices:
            if option_id.startswith("force-deescalation-response:") and option_id.endswith(":accept"):
                selected = option_id
                break
            if option_id.startswith("force-deescalation:") and option_id.endswith(":mutual"):
                selected = option_id
                break
            if option_id.startswith("force-withdrawal-fulfillment:"):
                selected = option_id
                break
        selected_ids.append(selected)
        return {"selected_id": selected}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_deescalation)

    for _ in range(6):
        due = tick(world)
        await review_force_contacts(world, due)
        if (world.relations.obligations
                and all(item.status == "fulfilled" for item in world.relations.obligations.values())):
            break

    assert len(selected_ids) == 4
    assert any(item.startswith("force-deescalation:") for item in selected_ids)
    assert any(item.startswith("force-deescalation-response:") for item in selected_ids)
    assert sum(item.startswith("force-withdrawal-fulfillment:") for item in selected_ids) == 2
    assert {item.status for item in world.relations.obligations.values()} == {"fulfilled"}
    assert world.society.force_standoffs[standoff_id].stage == "resolved"
    assert world.society.detachments[own_id].stage == "marching"
    assert world.society.detachments[rival_id].stage == "marching"
    assert not [event for event in world.events
                if event.causal_origin.value == "llm_interpretation" and event.deltas]
    validate_history(world.events, world.clock.absolute_day)
    path = tmp_path / "provider-force-deescalation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
