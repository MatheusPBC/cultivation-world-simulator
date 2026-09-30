"""Focused proof for presentation, declaration, evasion, return and seizure.

The fixture uses the existing mountain passage. Blockade remains a separate
force owner; seizure is only possible through an explicit operator decision.
"""

import asyncio
import json
from contextlib import closing
import sqlite3

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.customs import (
    CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY,
    attempt_customs_fee_evasion,
    checkpoint_active,
    customs_cargo_options,
    customs_open_options,
    customs_payment_options,
    customs_seizure_options,
    declare_customs_manifest,
    inspect_waiting_parcel,
    _checkpoint_for_route,
    open_customs_checkpoint,
    pay_customs_fee,
    return_contraband_cargo,
)
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval import ai_decider
from src.sim.medieval.logistics import open_order
from src.sim.medieval.persistence import SCHEMA, load_world, save_world, world_snapshot
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint


SITE = "passagem-negra"
ROUTE = "road-pontenegro-ferroalto"


def decided(world, option, event_type="customs_decided"):
    return record_event(world, event_type, "Decisão civil preparada.", fact_kind=FactKind.DECISION,
                        causal_origin=CausalOrigin.ACTOR_DECISION, decision=option.decision(),
                        causal_payload={"decision_source": {"kind": "api"}})


def prepared_world():
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.strategy.objectives.clear()
    actor = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, actor)[0]
    open_customs_checkpoint(world, option.id, decision_event_id=decided(world, option, "customs_open_decided").id)
    asyncio.run(MedievalSimulator(world).step())
    assert checkpoint_active(world, world.economy.customs_checkpoints[f"customs:{SITE}"])
    return world


def test_deterministic_intent_cannot_open_a_customs_checkpoint():
    world = create_medieval_world(73)
    actor = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, actor)[0]
    decision = record_event(world, "customs_open_decided", "Intenção determinística de teste.",
                            fact_kind=FactKind.DECISION, decision=option.decision())
    before = world_snapshot(world)

    with pytest.raises(ValueError, match="stale"):
        open_customs_checkpoint(world, option.id, decision_event_id=decision.id)

    assert world_snapshot(world) == before


def presented_parcel(world):
    decision = record_event(world, "freight_decided", "Despachar carga preparada.",
                            fact_kind=FactKind.DECISION, decision={"action": "prepared_freight"})
    order = open_order(world, "stock:ferroalto", "stock:pontenegro", "food", 10, [ROUTE],
                       decision_ids=(decision.id,))
    asyncio.run(MedievalSimulator(world).step())
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    notice = world.knowledge.customs_notices[f"customs_notice:{parcel.id}"]
    assert parcel.stage == "held" and notice.state == "presented"
    return order, parcel, notice


def declared_parcel(world):
    order, parcel, notice = presented_parcel(world)
    actor = order.owner_ref
    option = next(item for item in customs_cargo_options(world, actor) if item.action == "declare_customs_manifest")
    event = declare_customs_manifest(world, option.id, decision_event_id=decided(world, option).id)
    return order, parcel, world.knowledge.customs_notices[notice.id], event


def test_presentation_then_manifest_payment_releases_same_parcel_and_survives_save(tmp_path):
    world = prepared_world()
    order, parcel, notice, declaration = declared_parcel(world)
    manifest = world.economy.cargo_manifests[f"cargo_manifest:{parcel.id}"]
    assert notice.state == "fee_due" and notice.fee is not None
    assert (manifest.parcel_id, manifest.order_id, manifest.resource_id, manifest.quantity) == (
        parcel.id, order.id, "food", 10)
    assert declaration.event_type == "cargo_manifest_declared"

    path = tmp_path / "customs.mws"
    save_world(world, path)
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        assert conn.execute("SELECT schema_version FROM metadata WHERE id=1").fetchone() == (SCHEMA,)
    world = load_world(path)
    option = customs_payment_options(world, order.owner_ref)[0]
    payment = pay_customs_fee(world, option.id, decision_event_id=decided(world, option, "customs_fee_decided").id)
    released = world.economy.parcels[parcel.id]
    assert released.id == parcel.id and released.quantity == parcel.quantity and released.stage == "waiting"
    assert released.held_checkpoint_id is None and released.held_notice_id is None
    assert world.knowledge.customs_notices[notice.id].state == "cleared"
    assert payment.event_type == "customs_fee_paid"
    world.economy.validate(world)
    world.knowledge.validate(world)


