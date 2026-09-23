"""A researched, built and maintained wall changes a siege through Map state."""

from copy import deepcopy

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event
from src.sim.medieval.expansion import (_construction_terms, progress_expansions,
                                        site_construction_options, start_site_construction)
from src.sim.medieval.infrastructure import (damage_site, execute_repair_authorization_option,
                                             progress_repairs, repair_authorization_options)
from src.sim.medieval.economy import monthly_workforce
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.research import learn_technology
from src.sim.medieval.route_intelligence import refresh_route_reports, refresh_site_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.settlement_investment import (execute_settlement_investment_option,
                                                    settlement_investment_options)
from src.sim.medieval.siege_campaign import (_barrier_reading, _garrison_wear, begin_siege_campaign,
                                             siege_campaign_options)
from src.systems.time import WorldClock

from tests.test_medieval_siege_campaign import (ATTACKER, DEFENDER, TARGET,
                                                _defending_garrison, _prepared_attacker,
                                                _teach_fortification, decide, tick)


def _build_barrier(world):
    _teach_fortification(world)
    assert not [item for item in site_construction_options(world, DEFENDER)
                if item.blueprint_id == "defensive-palisade-construction"]
    decision = record_event(world, "barrier_research_decided", "Pesquisar barreiras defensivas.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "research", "actor_ref": DEFENDER.to_dict(),
                                      "technology_id": "defensive_barriers"})
    learn_technology(world, DEFENDER, "defensive_barriers", "research", (decision.id,))
    option = next(item for item in site_construction_options(world, DEFENDER)
                  if item.settlement_id == TARGET
                  and item.blueprint_id == "defensive-palisade-construction")
    stock = world.economy.stocks[option.stock_id]
    account = world.economy.accounts[option.account_id]
    materials_before = {resource: stock.goods[resource] for resource in ("wood", "stone", "tools")}
    balance_before = account.balance
    authorization = record_event(world, "site_construction_authorized", "Construir paliçada.",
                                 fact_kind=FactKind.DECISION, decision=_construction_terms(option))
    project = start_site_construction(world, option, decision_event_id=authorization.id)
    learned = world.knowledge.technologies["technology:polity:escarlia:defensive_barriers"]
    start = world.event_index()[project.last_event_id]
    assert learned.event_id in {link.cause_event_id for link in start.causal_links}
    assert option.new_site_id not in world.map.infrastructure_sites
    for day in (30, 60):
        world.clock = WorldClock(day)
        progress_expansions(world, {group.id: group.count for group in world.society.population.values()})
    assert world.economy.expansions[project.id].stage == "completed"
    site = world.map.infrastructure_sites[option.new_site_id]
    assert site.owner_ref == site.maintainer_ref == DEFENDER
    assert site.kind == "palisade" and site.capability_ids == ("defensive_barrier",)
    stock = world.economy.stocks[option.stock_id]
    assert {resource: materials_before[resource] - stock.goods[resource]
            for resource in materials_before} == {"wood": 24, "stone": 12, "tools": 6}
    assert world.economy.accounts[option.account_id].balance < balance_before
    return site


