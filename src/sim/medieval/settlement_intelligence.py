"""Dated, aggregate settlement observations and physically delivered bulletins."""

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.governance.authority import can_actor_act_for, headquarters_holder, political_holder
from src.classes.governance.knowledge import settlement_report_id
from src.classes.governance.models import FieldEngagementReading, SettlementReport
from src.classes.mechanical_language import EntityRef
from .economy import _causes, _delta
from .events import record_event
from .routing import supply_path


def _sources(world, settlement_id):
    need = world.economy.needs[settlement_id]
    stock = world.economy.stocks[need.stock_id]
    resident_events = [group.last_event_id for group in world.society.population.values()
                       if group.settlement_id == settlement_id]
    # A settlement report reads the condition *and* the public granary that
    # supports its next legal relief affordance.  Freight can replenish that
    # granary without changing ``SettlementNeeds`` until a later distribution
    # or monthly consumption.  Keeping the stock receipt here preserves
    # ``cargo_delivered -> observation -> decision`` rather than making a
    # newly observed material arrival disappear from Why.
    return _causes(need.last_event_id, stock.last_event_ids.get("food"), *resident_events)


def _occupation_source(world, settlement_id, occupier_id):
    """Find the latest material occupation fact for a changed local reading."""
    for event in reversed(world.events):
        if any(delta.owner_kind == "settlement" and delta.owner_id == settlement_id
               and delta.aspect == "occupier_id" and delta.after == str(occupier_id)
               for delta in event.deltas):
            return event.id
    return None


def _field_engagement_readings(world, settlement_id, day):
    """Bounded after-action facts visible at the settlement, not private plans."""
    readings = []
    events = world.event_index()
    for engagement in sorted(world.society.field_engagements.values(), key=lambda item: item.id):
        event = events.get(engagement.last_event_id)
        if (engagement.status != "resolved" or engagement.settlement_id != settlement_id or event is None
                or event.event_type != "field_engagement_resolved" or not day - 30 <= event.day <= day):
            continue
        readings.append(FieldEngagementReading(
            event_id=event.id, engagement_id=engagement.id,
            challenger_ref=engagement.challenger_ref, defender_ref=engagement.defender_ref,
            winner_ref=engagement.winner_ref, challenger_casualties=engagement.challenger_casualties,
            defender_casualties=engagement.defender_casualties))
    return tuple(readings)