def test_customs_evasion_is_an_actor_choice_in_the_full_monthly_menu(monkeypatch):
    from src.sim.medieval.institutional_agenda import (monthly_actors, monthly_adapters,
                                                        review_monthly_institutional_turn)
    from src.sim.medieval.institutional_decision_turn import _by_id

    world = prepared_world()
    order, parcel, notice = presented_parcel(world)
    notice = world.knowledge.customs_notices[f"customs_notice:{parcel.id}"]
    assert notice.classification == "ordinary" and notice.state == "presented"
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 256,
                                                    "ai_max_calls": 1000})
    actor = order.owner_ref
    adapters = monthly_adapters()
    assert "customs" in {adapter.name for adapter in adapters}
    assert actor in monthly_actors(world)
    options = _by_id(world, actor, adapters)
    option = next(option for _, option in options.values()
                  if getattr(option, "action", None) == "attempt_customs_fee_evasion"
                  and option.parcel_id == parcel.id)
    assert any(getattr(candidate, "action", None) == "declare_customs_manifest"
               and candidate.parcel_id == parcel.id for _, candidate in options.values())
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr(type(world.rng), "randrange", lambda _rng, _n: 0)
    selected = []

    async def choose_customs_evasion(prompt, *_args, **_kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        choice = next((item for item in payload["choices"] if item["id"] == option.id), None)
        if payload["you_are"]["id"] == actor.id and choice is not None:
            selected.append(choice["id"])
            return {"selected_id": choice["id"]}
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_customs_evasion)
    asyncio.run(review_monthly_institutional_turn(world))

    assert selected == [option.id]
    assert world.knowledge.customs_notices[notice.id].state == "detected"
    decision = next(item for item in world.events if item.decision == option.decision())
    detection = next(item for item in world.events
                     if item.event_type == "customs_fee_evasion_detected")
    assert decision.id in {link.cause_event_id for link in detection.causal_links}


def test_presentation_classifies_catalogued_contraband_without_inventing_a_material_result():
    world = prepared_world()
    stock = world.economy.stocks["stock:ferroalto"]
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "weapons": 10},
    })
    decision = record_event(world, "freight_decided", "Despachar armamentos preparados.",
                            fact_kind=FactKind.DECISION, decision={"action": "prepared_freight"})
    order = open_order(world, "stock:ferroalto", "stock:pontenegro", "weapons", 2, [ROUTE],
                       decision_ids=(decision.id,))
    asyncio.run(MedievalSimulator(world).step())
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    notice = world.knowledge.customs_notices[f"customs_notice:{parcel.id}"]
    assert notice.classification == "contraband"
    presentation = next(event for event in world.events if event.id == notice.event_id)
    assert any(delta.owner_kind == "customs_notice" and delta.aspect == "classification"
               and delta.after == "contraband" for delta in presentation.deltas)
    from src.server.medieval.queries import causal_view
    classification_why = causal_view(world, presentation.id)
    assert classification_why.event.id == presentation.id
    assert any(delta.aspect == "classification" and delta.after == "contraband"
               for delta in classification_why.event.deltas)
    assert parcel.stage == "held" and notice.state == "presented"


def test_owner_can_explicitly_return_contraband_to_source_stock(tmp_path):
    world = prepared_world()
    stock = world.economy.stocks["stock:ferroalto"]
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, "weapons": 10},
    })
    decision = record_event(world, "freight_decided", "Despachar armamentos preparados.",
                            fact_kind=FactKind.DECISION, decision={"action": "prepared_freight"})
    order = open_order(world, "stock:ferroalto", "stock:pontenegro", "weapons", 2, [ROUTE],
                       decision_ids=(decision.id,))
    asyncio.run(MedievalSimulator(world).step())
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    notice = world.knowledge.customs_notices[f"customs_notice:{parcel.id}"]
    option = next(item for item in customs_cargo_options(world, order.owner_ref)
                  if item.action == "return_contraband_cargo")
    source_before = world.economy.stocks[order.source_id].goods[order.resource_id]
    decision = decided(world, option, "contraband_return_decided")
    returned = return_contraband_cargo(world, option.id, decision_event_id=decision.id)
    assert returned.event_type == "contraband_returned"
    assert parcel.id not in world.economy.parcels
    assert world.economy.stocks[order.source_id].goods[order.resource_id] == source_before + parcel.quantity
    assert world.economy.freight_orders[order.id].resolved_quantity == parcel.quantity
    assert world.knowledge.customs_notices[notice.id].state == "returned"
    assert decision.id in {link.cause_event_id for link in returned.causal_links}
    save_world(world, tmp_path / "contraband-return.mws")
    world.economy.validate(world)
    world.knowledge.validate(world)


