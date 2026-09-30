"""History optimizations must retain isolation and reject invalid event candidates."""

import copy
import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.state_delta import StateDelta
from src.sim.medieval.events import WorldEvent
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


def test_route_delta_index_matches_legacy_lookup_for_touched_and_untouched_routes():
    from src.sim.medieval.logistics import _route_causes
    from src.sim.medieval.economy import _causes

    world = create_medieval_world(73)
    touched, untouched = tuple(world.map.routes)[:2]
    first = record_event(
        world, "route_changed", "Primeira alteração de rota.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=touched, aspect="enabled",
                            before="True", after="False"),),
    )
    record_event(
        world, "observed", "Observação sem alteração de rota.",
    )

    def legacy(route_ids):
        pending = set(route_ids)
        latest = {}
        for event in reversed(world.events):
            for delta in event.deltas:
                if delta.owner_kind == "route" and delta.owner_id in pending:
                    latest[delta.owner_id] = event.id
                    pending.remove(delta.owner_id)
            if not pending:
                break
        return latest

    route_ids = (touched, untouched)
    expected_latest = legacy(route_ids)
    expected_causes = {
        route_id: _causes(expected_latest.get(route_id), *(s.last_event_id
            for s in world.map.infrastructure_sites.values() if route_id in s.route_ids))
        for route_id in route_ids
    }
    assert world.route_delta_event_index() == expected_latest
    assert _route_causes(world, route_ids) == expected_causes
    assert first.id == world.route_delta_event_index()[touched]
    assert untouched not in world.route_delta_event_index()


def test_route_delta_index_rebuilds_after_suffix_replacement_and_shrink():
    world = create_medieval_world(73)
    route_a, route_b = tuple(world.map.routes)[:2]
    first = record_event(
        world, "route_changed", "Rota A.", fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route_a, aspect="enabled",
                            before="True", after="False"),),
    )
    assert world.route_delta_event_index()[route_a] == first.id
    appended = record_event(
        world, "route_changed", "Rota B.", fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route_b, aspect="enabled",
                            before="True", after="False"),),
    )
    assert world.route_delta_event_index()[route_b] == appended.id

    replacement = WorldEvent(
        id=appended.id, day=appended.day, sequence=appended.sequence,
        event_type="route_replaced", content="Substituição de rota.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(id=f"{appended.id}:delta:0", event_id=appended.id,
                           owner_kind="route", owner_id=route_a, aspect="enabled",
                           before="False", after="True"),),
    )
    world.events[-1] = replacement
    rebuilt = world.route_delta_event_index()
    assert rebuilt[route_a] == replacement.id
    assert route_b not in rebuilt

    world.events.pop()
    assert world.route_delta_event_index() == {route_a: first.id}


def test_transaction_copy_isolates_route_delta_index_map():
    world = create_medieval_world(73)
    route_a, route_b = tuple(world.map.routes)[:2]
    record_event(
        world, "route_changed", "Rota A.", fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route_a, aspect="enabled",
                            before="True", after="False"),),
    )
    world.route_delta_event_index()
    candidate = world.transaction_copy()
    assert candidate._route_delta_cache[2] is not world._route_delta_cache[2]
    record_event(
        candidate, "route_changed", "Rota B candidata.", fact_kind=FactKind.STATE_TRANSITION,
        deltas=(StateDelta(owner_kind="route", owner_id=route_b, aspect="enabled",
                            before="True", after="False"),),
    )
    assert candidate.route_delta_event_index()[route_b].startswith("event:")
    assert route_b not in world.route_delta_event_index()


def test_actor_transition_requires_a_real_decision_cause_at_record_time():
    world = create_medieval_world(73)
    with pytest.raises(ValueError, match="real decision cause"):
        record_event(
            world,
            "unauthored_actor_transition",
            "Não deve ser aceito.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.ACTOR_DECISION,
            deltas=(StateDelta(owner_kind="stock", owner_id="s", aspect="food", before="1", after="2"),),
        )


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


