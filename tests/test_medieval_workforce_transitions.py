"""Focused causal coverage for local economic workforce transitions."""

import copy
from types import SimpleNamespace

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import produce_monthly
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.intelligence import refresh_reports
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.workforce import (accept_workforce_transition, labor_shortfall, refresh_workforce_notices,
                                         WorkforceTransitionOption, resolve_workforce_transitions, workforce_adapters,
                                         workforce_transition_options, _transition_situation)
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval import ai_decider


CUSTOMS_SITE = "passagem-negra"
CUSTOMS_ROUTE = "road-pontenegro-ferroalto"


@pytest.mark.asyncio
async def test_natural_food_pressure_can_improve_through_workforce_decisions():
    """A pressured natural run improves only after material labour choices.

    This is deliberately a bounded acceptance fixture, not a promise that
    every natural seed is prosperous.  It proves that the existing fallback
    selects enumerated workforce/employment affordances and that the later
    production receipts can lower the same food pressure without a subsidy or
    narrative event.
    """
    world = create_medieval_world(73)
    engine = MedievalSimulator(world)
    initial_pressure = None
    while world.clock.absolute_day < 60:
        await engine.step()
        if world.clock.absolute_day == 30:
            initial_pressure = sum(need.missing_food for need in world.economy.needs.values())

    final_pressure = sum(need.missing_food for need in world.economy.needs.values())
    assert initial_pressure is not None and final_pressure < initial_pressure
    assert world.society.workforce_transitions
    assert any(event.event_type == "workforce_transition_completed" for event in world.events)
    assert world.economy.employment_contracts
    assert any(event.event_type == "production_limited" and any(
        delta.owner_kind == "production" and delta.aspect == "labor_shortfall"
        for delta in event.deltas) for event in world.events)


def labour_limited_world():
    world = create_medieval_world(73)
    facility = world.economy.facilities["works:campos-do-lume"]
    recipe = world.economy.recipes[facility.recipe_id]
    # The site and material recipe remain canonical; only this prepared fixture
    # asks that a local production line need artisans where only farmers exist.
    world.economy.recipes[recipe.id] = recipe.model_copy(update={"occupation": "artisan"})
    produce_monthly(world)
    refresh_workforce_notices(world)
    notice = next(item for item in world.knowledge.workforce_offer_notices.values()
                  if item.demand_id.endswith(facility.id))
    group = world.society.population[notice.source_group_id]
    options = workforce_transition_options(world, group.id)
    assert len(options) == 1
    return world, group, facility, options[0]


def decide(world, option):
    notice = world.knowledge.workforce_offer_notices[option.notice_id]
    return record_event(world, "workforce_transition_decided", "O grupo avaliou sua oferta local.",
                        fact_kind=FactKind.DECISION, decision=option.decision(), cause_ids=(notice.event_id,))


@pytest.mark.asyncio
async def test_population_group_can_choose_workforce_offer_from_the_composed_turn(monkeypatch):
    world, group, _facility, option = labour_limited_world()
    actor = EntityRef("population_group", group.id)
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr(ai_decider, "within_budget", lambda _world: True)
    async def choose(*_args, **_kwargs):
        return option.id
    monkeypatch.setattr(ai_decider, "select_option", choose)

    _claims, covered = await review_institutional_decision_turn(world, actor, workforce_adapters())

    assert covered is True
    assert len(world.society.workforce_transitions) == 1
    transition = next(iter(world.society.workforce_transitions.values()))
    assert transition.source_group_id == group.id
    assert transition.decision_event_id in {event.id for event in world.events
                                            if event.event_type == "institutional_decision_turn_decided"}


