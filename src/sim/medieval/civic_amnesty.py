"""Formal, actor-decided amnesty after a civic negotiation.

An amnesty is an institutional record, not a rollback: the rebellion and its
breach remain historical facts, while the current settlement relationship can
carry a separate resolved status.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .civic_protest import _event
from .economy import _causes, _delta
from .events import record_event
from src.classes.society.amnesty import CivicAmnesty

AMNESTY_ACTION = "grant_civic_amnesty"


@dataclass(frozen=True)
class CivicAmnestyOption:
    id: Identity
    movement_id: Identity
    settlement_id: Identity
    actor_ref: EntityRef
    report_event_id: Identity
    negotiation_event_id: Identity

    def decision(self):
        return {
            "action": AMNESTY_ACTION,
            "actor_ref": self.actor_ref.to_dict(),
            "selected_affordance_id": self.id,
        }


def civic_amnesty_options(world, actor):
    """Enumerate only amnesties available to the current administrator."""
    if (not isinstance(actor, EntityRef) or actor.kind != "polity"
            or not can_actor_act_for(world, actor, actor, "military")):
        return ()
    options = []
    for movement in sorted(world.society.civic_movements.values(), key=lambda item: item.id):
        settlement = world.society.settlements.get(movement.settlement_id)
        report = world.knowledge.settlement_report(actor, movement.settlement_id)
        last = _event(world, movement.last_event_id)
        if (settlement is None or settlement.administrator_id != actor.id
                or movement.stage != "dissolved"
                or last is None or last.event_type != "civic_movement_dissolved"
                or report is None or report.observed_day != world.clock.absolute_day
                or movement.id in {item.movement_id for item in world.society.civic_amnesties.values()}):
            continue
        options.append(CivicAmnestyOption(
            id=f"civic-amnesty:{movement.id}:{movement.last_event_id}:{report.event_id}",
            movement_id=movement.id, settlement_id=movement.settlement_id,
            actor_ref=actor, report_event_id=report.event_id,
            negotiation_event_id=movement.last_event_id))
    return tuple(options)


def _decision(world, decision_event_id):
    decision = _event(world, decision_event_id)
    if (decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision is None
            or decision.decision.get("action") != AMNESTY_ACTION
            or set(decision.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("civic amnesty requires a current actor decision")
    return decision, EntityRef.from_dict(decision.decision["actor_ref"])


def grant_civic_amnesty(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in civic_amnesty_options(candidate, actor)
                   if item.id == option_id), None)
    if option is None:
        raise ValueError("civic amnesty option is stale or unknown")
    decision, decision_actor = _decision(candidate, decision_event_id)
    if decision_actor != actor or decision.decision != option.decision():
        raise ValueError("civic amnesty has the wrong decision")
    movement = candidate.society.civic_movements.get(option.movement_id)
    if movement is None or movement.stage != "dissolved" or movement.last_event_id != option.negotiation_event_id:
        raise ValueError("civic negotiation is no longer eligible for amnesty")
    event = record_event(
        candidate, "civic_amnesty_granted",
        "A administração concedeu anistia formal após a negociação cívica.",
        fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
        causal_payload={
            "decision_event_id": decision.id,
            "actor_ref": decision_actor.to_dict(),
            "selected_affordance_id": option.id,
            "amnesty_id": f"civic-amnesty:{decision.id}",
            "movement_id": movement.id,
            "negotiation_event_id": option.negotiation_event_id,
        },
        deltas=(_delta("civic_amnesty", f"civic-amnesty:{decision.id}", "stage", None, "granted"),),
        cause_ids=_causes(decision.id, option.negotiation_event_id, option.report_event_id),
    )
    amnesty = CivicAmnesty(
        id=f"civic-amnesty:{decision.id}", movement_id=movement.id,
        settlement_id=movement.settlement_id, administrator_ref=actor,
        granted_day=candidate.clock.absolute_day, decision_event_id=decision.id,
        last_event_id=event.id,
    )
    candidate.society.civic_amnesties[amnesty.id] = amnesty
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return amnesty


__all__ = ["AMNESTY_ACTION", "CivicAmnestyOption", "civic_amnesty_options", "grant_civic_amnesty"]
