"""One creature decision interrupts a real defensive plan and a food shipment."""

from copy import deepcopy
import json

import pytest

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.knowledge import force_contact_notice_id
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import Detachment
from src.classes.economy.models import Stock
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
                                    detachment_retreat_options, retreat_detachment,
                                    establish_garrison, garrison_options)
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


def _prepare_portovelho_garrison(world):
    """A real local soldier cohort and treasury establish the scenario's defense."""
    actor = EntityRef("polity", "escarlia")
    population_before = sum(item.count for item in world.society.population.values())
    group = world.society.population["pop:portovelho:human:soldier"]
    assert group.count > 0
    detachment_id = "detachment:prepared-portovelho-garrison"
    garrison_id = f"garrison:{detachment_id}"
    account = next(item for item in world.economy.accounts.values() if item.owner_ref == actor)
    premise = record_event(
        world, "fixture_defender_detachment_arrived", "Premissa preparada: soldados locais já presentes.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_creature_garrison_fixture",
            "source_refs": [{"kind": "settlement", "id": "portovelho"},
                            {"kind": "population_group", "id": group.id},
                            {"kind": "account", "id": account.id}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("detachment", detachment_id, "stage", None, "present"),
                _delta("detachment", detachment_id, "owner_ref", None, actor.id),
                _delta("detachment", detachment_id, "source_group_id", None, group.id),
                _delta("detachment", detachment_id, "location_id", None, "portovelho"),
                _delta("detachment", detachment_id, "count", None, group.count),
                _delta("detachment", detachment_id, "provisions", None, 4000)),
        cause_ids=tuple(item for item in (group.last_event_id,) if item))
    world.society.detachments[detachment_id] = Detachment(
        id=detachment_id, owner_ref=actor, source_group_id=group.id, count=group.count,
        location_id="portovelho", destination_id="portovelho", route_ids=(), route_index=0,
        provisions=4000, stage="present", started_day=world.clock.absolute_day,
        due_day=world.clock.absolute_day + 1, decision_event_id=premise.id,
        last_event_id=premise.id)
    option = next(item for item in garrison_options(world, actor)
                  if item.detachment_id == detachment_id and item.kind == "garrison")
    decision = decide(world, option)
    establish_garrison(world, actor, option.id, decision.id)
    established = world.event_index()[world.society.garrisons[garrison_id].last_event_id]
    assert established.event_type == "garrison_established"
    assert decision.id in {link.cause_event_id for link in established.causal_links}
    assert sum(item.count for item in world.society.population.values()) == population_before
    world.agenda.schedule(ScheduledSituation(detachment_id, "force", world.clock.absolute_day + 1))
    return detachment_id, garrison_id


def _prepare_competing_rites_and_faith(world):
    """Finite initial premises; later outcomes belong to the real runtime."""
    from src.sim.medieval.rites import record_rite_offer, rite_offer_options, rite_sponsor_options, sponsor_rite
    from src.sim.medieval.religion import invitation_options, invite_religious_adherence
    from src.sim.medieval.religion_policy import schedule_invitation_response
    order = EntityRef("organization", "ordem-da-aurora")
    local = world.society.characters["character:005"]
    visiting = world.society.characters["character:011"]
    population_before = sum(g.count for g in world.society.population.values())
    group = world.society.population[visiting.population_group_id]
    destination = next(g for g in world.society.population.values()
                       if (g.settlement_id, g.people, g.occupation) == ("pedraclara", group.people, group.occupation))
    world.society.transfer_people(group.id, "pedraclara", group.occupation, 1, (visiting.id,))
    stock = world.economy.stocks["stock:ordem-da-aurora"]
    other = world.economy.stocks["stock:coro-das-cinzas"]
    assert stock.goods["reagents"] >= 6 and stock.goods["crystals"] >= 2
    moves = {"reagents": stock.goods["reagents"] - 6, "crystals": stock.goods["crystals"] - 2}
    changes = [_delta("population_group", group.id, "count", group.count, group.count - 1),
               _delta("population_group", destination.id, "count", destination.count, destination.count + 1),
               _delta("character", visiting.id, "location_id", visiting.location_id, "pedraclara"),
               _delta("character", visiting.id, "population_group_id", group.id, destination.id)]
    organization = world.society.organizations[order.id]
    members = tuple(sorted(set((*organization.member_ids, local.id))))
    changes.append(_delta("organization", order.id, "member_ids", list(organization.member_ids), list(members)))
    for resource, amount in moves.items():
        changes.extend((_delta("stock", stock.id, resource, stock.goods[resource], stock.goods[resource] - amount),
                        _delta("stock", other.id, resource, other.goods[resource], other.goods[resource] + amount)))
    for place in ("pedraclara", "campomanso"):
        need = world.economy.needs[place]
        changes.append(_delta("subsistence", place, "health", need.health, 700))
    for person in (local, visiting):
        changes.append(_delta("character", person.id, "restoration_magic", person.skills.restoration_magic, 40))
    premise = record_event(world, "fixture_civil_ritual_premise", "Premissas finitas de agentes, saúde e reservas do cenário.",
        fact_kind=FactKind.STATE_TRANSITION, deltas=tuple(changes), causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "medieval_composed_fixture",
            "source_refs": [{"kind":"scenario","id":"medieval_composed_fixture"}],
            "observed_day":world.clock.absolute_day}})
    for identity in (group.id, destination.id):
        world.society.population[identity] = world.society.population[identity].model_copy(update={"last_event_id":premise.id})
    for person in (local, visiting):
        current = world.society.characters[person.id]
        world.society.characters[person.id] = current.model_copy(update={
            "skills":current.skills.model_copy(update={"restoration_magic":40})})
    for current, sign in ((stock, -1), (other, 1)):
        world.economy.stocks[current.id] = current.model_copy(update={
            "goods": {**current.goods, **{key:current.goods[key]+sign*amount for key,amount in moves.items()}},
            "last_event_ids": {**current.last_event_ids, **{key:premise.id for key in moves}}})
    for place in ("pedraclara", "campomanso"):
        need = world.economy.needs[place]
        world.economy.needs[place] = need.model_copy(update={"health":700,"last_event_id":premise.id})
    # Membership gives the local emissary institutional presence, not faith.
    world.society.organizations[order.id] = organization.model_copy(update={
        "member_ids":members})
    refresh_settlement_reports(world)
    rites = []
    for person, blueprint, target in ((local, "rite-of-restoration", None),
                                      (visiting, "rite-of-restoration", None)):
        option = next(o for o in rite_offer_options(world, person.id)
                      if o.sponsor_ref == order and o.blueprint_id == blueprint and o.target_settlement_id == target)
        offer = record_rite_offer(world, person.id, option.id, decision_source={"kind":"api"})
        choice = next(o for o in rite_sponsor_options(world, order) if o.offer_event_id == offer.id)
        rites.append(sponsor_rite(world, order, choice.id, decide(world, choice).id))
    assert rites[0].stock_id == rites[1].stock_id and rites[0].due_day == rites[1].due_day
    recipient = EntityRef("population_group", "pop:pedraclara:orc:artisan")
    invitation = next(o for o in invitation_options(world, order) if o.recipient_ref == recipient)
    notice = invite_religious_adherence(world, order, invitation.id, decide(world, invitation).id)
    assert sum(g.count for g in world.society.population.values()) == population_before
    assert not world.society.religious_adherences
    # Wake-up is prepared, never acceptance. The recipient chooses after start.
    return tuple(r.id for r in rites), recipient, notice, schedule_invitation_response