def test_local_transition_is_dated_conservative_and_causally_material(tmp_path):
    world, group, facility, option = labour_limited_world()
    sponsor = world.economy.accounts[facility.payroll_account_id]
    household = world.economy.accounts[f"household:{group.id}"]
    before_money = sum(account.balance for account in world.economy.accounts.values())
    before_sponsor, before_household = sponsor.balance, household.balance

    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)

    assert transition.count == 1
    assert transition.due_day == transition.started_day + 30
    assert world.society.available_count(group.id) == group.count - 1
    assert world.economy.accounts[sponsor.id].balance == before_sponsor - transition.stipend_per_person
    assert world.economy.accounts[household.id].balance == before_household + transition.stipend_per_person
    assert sum(account.balance for account in world.economy.accounts.values()) == before_money
    assert not workforce_transition_options(world, group.id), "a reserved group cannot work, migrate, or accept again"
    start = next(event for event in world.events if event.event_type == "workforce_transition_started")
    assert start.fact_kind == FactKind.STATE_TRANSITION
    assert start.causal_origin.value == "actor_decision"
    assert start.causal_payload == {
        "decision_event_id": transition.decision_event_id,
        "actor_ref": EntityRef("population_group", group.id).to_dict(),
        "selected_affordance_id": option.id,
    }
    assert any(link.cause_event_id == transition.decision_event_id for link in start.causal_links)


    path = tmp_path / "mid-transition.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.society.workforce_transitions[transition.id] == transition
    awaitable = MedievalSimulator(resumed).step()
    # The scheduled day is the next monthly boundary; resolving it happens
    # before that boundary's production phase.
    import asyncio
    asyncio.run(awaitable)
    assert transition.id not in resumed.society.workforce_transitions
    artisan = resumed.society.population[transition.target_group_id]
    assert artisan.occupation == "artisan" and artisan.count == transition.count
    completed = next(event for event in resumed.events if event.event_type == "workforce_transition_completed")
    assert completed.fact_kind == FactKind.STATE_TRANSITION
    assert transition.last_event_id in {link.cause_event_id for link in completed.causal_links}


def test_spent_sponsor_funds_remove_a_same_day_workforce_option():
    world, group, facility, option = labour_limited_world()
    assert option in workforce_transition_options(world, group.id)
    account = world.economy.accounts[facility.payroll_account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})

    # Offers are notices, not reservations. Another decision may spend the
    # sponsor's funds before this group receives its turn.
    assert workforce_transition_options(world, group.id) == ()


def labour_signal(world, facility):
    """The typed, quantified labour shortfall recorded by today's production."""
    return next((labor_shortfall(event, "production", facility.id) for event in world.events
                 if event.day == world.clock.absolute_day
                 and labor_shortfall(event, "production", facility.id) is not None), None)


def due_situations(world, transition):
    """Advance to the scheduled day and take the agenda entry, as the runner does."""
    world.clock = world.clock.advance(transition.due_day - world.clock.absolute_day)
    return [item for item in world.agenda.pop_due(world.clock.absolute_day)
            if item.kind == "workforce_transition"]


def test_completion_moves_both_cohorts_under_its_own_receipt():
    world, group, facility, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    before = world.society.population[group.id].count

    resolve_workforce_transitions(world, due_situations(world, transition))

    completed = next(event for event in world.events if event.event_type == "workforce_transition_completed")
    assert transition.id not in world.society.workforce_transitions
    assert world.society.population[group.id].count == before - transition.count
    artisans = world.society.population[transition.target_group_id]
    assert artisans.occupation == "artisan" and artisans.count == transition.count
    assert world.society.population[group.id].last_event_id == completed.id == artisans.last_event_id
    assert world.society.available_count(group.id) == world.society.population[group.id].count
    world.society.validate(set(world.map.regions), world)


def test_an_impossible_completion_is_a_fact_without_a_spurious_material_event(tmp_path):
    world, group, facility, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    situations = due_situations(world, transition)
    # A legitimate change of the world: the source cohort is no longer farming.
    source = world.society.population[group.id]
    world.society.population[source.id] = source.model_copy(update={"occupation": "artisan"})
    counts = {key: item.count for key, item in world.society.population.items()}
    money = sum(account.balance for account in world.economy.accounts.values())

    resolve_workforce_transitions(world, situations)

    failed = next(event for event in world.events if event.event_type == "workforce_transition_failed")
    assert failed.fact_kind == FactKind.STATE_TRANSITION
    assert any(delta.owner_kind == "workforce_transition" and delta.owner_id == transition.id
               and delta.aspect == "stage" and delta.before == "training" and delta.after == "failed"
               for delta in failed.deltas)
    assert transition.last_event_id in {link.cause_event_id for link in failed.causal_links}
    assert not any(event.event_type == "workforce_transition_completed" for event in world.events)
    assert transition.id not in world.society.workforce_transitions
    assert {key: item.count for key, item in world.society.population.items()} == counts
    assert sum(account.balance for account in world.economy.accounts.values()) == money
    assert world.society.available_count(group.id) == world.society.population[group.id].count
    world.society.validate(set(world.map.regions), world)
    save_world(world, tmp_path / "released-transition.mws")


