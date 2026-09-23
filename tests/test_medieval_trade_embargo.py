"""A directed economic closure: refuse one counterparty at one's own post.

Everything an administration had before was universal (an export rate, a
service suspension) or armed (route interdiction). An embargo names a single
counterparty. It touches no route and no other owner's trade, and the target is
told nothing by decree: it finds out when its own cargo comes back.
"""

import asyncio
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.customs import checkpoint_active
from src.sim.medieval.embargo import (embargo_adapters, embargo_blocker, embargo_options,
                                      embargoes_of, execute_embargo, is_embargoed)
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.logistics import open_order
from src.sim.medieval.persistence import load_world, save_world, world_snapshot

from src.sim.medieval.customs import customs_open_options, open_customs_checkpoint
from src.run.medieval_world import create_medieval_world

from tests.test_medieval_customs import ROUTE, SITE


OPERATOR = EntityRef("polity", "auren")
TARGET = "escarlia"
CHECKPOINT = f"customs:{SITE}"


def declare(world, target_id=TARGET, kind="declare"):
    from src.sim.medieval.embargo import _terms

    option = next(item for item in embargo_options(world, OPERATOR)
                  if item.target_id == target_id and item.kind == kind)
    decision = record_event(world, "trade_embargo_authorized", "Medida comercial.",
                            fact_kind=FactKind.DECISION, decision=_terms(option))
    return execute_embargo(world, option, decision_event_id=decision.id)


