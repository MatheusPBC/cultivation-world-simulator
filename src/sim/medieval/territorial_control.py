"""Explicit territorial control layered between occupation and administration."""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.control import TerritorialControl
from src.classes.society.models import Identity

from .economy import _causes, _delta
from .events import record_event


CONTROL_ACTION = "establish_territorial_control"
WITHDRAW_CONTROL_ACTION = "withdraw_territorial_control"


@dataclass(frozen=True)
class TerritorialControlOption:
    id: Identity
    actor_ref: EntityRef
    settlement_id: Identity
    garrison_id: Identity
    report_event_id: Identity
    basis: str = "occupation"
    kind: str = "establish"

    def decision(self):
        return {"action": WITHDRAW_CONTROL_ACTION if self.kind == "withdraw" else CONTROL_ACTION,
                "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _current_garrison(world, actor, settlement_id):
    settlement = world.society.settlements.get(settlement_id)
    if settlement is None or settlement.occupier_id != actor.id:
        return None
    for garrison in sorted(world.society.garrisons.values(), key=lambda item: item.id):
        detachment = world.society.detachments.get(garrison.detachment_id)
        if (garrison.settlement_id == settlement_id and garrison.stage == "active"
                and detachment is not None and detachment.owner_ref == actor
                and detachment.stage == "present" and detachment.location_id == settlement_id
                and detachment.provisions >= detachment.count):
            return garrison
    return None


def territorial_control_options(world, actor):
    """Enumerate control only after a paid, supplied occupation is durable."""
    if not isinstance(actor, EntityRef) or actor.kind != "polity":
        return ()
    if not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for settlement in sorted(world.society.settlements.values(), key=lambda item: item.id):
        garrison = _current_garrison(world, actor, settlement.id)
        report = world.knowledge.settlement_report(actor, settlement.id)
        if (garrison is None or report is None or report.observed_day != world.clock.absolute_day
                or report.occupier_id != settlement.occupier_id):
            continue
        control = world.society.territorial_controls.get(f"territorial-control:{settlement.id}")
        if control is None:
            options.append(TerritorialControlOption(
                id=f"territorial-control:{settlement.id}:{garrison.last_event_id}:{report.event_id}",
                actor_ref=actor, settlement_id=settlement.id, garrison_id=garrison.id,
                report_event_id=report.event_id))
        elif control.stage == "active" and control.controller_id == actor.id:
            options.append(TerritorialControlOption(
                id=f"territorial-control-withdraw:{settlement.id}:{control.last_event_id}:{garrison.last_event_id}:{report.event_id}",
                actor_ref=actor, settlement_id=settlement.id, garrison_id=garrison.id,
                report_event_id=report.event_id, kind="withdraw"))
    return tuple(options)


def establish_territorial_control(world, actor, option_id, decision_event_id):
    """Persist control without changing administration, ownership or claims."""
    candidate = deepcopy(world)
    decision = next((event for event in candidate.events if event.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != candidate.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != CONTROL_ACTION
            or decision.decision.get("actor_ref") != actor.to_dict()):
        raise ValueError("territorial control requires a current actor decision")
    option = next((item for item in territorial_control_options(candidate, actor) if item.id == option_id), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("territorial control option is stale or unknown")
    require_authority(candidate, actor, "military")
    control = TerritorialControl(
        id=f"territorial-control:{option.settlement_id}", settlement_id=option.settlement_id,
        controller_kind=actor.kind, controller_id=actor.id, basis=option.basis,
        started_day=candidate.clock.absolute_day, decision_event_id=decision.id, last_event_id="pending")
    event = record_event(
        candidate, "territorial_control_established",
        "A instituição assumiu controle territorial explícito enquanto mantém a guarnição; a administração não mudou.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("territorial_control", control.id, "stage", None, "active"),
                _delta("territorial_control", control.id, "settlement_id", None, control.settlement_id),
                _delta("territorial_control", control.id, "controller_id", None, control.controller_id),
                _delta("territorial_control", control.id, "basis", None, control.basis)),
        cause_ids=_causes(decision.id, candidate.society.garrisons[option.garrison_id].last_event_id,
                           option.report_event_id),
    )
    candidate.society.territorial_controls[control.id] = control.model_copy(update={"last_event_id": event.id})
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.territorial_controls[control.id]


def withdraw_territorial_control(world, actor, option_id, decision_event_id):
    """End only the control mandate; the physical column remains for its own decision."""
    candidate = deepcopy(world)
    decision = next((event for event in candidate.events if event.id == decision_event_id), None)
    if (decision is None or decision.fact_kind != FactKind.DECISION or decision.day != candidate.clock.absolute_day
            or decision.decision is None or decision.decision.get("action") != WITHDRAW_CONTROL_ACTION
            or decision.decision.get("actor_ref") != actor.to_dict()):
        raise ValueError("territorial control withdrawal requires a current actor decision")
    option = next((item for item in territorial_control_options(candidate, actor)
                   if item.id == option_id and item.kind == "withdraw"), None)
    if option is None or decision.decision != option.decision():
        raise ValueError("territorial control withdrawal option is stale or unknown")
    require_authority(candidate, actor, "military")
    identity = f"territorial-control:{option.settlement_id}"
    control = candidate.society.territorial_controls[identity]
    event = record_event(
        candidate, "territorial_control_withdrawn",
        "A instituição retirou o mandato de controle territorial; a presença militar continua separada.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("territorial_control", identity, "stage", "active", "withdrawn"),
                _delta("territorial_control", identity, "ended_day", None, candidate.clock.absolute_day)),
        cause_ids=_causes(decision.id, control.last_event_id,
                           candidate.society.garrisons[option.garrison_id].last_event_id,
                           option.report_event_id),
    )
    candidate.society.territorial_controls[identity] = control.model_copy(
        update={"stage": "withdrawn", "ended_day": candidate.clock.absolute_day, "last_event_id": event.id})
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.economy.validate(candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.territorial_controls[identity]


def lapse_territorial_control(world, settlement_id, *, cause_ids=(), reason=None):
    """End control only when its physical support is materially gone."""
    identity = f"territorial-control:{settlement_id}"
    control = world.society.territorial_controls.get(identity)
    if control is None or control.stage != "active":
        return None
    event = record_event(
        world, "territorial_control_lapsed",
        reason or "O controle territorial cessou quando sua base material deixou de existir.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("territorial_control", identity, "stage", "active", "lapsed"),
                _delta("territorial_control", identity, "ended_day", None, world.clock.absolute_day)),
        cause_ids=_causes(control.last_event_id, *cause_ids),
    )
    world.society.territorial_controls[identity] = control.model_copy(
        update={"stage": "lapsed", "ended_day": world.clock.absolute_day, "last_event_id": event.id})
    return event


__all__ = ["CONTROL_ACTION", "WITHDRAW_CONTROL_ACTION", "TerritorialControlOption",
           "territorial_control_options", "establish_territorial_control",
           "withdraw_territorial_control", "lapse_territorial_control"]