def test_a_superseded_offer_is_withdrawn_by_a_fact_not_deleted_silently():
    world, group, facility, option = labour_limited_world()
    notice = world.knowledge.workforce_offer_notices[option.notice_id]
    superseded = notice.observation()
    world.clock = world.clock.advance(30)
    produce_monthly(world)
    shortfall = labour_signal(world, facility)
    assert shortfall is not None and shortfall > 0, "production must restate the material labour shortfall"
    refresh_workforce_notices(world)

    retraction = next(event for event in world.events
                      if event.event_type == "workforce_offer_retracted"
                      and any(delta.owner_kind == "workforce_offer" and delta.owner_id == notice.id
                              for delta in event.deltas))
    assert retraction.fact_kind == FactKind.STATE_TRANSITION
    assert any(delta.owner_kind == "workforce_offer" and delta.owner_id == notice.id
               and delta.aspect == "observation" and delta.before == superseded and delta.after == "None"
               for delta in retraction.deltas)
    current = world.knowledge.workforce_offer_notices.get(notice.id)
    assert current is None or current.observed_day == world.clock.absolute_day
    world.knowledge.validate(world)
    world.society.validate(set(world.map.regions), world)


def test_a_demand_backing_an_active_transition_is_never_rewritten():
    world, group, facility, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    notice = world.knowledge.workforce_offer_notices[transition.notice_id]
    report = world.knowledge.workforce_demand_reports[transition.demand_id]

    world.clock = world.clock.advance(15)
    produce_monthly(world)
    assert labour_signal(world, facility), "a new material labour signal must reach the refresh"
    events = len(world.events)
    refresh_workforce_notices(world)

    assert world.knowledge.workforce_offer_notices[transition.notice_id] == notice
    assert world.knowledge.workforce_demand_reports[transition.demand_id] == report
    assert len(world.events) >= events
    assert not any(event.event_type == "workforce_offer_retracted"
                   and any(delta.owner_kind == "workforce_offer" and delta.owner_id == notice.id
                           for delta in event.deltas)
                   for event in world.events)
    assert world.society.workforce_transitions[transition.id] == transition
    world.knowledge.validate(world)
    world.society.validate(set(world.map.regions), world)


def test_the_labour_signal_is_typed_quantified_and_restated_every_cycle():
    world, group, facility, option = labour_limited_world()
    recipe = world.economy.recipes[facility.recipe_id]
    first = labour_signal(world, facility)
    assert 0 < first <= recipe.workers
    report = next(iter(world.knowledge.workforce_demand_reports.values()))
    assert 0 < report.count <= first
    world.knowledge.validate(world)

    # An unchanged limitation records no new field delta, but the signal is a
    # statement about this cycle, so it must be restated for the next demand.
    world.clock = world.clock.advance(30)
    produce_monthly(world)
    assert labour_signal(world, facility) == first


def test_transition_situation_exposes_dated_unaffordable_reading_without_balances():
    from src.sim.medieval.economy import consume_monthly
    from src.systems.time import WorldClock

    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.clock = WorldClock(30)
    target = "pedraclara"
    stock = world.economy.stocks[f"stock:{target}"]
    world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {"food": 1000}})
    consume_monthly(world)
    group = next(item for item in world.society.population.values() if item.settlement_id == target)
    actor = EntityRef("population_group", group.id)

    assert _transition_situation(world, actor, ())["unaffordable_food"] == 0
    refresh_reports(world)
    situation = _transition_situation(world, actor, ())

    assert situation["unaffordable_food"] > 0
    assert situation["unaffordable_group_count"] > 0
    assert "household" not in situation and "balance" not in situation


def test_transition_situation_reports_zero_affordability_without_a_reading():
    world, group, _facility, _option = labour_limited_world()
    actor = EntityRef("population_group", group.id)

    situation = _transition_situation(world, actor, ())

    assert situation["unaffordable_food"] == 0
    assert situation["unaffordable_group_count"] == 0


def test_agricultural_labour_limit_creates_a_private_return_to_farming_offer():
    world = create_medieval_world(73)
    produce_monthly(world)
    refresh_workforce_notices(world)
    assert {report.target_occupation for report in world.knowledge.workforce_demand_reports.values()} == {"farmer"}
    assert world.knowledge.workforce_offer_notices
    assert all(notice.target_occupation != "artisan"
               for notice in world.knowledge.workforce_offer_notices.values())


