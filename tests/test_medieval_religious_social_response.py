"""Material religious interference permits, but never mandates, a civic response."""

import json
import pytest

from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.sim.medieval import ai_decider
from src.sim.medieval.actor_dossier import observed_assembly_interference
from src.sim.medieval.assembly_denial import assembly_denial_options, execute_assembly_denial_option
from src.sim.medieval.civic_protest import civic_protest_options
from src.sim.medieval.events import validate_history
from src.sim.medieval.force import force_position_options, prepare_force_position
from src.sim.medieval.institutional_agenda import monthly_adapters
from src.sim.medieval.institutional_decision_turn import review_institutional_decision_turn_with_provider
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from tests.test_medieval_rites import ailing_world, started, decide, tick_to, PLACE, totals


def observed_denial():
    world, healer = ailing_world()
    need = world.economy.needs[PLACE]
    world.economy.needs[need.id] = need.model_copy(update={"unrest": 620})
    _, rite = started(world, healer)
    government = EntityRef("polity", "auren")
    # A pre-existing local supplied military column is a controlled premise,
    # backed by the world's existing soldiers, not created by the denial.
    group = next(g for g in world.society.population.values()
                 if g.settlement_id == PLACE and g.count > 20 and g.occupation != "soldier")
    soldier_id = f"pop:{PLACE}:{group.people}:soldier"
    assert world.society.available_count(soldier_id) >= 5
    force = Detachment(id="detachment:religious-social-premise", owner_ref=government,
                       source_group_id=soldier_id, count=5, location_id=PLACE, destination_id=PLACE,
                       route_ids=(), route_index=0, provisions=25, stage="present",
                       started_day=world.clock.absolute_day, due_day=world.clock.absolute_day + 1,
                       decision_event_id=rite.sponsor_decision_id, last_event_id=rite.last_event_id)
    world.society.detachments[force.id] = force
    refresh_settlement_reports(world)
    position = next(o for o in force_position_options(world, government) if o.detachment_id == force.id)
    prepared = prepare_force_position(world, government, position.id, decide(world, position).id)
    tick_to(world, prepared.ready_day)
    refresh_settlement_reports(world)
    assert not civic_protest_options(world, group.id)
    option = next(o for o in assembly_denial_options(world, government)
                  if o.detachment_id == force.id and o.kind == "deny")
    execute_assembly_denial_option(world, government, option.id, decide(world, option).id)
    return world, rite, group.id


@pytest.mark.parametrize("protest", [True, False])
async def test_interrupted_assembly_is_observed_then_group_and_government_choose(monkeypatch, tmp_path, protest):
    world, rite, group_id = observed_denial()
    before_goods, before_money, before_people = totals(world)
    tick_to(world, world.clock.absolute_day + 1)
    assert world.research.rites[rite.id].stage == "interrupted"
    assert world.economy.needs[PLACE].unrest == 680
    assert not world.society.civic_protests
    group_actor = EntityRef("population_group", group_id)
    report = world.knowledge.settlement_report(group_actor, PLACE)
    assert report.observed_day == world.clock.absolute_day and report.unrest == 680
    options = civic_protest_options(world, group_id)
    target = next(o.id for o in options if o.demand_kind == "organized_strike")
    pressure = next(e for e in world.events if e.event_type == "rite_interruption_pressure")
    assert pressure.id in {link.cause_event_id for link in world.event_index()[report.event_id].causal_links}
    incident = observed_assembly_interference(world, report)[0]
    assert incident["event_id"] == pressure.id and incident["site_id"] == rite.site_id
    assert rite.blueprint_id not in str(incident) and rite.officiant_id not in str(incident)
    assert observed_assembly_interference(world, report.model_copy(update={
        "recipient_ref": EntityRef("polity", "escarlia"), "channel": "settlement_bulletin"})) == []
    prompts = []
    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        prompts.append(payload)
        ids = [o["id"] for o in payload["choices"]]
        if payload["you_are"] == group_actor.to_dict():
            observed = next(r for r in payload["situation"]["known_settlement_reports"] if r["settlement_id"] == PLACE)
            assert observed["observed_assembly_interference"] == [incident]
            return {"selected_id": target if protest else ai_decider.NO_ACTION}
        return {"selected_id": next(identity for identity in ids if identity.startswith("rite-assembly-lift:"))}
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 10, "ai_max_calls": 10})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    await review_institutional_decision_turn_with_provider(world, monthly_adapters(), actors=(group_actor,))
    assert bool(world.society.civic_protests) is protest
    if protest:
        demand = next(iter(world.society.civic_protests.values()))
        assert demand.report_event_id == report.event_id
        assert world.society.available_count(group_id) == world.society.population[group_id].count - demand.participants
    else:
        assert world.society.available_count(group_id) == world.society.population[group_id].count
    await review_institutional_decision_turn_with_provider(
        world, monthly_adapters(), actors=(EntityRef("polity", "auren"),))
    assert len(prompts) == 2
    assert rite.site_id not in world.society.assembly_denials
    assert world.research.rites[rite.id].stage == "interrupted", "permission does not resurrect a spent rite"
    assert totals(world)[1:] == (before_money, before_people)
    blueprint = world.research.rite_blueprints[rite.blueprint_id]
    assert totals(world)[0] == {key: value - blueprint.inputs.get(key, 0) for key, value in before_goods.items()}
    validate_history(world.events, world.clock.absolute_day)
    path = tmp_path / "religious-social-response.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
