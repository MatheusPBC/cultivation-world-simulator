"""The drake acts only when a provider chooses; never by deadline or routine."""

import pytest

from src.classes.mechanical_language import EntityRef
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.creature_policy import REVIEW_KIND, review_creatures
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.run.medieval_creatures import DRAKE_ECHO_ID, DRAKE_ID, ROUTE_ID
from tests.test_medieval_creatures import buy_across_the_river, crossed_world
from tests.test_medieval_logistics import total_food

AUREN = EntityRef("polity", "auren")


def enable(world, *, per_step=256, maximum=1000):
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": per_step,
                                                   "ai_max_calls": maximum})
    return world


def provider(monkeypatch, decide):
    """Local stand-in for the existing client: no network and no key."""
    prompts = []

    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        answer = decide(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)
    return prompts


def choose(kind_marker):
    """Pick the primary drake's choice; leave the second individual independent."""
    def decide(prompt):
        import json
        payload = json.loads(prompt[prompt.index("{"):])
        if payload.get("you_are", {}).get("id") == DRAKE_ECHO_ID:
            return {"selected_id": "NO_ACTION"}
        for choice in payload["choices"]:
            if kind_marker in choice["label"]:
                return {"selected_id": choice["id"]}
        return {"selected_id": "NO_ACTION"}
    return decide


def primary_creature_prompts(prompts):
    return [prompt for prompt in prompts if f'"id": "{DRAKE_ID}"' in prompt]


async def hungry_world():
    """Real crossings made the drake hungry and earned it a dated turn."""
    world = enable(await crossed_world())
    assert not world.creatures.demands, "hunger alone demands nothing"
    assert any(entry["kind"] == REVIEW_KIND for entry in world.agenda.to_dict())
    return world


async def test_a_provider_drives_demand_and_a_tribute_settles_it(tmp_path, monkeypatch):
    world = await hungry_world()
    prompts = provider(monkeypatch, choose("Exigir tributo"))

    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    assert demand.stage == "open" and world.map.routes[ROUTE_ID].enabled
    for prompt in prompts:
        # The drake speaks of its own body only; no institution's holdings.
        assert "treasury:" not in prompt and "stock:" not in prompt

    # The next day the noticed administrations, and only they, may answer.
    prompts = provider(monkeypatch, choose("Entregar"))
    food = total_food(world)
    condition = world.creatures.creatures[DRAKE_ID].condition
    for _ in range(3):
        if world.creatures.demands[demand.id].stage == "satisfied":
            break
        await engine.step()

    settled = world.creatures.demands[demand.id]
    assert settled.stage == "satisfied"
    assert world.creatures.creatures[DRAKE_ID].condition > condition
    assert total_food(world) < food, "the tribute was really eaten"
    assert world.map.routes[ROUTE_ID].enabled
    for prompt in prompts:
        assert "hunger_threshold" not in prompt and "condition" not in prompt
    path = tmp_path / "drake-ai.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


async def test_without_a_choice_no_deadline_demands_or_closes_the_river(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))

    # Nobody offers anything: the provider declines every institutional turn.
    provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})
    while world.clock.absolute_day < demand.due_day:
        await engine.step()
    assert world.creatures.demands[demand.id].stage == "open"
    assert world.map.routes[ROUTE_ID].enabled, "a deadline closes nothing by itself"

    # No daily retry is minted by hunger or silence. Disabled/error behaviour
    # is checked on new worlds that each have a real perception-granted turn.
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())
    disabled = await hungry_world()
    disabled.config = disabled.config.model_copy(update={"ai_enabled": False})
    await MedievalSimulator(disabled).step()
    assert not disabled.creatures.demands and disabled.map.routes[ROUTE_ID].enabled

    failed = await hungry_world()
    provider(monkeypatch, lambda prompt: RuntimeError("provider down"))
    with pytest.raises(ProviderDecisionRequired):
        await MedievalSimulator(failed).step()
    assert failed.map.routes[ROUTE_ID].enabled
    assert not any(item.event_type == "ai_decision_failed" for item in failed.events)

    # A later crossing remains factual, but an ignored open demand does not
    # mint another creature turn just because more cargo passes the river.
    buy_across_the_river(world)
    await engine.step()
    await engine.step()
    pending = sum(item.quantity for item in world.economy.parcels.values())
    assert pending, "the bilateral cargo is still on the water"
    provider(monkeypatch, choose("Fechar a passagem"))
    for _ in range(4):
        await engine.step()
    assert world.map.routes[ROUTE_ID].enabled
    assert world.creatures.creatures[DRAKE_ID].restricted_route_id is None
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())


