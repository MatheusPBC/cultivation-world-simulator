"""One creature decision interrupts a real defensive plan and a food shipment."""

from copy import deepcopy
import json

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.knowledge import force_contact_notice_id
from src.classes.mechanical_language import EntityRef
from src.run.medieval_creatures import DRAKE_ID, ROUTE_ID
from src.sim.medieval import ai_decider
from src.sim.medieval.creatures import creature_options, execute_creature_option
from src.sim.medieval.economy import _delta
from src.sim.medieval.dated import resolve_dated
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval.events import record_event
from src.sim.medieval.markets import purchase
from src.sim.medieval.persistence import load_world, save_world, world_snapshot
from src.sim.medieval.route_intelligence import refresh_route_reports
from src.sim.medieval.settlement_intelligence import refresh_settlement_reports
from src.sim.medieval.strategy_response import (adopt_occupied_settlement_defense,
                                                 defense_adoption_options, defense_action_options,
                                                 review_strategy_responses_with_provider, REVIEW_KIND)
from src.sim.medieval.force import (detect_force_standoffs, detachment_reroute_options,
                                    detachment_retreat_options, retreat_detachment)
from src.sim.medieval.force_command import detachment_command_options, execute_detachment_command_option
from src.sim.medieval.force_contact_policy import review_force_contacts, review_id as contact_review_id
from src.systems.calendar_agenda import ScheduledSituation
from tests.test_medieval_creatures import crossed_world
from tests.test_medieval_markets import consent, terms
from tests.test_medieval_strategy_response import tick


VALEDOURO = EntityRef("polity", "valedouro")


def decide(world, option):
    return record_event(world, "fixture_decided", "O ator escolheu uma opção válida.",
                        fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(),
                        causal_payload={"decision_source": {"kind": "api"}})