@pytest.mark.asyncio
async def test_checkpoint_owner_chooses_contraband_seizure_in_monthly_menu(monkeypatch):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.strategy.objectives.clear()
    actor = world.map.infrastructure_sites[SITE].owner_ref
    open_option = customs_open_options(world, SITE, actor)[0]
    open_customs_checkpoint(world, open_option.id,
                            decision_event_id=decided(world, open_option, "customs_open_decided").id)
    await MedievalSimulator(world).step()
    assert checkpoint_active(world, world.economy.customs_checkpoints[f"customs:{SITE}"])
    source = world.economy.stocks["stock:ferroalto"]
    world.economy.stocks[source.id] = source.model_copy(update={
        "goods": {**source.goods, "weapons": 10},
    })
    decision = record_event(world, "freight_decided", "Despachar armamentos preparados.",
                            fact_kind=FactKind.DECISION, decision={"action": "prepared_freight"})
    order = open_order(world, "stock:ferroalto", "stock:pontenegro", "weapons", 2, [ROUTE],
                       decision_ids=(decision.id,))
    await MedievalSimulator(world).step()
    parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
    notice = world.knowledge.customs_notices[f"customs_notice:{parcel.id}"]
    # The catalogued contraband classification is evidence. It still needs the
    # checkpoint operator's own decision before ownership/material custody changes.
    operator = world.economy.customs_checkpoints[notice.checkpoint_id].operator_ref
    seizure = customs_seizure_options(world, operator)
    assert seizure and all(item.actor_ref == operator for item in seizure)
    assert len(seizure) == 1, "o menu deve distinguir inequivocamente o destino de estoque"
    target = seizure[0]
    before = world.economy.stocks[target.destination_stock_id].goods.get("weapons", 0)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 256,
                                                    "ai_max_calls": 1000})
    from src.sim.medieval.institutional_agenda import (monthly_actors, monthly_adapters,
                                                        review_monthly_institutional_turn)
    from src.sim.medieval.institutional_decision_turn import _by_id

    adapters = monthly_adapters()
    assert operator in monthly_actors(world)
    customs_adapter = next(item for item in adapters if item.name == "customs")
    label = customs_adapter.label_fn(target)
    current = _by_id(world, operator, adapters)
    assert target.id in current
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    selected = []

    async def choose_seizure(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        choice = next((item for item in payload["choices"] if item["label"] == label), None)
        if payload["you_are"]["id"] == operator.id and choice is not None:
            selected.append(target.id)
            return {"selected_id": choice["id"]}
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_seizure)
    await review_monthly_institutional_turn(world)

    assert selected == [target.id]
    decision = next(item for item in world.events
                    if item.fact_kind is FactKind.DECISION and item.decision == target.decision())
    assert decision.causal_origin is CausalOrigin.ACTOR_DECISION
    assert decision.causal_payload["decision_source"]["kind"] == "provider"
    event = next(item for item in world.events
                 if item.event_type == "contraband_seized"
                 and decision.id in {link.cause_event_id for link in item.causal_links})
    assert event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert event.causal_payload == {
        "decision_event_id": decision.id,
        "actor_ref": operator.to_dict(),
        "selected_affordance_id": target.id,
    }
    assert event.event_type == "contraband_seized"
    assert parcel.id not in world.economy.parcels
    assert world.economy.stocks[target.destination_stock_id].goods["weapons"] == before + parcel.quantity
    assert world.economy.freight_orders[order.id].resolved_quantity == parcel.quantity
    assert world.knowledge.customs_notices[notice.id].state == "seized"
    from src.server.medieval.queries import causal_view
    why = causal_view(world, event.id)
    assert decision.id in {item.id for item in why.causes}
    assert any(delta.owner_kind == "stock" and delta.owner_id == target.destination_stock_id
               and delta.aspect == "weapons" and int(delta.after) - int(delta.before) == parcel.quantity
               for delta in why.event.deltas)
    world.economy.validate(world)
    world.knowledge.validate(world)