async def prepared_world():
    """The authored pass with a staffed post, built without a nested loop."""
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.strategy.objectives.clear()
    actor = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, actor)[0]
    decision = record_event(world, "customs_open_decided", "Abrir posto.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    open_customs_checkpoint(world, option.id, decision_event_id=decision.id)
    await MedievalSimulator(world).step()
    assert checkpoint_active(world, world.economy.customs_checkpoints[CHECKPOINT])
    return world


def ship(world, source="stock:pontenegro", destination="stock:ferroalto", quantity=10):
    """A shipment whose owner is the destination holder -- here, the target."""
    decision = record_event(world, "freight_decided", "Despachar carga preparada.",
                            fact_kind=FactKind.DECISION, decision={"action": "prepared_freight"})
    return open_order(world, source, destination, "food", quantity, [ROUTE], decision_ids=(decision.id,))


def total_food(world):
    return (sum(stock.goods.get("food", 0) for stock in world.economy.stocks.values())
            + sum(parcel.quantity for parcel in world.economy.parcels.values()
                  if world.economy.freight_orders[parcel.order_id].resource_id == "food"))


async def test_declaring_and_lifting_is_one_dated_policy_transition():
    world = await prepared_world()
    assert embargoes_of(world, OPERATOR) == ()

    declared = declare(world)
    assert embargoes_of(world, OPERATOR) == (TARGET,)
    assert declared.event_type == "trade_embargo_declared"
    assert is_embargoed(world, OPERATOR, EntityRef("polity", TARGET))
    world.authority.validate(world)

    # The same counterparty is not offered twice; only the reverse act is.
    assert not [item for item in embargo_options(world, OPERATOR)
                if item.target_id == TARGET and item.kind == "declare"]
    lifted = declare(world, kind="lift")
    assert lifted.event_type == "trade_embargo_lifted"
    assert embargoes_of(world, OPERATOR) == ()
    world.authority.validate(world)


@pytest.mark.parametrize("missing", ["authority", "checkpoint", "target_self", "target_unknown"])
async def test_the_closure_requires_authority_a_staffed_own_post_and_a_real_counterparty(missing):
    world = await prepared_world()
    checkpoint = world.economy.customs_checkpoints[CHECKPOINT]
    target, expected = TARGET, "authority"
    if missing == "authority":
        world.authority.offices = {key: office for key, office in world.authority.offices.items()
                                   if office.institution_ref != OPERATOR}
    elif missing == "checkpoint":
        checkpoint, expected = None, "checkpoint"
    elif missing == "target_self":
        target, expected = OPERATOR.id, "target"
    else:
        target, expected = "nao-existe", "target"

    assert embargo_blocker(world, OPERATOR, target, checkpoint, kind="declare") == expected
    if missing == "checkpoint":
        world.economy.customs_checkpoints.pop(CHECKPOINT)
    if missing in {"authority", "checkpoint"}:
        assert not embargo_options(world, OPERATOR)


async def test_only_the_named_counterparty_is_refused_and_goods_are_conserved():
    world = await prepared_world()
    declare(world)
    food_before = total_food(world)

    # Escarlia owns stock:ferroalto; the refusal must hit only its cargo.
    order = ship(world)
    assert world.economy.freight_orders[order.id].owner_ref == EntityRef("polity", TARGET)
    await MedievalSimulator(world).step()

    notice = next(item for item in world.knowledge.customs_notices.values()
                  if item.order_id == order.id)
    assert notice.state == "refused" and notice.fee is None and notice.manifest_id is None
    refusal = next(item for item in world.events if item.id == notice.state_event_id)
    assert refusal.event_type == "customs_refused"
    assert total_food(world) == food_before, "a carga voltou; nada foi criado nem destruído"
    assert not any(parcel.order_id == order.id for parcel in world.economy.parcels.values())
    world.economy.validate(world)
    world.knowledge.validate(world)

    # A third party crossing the same post is untouched by the measure.
    assert not is_embargoed(world, OPERATOR, EntityRef("polity", "valedouro"))
    assert world.map.get_route_operational_capacity(ROUTE) > 0, "a rota nunca foi fechada"


async def test_the_target_learns_only_from_its_own_returned_cargo():
    world = await prepared_world()
    declare(world)
    target_ref = EntityRef("polity", TARGET)

    # The declaration itself tells the target nothing.
    assert not [item for item in world.knowledge.customs_notices.values()
                if item.recipient_ref == target_ref]
    assert not any(event.event_type == "trade_embargo_declared"
                   and item.recipient_ref == target_ref
                   for event in world.events
                   for item in world.knowledge.customs_notices.values())

    order = ship(world)
    await MedievalSimulator(world).step()
    notice = next(item for item in world.knowledge.customs_notices.values() if item.order_id == order.id)
    assert notice.recipient_ref == target_ref and notice.state == "refused"

    # No memory and no retaliation was manufactured from the measure. Other
    # verticals keep acting on their own reasons; nothing points at ours.
    assert not world.relations.memories
    embargo_events = {item.id for item in world.events
                      if item.event_type in {"trade_embargo_declared", "customs_refused"}}
    assert not [item for item in world.events
                if item.fact_kind == FactKind.DECISION
                and embargo_events & {link.cause_event_id for link in item.causal_links}]


async def test_the_refused_order_keeps_its_remaining_answers(tmp_path):
    world = await prepared_world()
    declare(world)
    order = ship(world)
    await MedievalSimulator(world).step()

    from src.sim.medieval.freight_recovery import (execute_freight_recovery,
                                                   freight_recovery_options, refused_routes)

    kept = world.economy.freight_orders[order.id]
    assert kept.delivered_quantity == 0
    assert kept.route_ids == order.route_ids, "a ordem histórica não foi reescrita"
    # Logistics accounts for every unit, so a cargo that left the road is
    # resolved; the answer is a successor order, never a rewrite.
    assert kept.resolved_quantity == order.quantity
    world.economy.validate(world)

    # The refusal is itself a canonical reason to avoid that passage, so the
    # recovery owner now sees it exactly as it sees a closed road.
    assert refused_routes(world, kept) == (ROUTE,)

    # Recovery has always been limited to an owner's *internal* transfer
    # (``_recoverable`` requires both ends to be its own). Cross-owner trade
    # never had it, embargo or not, so the measure removes no answer: this
    # asserts the pre-existing boundary rather than pretending it changed.
    owner = kept.owner_ref
    assert world.economy.stocks[kept.source_id].owner_ref != owner
    assert not [item for item in freight_recovery_options(world, owner)
                if item.order_id == kept.id]

    # And the refusal reason is scoped to the order it belongs to: an
    # untouched order reports no refused passage at all.
    other = ship(world, quantity=5)
    assert refused_routes(world, world.economy.freight_orders[other.id]) == ()

    path = tmp_path / "embargo.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert embargoes_of(resumed, OPERATOR) == (TARGET,)
    resumed.authority.validate(resumed)


async def test_the_measure_is_part_of_the_composed_civil_menu():
    """It travels with the civil family, not as a second consultation."""
    from src.sim.medieval.concurrent_civil_decision import CIVIL_ADAPTERS, concurrent_civil_options

    world = await prepared_world()
    assert "trade_embargo" in {adapter.name for adapter in CIVIL_ADAPTERS}
    civil = [item for item in concurrent_civil_options(world, OPERATOR)
             if getattr(item, "target_id", None) is not None]
    assert civil, "a medida aparece no menu civil composto"
    assert {item.id for item in civil} == {item.id for item in embargo_options(world, OPERATOR)}


async def test_the_measure_reaches_the_single_composed_institutional_menu():
    """The menu the actor actually receives is the monthly composed one."""
    from src.sim.medieval.institutional_agenda import monthly_actors, monthly_adapters
    from src.sim.medieval.institutional_decision_turn import _by_id

    world = await prepared_world()
    adapters = monthly_adapters()
    assert "trade_embargo" in {adapter.name for adapter in adapters}
    assert OPERATOR in monthly_actors(world)

    composed = _by_id(world, OPERATOR, adapters)
    offered = [option for option, in ((item[1],) for item in composed.values())
               if getattr(option, "target_id", None) is not None]
    assert offered, "a medida aparece no menu único do ator"
    assert {item.target_id for item in offered} == set(world.society.polities) - {OPERATOR.id}

    # It is registered exactly once: a second registration would make the same
    # affordance answerable twice in one turn.
    assert [adapter.name for adapter in adapters].count("trade_embargo") == 1


async def test_a_stale_choice_through_the_composed_menu_fails_closed(monkeypatch):
    """Same fail-closed contract, exercised through the real monthly menu."""
    from src.sim.medieval.institutional_agenda import monthly_adapters

    world = await prepared_world()
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item for item in payload["choices"]
                       if item["label"].startswith("Recusar a carga")), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["id"])
        world.economy.customs_checkpoints.pop(CHECKPOINT)
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, OPERATOR, monthly_adapters())
    assert len(chosen) == 1
    assert embargoes_of(world, OPERATOR) == ()


async def test_a_stale_embargo_choice_fails_closed(monkeypatch):
    world = await prepared_world()
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item for item in payload["choices"]
                       if item["label"].startswith("Recusar a carga")), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["id"])
        # The post stops being staffed while the actor answers.
        world.economy.customs_checkpoints.pop(CHECKPOINT)
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, OPERATOR, embargo_adapters())
    assert len(chosen) == 1
    assert embargoes_of(world, OPERATOR) == ()

    decision = next((item for item in world.events
                     if item.event_type == "institutional_decision_turn_decided"), None)
    if decision is not None:
        assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}