def _observe(world, actor, settlement_id, *, presence_causes=()):
    day = world.clock.absolute_day
    key = settlement_report_id(actor, settlement_id)
    previous = world.knowledge.settlement_reports.get(key)
    rite_underway = any(rite.settlement_id == settlement_id and rite.stage == "officiating"
                        for rite in world.research.rites.values())
    protest_underway = any(protest.settlement_id == settlement_id and protest.stage == "open"
                           for protest in world.society.civic_protests.values())
    warded = any(ward.settlement_id == settlement_id and ward.until_day > day
                 for ward in world.research.wards.values())
    field_engagements = _field_engagement_readings(world, settlement_id, day)
    settlement = world.society.settlements[settlement_id]
    need = world.economy.needs[settlement_id]
    population = world.society.population_at(settlement_id)
    present_population = world.society.present_population_at(settlement_id)
    if (previous is not None and previous.observed_day == day
            and previous.recipient_ref == actor and previous.publisher_ref == actor
            and previous.population == population and previous.present_population == present_population
            and previous.housing_capacity == settlement.housing_capacity
            and previous.health == need.health and previous.missing_food == need.missing_food
            and previous.unrest == need.unrest and previous.occupier_id == settlement.occupier_id
            and previous.rite_underway == rite_underway and previous.protest_underway == protest_underway
            and previous.warded == warded and previous.field_engagements == field_engagements):
        return previous
    report = SettlementReport(id=key, recipient_ref=actor, publisher_ref=actor, settlement_id=settlement_id,
                              observed_day=day, population=population,
                              present_population=present_population,
                              housing_capacity=settlement.housing_capacity, health=need.health,
                              missing_food=need.missing_food, unrest=need.unrest,
                              occupier_id=settlement.occupier_id,
                              # Only that a rite is underway here: never who
                              # performs it, with what skill, stock or funds.
                              rite_underway=rite_underway,
                              protest_underway=protest_underway,
                              # Standing protective works are visible; the rite
                              # that raised them and its sponsor are not.
                              warded=warded, field_engagements=field_engagements,
                              channel="local_settlement_report", event_id="pending")
    occupation_source = (_occupation_source(world, settlement_id, settlement.occupier_id)
                         if previous is None or previous.occupier_id != settlement.occupier_id else None)
    causes = _causes(*_sources(world, settlement_id),
                     previous.event_id if previous is not None else None,
                     occupation_source,
                     *(item.event_id for item in field_engagements),
                     *presence_causes)
    causal_payload = None
    if not causes:
        # The first observation of a newly generated settlement may precede
        # every owner receipt. Preserve that world-generation premise
        # explicitly instead of emitting an unrooted report transition.
        causal_payload = {"root_premise": {
            "kind": "world_generation",
            "domain": "settlement_observation",
            "source_refs": [
                {"kind": "settlement", "id": settlement_id},
                {"kind": "settlement_needs", "id": need.id},
                {"kind": "stock", "id": need.stock_id},
                {"kind": "observer", "id": f"{actor.kind}:{actor.id}"},
            ],
            "observed_day": day,
        }}
    event = record_event(world, "settlement_observed",
                         f"{settlement.name}: {report.present_population}/{report.population} presentes, saúde {report.health}/1000.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("settlement_report", key, "observation",
                                        previous.observation() if previous else None, report.observation()),),
                         causal_payload=causal_payload, cause_ids=causes)
    report = report.model_copy(update={"event_id": event.id})
    world.knowledge.settlement_reports[key] = report
    return report


def observe_present_household(world, group_id, settlement_id, journey_event_id):
    """A household stranded at an endpoint may observe where it physically is."""
    journey = next((item for item in world.society.migrations.values()
                    if item.source_group_id == group_id and item.destination_id == settlement_id
                    and item.stage == "stranded" and item.last_event_id == journey_event_id), None)
    if journey is None:
        raise ValueError("settlement observation requires the household's stranded journey")
    return _observe(world, EntityRef("population_group", group_id), settlement_id,
                    presence_causes=(journey_event_id,))


def _present_observer(world, recipient_ref, settlement_id):
    """Whether this observer still stands where its own local report was made.

    A local observation is a fact about presence, not a standing subscription.
    Residents, a located person, the administration, an institution operating
    a site here, a present detachment and a current office holder standing in
    the settlement are all really here; anyone else has only been here.
    """
    settlement = world.society.settlements.get(settlement_id)
    if settlement is None:
        return False
    if recipient_ref.kind == "population_group":
        group = world.society.population.get(recipient_ref.id)
        return group is not None and group.settlement_id == settlement_id
    if recipient_ref.kind == "character":
        person = world.society.characters.get(recipient_ref.id)
        return person is not None and person.death_day is None and person.location_id == settlement_id
    if (settlement.administrator_id is not None
            and recipient_ref == EntityRef("polity", settlement.administrator_id)):
        return True
    if any(site.owner_ref == recipient_ref and settlement.region_id in site.region_ids
           for site in world.map.infrastructure_sites.values()):
        return True
    if any(detachment.owner_ref == recipient_ref and detachment.location_id == settlement_id
           and detachment.stage == "present" for detachment in world.society.detachments.values()):
        return True
    day = world.clock.absolute_day
    for office in world.authority.offices.values():
        if (office.institution_ref != recipient_ref or office.holder_ref.kind != "character"
                or office.starts_day > day or (office.ends_day is not None and day >= office.ends_day)):
            continue
        holder = world.society.characters.get(office.holder_ref.id)
        if holder is not None and holder.death_day is None and holder.location_id == settlement_id:
            return True
    return False