def _prepare_defender_instruction(world, detachment_id):
    """Existing knowledge is a declared premise, never an equipment bonus."""
    from src.sim.medieval.research import learn_technology
    from src.sim.medieval.force_training import start_training, training_options
    from src.sim.medieval.field_engagement import field_strength
    actor = EntityRef("polity", "escarlia")
    column = world.society.detachments[detachment_id]
    strength_before = field_strength(world, column)[0]
    source = world.economy.stocks["stock:ferroalto"]
    stock_id = "stock:prepared-defender-instruction"
    # Prior supply at the prepared garrison is finite: one existing tool is
    # relocated, not created. This is an initial scenario fact, not dispatch.
    assert source.goods["tools"] >= 1
    premise = record_event(
        world, "fixture_defender_instruction_premise",
        "Premissa preparada: técnica prévia e uma ferramenta já posicionada na guarnição.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("stock", source.id, "tools", source.goods["tools"], source.goods["tools"] - 1),
                _delta("stock", stock_id, "tools", 0, 1)),
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "medieval_composed_instruction",
            "source_refs": [{"kind": "scenario", "id": "medieval_composed_instruction"}],
            "observed_day": world.clock.absolute_day}})
    world.economy.stocks[source.id] = source.model_copy(update={
        "goods": {**source.goods, "tools": source.goods["tools"] - 1},
        "last_event_ids": {**source.last_event_ids, "tools": premise.id}})
    world.economy.stocks[stock_id] = Stock(
        id=stock_id, owner_ref=actor, location_id=column.location_id, capacity=10,
        goods={"tools": 1}, last_event_ids={"tools": premise.id})
    # This helper does not claim to repeat paid research. That chain retains
    # its own acceptance; here we test whether prior knowledge is applied.
    learn_technology(world, actor, "field_drill", "teaching", (premise.id,))
    assert field_strength(world, column)[0] == strength_before
    option = next(item for item in training_options(world, actor, detachment_id=detachment_id)
                  if item.technology_id == "field_drill" and item.stock_id == stock_id)
    training = start_training(world, actor, option.id, decide(world, option).id)
    assert world.economy.stocks[stock_id].goods["tools"] == 0
    assert field_strength(world, world.society.detachments[detachment_id])[0] == strength_before
    return training.id


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
                      if ":160:" in item.id)
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
        # Controlled scenario policy: interpret the current actor and the
        # engine-authored option descriptions. It deliberately does not
        # inspect affordance IDs or count consultations, so the same intent
        # cannot fire a stage that the current owner did not offer.
        labels = [item["label"] for item in choices]
        if actor.kind == "creature":
            wanted = "Fechar a passagem até ser atendido."
        elif actor.kind == "character" and any(
                "Autorizar o QG" in label for label in labels):
            wanted = "Autorizar o QG a preparar uma resposta material à ocupação observada."
        elif actor.kind == "character" and any("40 dias" in label for label in labels):
            wanted = next(label for label in labels if "40 dias" in label)
        elif actor.kind in {"polity", "organization"} and any(
                label.startswith("Nomear ") for label in labels):
            wanted = next(label for label in labels if label.startswith("Nomear "))
        else:
            return {"selected_id": ai_decider.NO_ACTION}
        selected = next((item["id"] for item in choices if item["label"] == wanted), None)
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