def test_built_barrier_resists_siege_until_a_material_impact_disables_it(tmp_path):
    world = create_medieval_world(211)
    site = _build_barrier(world)
    refresh_settlement_reports(world)
    refresh_route_reports(world)
    attacker_id = _prepared_attacker(world, count=40)
    garrison_id = _defending_garrison(world, count=40, provisions=400)
    investment = next(item for item in settlement_investment_options(world, ATTACKER,
                                                                      detachment_id=attacker_id)
                      if item.kind == "invest")
    execute_settlement_investment_option(world, ATTACKER, investment.id, decide(world, investment).id)
    option = next(item for item in siege_campaign_options(world, ATTACKER)
                  if item.defender_garrison_id == garrison_id)
    campaign = begin_siege_campaign(world, ATTACKER, option.id, decide(world, option).id)
    attacker = world.society.detachments[attacker_id]
    defender = world.society.detachments[world.society.garrisons[garrison_id].detachment_id]
    with_barrier = _garrison_wear(world, campaign, attacker, defender)

    damaged = deepcopy(world)
    impact = record_event(damaged, "fixture_falling_tree", "Impacto físico externo sobre a paliçada.",
                          fact_kind=FactKind.OCCURRENCE, causal_origin=CausalOrigin.EXTERNAL_EVENT)
    damage = record_event(damaged, "fixture_palisade_damaged", "A paliçada perdeu integridade.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("site", site.id, "integrity", 1.0, 0.4),),
                          cause_ids=(impact.id, site.last_event_id))
    damage_site(damaged, site.id, event_id=damage.id)
    assert _garrison_wear(damaged, damaged.society.siege_campaigns[campaign.id],
                          damaged.society.detachments[attacker_id],
                          damaged.society.detachments[defender.id]) == with_barrier + 1

    tick(world)
    tick(damaged)
    intact_progress = world.event_index()[world.society.siege_campaigns[campaign.id].last_event_id]
    damaged_progress = damaged.event_index()[damaged.society.siege_campaigns[campaign.id].last_event_id]
    assert world.society.siege_campaigns[campaign.id].garrison_endurance == (
        damaged.society.siege_campaigns[campaign.id].garrison_endurance + 1)
    assert any(delta.aspect == "barrier_resistance" and delta.after == "1"
               for delta in intact_progress.deltas)
    assert any(delta.aspect == "barrier_resistance" and delta.after == "0"
               for delta in damaged_progress.deltas)
    assert site.last_event_id in {link.cause_event_id for link in intact_progress.causal_links}
    assert damage.id in {link.cause_event_id for link in damaged_progress.causal_links}

    from tools.medieval_causal_audit import audit
    for label, branch in (("intact", world), ("damaged", damaged)):
        path = tmp_path / f"palisade-{label}.mws"
        save_world(branch, path)
        assert world_snapshot(load_world(path)) == world_snapshot(branch)
        assert audit(path)["ok"] is True


def test_damaged_barrier_needs_observed_paid_repair_to_resist_again(tmp_path):
    world = create_medieval_world(211)
    site = _build_barrier(world)
    impact = record_event(world, "fixture_falling_tree", "Impacto físico externo sobre a paliçada.",
                          fact_kind=FactKind.OCCURRENCE, causal_origin=CausalOrigin.EXTERNAL_EVENT)
    damage = record_event(world, "fixture_palisade_damaged", "A paliçada perdeu integridade.",
                          fact_kind=FactKind.STATE_TRANSITION,
                          deltas=(_delta("site", site.id, "integrity", 1.0, 0.4),),
                          cause_ids=(impact.id, site.last_event_id))
    damage_site(world, site.id, event_id=damage.id)
    assert _barrier_reading(world, DEFENDER, TARGET)[1] == 0
    refresh_site_reports(world, site_ids=(site.id,))
    option = next(item for item in repair_authorization_options(world, DEFENDER)
                  if item.site_id == site.id)
    decision = record_event(world, "repair_authorization_decided", "Reparar a paliçada.",
                            fact_kind=FactKind.DECISION, decision=option.decision(),
                            cause_ids=(world.knowledge.site_report(DEFENDER, site.id).event_id,))
    project = execute_repair_authorization_option(world, DEFENDER, option.id, decision.id)
    assert project.stage == "waiting" and _barrier_reading(world, DEFENDER, TARGET)[1] == 0
    stock_before = dict(world.economy.stocks[project.stock_id].goods)
    balance_before = world.economy.accounts[project.account_id].balance
    world.clock = WorldClock(90)
    refresh_site_reports(world, site_ids=(site.id,))
    progress_repairs(world, monthly_workforce(world))
    repaired = world.map.infrastructure_sites[site.id]
    assert round(repaired.integrity, 3) == 0.5
    assert _barrier_reading(world, DEFENDER, TARGET)[1] == 1
    assert world.economy.stocks[project.stock_id].goods != stock_before
    assert world.economy.accounts[project.account_id].balance < balance_before
    repair_event = world.event_index()[world.economy.repairs[project.id].last_event_id]
    assert damage.id in {link.cause_event_id for link in world.event_index()[project.last_event_id].causal_links}
    assert any(delta.owner_kind == "site" and delta.owner_id == site.id
               and delta.aspect == "integrity" for delta in repair_event.deltas)
    path = tmp_path / "palisade-repaired.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    assert audit(path)["ok"] is True
