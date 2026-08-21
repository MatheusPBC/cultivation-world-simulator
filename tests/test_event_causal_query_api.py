"""
Tests for GET /api/v1/query/events/{event_id}/causal (the "why" query, Task 5).

Covers docs/specs/causal-world-kernel.md §7.1: depth clamp, node-limit
truncation, cycle protection, missing/pruned ancestors as data (not errors),
effects (downstream), state deltas, and opt-in decision resolution through a
`motivated_by` edge.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.core.world import World
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.event import Event, FactKind
from src.systems.time import Month, Year, create_month_stamp


def create_test_map():
    m = Map(width=10, height=10)
    for x in range(10):
        for y in range(10):
            m.create_tile(x, y, TileType.PLAIN)
    return m


def make_event(year: int, month: int, content: str, **kwargs) -> Event:
    return Event(month_stamp=create_month_stamp(Year(year), Month(month)), content=content, **kwargs)


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_events.db"


@pytest.fixture
def world(temp_db_path):
    game_map = create_test_map()
    month_stamp = create_month_stamp(Year(100), Month.JANUARY)
    w = World.create_with_db(map=game_map, month_stamp=month_stamp, events_db_path=temp_db_path)
    yield w
    w.event_manager.close()


@pytest.fixture
def client_with_world(world):
    from src.server import main

    original_instance = main.game_instance.copy()
    main.game_instance["world"] = world
    main.game_instance["sim"] = MagicMock()
    main.game_instance["is_paused"] = True

    client = TestClient(main.app)
    yield client

    main.game_instance.update(original_instance)


class TestEventCausalDetailBasics:
    def test_404_for_unknown_event(self, client_with_world):
        response = client_with_world.get("/api/v1/query/events/does-not-exist/causal")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "EVENT_NOT_FOUND"

    def test_event_with_no_links_returns_empty_causal_shape(self, client_with_world, world):
        event = make_event(100, 1, "lonely event")
        world.event_manager.add_event(event)

        response = client_with_world.get(f"/api/v1/query/events/{event.id}/causal")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["event"]["id"] == event.id
        assert data["causes"] == []
        assert data["effects"] == []
        assert data["deltas"] == []
        assert data["decision"] is None
        assert data["truncated"] is False

    def test_direct_cause_is_returned_at_depth_one(self, client_with_world, world):
        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY, weight=0.5)
        ]
        world.event_manager.add_event(cause)
        world.event_manager.add_event(effect)

        response = client_with_world.get(f"/api/v1/query/events/{effect.id}/causal")
        data = response.json()["data"]

        assert len(data["causes"]) == 1
        edge = data["causes"][0]
        assert edge["relation"] == "triggered_by"
        assert edge["weight"] == 0.5
        assert edge["depth"] == 1
        assert edge["pruned"] is False
        assert edge["event"]["id"] == cause.id

    def test_effects_are_the_direct_downstream_edges(self, client_with_world, world):
        cause = make_event(100, 1, "cause")
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=cause.id, relation=CausalRelation.TRIGGERED_BY)
        ]
        world.event_manager.add_event(cause)
        world.event_manager.add_event(effect)

        response = client_with_world.get(f"/api/v1/query/events/{cause.id}/causal")
        data = response.json()["data"]

        assert len(data["effects"]) == 1
        assert data["effects"][0]["event"]["id"] == effect.id
        assert data["effects"][0]["pruned"] is False


class TestEventCausalDetailDepthAndTruncation:
    def _build_chain(self, world, length: int) -> list[Event]:
        events = [make_event(100, i + 1, f"e{i}") for i in range(length)]
        for i in range(1, length):
            events[i].causal_links = [
                CausalLink(event_id=events[i].id, cause_event_id=events[i - 1].id, relation=CausalRelation.TRIGGERED_BY)
            ]
        for event in events:
            world.event_manager.add_event(event)
        return events

    def test_depth_is_clamped_to_five(self, client_with_world, world):
        events = self._build_chain(world, 8)  # a chain of 7 ancestor hops

        response = client_with_world.get(f"/api/v1/query/events/{events[-1].id}/causal?depth=99")
        data = response.json()["data"]

        max_depth_seen = max((edge["depth"] for edge in data["causes"]), default=0)
        assert max_depth_seen <= 5
        assert data["truncated"] is True

    def test_shallow_depth_walks_fewer_ancestors_and_reports_truncated(self, client_with_world, world):
        events = self._build_chain(world, 5)

        response = client_with_world.get(f"/api/v1/query/events/{events[-1].id}/causal?depth=1&limit=40")
        data = response.json()["data"]

        assert len(data["causes"]) == 1
        assert data["causes"][0]["depth"] == 1
        assert data["truncated"] is True

    def test_full_shallow_chain_is_not_truncated_when_it_fits(self, client_with_world, world):
        events = self._build_chain(world, 3)  # 2 ancestor hops, fits in depth=3/limit=40 defaults

        response = client_with_world.get(f"/api/v1/query/events/{events[-1].id}/causal")
        data = response.json()["data"]

        assert len(data["causes"]) == 2
        assert data["truncated"] is False

    def test_node_limit_truncates_a_wide_fan_in(self, client_with_world, world):
        effect = make_event(100, 10, "effect")
        causes = [make_event(100, i + 1, f"cause{i}") for i in range(5)]
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id=c.id, relation=CausalRelation.CONTRIBUTED_TO)
            for c in causes
        ]
        for c in causes:
            world.event_manager.add_event(c)
        world.event_manager.add_event(effect)

        response = client_with_world.get(f"/api/v1/query/events/{effect.id}/causal?limit=3")
        data = response.json()["data"]

        assert len(data["causes"]) == 3
        assert data["truncated"] is True

    def test_limit_is_clamped_to_the_server_maximum(self, client_with_world, world):
        event = make_event(100, 1, "solo")
        world.event_manager.add_event(event)

        response = client_with_world.get(f"/api/v1/query/events/{event.id}/causal?limit=999999")

        assert response.status_code == 200


class TestEventCausalDetailCycleProtection:
    def test_a_cycle_does_not_loop_and_terminates(self, client_with_world, world):
        a = make_event(100, 1, "a")
        b = make_event(100, 2, "b")
        world.event_manager.add_event(a)
        world.event_manager.add_event(b)
        a.causal_links = [CausalLink(event_id=a.id, cause_event_id=b.id, relation=CausalRelation.TRIGGERED_BY)]
        b.causal_links = [CausalLink(event_id=b.id, cause_event_id=a.id, relation=CausalRelation.TRIGGERED_BY)]
        world.event_manager.update_decision_payload(a.id, a.causal_payload)  # no-op, keeps intent explicit

        response = client_with_world.get(f"/api/v1/query/events/{a.id}/causal?depth=5&limit=50")

        assert response.status_code == 200
        data = response.json()["data"]
        # a -> b -> a: a cause of `a` pointing back at `a` itself must not be
        # traversed again, so the cause list stays small and finite.
        assert len(data["causes"]) <= 2


class TestEventCausalDetailPrunedAncestor:
    def test_missing_ancestor_is_represented_as_pruned_data_not_an_error(self, client_with_world, world):
        effect = make_event(100, 2, "effect")
        effect.causal_links = [
            CausalLink(event_id=effect.id, cause_event_id="cleaned-up-id", relation=CausalRelation.ENABLED_BY, weight=0.3)
        ]
        world.event_manager.add_event(effect)

        response = client_with_world.get(f"/api/v1/query/events/{effect.id}/causal")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["causes"]) == 1
        assert data["causes"][0]["pruned"] is True
        assert data["causes"][0]["event"] is None
        assert data["causes"][0]["weight"] == 0.3


class TestEventCausalDetailDecisionAndDeltas:
    def test_decision_is_resolved_through_the_motivated_by_edge(self, client_with_world, world):
        decision_payload = {
            "id": "d1",
            "chosen_chain": [{"action_name": "breakthrough", "params": {}}],
            "thinking": "time to break through",
        }
        decision = make_event(
            100, 1, "decision",
            fact_kind=FactKind.DECISION,
            causal_payload={"deltas": [], "decision": decision_payload},
        )
        action_start = make_event(100, 2, "started breakthrough")
        action_start.causal_links = [
            CausalLink(event_id=action_start.id, cause_event_id=decision.id, relation=CausalRelation.MOTIVATED_BY)
        ]
        world.event_manager.add_event(decision)
        world.event_manager.add_event(action_start)

        response = client_with_world.get(f"/api/v1/query/events/{action_start.id}/causal")
        data = response.json()["data"]

        assert data["decision"] is not None
        assert data["decision"]["thinking"] == "time to break through"
        # The decision event itself is hidden from the default timeline...
        timeline = client_with_world.get("/api/v1/query/events").json()["data"]["events"]
        assert decision.id not in {e["id"] for e in timeline}
        # ...but the `why` drill-down still resolved it by id.

    def test_no_motivated_by_edge_means_no_decision(self, client_with_world, world):
        event = make_event(100, 1, "no decision here")
        world.event_manager.add_event(event)

        response = client_with_world.get(f"/api/v1/query/events/{event.id}/causal")

        assert response.json()["data"]["decision"] is None

    def test_deltas_come_from_the_events_own_causal_payload(self, client_with_world, world):
        event = make_event(
            100, 1, "population fell",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_payload={"deltas": [{"aspect": "population", "before": "80.0", "after": "78.4"}], "decision": None},
        )
        world.event_manager.add_event(event)

        response = client_with_world.get(f"/api/v1/query/events/{event.id}/causal")
        data = response.json()["data"]

        assert data["deltas"] == [{"aspect": "population", "before": "80.0", "after": "78.4"}]
