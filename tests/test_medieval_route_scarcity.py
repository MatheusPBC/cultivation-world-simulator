"""The first bounded route-to-scarcity causal slice."""

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_aid import aid_request_options
from src.sim.medieval.logistics import queue_freight


ROAD = "road-campomanso-pedraclara"
SOURCE = "stock:campomanso"
DESTINATION = "stock:pedraclara"
AUREN = EntityRef("polity", "auren")


async def test_interrupted_food_route_becomes_dated_scarcity_and_aid_affordance():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    destination = world.economy.stocks[DESTINATION]
    world.economy.stocks[DESTINATION] = destination.model_copy(update={"goods": {}})

    before_capacity = world.map.get_route_operational_capacity(ROAD)
    world.map.routes[ROAD].update_runtime(enabled=False)
    interrupted = record_event(
        world,
        "route_interrupted",
        "A passagem foi interrompida.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("route", ROAD, "operational_capacity", before_capacity, 0.0),),
    )
    intent = {
        "action": "freight",
        "source_id": SOURCE,
        "destination_id": DESTINATION,
        "resource_id": "food",
        "quantity": 1,
        "route_ids": [ROAD],
        "actor_ref": world.economy.stocks[SOURCE].owner_ref.to_dict(),
    }
    decision = record_event(world, "freight_decided", "Frete autorizado.",
                            fact_kind=FactKind.DECISION, decision=intent)
    queue_freight(world, SOURCE, DESTINATION, "food", 1, (ROAD,), decision_event_id=decision.id)

    while world.clock.absolute_day < 30:
        await MedievalSimulator(world).step()

    need = world.economy.needs["pedraclara"]
    assert (need.missing_food, need.health, need.unrest) == (2400, 900, 100)
    report = world.knowledge.settlement_report(AUREN, "pedraclara")
    assert report is not None
    assert report.observed_day == 30
    assert (report.missing_food, report.health, report.unrest) == (2400, 900, 100)

    subsistence = next(event for event in world.events
                       if event.event_type == "subsistence_resolved"
                       and any(delta.owner_id == "pedraclara" for delta in event.deltas))
    assert interrupted.id in {link.cause_event_id for link in subsistence.causal_links}
    assert any(option.requester_settlement_id == "pedraclara"
               for option in aid_request_options(world, AUREN))
    # A request/notice is only a dated institutional decision.  The blocked
    # settlement receives no institutional aid without an independent provider
    # acceptance and later fulfillment. Another polity may still make its own
    # offline local-relief decision elsewhere in the same monthly boundary.
    assert not any(event.event_type == "institutional_aid_accepted" for event in world.events)
    assert not any(event.event_type == "relief_distributed"
                   and event.causal_payload["relief_distribution"]["settlement_id"] == "pedraclara"
                   for event in world.events)
