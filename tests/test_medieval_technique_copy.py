"""Causal checks for copying a technique from sustained, foreign work access."""

import json

import pytest

from src.classes.economy.maintenance import repair_intent
from src.classes.economy.models import Stock
from src.classes.environment.infrastructure import InfrastructureSite
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.economy import _delta, monthly_workforce
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.infrastructure import damage_site, progress_repairs, start_repair
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.technique_copy import (COPY_WAGE, open_technique_copy,
                                              resolve_technique_copies,
                                              technique_copy_options)
from src.sim.medieval.technique_copy_policy import review_technique_copies_with_provider
from src.sim.medieval.technology_sighting import disclosure_options, execute_disclosure
from src.systems.time import WorldClock


COPIER = EntityRef("polity", "auren")
HOLDER = EntityRef("polity", "escarlia")
SITE = "minas-de-ferroalto"
LOCAL_STOCK = "stock:auren-ferroalto"


def decide(world, option, event_type="technique_copy_decided"):
    return record_event(world, event_type, "Escolha de uma affordance técnica canônica.",
                        fact_kind=FactKind.DECISION, decision=option.decision())


def access_world(*, progress=True):
    """A foreign charcoal line, a real sighting, and Auren's paid repair work.

    The distinct maintainer is an authored fixture for a shared foreign site:
    Escarlia continues owning the mine and its line while Auren pays the local
    repair work.  The actual repair executor, payroll, observation, sighting
    and dated agenda are all used unchanged.
    """
    world = create_medieval_world(73)
    site = world.map.infrastructure_sites[SITE]
    world.map.infrastructure_sites[SITE] = InfrastructureSite.from_dict({
        **site.to_dict(), "maintainer_ref": COPIER.to_dict(),
    })
    world.economy.stocks[LOCAL_STOCK] = Stock(
        id=LOCAL_STOCK, owner_ref=COPIER, location_id="ferroalto", capacity=10_000,
        goods={"wood": 50, "stone": 50, "iron": 50, "tools": 100, "food": 100},
    )
    holder_line = world.economy.facilities["works:minas-de-ferroalto"]
    world.economy.facilities[holder_line.id] = holder_line.model_copy(update={"recipe_id": "charcoal"})

    # The disclosure is factual and voluntary; the recipient learns no recipe.
    learn_technology(world, HOLDER, "metallurgy", "research", ())
    disclosure = next(item for item in disclosure_options(world, HOLDER)
                      if item.recipient_ref == COPIER and item.technology_id == "metallurgy")
    sighting = execute_disclosure(world, disclosure, decide(world, disclosure, "technology_disclosed").id)

    # The repair uses a material damage receipt, Auren's own local stock and a
    # normal monthly wage settlement.  At 30 it remains active, so it is a
    # durable access relation rather than a forged payroll entry.
    site = world.map.infrastructure_sites[SITE]
    damage = record_event(world, "fixture_site_damage", "Premissa material de reparo compartilhado.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("site", SITE, "integrity", site.integrity, 0.8),))
    damage_site(world, SITE, event_id=damage.id)
    refresh_site_reports(world, site_ids=(SITE,))
    blueprint = next(item for item in world.economy.repair_blueprints.values() if item.site_kind == "mine")
    repair_decision = record_event(
        world, "repair_decided", "Autorizar reparo estrangeiro já contratado.", fact_kind=FactKind.DECISION,
        decision=repair_intent(COPIER, SITE, blueprint.id, LOCAL_STOCK, "treasury:auren"),
    )
    repair = start_repair(world, SITE, blueprint.id, decision_event_id=repair_decision.id)
    if not progress:
        return world, sighting, repair
    world.clock = WorldClock(30)
    refresh_site_reports(world, site_ids=(SITE,))
    progress_repairs(world, monthly_workforce(world))
    repair = world.economy.repairs[repair.id]
    assert repair.stage == "repairing" and world.economy.payrolls[repair.id].day == 30
    refresh_site_reports(world, site_ids=(SITE,))
    return world, sighting, repair


def open_copy(world):
    option, = technique_copy_options(world, COPIER)
    copy = open_technique_copy(world, COPIER, option.id, decide(world, option).id)
    return option, copy


@pytest.mark.asyncio
async def test_sustained_foreign_paid_access_copies_without_harming_holder_and_round_trips(tmp_path, monkeypatch):
    # This goes through the engine review: the provider sees only the current
    # sighting/report options and returns one engine-generated ID.
    world, sighting, _ = access_world(progress=False)
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 3})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def choose_first(prompt, *_args, **_kwargs):
        return {"selected_id": json.loads(prompt.rsplit("\n", 1)[1])["choices"][0]["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose_first)
    await MedievalSimulator(world).step()
    engine_copy, = world.research.technique_copies.values()
    assert engine_copy.stage == "copying"

    # Resolve a matching standalone world without skipping the engine's other
    # dated agendas; this isolates the copy executor and keeps save validation
    # meaningful after the successful conclusion.
    world, sighting, _ = access_world()
    option, copy = open_copy(world)
    holder_stock = world.economy.stocks["stock:ferroalto"].model_copy(deep=True)
    holder_site = world.map.infrastructure_sites[SITE].to_dict()
    holder_offices = {key: value.model_copy(deep=True) for key, value in world.authority.offices.items()}
    balance = world.economy.accounts[copy.account_id].balance
    world.clock = WorldClock(copy.due_day)
    resolve_technique_copies(world, world.agenda.pop_due(world.clock.absolute_day))

    result = world.research.technique_copies[copy.id]
    knowledge = next(item for item in world.knowledge.technologies.values()
                     if item.owner_ref == COPIER and item.technology_id == "metallurgy")
    receipt = next(item for item in world.events if item.id == knowledge.event_id)
    causes = {item.cause_event_id for item in receipt.causal_links}
    assert result.stage == "completed" and knowledge.channel == "copied"
    assert world.economy.payrolls[copy.id].gross == COPY_WAGE
    assert world.economy.accounts[copy.account_id].balance == balance - COPY_WAGE
    assert {sighting.event_id, copy.report_event_id, copy.access_event_id} <= causes
    assert world.knowledge.knows(HOLDER, "metallurgy")
    assert world.economy.stocks["stock:ferroalto"] == holder_stock
    assert world.map.infrastructure_sites[SITE].to_dict() == holder_site
    assert world.authority.offices == holder_offices
    assert not any(item.recipient_ref == HOLDER for item in world.knowledge.technology_sightings.values())
    assert not any(item.recipient_ref == HOLDER for item in world.knowledge.notices.values())
    path = tmp_path / "technique-copy.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)



@pytest.mark.asyncio
async def test_missing_evidence_access_prerequisite_or_authority_and_no_action_do_not_copy(monkeypatch):
    # Every condition is independently required before an option exists.
    for missing in ("sighting", "access", "prerequisite", "authority", "funds", "labor"):
        world, _, repair = access_world()
        if missing == "sighting":
            world.knowledge.technology_sightings.clear()
        elif missing == "access":
            world.economy.payrolls.pop(repair.id)
        elif missing == "prerequisite":
            tech = world.research.technologies["metallurgy"]
            world.research.technologies[tech.id] = tech.model_copy(update={"prerequisites": ("irrigation",)})
        elif missing == "funds":
            account = world.economy.accounts["treasury:auren"]
            world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
        elif missing == "labor":
            for group_id, group in tuple(world.society.population.items()):
                if group.settlement_id == "ferroalto" and group.occupation == "artisan":
                    world.society.population[group_id] = group.model_copy(update={"count": 0})
        else:
            office = world.authority.offices["office:polity:auren"]
            world.authority.offices[office.id] = office.model_copy(update={"ends_day": world.clock.absolute_day})
        before = (dict(world.research.technique_copies), dict(world.knowledge.technologies),
                  world.economy.accounts["treasury:auren"].balance)
        assert not technique_copy_options(world, COPIER)
        assert before == (dict(world.research.technique_copies), dict(world.knowledge.technologies),
                          world.economy.accounts["treasury:auren"].balance)

    # A forged ID is refused after a matching decision, leaving the executor's
    # canonical owners alone.
    world, _, _ = access_world()
    option, = technique_copy_options(world, COPIER)
    decision = decide(world, option)
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale or unknown"):
        open_technique_copy(world, COPIER, option.id + ":forged", decision.id)
    assert world_snapshot(world) == before

    # The linked provider review treats NO_ACTION as a zero-delta interpretation,
    # not as a scripted copy.
    world, _, _ = access_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 1, "ai_max_calls": 2})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    async def no_action(*_args, **_kwargs):
        return {"selected_id": ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", no_action)
    stock = world.economy.stocks[LOCAL_STOCK].model_copy(deep=True)
    balance = world.economy.accounts["treasury:auren"].balance
    assert not await review_technique_copies_with_provider(world)
    assert not world.research.technique_copies and not world.knowledge.knows(COPIER, "metallurgy")
    assert world.economy.stocks[LOCAL_STOCK] == stock
    assert world.economy.accounts["treasury:auren"].balance == balance
    assert world.events[-1].event_type == "ai_decision_interpreted" and not world.events[-1].deltas

    # Funds disappearing after opening resolve to a factual failure; they do
    # not let settle_work throw after the agenda has already been consumed.
    world, _, _ = access_world()
    _, copy = open_copy(world)
    world.clock = WorldClock(copy.due_day)
    account = world.economy.accounts[copy.account_id]
    world.economy.accounts[account.id] = account.model_copy(update={"balance": 0})
    resolve_technique_copies(world, world.agenda.pop_due(world.clock.absolute_day))
    failed = world.research.technique_copies[copy.id]
    assert failed.stage == "failed" and failed.blocker == "payroll_funds"
    assert copy.id not in world.economy.payrolls and world.agenda.get(copy.id) is None

    # A real finishing repair ends the paid access before this copy resolves.
    world, _, _ = access_world()
    _, copy = open_copy(world)
    world.clock = WorldClock(copy.due_day)
    refresh_site_reports(world, site_ids=(SITE,))
    progress_repairs(world, monthly_workforce(world))
    balance = world.economy.accounts[copy.account_id].balance
    resolve_technique_copies(world, world.agenda.pop_due(world.clock.absolute_day))
    failed = world.research.technique_copies[copy.id]
    assert failed.stage == "failed" and failed.blocker == "access_lost"
    assert not world.knowledge.knows(COPIER, "metallurgy")
    assert world.economy.payrolls[copy.id].gross == COPY_WAGE
    assert world.economy.accounts[copy.account_id].balance == balance - COPY_WAGE
