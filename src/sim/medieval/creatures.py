"""The River Lume drake: one sentient neighbour with material limits.

There is no monster engine here, no spawn, no attack, no loot and no battle.
The drake only ever learns what physically crossed its river, and every step it
takes is an explicit decision over engine-enumerated options. Its single
material power is to close the crossing it inhabits — a Map change it may undo,
and only its own.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.environment.creature import CreatureDemand
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.knowledge import creature_tribute_notice_id, creature_damage_notice_id
from src.classes.governance.models import CreatureTributeNotice, CreatureDamageNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .economy import _apply_stock, _causes, _delta
from .events import record_event

MAINTAIN_ACTION = "creature_maintain"
REQUEST_ACTION = "creature_request_tribute"
WITHDRAW_ACTION = "creature_withdraw"
RESTRICT_ACTION = "creature_restrict_passage"
DAMAGE_ACTION = "creature_damage_site"
TRIBUTE_ACTION = "offer_creature_tribute"
CONDITION_PER_CROSSING = 40
CONDITION_PER_TRIBUTE = 200
CONDITION_PER_SITE_DAMAGE = 100
SITE_DAMAGE = 0.10
DEMAND_DAYS = 10


@dataclass(frozen=True)
class CreatureOption:
    """Transient option of one creature; a decider only selects this ID."""
    id: Identity
    creature_id: Identity
    kind: str
    route_id: Identity | None = None
    demand_id: Identity | None = None
    site_id: Identity | None = None
    food: int = 0

    def decision(self):
        return {"action": {"maintain": MAINTAIN_ACTION, "request": REQUEST_ACTION,
                            "withdraw": WITHDRAW_ACTION, "restrict": RESTRICT_ACTION,
                            "damage": DAMAGE_ACTION}[self.kind],
                "actor_ref": EntityRef("creature", self.creature_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class TributeOption:
    id: Identity
    actor_ref: EntityRef
    demand_id: Identity
    stock_id: Identity
    food: int

    def decision(self):
        return {"action": TRIBUTE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    if not isinstance(event_id, str) or not event_id.startswith("event:"):
        return None
    position = event_id.partition(":")[2]
    if not position.isdecimal() or not 1 <= int(position) <= len(world.events):
        return None
    event = world.events[int(position) - 1]
    return event if event.id == event_id else None


def _decision(world, decision_event_id, action):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("creature action requires a current decision")
    return event


def perceive_cargo(world, route_id, cargo_event_id):
    """Only cargo that actually departed across the river is ever perceived.

    The drake reads no stock, plan, authority, force or offer: it sees that
    something crossed, and its own body grows hungrier with the watching.
    """
    perceived = []
    for _, creature in sorted(world.creatures.creatures.items()):
        if route_id not in creature.route_ids:
            continue
        condition = max(0, creature.condition - CONDITION_PER_CROSSING)
        event = record_event(world, "creature_perceived_cargo",
                             f"{creature.name}: uma carga cruzou o rio sob seus olhos.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("creature", creature.id, "condition", creature.condition, condition),
                                     _delta("creature", creature.id, "perceived_crossings",
                                            creature.perceived_crossings, creature.perceived_crossings + 1)),
                             cause_ids=_causes(cargo_event_id, creature.last_event_id))
        world.creatures.creatures[creature.id] = creature.model_copy(update={
            "condition": condition, "perceived_crossings": creature.perceived_crossings + 1,
            "last_perceived_day": world.clock.absolute_day, "last_event_id": event.id})
        # Hunger only earns the creature a dated turn; it demands nothing.
        from .creature_policy import note_perception
        note_perception(world, world.creatures.creatures[creature.id])
        perceived.append(world.creatures.creatures[creature.id])
    return tuple(perceived)


def creature_options(world, creature_id):
    """Compose one concrete turn from the creature's own physical affordances."""
    creature = world.creatures.creatures.get(creature_id)
    if creature is None:
        return ()
    options = []
    base = f"creature:{creature.id}:{creature.last_event_id}"
    options.append(CreatureOption(f"{base}:maintain", creature.id, "maintain"))
    hungry = creature.condition < creature.hunger_threshold
    open_demands = world.creatures.open_demands(creature.id)
    for route_id in creature.route_ids:
        if hungry and not open_demands and creature.restricted_route_id is None:
            options.append(CreatureOption(f"{base}:request:{route_id}", creature.id, "request",
                                          route_id=route_id, food=creature.tribute_food))
        expired = [item for item in world.creatures.demands.values()
                   if item.creature_id == creature.id and item.route_id == route_id
                   and item.stage == "open" and item.due_day <= world.clock.absolute_day]
        if hungry and expired and creature.restricted_route_id is None:
            options.append(CreatureOption(f"{base}:restrict:{route_id}", creature.id, "restrict",
                                          route_id=route_id, demand_id=sorted(item.id for item in expired)[0]))
    if hungry and creature.damaged_site_id is None:
        target = _damage_target(world, creature, expired_demands=tuple(
            item for item in world.creatures.demands.values()
            if item.creature_id == creature.id and item.stage == "open"
            and item.due_day < world.clock.absolute_day))
        if target is not None:
            demand, site = target
            options.append(CreatureOption(
                f"{base}:damage:{demand.id}:{demand.route_id}:{site.id}", creature.id, "damage",
                route_id=demand.route_id, demand_id=demand.id, site_id=site.id))
    if creature.restricted_route_id is not None:
        options.append(CreatureOption(f"{base}:withdraw:{creature.restricted_route_id}", creature.id,
                                      "withdraw", route_id=creature.restricted_route_id))
    return tuple(options)


