from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.server.api.public_v1.query import create_public_query_router
from src.server.services.game_queries import get_world_semantic_model
from src.server.services.game_query_service import GameQueryService


def _semantic_model() -> dict:
    return {
        "language_version": 1,
        "active_concepts": [{"id": "settlement_load"}],
        "historical_concepts": [{"id": "old_pressure"}],
        "groundings": [{"id": "grounding-1"}],
        "derived_metric_definitions": [{"id": "population_pressure"}],
        "condition_definitions": [{"id": "overcrowded"}],
        "condition_instances": [{"id": "condition-1"}],
        "mechanic_proposals": [{"id": "proposal-1"}],
        "reaction_receipts": [{"id": "receipt-1", "domain": "population"}],
    }


def test_semantic_model_query_uses_service_layer_and_public_envelope():
    semantic_model = _semantic_model()
    runtime = {
        "world": SimpleNamespace(
            mechanical_language=SimpleNamespace(to_public_dict=lambda: semantic_model)
        )
    }
    service = GameQueryService(SimpleNamespace(runtime=runtime))
    router = create_public_query_router(query_service=service)
    routes = {route.path: route.endpoint for route in router.routes}

    response = routes["/api/v1/query/world/semantic-model"]()

    assert response == {"ok": True, "data": semantic_model}
    assert set(response["data"]) == {
        "language_version",
        "active_concepts",
        "historical_concepts",
        "groundings",
        "derived_metric_definitions",
        "condition_definitions",
        "condition_instances",
        "mechanic_proposals",
        "reaction_receipts",
    }


def test_semantic_model_query_uses_public_world_not_ready_error():
    with pytest.raises(HTTPException) as caught:
        get_world_semantic_model({"world": None})

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "WORLD_NOT_READY"
    assert caught.value.detail["message"] == "World not initialized"