def test_transaction_copy_isolates_pydantic_values_and_mutable_payloads():
    from pydantic import BaseModel, ConfigDict, PrivateAttr

    from src.classes.core.medieval_world import _copy_transaction_value

    class FrozenScalar(BaseModel):
        model_config = ConfigDict(frozen=True)
        value: int

    class FrozenNested(BaseModel):
        model_config = ConfigDict(frozen=True)
        values: list[int]

    class MutableScalar(BaseModel):
        value: int

    class FrozenPrivate(BaseModel):
        model_config = ConfigDict(frozen=True)
        value: int
        _payload: list[int] = PrivateAttr(default_factory=lambda: [3])

    class FrozenEmptyPrivate(BaseModel):
        model_config = ConfigDict(frozen=True)
        value: int
        _payload: dict[str, int] = PrivateAttr(default_factory=dict)

    class FrozenExtra(BaseModel):
        model_config = ConfigDict(frozen=True, extra="allow")
        value: int

    class FrozenEmptyExtra(BaseModel):
        model_config = ConfigDict(frozen=True, extra="allow")
        value: int

    scalar = FrozenScalar(value=3)
    nested = FrozenNested(values=[3])
    mutable = MutableScalar(value=3)
    private = FrozenPrivate(value=3)
    extra = FrozenExtra(value=3, payload=[3])
    empty_private = FrozenEmptyPrivate(value=3)
    empty_extra = FrozenEmptyExtra(value=3, payload={})

    scalar_copy = _copy_transaction_value(scalar)
    assert scalar_copy is not scalar
    assert scalar_copy.value == scalar.value
    nested_copy = _copy_transaction_value(nested)
    assert nested_copy is not nested
    assert nested_copy.values is not nested.values
    nested_copy.values.append(4)
    assert nested.values == [3]
    mutable_copy = _copy_transaction_value(mutable)
    assert mutable_copy is not mutable
    private_copy = _copy_transaction_value(private)
    assert private_copy is not private
    assert private_copy._payload is not private._payload
    private_copy._payload.append(4)
    assert private._payload == [3]
    extra_copy = _copy_transaction_value(extra)
    assert extra_copy is not extra
    assert extra_copy.payload is not extra.payload
    extra_copy.payload.append(4)
    assert extra.payload == [3]
    empty_private_copy = _copy_transaction_value(empty_private)
    assert empty_private_copy is not empty_private
    assert empty_private_copy._payload is not empty_private._payload
    empty_private_copy._payload["candidate"] = 4
    assert empty_private._payload == {}
    empty_extra_copy = _copy_transaction_value(empty_extra)
    assert empty_extra_copy is not empty_extra
    assert empty_extra_copy.payload is not empty_extra.payload
    empty_extra_copy.payload["candidate"] = 4
    assert empty_extra.payload == {}


def test_transaction_copy_shares_frozen_knowledge_values_but_not_registries():
    from src.classes.governance.models import KnowledgeReport
    from src.classes.mechanical_language import EntityRef

    world = create_medieval_world(73)
    report = KnowledgeReport(
        id="report:test", recipient_ref=EntityRef("polity", "valedouro"),
        publisher_ref=EntityRef("polity", "valedouro"), stock_id="stock:test",
        resource_id="food", kind="inventory", channel="administrative_report",
        observed_day=0, quantity=1, population=1, unit_price=1, quote_day=0,
        export_rate_permille=0, export_policy_event_id=None, export_collector_ref=None,
        event_id="event:1",
    )
    world.knowledge.reports[report.id] = report
    object.__setattr__(world.knowledge, "_semantic_validation_key", ("sentinel",))
    world.knowledge.for_actor(EntityRef("polity", "valedouro"))

    candidate = world.transaction_copy()

    assert candidate.knowledge is not world.knowledge
    assert candidate.knowledge.reports is not world.knowledge.reports
    assert world.knowledge.reports._owner is world.knowledge
    assert candidate.knowledge.reports._owner is candidate.knowledge
    assert candidate.knowledge.reports["report:test"] is world.knowledge.reports["report:test"]
    assert candidate.knowledge._semantic_validation_key is None
    assert candidate.knowledge._query_cache is not world.knowledge._query_cache
    assert candidate.knowledge._registry_epochs == world.knowledge._registry_epochs
    assert candidate.knowledge._query_cache["reports"][1][("polity", "valedouro")] is \
        world.knowledge._query_cache["reports"][1][("polity", "valedouro")]

    replacement = candidate.knowledge.reports["report:test"].model_copy(update={"quantity": 1})
    candidate.knowledge.reports["report:test"] = replacement
    assert world.knowledge.reports["report:test"] is not replacement


