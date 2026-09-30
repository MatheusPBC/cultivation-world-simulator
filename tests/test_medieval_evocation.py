"""A paid evocation manifests one temporary construct, not a second population."""

from copy import deepcopy
import json

import pytest

from src.classes.mechanical_language import EntityRef
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.evocation import active_manifestation
from src.sim.medieval.events import validate_history
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.rites import record_rite_offer, rite_offer_options, rite_sponsor_options, sponsor_rite
from src.sim.medieval.route_intelligence import refresh_site_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_rites import decide, tick_to, totals

SPONSOR = EntityRef("organization", "liga-das-barcas")
SITE = "docas-de-portovelho"
BLUEPRINT = "rite-of-evoked-bulwark"
CASTER = "character:007"


def prepare(world=None):
    world = create_medieval_world(73) if world is None else world
    caster = world.society.characters[CASTER]
    world.society.characters[caster.id] = caster.model_copy(
        update={"skills": caster.skills.model_copy(update={"evocation_magic": 40})})
    stock = next(s for s in world.economy.stocks.values()
                 if s.owner_ref == SPONSOR and s.location_id == "portovelho")
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "reagents": 18, "crystals": 6}})
    refresh_settlement_reports(world)
    refresh_site_reports(world)
    return world


def current_option(world):
    offered = next(o for o in rite_offer_options(world, CASTER)
                   if o.blueprint_id == BLUEPRINT and o.site_id == SITE)
    offer = record_rite_offer(world, CASTER, offered.id, decision_source={"kind": "api"})
    return next(o for o in rite_sponsor_options(world, SPONSOR) if o.offer_event_id == offer.id)


def evoke(world):
    option = current_option(world)
    rite = sponsor_rite(world, SPONSOR, option.id, decide(world, option).id)
    tick_to(world, rite.due_day)
    return world.research.manifestations[f"manifestation:{rite.id}"]


def test_paid_evocation_has_a_visible_origin_finite_term_and_no_permanent_goods(tmp_path):
    from src.server.medieval.queries import research_view
    world = prepare()
    before = totals(world)
    integrity = world.map.infrastructure_sites[SITE].integrity
    manifestation = evoke(world)
    rite = world.research.rites[manifestation.rite_id]
    assert rite.due_day - rite.started_day == 4
    assert manifestation.until_day - manifestation.started_day == 12
    assert world.research.rite_recoveries[CASTER].until_day == rite.due_day + 2
    assert active_manifestation(world, SITE) == manifestation
    after = totals(world)
    assert after[0]["reagents"] == before[0]["reagents"] - 6
    assert after[0]["crystals"] == before[0]["crystals"] - 2
    assert before[1:] == after[1:]
    assert world.map.infrastructure_sites[SITE].integrity == integrity
    assert world.economy.payrolls[rite.id].gross == 4
    assert not any(o.blueprint_id == BLUEPRINT for o in rite_offer_options(world, CASTER))
    assert world.knowledge.site_report(SPONSOR, SITE).manifestation_id == manifestation.id
    assert world.knowledge.site_report(EntityRef("character", CASTER), SITE).manifestation_id == manifestation.id
    assert research_view(world).manifestations == [manifestation]
    receipt = world.event_index()[manifestation.last_event_id]
    assert receipt.event_type == "rite_completed"
    assert {rite.sponsor_decision_id, rite.officiant_decision_id} <= {
        link.cause_event_id for link in receipt.causal_links}
    path = tmp_path / "evocation.mws"
    save_world(world, path)
    restored = load_world(path)
    assert world_snapshot(restored) == world_snapshot(world)
    tick_to(restored, manifestation.until_day)
    assert restored.research.manifestations[manifestation.id].stage == "expired"
    assert active_manifestation(restored, SITE) is None and restored.agenda.get(manifestation.id) is None
    report = restored.knowledge.site_report(SPONSOR, SITE)
    assert report.manifestation_id is None
    expired = restored.research.manifestations[manifestation.id].last_event_id
    assert expired in {link.cause_event_id for link in restored.event_index()[report.event_id].causal_links}
    assert totals(restored) == after
    validate_history(restored.events, restored.clock.absolute_day)
    save_world(restored, tmp_path / "expired.mws")


async def test_real_drake_impact_spends_the_construct_and_changes_paired_material_damage(tmp_path):
    from tests.test_medieval_creatures import crossed_world
    from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
    from src.sim.medieval.creatures import creature_options, execute_creature_option
    from src.systems.material_hazard_impacts import creature_site_damage_magnitude
    world = prepare(await crossed_world())
    control = deepcopy(world)
    manifestation = evoke(world)
    tick_to(control, world.clock.absolute_day)
    damage_amounts = []
    for branch in (world, control):
        request = next(o for o in creature_options(branch, DRAKE_ID)
                       if o.kind == "request" and o.route_id == ROUTE_ID)
        execute_creature_option(branch, DRAKE_ID, request.id, decide(branch, request).id)
        demand = next(iter(branch.creatures.demands.values()))
        tick_to(branch, demand.due_day + 1)
        damage = next(o for o in creature_options(branch, DRAKE_ID)
                      if o.kind == "damage" and o.site_id == SITE)
        before = branch.map.infrastructure_sites[SITE].integrity
        # Enumerating options and reading magnitude does not spend the entity.
        creature_site_damage_magnitude(branch, "river_drake", SITE)
        if branch is world:
            assert active_manifestation(branch, SITE) is not None
        execute_creature_option(branch, DRAKE_ID, damage.id, decide(branch, damage).id)
        damage_amounts.append(before - branch.map.infrastructure_sites[SITE].integrity)
        validate_history(branch.events, branch.clock.absolute_day)
    assert damage_amounts == pytest.approx([0.05, 0.10])
    spent = world.research.manifestations[manifestation.id]
    assert spent.stage == "spent" and world.agenda.get(spent.id) is None
    assert creature_site_damage_magnitude(world, "river_drake", SITE) == pytest.approx(0.10)
    impact = world.event_index()[spent.last_event_id]
    assert impact.causal_payload["evoked_interception"]["manifestation_id"] == spent.id
    assert manifestation.last_event_id in {link.cause_event_id for link in impact.causal_links}
    assert world.knowledge.site_report(SPONSOR, SITE).manifestation_id is None
    path = tmp_path / "spent.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)