@pytest.mark.parametrize("failure", ["invented", "stale", "authority", "damaged", "suspended", "owner_lost"])
def test_manifest_executor_revalidates_current_option_without_mutation(failure):
    world = prepared_world()
    order, parcel, _ = presented_parcel(world)
    option = next(item for item in customs_cargo_options(world, order.owner_ref)
                  if item.action == "declare_customs_manifest")
    if failure == "invented":
        option = option.model_copy(update={"id": option.id + ":invented"})
    elif failure == "stale":
        world.clock = world.clock.advance(1)
    elif failure == "authority":
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"ends_day": world.clock.absolute_day})
    elif failure in {"damaged", "suspended"}:
        field, value = ("integrity", 0.9) if failure == "damaged" else ("service_suspended", True)
        site = world.map.infrastructure_sites[SITE]
        fact = record_event(
            world, "site_changed", "Serviço alterado.", fact_kind=FactKind.STATE_TRANSITION,
            deltas=(StateDelta(owner_kind="site", owner_id=site.id, aspect=field,
                               before=str(getattr(site, field)), after=str(value)),),
        )
        world.map.update_infrastructure_site_runtime(site.id, **{field: value, "last_event_id": fact.id})
    else:
        site = world.map.infrastructure_sites[SITE]
        world.map.infrastructure_sites[SITE] = type(site).from_dict({
            **site.to_dict(), "owner_ref": {"kind": "polity", "id": "valedouro"},
        })
    decision = decided(world, option)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="customs"):
        declare_customs_manifest(world, option.id, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    assert world.economy.parcels[parcel.id].stage == "held"


def test_detected_evasion_keeps_cargo_held_then_legal_declaration_and_payment(monkeypatch):
    world = prepared_world()
    order, parcel, notice = presented_parcel(world)
    option = next(item for item in customs_cargo_options(world, order.owner_ref)
                  if item.action == "attempt_customs_fee_evasion")
    monkeypatch.setattr(type(world.rng), "randrange", lambda _rng, _n: 0)
    decision = decided(world, option)
    detected = attempt_customs_fee_evasion(world, option.id, decision_event_id=decision.id)
    notice = world.knowledge.customs_notices[notice.id]
    checkpoint = world.economy.customs_checkpoints[notice.checkpoint_id]
    assert detected.event_type == "customs_fee_evasion_detected"
    assert world.economy.parcels[parcel.id].stage == "held" and notice.state == "detected"
    assert checkpoint.inspection_slots_used == 1
    assert {delta.aspect for delta in detected.deltas if delta.owner_kind == "customs_inspection"} == {
        "roll_permille", "threshold_permille"}
    from src.server.medieval.queries import causal_view
    detection_why = causal_view(world, detected.id)
    assert decision.id in {item.id for item in detection_why.causes}
    assert any(delta.aspect == "state" and delta.after == "detected"
               for delta in detection_why.event.deltas)

    declaration = next(item for item in customs_cargo_options(world, order.owner_ref)
                       if item.action == "declare_customs_manifest")
    declare_customs_manifest(world, declaration.id, decision_event_id=decided(world, declaration).id)
    payment = customs_payment_options(world, order.owner_ref)[0]
    pay_customs_fee(world, payment.id, decision_event_id=decided(world, payment).id)
    assert world.economy.parcels[parcel.id].stage == "waiting"


def test_capacity_exhaustion_is_undetected_without_rng_or_fee():
    world = prepared_world()
    order, parcel, notice = presented_parcel(world)
    checkpoint = world.economy.customs_checkpoints[notice.checkpoint_id]
    capacity = checkpoint.staff_count * CUSTOMS_INSPECTIONS_PER_STAFF_PER_DAY
    world.economy.customs_checkpoints[checkpoint.id] = checkpoint.model_copy(
        update={"inspection_day": world.clock.absolute_day, "inspection_slots_used": capacity})
    option = next(item for item in customs_cargo_options(world, order.owner_ref)
                  if item.action == "attempt_customs_fee_evasion")
    rng_before = world.rng.getstate()
    event = attempt_customs_fee_evasion(world, option.id, decision_event_id=decided(world, option).id)
    updated = world.economy.parcels[parcel.id]
    assert event.event_type == "customs_fee_evaded" and world.rng.getstate() == rng_before
    assert updated.stage == "waiting" and updated.quantity == parcel.quantity and updated.due_day == world.clock.absolute_day + 1
    assert world.knowledge.customs_notices[notice.id].state == "evaded_undetected"
    assert not customs_payment_options(world, order.owner_ref)


def test_fee_due_payment_rejects_insufficient_cash_without_releasing_parcel():
    world = prepared_world()
    order, parcel, notice, _ = declared_parcel(world)
    option = customs_payment_options(world, order.owner_ref)[0]
    account = world.economy.accounts[option.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    decision = decided(world, option, "customs_fee_decided")
    before_events = len(world.events)
    with pytest.raises(ValueError, match="customs payment"):
        pay_customs_fee(world, option.id, decision_event_id=decision.id)
    assert len(world.events) == before_events and world.economy.parcels[parcel.id].stage == "held"
    assert world.knowledge.customs_notices[notice.id].state == "fee_due"


def test_evasion_rng_state_survives_save_and_month_checkpoint_rollback(tmp_path):
    world = prepared_world()
    order, parcel, notice = presented_parcel(world)
    option = next(item for item in customs_cargo_options(world, order.owner_ref)
                  if item.action == "attempt_customs_fee_evasion")
    checkpoint = SimulationMonthCheckpoint.capture(world)
    attempt_customs_fee_evasion(world, option.id, decision_event_id=decided(world, option).id)
    after_attempt = world_snapshot(world)
    path = tmp_path / "rng-customs.mws"
    save_world(world, path)
    restored = load_world(path)
    assert restored.rng.getstate() == world.rng.getstate()
    assert restored.rng.randrange(1000) == world.rng.randrange(1000)
    checkpoint.restore()
    assert world.economy.parcels[parcel.id].stage == "held"
    assert world.knowledge.customs_notices[notice.id].state == "presented"
    assert world_snapshot(world) != after_attempt


def test_ambiguous_active_checkpoints_on_one_route_are_rejected():
    world = prepared_world()
    checkpoint = world.economy.customs_checkpoints[f"customs:{SITE}"]
    # Deliberately inject an invalid second registry member to prove the lookup
    # never picks a lexical winner when a malformed future map reaches it.
    duplicate = checkpoint.model_copy(update={"id": "customs:ambiguous", "site_id": SITE})
    world.economy.customs_checkpoints[duplicate.id] = duplicate
    payroll = world.economy.payrolls[checkpoint.id]
    world.economy.payrolls[duplicate.id] = payroll.model_copy(update={"id": duplicate.id})
    with pytest.raises(ValueError, match="ambiguous active customs"):
        _checkpoint_for_route(world, ROUTE)


def test_unstaffed_or_suspended_or_damaged_checkpoint_does_not_present_cargo():
    for field, value in (("enabled", False), ("service_suspended", True), ("integrity", 0.9)):
        world = prepared_world()
        site = world.map.infrastructure_sites[SITE]
        fact = record_event(
            world, "site_changed", "Serviço físico alterado.", fact_kind=FactKind.STATE_TRANSITION,
            deltas=(StateDelta(owner_kind="site", owner_id=site.id, aspect=field,
                               before=str(getattr(site, field)), after=str(value)),),
        )
        world.map.update_infrastructure_site_runtime(SITE, **{field: value, "last_event_id": fact.id})
        decision = record_event(world, "freight_decided", "Preparar carga.", fact_kind=FactKind.DECISION,
                                decision={"action": "prepared_freight"})
        order = open_order(world, "stock:ferroalto", "stock:pontenegro", "food", 10, [ROUTE],
                           decision_ids=(decision.id,))
        parcel = next(item for item in world.economy.parcels.values() if item.order_id == order.id)
        assert inspect_waiting_parcel(world, parcel, ROUTE) is None
        assert parcel.id not in {notice.parcel_id for notice in world.knowledge.customs_notices.values()}


@pytest.mark.asyncio
async def test_failed_durable_commit_restores_customs_staffing_and_opening(monkeypatch, tmp_path):
    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.strategy.objectives.clear()
    actor = world.map.infrastructure_sites[SITE].owner_ref
    option = customs_open_options(world, SITE, actor)[0]
    open_customs_checkpoint(world, option.id, decision_event_id=decided(world, option, "customs_open_decided").id)
    before = world_snapshot(world)
    events = list(world.events)

    def fail(*args, **kwargs):
        raise OSError("customs durable write failed")

    from src.sim.medieval import engine
    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="customs durable"):
        await MedievalSimulator(world, save_path=tmp_path / "customs.mws").step()
    assert world_snapshot(world) == before and world.events == events