def test_knowledge_registry_does_not_keep_owner_alive_without_cyclic_gc():
    import gc
    import weakref

    from src.classes.governance.knowledge import KnowledgeState

    state = KnowledgeState()
    registry = state.reports
    owner_ref = weakref.ref(state)
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        del state
        assert owner_ref() is None
        assert registry._owner is None
        registry["orphaned"] = object()
        assert registry["orphaned"] is not None
    finally:
        if gc_was_enabled:
            gc.enable()


def test_knowledge_state_deepcopy_rebinds_registry_owner_and_epochs():
    import copy

    from src.classes.governance.knowledge import KnowledgeState

    state = KnowledgeState()
    state.reports["original"] = object()
    copied = copy.deepcopy(state)

    assert copied is not state
    assert copied.reports is not state.reports
    assert copied.reports._owner is copied
    assert copied.notices._owner is copied
    assert copied._registry_epoch == state._registry_epoch
    assert copied._registry_epochs == state._registry_epochs

    original_epoch = state._registry_epoch
    copied_epoch = copied._registry_epoch
    original_reports_epoch = state._registry_epochs["reports"]
    copied.reports["copied"] = object()

    assert copied._registry_epoch == copied_epoch + 1
    assert copied._registry_epochs["reports"] == original_reports_epoch + 1
    assert state._registry_epoch == original_epoch
    assert state._registry_epochs["reports"] == original_reports_epoch
    assert "copied" not in state.reports


def test_knowledge_semantic_validation_cache_is_invalidated_by_new_facts():
    world = create_medieval_world(73)
    world.knowledge.validate(world)
    first_key = world.knowledge._semantic_validation_key
    first_structural_epoch = world.knowledge._structural_validation_epoch
    assert first_structural_epoch == world.knowledge._registry_epoch

    # Revalidating an unchanged canonical snapshot is the fast path used by
    # nested owners in one transaction.
    world.knowledge.validate(world)
    assert world.knowledge._semantic_validation_key == first_key

    record_event(world, "observed", "Novo fato invalida a validação transitória.")
    world.knowledge.validate(world)
    assert world.knowledge._semantic_validation_key != first_key
    assert world.knowledge._structural_validation_epoch == world.knowledge._registry_epoch


def test_knowledge_semantic_validation_cache_is_invalidated_by_registry_replacement():
    world = create_medieval_world(73)
    world.knowledge.validate(world)
    first_key = world.knowledge._semantic_validation_key
    first_structural_epoch = world.knowledge._structural_validation_epoch
    world.knowledge.technologies["invalid"] = next(iter(world.knowledge.technologies.values())) \
        if world.knowledge.technologies else None
    if "invalid" in world.knowledge.technologies:
        with pytest.raises(ValueError):
            world.knowledge.validate(world)
    else:
        # The generated world may start without technical knowledge; replacing
        # any registry value still changes the validation identity.
        world.knowledge.reports["invalid"] = object()
        with pytest.raises(ValueError):
            world.knowledge.validate(world)
    assert world.knowledge._semantic_validation_key == first_key
    assert world.knowledge._structural_validation_epoch == first_structural_epoch


def test_knowledge_actor_query_cache_keeps_independent_registry_indexes():
    world = create_medieval_world(73)
    actor = next(iter(world.society.polities))
    from src.classes.mechanical_language import EntityRef

    actor_ref = EntityRef("polity", actor)
    world.knowledge.for_actor(actor_ref)
    world.knowledge.routes_for_actor(actor_ref)
    world.knowledge.for_actor(actor_ref)

    assert set(world.knowledge._query_cache) >= {"reports", "route_reports"}


def test_knowledge_actor_query_cache_ignores_writes_to_other_registries():
    world = create_medieval_world(73)
    actor = next(iter(world.society.polities))
    from src.classes.mechanical_language import EntityRef

    actor_ref = EntityRef("polity", actor)
    first = world.knowledge.for_actor(actor_ref)
    reports_epoch = world.knowledge._registry_epochs["reports"]

    # A notice write must not invalidate an index built from reports.  The
    # registry epochs are intentionally per-domain rather than global.
    world.knowledge.notices["notice:unrelated"] = object()

    assert world.knowledge._registry_epochs["reports"] == reports_epoch
    assert world.knowledge.for_actor(actor_ref) is first


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