@pytest.mark.asyncio
async def test_blocked_campaign_reaches_prepared_garrison_without_post_start_injection(
        monkeypatch, tmp_path):
    """The route response reaches a materially defended city on the same column."""
    world = await crossed_world(destination_food=0)
    request = next(item for item in creature_options(world, DRAKE_ID) if item.kind == "request")
    execute_creature_option(world, DRAKE_ID, request.id, decide(world, request).id)
    demand = next(iter(world.creatures.demands.values()))
    from src.sim.medieval.creature_policy import schedule_review
    schedule_review(world, DRAKE_ID, demand.due_day + 1)
    while world.clock.absolute_day < demand.due_day - 2:
        tick(world)

    direct = world.map.routes["road-portovelho-salgueiro"]
    record_event(world, "fixture_road_closed", "Passagem inicial indisponível no ramo de interferência.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "campaign_garrison_fixture",
                     "source_refs": [{"kind": "scenario", "id": "campaign_garrison_fixture"},
                                     {"kind": "route", "id": direct.id}],
                     "observed_day": world.clock.absolute_day}},
                 deltas=(_delta("route", direct.id, "enabled", True, False),))
    direct.update_runtime(enabled=False)
    settlement = world.society.settlements["portovelho"]
    record_event(world, "fixture_occupation", "Premissa preparada de ocupação rival.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "campaign_garrison_fixture",
                     "source_refs": [{"kind": "scenario", "id": "campaign_garrison_fixture"},
                                     {"kind": "settlement", "id": settlement.id}],
                     "observed_day": world.clock.absolute_day}},
                 deltas=(_delta("settlement", settlement.id, "occupier_id", None, "escarlia"),))
    world.society.set_occupation(settlement.id, "escarlia")
    initial_administrator_id = settlement.administrator_id
    defender_id, garrison_id = _prepare_portovelho_garrison(world)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    order = purchase(world, *consent(world, terms(world, quantity=500)))
    assert ROUTE_ID in order.route_ids
    # A prior allied reserve is a prepared-world premise, not a post-start
    # injection. Move existing food into a dedicated field depot so civilian
    # subsistence reserves remain protected during mobilization.
    camp_stock = world.economy.stocks["stock:campomanso"]
    pedraclara_stock = world.economy.stocks["stock:pedraclara"]
    depot_id = "stock:campaign-field-depot-valedouro"
    assert camp_stock.goods["food"] >= 6000 and pedraclara_stock.goods["food"] >= 4000
    depot_event = record_event(
        world, "fixture_campaign_depot_prepared", "Premissa de cenário: reserva de campanha aliada já posicionada.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_garrison_fixture",
            "source_refs": [{"kind": "scenario", "id": "campaign_garrison_fixture"},
                            {"kind": "stock", "id": camp_stock.id},
                            {"kind": "stock", "id": pedraclara_stock.id},
                            {"kind": "settlement", "id": "salgueiro"}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("stock", camp_stock.id, "food", camp_stock.goods["food"],
                       camp_stock.goods["food"] - 6000),
                _delta("stock", pedraclara_stock.id, "food", pedraclara_stock.goods["food"],
                       pedraclara_stock.goods["food"] - 4000),
                _delta("stock", depot_id, "food", None, 10000)),
        cause_ids=tuple(event_id for event_id in
                        (camp_stock.last_event_ids.get("food"), pedraclara_stock.last_event_ids.get("food"))
                        if event_id))
    world.economy.stocks[camp_stock.id] = camp_stock.model_copy(update={
        "goods": {**camp_stock.goods, "food": camp_stock.goods["food"] - 6000},
        "last_event_ids": {**camp_stock.last_event_ids, "food": depot_event.id}})
    world.economy.stocks[pedraclara_stock.id] = pedraclara_stock.model_copy(update={
        "goods": {**pedraclara_stock.goods, "food": pedraclara_stock.goods["food"] - 4000},
        "last_event_ids": {**pedraclara_stock.last_event_ids, "food": depot_event.id}})
    world.economy.stocks[depot_id] = Stock(
        id=depot_id, owner_ref=VALEDOURO, location_id="salgueiro", capacity=12000,
        goods={"food": 10000}, last_event_ids={"food": depot_event.id})
    world.economy.validate(world)
    reserve_group = world.society.population["pop:salgueiro:human:soldier"]
    civilian_group = world.society.population["pop:salgueiro:human:farmer"]
    reserve_count = max(0, 60 - reserve_group.count)
    assert world.society.available_count(civilian_group.id) >= reserve_count
    mobilization_premise = record_event(
        world, "fixture_campaign_reserve_prepared", "Premissa de cenário: reserva humana convocada antes do início.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "campaign_garrison_fixture",
            "source_refs": [{"kind": "scenario", "id": "campaign_garrison_fixture"},
                            {"kind": "population_group", "id": civilian_group.id},
                            {"kind": "population_group", "id": reserve_group.id}],
            "observed_day": world.clock.absolute_day}},
        deltas=(_delta("population_group", civilian_group.id, "count",
                       civilian_group.count, civilian_group.count - reserve_count),
                _delta("population_group", reserve_group.id, "count",
                       reserve_group.count, reserve_group.count + reserve_count)),
        cause_ids=tuple(event_id for event_id in (civilian_group.last_event_id, reserve_group.last_event_id)
                        if event_id))
    world.society.population[civilian_group.id] = civilian_group.model_copy(update={
        "count": civilian_group.count - reserve_count, "last_event_id": mobilization_premise.id})
    world.society.population[reserve_group.id] = reserve_group.model_copy(update={
        "count": reserve_group.count + reserve_count, "last_event_id": mobilization_premise.id})
    world.society.validate(set(world.map.regions), world)
    schedule_review(world, DRAKE_ID, world.clock.absolute_day + 1)
    refresh_route_reports(world)
    refresh_settlement_reports(world)
    adoption = next(item for item in defense_adoption_options(world, VALEDOURO)
                    if item.settlement_id == settlement.id)
    plan = adopt_occupied_settlement_defense(world, VALEDOURO, adoption.id,
                                             decide(world, adoption).id)
    expedition = max((item for item in defense_action_options(world, VALEDOURO, plan.id)
                      if ROUTE_ID in item.id), key=lambda item: (item.days, item.count))
    commander = world.society.characters["character:002"]
    if commander.location_id != expedition.settlement_id:
        record_event(world, "fixture_commander_available", "Comandante elegível na origem.",
                     fact_kind=FactKind.STATE_TRANSITION,
                     causal_payload={"root_premise": {
                         "kind": "scenario_bootstrap", "domain": "campaign_garrison_fixture",
                         "source_refs": [{"kind": "scenario", "id": "campaign_garrison_fixture"},
                                         {"kind": "character", "id": commander.id}],
                         "observed_day": world.clock.absolute_day}},
                     deltas=(_delta("character", commander.id, "location_id",
                                    commander.location_id, expedition.settlement_id),))
        world.society.characters[commander.id] = commander.model_copy(
            update={"location_id": expedition.settlement_id})
    civil_rites, faith_actor, faith_notice, schedule_faith_review = _prepare_competing_rites_and_faith(world)
    defender_instruction_id = _prepare_defender_instruction(world, defender_id)
    # The cargo fixture suppresses all production. Keep one ordinary authored
    # farm for the civil livelihood chain; no harvest, wages or food are added.
    from src.run.medieval_world import create_medieval_world
    farm = create_medieval_world(73).economy.facilities["works:campos-de-pedra-clara"]
    farm_premise = record_event(
        world, "fixture_existing_civil_farm", "Premissa preparada: os campos locais existentes continuam operando.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("facility", farm.id, "max_batches", None, farm.max_batches),),
        causal_payload={"root_premise": {
            "kind": "scenario_bootstrap", "domain": "medieval_composed_livelihood",
            "source_refs": [{"kind": "scenario", "id": "medieval_composed_livelihood"}],
            "observed_day": world.clock.absolute_day}})
    world.economy.facilities[farm.id] = farm.model_copy(update={"last_event_id": farm_premise.id})
    control = deepcopy(world)
    control_direct = control.map.routes["road-portovelho-salgueiro"]
    record_event(control, "fixture_control_route_open", "Contrafactual: a estrada direta permaneceu aberta.",
                 fact_kind=FactKind.STATE_TRANSITION,
                 causal_payload={"root_premise": {
                     "kind": "scenario_bootstrap", "domain": "campaign_garrison_control",
                     "source_refs": [{"kind": "scenario", "id": "campaign_garrison_control"},
                                     {"kind": "route", "id": control_direct.id}],
                     "observed_day": control.clock.absolute_day}},
                 deltas=(_delta("route", control_direct.id, "enabled", False, True),))
    control_direct.update_runtime(enabled=True)
    refresh_route_reports(control)
    start_day = world.clock.absolute_day
    for candidate in (world, control):
        candidate.config = candidate.config.model_copy(update={
            "ai_enabled": True, "ai_calls_per_step": 256, "ai_max_calls": 2000})
        schedule_faith_review(candidate, candidate.knowledge.religious_invitation_notices[faith_notice.id])
    blocked_mode = True
    provider_calls = []
    mature_garrison_choices = []
    active_candidate = [world]

    async def choose(prompt, *args, **kwargs):
        payload = json.loads(prompt[prompt.index("{"):])
        actor = EntityRef(**payload["you_are"])
        choices = payload["choices"]
        labels = [item["label"] for item in choices]
        situation = payload.get("situation", {})
        garrison_context = situation.get("campaign", {})
        own_garrison = situation.get("your_garrison") or {}
        mature_garrison_days = [item.get("days_active", 0)
                                for item in garrison_context.get("garrisons", ())
                                if item.get("stage") == "active"]
        if own_garrison.get("stage") == "active":
            mature_garrison_days.append(own_garrison.get("days_active", 0))
        garrison_mature = any(days >= 3 for days in mature_garrison_days)
        if actor == faith_actor and any(label.startswith("Escolher adesão ao convite ") for label in labels):
            wanted = next(label for label in labels if label.startswith("Escolher adesão ao convite "))
        elif actor == EntityRef("polity", "auren") and any(
                label.startswith("Construir ") and " em Pedraclara;" in label for label in labels):
            wanted = next(label for label in labels if label.startswith("Construir ") and " em Pedraclara;" in label)
        elif actor == EntityRef("polity", "auren") and any(
                label.startswith("Fundar a linha craft-workshop-foundation no sítio site:pedraclara:")
                for label in labels):
            wanted = next(label for label in labels if label.startswith(
                "Fundar a linha craft-workshop-foundation no sítio site:pedraclara:"))
        elif actor.kind == "creature":
            if not blocked_mode:
                return {"selected_id": ai_decider.NO_ACTION}
            wanted = "Fechar a passagem até ser atendido."
        elif actor.kind == "character" and payload.get("situation", {}).get("alternative_routes"):
            wanted = next((label for label in labels if label.startswith("Reencaminhar")), None)
        elif actor.kind == "character" and any("Autorizar o QG" in label for label in labels):
            wanted = "Autorizar o QG a preparar uma resposta material à ocupação observada."
        elif actor.kind == "character" and "supply_needs" in payload.get("situation", {}):
            wanted = next(label for label in labels if label.startswith("Enviar "))
        elif actor.kind == "character" and any(" dias e marchar" in label for label in labels):
            mobilizations = [label for label in labels if " dias e marchar" in label]
            wanted = max(mobilizations, key=lambda label: (
                int(label.split("para até ")[1].split(" dias")[0]), int(label.split()[1])))
        elif actor == VALEDOURO and garrison_mature and any(
                label == "Propor cessar-fogo mútuo." for label in labels):
            wanted = "Propor cessar-fogo mútuo."
            mature_garrison_choices.append((active_candidate[0].clock.absolute_day,
                                            tuple(mature_garrison_days)))
        elif any(label == "Aceitar o cessar-fogo." for label in labels):
            wanted = "Aceitar o cessar-fogo."
        elif any(label == "Cumprir a retirada material prometida no cessar-fogo." for label in labels):
            wanted = "Cumprir a retirada material prometida no cessar-fogo."
        elif actor == VALEDOURO and any(
                label == "Preparar uma posição no assentamento atual por três dias." for label in labels):
            wanted = "Preparar uma posição no assentamento atual por três dias."
        elif actor == VALEDOURO and any(
                label == "Pressionar todos os acessos operacionais deste assentamento com a coluna preparada."
                for label in labels):
            wanted = "Pressionar todos os acessos operacionais deste assentamento com a coluna preparada."
        elif actor == VALEDOURO and any(label == "Iniciar cerco material em portovelho." for label in labels):
            wanted = "Iniciar cerco material em portovelho."
        elif actor == VALEDOURO and any(
                label.startswith("Ocupar o assentamento após a brecha") for label in labels):
            wanted = next(label for label in labels
                          if label.startswith("Ocupar o assentamento após a brecha"))
        elif actor == VALEDOURO and any(
                label.startswith("Estabelecer uma guarnição paga para sustentar a ocupação")
                for label in labels):
            wanted = next(label for label in labels
                          if label.startswith("Estabelecer uma guarnição paga para sustentar a ocupação"))
        elif actor.kind in {"polity", "organization"} and any(
                label.startswith("Nomear ") for label in labels):
            wanted = next(label for label in labels if label.startswith("Nomear "))
        else:
            provider_calls.append((active_candidate[0].clock.absolute_day, actor.kind, actor.id,
                                   tuple(payload.get("situation", {}).keys()), tuple(labels), ai_decider.NO_ACTION))
            return {"selected_id": ai_decider.NO_ACTION}
        selected = next((item["id"] for item in choices if item["label"] == wanted), None)
        provider_calls.append((active_candidate[0].clock.absolute_day, actor.kind, actor.id,
                               tuple(payload.get("situation", {}).keys()), tuple(labels), selected))
        return {"selected_id": selected or ai_decider.NO_ACTION}

    monkeypatch.setattr(ai_decider, "provider_available", lambda: True)
    monkeypatch.setattr("src.utils.llm.client.call_llm_json", choose)
    treatment_engine, control_engine = MedievalSimulator(world), MedievalSimulator(control)
    first_close = (start_day // 30 + 1) * 30
    while world.clock.absolute_day < first_close:
        await treatment_engine.step()
    blocked_mode = False
    active_candidate[0] = control
    while control.clock.absolute_day < first_close:
        await control_engine.step()

    async def reach_contact(candidate, *, expected_block):
        active_candidate[0] = candidate
        engine = treatment_engine if candidate is world else control_engine
        limit = start_day + 120
        while candidate.clock.absolute_day < limit:
            campaign_column_id = candidate.strategy.plans[plan.id].detachment_id
            if campaign_column_id is not None and any(notice.own_detachment_id == campaign_column_id
                   for notice in candidate.knowledge.force_contact_notices.values()):
                break
            await engine.step()
        else:
            plan_state = candidate.strategy.plans[plan.id]
            column = candidate.society.detachments.get(plan_state.detachment_id)
            pytest.fail(f"column did not reach contact; day={candidate.clock.absolute_day}; "
                        f"plan={plan_state.stage}/{plan_state.blocker}; "
                        f"column={column}; events={[e.event_type for e in candidate.events[-25:]]}; "
                        f"provider_calls={provider_calls[-12:]}")
        own_id = candidate.strategy.plans[plan.id].detachment_id
        assert own_id is not None and own_id != defender_id
        assert candidate.society.detachments[own_id].location_id == "portovelho"
        assert candidate.society.detachments[own_id].stage == "present"
        assert candidate.society.detachments[defender_id].stage == "present"
        assert candidate.society.garrisons[garrison_id].stage == "active"
        training = candidate.society.detachment_trainings[defender_instruction_id]
        assert training.stage == "completed" and training.ready_day > start_day
        completion = candidate.event_index()[training.last_event_id]
        assert completion.event_type == "detachment_training_completed"
        assert training.knowledge_event_id in {link.cause_event_id for link in completion.causal_links}
        assert candidate.event_index()[training.knowledge_event_id].event_type == "technology_taught"
        from src.sim.medieval.field_engagement import _military_training_bonus
        assert _military_training_bonus(candidate, candidate.society.detachments[defender_id]) == 1
        arrival = next(event for event in reversed(candidate.events)
                       if event.event_type == "detachment_arrived"
                       and any(delta.owner_id == own_id and delta.aspect == "stage"
                               for delta in event.deltas))
        notice = next(notice for notice in candidate.knowledge.force_contact_notices.values()
                      if notice.own_detachment_id == own_id)
        assert notice.settlement_id == "portovelho"
        events = candidate.event_index()
        pending, ancestors = [notice.event_id], set()
        while pending:
            current = pending.pop()
            if current in ancestors:
                continue
            ancestors.add(current)
            pending.extend(link.cause_event_id for link in events[current].causal_links)
        assert arrival.id in ancestors
        closure_events = [event for event in candidate.events
                          if event.event_type == "creature_restricted_route"]
        assert bool(closure_events) is expected_block
        if expected_block:
            closure = closure_events[-1]
            assert candidate.map.routes[ROUTE_ID].enabled is False
        else:
            assert not closure_events
            assert candidate.map.routes[ROUTE_ID].enabled is True
        assert sum(event.event_type == "garrison_maintained" and
                   any(delta.owner_id == garrison_id for delta in event.deltas)
                   for event in candidate.events) >= 3
        return arrival, notice

    blocked_mode = True
    treatment_arrival, _ = await reach_contact(world, expected_block=True)
    blocked_mode = False
    control_arrival, _ = await reach_contact(control, expected_block=False)
    assert control_arrival.day < treatment_arrival.day

    async def reach_occupation(candidate, engine, *, expected_block):
        active_candidate[0] = candidate
        settlement = candidate.society.settlements["portovelho"]
        from src.sim.medieval.campaign_supply import campaign_stock_id
        from src.sim.medieval.settlement_investment import settlement_investment_options
        deadline = candidate.clock.absolute_day + 180
        own_id = candidate.strategy.plans[plan.id].detachment_id
        if expected_block:
            review_boundary = (candidate.clock.absolute_day // 30 + 1) * 30
            while (candidate.clock.absolute_day < deadline
                   and (f"force-position:{own_id}" not in candidate.society.force_positions
                        or candidate.society.force_positions[f"force-position:{own_id}"].stage != "prepared")):
                await engine.step()
            position = candidate.society.force_positions.get(f"force-position:{own_id}")
            assert position is not None and position.stage == "prepared", (
                f"the column did not prepare at contact; events={[event.event_type for event in candidate.events[-30:]]}"
            )
            while candidate.clock.absolute_day < review_boundary:
                await engine.step()
            assert settlement.occupier_id == "escarlia"
            assert not any(item.detachment_id == own_id and item.stage == "active"
                           for item in candidate.society.settlement_investments.values())
            assert not any(item.attacker_detachment_id == own_id
                           for item in candidate.society.siege_campaigns.values())
            assert not any(event.event_type == "settlement_invested"
                           and any(delta.owner_id == own_id for delta in event.deltas)
                           for event in candidate.events)
            assert candidate.map.routes[ROUTE_ID].enabled is False
            assert candidate.society.detachments[own_id].stage == "present"
            assert not any(option.detachment_id == own_id
                           for option in settlement_investment_options(candidate, VALEDOURO))
            prepared_event = next(event for event in candidate.events
                                  if event.event_type == "force_position_prepared"
                                  and any(delta.owner_id == f"force-position:{own_id}"
                                          for delta in event.deltas))
            reconsultation = next(event for event in candidate.events
                                  if event.event_type == "force_standoff_decided"
                                  and event.day > prepared_event.day
                                  and event.decision is not None
                                  and event.decision.get("actor_ref") == VALEDOURO.to_dict())
            assert any(link.cause_event_id == prepared_event.id
                       for link in reconsultation.causal_links)
            assert not any(event.event_type.startswith("fixture_") and event.day > start_day
                           for event in candidate.events)
            return None
        def occupation_event():
            return next((event for event in candidate.events
                         if event.event_type == "settlement_occupied_after_siege"
                         and event.day > start_day
                         and any(delta.owner_id == settlement.id
                                 and delta.aspect == "occupier_id"
                                 and delta.after == VALEDOURO.id
                                 for delta in event.deltas)), None)

        while occupation_event() is None and candidate.clock.absolute_day < deadline:
            await engine.step()
        occupation = occupation_event()
        assert occupation is not None, (
            f"no occupation by day {deadline}; stage={candidate.society.detachments[own_id].stage}; "
            f"count={candidate.society.detachments[own_id].count}; "
            f"provisions={candidate.society.detachments[own_id].provisions}; "
            f"position={candidate.society.force_positions.get(f'force-position:{own_id}')}; "
            f"investment_options={settlement_investment_options(candidate, VALEDOURO)}; "
            f"local_reports={[(r.route_id, r.observed_day, r.operational_capacity, r.channel) for r in candidate.knowledge.route_reports.values() if r.recipient_ref == VALEDOURO and r.observed_day >= candidate.clock.absolute_day - 30 and r.route_id in {'river-pedraclara-portovelho', 'road-portovelho-cinzaverde', 'road-portovelho-salgueiro'}]}; "
            f"campaign_events={[(event.day, event.event_type) for event in candidate.events if any(token in event.event_type for token in ('siege', 'force_position', 'settlement_invested', 'detachment_disbanded'))]}; "
            f"campaign_calls={[(call[0], tuple(label for label in call[4] if any(token in label for token in ('posição', 'acessos', 'cerco material', 'Ocupar'))), call[5]) for call in provider_calls if call[2] == VALEDOURO.id and call[0] < 130]}"
        )
        position = candidate.society.force_positions[f"force-position:{own_id}"]
        investment = next(item for item in candidate.society.settlement_investments.values()
                          if item.detachment_id == own_id)
        campaign = next(item for item in candidate.society.siege_campaigns.values()
                        if item.attacker_detachment_id == own_id)
        assert position.stage == "prepared"
        assert investment.stage == "active"
        assert campaign.phase == "breached"
        assert candidate.society.detachments[own_id].stage == "present"
        assert candidate.society.settlements[settlement.id].occupier_id == VALEDOURO.id
        assert bool(any(event.event_type == "creature_restricted_route" for event in candidate.events)) \
            is expected_block
        event_by_type = {}
        for event_type in ("force_position_preparing", "force_position_prepared", "settlement_invested",
                           "siege_campaign_started", "siege_campaign_breached",
                           "settlement_occupied_after_siege"):
            event_by_type[event_type] = next(event for event in candidate.events
                                             if event.event_type == event_type)
        assert event_by_type["force_position_preparing"].day > start_day
        assert event_by_type["settlement_occupied_after_siege"].sequence > \
            event_by_type["siege_campaign_breached"].sequence
        assert any(link.cause_event_id == event_by_type["force_position_preparing"].id
                   for link in event_by_type["force_position_prepared"].causal_links)
        assert any(link.cause_event_id == event_by_type["force_position_prepared"].id
                   for link in event_by_type["settlement_invested"].causal_links)
        assert any(link.cause_event_id == event_by_type["settlement_invested"].id
                   for link in event_by_type["siege_campaign_started"].causal_links)
        assert any(link.cause_event_id == event_by_type["siege_campaign_breached"].id
                   for link in event_by_type["settlement_occupied_after_siege"].causal_links)
        assert not any(event.event_type.startswith("fixture_") and event.day > start_day
                       for event in candidate.events)
        event_by_type["settlement_occupied_after_siege"] = occupation
        return event_by_type

    blocked_mode = True
    blocked_chain = await reach_occupation(world, treatment_engine, expected_block=True)
    blocked_mode = False
    control_chain = await reach_occupation(control, control_engine, expected_block=False)
    assert blocked_chain is None
    assert control_chain["settlement_occupied_after_siege"].day == control.clock.absolute_day
    selected_actors = {(call[1], call[2]) for call in provider_calls
                       if call[0] > start_day and call[5] not in (None, ai_decider.NO_ACTION)}
    assert any(kind == "polity" and identity == VALEDOURO.id
               for kind, identity in selected_actors)
    assert any(kind == "character" for kind, _ in selected_actors)

    from src.sim.medieval.force import garrison_options
    control_detachment_id = control.strategy.plans[plan.id].detachment_id
    assert control_detachment_id is not None
    garrison_id = f"garrison:{control_detachment_id}"
    garrison_deadline = control.clock.absolute_day + 90
    active_candidate[0] = control

    def paid_garrison_days():
        return sum(event.event_type == "garrison_maintained"
                   and any(delta.owner_id == garrison_id for delta in event.deltas)
                   for event in control.events)

    while (control.clock.absolute_day < garrison_deadline
           and (garrison_id not in control.society.garrisons
                or control.society.garrisons[garrison_id].stage != "active"
                or paid_garrison_days() < 3)):
        await control_engine.step()
    garrison_options_now = garrison_options(control, VALEDOURO)
    garrison_calls = [(call[0], call[4], call[5]) for call in provider_calls
                      if call[2] == VALEDOURO.id
                      and any("guarnição" in label for label in call[4])]
    assert (garrison_id in control.society.garrisons
            and control.society.garrisons[garrison_id].stage == "active"
            and paid_garrison_days() >= 3), (
        f"the captured settlement did not receive an owner-selected garrison: "
        f"day={control.clock.absolute_day}; "
        f"occupier={control.society.settlements['portovelho'].occupier_id}; "
        f"detachment={control.society.detachments[control_detachment_id]}; "
        f"options={[(item.kind, item.id) for item in garrison_options_now]}; "
        f"maintenance_days={paid_garrison_days()}; "
        f"calls={garrison_calls}")
    ceasefire_deadline = control.clock.absolute_day + 120
    while control.clock.absolute_day < ceasefire_deadline:
        active_proposals = [proposal for proposal in control.relations.proposals.values()
                            if proposal.proposal_kind == "campaign_ceasefire"
                            and proposal.status == "accepted"]
        if active_proposals and all(
                obligation.status == "fulfilled"
                for obligation in control.relations.obligations.values()
                if obligation.proposal_id in {proposal.id for proposal in active_proposals}):
            break
        await control_engine.step()
    accepted = [proposal for proposal in control.relations.proposals.values()
                if proposal.proposal_kind == "campaign_ceasefire" and proposal.status == "accepted"]
    relevant_calls = [(call[0], call[4], call[5]) for call in provider_calls
                      if call[2] in {VALEDOURO.id, "escarlia"}
                      and any("cessar-fogo" in label or "Cumprir a retirada" in label
                              for label in call[4])]
    assert accepted, (
        f"the mature occupying institution did not offer a bilateral withdrawal; "
        f"day={control.clock.absolute_day}; garrison={control.society.garrisons[garrison_id]}; "
        f"calls={relevant_calls[-12:]}"
    )
    proposal = accepted[-1]
    obligations = [item for item in control.relations.obligations.values()
                   if item.proposal_id == proposal.id]
    assert len(obligations) == 2
    assert all(item.status == "fulfilled" for item in obligations)
    assert control.society.garrisons[garrison_id].stage == "withdrawn"
    assert control.society.settlements["portovelho"].occupier_id is None
    assert control.society.settlements["portovelho"].administrator_id == initial_administrator_id
    assert (control.society.detachments[control_detachment_id].stage == "marching"
            or control.society.detachments[control_detachment_id].location_id != "portovelho")
    assert (control.society.detachments[defender_id].stage == "marching"
            or control.society.detachments[defender_id].location_id != "portovelho")
    assert paid_garrison_days() >= 3
    fulfillment_events = [event for event in control.events
                          if event.event_type == "commitment_fulfilled"
                          and event.causal_payload.get("proposal_id") == proposal.id]
    assert len(fulfillment_events) == 2
    assert (mature_garrison_choices
            and any(days >= 3 for days in mature_garrison_choices[-1][1]))
    withdrawal_events = [event for event in control.events
                         if event.event_type == "detachment_withdrawal_started"
                         and any(delta.owner_id in {control_detachment_id, defender_id}
                                 and delta.aspect == "stage" and delta.after == "marching"
                                 for delta in event.deltas)]
    assert {next(delta.owner_id for delta in event.deltas
                 if delta.aspect == "stage" and delta.after == "marching")
            for event in withdrawal_events} == {control_detachment_id, defender_id}
    event_index = control.event_index()
    for event in withdrawal_events:
        assert event.causal_origin == CausalOrigin.ACTOR_DECISION
        source_decisions = [event_index[link.cause_event_id] for link in event.causal_links
                            if link.cause_event_id in event_index
                            and event_index[link.cause_event_id].fact_kind == FactKind.DECISION]
        assert len(source_decisions) == 1
        assert source_decisions[0].decision.get("actor_ref") == event.causal_payload["actor_ref"]
    for event in fulfillment_events:
        material = event_index[event.causal_payload["material_event_id"]]
        assert material.id in {link.cause_event_id for link in event.causal_links}
        assert any(event_index[link.cause_event_id].fact_kind == FactKind.DECISION
                   for link in material.causal_links
                   if link.cause_event_id in event_index)
    position_id = f"force-position:{control_detachment_id}"
    preparation_attempts = [event for event in control.events
                            if event.event_type == "force_position_preparing"
                            and any(delta.owner_id == position_id and delta.aspect == "stage"
                                    and delta.after == "preparing" for delta in event.deltas)]
    assert len(preparation_attempts) >= 2
    closure = next(event for event in reversed(world.events)
                   if event.event_type == "creature_restricted_route")
    cargo_delay = next(event for event in world.events
                       if event.event_type == "cargo_delayed"
                       and closure.id in {link.cause_event_id for link in event.causal_links})
    assert cargo_delay is not None
    assert control.economy.freight_orders[order.id].delivered_quantity > \
        world.economy.freight_orders[order.id].delivered_quantity
    common_boundary = (max(world.clock.absolute_day, control.clock.absolute_day) // 30 + 1) * 30
    for candidate, engine in ((world, treatment_engine), (control, control_engine)):
        candidate.config = candidate.config.model_copy(update={"ai_enabled": False})
        while candidate.clock.absolute_day < common_boundary:
            await engine.step()
    blocked_need = world.economy.needs["portovelho"]
    control_need = control.economy.needs["portovelho"]
    assert blocked_need.missing_food > control_need.missing_food
    assert blocked_need.health < control_need.health

    # Continue the same worlds, not a new economic fixture: ordinary reviews
    # may build the workshop and its line; construction and production use
    # shared real stock, treasury and workers throughout the campaign history.
    for candidate, engine in ((world, treatment_engine), (control, control_engine)):
        active_candidate[0] = candidate
        blocked_mode = candidate is world
        candidate.config = candidate.config.model_copy(update={"ai_enabled": True})
        while candidate.clock.absolute_day < 240:
            await engine.step()
        line = next(f for f in candidate.economy.facilities.values()
                    if f.site_id.startswith("site:pedraclara:") and f.recipe_id == "toolmaking")
        payroll = candidate.economy.payrolls[line.id]
        assert payroll.gross > 0
        assert any(candidate.society.population[group].occupation == "artisan"
                   for group in payroll.workers_by_group)
        assert any(event.event_type == "household_purchase_completed"
                   and payroll.last_event_id in {link.cause_event_id for link in event.causal_links}
                   for event in candidate.events)

    for candidate, name in ((world, "blocked"), (control, "control")):
        local_rite, competing_rite = (candidate.research.rites[identity] for identity in civil_rites)
        assert local_rite.stage == "completed" and competing_rite.stage == "failed"
        complete = candidate.event_index()[local_rite.last_event_id]
        failed = candidate.event_index()[competing_rite.last_event_id]
        assert complete.day > start_day and failed.day == complete.day
        consumed = complete
        assert any(d.owner_id == local_rite.stock_id and d.aspect == "reagents" for d in complete.deltas)
        assert consumed.id in {link.cause_event_id for link in failed.causal_links}
        affiliation = next(a for a in candidate.society.religious_adherences.values() if a.actor_ref == faith_actor)
        assert affiliation.joined_day > start_day
        assert affiliation.invitation_id == faith_notice.id
        assert not any(a.actor_ref.kind == "character" for a in candidate.society.religious_adherences.values())
        assert {g.people for g in candidate.society.population.values()} == {"human","elf","dwarf","orc"}
        assert candidate.economy.payrolls[local_rite.id].gross == 4
        path = tmp_path / f"campaign-garrison-{name}.mws"
        save_world(candidate, path)
        restored = load_world(path)
        assert world_snapshot(restored) == world_snapshot(candidate)
        from tools.medieval_causal_audit import audit
        assert audit(path)["ok"] is True
        if name == "control":
            from src.server.medieval.queries import causal_view
            defender_fulfillment = next(event for event in fulfillment_events
                                        if event.causal_payload["clause_index"] == 1)
            material = restored.event_index()[defender_fulfillment.causal_payload["material_event_id"]]
            why = causal_view(restored, material.id, after=material.sequence - 1, limit=100)
            assert why.event.id == material.id
            assert any(item.fact_kind == FactKind.DECISION for item in why.causes)
            assert any(item.event_type == "commitment_fulfilled"
                       and item.causal_payload.get("material_event_id") == material.id
                       for item in why.effects)
