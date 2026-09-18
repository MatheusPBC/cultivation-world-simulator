"""First concurrent-decision vertical: supply and institutional aid together."""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.concurrent_civil_decision import (
    concurrent_civil_options,
    review_concurrent_civil_decision_with_provider,
)
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.infrastructure import (
    REPAIR_AUTHORIZATION_ACTION,
    damage_site,
    execute_repair_authorization_option,
    repair_authorization_options,
    review_maintenance,
)
from src.sim.medieval.institutional_aid_policy import review_institutional_aid_with_provider
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.procurement import SUPPLY_OBJECTIVE_ACTION, execute_supply_objective_option, review_supply
from src.sim.medieval.institutional_aid import REQUEST_ACTION
from src.sim.medieval.persistence import world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from tests.test_medieval_institutional_aid import prepared_world

REQUESTER = EntityRef("polity", "auren")
OBJECTIVE_ID = "supply:pedraclara"
MAINTAINER = EntityRef("polity", "auren")
SITE = "passagem-negra"


def civil_pressure_world():
    """A prior automatic pass already left the plan blocked (stale local
    report); only after fresh reports arrive does a preview succeed. Nothing
    here force-sets a plan or fabricates a contradiction."""
    world = prepared_world()
    review_supply(world)
    plan = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    assert plan.stage == "blocked"
    refresh_reports(world)
    refresh_route_reports(world)
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 5, "ai_max_calls": 20})
    return world


def _damage(world, site_id=SITE, integrity=0.8):
    site = world.map.infrastructure_sites[site_id]
    fact = record_event(world, "storm_damaged_site", "Desabamento danificou a passagem.",
                        fact_kind=FactKind.STATE_TRANSITION,
                        deltas=(_delta("site", site_id, "integrity", site.integrity, integrity),))
    return damage_site(world, site_id, event_id=fact.id)


def repair_pressure_world():
    """A real prepared physical fact damages a polity-maintained site; the
    maintainer then observes it exactly as the engine would each boundary."""
    world = create_medieval_world(73)
    _damage(world)
    refresh_reports(world)
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 5, "ai_max_calls": 20})
    return world


def provider(monkeypatch, answer, prompts):
    async def call_llm_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        if answer == "first":
            payload = json.loads(prompt[prompt.index("{"):])
            return {"selected_id": payload["choices"][0]["id"]}
        return {"selected_id": answer}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


def test_the_natural_menu_offers_supply_and_aid_together():
    world = civil_pressure_world()
    options = concurrent_civil_options(world, REQUESTER)
    kinds = {option.decision()["action"] for option in options}
    assert kinds == {SUPPLY_OBJECTIVE_ACTION, REQUEST_ACTION}
    supply_option = next(o for o in options if o.decision()["action"] == SUPPLY_OBJECTIVE_ACTION)
    assert supply_option.objective_id == OBJECTIVE_ID
    # The option names only the objective; no supplier/quantity/route leaks out.
    assert set(vars(supply_option)) == {"id", "actor_ref", "objective_id"}


async def test_no_action_materializes_no_supply_or_aid(monkeypatch):
    world = civil_pressure_world()
    prompts = []
    provider(monkeypatch, ai_decider.NO_ACTION, prompts)
    before = world_snapshot(world)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert claimed == {OBJECTIVE_ID} and sites == set() and excluded == {REQUESTER}
    after = world_snapshot(world)
    assert not world.economy.freight_orders
    assert not world.knowledge.institutional_aid_notices
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}
    assert after["event_count"] > before["event_count"], "only a zero-delta receipt was added"


async def test_unavailable_provider_claims_nothing_so_the_deterministic_fallback_still_runs(monkeypatch):
    """A never-consulted actor (no budget, no key) must not starve the
    maintenance/procurement safety net that existed before this menu did.

    This is the exact failure an audited natural run surfaced: with
    ``ai_enabled`` on but no provider configured, every boundary offered the
    same repair/supply options forever without ever authorizing them, because
    the old code claimed them unconditionally whenever they were *offered*,
    not only when the actor was actually asked.
    """
    world = civil_pressure_world()
    monkeypatch.setattr(ai_decider, "provider_available", lambda: False)
    before = world_snapshot(world)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert claimed == set() and sites == set() and excluded == set()
    plan_before_review = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    review_supply(world, exclude_objective_ids=claimed)
    after = world_snapshot(world)
    assert {k: v for k, v in before.items() if k != "event_count"} != \
        {k: v for k, v in after.items() if k != "event_count"}, \
        "the deterministic pass must still be free to act on the un-claimed objective"