def _provider_response(monkeypatch, choose_id):
    async def call_llm_json(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        return {"selected_id": choose_id(payload)}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", call_llm_json)


@pytest.mark.asyncio
async def test_drake_closure_holds_a_mobilized_column_and_food_against_open_route(monkeypatch, tmp_path):
    world = await crossed_world(destination_food=0)
    demand_option = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "request")
    execute_creature_option(world, DRAKE_ID, demand_option.id, decide(world, demand_option).id)
    demand = next(iter(world.creatures.demands.values()))

    while world.clock.absolute_day < demand.due_day - 2:
        tick(world)
    direct = world.map.routes["road-portovelho-salgueiro"]
    record_event(world, "fixture_road_closed", "Uma estrada existente está indisponível.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "campaign_creature_fixture",
                     "source_refs": [{"kind": "scenario", "id": "campaign_creature_fixture"},
                                     {"kind": "route", "id": direct.id}],
                     "observed_day": world.clock.absolute_day,
                 }},
                 deltas=(_delta("route", direct.id, "enabled", True, False),))
    direct.update_runtime(enabled=False)
    settlement = world.society.settlements["portovelho"]
    record_event(world, "fixture_occupation", "A cidade encontra-se ocupada.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "campaign_creature_fixture",
                     "source_refs": [{"kind": "scenario", "id": "campaign_creature_fixture"},
                                     {"kind": "settlement", "id": settlement.id}],
                     "observed_day": world.clock.absolute_day,
                 }},
                 deltas=(_delta("settlement", settlement.id, "occupier_id", None, "escarlia"),))
    world.society.set_occupation(settlement.id, "escarlia")
    refresh_route_reports(world)
    refresh_settlement_reports(world)

    adoption = next(item for item in defense_adoption_options(world, VALEDOURO)
                    if item.settlement_id == "portovelho")
    plan = adopt_occupied_settlement_defense(world, VALEDOURO, adoption.id, decide(world, adoption).id)
    values = terms(world, quantity=2000)
    order = purchase(world, *consent(world, values))
    assert ROUTE_ID in order.route_ids

    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 10, "ai_max_calls": 100,
    })
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)

    def choose(payload):
        choices = payload["choices"]
        return next((item["id"] for item in choices
                     if ROUTE_ID in item["id"] and ":160:" in item["id"]), choices[0]["id"])

    _provider_response(monkeypatch, choose)
    assert await review_strategy_responses_with_provider(world, tick(world))
    due = tick(world)
    assert world.clock.absolute_day == demand.due_day
    assert await review_strategy_responses_with_provider(world, due)
    plan = world.strategy.plans[plan.id]
    assert plan.stage == "mobilized"
    column_id = plan.detachment_id
    original_route_ids = world.society.detachments[column_id].route_ids
    assert ROUTE_ID in original_route_ids

    open_world = deepcopy(world)
    commander_world = deepcopy(world)
    column_id = plan.detachment_id
    person = commander_world.society.characters["character:002"]
    departure = commander_world.society.detachments[column_id].location_id
    if person.location_id != departure:
        record_event(commander_world, "fixture_commander_at_departure",
                     "O comandante da fixture está presente no ponto de partida.",
                     fact_kind=FactKind.STATE_TRANSITION,
                     deltas=(_delta("character", person.id, "location_id", person.location_id, departure),))
        commander_world.society.characters[person.id] = person.model_copy(update={"location_id": departure})
    command_choices = detachment_command_options(commander_world, VALEDOURO, detachment_id=column_id)
    appointment = next(item for item in command_choices
                       if item.decision()["action"] == "appoint_detachment_commander")
    execute_detachment_command_option(
        commander_world, VALEDOURO, appointment.id, decide(commander_world, appointment).id)
    restriction = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "restrict")
    execute_creature_option(world, DRAKE_ID, restriction.id, decide(world, restriction).id)
    closure = next(item for item in reversed(world.events) if item.event_type == "creature_restricted_route")
    command_restriction = next(item for item in creature_options(commander_world, DRAKE_ID)
                               if item.kind == "restrict")
    execute_creature_option(commander_world, DRAKE_ID, command_restriction.id,
                            decide(commander_world, command_restriction).id)
    assert not world.map.routes[ROUTE_ID].enabled

    for _ in range(12):
        tick(world)
        tick(open_world)
        tick(commander_world)
        if any(event.event_type == "detachment_held" for event in world.events):
            break
    else:
        pytest.fail("the column never reached the closed river")
    held = next(item for item in reversed(world.events) if item.event_type == "detachment_held")
    assert closure.id in {link.cause_event_id for link in held.causal_links}
    assert world.society.detachments[column_id].stage == "marching"
    assert world.society.detachments[column_id].route_index < len(world.society.detachments[column_id].route_ids)
    assert open_world.society.detachments[column_id].route_index > world.society.detachments[column_id].route_index
    field_actor = EntityRef("character", commander_world.society.detachment_commands[column_id].character_id)
    field_report = commander_world.knowledge.route_report(field_actor, ROUTE_ID)
    assert field_report is not None and field_report.channel == "field_route_observation"
    field_options = detachment_reroute_options(commander_world, VALEDOURO, plan.id,
                                               actor_ref=field_actor)
    field_retreats = detachment_retreat_options(commander_world, VALEDOURO, plan.id,
                                                actor_ref=field_actor)
    assert field_retreats and all(option.actor_ref == field_actor for option in field_retreats)
    assert all(option.actor_ref == field_actor for option in field_options)

    # On a separate branch, the commander can decide to return along the
    # physical prefix they personally observed while marching. This is a real
    # independent choice, not the institution's later HQ reroute.
    commander_hold_id = commander_world.society.detachments[column_id].last_event_id
    march_review_id = f"detachment-march-review:{column_id}:{commander_hold_id}"
    march_review = commander_world.agenda.get(march_review_id)
    assert march_review is not None
    assert march_review.due_day == commander_world.clock.absolute_day + 1
    current_retreats = field_retreats

    def choose_field_retreat(payload):
        actor = EntityRef(**payload["you_are"])
        choices = payload["choices"]
        assert actor == field_actor
        assert choices and current_retreats[0].id in {choice["id"] for choice in choices}
        return current_retreats[0].id

    _provider_response(monkeypatch, choose_field_retreat)
    await review_force_contacts(commander_world, (march_review,))
    assert commander_world.strategy.plans[plan.id].stage == "withdrawn"
    field_retreat_event = next(event for event in reversed(commander_world.events)
                               if event.event_type == "detachment_retreat_started")
    field_decision = next(event for event in reversed(commander_world.events)
                          if event.event_type == "detachment_commander_march_decided")
    assert field_decision.decision["actor_ref"] == field_actor.to_dict()
    assert field_retreat_event.causal_links
    assert field_retreat_event.id == commander_world.society.detachments[column_id].last_event_id
    field_save = tmp_path / "commander-march-withdrawal.mws"
    save_world(commander_world, field_save)
    assert world_snapshot(load_world(field_save)) == world_snapshot(commander_world)

    # The halt itself is not enough to make an alternate route knowable. The
    # institution first receives current route readings, then its own HQ makes
    # a separate choice on the persisted defense plan.
    refresh_route_reports(world)
    headquarters_review = world.agenda.get(f"strategy-response-review:{plan.id}")
    assert headquarters_review is not None
    assert headquarters_review.due_day == world.clock.absolute_day + 1
    reroutes = detachment_reroute_options(world, VALEDOURO, plan.id)
    assert len(reroutes) == 1 and ROUTE_ID not in reroutes[0].route_ids
    headquarters = reroutes[0].actor_ref
    assert headquarters.kind == "character"
    assert all(world.knowledge.route_report(headquarters, route_id) is not None
               for route_id in (reroutes[0].blocked_route_id, *reroutes[0].route_ids))
    retreat_world = deepcopy(world)
    retreats = detachment_retreat_options(retreat_world, VALEDOURO, plan.id)
    assert retreats, "the halted column should have a known route back to own administration"
    retreat = retreats[0]
    stale_return = deepcopy(retreat_world)
    stale_option = detachment_retreat_options(stale_return, VALEDOURO, plan.id)[0]
    stale_decision = decide(stale_return, stale_option)
    stale_route = stale_return.map.routes[stale_option.route_ids[0]]
    record_event(stale_return, "fixture_return_route_closed", "A rota de retorno foi fechada após o boletim.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 deltas=(_delta("route", stale_route.id, "enabled", stale_route.enabled, False),))
    stale_route.update_runtime(enabled=False)
    before_stale_execution = world_snapshot(stale_return)
    with pytest.raises(ValueError, match="physically possible"):
        retreat_detachment(stale_return, VALEDOURO, plan.id, stale_option.id, stale_decision.id)
    assert world_snapshot(stale_return) == before_stale_execution

    def choose_retreat(payload):
        choices = payload["choices"]
        assert any(choice["id"] == retreat.id for choice in choices)
        return retreat.id

    _provider_response(monkeypatch, choose_retreat)
    retreat_review = ScheduledSituation(f"strategy-response-review:{plan.id}", REVIEW_KIND,
                                        retreat_world.clock.absolute_day)
    assert await review_strategy_responses_with_provider(retreat_world, (retreat_review,))
    retreating_column = retreat_world.society.detachments[column_id]
    assert retreat_world.strategy.plans[plan.id].stage == "withdrawn"
    assert retreating_column.stage == "marching"
    assert retreating_column.destination_id == retreat.destination_id
    assert retreating_column.route_ids[retreating_column.route_index:] == retreat.route_ids
    retreat_event = next(item for item in reversed(retreat_world.events)
                         if item.event_type == "detachment_retreat_started")
    assert held.id in {link.cause_event_id for link in retreat_event.causal_links}
    retreat_save = tmp_path / "halted-campaign-retreat.mws"
    save_world(retreat_world, retreat_save)
    restored_retreat = load_world(retreat_save)
    assert world_snapshot(restored_retreat) == world_snapshot(retreat_world)

    _provider_response(monkeypatch, choose)
    without_headquarters_bulletins = deepcopy(world)
    for report_id, report in tuple(without_headquarters_bulletins.knowledge.route_reports.items()):
        if report.recipient_ref == headquarters:
            del without_headquarters_bulletins.knowledge.route_reports[report_id]
    assert not detachment_reroute_options(without_headquarters_bulletins, VALEDOURO, plan.id), (
        "a QG cannot choose a route using only institution-pooled reports")
    assert not detachment_retreat_options(without_headquarters_bulletins, VALEDOURO, plan.id), (
        "a QG cannot choose a retreat route without its own reports")
    world.clock = world.clock.advance(1)
    due = world.agenda.pop_due(world.clock.absolute_day)
    assert headquarters_review in due
    open_world.clock = open_world.clock.advance(1)
    resolve_dated(open_world, open_world.agenda.pop_due(open_world.clock.absolute_day))
    resolve_dated(world, due)
    review_hold = world.event_index()[world.society.detachments[column_id].last_event_id]
    assert review_hold.event_type == "detachment_held"
    assert closure.id in {link.cause_event_id for link in review_hold.causal_links}
    assert await review_strategy_responses_with_provider(world, due)
    rerouted = world.society.detachments[column_id]
    reroute_event = next(item for item in reversed(world.events)
                         if item.event_type == "detachment_rerouted")
    reroute_causes = {link.cause_event_id for link in reroute_event.causal_links}
    assert rerouted.route_ids != original_route_ids
    assert ROUTE_ID not in rerouted.route_ids[rerouted.route_index:]
    assert review_hold.id in reroute_causes
    assert all(world.knowledge.route_report(headquarters, route_id).event_id in reroute_causes
               for route_id in (reroutes[0].blocked_route_id, *reroutes[0].route_ids))

    for _ in range(12):
        tick(world)
        tick(open_world)
        if any(event.event_type == "cargo_delayed" for event in world.events):
            break
    assert any(event.event_type == "cargo_delayed" for event in world.events)
    assert any(closure.id in {link.cause_event_id for link in event.causal_links}
               for event in world.events if event.event_type == "cargo_delayed")
    assert open_world.economy.freight_orders[order.id].delivered_quantity > \
        world.economy.freight_orders[order.id].delivered_quantity
    assert open_world.society.detachments[column_id].stage == "present"

    # The same material interruption reaches civilian subsistence. Neither
    # world starts with a granary reserve in Portovelho; only the cargo's
    # ability to cross the river differs after the fork.
    next_closing = (world.clock.absolute_day // 30 + 1) * 30
    for candidate in (world, open_world):
        candidate.config = candidate.config.model_copy(update={"ai_enabled": False})
        engine = MedievalSimulator(candidate)
        while candidate.clock.absolute_day < next_closing:
            await engine.step()
    closed_need = world.economy.needs["portovelho"]
    open_need = open_world.economy.needs["portovelho"]
    assert closed_need.missing_food > open_need.missing_food
    assert closed_need.health < open_need.health
    closed_subsistence = next(event for event in reversed(world.events)
                              if event.event_type == "subsistence_resolved"
                              and event.causal_payload.get("subsistence", {}).get("settlement_id") == "portovelho")
    assert closure.id in {link.cause_event_id for link in closed_subsistence.causal_links}

    # Continue the same campaign through contact so a real named commander gets
    # an independent tactical turn after the blocked route, HQ report, and reroute.
    while world.society.detachments[column_id].stage == "marching":
        tick(world)
    column = world.society.detachments[column_id]
    assert column.stage == "present" and column.location_id == "portovelho"
    from tests.test_medieval_field_engagement import add_column

    resident = next(item for item in world.society.population.values()
                    if item.settlement_id == "ferroalto")
    rival_group_id = f"pop:ferroalto:{resident.people}:soldier"
    world.society.population[rival_group_id] = resident.model_copy(
        update={"id": rival_group_id, "occupation": "soldier", "count": 1})
    rival, _ = add_column(world, rival_group_id,
                          identity="detachment:drake-campaign-contact-rival",
                          owner=EntityRef("polity", "escarlia"), count=20,
                          location_id="portovelho")
    detect_force_standoffs(world, rival.id)
    standoff = next(item for item in world.society.force_standoffs.values()
                    if set(item.detachment_ids) == {column_id, rival.id})
    notice_id = force_contact_notice_id(standoff.id, VALEDOURO)
    notice = world.knowledge.force_contact_notices[notice_id]
    commander = world.society.characters["character:002"]
    world.society.characters[commander.id] = commander.model_copy(update={"location_id": "portovelho"})
    world.config = world.config.model_copy(update={"ai_enabled": True, "ai_calls_per_step": 32,
                                                   "ai_max_calls": 100})
    asked = []

    def choose_command(payload):
        actor = EntityRef(**payload["you_are"])
        choices = payload["choices"]
        asked.append(actor)
        if actor == VALEDOURO:
            return next(item["id"] for item in choices
                        if item["id"].startswith("detachment-command-appoint:"))
        assert actor == EntityRef("character", commander.id)
        return next(item["id"] for item in choices if ":press:" in item["id"])

    _provider_response(monkeypatch, choose_command)
    contact_due = tick(world)
    contact = next(item for item in contact_due if item.id == contact_review_id(notice_id))
    await review_force_contacts(world, (contact,))
    appointment = world.society.detachment_commands[column_id]
    assert appointment.character_id == commander.id
    command_due = tick(world)
    assert any(item.kind == "detachment_command_review" for item in command_due)
    await review_force_contacts(world, command_due)
    commander_decision = next(item for item in reversed(world.events)
                              if item.event_type == "detachment_commander_decided")
    assert commander_decision.decision["actor_ref"] == EntityRef("character", commander.id).to_dict()
    assert notice.event_id in {link.cause_event_id for link in commander_decision.causal_links}
    assert appointment.last_event_id in {link.cause_event_id for link in commander_decision.causal_links}
    assert asked == [VALEDOURO, EntityRef("character", commander.id)]
    arrived = next(item for item in world.events if item.event_type == "detachment_arrived"
                   and any(delta.owner_kind == "detachment" and delta.owner_id == column_id
                           for delta in item.deltas))
    events = world.event_index()

    def has_causal_ancestor(event_id, ancestor_id):
        pending, visited = [event_id], set()
        while pending:
            current_id = pending.pop()
            if current_id == ancestor_id:
                return True
            if current_id in visited:
                continue
            visited.add(current_id)
            current = events.get(current_id)
            if current is not None:
                pending.extend(link.cause_event_id for link in current.causal_links)
        return False

    assert has_causal_ancestor(arrived.id, reroute_event.id)
    assert has_causal_ancestor(standoff.started_event_id, arrived.id)
    assert world.event_index()[notice.event_id].event_type == "armed_standoff_observed"
    assert standoff.started_event_id in {link.cause_event_id
                                         for link in world.event_index()[notice.event_id].causal_links}
    assert has_causal_ancestor(commander_decision.id, closure.id)

    path = tmp_path / "drake-interrupted-campaign.mws"
    save_world(world, path)
    assert world_snapshot(load_world(path)) == world_snapshot(world)
    from tools.medieval_causal_audit import audit
    audit_result = audit(path)
    audit_errors = {
        key: audit_result[key] for key in (
            "story_material_events", "decision_origin_without_source", "decision_authorship_errors",
            "decision_source_errors", "root_premise_errors", "unrooted_material_events",
            "interpretation_material_events", "broken_cause_ids",
        ) if audit_result[key]
    }
    assert audit_result["ok"] is True, audit_errors


@pytest.mark.asyncio
async def test_prepared_crisis_runs_actor_choices_without_post_start_injection(monkeypatch, tmp_path):
    """After the scenario starts, only agendas, menus and owners move it."""
    world = await crossed_world(destination_food=0)
    request = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "request")
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    # The request is a prepared fact; its deadline review is scheduled before
    # the start line, just as the creature policy would schedule it on choice.
    from src.sim.medieval.creature_policy import schedule_review
    schedule_review(world, DRAKE_ID, demand.due_day + 1)
    while world.clock.absolute_day < demand.due_day - 2:
        tick(world)

    direct = world.map.routes["road-portovelho-salgueiro"]
    record_event(world, "fixture_road_closed", "Passagem inicial indisponível.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "autonomous_campaign_fixture",
                     "source_refs": [{"kind": "scenario", "id": "autonomous_campaign_fixture"},
                                     {"kind": "route", "id": direct.id}],
                     "observed_day": world.clock.absolute_day}},
                 deltas=(_delta("route", direct.id, "enabled", True, False),))
    direct.update_runtime(enabled=False)
    settlement = world.society.settlements["portovelho"]
    record_event(world, "fixture_occupation", "Ocupação inicial do cenário.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "autonomous_campaign_fixture",
                     "source_refs": [{"kind": "scenario", "id": "autonomous_campaign_fixture"},
                                     {"kind": "settlement", "id": settlement.id}],
                     "observed_day": world.clock.absolute_day}},
                 deltas=(_delta("settlement", settlement.id, "occupier_id", None, "escarlia"),))
    world.society.set_occupation(settlement.id, "escarlia")
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    adoption = next(item for item in defense_adoption_options(world, VALEDOURO)
                    if item.settlement_id == settlement.id)
    plan = adopt_occupied_settlement_defense(world, VALEDOURO, adoption.id,
                                             decide(world, adoption).id)
    order = purchase(world, *consent(world, terms(world, quantity=2000)))
    assert ROUTE_ID in order.route_ids
    expedition = next(item for item in defense_action_options(world, VALEDOURO, plan.id)
                      if ROUTE_ID in item.id and ":160:" in item.id)
    commander = world.society.characters["character:002"]
    if commander.location_id != expedition.settlement_id:
        record_event(world, "fixture_commander_available",
                     "Comandante elegível presente na origem antes do cenário começar.",
                     fact_kind=FactKind.STATE_TRANSITION,
                     causal_payload={"root_premise": {
                         "kind": "scenario_bootstrap", "domain": "autonomous_campaign_fixture",
                         "source_refs": [{"kind": "scenario", "id": "autonomous_campaign_fixture"},
                                         {"kind": "character", "id": commander.id}],
                         "observed_day": world.clock.absolute_day}},
                     deltas=(_delta("character", commander.id, "location_id",
                                    commander.location_id, expedition.settlement_id),))
        world.society.characters[commander.id] = commander.model_copy(
            update={"location_id": expedition.settlement_id})

    # This is the start line: no direct decision or material executor below.
    start_day = world.clock.absolute_day
    world.config = world.config.model_copy(update={
        "ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 2000})
    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    asked = []

    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        actor = EntityRef(**payload["you_are"])
        choices = payload["choices"]
        asked.append((world.clock.absolute_day, actor))
        if actor.kind == "creature":
            selected = next((item["id"] for item in choices if ":restrict:" in item["id"]), None)
        elif actor.kind == "character":
            selected = next((item["id"] for item in choices
                             if item["id"].startswith("strategy-defense-authorize:")), None)
            if selected is None:
                selected = next((item["id"] for item in choices
                                 if ROUTE_ID in item["id"] and ":160:" in item["id"]), None)
        else:
            selected = next((item["id"] for item in choices
                             if item["id"].startswith("detachment-command-appoint:")), None)
        return {"selected_id": selected or ai_decider.NO_ACTION}

    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    engine = MedievalSimulator(world)
    while world.clock.absolute_day < start_day + 35:
        await engine.step()
        if (any(event.event_type == "creature_restricted_route" for event in world.events)
                and any(event.event_type == "cargo_delayed" for event in world.events)):
            break

    assert any(event.event_type == "strategy_defense_political_ordered" for event in world.events)
    assert any(event.event_type == "strategy_defense_force_decided" for event in world.events)
    assert world.strategy.plans[plan.id].detachment_id is not None
    column_id = world.strategy.plans[plan.id].detachment_id
    assert world.society.detachment_commands[column_id].character_id == commander.id
    assert any(event.event_type == "strategy_defense_command_decided" for event in world.events)
    assert any(event.event_type == "creature_restricted_route" for event in world.events)
    assert any(event.event_type == "cargo_delayed" for event in world.events)
    assert any(actor.kind == "creature" for _, actor in asked)
    assert len({actor.id for _, actor in asked if actor.kind == "character"}) >= 2

    closure = next(event for event in reversed(world.events)
                   if event.event_type == "creature_restricted_route")
    delayed = next(event for event in reversed(world.events)
                   if event.event_type == "cargo_delayed")
    assert closure.id in {link.cause_event_id for link in delayed.causal_links}
    next_closing = (world.clock.absolute_day // 30 + 1) * 30
    while world.clock.absolute_day < next_closing:
        await engine.step()
    pre_review = tmp_path / "pre-route-review.mws"
    save_world(world, pre_review)
    from tools.medieval_provider_route_review_probe import probe
    bounded = await probe(pre_review)
    assert len(bounded["calls"]) == 2
    assert all(item["selected_id"] == ai_decider.NO_ACTION for item in bounded["calls"])
    assert bounded["persisted"] is False
    subsistence = next(event for event in reversed(world.events)
                       if event.event_type == "subsistence_resolved"
                       and event.causal_payload.get("subsistence", {}).get("settlement_id") == "portovelho")
    assert closure.id in {link.cause_event_id for link in subsistence.causal_links}
    assert world.economy.needs["portovelho"].missing_food > 0
    while world.clock.absolute_day < start_day + 70 and not any(
            event.event_type == "detachment_commander_declined_reroute" for event in world.events):
        await engine.step()
    commander_decision = next(event for event in reversed(world.events)
                              if event.event_type == "detachment_commander_declined_reroute")
    held_id = next(link.cause_event_id for link in commander_decision.causal_links
                   if world.event_index()[link.cause_event_id].event_type == "detachment_held")
    held = world.event_index()[held_id]
    assert closure.id in {link.cause_event_id for link in held.causal_links}
    while world.clock.absolute_day < start_day + 70 and not any(
            event.event_type == "strategy_defense_reroute_declined" for event in world.events):
        await engine.step()
    headquarters_decision = next(event for event in reversed(world.events)
                                 if event.event_type == "strategy_defense_reroute_declined")
    event_index = world.event_index()
    ancestors = set()
    pending = [link.cause_event_id for link in headquarters_decision.causal_links]
    while pending:
        cause_id = pending.pop()
        if cause_id in ancestors:
            continue
        ancestors.add(cause_id)
        pending.extend(link.cause_event_id for link in event_index[cause_id].causal_links)
    assert closure.id in ancestors
    from src.server.medieval.queries import causal_view
    assert closure.id in {cause.id for cause in causal_view(world, delayed.id).causes}
    assert closure.id in {cause.id for cause in causal_view(world, subsistence.id).causes}
    save_path = tmp_path / "autonomous-creature-interference.mws"
    save_world(world, save_path)
    resumed = load_world(save_path)
    assert world_snapshot(resumed) == world_snapshot(world)
    assert closure.id in {cause.id for cause in causal_view(resumed, subsistence.id).causes}
    from tools.medieval_causal_audit import audit
    assert audit(save_path)["ok"] is True
