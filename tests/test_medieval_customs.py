"""Focused proof for presentation, declaration, and civil fee evasion.

The fixture uses the existing mountain passage.  It proves neither blockade
nor confiscation: every path preserves the exact parcel and its quantity.
"""

import asyncio

import pytest

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
    declare_customs_manifest,
    inspect_waiting_parcel,
    _checkpoint_for_route,
    open_customs_checkpoint,
    pay_customs_fee,
)
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.logistics import open_order
from src.sim.medieval.persistence import SCHEMA, load_world, save_world, world_snapshot
from src.sim.simulator_engine.month_transaction import SimulationMonthCheckpoint


SITE = "passagem-negra"
ROUTE = "road-pontenegro-ferroalto"


def decided(world, option, event_type="customs_decided"):
    return record_event(world, event_type, "Decisão civil preparada.", fact_kind=FactKind.DECISION,
                        decision=option.decision())


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
    world = load_world(path)
    assert SCHEMA == 32
    option = customs_payment_options(world, order.owner_ref)[0]
    payment = pay_customs_fee(world, option.id, decision_event_id=decided(world, option, "customs_fee_decided").id)
    released = world.economy.parcels[parcel.id]
    assert released.id == parcel.id and released.quantity == parcel.quantity and released.stage == "waiting"
    assert released.held_checkpoint_id is None and released.held_notice_id is None
    assert world.knowledge.customs_notices[notice.id].state == "cleared"
    assert payment.event_type == "customs_fee_paid"
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
    detected = attempt_customs_fee_evasion(world, option.id, decision_event_id=decided(world, option).id)
    notice = world.knowledge.customs_notices[notice.id]
    checkpoint = world.economy.customs_checkpoints[notice.checkpoint_id]
    assert detected.event_type == "customs_fee_evasion_detected"
    assert world.economy.parcels[parcel.id].stage == "held" and notice.state == "detected"
    assert checkpoint.inspection_slots_used == 1
    assert {delta.aspect for delta in detected.deltas if delta.owner_kind == "customs_inspection"} == {
        "roll_permille", "threshold_permille"}

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
