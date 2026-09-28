"""Direct material commands must publish receipts and causes atomically."""

import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.material_execution import execute_material
from src.sim.medieval.persistence import world_snapshot


def test_direct_material_boundary_rejects_silent_mutation():
    world = create_medieval_world(73)
    before = world_snapshot(world)

    def silently_change_cash(candidate):
        account = candidate.economy.accounts["treasury:auren"]
        candidate.economy.accounts[account.id] = account.model_copy(
            update={"balance": account.balance + 1})

    with pytest.raises(ValueError, match="state-transition receipt"):
        execute_material(world, silently_change_cash)

    assert world_snapshot(world) == before


def test_direct_material_boundary_rejects_rootless_transition():
    world = create_medieval_world(73)
    before = world_snapshot(world)

    def change_without_cause(candidate):
        account = candidate.economy.accounts["treasury:auren"]
        event = record_event(
            candidate, "unattributed_cash_changed", "Mudança sem causa.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("account", account.id, "balance",
                           account.balance, account.balance + 1),),
        )
        candidate.economy.accounts[account.id] = account.model_copy(
            update={"balance": account.balance + 1, "last_event_id": event.id})

    with pytest.raises(ValueError, match="recorded cause"):
        execute_material(world, change_without_cause)

    assert world_snapshot(world) == before