@pytest.mark.asyncio
async def test_deadline_turn_can_choose_material_retaliation_through_the_engine(monkeypatch):
    import json

    world = await hungry_world()
    prompts = []

    def choose_request_or_retaliation(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        actor = payload.get("you_are", {})
        if actor.get("id") != DRAKE_ID:
            return {"selected_id": "NO_ACTION"}
        choices = payload.get("choices", [])
        for option in choices:
            if "Atacar uma coorte anônima" in option.get("label", ""):
                return {"selected_id": option["id"]}
        for option in choices:
            if "Exigir tributo" in option.get("label", ""):
                return {"selected_id": option["id"]}
        return {"selected_id": "NO_ACTION"}

    prompts = provider(monkeypatch, choose_request_or_retaliation)
    engine = MedievalSimulator(world)
    for _ in range(24):
        if any(item.creature_id == DRAKE_ID for item in world.creatures.demands.values()):
            demand = next(item for item in world.creatures.demands.values()
                          if item.creature_id == DRAKE_ID)
            if any(event.event_type == "creature_attacked_population"
                   and event.causal_payload.get("actor_ref", {}).get("id") == DRAKE_ID
                   for event in world.events):
                break
        await engine.step()

    demand = next(item for item in world.creatures.demands.values()
                  if item.creature_id == DRAKE_ID)
    attack = next(event for event in world.events
                  if event.event_type == "creature_attacked_population"
                  and event.causal_payload.get("actor_ref", {}).get("id") == DRAKE_ID)
    decision = world.event_index()[attack.causal_payload["decision_event_id"]]
    assert attack.day == demand.due_day
    assert decision.fact_kind.value == "decision"
    assert decision.causal_origin.value == "actor_decision"
    assert decision.decision["action"] == "creature_attack_population"
    assert decision.id in {link.cause_event_id for link in attack.causal_links}
    impact = attack.causal_payload["hazard_impact"]
    target_id = impact["target_ref"]["id"]
    assert impact["affected_count"] > 0
    assert any(delta.owner_kind == "population_group" and delta.owner_id == target_id
               and delta.aspect == "count"
               and delta.after == str(world.society.population[target_id].count)
               for delta in attack.deltas)
    assert demand.last_event_id == attack.id
    assert world.creatures.demands[demand.id].stage == "expired"
    assert world.map.routes[demand.route_id].enabled
    assert prompts, "the scheduled turn must reach the selected provider boundary"


@pytest.mark.asyncio
async def test_creature_site_damage_is_repaired_through_the_engine(monkeypatch, tmp_path):
    import json

    from src.sim.medieval.concurrent_civil_decision import REPAIR_ADAPTER
    from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn_with_provider
    from src.sim.medieval.infrastructure import (current_observation,
                                                 repair_authorization_options)
    from tests.test_medieval_infrastructure import provisioned

    site_id = "docas-de-portovelho"
    world = await hungry_world()
    site = world.map.infrastructure_sites[site_id]
    maintainer = site.maintainer_ref
    capacity_before = world.map.get_route_operational_capacity(ROUTE_ID)

    def choose_damage_then_repair(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        choices = payload.get("choices", [])
        for option in choices:
            if option.get("label", "").startswith("Autorizar o reparo da instalação"):
                return {"selected_id": option["id"]}
        actor = payload.get("you_are", {})
        if actor.get("id") != DRAKE_ID:
            return {"selected_id": "NO_ACTION"}
        for option in choices:
            if "Danificar a instalação aquática" in option.get("label", ""):
                return {"selected_id": option["id"]}
        for option in choices:
            if "Exigir tributo" in option.get("label", ""):
                return {"selected_id": option["id"]}
        return {"selected_id": "NO_ACTION"}

    prompts = provider(monkeypatch, choose_damage_then_repair)
    engine = MedievalSimulator(world)
    for _ in range(24):
        await engine.step()
        if world.map.infrastructure_sites[site_id].integrity < 1.0:
            break

    damage = next(event for event in world.events if event.event_type == "creature_damaged_site")
    decision = world.event_index()[damage.causal_payload["decision_event_id"]]
    demand = next(item for item in world.creatures.demands.values()
                  if item.creature_id == DRAKE_ID)
    assert damage.day == demand.due_day
    assert decision.fact_kind.value == "decision"
    assert decision.causal_origin.value == "actor_decision"
    assert any(link.cause_event_id == decision.id for link in damage.causal_links)
    assert world.map.infrastructure_sites[site_id].integrity < 1.0
    assert world.map.get_route_operational_capacity(ROUTE_ID) < capacity_before
    report = current_observation(world, maintainer, site_id)
    assert report is not None and report.integrity < 1.0
    report_event = world.event_index()[report.event_id]
    assert any(link.cause_event_id == damage.id for link in report_event.causal_links)
    repairs = repair_authorization_options(world, maintainer)
    assert any(option.site_id == site_id for option in repairs)

    # This pressured fixture begins the response with its local repair materials
    # already provisioned; the simulation does not create them as a consequence
    # of the damage or the maintainer's decision.
    provisioned(world, site_id)
    await review_institutional_decision_turn_with_provider(
        world, (REPAIR_ADAPTER,), actors=(maintainer,))
    repair = next(event for event in world.events if event.event_type == "repair_started")
    repair_decision = world.event_index()[repair.causal_payload["decision_event_id"]]
    project = next(project for project in world.economy.repairs.values()
                   if project.site_id == site_id)
    blueprint = world.economy.repair_blueprints[project.blueprint_id]
    assert repair_decision.causal_origin.value == "actor_decision"
    assert any(link.cause_event_id == report.event_id for link in repair.causal_links)
    assert any(link.cause_event_id == damage.id for link in report_event.causal_links)
    assert project.stage == "waiting"
    assert world.map.infrastructure_sites[site_id].integrity < 1.0
    repair_stock_before = dict(world.economy.stocks[project.stock_id].goods)

    for _ in range(15):
        if world.map.get_route_operational_capacity(ROUTE_ID) >= capacity_before:
            break
        await engine.step()

    assert project.id in world.economy.repairs
    assert world.economy.repairs[project.id].stage == "completed"
    assert world.map.infrastructure_sites[site_id].integrity == pytest.approx(1.0)
    assert world.map.get_route_operational_capacity(ROUTE_ID) == pytest.approx(capacity_before)
    repair_completion = next(event for event in world.events
                             if event.event_type == "repair_progressed"
                             and any(delta.owner_kind == "site" and delta.owner_id == site_id
                                     and float(delta.after) >= 1.0 for delta in event.deltas))
    assert any(link.cause_event_id == repair.id for link in repair_completion.causal_links)
    assert all(world.economy.stocks[project.stock_id].goods.get(resource, 0)
               < repair_stock_before.get(resource, 0) for resource in blueprint.inputs)
    from tools.medieval_causal_audit import audit
    path = tmp_path / "creature-site-repair.mws"
    save_world(world, path)
    causal_audit = audit(path)
    violations = {key: value for key, value in causal_audit.items()
                  if key in {"story_material_events", "decision_origin_without_source",
                             "decision_authorship_errors", "decision_source_errors",
                             "root_premise_errors", "unrooted_material_events",
                             "interpretation_material_events", "broken_cause_ids"} and value}
    violations["unrooted_event_types"] = {
        event_id: world.event_index()[event_id].event_type
        for event_id in causal_audit["unrooted_material_events"]
    }
    assert causal_audit["ok"], violations
    assert prompts


@pytest.mark.asyncio
async def test_unanswered_demand_restricts_then_creature_later_withdraws_by_choice(monkeypatch):
    import json

    world = await hungry_world()

    def choose_restrict_then_withdraw(prompt):
        payload = json.loads(prompt[prompt.index("{"):])
        actor = payload.get("you_are", {})
        if actor.get("id") != DRAKE_ID:
            return {"selected_id": "NO_ACTION"}
        for option in payload.get("choices", []):
            if "Recuar e reabrir" in option.get("label", ""):
                return {"selected_id": option["id"]}
        for option in payload.get("choices", []):
            if "Fechar a passagem" in option.get("label", ""):
                return {"selected_id": option["id"]}
        for option in payload.get("choices", []):
            if "Exigir tributo" in option.get("label", ""):
                return {"selected_id": option["id"]}
        return {"selected_id": "NO_ACTION"}

    prompts = provider(monkeypatch, choose_restrict_then_withdraw)
    engine = MedievalSimulator(world)
    for _ in range(40):
        await engine.step()
        if (any(event.event_type == "creature_withdrew" for event in world.events)
                and world.map.routes[ROUTE_ID].enabled):
            break

    demand = next(item for item in world.creatures.demands.values()
                  if item.creature_id == DRAKE_ID)
    restriction = next(event for event in world.events
                       if event.event_type == "creature_restricted_route")
    withdrawal = next(event for event in world.events if event.event_type == "creature_withdrew")
    events = world.event_index()
    restrict_decision = next(events[link.cause_event_id] for link in restriction.causal_links
                             if events[link.cause_event_id].fact_kind.value == "decision")
    withdraw_decision = next(events[link.cause_event_id] for link in withdrawal.causal_links
                             if events[link.cause_event_id].fact_kind.value == "decision")
    institutional_refusal = next(event for event in world.events
                                 if event.fact_kind.value == "decision"
                                 and (event.decision or {}).get("action") == "no_action"
                                 and (event.decision or {}).get("actor_ref", {}).get("kind") == "polity")
    refusal_actor = EntityRef("polity", institutional_refusal.decision["actor_ref"]["id"])
    refusal_notice = next(notice for notice in
                          world.knowledge.creature_tributes_for_actor(refusal_actor)
                          if notice.demand_id == demand.id)
    assert demand.stage == "expired"
    assert restriction.day == demand.due_day
    assert withdrawal.day == restriction.day + 1
    assert any(delta.owner_kind == "route" and delta.owner_id == ROUTE_ID
               and delta.aspect == "enabled" and delta.after == "False"
               for delta in restriction.deltas)
    assert any(delta.owner_kind == "route" and delta.owner_id == ROUTE_ID
               and delta.aspect == "enabled" and delta.after == "True"
               for delta in withdrawal.deltas)
    assert restrict_decision.causal_origin.value == "actor_decision"
    assert withdraw_decision.causal_origin.value == "actor_decision"
    assert institutional_refusal.causal_origin.value == "actor_decision"
    assert institutional_refusal.decision["selected_affordance_id"] == "NO_ACTION"
    assert any(link.cause_event_id == refusal_notice.event_id
               for link in institutional_refusal.causal_links)
    assert any(link.cause_event_id == restriction.id for link in withdrawal.causal_links)
    assert world.map.routes[ROUTE_ID].enabled
    assert prompts


async def test_creature_selection_that_goes_stale_pauses_instead_of_noop(monkeypatch):
    from src.sim.medieval import creature_policy as policy

    world = await hungry_world()
    initial = policy.creature_options(world, DRAKE_ID)
    assert len(initial) > 1
    calls = 0

    def options(current, creature_id):
        nonlocal calls
        calls += 1
        return initial if calls == 1 else ()

    monkeypatch.setattr(policy, "creature_options", options)
    provider(monkeypatch, lambda prompt: {"selected_id": initial[0].id})
    due = world.agenda.pop_due(world.clock.absolute_day + 1)
    with pytest.raises(ProviderDecisionRequired):
        await review_creatures(world, due)
    assert not any(event.event_type == "creature_decided" for event in world.events)
async def test_many_real_crossings_do_not_fan_out_reviews_while_demand_is_open(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    crossings_before = world.creatures.creatures[DRAKE_ID].perceived_crossings
    prompts = provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})
    for _ in range(8):
        buy_across_the_river(world)

    for _ in range(40):
        await engine.step()
        if (world.clock.absolute_day >= demand.due_day
                and not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())):
            break

    creature_prompts = [prompt for prompt in primary_creature_prompts(prompts)
                        if '"crossings_you_saw"' in prompt]
    assert world.creatures.creatures[DRAKE_ID].perceived_crossings > crossings_before
    assert len(creature_prompts) == 1, "only the bounded deadline can offer retaliation"
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())


async def test_ignored_expired_demand_stops_reviews_and_keeps_route_open(monkeypatch):
    world = await hungry_world()
    provider(monkeypatch, choose("Exigir tributo"))
    engine = MedievalSimulator(world)
    for _ in range(6):
        if world.creatures.demands:
            break
        await engine.step()
    demand = next(iter(world.creatures.demands.values()))
    prompts = provider(monkeypatch, lambda prompt: {"selected_id": "NO_ACTION"})

    while world.clock.absolute_day < demand.due_day:
        await engine.step()
    creature_calls = len([prompt for prompt in primary_creature_prompts(prompts)
                          if '"crossings_you_saw"' in prompt])
    assert demand.stage == "open" and demand.due_day <= world.clock.absolute_day
    assert world.map.routes[ROUTE_ID].enabled

    for _ in range(6):
        buy_across_the_river(world)
    for _ in range(10):
        await engine.step()

    assert len([prompt for prompt in primary_creature_prompts(prompts)
                if '"crossings_you_saw"' in prompt]) == creature_calls
    assert not any(item["kind"] == REVIEW_KIND for item in world.agenda.to_dict())
    assert world.map.routes[ROUTE_ID].enabled
