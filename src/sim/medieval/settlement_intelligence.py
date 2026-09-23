"""Dated, aggregate settlement observations and physically delivered bulletins."""

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.knowledge import settlement_report_id
from src.classes.governance.models import SettlementReport, settlement_observation
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
            and previous.warded == warded):
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
                              warded=warded,
                              channel="local_settlement_report", event_id="pending")
    occupation_source = (_occupation_source(world, settlement_id, settlement.occupier_id)
                         if previous is None or previous.occupier_id != settlement.occupier_id else None)
    event = record_event(world, "settlement_observed",
                         f"{settlement.name}: {report.present_population}/{report.population} presentes, saúde {report.health}/1000.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("settlement_report", key, "observation",
                                        previous.observation() if previous else None, report.observation()),),
                         cause_ids=_causes(*_sources(world, settlement_id),
                                           previous.event_id if previous is not None else None,
                                           occupation_source,
                                           *presence_causes))
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


def _recipients(world):
    return [EntityRef("population_group", group_id) for group_id in sorted(world.society.population)
            if world.society.available_count(group_id) > 0]


def _reachable(world, settlement_id, recipient):
    group = world.society.population.get(recipient.id)
    return group is not None and world.society.available_count(group.id) > 0 and (
        supply_path(world, settlement_id, group.settlement_id) is not None)


def _publish(world, report):
    publisher = report.publisher_ref
    if not can_actor_act_for(world, publisher, publisher, "trade"):
        return
    targets = [recipient for recipient in _recipients(world) if recipient != publisher
               and (world.knowledge.settlement_report(recipient, report.settlement_id) is None
                    or world.knowledge.settlement_report(recipient, report.settlement_id).observed_day != report.observed_day)
               and _reachable(world, report.settlement_id, recipient)]
    if not targets:
        return
    observation = report.observation()
    decision = record_event(world, "settlement_report_published",
                            f"Boletim público de {world.society.settlements[report.settlement_id].name} publicado.",
                            fact_kind=FactKind.DECISION,
                            decision={"action": "publish_settlement_report", "actor_ref": publisher.to_dict(),
                                      "settlement_id": report.settlement_id, "observation": observation,
                                      "recipients": [recipient.to_dict() for recipient in targets]},
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
        world.knowledge.settlement_reports[keys[recipient]] = report.model_copy(update={
            "id": keys[recipient], "recipient_ref": recipient, "channel": "settlement_bulletin", "event_id": delivery.id})


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


def refresh_existing_local_settlement_reports(world, settlement_id):
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
            _observe(world, report.recipient_ref, settlement_id)
