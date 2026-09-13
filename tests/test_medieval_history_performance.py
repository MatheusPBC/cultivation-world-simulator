"""History optimizations must retain isolation and reject invalid event candidates."""

import copy
import pytest

from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.events import record_event


def test_event_clone_validates_corrupted_payload_before_it_can_enter_candidate():
    world = create_medieval_world(73)
    event = record_event(world, "observed", "Um fato observado.")
    corrupted = event.model_copy(update={"content": None})
    with pytest.raises(ValueError):
        copy.deepcopy(corrupted)
    assert event.content == "Um fato observado."


def test_event_clone_isolates_nested_decision_and_causal_evidence():
    world = create_medieval_world(73)
    decision = record_event(world, "choice", "Intenção de teste.", fact_kind=FactKind.DECISION,
                            decision={"parameters": {"routes": ["road-a"], "amount": 17}})
    effect = record_event(world, "effect", "Efeito de teste.", fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(StateDelta(owner_kind="stock", owner_id="s", aspect="food", before="1", after="2"),),
                          cause_ids=(decision.id,))
    effect.causal_links[0].note_params = {"nested": {"source": ["report-a"]}}
    clones = copy.deepcopy([decision, effect])
    assert [e.model_dump(mode="json") for e in clones] == [e.model_dump(mode="json") for e in (decision, effect)]
    clones[0].decision["parameters"]["routes"].append("road-b")
    clones[1].deltas[0].after = "999"
    clones[1].causal_links[0].note_params["nested"]["source"].append("report-b")
    assert decision.decision["parameters"]["routes"] == ["road-a"]
    assert effect.deltas[0].after == "2"
    assert effect.causal_links[0].note_params["nested"]["source"] == ["report-a"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_clone_does_not_silently_turn_nonfinite_decision_data_into_null(bad):
    world = create_medieval_world(73)
    event = record_event(world, "choice", "Intenção.", fact_kind=FactKind.DECISION,
                         decision={"quantity": 1})
    event.decision["quantity"] = bad
    with pytest.raises(ValueError):
        copy.deepcopy(event)


def test_cargo_batch_reads_route_history_once_and_next_batch_observes_new_causes():
    from src.sim.medieval.logistics import resolve_parcels
    from src.systems.time import WorldClock
    from tests.test_medieval_logistics import cargo_world, ship, ROAD

    class CountedHistory(list):
        inspected = 0

        def __reversed__(self):
            for event in super().__reversed__():
                self.inspected += 1
                yield event

    world = cargo_world()
    ship(world, 40)
    ship(world, 40)
    world.events = CountedHistory(world.events)
    # A closure delays both parcels. A later reopening must replace its cause;
    # unrelated history must not be rescanned separately for every parcel.
    for day, enabled, expected_type in [(1, False, "cargo_delayed"), (2, True, "cargo_departed")]:
        world.clock = WorldClock(day)
        world.map.routes[ROAD].update_runtime(enabled=enabled)
        change = record_event(world, "route_changed", "Passagem alterada.",
                              fact_kind=FactKind.STATE_TRANSITION,
                              deltas=(StateDelta(owner_kind="route", owner_id=ROAD,
                                                 aspect="enabled", before=str(not enabled), after=str(enabled)),))
        for _ in range(100):
            record_event(world, "observed", "Fato sem relação com a passagem.")
        start = len(world.events)
        world.events.inspected = 0
        resolve_parcels(world, world.agenda.pop_due(day))
        effects = world.events[start:]
        assert len(effects) == 2
        assert all(e.event_type == expected_type for e in effects)
        assert all(change.id in {link.cause_event_id for link in e.causal_links} for e in effects)
        assert world.events.inspected <= start
    assert sum(p.quantity for p in world.economy.parcels.values() if p.stage == "traveling") == 80
