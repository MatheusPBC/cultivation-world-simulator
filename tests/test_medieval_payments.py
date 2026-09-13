"""Money cannot leave an owner's account through another actor's intent."""

import pytest

from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import transfer_money
from src.sim.medieval.events import record_event
from src.sim.medieval.persistence import load_world, save_world, world_snapshot


@pytest.mark.parametrize("actor", [None, {"kind": "polity", "id": "valedouro"}])
def test_payment_requires_the_account_owners_explicit_intent(actor):
    world = create_medieval_world(73)
    intent = {"action": "pay", "source_id": "treasury:auren", "target_id": "treasury:valedouro", "amount": 17}
    if actor is not None:
        intent["actor_ref"] = actor
    decision = record_event(world, "payment_decided", "Solicitação de pagamento.",
                            fact_kind=FactKind.DECISION, decision=intent)
    before, history = world_snapshot(world), list(world.events)
    with pytest.raises(ValueError, match="decision"):
        transfer_money(world, "treasury:auren", "treasury:valedouro", 17, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    assert world.events == history


def test_payment_decision_expires_with_its_day_and_a_current_one_executes(tmp_path):
    world = create_medieval_world(73)
    terms = {"action": "pay", "source_id": "treasury:auren", "target_id": "treasury:valedouro",
             "amount": 17, "actor_ref": {"kind": "polity", "id": "auren"}}
    stale = record_event(world, "payment_decided", "Intenção de pagamento do dia anterior.",
                         fact_kind=FactKind.DECISION, decision=dict(terms))
    path = tmp_path / "payment.mws"
    save_world(world, path)
    world = load_world(path)
    world.clock = world.clock.advance(1)
    before, history, saved = world_snapshot(world), list(world.events), path.read_bytes()
    with pytest.raises(ValueError, match="decision"):
        transfer_money(world, "treasury:auren", "treasury:valedouro", 17, decision_event_id=stale.id)
    assert world_snapshot(world) == before
    assert world.events == history
    assert path.read_bytes() == saved
    assert stale.id not in world.economy.payments
    source, target = world.economy.accounts["treasury:auren"], world.economy.accounts["treasury:valedouro"]
    total = sum(a.balance for a in world.economy.accounts.values())
    current = record_event(world, "payment_decided", "Intenção de pagamento de hoje.",
                           fact_kind=FactKind.DECISION, decision=dict(terms))
    transfer_money(world, "treasury:auren", "treasury:valedouro", 17, decision_event_id=current.id)
    receipt = world.events[-1]
    assert world.economy.accounts["treasury:auren"].balance == source.balance - 17
    assert world.economy.accounts["treasury:valedouro"].balance == target.balance + 17
    assert sum(a.balance for a in world.economy.accounts.values()) == total
    assert world.economy.payments[current.id] == receipt.id and stale.id not in world.economy.payments
    assert current.id in {link.cause_event_id for link in receipt.causal_links}
    assert all(world.economy.accounts[a].last_event_id == receipt.id for a in ("treasury:auren", "treasury:valedouro"))
    assert world_snapshot(world)["event_count"] == before["event_count"] + 2


@pytest.mark.parametrize("revocation", ["expired", "scope_removed"])
def test_payment_rechecks_current_mandate_after_save_load(tmp_path, revocation):
    world = create_medieval_world(73)
    decision = record_event(world, "payment_decided", "Intenção de pagamento.", fact_kind=FactKind.DECISION,
                            decision={"action": "pay", "source_id": "treasury:auren",
                                      "target_id": "treasury:valedouro", "amount": 17,
                                      "actor_ref": {"kind": "polity", "id": "auren"}})
    office = world.authority.offices["office:polity:auren"]
    change = {"ends_day": 0} if revocation == "expired" else {"scopes": ("supply",)}
    world.authority.offices[office.id] = office.model_copy(update=change)
    path = tmp_path / "mandate.mws"
    save_world(world, path)
    world = load_world(path)
    before, history, saved = world_snapshot(world), list(world.events), path.read_bytes()
    with pytest.raises(ValueError, match="authority"):
        transfer_money(world, "treasury:auren", "treasury:valedouro", 17, decision_event_id=decision.id)
    assert world_snapshot(world) == before
    assert world.events == history
    assert path.read_bytes() == saved
