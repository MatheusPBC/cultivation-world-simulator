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
