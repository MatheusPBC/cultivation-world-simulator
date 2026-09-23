"""Founding a site's first line: new employment from authored capability only.

An expansion always had to modify a facility that already existed, so a site
whose authored capability had no line could never gain one and its matching
cohort could never be employed. A foundation opens that first line. It creates
no capability, no money and no goods: the Map already declares what the place
can do, and the works are paid labour on the owner's own stock and account.
"""

import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval import ai_decider
from src.sim.medieval.ai_decider import ProviderDecisionRequired
from src.sim.medieval.economy import produce_monthly
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import (foundation_blocker, foundation_options,
                                        progress_expansions, start_foundation)
from src.sim.medieval.concurrent_civil_decision import concurrent_civil_options
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.systems.time import WorldClock


SITE = "oficinas-da-serra"
LINE = "works:oficinas-da-serra"
BLUEPRINT = "craft-workshop-foundation"
FOUNDED = "line:oficinas-da-serra:toolmaking"
SETTLEMENT = "ferroalto"


def unbuilt_world():
    """The authored craftsmanship site exists; its workshop was never built.

    Removing the line is the premise, not the mechanism: the site keeps its
    authored capability and the owner keeps its own stock and treasury.
    """
    world = create_medieval_world(73)
    world.economy.facilities.pop(LINE)
    owner = world.map.infrastructure_sites[SITE].owner_ref
    stock, account = holdings(world, owner)
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "wood": 200, "iron": 200, "stone": 200}})
    world.economy.accounts[account.id] = account.model_copy(
        update={"balance": max(account.balance, 5000)})
    return world, owner


def holdings(world, owner):
    from src.sim.medieval.expansion import _local_holdings

    stock, account = _local_holdings(world, owner, SETTLEMENT)
    assert stock is not None and account is not None
    return stock, account


def only_option(world, owner):
    options = [item for item in foundation_options(world, owner) if item.blueprint_id == BLUEPRINT]
    assert len(options) == 1, [item.id for item in options]
    return options[0]


def authorize(world, option):
    from src.sim.medieval.expansion import _foundation_terms
    return record_event(world, "line_foundation_authorized", "Fundar a linha.",
                        fact_kind=FactKind.DECISION, decision=_foundation_terms(option))


def build(world, option, day_limit=400):
    """Run the shared expansion progress until the project finishes."""
    project = start_foundation(world, option, decision_event_id=authorize(world, option).id)
    day = world.clock.absolute_day
    while world.economy.expansions[project.id].stage != "completed" and day < day_limit:
        day += 30
        world.clock = WorldClock(day)
        progress_expansions(world, {g.id: g.count for g in world.society.population.values()})
    return world.economy.expansions[project.id]


def total(world, resource):
    return sum(stock.goods.get(resource, 0) for stock in world.economy.stocks.values())


def test_a_capable_site_without_its_line_can_be_founded():
    world, owner = unbuilt_world()
    option = only_option(world, owner)
    assert option.site_id == SITE
    # Nothing is founded where the line already exists.
    world_with_line, owner_with_line = create_medieval_world(73), world.map.infrastructure_sites[SITE].owner_ref
    assert not [item for item in foundation_options(world_with_line, owner_with_line)
                if item.blueprint_id == BLUEPRINT]


@pytest.mark.parametrize("missing", ["site_capability", "authority", "funds", "labor", "site", "line_exists"])
def test_every_authored_and_material_gate_is_required(missing):
    from dataclasses import replace

    world, owner = unbuilt_world()
    site = world.map.infrastructure_sites[SITE]
    blueprint = world.economy.expansion_blueprints[BLUEPRINT]
    if missing == "site_capability":
        world.map.infrastructure_sites[SITE] = replace(site, capability_ids=("transport",))
    elif missing == "authority":
        world.authority.offices = {key: office for key, office in world.authority.offices.items()
                                   if office.institution_ref != owner}
    elif missing == "funds":
        for item in tuple(world.economy.accounts.values()):
            if item.owner_ref == owner:
                world.economy.accounts[item.id] = item.model_copy(update={"balance": 0})
    elif missing == "labor":
        for group_id, group in tuple(world.society.population.items()):
            if group.settlement_id == SETTLEMENT:
                world.society.population[group_id] = group.model_copy(update={"count": 0})
    elif missing == "site":
        world.map.infrastructure_sites[SITE] = replace(site, enabled=False)
    else:
        world.economy.facilities[FOUNDED] = create_medieval_world(73).economy.facilities[LINE].model_copy(
            update={"id": FOUNDED, "recipe_id": "toolmaking"})

    site = world.map.infrastructure_sites[SITE]
    owner_stock, owner_account = holdings(world, owner)
    assert foundation_blocker(world, owner, site, blueprint, owner_stock, owner_account) is not None
    assert not [item for item in foundation_options(world, owner) if item.blueprint_id == BLUEPRINT]