def test_food_pressure_expands_only_the_engine_owned_farmer_demand():
    world = create_medieval_world(73)
    produce_monthly(world)
    need = world.economy.needs["pedraclara"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 450})
    world.clock = world.clock.advance(30)
    produce_monthly(world)
    refresh_workforce_notices(world)

    facility = next(item for item in world.economy.facilities.values()
                    if item.stock_id == need.stock_id and world.economy.recipes[item.recipe_id].occupation == "farmer")
    report = next(item for item in world.knowledge.workforce_demand_reports.values()
                  if item.work_id == facility.id)
    assert report.count >= 50, "450 missing food at 100 per batch requires five authored batches"
    assert all(notice.count <= world.society.population[notice.source_group_id].count // 2
               for notice in world.knowledge.workforce_offer_notices.values()
               if notice.demand_id == report.id)


def test_relief_does_not_make_same_day_labor_receipt_stale():
    world = create_medieval_world(73)
    produce_monthly(world)
    need = world.economy.needs["pedraclara"]
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 450})
    refresh_workforce_notices(world)
    report = next(item for item in world.knowledge.workforce_demand_reports.values()
                  if item.work_id == "works:campos-de-pedra-clara")
    offer = next(item for item in world.knowledge.workforce_offer_notices.values()
                 if item.demand_id == report.id)

    # A separate owner may cover the observed food shortfall before the group
    # answers. The production event and its typed labour signal are unchanged.
    world.economy.needs[need.id] = need.model_copy(update={"missing_food": 0})

    options = workforce_transition_options(world, offer.source_group_id)
    assert any(option.notice_id == offer.id for option in options)


def test_offline_workforce_fallback_prioritizes_farming_when_food_is_missing(monkeypatch):
    """A hungry group chooses the enumerated food-production offer first."""
    import src.sim.medieval.workforce as workforce

    world = create_medieval_world(73)
    refresh_reports(world)
    group = next(iter(sorted(world.society.population.values(), key=lambda item: item.id)))
    report = world.knowledge.settlement_report(
        EntityRef("population_group", group.id), group.settlement_id)
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 10})

    farmer_notice = f"notice:{group.id}:farmer"
    artisan_notice = f"notice:{group.id}:artisan"
    source_event_id = world.events[-1].id
    world.knowledge.workforce_offer_notices[farmer_notice] = SimpleNamespace(
        target_occupation="farmer", event_id=source_event_id)
    world.knowledge.workforce_offer_notices[artisan_notice] = SimpleNamespace(
        target_occupation="artisan", event_id=source_event_id)
    options = (WorkforceTransitionOption(id="option:artisan", notice_id=artisan_notice, group_id=group.id),
               WorkforceTransitionOption(id="option:farmer", notice_id=farmer_notice, group_id=group.id))
    chosen = []
    monkeypatch.setattr(workforce, "workforce_transition_options", lambda _world, _group_id: options)
    monkeypatch.setattr(workforce, "accept_workforce_transition",
                        lambda _world, option_id, *, decision_event_id: chosen.append(option_id))

    workforce.review_workforce_transition_fallback(world)

    assert chosen == ["option:farmer"]


def test_offline_workforce_fallback_prefers_local_food_production(monkeypatch):
    """Local subsistence pressure outranks a larger remote offer."""
    import src.sim.medieval.workforce as workforce

    world = create_medieval_world(73)
    refresh_reports(world)
    group = next(item for item in sorted(world.society.population.values(), key=lambda item: item.id)
                 if item.settlement_id == "pedraclara")
    report = world.knowledge.settlement_report(
        EntityRef("population_group", group.id), group.settlement_id)
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 10})
    source_event_id = world.events[-1].id
    world.knowledge.workforce_offer_notices.update({
        "notice:local": SimpleNamespace(target_occupation="farmer", demand_id="demand:local",
                                         event_id=source_event_id, count=10),
        "notice:remote": SimpleNamespace(target_occupation="farmer", demand_id="demand:remote",
                                          event_id=source_event_id, count=200),
    })
    world.knowledge.workforce_demand_reports.update({
        "demand:local": SimpleNamespace(work_kind="facility", work_id="site:local"),
        "demand:remote": SimpleNamespace(work_kind="facility", work_id="site:remote"),
    })
    options = (WorkforceTransitionOption(id="option:remote", notice_id="notice:remote", group_id=group.id),
               WorkforceTransitionOption(id="option:local", notice_id="notice:local", group_id=group.id))
    chosen = []
    monkeypatch.setattr(workforce, "workforce_transition_options", lambda _world, _group_id: options)
    monkeypatch.setattr(workforce, "_work_settlement_id",
                        lambda _world, _kind, work_id: "pedraclara" if work_id == "site:local" else "campomanso")
    monkeypatch.setattr(workforce, "accept_workforce_transition",
                        lambda _world, option_id, *, decision_event_id: chosen.append(option_id))

    workforce.review_workforce_transition_fallback(world)

    assert chosen == ["option:local"]