def observe_present_agent(world, actor, settlement_id, presence_causes=()):
    """An institution's own person standing somewhere observes it for the institution.

    This is the ordinary dated local observation any present actor makes --
    ``local_settlement_report``, recipient and publisher alike, derived from
    presence and from nobody else's bulletin. It reads the same aggregate
    condition a resident reads and never a foreign stock, account or plan.
    The caller owns whatever put the person there and passes its dated
    receipts as the presence cause.
    """
    if (not isinstance(actor, EntityRef) or settlement_id not in world.society.settlements
            or not _present_observer(world, actor, settlement_id)):
        raise ValueError("settlement observation requires the institution's present agent")
    report = _observe(world, actor, settlement_id, presence_causes=tuple(presence_causes))
    if report.channel != "local_settlement_report" or report.recipient_ref != report.publisher_ref:
        raise ValueError("a present agent produces its institution's own local observation")
    return report


def observe_present_force(world, detachment_id):
    """A detachment standing somewhere lets its owner observe that place.

    Reconnaissance produces knowledge and nothing else: no control, no access
    to anyone's stock, and no reading of another institution's force.
    """
    detachment = world.society.detachments.get(detachment_id)
    if detachment is None or detachment.stage != "present":
        raise ValueError("settlement observation requires a present detachment")
    report = _observe(world, detachment.owner_ref, detachment.location_id,
                      presence_causes=(detachment.last_event_id,))
    from .rites import observe_rites
    observe_rites(world, settlement_id=detachment.location_id)
    return report


def _recipients(world, publisher):
    recipients = [EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
                  if world.society.available_count(group_id) > 0]
    if publisher.kind == "polity":
        for holder in (political_holder(world, publisher), headquarters_holder(world, publisher)):
            if holder is not None and holder not in recipients:
                recipients.append(holder)
    return recipients


def _reachable(world, settlement_id, recipient):
    if recipient.kind == "character":
        person = world.society.characters.get(recipient.id)
        return (person is not None and person.death_day is None
                and supply_path(world, settlement_id, person.location_id) is not None)
    group = world.society.population.get(recipient.id)
    return group is not None and world.society.available_count(group.id) > 0 and (
        supply_path(world, settlement_id, group.settlement_id) is not None)


def _publish(world, report):
    publisher = report.publisher_ref
    if not can_actor_act_for(world, publisher, publisher, "trade"):
        return
    targets = [recipient for recipient in _recipients(world, publisher) if recipient != publisher
               and (world.knowledge.settlement_report(recipient, report.settlement_id) is None
                    or world.knowledge.settlement_report(recipient, report.settlement_id).observed_day != report.observed_day)
               and _reachable(world, report.settlement_id, recipient)]
    if not targets:
        return
    observation = report.observation()
    decision = record_event(world, "settlement_report_published",
                            f"Boletim público de {world.society.settlements[report.settlement_id].name} publicado.",
                            fact_kind=FactKind.DECISION,
                            causal_origin=CausalOrigin.DETERMINISTIC,
                            decision={"action": "publish_settlement_report", "actor_ref": publisher.to_dict(),
                                      "settlement_id": report.settlement_id, "observation": observation,
                                      "recipients": [recipient.to_dict() for recipient in targets]},
                            causal_payload={"decision_source": {"kind": "owner", "owner": "knowledge",
                                                                  "rule": "monthly_settlement_bulletin"}},
                            cause_ids=(report.event_id,))
    keys = {recipient: settlement_report_id(recipient, report.settlement_id) for recipient in targets}
    previous = {recipient: world.knowledge.settlement_reports.get(key) for recipient, key in keys.items()}
    delivery = record_event(world, "settlement_report_received",
                            f"Boletim de {world.society.settlements[report.settlement_id].name} entregue.",
                            fact_kind=FactKind.STATE_TRANSITION,
                            deltas=tuple(_delta("settlement_report", keys[recipient], "observation",
                                                previous[recipient].observation() if previous[recipient] else None,
                                                observation) for recipient in targets),
                            cause_ids=_causes(decision.id, report.event_id))
    for recipient in targets:
        delivered = report.model_copy(update={
            "id": keys[recipient], "recipient_ref": recipient, "channel": "settlement_bulletin", "event_id": delivery.id})
        world.knowledge.settlement_reports[keys[recipient]] = delivered
        if (recipient == headquarters_holder(world, publisher)
                and any(publisher in {item.challenger_ref, item.defender_ref}
                        for item in report.field_engagements)):
            from .field_aftermath_policy import schedule_headquarters_field_response
            schedule_headquarters_field_response(world, delivered)
        if recipient == political_holder(world, publisher) and report.field_engagements:
            from .strategy_response import schedule_political_campaign_result_review
            schedule_political_campaign_result_review(world, delivered)


