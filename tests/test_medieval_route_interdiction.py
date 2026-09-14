"""A prepared column can close one local route without gaining its assets."""

import asyncio
import copy
import json

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.events import record_event
from src.sim.medieval.force import (detect_force_standoffs, force_position_options,
                                    prepare_force_position, raise_detachment, raise_options,
                                    withdraw_detachment, withdrawal_options)
from src.sim.medieval.force_contact_policy import review_force_contacts
from src.sim.medieval.logistics import queue_freight
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.route_interdiction import execute_route_interdiction_option, route_interdiction_options
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports


OWNER = EntityRef("polity", "auren")
RIVAL = EntityRef("polity", "escarlia")
HOME = "campomanso"
TARGET = "pedraclara"
ROAD = "road-campomanso-pedraclara"


def decide(world, option):
    return record_event(world, "route_interdiction_decided", "Decisão canônica de interdição.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def tick(world):
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    resolve_dated(world, due)
    return due


def prepared_contact_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    group = next(item for item in world.society.population.values() if item.settlement_id == HOME)
    soldiers_id = f"pop:{HOME}:{group.people}:soldier"
    world.society.population[soldiers_id] = group.model_copy(
        update={"id": soldiers_id, "occupation": "soldier", "count": 20})
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    raised = next(item for item in raise_options(world, OWNER, days=20) if item.destination_id == TARGET)
    own = raise_detachment(world, OWNER, raised.id, decide(world, raised).id, days=20)
    while world.society.detachments[own.id].stage == "marching":
        tick(world)
    position = force_position_options(world, OWNER, detachment_id=own.id)[0]
    prepare_force_position(world, OWNER, position.id, decide(world, position).id)
    for _ in range(3):
        tick(world)
    # A route reading belongs to the endpoint administration; this refresh is
    # the actor's dated observation, not omniscient access to Map internals.
    refresh_route_reports(world, route_ids=(ROAD,))
    own = world.society.detachments[own.id]

    resident = next(item for item in world.society.population.values() if item.settlement_id == "ferroalto")
    rival_group = resident.model_copy(update={"id": f"pop:ferroalto:{resident.people}:soldier",
                                              "occupation": "soldier", "count": 5})
    world.society.population[rival_group.id] = rival_group
    rival = Detachment(id="detachment:interdiction-rival", owner_ref=RIVAL, source_group_id=rival_group.id,
                       count=5, location_id=TARGET, destination_id=TARGET, route_ids=(), route_index=0,
                       provisions=999, stage="present", started_day=world.clock.absolute_day,
                       due_day=world.clock.absolute_day + 1, decision_event_id=own.decision_event_id,
                       last_event_id=own.last_event_id)
    world.society.detachments[rival.id] = rival
    detect_force_standoffs(world, rival.id)
    return world, own.id


def queue_real_food(world):
    source = next(item for item in world.economy.stocks.values()
                  if item.owner_ref == OWNER and item.location_id == HOME and item.goods.get("food", 0) > 1)
    destination = next(item for item in world.economy.stocks.values()
                       if item.owner_ref == OWNER and item.location_id == TARGET)
    decision = record_event(
        world, "freight_decided", "Frete interno canônico para testar atraso físico.", fact_kind=FactKind.DECISION,
        decision={"action": "freight", "source_id": source.id, "destination_id": destination.id,
                  "resource_id": "food", "quantity": 1, "route_ids": [ROAD],
                  "actor_ref": OWNER.to_dict()},
    )
    return queue_freight(world, source.id, destination.id, "food", 1, (ROAD,), decision_event_id=decision.id)


async def test_contact_selected_interdiction_closes_map_reports_and_delays_existing_cargo(tmp_path, monkeypatch):
    world, own_id = prepared_contact_world()
    notice = world.knowledge.force_contacts_for_actor(OWNER)[0]
    disabled_before = world_snapshot(world)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    await review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),))
    assert world_snapshot(world) == disabled_before

    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 10})
    prompts = []

    async def choose_interdict(prompt, *_args, **_kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": next(choice["id"] for choice in payload["choices"]
                               if choice["label"].endswith(f"{ROAD} com esta coluna preparada."))}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_interdict)
    order = queue_real_food(world)
    source_before = world.economy.stocks[order.source_id].goods["food"]
    parcel_id = next(parcel.id for parcel in world.economy.parcels.values() if parcel.order_id == order.id)
    await review_force_contacts(world, (world.agenda.get(f"force-contact-review:{notice.id}"),))

    active = next(item for item in world.society.route_interdictions.values() if item.stage == "active")
    assert active.detachment_id == own_id and active.route_id == ROAD
    assert world.map.get_route_operational_capacity(ROAD) == 0
    assert world.knowledge.route_report(OWNER, ROAD).operational_capacity == 0
    assert world.economy.stocks[order.source_id].goods["food"] == source_before
    assert world.economy.parcels[parcel_id].quantity == 1
    assert "interdictor" not in prompts[0] and "provisions" not in prompts[0]

    tick(world)
    assert world.economy.parcels[parcel_id].quantity == 1
    delay = next(event for event in reversed(world.events) if event.event_type == "cargo_delayed")
    interdict_event = next(event for event in world.events if event.event_type == "route_interdicted")
    assert interdict_event.id in {link.cause_event_id for link in delay.causal_links}
    path = tmp_path / "route-interdiction.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_explicit_lift_and_departure_revoke_only_the_force_cause():
    world, own_id = prepared_contact_world()
    option = next(item for item in route_interdiction_options(world, OWNER, detachment_id=own_id)
                  if item.kind == "interdict" and item.route_id == ROAD)
    active = execute_route_interdiction_option(world, OWNER, option.id, decide(world, option).id)
    assert active.stage == "active" and world.map.get_route_operational_capacity(ROAD) == 0

    lift = next(item for item in route_interdiction_options(world, OWNER, detachment_id=own_id) if item.kind == "lift")
    execute_route_interdiction_option(world, OWNER, lift.id, decide(world, lift).id)
    assert world.map.get_route_operational_capacity(ROAD) > 0

    external = copy.deepcopy(world)
    option = next(item for item in route_interdiction_options(external, OWNER, detachment_id=own_id)
                  if item.kind == "interdict" and item.route_id == ROAD)
    execute_route_interdiction_option(external, OWNER, option.id, decide(external, option).id)
    external.map.routes[ROAD].update_runtime(enabled=False)
    lift = next(item for item in route_interdiction_options(external, OWNER, detachment_id=own_id) if item.kind == "lift")
    execute_route_interdiction_option(external, OWNER, lift.id, decide(external, lift).id)
    assert external.map.get_route_operational_capacity(ROAD) == 0

    revoked = copy.deepcopy(world)
    option = next(item for item in route_interdiction_options(revoked, OWNER, detachment_id=own_id)
                  if item.kind == "interdict" and item.route_id == ROAD)
    execute_route_interdiction_option(revoked, OWNER, option.id, decide(revoked, option).id)
    withdrawal = withdrawal_options(revoked, OWNER, detachment_id=own_id)[0]
    withdraw_detachment(revoked, OWNER, withdrawal.id, decide(revoked, withdrawal).id)
    assert revoked.map.get_route_operational_capacity(ROAD) > 0
    lifted = next(event for event in reversed(revoked.events) if event.event_type == "route_interdiction_lifted")
    withdrawal_event = next(event for event in reversed(revoked.events) if event.event_type == "detachment_withdrawal_started")
    assert lifted.sequence < withdrawal_event.sequence