def _damage_target(world, creature, *, expired_demands):
    """Return the one engine-selected exposed aquatic site, if any.

    This deliberately uses authored topology only.  Site condition, control,
    service, stock and reports never enter the creature's context; an intact
    site is the only runtime filter needed to ensure the action has an effect.
    """
    for demand in sorted(expired_demands, key=lambda item: item.id):
        route = world.map.routes.get(demand.route_id)
        if route is None:
            continue
        for site in sorted(world.map.infrastructure_sites.values(), key=lambda item: item.id):
            if (demand.route_id not in site.route_ids
                    or not set(site.region_ids).intersection(route.endpoint_region_ids)
                    or creature.water_body_id not in site.water_body_ids
                    or site.integrity <= 0.0):
                continue
            return demand, site
    return None


def _endpoint_administrations(world, route_id):
    route = world.map.routes[route_id]
    actors = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        if settlement.region_id in route.endpoint_region_ids and settlement.administrator_id is not None:
            actor = EntityRef("polity", settlement.administrator_id)
            if actor not in actors:
                actors.append(actor)
    return tuple(actors)


def execute_creature_option(world, creature_id, option_id, decision_event_id):
    """One explicit creature decision; nothing here happens by itself."""
    candidate = deepcopy(world)
    option = next((item for item in creature_options(candidate, creature_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("creature option is stale or unknown")
    decision = _decision(candidate, decision_event_id,
                         {"maintain": MAINTAIN_ACTION, "request": REQUEST_ACTION,
                          "withdraw": WITHDRAW_ACTION, "restrict": RESTRICT_ACTION,
                          "damage": DAMAGE_ACTION}[option.kind])
    if decision.decision != option.decision():
        raise ValueError("creature decision does not match its option")
    creature = candidate.creatures.creatures[creature_id]
    if option.kind == "maintain":
        record_event(candidate, "creature_maintained", f"{creature.name}: permaneceu como está.",
                     fact_kind=FactKind.STATE_TRANSITION,
                     deltas=(_delta("creature", creature.id, "condition", creature.condition, creature.condition),),
                     cause_ids=_causes(decision.id, creature.last_event_id))
        candidate.creatures.creatures[creature.id] = creature.model_copy(
            update={"last_event_id": candidate.events[-1].id})
    elif option.kind == "request":
        _demand(candidate, creature, option, decision)
    elif option.kind == "restrict":
        _restrict(candidate, creature, option, decision)
    elif option.kind == "damage":
        _damage_site(candidate, creature, option, decision)
    else:
        _withdraw(candidate, creature, option, decision)
    clear_resolved_damage(candidate)
    candidate.creatures.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.creatures.creatures[creature_id]


def _damage_site(world, creature, option, decision):
    """Apply the fixed creature effect to one currently valid Map site."""
    expired = tuple(item for item in world.creatures.demands.values()
                    if item.creature_id == creature.id and item.stage == "open"
                    and item.due_day < world.clock.absolute_day)
    target = _damage_target(world, creature, expired_demands=expired)
    if target is None or target[0].id != option.demand_id or target[1].id != option.site_id:
        raise ValueError("creature site damage is no longer possible")
    demand, site = target
    before_integrity = site.integrity
    after_integrity = max(0.0, before_integrity - SITE_DAMAGE)
    before_condition = creature.condition
    after_condition = max(0, before_condition - CONDITION_PER_SITE_DAMAGE)
    event_id = f"event:{len(world.events) + 1}"
    event = record_event(
        world, "creature_damaged_site",
        f"{creature.name}: uma passagem aquática sofreu dano material.",
        fact_kind=FactKind.STATE_TRANSITION,
        causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(_delta("site", site.id, "integrity", before_integrity, after_integrity),
                _delta("creature", creature.id, "condition", before_condition, after_condition),
                _delta("creature", creature.id, "damaged_site_id", None, site.id),
                _delta("creature", creature.id, "damage_event_id", None, event_id)),
        cause_ids=_causes(decision.id, demand.last_event_id, creature.last_event_id),
    )
    world.map.update_infrastructure_site_runtime(site.id, integrity=after_integrity, last_event_id=event.id)
    world.creatures.creatures[creature.id] = creature.model_copy(update={
        "condition": after_condition, "damaged_site_id": site.id,
        "damage_event_id": event.id, "last_event_id": event.id})
    _notify_damage_holders(world, demand, site, event)
    from .route_intelligence import refresh_site_reports
    refresh_site_reports(world, site_ids=(site.id,))
    return event


def _notify_damage_holders(world, demand, site, damage_event):
    """Give only existing demand holders a route/site fact, without attribution."""
    holders = sorted({notice.recipient_ref for notice in world.knowledge.creature_tribute_notices.values()
                      if notice.demand_id == demand.id}, key=lambda ref: (ref.kind, ref.id))
    for recipient in holders:
        notice_id = creature_damage_notice_id(demand.id, site.id, recipient)
        notice = CreatureDamageNotice(
            id=notice_id, recipient_ref=recipient, demand_id=demand.id,
            route_id=demand.route_id, site_id=site.id, event_id="pending",
            learned_day=world.clock.absolute_day,
        )
        event = record_event(
            world, "creature_damage_noticed",
            "Uma instalação ligada à passagem observada sofreu dano.",
            fact_kind=FactKind.STATE_TRANSITION,
            deltas=(_delta("creature_damage_notice", notice.id, "observation", None,
                            f"{notice.route_id}:{notice.site_id}"),),
            cause_ids=(damage_event.id,),
        )
        world.knowledge.creature_damage_notices[notice.id] = notice.model_copy(update={"event_id": event.id})


def _damage_demand(world, creature, damage_event):
    """Find the demand that causally opened the one pending damage binding."""
    seen = set()
    stack = [damage_event.id]
    while stack:
        event_id = stack.pop()
        if event_id in seen:
            continue
        seen.add(event_id)
        event = _event(world, event_id)
        if event is None:
            continue
        for demand in world.creatures.demands.values():
            if demand.creature_id != creature.id:
                continue
            if (event.id in {demand.last_event_id, demand.decision_event_id}
                    or any(delta.owner_kind == "creature_demand" and delta.owner_id == demand.id
                           for delta in event.deltas)):
                return demand
        stack.extend(link.cause_event_id for link in event.causal_links)
    return None


def clear_resolved_damage(world):
    """Record an explicit receipt when the demand behind retaliation closes.

    Restoration-based clearing is intentionally left to the monthly repair
    owner.  Demand settlement/expiry is safe to resolve here because the same
    creature executor has just revalidated that transition.
    """
    for creature in tuple(world.creatures.creatures.values()):
        if creature.damage_event_id is None:
            continue
        damage = _event(world, creature.damage_event_id)
        demand = _damage_demand(world, creature, damage) if damage is not None else None
        if damage is None or demand is None or demand.stage == "open":
            continue
        causes = _causes(damage.id, demand.last_event_id, creature.last_event_id)
        event = record_event(
            world, "creature_damage_cleared",
            "A ameaça material deixou de estar vinculada à exigência encerrada.",
            fact_kind=FactKind.STATE_TRANSITION,
            causal_origin=CausalOrigin.DETERMINISTIC,
            deltas=(_delta("creature", creature.id, "damaged_site_id", creature.damaged_site_id, None),
                    _delta("creature", creature.id, "damage_event_id", creature.damage_event_id, None)),
            cause_ids=causes,
        )
        world.creatures.creatures[creature.id] = creature.model_copy(update={
            "damaged_site_id": None, "damage_event_id": None, "last_event_id": event.id})


def _demand(world, creature, option, decision):
    demand_id = f"creature_demand:{decision.id}"
    day = world.clock.absolute_day
    recipients = _endpoint_administrations(world, option.route_id)
    event = record_event(world, "creature_demanded_tribute",
                         f"{creature.name}: exige {option.food} de alimento para manter a passagem.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("creature_demand", demand_id, "stage", None, "open"),),
                         cause_ids=_causes(decision.id, creature.last_event_id, creature.last_event_id))
    demand = CreatureDemand(id=demand_id, creature_id=creature.id, route_id=option.route_id, food=option.food,
                            opened_day=day, due_day=day + DEMAND_DAYS, perception_event_id=creature.last_event_id,
                            decision_event_id=decision.id, last_event_id=event.id)
    world.creatures.demands[demand.id] = demand
    world.creatures.creatures[creature.id] = creature.model_copy(update={"last_event_id": event.id})
    for recipient in recipients:
        notice = CreatureTributeNotice(id=creature_tribute_notice_id(demand.id, recipient), recipient_ref=recipient,
                                       creature_id=creature.id, demand_id=demand.id, route_id=demand.route_id,
                                       food=demand.food, due_day=demand.due_day, event_id=event.id, learned_day=day)
        world.knowledge.creature_tribute_notices[notice.id] = notice
    return demand


def _restrict(world, creature, option, decision):
    route = world.map.routes[option.route_id]
    demand = world.creatures.demands[option.demand_id]
    event = record_event(world, "creature_restricted_route",
                         f"{creature.name}: fechou a passagem até receber o que pediu.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("route", route.id, "enabled", route.enabled, False),
                                 _delta("creature_demand", demand.id, "stage", "open", "expired")),
                         cause_ids=_causes(decision.id, creature.last_event_id, demand.last_event_id))
    world.map.routes[route.id].update_runtime(enabled=False)
    world.creatures.demands[demand.id] = demand.model_copy(update={"stage": "expired", "last_event_id": event.id})
    world.creatures.creatures[creature.id] = creature.model_copy(update={
        "restricted_route_id": route.id, "restriction_event_id": event.id, "last_event_id": event.id})
    return event


def _withdraw(world, creature, option, decision):
    """Undo only this creature's own closure, and only if it still holds."""
    route = world.map.routes[creature.restricted_route_id]
    if route.enabled:
        raise ValueError("the creature has no standing closure to withdraw")
    event = record_event(world, "creature_withdrew",
                         f"{creature.name}: recuou e liberou a passagem.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("route", route.id, "enabled", False, True),),
                         cause_ids=_causes(decision.id, creature.last_event_id, creature.restriction_event_id))
    world.map.routes[route.id].update_runtime(enabled=True)
    world.creatures.creatures[creature.id] = creature.model_copy(update={
        "restricted_route_id": None, "restriction_event_id": None, "last_event_id": event.id})
    return event


def tribute_options(world, actor):
    """Only from one's own notice, own authority and own local food."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "supply"):
        return ()
    day = world.clock.absolute_day
    options = []
    for notice in world.knowledge.creature_tributes_for_actor(actor):
        demand = world.creatures.demands.get(notice.demand_id)
        if demand is None or demand.stage != "open" or demand.due_day < day:
            continue
        for _, stock in sorted(world.economy.stocks.items()):
            if stock.owner_ref != actor or stock.goods.get("food", 0) < notice.food:
                continue
            options.append(TributeOption(f"creature-tribute:{demand.id}:{stock.id}:{notice.food}",
                                         actor, demand.id, stock.id, notice.food))
    return tuple(options)


def offer_creature_tribute(world, actor, option_id, decision_event_id):
    """Exact local food leaves the stock; only the creature's condition grows."""
    candidate = deepcopy(world)
    option = next((item for item in tribute_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("creature tribute option is stale or unknown")
    decision = _decision(candidate, decision_event_id, TRIBUTE_ACTION)
    if decision.decision != option.decision():
        raise ValueError("creature tribute decision does not match its option")
    require_authority(candidate, actor, "supply")
    demand = candidate.creatures.demands[option.demand_id]
    creature = candidate.creatures.creatures[demand.creature_id]
    stock = candidate.economy.stocks[option.stock_id]
    food = stock.goods.get("food", 0)
    if stock.owner_ref != actor or food < demand.food:
        raise ValueError("tribute requires the institution's own local food")
    condition = min(1000, creature.condition + CONDITION_PER_TRIBUTE)
    event = _apply_stock(candidate, stock, {**stock.goods, "food": food - demand.food},
                         "creature_tribute_delivered",
                         f"{creature.name}: recebeu {demand.food} de alimento e manteve a passagem.",
                         extra_deltas=(_delta("creature_demand", demand.id, "stage", "open", "satisfied"),
                                       _delta("creature", creature.id, "condition", creature.condition, condition)),
                         cause_ids=_causes(decision.id, demand.last_event_id, creature.last_event_id))
    candidate.creatures.demands[demand.id] = demand.model_copy(update={
        "stage": "satisfied", "settled_by_ref": actor.to_dict(), "last_event_id": event.id})
    candidate.creatures.creatures[creature.id] = creature.model_copy(update={
        "condition": condition, "last_event_id": event.id})
    clear_resolved_damage(candidate)
    candidate.creatures.validate(candidate)
    candidate.knowledge.validate(candidate)
    candidate.economy.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.creatures.demands[demand.id]