def test_workforce_fallback_covers_actor_skipped_by_provider_budget(monkeypatch):
    """Provider availability does not suppress an unconsulted actor's safety net."""
    import src.sim.medieval.workforce as workforce

    world = create_medieval_world(73)
    world.config = world.config.model_copy(update={"ai_enabled": True})
    refresh_reports(world)
    group = next(iter(sorted(world.society.population.values(), key=lambda item: item.id)))
    report = world.knowledge.settlement_report(
        EntityRef("population_group", group.id), group.settlement_id)
    world.knowledge.settlement_reports[report.id] = report.model_copy(update={"missing_food": 10})
    notice_id = f"notice:{group.id}:farmer"
    world.knowledge.workforce_offer_notices[notice_id] = SimpleNamespace(
        target_occupation="farmer", event_id=world.events[-1].id)
    option = WorkforceTransitionOption(id="option:farmer", notice_id=notice_id, group_id=group.id)
    chosen = []
    monkeypatch.setattr(workforce, "workforce_transition_options", lambda _world, _group_id: (option,))
    monkeypatch.setattr(workforce, "accept_workforce_transition",
                        lambda _world, option_id, *, decision_event_id: chosen.append(option_id))
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    workforce.review_workforce_transition_fallback(world)

    assert chosen == ["option:farmer"]


def test_artisan_can_accept_a_paid_return_to_farming_when_harvest_is_labor_limited():
    world = create_medieval_world(73)
    produce_monthly(world)
    refresh_workforce_notices(world)
    notice = next(item for item in world.knowledge.workforce_offer_notices.values()
                  if item.target_occupation == "farmer")
    group = world.society.population[notice.source_group_id]
    option = workforce_transition_options(world, group.id)[0]
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    assert transition.target_occupation == "farmer"
    expected = world.knowledge.workforce_demand_reports[notice.demand_id].count
    assert transition.count == expected
    world.clock = world.clock.advance(30)
    resolve_workforce_transitions(world, due_situations(world, transition))
    assert world.society.population[group.id].occupation == "artisan"
    target = next(item for item in world.society.population.values()
                  if item.settlement_id == group.settlement_id and item.people == group.people
                  and item.occupation == "farmer")
    assert target.count == expected


def test_repair_labour_limit_is_an_equivalent_material_demand_source():
    from src.sim.medieval.economy import _delta, monthly_workforce
    from src.sim.medieval.infrastructure import damage_site, progress_repairs, review_maintenance
    from src.sim.medieval.intelligence import refresh_reports

    world = create_medieval_world(73)
    site = world.map.infrastructure_sites["docas-de-portovelho"]
    # A repair retains its existing material and authority preconditions; this
    # fixture changes only the local economic classification that supplies work.
    for group in tuple(world.society.population.values()):
        if group.settlement_id != "portovelho" or group.occupation != "artisan":
            continue
        named = tuple(person.id for person in world.society.characters.values()
                      if person.population_group_id == group.id)
        world.society.transfer_people(group.id, group.settlement_id, "farmer", group.count, named)
    stock = next(item for item in world.economy.stocks.values()
                 if item.owner_ref == site.maintainer_ref and item.location_id == "portovelho")
    blueprint = next(item for item in world.economy.repair_blueprints.values() if item.site_kind == site.kind)
    world.economy.stocks[stock.id] = stock.model_copy(update={
        "goods": {**stock.goods, **{resource: stock.goods.get(resource, 0) + amount * 10
                                      for resource, amount in blueprint.inputs.items()}}})
    damaged = record_event(world, "prepared_site_damage", "Fato material de dano.",
                           fact_kind=FactKind.STATE_TRANSITION,
                           deltas=(_delta("site", site.id, "integrity", site.integrity, 0.8),))
    damage_site(world, site.id, event_id=damaged.id)
    refresh_reports(world)
    review_maintenance(world)
    world.clock = world.clock.advance(30)
    refresh_reports(world)
    progress_repairs(world, monthly_workforce(world))
    refresh_workforce_notices(world)

    report = next(item for item in world.knowledge.workforce_demand_reports.values()
                  if item.work_kind == "repair")
    offer = next(item for item in world.knowledge.workforce_offer_notices.values()
                 if item.demand_id == report.id)
    assert report.source_event_id == world.economy.repairs[report.work_id].last_event_id
    assert offer.recipient_ref.id == offer.source_group_id
    assert report.recipient_ref == report.sponsor_ref


