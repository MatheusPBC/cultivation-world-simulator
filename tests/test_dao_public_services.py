from types import SimpleNamespace

import pytest

from src.classes.causal_origin import CausalOrigin
from src.classes.celestial_dao import DaoPetition, DaoTradition
from src.classes.event import FactKind
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.server.services.game_command_service import GameCommandService
from src.server.services.game_query_service import GameQueryService


class _Runtime:
    def __init__(self, world):
        self.world = world
        self.mutations = 0

    def get(self, key):
        return self.world if key == "world" else None

    async def run_mutation(self, operation):
        self.mutations += 1
        return operation()


def _service(service_cls, runtime):
    service = object.__new__(service_cls)
    service._deps = SimpleNamespace(runtime=runtime)
    return service


@pytest.mark.asyncio
async def test_dao_public_services_query_and_serialize_mutation(
    base_world, dummy_avatar
):
    base_world.map.regions[7] = SimpleNamespace(id=7, dao_tradition=DaoTradition.MERCY)
    base_world.avatar_manager.register_avatar(dummy_avatar)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=dummy_avatar.id
    )
    petition = DaoPetition(
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        tradition=DaoTradition.MERCY,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    base_world.dao_petitions.append(petition)
    runtime = _Runtime(base_world)

    query_data = _service(GameQueryService, runtime).get_dao_petitions()
    result = await _service(GameCommandService, runtime).answer_dao_petition(
        petition_id=petition.id, response="sign"
    )

    assert query_data["pending"][0]["id"] == petition.id
    assert query_data["pending"][0]["initiator_name"]
    assert result["event_id"]
    assert runtime.mutations == 1

    response_event = base_world.event_manager.get_event_by_id(result["event_id"])
    decision_events = [
        event
        for event in base_world.event_manager.get_recent_events(
            limit=100, include_decisions=True
        )
        if event.fact_kind is FactKind.DECISION
        and event.event_type == "dao_petition_decision"
    ]
    assert len(decision_events) == 1
    assert decision_events[0].causal_payload["decision"]["source"] == "api"
    assert response_event.causal_origin is CausalOrigin.ACTOR_DECISION
    assert response_event.causal_payload["deltas"][0]["event_id"] == response_event.id
    assert any(
        link.cause_event_id == decision_events[0].id
        for link in response_event.causal_links
    )

    history_data = _service(GameQueryService, runtime).get_dao_petitions()["history"]
    assert (
        history_data[0]["response_content"]
        == response_event.content
    )


@pytest.mark.asyncio
async def test_imperial_claim_command_runs_inside_runtime_mutation(
    base_world, dummy_avatar
):
    emperor = dummy_avatar
    emperor.official_rank = OFFICIAL_GRAND_COUNCILOR
    emperor.court_reputation = 700
    from copy import copy

    claimant = copy(emperor)
    claimant.id = "claimant"
    base_world.avatar_manager.register_avatar(emperor)
    base_world.avatar_manager.register_avatar(claimant)
    base_world.dynasty = Dynasty(
        id=1, name="Test", desc="", current_emperor_id=emperor.id
    )
    runtime = _Runtime(base_world)

    result = await _service(GameCommandService, runtime).open_imperial_claim(
        avatar_id=claimant.id
    )

    assert result["claims"][0]["candidate_id"] == claimant.id
    assert base_world.event_manager.get_event_by_id(result["event_id"]) is not None
    assert runtime.mutations == 1
