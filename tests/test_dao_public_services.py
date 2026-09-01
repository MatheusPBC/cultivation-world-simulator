from types import SimpleNamespace

import pytest

from src.classes.celestial_dao import DaoTradition
from src.classes.core.dynasty import Dynasty
from src.classes.official_rank import OFFICIAL_GRAND_COUNCILOR
from src.server.services.game_command_service import GameCommandService
from src.server.services.game_query_service import GameQueryService
from src.systems.celestial_dao_service import create_petition


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
    petition = create_petition(
        base_world,
        initiator_kind="court",
        initiator_id="1",
        region_id=7,
        motivated_event_ids=[],
        rite_event_ids=["r1", "r2", "r3"],
    )
    runtime = _Runtime(base_world)

    query_data = _service(GameQueryService, runtime).get_dao_petitions()
    result = await _service(GameCommandService, runtime).answer_dao_petition(
        petition_id=petition.id, response="sign"
    )

    assert query_data["pending"][0]["id"] == petition.id
    assert query_data["pending"][0]["initiator_name"]
    assert result["event_id"]
    assert runtime.mutations == 1

    history_data = _service(GameQueryService, runtime).get_dao_petitions()["history"]
    assert (
        history_data[0]["response_content"]
        == base_world.event_manager.get_event_by_id(result["event_id"]).content
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

    assert result["claimant_avatar_id"] == claimant.id
    assert runtime.mutations == 1