@pytest.mark.parametrize("mode", ["invented", "stale", "funds", "authority", "busy"])
def test_invalid_acceptance_never_executes_a_transition(mode):
    world, group, facility, option = labour_limited_world()
    if mode == "invented":
        decision = record_event(world, "workforce_transition_decided", "ID inventado.", fact_kind=FactKind.DECISION,
                                decision={**option.decision(), "option_id": "workforce_transition:invented"})
        selected = "workforce_transition:invented"
    else:
        decision = decide(world, option)
        selected = option.id
    if mode == "stale":
        world.clock = world.clock.advance(1)
    elif mode == "funds":
        account = world.economy.accounts[facility.payroll_account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    elif mode == "authority":
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("taxation",)})
    elif mode == "busy":
        # The same availability boundary used by labour and migration makes the
        # offer obsolete before an owner is allowed to reserve a second use.
        transition = accept_workforce_transition(world, option.id, decision_event_id=decision.id)
        before = (copy.deepcopy(world.society.workforce_transitions), copy.deepcopy(world.economy.accounts))
        second = record_event(world, "workforce_transition_decided", "Oferta já indisponível.",
                              fact_kind=FactKind.DECISION, decision=option.decision(),
                              cause_ids=(world.knowledge.workforce_offer_notices[option.notice_id].event_id,))
        with pytest.raises(ValueError, match="stale|selected"):
            accept_workforce_transition(world, option.id, decision_event_id=second.id)
        assert world.society.workforce_transitions == before[0] and world.economy.accounts == before[1]
        assert transition.id in world.society.workforce_transitions
        return
    before = (copy.deepcopy(world.society.workforce_transitions), copy.deepcopy(world.economy.accounts))
    with pytest.raises(ValueError):
        accept_workforce_transition(world, selected, decision_event_id=decision.id)
    assert world.society.workforce_transitions == before[0]
    assert world.economy.accounts == before[1]


def test_workforce_receipts_keep_decision_and_prose_out_of_material_owners():
    world, _, _, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    events = {event.id: event for event in world.events}
    decision = events[transition.decision_event_id]
    start = events[transition.last_event_id]
    assert decision.deltas == ()
    assert start.fact_kind == FactKind.STATE_TRANSITION
    assert all(event.causal_origin.value != "llm_interpretation" for event in (decision, start))
    assert all(link.cause_event_id != decision.id or start.fact_kind == FactKind.STATE_TRANSITION
               for link in start.causal_links)
    # The only quantities are engine-derived receipts, not fields in the group decision.
    assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}


def test_save_snapshot_rejects_corrupted_transition_provenance():
    world, _, _, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    snapshot = world_snapshot(world)
    snapshot["society"]["workforce_transitions"][transition.id]["due_day"] += 1
    from src.sim.medieval.persistence import restore_snapshot
    with pytest.raises(ValueError, match="workforce transition"):
        restore_snapshot(snapshot, world.events)


def test_failed_durable_resolution_keeps_the_active_transition(tmp_path, monkeypatch):
    import asyncio
    from src.sim.medieval import engine

    world, _, _, option = labour_limited_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    simulator = MedievalSimulator(world, save_path=tmp_path / "transition.mws")
    before_snapshot = world_snapshot(world)
    before_events = list(world.events)

    def fail(*args, **kwargs):
        raise OSError("transition disk unavailable")

    monkeypatch.setattr(engine, "save_world", fail)
    with pytest.raises(OSError, match="transition disk"):
        asyncio.run(simulator.step())
    assert world_snapshot(world) == before_snapshot
    assert world.events == before_events
    assert transition.id in world.society.workforce_transitions