@pytest.mark.parametrize("blocker", ["means", "unknown_id", "local_observation"])
def test_evocation_rejects_an_invalid_selection_without_partial_state(blocker):
    world = prepare()
    option = current_option(world)
    decision = decide(world, option)
    identity = option.id
    if blocker == "means":
        stock = world.economy.stocks[option.stock_id]
        world.economy.stocks[stock.id] = stock.model_copy(update={"goods": {**stock.goods, "crystals": 0}})
    elif blocker == "unknown_id":
        identity += ":invented"
    else:
        report = world.knowledge.site_report(EntityRef("character", CASTER), SITE)
        del world.knowledge.site_reports[report.id]
    before = world_snapshot(world)
    with pytest.raises(ValueError, match="stale|unknown"):
        sponsor_rite(world, SPONSOR, identity, decision.id)
    assert world_snapshot(world) == before


async def test_evocation_is_selected_by_independent_dated_actor_turns(monkeypatch):
    from src.sim.medieval import ai_decider
    from src.sim.medieval.character_rite_policy import schedule_character_rite_offers
    from tests.test_medieval_character_rite_policy import advance_review
    world = prepare()
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 20,
                                                   "ai_max_calls": 30})
    async def select(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        selected = next((choice["id"] for choice in payload["choices"]
                         if "anteparo" in choice["label"]), ai_decider.NO_ACTION)
        return {"selected_id": selected}
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", select)
    assert schedule_character_rite_offers(world)
    await advance_review(world)
    assert not world.research.rites
    await advance_review(world)
    rite = next(r for r in world.research.rites.values() if r.blueprint_id == BLUEPRINT)
    offer = world.event_index()[rite.officiant_decision_id]
    sponsorship = world.event_index()[rite.sponsor_decision_id]
    assert offer.decision["actor_ref"] == EntityRef("character", CASTER).to_dict()
    assert sponsorship.decision["actor_ref"] == SPONSOR.to_dict()
    assert sponsorship.day == offer.day + 1
    tick_to(world, rite.due_day)
    assert active_manifestation(world, SITE) is not None
    assert all(not e.deltas for e in world.events if e.causal_origin.value == "llm_interpretation")
    validate_history(world.events, world.clock.absolute_day)


def test_local_force_denial_on_completion_day_prevents_manifestation():
    from src.classes.society.force import Detachment
    from src.sim.medieval.assembly_denial import assembly_denial_options, execute_assembly_denial_option
    from src.sim.medieval.force import force_position_options, prepare_force_position
    from src.sim.medieval.rites import observe_rites
    world = prepare()
    option = current_option(world)
    rite = sponsor_rite(world, SPONSOR, option.id, decide(world, option).id)
    actor = EntityRef("polity", "escarlia")
    soldiers = next(g for g in world.society.population.values()
                    if g.settlement_id == "portovelho" and g.occupation == "soldier")
    # The already-present supplied column is a fixture premise, not a march or
    # recruitment claim. Deduct its provisions from existing food, not an empty
    # rite stock; this test exercises denial, not supply transport.
    stock = next(s for s in world.economy.stocks.values() if s.goods.get("food", 0) >= 10)
    world.economy.stocks[stock.id] = stock.model_copy(
        update={"goods": {**stock.goods, "food": stock.goods["food"] - 10}})
    world.society.detachments["detachment:evocation-denial"] = Detachment(
        id="detachment:evocation-denial", owner_ref=actor, source_group_id=soldiers.id,
        count=1, location_id="portovelho", destination_id="portovelho", route_ids=(),
        route_index=0, provisions=10, stage="present", started_day=world.clock.absolute_day,
        due_day=world.clock.absolute_day + 1, decision_event_id=rite.sponsor_decision_id,
        last_event_id=rite.last_event_id)
    position = next(o for o in force_position_options(world, actor)
                    if o.detachment_id == "detachment:evocation-denial")
    prepared = prepare_force_position(world, actor, position.id, decide(world, position).id)
    tick_to(world, prepared.ready_day)
    observe_rites(world)
    control = deepcopy(world)
    denial = next(o for o in assembly_denial_options(world, actor) if o.site_id == SITE)
    execute_assembly_denial_option(world, actor, denial.id, decide(world, denial).id)
    assert world.agenda.get(SITE).due_day == rite.due_day
    tick_to(world, rite.due_day)
    tick_to(control, rite.due_day)
    assert world.research.rites[rite.id].stage == "interrupted"
    assert not world.research.manifestations and rite.id not in world.economy.payrolls
    assert active_manifestation(control, SITE) is not None
    validate_history(world.events, world.clock.absolute_day)
