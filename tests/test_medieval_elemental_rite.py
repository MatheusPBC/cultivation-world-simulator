"""Elemental work restores an observed pass through independent, paid decisions."""

from copy import deepcopy
import json

import pytest

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.economy import _delta
from src.sim.medieval.events import record_event, validate_history
from src.sim.medieval.infrastructure import damage_site, repair_authorization_options
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.rites import (record_rite_offer, rite_offer_options, rite_sponsor_options,
                                    sponsor_rite)
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_rites import decide, tick_to, totals

ACTOR = EntityRef("polity", "auren")
SITE = "passagem-negra"
BLUEPRINT = "rite-of-earth-shaping"


def damage(world, *, integrity=None, enabled=None):
    site = world.map.infrastructure_sites[SITE]
    deltas = []
    if integrity is not None:
        deltas.append(_delta("site", SITE, "integrity", site.integrity, integrity))
    if enabled is not None:
        deltas.append(_delta("site", SITE, "enabled", site.enabled, enabled))
    event = record_event(world, "prepared_pass_damage", "Dano físico preparado na passagem.",
                         fact_kind=FactKind.STATE_TRANSITION, deltas=tuple(deltas),
                         cause_ids=(site.last_event_id,) if site.last_event_id else (),
                         causal_payload=None if site.last_event_id else {
                             "root_premise": {"kind": "world_generation", "domain": "infrastructure_site",
                                              "source_refs": [{"kind": "site", "id": SITE}]}})
    damage_site(world, SITE, event_id=event.id)
    return event


def prepared_world():
    world = create_medieval_world(73)
    # Prepared qualification and existing materials, never runtime grants.
    caster = next(c for c in world.society.characters.values() if c.location_id == "pontenegro")
    world.society.characters[caster.id] = caster.model_copy(
        update={"skills": caster.skills.model_copy(update={"elemental_magic": 40})})
    world.society.transfer_people(caster.population_group_id, "pontenegro", "artisan", 2)
    stock = world.economy.stocks["stock:pontenegro"]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "reagents": 8, "crystals": 2}})
    damage(world, integrity=0.6)
    refresh_settlement_reports(world)
    refresh_site_reports(world)
    return world, caster.id


def offer_and_option(world, caster_id):
    option = next(o for o in rite_offer_options(world, caster_id) if o.blueprint_id == BLUEPRINT)
    offer = record_rite_offer(world, caster_id, option.id, decision_source={"kind": "api"})
    return next(o for o in rite_sponsor_options(world, ACTOR) if o.offer_event_id == offer.id)


def start(world, caster_id):
    option = offer_and_option(world, caster_id)
    return sponsor_rite(world, ACTOR, option.id, decide(world, option).id)


def test_elemental_work_pays_consumes_and_recovers_real_route_capacity(tmp_path):
    world, caster = prepared_world()
    before = totals(world)
    capacities = {key: world.map.get_route_operational_capacity(key) for key in world.map.routes}
    sponsor_report = world.knowledge.site_report(ACTOR, SITE)
    personal_report = world.knowledge.site_report(EntityRef("character", caster), SITE)
    rite = start(world, caster)
    assert rite.due_day - rite.started_day == 6
    assert totals(world) == before and world.map.infrastructure_sites[SITE].integrity == 0.6
    assert not any(o.site_id == SITE for o in repair_authorization_options(world, ACTOR))
    start_event = world.event_index()[rite.last_event_id]
    assert sponsor_report.event_id in {link.cause_event_id for link in start_event.causal_links}
    offer = world.event_index()[rite.officiant_decision_id]
    assert personal_report.event_id in {link.cause_event_id for link in offer.causal_links}

    tick_to(world, rite.due_day)
    done = world.research.rites[rite.id]
    assert done.stage == "completed"
    assert world.map.infrastructure_sites[SITE].integrity == 0.7
    assert world.research.rite_recoveries[caster].until_day == rite.due_day + 3
    assert not rite_offer_options(world, caster), "recovery prevents immediate repeated work"
    after = totals(world)
    assert after[0]["reagents"] == before[0]["reagents"] - 4
    assert after[0]["crystals"] == before[0]["crystals"] - 1
    assert after[1:] == before[1:]
    assert world.economy.payrolls[rite.id].gross == 4
    assert any(world.map.get_route_operational_capacity(key) > capacity for key, capacity in capacities.items())
    receipt = world.event_index()[done.last_event_id]
    assert any(d.owner_kind == "site" and d.owner_id == SITE and d.aspect == "integrity"
               for d in receipt.deltas)
    assert not any(d.owner_kind == "subsistence" for d in receipt.deltas)
    validate_history(world.events, world.clock.absolute_day)
    path = tmp_path / "elemental.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


@pytest.mark.parametrize("blocker", ["means", "sponsor_observation", "personal_observation",
                                      "standard_repair", "invented_id"])
def test_elemental_sponsorship_rejects_invalid_choice_without_partial_mutation(blocker):
    world, caster = prepared_world()
    option = offer_and_option(world, caster)
    decision = decide(world, option)
    option_id = option.id
    if blocker == "means":
        stock = world.economy.stocks[option.stock_id]
        world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "crystals": 0}})
    elif blocker.endswith("observation"):
        actor = ACTOR if blocker == "sponsor_observation" else EntityRef("character", caster)
        report = world.knowledge.site_report(actor, SITE)
        del world.knowledge.site_reports[report.id]
    elif blocker == "standard_repair":
        from src.sim.medieval.infrastructure import execute_repair_authorization_option
        repair = next(o for o in repair_authorization_options(world, ACTOR) if o.site_id == SITE)
        execute_repair_authorization_option(world, ACTOR, repair.id, decide(world, repair).id)
    else:
        option_id += ":invented"
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown"):
        sponsor_rite(world, ACTOR, option_id, decision.id)
    assert world_snapshot(world) == before