def customs_staff_shortfall_world():
    """Create one real, staffed post whose paid inspection capacity is exhausted.

    The fixture deliberately drives dated cargo through the post rather than
    forging a demand event.  The third evasion attempt reaches an actually
    full two-slot inspection service, which emits the typed material shortfall.
    """
    import asyncio

    from src.sim.medieval.customs import (attempt_customs_fee_evasion, customs_cargo_options,
                                          customs_open_options, open_customs_checkpoint)
    from src.sim.medieval.logistics import open_order

    world = create_medieval_world(73)
    world.economy.facilities.clear()
    world.strategy.objectives.clear()
    operator = world.map.infrastructure_sites[CUSTOMS_SITE].owner_ref
    opening = customs_open_options(world, CUSTOMS_SITE, operator)[0]
    opened = record_event(world, "customs_open_decided", "Abrir posto civil.", fact_kind=FactKind.DECISION,
                          decision=opening.decision())
    open_customs_checkpoint(world, opening.id, decision_event_id=opened.id)
    simulator = MedievalSimulator(world)
    asyncio.run(simulator.step())
    for index in range(3):
        freight = record_event(world, "freight_decided", "Remessa preparada.", fact_kind=FactKind.DECISION,
                               decision={"action": f"prepared_freight_{index}"})
        open_order(world, "stock:ferroalto", "stock:pontenegro", "food", 10, [CUSTOMS_ROUTE],
                   decision_ids=(freight.id,))
    asyncio.run(simulator.step())
    for _ in range(3):
        option = next(item for item in customs_cargo_options(world, operator)
                      if item.action == "attempt_customs_fee_evasion")
        decision = record_event(world, "customs_decided", "A carga escolheu sua via.",
                                fact_kind=FactKind.DECISION, decision=option.decision())
        attempt_customs_fee_evasion(world, option.id, decision_event_id=decision.id)
    report = next(item for item in world.knowledge.workforce_demand_reports.values()
                  if item.work_kind == "customs")
    notice = next(item for item in world.knowledge.workforce_offer_notices.values()
                  if item.demand_id == report.id)
    option = workforce_transition_options(world, notice.source_group_id)[0]
    return world, simulator, report, notice, option


def test_customs_capacity_shortfall_converts_and_then_pays_the_merchant_staff(tmp_path):
    import asyncio

    from src.sim.medieval.customs import checkpoint_active

    world, simulator, report, notice, option = customs_staff_shortfall_world()
    checkpoint = world.economy.customs_checkpoints[report.work_id]
    source = world.society.population[notice.source_group_id]
    sponsor = world.economy.accounts[report.account_id]
    household = world.economy.accounts[f"household:{source.id}"]
    before = (sponsor.balance, household.balance)

    assert report.target_occupation == notice.target_occupation == "merchant"
    assert checkpoint.inspection_slots_used == checkpoint.staff_count * 2
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    assert transition.target_occupation == "merchant"
    assert world.economy.accounts[sponsor.id].balance == before[0] - transition.stipend_per_person
    assert world.economy.accounts[household.id].balance == before[1] + transition.stipend_per_person

    path = tmp_path / "customs-workforce.mws"
    save_world(world, path)
    world = load_world(path)
    simulator = MedievalSimulator(world)
    while transition.id in world.society.workforce_transitions:
        asyncio.run(simulator.step())
    checkpoint = world.economy.customs_checkpoints[report.work_id]
    merchant = world.society.population[transition.target_group_id]
    assert merchant.occupation == "merchant" and checkpoint.staff_group_id == merchant.id
    # The transition may complete between monthly payroll boundaries.  The next
    # paid cycle is where the checkpoint actually uses its explicit new staff.
    while world.clock.absolute_day < 90:
        asyncio.run(simulator.step())
    payroll = world.economy.payrolls[checkpoint.id]
    assert payroll.workers_by_group == {merchant.id: checkpoint.staff_count}
    assert checkpoint_active(world, world.economy.customs_checkpoints[checkpoint.id])
    world.society.validate(set(world.map.regions), world)
    world.economy.validate(world)
    world.knowledge.validate(world)


@pytest.mark.parametrize("failure", ["stale", "funds", "authority", "unavailable"])
def test_customs_workforce_acceptance_revalidates_current_material_boundary(failure):
    world, _, report, notice, option = customs_staff_shortfall_world()
    decision = decide(world, option)
    if failure == "stale":
        world.clock = world.clock.advance(1)
    elif failure == "funds":
        account = world.economy.accounts[report.account_id]
        world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    elif failure == "authority":
        office = world.authority.offices["office:polity:auren"]
        world.authority.offices[office.id] = office.model_copy(update={"scopes": ("taxation",)})
    else:
        # A first accepted offer reserves the cohort.  A second group decision
        # cannot turn the same unavailable people into a second merchant staff.
        accepted = accept_workforce_transition(world, option.id, decision_event_id=decision.id)
        again = record_event(world, "workforce_transition_decided", "Grupo já reservado.",
                             fact_kind=FactKind.DECISION, decision=option.decision(),
                             cause_ids=(notice.event_id,))
        before = (copy.deepcopy(world.society.workforce_transitions), copy.deepcopy(world.economy.accounts))
        with pytest.raises(ValueError, match="stale|selected"):
            accept_workforce_transition(world, option.id, decision_event_id=again.id)
        assert world.society.workforce_transitions == before[0]
        assert world.economy.accounts == before[1]
        assert accepted.id in world.society.workforce_transitions
        return
    before = (copy.deepcopy(world.society.workforce_transitions), copy.deepcopy(world.economy.accounts))
    with pytest.raises(ValueError):
        accept_workforce_transition(world, option.id, decision_event_id=decision.id)
    assert world.society.workforce_transitions == before[0]
    assert world.economy.accounts == before[1]


