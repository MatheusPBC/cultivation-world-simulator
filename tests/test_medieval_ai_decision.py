"""A real provider may choose; it may never mutate, leak or be required."""

import json
from types import SimpleNamespace

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import (DECLINED_EVENT, FAILED_EVENT, INTERPRETED_EVENT,
                                         ProviderDecisionRequired)
from src.sim.medieval.institutional_aid_policy import (review_institutional_aid,
                                                       review_institutional_aid_with_provider)
from src.sim.medieval.institutional_aid import aid_request_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from tests.test_medieval_institutional_aid_policy import advance, pressured_world


def enable(world, *, per_step=2, maximum=10):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": per_step,
                                                   "ai_max_calls": maximum})
    return world


def provider(monkeypatch, answer, *, seen=None):
    """A local stand-in for the existing client: no network, no key, no prose kept."""
    async def call_llm_json(prompt, *args, **kwargs):
        if seen is not None:
            seen.append(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def test_provider_availability_reads_the_nested_llm_profile(monkeypatch):
    """The application settings own a container, not the runtime profile itself."""
    from src.config import settings_service

    profile = SimpleNamespace(has_api_key=True, model_name="provider-model",
                              base_url="https://provider.example", api_format="openai")
    # The suite fixture clears the real function's cache during teardown, so
    # restore it before that lifecycle hook runs.
    with monkeypatch.context() as scoped:
        scoped.setattr(settings_service, "get_settings_service",
                       lambda: SimpleNamespace(get_llm_runtime_config=lambda: (profile, "provider-key")))
        assert ai_decider.provider_available() is True


def test_codex_oauth_provider_does_not_require_an_api_key(monkeypatch):
    from src.config import settings_service

    profile = SimpleNamespace(model_name="gpt-5.6-luna", base_url="codex://local", api_format="codex_cli")
    with monkeypatch.context() as scoped:
        scoped.setattr(settings_service, "get_settings_service",
                       lambda: SimpleNamespace(get_llm_runtime_config=lambda: (profile, "")))
        assert ai_decider.provider_available() is True


async def requested_world():
    world = enable(pressured_world())
    review_institutional_aid(world, allow_requests=True)
    notice = next(item for _, item in sorted(world.knowledge.institutional_aid_notices.items())
                  if item.kind == "request")
    advance(world)
    return world, notice


async def test_a_provider_choice_becomes_a_canonical_decision_without_leaking(tmp_path, monkeypatch):
    world, notice = await requested_world()
    provider_actor = notice.recipient_ref
    from src.sim.medieval.institutional_aid import aid_response_options
    option = next(item for item in aid_response_options(world, provider_actor) if item.kind == "reject")
    prompts = []
    provider(monkeypatch, {"selected_id": option.id, "reason": "prosa que deve ser descartada"}, seen=prompts)

    await review_institutional_aid_with_provider(world, allow_requests=False)

    interpretation = next(item for item in world.events if item.event_type == INTERPRETED_EVENT)
    assert interpretation.deltas == (), "an interpretation carries no state change"
    assert interpretation.causal_origin.value == "llm_interpretation"
    rejected = next(item for item in world.events if item.event_type == "institutional_aid_rejected")
    decision = next(item for item in world.events
                    if item.id in {link.cause_event_id for link in rejected.causal_links}
                    and item.decision and item.decision.get("action") == "respond_institutional_aid")
    assert decision.causal_origin.value != "llm_interpretation"
    assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}
    assert decision.decision["selected_affordance_id"] == option.id
    assert interpretation.id not in {link.cause_event_id for link in rejected.causal_links}

    prompt = prompts[0]
    assert str(notice.requested_food) in prompt and option.id in prompt
    for secret in ("treasury:", "stock:", "api_key", "base_url", "reagents", "detachment"):
        assert secret not in prompt, "the prompt carries no foreign or private material"

    path = tmp_path / "ai.mws"
    save_world(world, path)
    payload = path.read_bytes().decode("utf-8", "ignore")
    assert "prosa que deve ser descartada" not in payload
    assert "selected_id" not in payload and "api_key" not in payload
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_aid_response_that_goes_stale_pauses_instead_of_becoming_noop(monkeypatch):
    from src.sim.medieval import institutional_aid_policy as policy

    world, notice = await requested_world()
    actor = notice.recipient_ref
    initial = policy._response_candidates(world, actor)
    assert initial[1] is not None
    calls = 0

    def response_candidates(current, current_actor):
        nonlocal calls
        calls += 1
        return initial if calls == 1 else ((), None, None)

    monkeypatch.setattr(policy, "_response_candidates", response_candidates)
    provider(monkeypatch, {"selected_id": initial[1].id})
    with pytest.raises(ProviderDecisionRequired):
        await policy._respond_with_provider(world, actor)
    assert not any(item.event_type in {"institutional_aid_accepted", "institutional_aid_rejected"}
                   for item in world.events)