def test_changed_pass_interrupts_elemental_result_without_enabling_or_free_work():
    world, caster = prepared_world()
    rite = start(world, caster)
    control = deepcopy(world)
    damage(world, enabled=False)
    before = totals(world)
    tick_to(world, rite.due_day)
    tick_to(control, rite.due_day)
    assert world.research.rites[rite.id].stage == "failed"
    assert world.map.infrastructure_sites[SITE].integrity == 0.6
    assert world.map.infrastructure_sites[SITE].enabled is False
    assert totals(world) == before and rite.id not in world.economy.payrolls
    assert control.research.rites[rite.id].stage == "completed"
    assert control.map.infrastructure_sites[SITE].integrity == 0.7


def test_old_or_absent_personal_report_cannot_offer_elemental_work():
    world, caster = prepared_world()
    actor = EntityRef("character", caster)
    report = world.knowledge.site_report(actor, SITE)
    world.clock = world.clock.advance(30)
    refresh_settlement_reports(world)
    assert not any(o.blueprint_id == BLUEPRINT for o in rite_offer_options(world, caster))
    assert world.knowledge.site_report(actor, SITE) == report


def test_late_validation_failure_rolls_back_the_elemental_contract(monkeypatch):
    from src.classes.research.state import ResearchState
    world, caster = prepared_world()
    option = offer_and_option(world, caster)
    decision = decide(world, option)
    before = world_snapshot(world)
    def reject(self, candidate=None):
        raise ValueError("prepared late validation failure")
    with monkeypatch.context() as scoped:
        scoped.setattr(ResearchState, "validate", reject)
        with pytest.raises(ValueError, match="late validation"):
            sponsor_rite(world, ACTOR, option.id, decision.id)
    assert world_snapshot(world) == before


async def test_elemental_offer_and_sponsorship_are_independent_dated_actor_turns(monkeypatch):
    from src.sim.medieval import ai_decider
    from src.sim.medieval.character_rite_policy import schedule_character_rite_offers
    from tests.test_medieval_character_rite_policy import advance_review
    world, caster = prepared_world()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20,
                                                   "ai_max_calls": 30})
    prompts = []
    async def select(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        selected = next((choice["id"] for choice in payload["choices"]
                         if "conformação" in choice["label"]), ai_decider.NO_ACTION)
        return {"selected_id": selected}
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", select)
    assert schedule_character_rite_offers(world)
    await advance_review(world)
    assert not world.research.rites
    await advance_review(world)
    rite = next(r for r in world.research.rites.values() if r.blueprint_id == BLUEPRINT)
    assert rite.officiant_id == caster
    offer = world.event_index()[rite.officiant_decision_id]
    sponsorship = world.event_index()[rite.sponsor_decision_id]
    assert offer.decision["actor_ref"] == EntityRef("character", caster).to_dict()
    assert sponsorship.decision["actor_ref"] == ACTOR.to_dict()
    assert sponsorship.day == offer.day + 1
    tick_to(world, rite.due_day)
    assert world.research.rites[rite.id].stage == "completed"
    assert world.map.infrastructure_sites[SITE].integrity == 0.7
    assert all(not e.deltas for e in world.events if e.causal_origin.value == "llm_interpretation")


def test_prepared_local_force_can_independently_interrupt_the_elemental_work():
    from src.classes.society.force import Detachment
    from src.sim.medieval.assembly_denial import assembly_denial_options, execute_assembly_denial_option
    from src.sim.medieval.force import force_position_options, prepare_force_position
    from src.sim.medieval.rites import observe_rites
    world, caster = prepared_world()
    rite = start(world, caster)
    soldiers = next(g for g in world.society.population.values()
                    if g.settlement_id == "pontenegro" and g.occupation == "soldier")
    # This test prepares a supplied local column; it does not claim recruitment
    # or marching. People remain reserved within their real source cohort.
    stock = world.economy.stocks[rite.stock_id]
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": stock.goods["food"] - 10}})
    world.society.detachments["detachment:elemental-denial"] = Detachment(
        id="detachment:elemental-denial", owner_ref=ACTOR, source_group_id=soldiers.id,
        count=1, location_id="pontenegro", destination_id="pontenegro", route_ids=(),
        route_index=0, provisions=10, stage="present", started_day=world.clock.absolute_day,
        due_day=world.clock.absolute_day + 1, decision_event_id=rite.sponsor_decision_id,
        last_event_id=rite.last_event_id)
    position = next(o for o in force_position_options(world, ACTOR)
                    if o.detachment_id == "detachment:elemental-denial")
    prepared = prepare_force_position(world, ACTOR, position.id, decide(world, position).id)
    tick_to(world, prepared.ready_day)
    observe_rites(world)
    control = deepcopy(world)
    denial = next(o for o in assembly_denial_options(world, ACTOR) if o.site_id == SITE)
    execute_assembly_denial_option(world, ACTOR, denial.id, decide(world, denial).id)
    tick_to(world, rite.due_day)
    tick_to(control, rite.due_day)
    assert world.research.rites[rite.id].stage == "interrupted"
    assert world.map.infrastructure_sites[SITE].integrity == 0.6
    assert control.map.infrastructure_sites[SITE].integrity == 0.7
    assert rite.id not in world.economy.payrolls
    assert world.economy.stocks[rite.stock_id].goods["reagents"] == 4
    interruption = world.event_index()[world.research.rites[rite.id].last_event_id]
    assert world.society.assembly_denials[SITE].last_event_id in {
        link.cause_event_id for link in interruption.causal_links}
