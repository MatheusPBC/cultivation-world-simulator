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


def test_recording_a_cause_addresses_its_event_without_traversing_the_history():
    class TraversedHistory(list):
        traversals = 0

        def __iter__(self):
            self.traversals += 1
            return super().__iter__()

        def __reversed__(self):
            self.traversals += 1
            return super().__reversed__()

    world = create_medieval_world(73)
    cause = record_event(world, "observed", "Fato que será citado como causa.")
    for _ in range(200):
        record_event(world, "observed", "Fato sem relação com a causa.")
    world.events = TraversedHistory(world.events)
    world.events.traversals = 0
    effect = record_event(world, "effect", "Efeito do fato citado.", fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(StateDelta(owner_kind="stock", owner_id="s", aspect="food", before="1", after="2"),),
                          cause_ids=(cause.id,))
    assert [link.cause_event_id for link in effect.causal_links] == [cause.id]
    assert world.events[-1] is effect
    assert world.events.traversals == 0


def test_transaction_copy_shares_only_the_validated_event_prefix_and_isolates_state():
    world = create_medieval_world(73)
    event = record_event(world, "observed", "Fato existente.")

    candidate = world.transaction_copy()
    assert candidate is not world
    assert candidate.events is not world.events
    assert candidate.events == world.events
    # The append-only prefix may be shared for speed; newly committed facts
    # still belong exclusively to the candidate's event list.
    assert candidate.events[0] is event
    record_event(candidate, "candidate_only", "Fato candidato.")
    assert len(candidate.events) == len(world.events) + 1
    assert len(world.events) == 1

    candidate.clock = candidate.clock.advance(1)
    assert candidate.clock.absolute_day != world.clock.absolute_day


def test_transaction_copy_isolates_registry_values_and_config_budget():
    world = create_medieval_world(73)
    stock = next(iter(world.economy.stocks.values()))
    population = next(iter(world.society.population.values()))
    candidate = world.transaction_copy()

    assert candidate.economy is not world.economy
    assert candidate.economy.stocks is not world.economy.stocks
    assert candidate.economy.stocks[stock.id] is not stock
    assert candidate.economy.stocks[stock.id].goods is not stock.goods
    assert candidate.society.population[population.id] is not population
    assert candidate.config is not world.config
    assert candidate.config.institutional_actions_consumed is not world.config.institutional_actions_consumed

    candidate.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": stock.goods.get("food", 0) + 1}}
    )
    candidate.society.population[population.id] = population.model_copy(update={"count": population.count + 1})
    candidate.config = candidate.config.model_copy(
        update={"institutional_actions_consumed": {"polity:x:0": 1}}
    )

    assert candidate.economy.stocks[stock.id].goods != world.economy.stocks[stock.id].goods
    assert candidate.society.population[population.id].count != world.society.population[population.id].count
    assert world.config.institutional_actions_consumed == {}


def test_transaction_copy_isolates_map_runtime_but_shares_authored_topology():
    world = create_medieval_world(73)
    route = next(iter(world.map.routes.values()))
    site = next(iter(world.map.infrastructure_sites.values()))
    candidate = world.transaction_copy()

    assert candidate.map is not world.map
    assert candidate.map.geography is world.map.geography
    assert candidate.map.regions is world.map.regions
    assert candidate.map.routes[route.id] is not route
    assert candidate.map.infrastructure_sites[site.id] is not site

    candidate.map.routes[route.id].update_runtime(quality=max(0.0, route.quality - 0.1))
    candidate.map.infrastructure_sites[site.id].update_runtime(integrity=0.5)
    candidate.map.force_route_interdictors[route.id] = "candidate-interdictor"
    candidate.map._infrastructure_site_updates.append({"op": "candidate"})

    assert world.map.routes[route.id].quality == route.quality
    assert world.map.infrastructure_sites[site.id].integrity == site.integrity
    assert route.id not in world.map.force_route_interdictors
    assert not world.map._infrastructure_site_updates


def test_event_equality_accepts_json_list_round_trip_for_tuple_decisions():
    world = create_medieval_world(73)
    event = record_event(
        world,
        "decision",
        "Escolha estruturada.",
        fact_kind=FactKind.DECISION,
        decision={"action": "no_action", "declined_option_ids": ("a", "b")},
    )
    loaded = type(event).model_validate(event.model_dump(mode="json"))
    assert event == loaded


@pytest.mark.parametrize("cause", ["event:0", "event:01", "event: 1", "event:1.0", "event:one", "event:",
                                   "evento:1", "event:1:delta:0", "", None, "future"])
def test_record_event_rejects_malformed_unknown_or_repeated_causes(cause):
    world = create_medieval_world(73)
    known = record_event(world, "observed", "Fato existente.")
    if cause == "future":
        cause = f"event:{len(world.events) + 1}"
    before = len(world.events)
    for causes in ((cause,), (known.id, cause), (known.id, known.id)):
        with pytest.raises(ValueError, match="cause"):
            record_event(world, "effect", "Efeito com causa inválida.", cause_ids=causes)
    assert len(world.events) == before
    assert record_event(world, "effect", "Efeito com causa válida.", cause_ids=(known.id,)).causal_links[0].cause_event_id == known.id


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
