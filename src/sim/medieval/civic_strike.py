"""A bounded general strike built from an existing civic movement."""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity
from src.classes.society.strike import CivicStrike
from src.systems.calendar_agenda import ScheduledSituation

from .civic_protest import _event, _own_report
from .civic_movement import MOVEMENT_MIN_DAYS
from .economy import _causes, _delta
from .events import record_event

STRIKE_ACTION = "start_general_strike"
STRIKE_KIND = "civic_general_strike"
STRIKE_DAYS = 3
STRIKE_MIN_UNREST = 600
STRIKE_MIN_PARTICIPANTS = 5


@dataclass(frozen=True)
class CivicStrikeOption:
    id: Identity
    actor_group_id: Identity
    movement_id: Identity
    settlement_id: Identity
    participants_by_group: dict[Identity, int]
    report_event_ids: tuple[Identity, ...]

    def decision(self):
        return {
            "action": STRIKE_ACTION,
            "actor_ref": EntityRef("population_group", self.actor_group_id).to_dict(),
            "selected_affordance_id": self.id,
        }

def _leader_group(world, movement):
    leader = world.society.characters.get(movement.leader_character_id)
    if (leader is None or leader.death_day is not None
            or leader.location_id != movement.settlement_id):
        return None
    return leader.population_group_id


def civic_general_strike_options(world, group_id):
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        if movement.stage != "active" or movement.started_day + MOVEMENT_MIN_DAYS > world.clock.absolute_day:
            continue
        if _leader_group(world, movement) != group_id:
            continue
        if any(item.stage == "active" and item.movement_id == movement.id
               for item in world.society.civic_strikes.values()):
            continue
        report_ids = []
        participants = {}
        valid = True
        for member_id in movement.member_group_ids:
            own = _own_report(world, member_id)
            if own is None or own[1].unrest < STRIKE_MIN_UNREST:
                valid = False
                break
            report_ids.append(own[1].event_id)
            available = world.society.available_count(member_id)
            count = min(available, max(STRIKE_MIN_PARTICIPANTS, world.society.population[member_id].count // 10))
            if count < STRIKE_MIN_PARTICIPANTS:
                valid = False
                break
            participants[member_id] = count
        if not valid or len(participants) < 2:
            continue
        option_id = f"civic-strike:{movement.id}:{movement.last_event_id}:{':'.join(report_ids)}"
        option = CivicStrikeOption(id=option_id, actor_group_id=group_id, movement_id=movement.id,
                                   settlement_id=movement.settlement_id,
                                   participants_by_group=participants,
                                   report_event_ids=tuple(report_ids))
        options.append(option)
    return tuple(options)


def _decision(world, decision_event_id):
    decision = _event(world, decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != STRIKE_ACTION
            or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("general strike requires a current actor decision")
    return decision, EntityRef.from_dict(decision.decision["actor_ref"])


def start_general_strike(world, group_id, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_general_strike_options(candidate, group_id)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("general strike option is stale or unknown")
    decision, actor = _decision(candidate, decision_event_id)
    if actor != EntityRef("population_group", group_id) or decision.decision != option.decision():
        raise ValueError("general strike has the wrong decision")
    movement = candidate.society.civic_movements.get(option.movement_id)
    if movement is None or movement.stage != "active":
        raise ValueError("general strike movement is no longer active")
    for member_id, count in option.participants_by_group.items():
        if candidate.society.available_count(member_id) < count:
            raise ValueError("general strike participants are no longer available")
    strike_id = f"civic-strike:{decision.id}"
    event = record_event(
        candidate, "civic_general_strike_started",
        "Um movimento cívico iniciou uma greve geral limitada por três dias.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                        "selected_affordance_id": option.id, "movement_id": movement.id},
        deltas=(
            _delta("civic_strike", strike_id, "stage", None, "active"),
            *(_delta("civic_strike", strike_id, f"participants:{member_id}", 0, count)
              for member_id, count in sorted(option.participants_by_group.items())),
        ),
        cause_ids=_causes(decision.id, movement.last_event_id, *option.report_event_ids),
    )
    strike = CivicStrike(
        id=strike_id, movement_id=movement.id, settlement_id=movement.settlement_id,
        participants_by_group=dict(option.participants_by_group),
        started_day=candidate.clock.absolute_day, due_day=candidate.clock.absolute_day + STRIKE_DAYS,
        decision_event_id=decision.id, last_event_id=event.id,
    )
    candidate.society.civic_strikes[strike_id] = strike
    candidate.agenda.schedule(ScheduledSituation(strike_id, STRIKE_KIND, strike.due_day))
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return strike


def resolve_civic_strikes(world, situations):
    for situation in situations:
        strike = world.society.civic_strikes.get(situation.id)
        if strike is None or strike.stage != "active":
            continue
        if situation.due_day != world.clock.absolute_day or situation.kind != STRIKE_KIND:
            raise ValueError("invalid civic strike schedule")
        event = record_event(
            world, "civic_general_strike_ended",
            "A greve geral terminou e liberou os trabalhadores reservados.",
            fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.DETERMINISTIC,
            deltas=(_delta("civic_strike", strike.id, "stage", "active", "completed"),
                    *(_delta("civic_strike", strike.id, f"participants:{member_id}", count, 0)
                      for member_id, count in sorted(strike.participants_by_group.items()))),
            cause_ids=_causes(strike.last_event_id),
        )
        world.society.civic_strikes[strike.id] = strike.model_copy(
            update={"stage": "completed", "last_event_id": event.id})


__all__ = ["CivicStrikeOption", "STRIKE_ACTION", "STRIKE_KIND",
           "civic_general_strike_options", "start_general_strike", "resolve_civic_strikes"]