async def test_stale_option_id_leaves_no_plan_or_state_delta(monkeypatch):
    world = civil_pressure_world()
    options = concurrent_civil_options(world, REQUESTER)
    supply_option = next(o for o in options if o.decision()["action"] == SUPPLY_OBJECTIVE_ACTION)
    forged_id = supply_option.id + ":forged"
    prompts = []
    provider(monkeypatch, forged_id, prompts)
    before = world_snapshot(world)
    plan_before = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert claimed == {OBJECTIVE_ID} and sites == set() and excluded == {REQUESTER}
    after = world_snapshot(world)
    plan_after = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    assert plan_before == plan_after
    assert not world.economy.freight_orders and not world.knowledge.institutional_aid_notices
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}


def test_a_genuinely_expired_option_id_is_rejected_without_any_delta():
    """Not an invented string: yesterday's real, then-valid option is rejected
    once a fresh day recomposes the menu, purely because it is no longer in
    the current list — the executor's own staleness check, exercised directly."""
    world = civil_pressure_world()
    options = concurrent_civil_options(world, REQUESTER)
    supply_option = next(o for o in options if o.decision()["action"] == SUPPLY_OBJECTIVE_ACTION)

    # A day genuinely passes and reports refresh, exactly as the engine does.
    world.clock = world.clock.advance(1)
    refresh_reports(world)
    refresh_route_reports(world)
    fresh_ids = {o.id for o in concurrent_civil_options(world, REQUESTER)}
    assert supply_option.id not in fresh_ids, "the day must actually invalidate yesterday's id"

    expired_decision = record_event(world, "supply_objective_decided", "Decisão sobre opção expirada.",
                                    fact_kind=FactKind.DECISION, decision=supply_option.decision())
    before = world_snapshot(world)
    plan_before = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_supply_objective_option(world, REQUESTER, supply_option.id, expired_decision.id)
    after = world_snapshot(world)
    plan_after = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    assert plan_before == plan_after
    assert not world.economy.freight_orders
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}


async def test_choosing_supply_uses_the_existing_procurement_executor(monkeypatch):
    world = civil_pressure_world()
    options = concurrent_civil_options(world, REQUESTER)
    supply_option = next(o for o in options if o.decision()["action"] == SUPPLY_OBJECTIVE_ACTION)
    prompts = []
    provider(monkeypatch, supply_option.id, prompts)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert claimed == {OBJECTIVE_ID} and sites == set() and excluded == {REQUESTER}
    plan = world.strategy.plans[f"plan:{OBJECTIVE_ID}"]
    assert plan.stage == "await_delivery" and plan.order_ids
    assert set(plan.order_ids) <= set(world.economy.freight_orders)
    assert not world.knowledge.institutional_aid_notices, "supply was chosen, not aid"
    decision = next(e for e in world.events if e.event_type == "institutional_decision_turn_decided")
    assert decision.decision == supply_option.decision()
    assert decision.causal_links, "the decision carries canonical evidence, not private state"
    assert decision.causal_origin.value == "actor_decision"


async def test_choosing_aid_uses_the_existing_institutional_aid_executor(monkeypatch):
    world = civil_pressure_world()
    options = concurrent_civil_options(world, REQUESTER)
    aid_option = next(o for o in options if o.decision()["action"] == REQUEST_ACTION)
    prompts = []
    provider(monkeypatch, aid_option.id, prompts)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert claimed == {OBJECTIVE_ID} and sites == set() and excluded == {REQUESTER}
    assert len(world.knowledge.institutional_aid_notices) == 1
    notice = next(iter(world.knowledge.institutional_aid_notices.values()))
    assert notice.requester_ref == REQUESTER and notice.recipient_ref == aid_option.provider_ref
    assert not world.economy.freight_orders, "aid was chosen, not supply"
    assert world.agenda.get(f"diplomatic-review:{world.clock.absolute_day + 1}") is not None, \
        "the same schedule_review the standalone aid policy calls"
    decision = next(e for e in world.events if e.event_type == "institutional_decision_turn_decided")
    assert decision.decision == aid_option.decision()
    assert decision.causal_origin.value == "actor_decision"


async def test_being_covered_by_the_menu_suppresses_a_second_separate_aid_request(monkeypatch):
    """A NO_ACTION menu answer must not let the standalone aid review ask again,
    while still leaving independent respond/fulfil/remediate untouched (there
    is none pending here, so nothing at all fires for this actor)."""
    world = civil_pressure_world()
    prompts = []
    provider(monkeypatch, ai_decider.NO_ACTION, prompts)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert excluded == {REQUESTER}
    before = world_snapshot(world)
    await review_institutional_aid_with_provider(world, allow_requests=True, excluded_requesters=excluded)
    after = world_snapshot(world)
    assert not world.knowledge.institutional_aid_notices
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}


def test_the_non_ai_fallback_leaves_review_supply_exactly_as_before():
    baseline = civil_pressure_world()
    baseline.config = baseline.config.model_copy(update={"ai_enabled": False})
    review_supply(baseline)

    control = civil_pressure_world()
    control.config = control.config.model_copy(update={"ai_enabled": False})
    review_supply(control, exclude_objective_ids=set())

    assert world_snapshot(baseline) == world_snapshot(control)