def refresh_settlement_reports(world):
    """Publish no mandatory gossip: only supplied administrations and local residents observe."""
    for settlement_id in sorted(world.society.settlements):
        settlement = world.society.settlements[settlement_id]
        actors = []
        if settlement.administrator_id is not None:
            admin = EntityRef("polity", settlement.administrator_id)
            if can_actor_act_for(world, admin, admin, "supply"):
                actors.append(admin)
        # An institution that owns a local site can inspect the settlement it
        # operates in.  This is still an actor-specific observation: it does
        # not expose another institution's stock or accounts, and it creates
        # no report while merely enumerating affordances.
        site_owners = {
            site.owner_ref
            for site in world.map.infrastructure_sites.values()
            if site.owner_ref is not None and settlement.region_id in site.region_ids
        }
        actors.extend(
            owner for owner in sorted(site_owners, key=lambda item: (item.kind, item.id))
            if can_actor_act_for(world, owner, owner, "supply")
        )
        field_observers = {detachment.owner_ref for detachment in world.society.detachments.values()
                           if detachment.stage == "present" and detachment.location_id == settlement_id}
        actors.extend(owner for owner in sorted(field_observers, key=lambda item: (item.kind, item.id))
                      if can_actor_act_for(world, owner, owner, "trade"))
        actors.extend(EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
                      if world.society.population[group_id].settlement_id == settlement_id
                      and world.society.available_count(group_id) > 0)
        # Relevant named residents make the same aggregate local observation as
        # their cohort. This grants neither stores, accounts, offices nor
        # information about other settlements.
        actors.extend(
            EntityRef("character", character_id)
            for character_id, character in sorted(world.society.characters.items())
            if character.death_day is None and character.location_id == settlement_id
        )
        for actor in actors:
            report = _observe(world, actor, settlement_id)
            if actor.kind == "polity":
                _publish(world, report)
    from .rites import observe_rites
    observe_rites(world)


def refresh_existing_local_settlement_reports(world, settlement_id, *, cause_event_ids=()):
    """Refresh a changed local status without creating new observers.

    Some public flags (such as a civic demand underway) are readable only by
    actors who already held a direct local observation.  This helper therefore
    never publishes a new bulletin and never turns mere reachability into
    knowledge; it only replaces an existing own local report.

    It also does not renew one for an observer that has since left. A past
    visit -- an agent's mission, a detachment that marched on -- is history,
    not a standing watch over someone else's town.
    """
    for report in sorted(world.knowledge.settlement_reports.values(), key=lambda item: item.id):
        if (report.settlement_id == settlement_id and report.recipient_ref == report.publisher_ref
                and report.channel == "local_settlement_report"
                and _present_observer(world, report.recipient_ref, settlement_id)):
            _observe(world, report.recipient_ref, settlement_id, presence_causes=cause_event_ids)
