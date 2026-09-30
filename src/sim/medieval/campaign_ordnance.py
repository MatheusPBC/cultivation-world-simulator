"""Engine-owned freight and use of researched siege artillery.

Ordnance remains ordinary Economy stock. A headquarters must send real goods
to a co-located campaign bag over known, physically valid routes; a later
current decision may spend one powder charge against an active siege. No
combat score or battery state is duplicated outside those owners.
"""

from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, headquarters_holder, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.sim.medieval.material_execution import execute_material

from .campaign_supply import campaign_stock_id
from .demand import reserve_quantity
from .economy import _causes, _delta
from .events import record_event
from .force import _decision as force_decision
from .logistics import open_order
from .routing import known_supply_path
from .siege_campaign import _current_parts, _schedule_campaign_contact_reviews


DISPATCH_ACTION = "dispatch_campaign_ordnance"
BOMBARD_ACTION = "bombard_siege"
ARTILLERY_RESOURCE = "artillery"
POWDER_RESOURCE = "gunpowder"
MAX_ARTILLERY_PIECES = 1
MAX_CAMPAIGN_ROUNDS = 3
GARRISON_ENDURANCE_PER_ROUND = 2


@dataclass(frozen=True)
class CampaignOrdnanceOption:
    id: Identity
    actor_ref: EntityRef
    campaign_id: Identity | None
    detachment_id: Identity
    kind: str
    resource_id: Identity | None = None
    source_stock_id: Identity | None = None
    quantity: int = 0
    route_ids: tuple[Identity, ...] = ()
    route_report_event_ids: tuple[Identity, ...] = ()

    def decision(self):
        return {"action": DISPATCH_ACTION if self.kind == "dispatch" else BOMBARD_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _pending_quantity(world, destination_id, resource_id):
    return sum(
        parcel.quantity for parcel in world.economy.parcels.values()
        if parcel.order_id in world.economy.freight_orders
        and (order := world.economy.freight_orders[parcel.order_id]).destination_id == destination_id
        and order.resource_id == resource_id
    )


def _has_bombarded_today(world, campaign_id):
    return any(
        event.day == world.clock.absolute_day
        and event.event_type in {"siege_artillery_fired", "siege_campaign_breached"}
        and isinstance(event.causal_payload, dict)
        and event.causal_payload.get("campaign_id") == campaign_id
        for event in world.events
    )


def _dispatch_options(world, actor, headquarters, attacker, bag, campaign_id):
    """Offer bounded equipment freight for an active siege or its staged column."""
    options = []
    incoming_artillery = _pending_quantity(world, bag.id, ARTILLERY_RESOURCE)
    artillery = bag.goods.get(ARTILLERY_RESOURCE, 0)
    for resource_id, target in (
        (ARTILLERY_RESOURCE, MAX_ARTILLERY_PIECES),
        (POWDER_RESOURCE, MAX_CAMPAIGN_ROUNDS),
    ):
        current = bag.goods.get(resource_id, 0)
        pending = _pending_quantity(world, bag.id, resource_id)
        if resource_id == POWDER_RESOURCE and artillery + incoming_artillery <= 0:
            continue
        desired = max(0, target - current - pending)
        if desired <= 0:
            continue
        resource = world.economy.resources.get(resource_id)
        if resource is None:
            continue
        pending_bulk = sum(
            parcel.quantity * world.economy.resources[order.resource_id].bulk
            for parcel in world.economy.parcels.values()
            if parcel.order_id in world.economy.freight_orders
            and (order := world.economy.freight_orders[parcel.order_id]).destination_id == bag.id
        )
        headroom = max(0, bag.capacity - world.economy.used_capacity(bag) - pending_bulk)
        for source in sorted(world.economy.stocks.values(), key=lambda item: item.id):
            if source.id == bag.id or source.owner_ref != actor:
                continue
            available = max(0, source.goods.get(resource_id, 0)
                            - reserve_quantity(world, source.id, resource_id))
            quantity = min(desired, available, headroom // resource.bulk)
            if quantity <= 0:
                continue
            route_ids = (() if source.location_id == bag.location_id else
                         known_supply_path(world, headquarters, source.location_id,
                                           bag.location_id, resource_id))
            if source.location_id != bag.location_id and not route_ids:
                continue
            report_ids = tuple(dict.fromkeys(
                report.event_id for route_id in route_ids
                if (report := world.knowledge.route_report(headquarters, route_id)) is not None
            ))
            materials = source.last_event_ids.get(resource_id)
            context_id = campaign_id or f"staging:{attacker.id}:{attacker.last_event_id}"
            option_id = (f"campaign-ordnance:dispatch:{context_id}:{attacker.last_event_id}:"
                         f"{bag.id}:{resource_id}:{source.id}:{quantity}:{materials}:"
                         f"{'-'.join(route_ids)}:{'-'.join(report_ids)}")
            options.append(CampaignOrdnanceOption(
                id=option_id, actor_ref=actor, campaign_id=campaign_id,
                detachment_id=attacker.id, kind="dispatch", resource_id=resource_id,
                source_stock_id=source.id, quantity=quantity, route_ids=tuple(route_ids),
                route_report_event_ids=report_ids))
    return options


def campaign_ordnance_options(world, actor):
    """Recompose current ammunition transport and artillery-use choices."""
    if (not isinstance(actor, EntityRef) or actor.kind != "polity"
            or not can_actor_act_for(world, actor, actor, "military")
            or not can_actor_act_for(world, actor, actor, "supply")
            or not world.knowledge.knows(actor, "gunpowder")):
        return ()
    headquarters = headquarters_holder(world, actor)
    if headquarters is None or not can_actor_act_for(world, headquarters, actor, "operations"):
        return ()

    options = []
    for campaign in sorted(world.society.siege_campaigns.values(), key=lambda item: item.id):
        if campaign.attacker_ref != actor or campaign.phase != "sieging":
            continue
        parts = _current_parts(world, campaign)
        if parts is None:
            continue
        attacker = parts[0]
        bag = world.economy.stocks.get(campaign_stock_id(attacker.id))
        if (bag is None or bag.owner_ref != actor or bag.location_id != attacker.location_id):
            continue

        options.extend(_dispatch_options(world, actor, headquarters, attacker, bag, campaign.id))
        artillery = bag.goods.get(ARTILLERY_RESOURCE, 0)
        powder = bag.goods.get(POWDER_RESOURCE, 0)
        knowledge = next((item for item in world.knowledge.technologies.values()
                          if item.owner_ref == actor and item.technology_id == "gunpowder"), None)
        if (artillery > 0 and powder > 0 and knowledge is not None
                and campaign.garrison_endurance > 0 and not _has_bombarded_today(world, campaign.id)):
            options.append(CampaignOrdnanceOption(
                id=(f"campaign-ordnance:bombard:{campaign.id}:{campaign.last_event_id}:"
                    f"{attacker.last_event_id}:{bag.last_event_ids.get(ARTILLERY_RESOURCE)}:"
                    f"{bag.last_event_ids.get(POWDER_RESOURCE)}:{world.clock.absolute_day}"),
                actor_ref=actor, campaign_id=campaign.id, detachment_id=attacker.id, kind="bombard"))

    # An invading column can make a current, independent decision to
    # pre-position researched equipment before investing the settlement. Once
    # investment closes the entrances, only equipment already in its bag can
    # reach the siege; the owner never bypasses the blockade.
    invested = {item.detachment_id for item in world.society.settlement_investments.values()
                if item.stage == "active"}
    active_campaign_detachments = {item.attacker_detachment_id
                                   for item in world.society.siege_campaigns.values()
                                   if item.phase == "sieging"}
    for attacker in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if (attacker.owner_ref != actor or attacker.stage != "present"
                or attacker.destination_id != attacker.location_id or attacker.id in invested
                or attacker.id in active_campaign_detachments):
            continue
        bag = world.economy.stocks.get(campaign_stock_id(attacker.id))
        if bag is None or bag.owner_ref != actor or bag.location_id != attacker.location_id:
            continue
        options.extend(_dispatch_options(world, actor, headquarters, attacker, bag, None))
    return tuple(options)


def _decision_for_option(world, actor, option, decision_event_id):
    action = DISPATCH_ACTION if option.kind == "dispatch" else BOMBARD_ACTION
    decision, decided_by = force_decision(world, decision_event_id, action)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("campaign ordnance has the wrong current actor decision")
    return decision


def _dispatch_in_place(world, actor, option_id, decision_event_id):
    option = next((item for item in campaign_ordnance_options(world, actor) if item.id == option_id), None)
    if option is None or option.kind != "dispatch":
        raise ValueError("campaign ordnance dispatch option is stale or unknown")
    decision = _decision_for_option(world, actor, option, decision_event_id)
    require_authority(world, actor, "supply")
    attacker = world.society.detachments.get(option.detachment_id)
    campaign = world.society.siege_campaigns.get(option.campaign_id) if option.campaign_id else None
    if attacker is None or (campaign is not None and
                            (campaign.attacker_detachment_id != attacker.id
                             or campaign.phase != "sieging" or _current_parts(world, campaign) is None)):
        raise ValueError("campaign ordnance detachment is no longer active")
    if campaign is None and (
            attacker.stage != "present" or attacker.destination_id != attacker.location_id
            or any(item.detachment_id == attacker.id and item.stage == "active"
                   for item in world.society.settlement_investments.values())):
        raise ValueError("campaign ordnance staging window has closed")
    destination = world.economy.stocks[campaign_stock_id(attacker.id)]
    source = world.economy.stocks[option.source_stock_id]
    if (source.owner_ref != actor or destination.owner_ref != actor
            or destination.location_id != attacker.location_id
            or source.goods.get(option.resource_id, 0) < option.quantity):
        raise ValueError("campaign ordnance stock or location changed")
    authorship = {"decision_event_id": decision.id,
                  "actor_ref": decision.decision["actor_ref"],
                  "selected_affordance_id": decision.decision["selected_affordance_id"]}
    return open_order(
        world, source.id, destination.id, option.resource_id, option.quantity, option.route_ids,
        decision_ids=(decision.id,),
        cause_ids=_causes(campaign.last_event_id if campaign is not None else None,
                          attacker.last_event_id,
                          source.last_event_ids.get(option.resource_id),
                          *option.route_report_event_ids),
        causal_origin=CausalOrigin.ACTOR_DECISION, causal_payload=authorship,
    )


def _bombard_in_place(world, actor, option_id, decision_event_id):
    option = next((item for item in campaign_ordnance_options(world, actor) if item.id == option_id), None)
    if option is None or option.kind != "bombard":
        raise ValueError("siege bombardment option is stale or unknown")
    decision = _decision_for_option(world, actor, option, decision_event_id)
    require_authority(world, actor, "military")
    if option.campaign_id is None:
        raise ValueError("siege bombardment requires an active campaign")
    campaign = world.society.siege_campaigns[option.campaign_id]
    parts = _current_parts(world, campaign)
    knowledge = next((item for item in world.knowledge.technologies.values()
                      if item.owner_ref == actor and item.technology_id == "gunpowder"), None)
    if parts is None or knowledge is None or _has_bombarded_today(world, campaign.id):
        raise ValueError("siege bombardment is no longer materially possible")
    attacker, garrison, _investment, defender = parts
    bag = world.economy.stocks.get(campaign_stock_id(attacker.id))
    if (bag is None or bag.owner_ref != actor or bag.location_id != attacker.location_id
            or bag.goods.get(ARTILLERY_RESOURCE, 0) < 1
            or bag.goods.get(POWDER_RESOURCE, 0) < 1):
        raise ValueError("siege bombardment requires a co-located artillery piece and powder")

    endurance = max(0, campaign.garrison_endurance - GARRISON_ENDURANCE_PER_ROUND)
    breached = endurance == 0
    powder_before = bag.goods[POWDER_RESOURCE]
    deltas = [
        _delta("stock", bag.id, POWDER_RESOURCE, powder_before, powder_before - 1),
        _delta("siege_campaign", campaign.id, "garrison_endurance",
               campaign.garrison_endurance, endurance),
    ]
    if breached:
        deltas.extend((
            _delta("siege_campaign", campaign.id, "phase", campaign.phase, "breached"),
            _delta("siege_campaign", campaign.id, "next_progress_day", campaign.next_progress_day, None),
        ))
    event = record_event(
        world, "siege_campaign_breached" if breached else "siege_artillery_fired",
        "A peça de cerco disparou; a pólvora foi consumida e a resistência material caiu.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                        "selected_affordance_id": option.id, "campaign_id": campaign.id,
                        "artillery_resource_id": ARTILLERY_RESOURCE,
                        "powder_resource_id": POWDER_RESOURCE,
                        "endurance_loss": min(GARRISON_ENDURANCE_PER_ROUND,
                                               campaign.garrison_endurance)},
        deltas=tuple(deltas),
        cause_ids=_causes(decision.id, campaign.last_event_id, attacker.last_event_id,
                          garrison.last_event_id, defender.last_event_id,
                          bag.last_event_ids.get(ARTILLERY_RESOURCE),
                          bag.last_event_ids.get(POWDER_RESOURCE), knowledge.event_id),
    )
    world.economy.stocks[bag.id] = bag.model_copy(update={
        "goods": {**bag.goods, POWDER_RESOURCE: powder_before - 1},
        "last_event_ids": {**bag.last_event_ids, POWDER_RESOURCE: event.id},
    })
    world.society.siege_campaigns[campaign.id] = campaign.model_copy(update={
        "garrison_endurance": endurance,
        "phase": "breached" if breached else campaign.phase,
        "next_progress_day": None if breached else campaign.next_progress_day,
        "last_event_id": event.id,
    })
    if breached:
        from .force import collapse_garrison_for_siege
        from .settlement_intelligence import refresh_existing_local_settlement_reports

        world.agenda.cancel(campaign.id)
        collapse_garrison_for_siege(world, garrison.id, campaign_event_id=event.id)
        refresh_existing_local_settlement_reports(world, campaign.settlement_id,
                                                 cause_event_ids=(event.id,))
    _schedule_campaign_contact_reviews(world, campaign, event)
    return event


def execute_campaign_ordnance_option(world, actor, option_id, decision_event_id):
    """Run one current shipment or bombardment in the shared material boundary."""
    current = next((item for item in campaign_ordnance_options(world, actor) if item.id == option_id), None)
    if current is None:
        raise ValueError("campaign ordnance option is stale or unknown")
    operation = _dispatch_in_place if current.kind == "dispatch" else _bombard_in_place
    return execute_material(world, operation, actor, option_id, decision_event_id)


__all__ = ["DISPATCH_ACTION", "BOMBARD_ACTION", "CampaignOrdnanceOption",
           "campaign_ordnance_options", "execute_campaign_ordnance_option"]