# --- Second slice: repair authorization joins the civil menu -----------------


def test_repair_option_appears_only_with_valid_observation_and_authority():
    world = repair_pressure_world()
    options = concurrent_civil_options(world, MAINTAINER)
    repair_option = next((o for o in options if o.decision()["action"] == REPAIR_AUTHORIZATION_ACTION), None)
    assert repair_option is not None and repair_option.site_id == SITE
    # Only canonical IDs: no blueprint, stock, account or quantity leaks out.
    assert set(vars(repair_option)) == {"id", "actor_ref", "site_id"}

    # No observation yet (the maintainer never saw the damage): no option.
    unobserved = create_medieval_world(73)
    _damage(unobserved)
    assert repair_authorization_options(unobserved, MAINTAINER) == ()

    # Observed, but the maintainer's own mandate lapsed: no option either.
    revoked = repair_pressure_world()
    office = revoked.authority.offices["office:polity:auren"]
    revoked.authority.offices[office.id] = office.model_copy(
        update={"scopes": tuple(scope for scope in office.scopes if scope != "supply")})
    assert repair_authorization_options(revoked, MAINTAINER) == ()


async def test_no_action_creates_no_repair_project(monkeypatch):
    world = repair_pressure_world()
    provider(monkeypatch, ai_decider.NO_ACTION, [])
    before = world_snapshot(world)
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert sites == {SITE}
    after = world_snapshot(world)
    assert not world.economy.repairs
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}


async def test_choosing_repair_uses_start_repair_and_leaves_integrity_unchanged(monkeypatch):
    world = repair_pressure_world()
    options = concurrent_civil_options(world, MAINTAINER)
    repair_option = next(o for o in options if o.decision()["action"] == REPAIR_AUTHORIZATION_ACTION)
    integrity_before = world.map.infrastructure_sites[SITE].integrity
    provider(monkeypatch, repair_option.id, [])
    claimed, sites, excluded = await review_concurrent_civil_decision_with_provider(world)
    assert sites == {SITE}
    assert len(world.economy.repairs) == 1
    project = next(iter(world.economy.repairs.values()))
    assert project.site_id == SITE and project.stage == "waiting" and project.restored_permille == 0
    assert world.map.infrastructure_sites[SITE].integrity == integrity_before, \
        "authorizing work repairs nothing by itself"
    decision = next(e for e in world.events if e.event_type == "institutional_decision_turn_decided")
    assert decision.decision == repair_option.decision()
    assert decision.causal_links, "the decision carries canonical evidence, not private state"
    assert decision.causal_origin.value == "actor_decision"


def test_a_genuinely_stale_repair_option_is_rejected_without_any_delta():
    """Not an invented string: the site is genuinely authorized through the
    deterministic fallback, so yesterday's menu option is no longer current."""
    world = repair_pressure_world()
    options = concurrent_civil_options(world, MAINTAINER)
    repair_option = next(o for o in options if o.decision()["action"] == REPAIR_AUTHORIZATION_ACTION)

    review_maintenance(world)
    assert world.economy.repairs, "the fallback must have genuinely authorized the site"
    fresh_ids = {o.id for o in repair_authorization_options(world, MAINTAINER)}
    assert repair_option.id not in fresh_ids, "an active repair must retire the old option"

    stale_decision = record_event(world, "repair_authorization_decided", "Decisão sobre opção expirada.",
                                  fact_kind=FactKind.DECISION, decision=repair_option.decision())
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        execute_repair_authorization_option(world, MAINTAINER, repair_option.id, stale_decision.id)
    after = world_snapshot(world)
    assert {k: v for k, v in before.items() if k != "event_count"} == \
        {k: v for k, v in after.items() if k != "event_count"}


def test_repair_can_coexist_with_another_civil_option_in_one_causal_fixture():
    """The same polity, auren, both maintains the damaged pass and administers
    the pressured settlement: one real actor, two independently valid options."""
    world = civil_pressure_world()
    _damage(world)
    refresh_reports(world)
    refresh_route_reports(world)
    options = concurrent_civil_options(world, REQUESTER)
    kinds = {option.decision()["action"] for option in options}
    assert REPAIR_AUTHORIZATION_ACTION in kinds
    assert kinds & {SUPPLY_OBJECTIVE_ACTION, REQUEST_ACTION}


def test_the_non_ai_fallback_leaves_review_maintenance_exactly_as_before():
    baseline = repair_pressure_world()
    baseline.config = baseline.config.model_copy(update={"ai_enabled": False})
    review_maintenance(baseline)

    control = repair_pressure_world()
    control.config = control.config.model_copy(update={"ai_enabled": False})
    review_maintenance(control, exclude_site_ids=set())

    assert world_snapshot(baseline) == world_snapshot(control)