def cross_settlement_world():
    """No local farmer stock at the facility's own settlement, but a reachable
    sponsor settlement elsewhere still has one -- exactly the documented gap
    (villages stay farmer, so nearby artisan work could never be filled)."""
    world = create_medieval_world(73)
    facility = world.economy.facilities["works:campos-do-lume"]
    recipe = world.economy.recipes[facility.recipe_id]
    world.economy.recipes[recipe.id] = recipe.model_copy(update={"occupation": "artisan"})
    stock = world.economy.stocks[facility.stock_id]
    refresh_route_reports(world)
    for candidate in list(world.society.population.values()):
        if candidate.settlement_id == stock.location_id and candidate.occupation != "artisan":
            # Shrink to just its named residents (never below), small enough
            # that MAX_GROUP_FRACTION_DENOMINATOR floors any offer to zero --
            # including the new opening soldier cohorts. A real, if tiny,
            # local cohort still cannot fill the demand.
            named = sum(1 for c in world.society.characters.values()
                       if c.population_group_id == candidate.id and c.death_day is None)
            world.society.population[candidate.id] = candidate.model_copy(update={"count": named})
    produce_monthly(world)
    refresh_workforce_notices(world)
    notice = next(item for item in world.knowledge.workforce_offer_notices.values()
                  if item.demand_id.endswith(facility.id))
    group = world.society.population[notice.source_group_id]
    options = tuple(item for item in workforce_transition_options(world, group.id)
                    if item.notice_id == notice.id)
    assert len(options) == 1
    return world, group, facility, options[0], stock.location_id


def test_no_local_farmers_widens_eligibility_to_a_reachable_sponsor_settlement():
    world, group, facility, option, destination_id = cross_settlement_world()
    assert group.settlement_id != destination_id
    assert (world.society.settlements[group.settlement_id].administrator_id
            == world.society.settlements[destination_id].administrator_id)

    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)

    assert transition.destination_settlement_id == destination_id
    # Real travel time was used, not the local-transition constant.
    assert transition.due_day > transition.started_day
    assert transition.due_day != transition.started_day + 30
    assert world.society.available_count(group.id) == group.count - transition.count


def test_cross_settlement_completion_both_relocates_and_reclassifies():
    world, group, facility, option, destination_id = cross_settlement_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    origin_before = world.society.population[group.id].count

    resolve_workforce_transitions(world, due_situations(world, transition))

    assert transition.id not in world.society.workforce_transitions
    assert world.society.population[group.id].count == origin_before - transition.count
    artisans = world.society.population[transition.target_group_id]
    assert artisans.settlement_id == destination_id
    assert artisans.occupation == "artisan" and artisans.count == transition.count
    world.society.validate(set(world.map.regions), world)


def test_cross_settlement_transition_survives_save_load_and_resolves(tmp_path):
    world, group, facility, option, destination_id = cross_settlement_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    path = tmp_path / "cross-settlement.mws"
    save_world(world, path)
    resumed = load_world(path)
    assert resumed.society.workforce_transitions[transition.id] == transition

    resolve_workforce_transitions(resumed, due_situations(resumed, transition))

    artisans = resumed.society.population[transition.target_group_id]
    assert artisans.settlement_id == destination_id and artisans.occupation == "artisan"


def test_customs_demand_never_recruits_beyond_its_own_settlement():
    """The documented narrowing: customs merchant demand stays local-only."""
    world, _, report, notice, option = customs_staff_shortfall_world()
    transition = accept_workforce_transition(world, option.id, decision_event_id=decide(world, option).id)
    assert transition.destination_settlement_id == world.society.population[transition.source_group_id].settlement_id
    assert transition.due_day == transition.started_day + 30