def test_completion_creates_a_producing_line_paying_real_wages(tmp_path):
    world, owner = unbuilt_world()
    option = only_option(world, owner)
    wood_before, iron_before = total(world, "wood"), total(world, "iron")
    money_before = sum(item.balance for item in world.economy.accounts.values())

    project = build(world, option)

    stock, account = holdings(world, owner)
    assert project.stage == "completed" and project.facility_id is None
    assert project.site_id == SITE and project.stock_id == stock.id and project.account_id == account.id
    created = world.economy.facilities[FOUNDED]
    assert created.recipe_id == "toolmaking" and created.max_batches == 10
    assert created.site_id == SITE and created.stock_id == project.stock_id
    assert created.payroll_account_id == project.account_id

    # Wages moved treasury money to the households that actually built it; no
    # coin and no material was created anywhere.
    assert sum(item.balance for item in world.economy.accounts.values()) == money_before
    assert total(world, "wood") < wood_before and total(world, "iron") < iron_before
    payroll = world.economy.payrolls[project.id]
    assert payroll.gross > 0 and payroll.workers_by_group

    # The new line is a real employer on the next production cycle.
    tools_before = world.economy.stocks[stock.id].goods.get("tools", 0)
    produce_monthly(world, {g.id: g.count for g in world.society.population.values()})
    assert world.economy.stocks[stock.id].goods.get("tools", 0) > tools_before
    assert world.economy.facilities[FOUNDED].last_batches > 0

    world.economy.validate(world)
    path = tmp_path / "foundation.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


def test_material_objectives_read_a_foundation_own_feeding_stock():
    """The investment review walks every open project, anchored or not."""
    from src.sim.medieval.investment import review_investment

    world, owner = unbuilt_world()
    option = only_option(world, owner)
    project = start_foundation(world, option, decision_event_id=authorize(world, option).id)
    stock, _account = holdings(world, owner)
    assert project.facility_id is None and project.stock_id == stock.id

    review_investment(world)

    inputs = world.economy.expansion_blueprints[BLUEPRINT].inputs
    for resource_id in inputs:
        goal = world.strategy.objectives.get(f"inputs:{stock.id}:{resource_id}")
        assert goal is not None and goal.stock_id == stock.id
    world.strategy.validate(world)


def test_ordinary_expansion_still_requires_a_parent_facility():
    """Negative regression for the optional ``facility_id``."""
    from src.classes.economy.expansion import ExpansionProject, validate_expansions

    world, owner = unbuilt_world()
    world.economy.expansions["expansion:forged"] = ExpansionProject(
        id="expansion:forged", facility_id=None, blueprint_id="workshop-extension",
        owner_ref=owner, decision_event_id="event:1", started_day=0, last_event_id="event:1")
    with pytest.raises(ValueError, match="unknown expansion target or blueprint"):
        validate_expansions(world.economy, world)

    # A foundation project is equally refused when it omits its own terms.
    world.economy.expansions = {"expansion:forged": ExpansionProject(
        id="expansion:forged", facility_id=None, blueprint_id=BLUEPRINT, site_id=SITE,
        stock_id=None, account_id=None, owner_ref=owner,
        decision_event_id="event:1", started_day=0, last_event_id="event:1")}
    with pytest.raises(ValueError, match="foundation requires its own site, stock and account"):
        validate_expansions(world.economy, world)


async def test_the_menu_offers_the_foundation_and_a_stale_choice_fails_closed(monkeypatch):
    world, owner = unbuilt_world()
    world.config = world.config.model_copy(
        update={"ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 1000})
    assert any(getattr(item, "blueprint_id", None) == BLUEPRINT
               for item in concurrent_civil_options(world, owner)) or owner.kind != "polity"

    from src.sim.medieval.expansion import foundation_adapters
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    chosen = []

    async def answer(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        picked = next((item for item in payload["choices"]
                       if item["label"].startswith("Fundar a linha")), None)
        if picked is None:
            return {"selected_id": ai_decider.NO_ACTION}
        chosen.append(picked["id"])
        # The site loses its authored capability while the actor answers.
        from dataclasses import replace
        site = world.map.infrastructure_sites[SITE]
        world.map.infrastructure_sites[SITE] = replace(site, capability_ids=("transport",))
        return {"selected_id": picked["id"]}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", answer)
    with pytest.raises(ProviderDecisionRequired, match="stale affordance"):
        await review_institutional_decision_turn(world, owner, foundation_adapters())
    assert len(chosen) == 1
    assert not world.economy.expansions
    assert FOUNDED not in world.economy.facilities

    # The actor's persisted decision never carries private material terms.
    decision = next((item for item in world.events
                     if item.event_type == "institutional_decision_turn_decided"), None)
    if decision is not None:
        assert set(decision.decision) == {"action", "actor_ref", "selected_affordance_id"}
