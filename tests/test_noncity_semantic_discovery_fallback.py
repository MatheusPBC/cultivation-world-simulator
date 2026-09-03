from src.utils.llm.test_mode_fallbacks import resolve_test_mode_task


def _site_metrics(capability_id: str = "zeta_transport") -> list[dict[str, object]]:
    return [
        {
            "dimension": "capacity",
            "concept_id": capability_id,
            "unit": "site_equivalents",
            "qualifiers": {"kind": "infrastructure_site"},
        }
    ]


def test_fallback_discovers_grounded_site_capacity_for_any_region_kind():
    results = []
    for region_type in ("normal", "cultivate"):
        results.append(
            resolve_test_mode_task(
                "semantic_discovery",
                {
                    "target": {
                        "kind": "region",
                        "id": "101",
                        "region_type": region_type,
                    },
                    "available_metrics": _site_metrics(),
                },
            )
        )

    assert results[0] == results[1]
    result = results[0]
    metric = result["derived_metrics"][0]
    condition = result["conditions"][0]
    assert metric["id"] == "infrastructure_site_zeta_transport_capacity"
    assert metric["dimension"] == "capacity"
    assert metric["unit"] == "site_equivalents"
    assert metric["expression"] == {
        "op": "clamp",
        "min": 0.0,
        "max": 1.0,
        "value": {
            "op": "metric",
            "dimension": "capacity",
            "concept_id": "zeta_transport",
            "qualifiers": {"kind": "infrastructure_site"},
        },
    }
    assert condition["metric_definition_id"] == metric["id"]
    assert 0 <= condition["resolve_below"] < condition["activate_above"] <= 1
    assert condition["activate_above"] - condition["resolve_below"] >= 0.05


def test_fallback_site_ids_are_stable_and_valid_for_arbitrary_capabilities():
    infos = {"available_metrics": _site_metrics("Soul Bell / Necromancy")}
    first = resolve_test_mode_task("semantic_discovery", infos)
    second = resolve_test_mode_task("semantic_discovery", infos)

    assert first == second
    for concept in first["concepts"]:
        assert concept["id"].islower()
        assert concept["id"].replace("_", "").isalnum()
        assert 3 <= len(concept["id"]) <= 63


def test_fallback_keeps_city_settlement_surface_and_rejects_unsupported_surface():
    city_result = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [
                {
                    "dimension": "load",
                    "concept_id": "settlement",
                    "unit": "ten_thousand_people",
                },
                {
                    "dimension": "capacity",
                    "concept_id": "settlement",
                    "unit": "ten_thousand_people",
                },
                *_site_metrics(),
            ],
        },
    )
    unsupported_result = resolve_test_mode_task(
        "semantic_discovery",
        {
            "available_metrics": [
                {
                    "dimension": "capacity",
                    "concept_id": "imaginary_capability",
                    "unit": "units",
                    "qualifiers": {"kind": "unverified"},
                }
            ],
        },
    )

    assert city_result["derived_metrics"][0]["id"] == "settlement_density_pressure"
    assert unsupported_result == {
        "concepts": [],
        "derived_metrics": [],
        "conditions": [],
        "mechanic_proposals": [],
    }
