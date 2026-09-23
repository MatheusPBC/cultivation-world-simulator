from pathlib import Path

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
            ai_max_calls=1,
        )


@pytest.mark.asyncio
async def test_real_provider_requires_an_explicit_total_budget(tmp_path):
    with pytest.raises(ValueError, match="explicit positive ai_max_calls"):
        await medieval_autonomy_smoke.run(
            73,
            30,
            tmp_path / "unbounded.mws",
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
    assert result["save_bytes"] == Path(output).stat().st_size
    assert result["save_elapsed_s"] >= 0
    assert result["load_elapsed_s"] >= 0
    assert result["memory_high_water_bytes"] > 0
    assert result["disk_free_bytes_after_save"] > 0


@pytest.mark.asyncio
async def test_smoke_checkpoint_writes_and_validates_distinct_artifacts(tmp_path):
    output = tmp_path / "natural-60.mws"
    result = await medieval_autonomy_smoke.run(73, 60, output, checkpoint_days=30)

    assert [item["day"] for item in result["checkpoints"]] == [30, 60]
    assert all(item["conservation"] and item["save_load_equivalent"]
               and item["bytes"] > 0 and item["elapsed_s"] >= 0
               and item["memory_high_water_bytes"] > 0
               for item in result["checkpoints"])
    assert all(Path(item["path"]).exists() for item in result["checkpoints"])
    assert len({item["path"] for item in result["checkpoints"]}) == 2


@pytest.mark.asyncio
async def test_smoke_resumes_checkpoint_for_bounded_additional_days(tmp_path):
    source = tmp_path / "source.mws"
    await medieval_autonomy_smoke.run(73, 30, source)

    output = tmp_path / "continued.mws"
    result = await medieval_autonomy_smoke.run(
        999, 30, output, resume_save=source, checkpoint_days=30)

    assert result["seed"] == 73
    assert result["start_day"] == 30
    assert result["advanced_days"] == 30
    assert result["saved_day"] == 60
    assert result["continuation_day"] == 61
    assert result["save_load_equivalent"] and result["all_resources_accounted"]
    assert [item["day"] for item in result["checkpoints"]] == [60]
    assert Path(result["checkpoints"][0]["path"]).name == \
        "continued.checkpoint-day-00060.mws"
    assert Path(result["checkpoints"][0]["path"]).is_file()

    from tools.medieval_causal_audit import audit
    assert audit(output)["ok"] is True


@pytest.mark.asyncio
async def test_smoke_resume_rejects_source_overwrite_and_existing_output(tmp_path):
    source = tmp_path / "source.mws"
    await medieval_autonomy_smoke.run(73, 30, source)

    with pytest.raises(ValueError, match="different paths"):
        await medieval_autonomy_smoke.run(73, 30, source, resume_save=source)

    existing = tmp_path / "existing.mws"
    existing.write_bytes(b"preserve")
    with pytest.raises(ValueError, match="already exists"):
        await medieval_autonomy_smoke.run(73, 30, existing, resume_save=source)
    assert existing.read_bytes() == b"preserve"

    checkpoint = tmp_path / "continued.checkpoint-day-00060.mws"
    checkpoint.write_bytes(b"prior evidence")
    with pytest.raises(ValueError, match="checkpoint output already exists"):
        await medieval_autonomy_smoke.run(
            73, 30, tmp_path / "continued.mws", resume_save=source,
            checkpoint_days=30)
    assert checkpoint.read_bytes() == b"prior evidence"


@pytest.mark.asyncio
async def test_fresh_smoke_keeps_relative_horizon_behavior(tmp_path):
    result = await medieval_autonomy_smoke.run(73, 30, tmp_path / "fresh.mws")

    assert result["start_day"] == 0
    assert result["advanced_days"] == 30
    assert result["saved_day"] == 30


def test_smoke_rejects_invalid_checkpoint_interval(tmp_path):
    with pytest.raises(ValueError, match="positive multiple of 30"):
        import asyncio
        asyncio.run(medieval_autonomy_smoke.run(73, 30, tmp_path / "bad.mws",
                                                checkpoint_days=15))


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


def test_recuperacao_profile_can_select_an_engine_authored_expansion():
    payload = {
        "choices": [
            {"id": "opaque:capacity", "label": "Investir na instalação works:campos com harvest-capacity."},
            {"id": "opaque:employment", "label": "Estabelecer vínculo local."},
        ]
    }
    assert medieval_autonomy_smoke._recuperacao_decision(payload) == "opaque:capacity"


def test_recuperacao_profile_uses_owned_relief_before_requesting_outside_aid():
    payload = {
        "choices": [
            {"id": "relief-distribute:polity:auren:100"},
            {"id": "institutional-aid-request:polity:auren:valedouro:r:1"},
        ],
        "situation": {"relief": {"settlement_reports": [{"missing_food": 900}]}},
    }
    assert medieval_autonomy_smoke._recuperacao_decision(payload) == \
        "relief-distribute:polity:auren:100"


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


def test_market_profile_selects_provider_alias_by_authored_label():
    payload = {
        "choices": [
            {"id": "choice:2", "label": "Pedir compra de food por rota conhecida."},
            {"id": "choice:3", "label": "Executar o abastecimento disponível para um assentamento pressionado."},
        ],
        "situation": {},
    }
    assert medieval_autonomy_smoke._market_decision(payload) == "choice:2"


def test_market_profile_selects_seller_alias_by_authored_label():
    payload = {
        "choices": [
            {"id": "choice:4", "label": "Aceitar pedido de compra de mercado."},
            {"id": "choice:5", "label": "Recusar o pedido de compra de mercado."},
        ],
        "situation": {},
    }
    assert medieval_autonomy_smoke._market_decision(payload) == "choice:4"


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


def test_recovery_profile_composes_only_enumerated_options():
    payload = {
        "choices": [
            {"id": "market-purchase:auren:objective:food:offer:1"},
            {"id": "permanent-employment:polity:auren:pedraclara:group:site:artisan:1:1:30:x"},
        ],
        "situation": {},
    }
    assert medieval_autonomy_smoke._recuperacao_decision(payload) == \
        "market-purchase:auren:objective:food:offer:1"


@pytest.mark.asyncio
async def test_pressured_recovery_fixture_proves_a_material_multistep_chain(tmp_path):
    """The fixture exercises existing affordances without an engine subsidy."""
    from tools.medieval_causal_audit import audit

    output = tmp_path / "recovery-120.mws"
    result = await medieval_autonomy_smoke.run(73, 120, output, gov_profile="recuperacao")

    assert result["food_conserved"] is True
    assert result["money_conserved"] is True
    assert result["save_load_equivalent"] is True
    assert result["deprivation_deaths"] == 0
    assert result["relief_given_total"] > 0
    assert result["market_purchases_total"] > 0
    assert result["permanent_employment_total"] > 0
    assert result["workforce_transitions_total"] > 0
    # Recovery is intentionally partial: the fixture must not hide pressure
    # by declaring equilibrium or manufacturing food.
    assert result["monthly_metrics"][-1]["missing_food"] > 0

    report = audit(output)
    assert report["ok"] is True
    assert report["broken_cause_ids"] == []
    assert report["decision_origin_without_source"] == []
    assert report["decision_authorship_errors"] == []
    assert report["interpretation_material_events"] == []
    assert report["material_event_types"]["relief_distributed"]["with_causal_links"] > 0
    assert report["material_by_origin"]["actor_decision"] > 0
