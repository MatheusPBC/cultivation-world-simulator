"""Formation and explicit escalation of bounded civic movements.

Movements reserve participants from existing cohorts and record a named leader.
An explicit rebellion declaration only records organized contestation and
pressure; it grants no authority, territory or automatic victory.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.classes.society.movement import CivicMovement

from .civic_protest import _event, _own_report
from .economy import _apply_stock, _causes, _delta
from .events import record_event

MOVEMENT_ACTION = "form_civic_movement"
MOVEMENT_MIN_UNREST = 650
MEMBER_MIN_UNREST = 450
MOVEMENT_MIN_PARTICIPANTS = 5
CATALYST_MAX_AGE = 45
MOVEMENT_MIN_DAYS = 3
REBELLION_ACTION = "declare_civic_rebellion"
REBELLION_MIN_UNREST = 800
REVOLUTION_ACTION = "declare_civic_revolution"
REVOLUTION_MIN_UNREST = 900
SUPPRESS_REBELLION_ACTION = "suppress_civic_rebellion"
OFFER_NEGOTIATION_ACTION = "offer_civic_negotiation"


@dataclass(frozen=True)
class CivicMovementOption:
    id: Identity
    initiator_group_id: Identity
    settlement_id: Identity
    member_group_ids: tuple[Identity, ...]
    participants_by_group: dict[Identity, int]
    leader_character_id: Identity
    report_event_ids: tuple[Identity, ...]
    catalyst_event_id: Identity

    def decision(self):
        return {
            "action": MOVEMENT_ACTION,
            "actor_ref": EntityRef("population_group", self.initiator_group_id).to_dict(),
            "selected_affordance_id": self.id,
        }


@dataclass(frozen=True)
class CivicMovementTerminalOption:
    id: Identity
    movement_id: Identity
    actor_group_id: Identity
    action: str = "dissolve_civic_movement"

    def decision(self):
        return {"action": self.action,
                "actor_ref": EntityRef("population_group", self.actor_group_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CivicRebellionOption:
    id: Identity
    movement_id: Identity
    actor_group_id: Identity
    settlement_id: Identity
    report_event_id: Identity
    mobilization_event_id: Identity

    def decision(self):
        return {"action": REBELLION_ACTION,
                "actor_ref": EntityRef("population_group", self.actor_group_id).to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CivicRebellionResponseOption:
    id: Identity
    movement_id: Identity
    actor_ref: EntityRef
    report_event_id: Identity
    action: str
    negotiation_stock_id: Identity | None = None
    negotiation_food: int = 0
    negotiation_stock_event_id: Identity | None = None

    def decision(self):
        return {"action": self.action,
                "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


@dataclass(frozen=True)
class CivicRevolutionOption:
    id: Identity
    movement_id: Identity
    actor_group_id: Identity
    settlement_id: Identity
    report_event_id: Identity
    rebellion_event_id: Identity
    mobilization_event_id: Identity

    def decision(self):
        return {"action": REVOLUTION_ACTION,
                "actor_ref": EntityRef("population_group", self.actor_group_id).to_dict(),
                "selected_affordance_id": self.id}


def _recent_catalyst(world, settlement_id):
    candidates = []
    for protest in world.society.civic_protests.values():
        if protest.settlement_id != settlement_id:
            continue
        event = _event(world, protest.last_event_id)
        if event is None or event.event_type not in {"civic_protest_refused", "civic_protest_dissolved",
                                                     "civic_protest_lapsed"}:
            continue
        if world.clock.absolute_day - event.day <= CATALYST_MAX_AGE:
            candidates.append(event)
    return max(candidates, key=lambda event: (event.day, event.id), default=None)


def _leader(world, group_id, settlement_id):
    return next((character for character in sorted(world.society.characters.values(), key=lambda item: item.id)
                 if character.population_group_id == group_id
                 and character.location_id == settlement_id
                 and character.death_day is None), None)


def civic_movement_options(world, group_id):
    current = _own_report(world, group_id)
    if current is None:
        return ()
    group, report = current
    if (report.unrest < MOVEMENT_MIN_UNREST
            or world.society.available_count(group.id) < MOVEMENT_MIN_PARTICIPANTS
            or any(item.stage == "active" and item.settlement_id == group.settlement_id
                   for item in world.society.civic_movements.values())):
        return ()
    catalyst = _recent_catalyst(world, group.settlement_id)
    leader = _leader(world, group.id, group.settlement_id)
    if catalyst is None or leader is None:
        return ()

    members = []
    reports = []
    for candidate in sorted(world.society.population.values(), key=lambda item: item.id):
        if candidate.settlement_id != group.settlement_id:
            continue
        own = _own_report(world, candidate.id)
        if (own is None or own[1].unrest < MEMBER_MIN_UNREST
                or world.society.available_count(candidate.id) < MOVEMENT_MIN_PARTICIPANTS):
            continue
        members.append(candidate)
        reports.append(own[1])
    if len(members) < 2 or group.id not in {item.id for item in members}:
        return ()
    participants = {
        item.id: min(world.society.available_count(item.id),
                     max(MOVEMENT_MIN_PARTICIPANTS, item.count // 20))
        for item in members
    }
    if any(value < MOVEMENT_MIN_PARTICIPANTS for value in participants.values()):
        return ()
    report_ids = tuple(report.event_id for report in reports)
    option_id = (f"civic-movement:{group.id}:{group.settlement_id}:"
                 f"{catalyst.id}:{':'.join(report_ids)}")
    return (CivicMovementOption(id=option_id, initiator_group_id=group.id,
                                settlement_id=group.settlement_id,
                                member_group_ids=tuple(item.id for item in members),
                                participants_by_group=participants,
                                leader_character_id=leader.id,
                                report_event_ids=report_ids,
                                catalyst_event_id=catalyst.id),)


def _decision(world, decision_event_id, action=MOVEMENT_ACTION):
    decision = _event(world, decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != action
            or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("civic movement requires a current actor decision")
    return decision, EntityRef.from_dict(decision.decision["actor_ref"])


def civic_rebellion_options(world, group_id):
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        if movement.stage != "active" or movement.started_day + MOVEMENT_MIN_DAYS > world.clock.absolute_day:
            continue
        leader = _leader(world, group_id, movement.settlement_id)
        if leader is None or leader.population_group_id != group_id or leader.id != movement.leader_character_id:
            continue
        current = _own_report(world, group_id)
        if current is None or current[1].unrest < REBELLION_MIN_UNREST:
            continue
        mobilization = next((strike for strike in sorted(world.society.civic_strikes.values(), key=lambda item: item.id)
                             if strike.movement_id == movement.id and strike.stage in {"active", "completed"}), None)
        if mobilization is None:
            continue
        option_id = f"civic-rebellion:{movement.id}:{movement.last_event_id}:{current[1].event_id}:{mobilization.last_event_id}"
        options.append(CivicRebellionOption(id=option_id, movement_id=movement.id,
                                            actor_group_id=group_id,
                                            settlement_id=movement.settlement_id,
                                            report_event_id=current[1].event_id,
                                            mobilization_event_id=mobilization.last_event_id))
    return tuple(options)


def civic_revolution_options(world, group_id):
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        if movement.stage != "rebellion" or movement.started_day + MOVEMENT_MIN_DAYS > world.clock.absolute_day:
            continue
        leader = _leader(world, group_id, movement.settlement_id)
        current = _own_report(world, group_id)
        if (leader is None or leader.id != movement.leader_character_id or current is None
                or current[1].unrest < REVOLUTION_MIN_UNREST):
            continue
        rebellion_event = _event(world, movement.last_event_id)
        mobilization = next((strike for strike in sorted(world.society.civic_strikes.values(), key=lambda item: item.id)
                             if strike.movement_id == movement.id and strike.stage == "completed"), None)
        if rebellion_event is None or rebellion_event.event_type != "civic_rebellion_declared" or mobilization is None:
            continue
        option_id = (f"civic-revolution:{movement.id}:{movement.last_event_id}:"
                     f"{current[1].event_id}:{mobilization.last_event_id}")
        options.append(CivicRevolutionOption(id=option_id, movement_id=movement.id,
                                             actor_group_id=group_id, settlement_id=movement.settlement_id,
                                             report_event_id=current[1].event_id,
                                             rebellion_event_id=rebellion_event.id,
                                             mobilization_event_id=mobilization.last_event_id))
    return tuple(options)


def civic_movement_dissolve_options(world, group_id):
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        if (movement.stage not in {"active", "negotiating"}
                or movement.started_day + MOVEMENT_MIN_DAYS > world.clock.absolute_day
                or movement.leader_character_id not in world.society.characters):
            continue
        if any(strike.stage == "active" and strike.movement_id == movement.id
               for strike in world.society.civic_strikes.values()):
            continue
        leader = world.society.characters[movement.leader_character_id]
        if leader.population_group_id != group_id or leader.location_id != movement.settlement_id:
            continue
        options.append(CivicMovementTerminalOption(
            id=f"civic-movement-dissolve:{movement.id}:{movement.last_event_id}",
            movement_id=movement.id, actor_group_id=group_id,
            action="accept_civic_negotiation" if movement.stage == "negotiating" else "dissolve_civic_movement"))
    return tuple(options)


def civic_rebellion_response_options(world, actor):
    if (not isinstance(actor, EntityRef) or actor.kind != "polity"
            or not can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        settlement = world.society.settlements.get(movement.settlement_id)
        report = world.knowledge.settlement_report(actor, movement.settlement_id)
        if (movement.stage not in {"active", "rebellion", "revolution"} or settlement is None
                or settlement.administrator_id != actor.id or report is None
                or report.observed_day != world.clock.absolute_day):
            continue
        responses = ((OFFER_NEGOTIATION_ACTION, "negotiate"),) if movement.stage == "active" else (
            (SUPPRESS_REBELLION_ACTION, "suppress"), (OFFER_NEGOTIATION_ACTION, "negotiate"))
        for action, suffix in responses:
            stock_id = None
            food = 0
            stock_event_id = None
            if action == OFFER_NEGOTIATION_ACTION:
                need = world.economy.needs.get(movement.settlement_id)
                candidate_stock = (world.economy.stocks.get(need.stock_id)
                                   if need is not None else None)
                if (candidate_stock is not None and candidate_stock.owner_ref == actor):
                    stock_id = candidate_stock.id
                    food = min(max(0, need.missing_food), 20,
                               max(0, candidate_stock.goods.get("food", 0)))
                    stock_event_id = candidate_stock.last_event_ids.get("food")
            options.append(CivicRebellionResponseOption(
                id=(f"civic-rebellion-{suffix}:{movement.id}:{movement.last_event_id}:{report.event_id}:"
                    f"{stock_id or 'none'}:{food}:{stock_event_id or 'none'}"),
                movement_id=movement.id, actor_ref=actor, report_event_id=report.event_id,
                action=action, negotiation_stock_id=stock_id, negotiation_food=food,
                negotiation_stock_event_id=stock_event_id))
    return tuple(options)


def form_civic_movement(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_movement_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic movement option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic movement has the wrong decision")
    if any(item.stage == "active" and item.settlement_id == option.settlement_id
           for item in candidate.society.civic_movements.values()):
        raise ValueError("settlement already has an active civic movement")
    for member_id, count in option.participants_by_group.items():
        if candidate.society.available_count(member_id) < count:
            raise ValueError("civic movement participants are no longer available")
    movement_id = f"civic-movement:{decision.id}"
    event = record_event(
        candidate, "civic_movement_formed",
        "Grupos locais formaram um movimento cívico com liderança nomeada.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(
            _delta("civic_movement", movement_id, "stage", None, "active"),
            _delta("civic_movement", movement_id, "leader_character_id", None, option.leader_character_id),
            *(_delta("civic_movement", movement_id, f"participants:{group_id}", 0, count)
              for group_id, count in sorted(option.participants_by_group.items())),
        ),
        cause_ids=_causes(decision.id, option.catalyst_event_id, *option.report_event_ids),
    )
    candidate.society.civic_movements[movement_id] = CivicMovement(
        id=movement_id, initiator_group_id=option.initiator_group_id,
        settlement_id=option.settlement_id, member_group_ids=option.member_group_ids,
        participants_by_group=dict(option.participants_by_group),
        leader_character_id=option.leader_character_id, started_day=candidate.clock.absolute_day,
        report_event_ids=option.report_event_ids, catalyst_event_id=option.catalyst_event_id,
        decision_event_id=decision.id, last_event_id=event.id,
    )
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return candidate.society.civic_movements[movement_id]


def dissolve_civic_movement(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_movement_dissolve_options(candidate, group_id)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("civic movement dissolution option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id, option.action)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic movement dissolution has the wrong decision")
    movement = candidate.society.civic_movements[option.movement_id]
    event = record_event(
        candidate, "civic_movement_dissolved",
        "A liderança encerrou o movimento cívico e liberou seus participantes.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(_delta("civic_movement", movement.id, "stage", movement.stage, "dissolved"),
                *(_delta("civic_movement", movement.id, f"participants:{member_id}", count, 0)
                  for member_id, count in sorted(movement.participants_by_group.items()))),
        cause_ids=_causes(decision.id, movement.last_event_id),
    )
    candidate.society.civic_movements[movement.id] = movement.model_copy(
        update={"stage": "dissolved", "last_event_id": event.id})
    if movement.stage == "negotiating":
        resolution_event_id = event.id
        if movement.negotiation_food > 0:
            stock = candidate.economy.stocks.get(movement.negotiation_stock_id)
            settlement = candidate.society.settlements.get(movement.settlement_id)
            if (stock is None or settlement is None or settlement.administrator_id != stock.owner_ref.id
                    or stock.goods.get("food", 0) < movement.negotiation_food):
                raise ValueError("civic negotiation material offer is stale")
            goods = dict(stock.goods)
            goods["food"] = goods.get("food", 0) - movement.negotiation_food
            food_event = _apply_stock(
                candidate, stock, goods, "civic_negotiation_food_delivered",
                "A administração entregou alimento como termo material da negociação cívica.",
                cause_ids=_causes(event.id, movement.negotiation_offer_event_id,
                                  stock.last_event_ids.get("food")))
            resolution_event_id = food_event.id
        from .economy import apply_civic_resolution_relief
        apply_civic_resolution_relief(candidate, movement.settlement_id,
                                      resolution_event_id=resolution_event_id, relief=60)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return candidate.society.civic_movements[movement.id]


def declare_civic_rebellion(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_rebellion_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic rebellion option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id, REBELLION_ACTION)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic rebellion has the wrong decision")
    movement = candidate.society.civic_movements.get(option.movement_id)
    if movement is None or movement.stage != "active":
        raise ValueError("civic movement is no longer able to declare rebellion")
    event = record_event(
        candidate, "civic_rebellion_declared",
        "Um movimento cívico organizado declarou uma rebelião contra a administração local.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(_delta("civic_movement", movement.id, "stage", "active", "rebellion"),),
        cause_ids=_causes(decision.id, movement.last_event_id,
                          option.report_event_id, option.mobilization_event_id),
    )
    candidate.society.civic_movements[movement.id] = movement.model_copy(
        update={"stage": "rebellion", "last_event_id": event.id})
    from .economy import apply_civic_rebellion_pressure
    apply_civic_rebellion_pressure(candidate, movement.settlement_id, rebellion_event_id=event.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return candidate.society.civic_movements[movement.id]


def declare_civic_revolution(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_revolution_options(candidate, group_id) if item.id == option_id), None)
    if option is None:
        raise ValueError("civic revolution option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id, REVOLUTION_ACTION)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("civic revolution has the wrong decision")
    movement = candidate.society.civic_movements.get(option.movement_id)
    if movement is None or movement.stage != "rebellion":
        raise ValueError("civic movement is no longer able to declare revolution")
    event = record_event(
        candidate, "civic_revolution_declared",
        "Uma rebelião organizada declarou uma revolução sob pressão material persistente.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(_delta("civic_movement", movement.id, "stage", "rebellion", "revolution"),),
        cause_ids=_causes(decision.id, movement.last_event_id,
                          option.report_event_id, option.mobilization_event_id),
    )
    candidate.society.civic_movements[movement.id] = movement.model_copy(
        update={"stage": "revolution", "last_event_id": event.id})
    from .economy import apply_civic_revolution_pressure
    apply_civic_revolution_pressure(candidate, movement.settlement_id, revolution_event_id=event.id)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return candidate.society.civic_movements[movement.id]


def respond_civic_rebellion(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_rebellion_response_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("civic rebellion response option is stale or unknown")
    decision, decision_actor = _decision(candidate, decision_event_id, option.action)
    if decision_actor != actor or decision.decision != option.decision():
        raise ValueError("civic rebellion suppression has the wrong decision")
    movement = candidate.society.civic_movements.get(option.movement_id)
    if movement is None or movement.stage not in {"active", "rebellion", "revolution"}:
        raise ValueError("civic movement is no longer responding")
    if option.action == SUPPRESS_REBELLION_ACTION and movement.stage == "active":
        raise ValueError("an active movement can only receive a negotiation offer")
    next_stage = "negotiating" if option.action == OFFER_NEGOTIATION_ACTION else "suppressed"
    event_type = "civic_negotiation_offered" if next_stage == "negotiating" else "civic_movement_suppressed"
    deltas = (_delta("civic_movement", movement.id, "stage", movement.stage, next_stage),)
    if next_stage == "suppressed":
        deltas += tuple(_delta("civic_movement", movement.id, f"participants:{member_id}", count, 0)
                        for member_id, count in sorted(movement.participants_by_group.items()))
    offer_deltas = ()
    offer_causes = ()
    if option.action == OFFER_NEGOTIATION_ACTION and option.negotiation_food > 0:
        offer_deltas = (
            _delta("civic_movement", movement.id, "negotiation_stock_id", None, option.negotiation_stock_id),
            _delta("civic_movement", movement.id, "negotiation_food", 0, option.negotiation_food),
        )
        offer_causes = tuple(item for item in (option.negotiation_stock_event_id,) if item)
    suppression_pressure = None
    if option.action == SUPPRESS_REBELLION_ACTION:
        from .economy import apply_civic_suppression_pressure
        suppression_pressure = apply_civic_suppression_pressure(
            candidate, movement.settlement_id, suppression_event_id=decision.id)
    event = record_event(
        candidate, event_type,
        ("A administração ofereceu uma negociação ao movimento cívico organizado."
         if next_stage == "negotiating" else
         "A administração suprimiu uma rebelião cívica organizada sob sua autoridade militar."),
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        deltas=(*deltas, *offer_deltas),
        cause_ids=_causes(decision.id, movement.last_event_id, option.report_event_id,
                          *(offer_causes or (() if suppression_pressure is None else (suppression_pressure.id,)))),
    )
    candidate.society.civic_movements[movement.id] = movement.model_copy(
        update={"stage": next_stage, "last_event_id": event.id,
                "negotiation_stock_id": (option.negotiation_stock_id
                                          if option.action == OFFER_NEGOTIATION_ACTION
                                          and option.negotiation_food > 0 else None),
                "negotiation_food": (option.negotiation_food
                                      if option.action == OFFER_NEGOTIATION_ACTION else 0),
                "negotiation_offer_event_id": (event.id
                                                if option.action == OFFER_NEGOTIATION_ACTION
                                                and option.negotiation_food > 0 else None)})
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return candidate.society.civic_movements[movement.id]


def suppress_civic_rebellion(world, actor, option_id, decision_event_id):
    option = next((item for item in civic_rebellion_response_options(world, actor)
                   if item.id == option_id and item.action == SUPPRESS_REBELLION_ACTION), None)
    if option is None:
        raise ValueError("civic rebellion suppression option is stale or unknown")
    return respond_civic_rebellion(world, actor, option.id, decision_event_id)


__all__ = ["CivicMovementOption", "CivicMovementTerminalOption", "CivicRebellionOption", "CivicRevolutionOption",
           "CivicRebellionResponseOption", "MOVEMENT_ACTION", "REBELLION_ACTION",
           "SUPPRESS_REBELLION_ACTION", "OFFER_NEGOTIATION_ACTION", "REVOLUTION_ACTION",
           "civic_rebellion_options", "civic_revolution_options", "civic_rebellion_response_options",
           "declare_civic_rebellion", "declare_civic_revolution", "respond_civic_rebellion",
           "suppress_civic_rebellion",
           "civic_movement_options", "civic_movement_dissolve_options",
           "form_civic_movement", "dissolve_civic_movement"]