async def test_provider_can_select_a_current_request_option(monkeypatch):
    world = enable(pressured_world())
    actor = next(EntityRef("polity", identity) for identity in sorted(world.society.polities)
                 if aid_request_options(world, EntityRef("polity", identity)))
    option = aid_request_options(world, actor)[0]

    async def call_llm_json(prompt, *args, **kwargs):
        assert option.id in prompt
        return {"selected_id": option.id}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    await review_institutional_aid_with_provider(world, allow_requests=True)

    request = next(item for item in world.events if item.event_type == "institutional_aid_requested")
    decision = next(item for item in world.events
                    if item.id in {link.cause_event_id for link in request.causal_links}
                    and item.decision and item.decision.get("action") == "request_institutional_aid")
    assert decision.decision["selected_affordance_id"] == option.id


async def test_private_affordance_handle_is_opaque_in_prompt_but_maps_back_to_canonical(monkeypatch):
    world = enable(pressured_world())
    actor = EntityRef("polity", "auren")
    prompts = []

    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        payload = json.loads(prompt.rsplit("\n", 1)[1])
        return {"selected_id": payload["choices"][0]["id"]}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    selected = await ai_decider.select_option(
        world, actor, {"today": world.clock.absolute_day},
        [{"id": "research:polity:auren:stock:ferroalto:treasury:auren:character:011",
          "label": "Financiar pesquisa enumerada."}],
    )

    assert selected == "research:polity:auren:stock:ferroalto:treasury:auren:character:011"
    assert "stock:ferroalto" not in prompts[0]
    assert "treasury:auren" not in prompts[0]


@pytest.mark.parametrize("answer", [RuntimeError("provider down"), {"selected_id": "forged:option"},
                                    {"selected_id": "NO_ACTION"}])
async def test_a_failed_or_invalid_answer_does_not_fabricate_an_aid_action(answer, monkeypatch):
    world, notice = await requested_world()
    provider(monkeypatch, answer)
    if isinstance(answer, Exception) or answer.get("selected_id") == "forged:option":
        with pytest.raises(ProviderDecisionRequired):
            await review_institutional_aid_with_provider(world, allow_requests=False)
        assert not any(item.event_type in {"institutional_aid_accepted", "institutional_aid_rejected",
                                           "institutional_aid_fulfilled", "institutional_aid_remediated"}
                       for item in world.events)
        return
    await review_institutional_aid_with_provider(world, allow_requests=False)

    receipts = [item for item in world.events
                if item.event_type in {INTERPRETED_EVENT, DECLINED_EVENT, FAILED_EVENT}]
    assert receipts and all(item.deltas == () for item in receipts)
    assert not any(item.event_type in {"institutional_aid_accepted", "institutional_aid_rejected",
                                       "institutional_aid_fulfilled", "institutional_aid_remediated"}
                   for item in world.events)
    assert json.dumps(world.config.model_dump(mode="json")).count("api_key") == 0


async def test_a_decline_is_its_own_event_type_not_a_sentence(monkeypatch):
    """A reader must tell "chose nothing" from "chose something" and from
    "could not be asked" by event type alone, never by parsing the prose."""
    world, _ = await requested_world()
    provider(monkeypatch, {"selected_id": ai_decider.NO_ACTION})
    await review_institutional_aid_with_provider(world, allow_requests=False)

    declines = [item for item in world.events if item.event_type == DECLINED_EVENT]
    assert len(declines) == 1
    assert declines[0].deltas == ()
    assert declines[0].causal_origin.value == "llm_interpretation"
    # The three outcomes never share one type.
    assert not any(item.event_type == INTERPRETED_EVENT for item in world.events)
    assert DECLINED_EVENT not in {INTERPRETED_EVENT, FAILED_EVENT}
    # A decline still spends the shared budget, exactly as before.
    assert ai_decider.spent_calls(world) == 1


async def test_aid_no_action_stops_later_family_consultations(monkeypatch):
    """An explicit decline is a complete actor turn, not an empty menu."""
    from src.sim.medieval import institutional_aid_policy as policy

    world = enable(pressured_world())
    calls = []

    async def response(_world, actor):
        calls.append(("response", actor.id))
        return False  # consulted, then NO_ACTION

    async def fulfillment(_world, actor):
        calls.append(("fulfillment", actor.id))
        return True

    async def remediation(_world, actor):
        calls.append(("remediation", actor.id))
        return True

    async def request(_world, actor):
        calls.append(("request", actor.id))
        return True

    monkeypatch.setattr(policy, "_respond_with_provider", response)
    monkeypatch.setattr(policy, "_fulfill_with_provider", fulfillment)
    monkeypatch.setattr(policy, "_remediate_with_provider", remediation)
    monkeypatch.setattr(policy, "_request_with_provider", request)

    await policy.review_institutional_aid_with_provider(world, allow_requests=True)

    assert calls
    assert {family for family, _actor in calls} == {"response"}
