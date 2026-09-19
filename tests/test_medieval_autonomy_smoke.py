import pytest

from tools import medieval_autonomy_smoke


@pytest.mark.asyncio
async def test_real_provider_probe_fails_explicitly_when_provider_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.sim.medieval.ai_decider.provider_available",
        lambda: False,
    )

    with pytest.raises(RuntimeError, match="real provider is not configured"):
        await medieval_autonomy_smoke.run(
            73,
            1,
            tmp_path / "unavailable.mws",
            real_provider=True,
        )


@pytest.mark.asyncio
async def test_real_provider_probe_cannot_be_disguised_as_deterministic_government(tmp_path):
    with pytest.raises(ValueError, match="cannot be combined"):
        await medieval_autonomy_smoke.run(
            73,
            1,
            tmp_path / "mixed.mws",
            gov_profile="reativo",
            real_provider=True,
        )


@pytest.mark.asyncio
async def test_smoke_accepts_string_output_paths(tmp_path):
    output = str(tmp_path / "string-output.mws")
    result = await medieval_autonomy_smoke.run(73, 30, output, gov_profile="desatento")

    assert result["save"] == output


def test_socorro_profile_only_selects_enumerated_aid_ids():
    payload = {
        "choices": [
            {"id": "relief-distribute:polity:auren:100"},
            {"id": "institutional-aid-request:polity:auren:valedouro:r:1"},
        ],
        "situation": {"relief": {"settlement_reports": [{"missing_food": 900}]}},
    }
    selected = medieval_autonomy_smoke._socorro_decision(payload)
    assert selected == "institutional-aid-request:polity:auren:valedouro:r:1"


def test_socorro_profile_can_select_an_enumerated_surplus_transfer():
    payload = {
        "choices": [
            {"id": "relief-transfer:auren:stock:pontenegro:stock:campomanso:150:route"},
            {"id": "relief-distribute:polity:auren:100"},
        ],
        "situation": {"relief": {"settlement_reports": [{"missing_food": 900}]}},
    }
    assert medieval_autonomy_smoke._socorro_decision(payload).startswith("relief-transfer:")


def test_alivio_profile_prioritizes_only_an_enumerated_relief_id():
    payload = {
        "choices": [
            {"id": "relief-distribute:polity:auren:100"},
            {"id": "institutional-aid-request:polity:auren:valedouro:r:1"},
        ],
        "situation": {"relief": {"settlement_reports": [{"missing_food": 900}]}},
    }
    assert medieval_autonomy_smoke._alivio_decision(payload) == "relief-distribute:polity:auren:100"


def test_market_profile_only_selects_an_enumerated_market_offer():
    payload = {
        "choices": [
            {"id": "institutional-aid-request:polity:auren:valedouro:r:1"},
            {"id": "market-purchase:auren:objective:food:offer:1"},
        ],
        "situation": {},
    }
    assert medieval_autonomy_smoke._market_decision(payload) == \
        "market-purchase:auren:objective:food:offer:1"


def test_mobility_profile_only_selects_enumerated_employment_and_transition_ids():
    employment = {
        "choices": [{"id": "permanent-employment:polity:auren:pedraclara:group:site:artisan:1:1:30:x"}],
        "situation": {},
    }
    population = {
        "choices": [{"id": "workforce_transition:pop:x:notice:event"}],
        "situation": {},
    }
    assert medieval_autonomy_smoke._mobilidade_decision(employment).startswith("permanent-employment:")
    assert medieval_autonomy_smoke._povo_decision(population, workforce=True).startswith("workforce_transition:")
