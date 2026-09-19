"""One bounded institutional espionage mission.

The engine enumerates a real person already acting for an institution and a
foreign settlement where that person is present.  Resolution never changes
the settlement: it records only the result and, on success, a reference to an
existing settlement-observation event.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.models import EspionageFinding
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Identity

from .economy import _causes, _delta
from .events import record_event
from .institutional_decision_turn import DiscretionaryAdapter


ESPIONAGE_ACTION = "espionage_mission"
MIN_INVESTIGATION_SKILL = 1
SUCCESS_INVESTIGATION_SKILL = 50


@dataclass(frozen=True)
class EspionageOption:
    id: Identity
    actor_ref: EntityRef
    agent_ref: EntityRef
    target_ref: EntityRef
    target_owner_ref: EntityRef
    evidence_event_id: Identity

    def decision(self):
        return {"action": ESPIONAGE_ACTION, "actor_ref": self.actor_ref.to_dict(),
                "selected_affordance_id": self.id}


def _event(world, event_id):
    return next((item for item in world.events if item.id == event_id), None)


def _target_evidence(world, target_owner_ref, target_id):
    report_id = f"settlement_report:{target_owner_ref.kind}:{target_owner_ref.id}:{target_id}"
    for event in reversed(world.events):
        if (event.event_type == "settlement_observed"
                and any(delta.owner_kind == "settlement_report" and delta.owner_id == report_id
                        and delta.aspect == "observation" for delta in event.deltas)):
            return event.id
    return None


def _agents(world, owner_ref):
    """Only current office holders can be used; membership or prose is not authority."""
    day = world.clock.absolute_day
    for office in sorted(world.authority.offices.values(), key=lambda item: item.id):
        if (office.institution_ref != owner_ref or office.holder_ref.kind != "character"
                or "diplomacy" not in office.scopes or office.starts_day > day
                or (office.ends_day is not None and day >= office.ends_day)):
            continue
        agent = world.society.characters.get(office.holder_ref.id)
        if (agent is not None and agent.death_day is None
                and agent.skills.investigation >= MIN_INVESTIGATION_SKILL):
            yield agent


def _already_resolved(world, actor_ref, agent_ref, target_ref):
    return any(item.recipient_ref == actor_ref and item.agent_ref == agent_ref
               and item.target_ref == target_ref and item.learned_day == world.clock.absolute_day
               for item in world.knowledge.espionage_findings.values())


def _target_detects(world, target_ref, target_owner_ref):
    return any(detachment.owner_ref == target_owner_ref and detachment.location_id == target_ref.id
               and detachment.stage == "present"
               for detachment in world.society.detachments.values())


def espionage_options(world, actor_ref):
    if (not isinstance(actor_ref, EntityRef) or actor_ref.kind not in {"polity", "organization"}
            or not can_actor_act_for(world, actor_ref, actor_ref, "diplomacy")):
        return ()
    options = []
    for agent in _agents(world, actor_ref):
        agent_ref = EntityRef("character", agent.id)
        for target in sorted(world.society.settlements.values(), key=lambda item: item.id):
            if target.administrator_id is None or target.administrator_id == actor_ref.id:
                continue
            target_ref = EntityRef("settlement", target.id)
            owner_ref = EntityRef("polity", target.administrator_id)
            evidence = _target_evidence(world, owner_ref, target.id)
            if evidence is None or agent.location_id != target.id or _already_resolved(world, actor_ref, agent_ref, target_ref):
                continue
            yield_option = EspionageOption(
                id=f"espionage:{actor_ref.kind}:{actor_ref.id}:{agent.id}:{target.id}:{evidence}",
                actor_ref=actor_ref, agent_ref=agent_ref, target_ref=target_ref,
                target_owner_ref=owner_ref, evidence_event_id=evidence)
            options.append(yield_option)
    return tuple(options)


def _decision(world, decision_event_id, option):
    event = _event(world, decision_event_id)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision != option.decision()):
        raise ValueError("espionage requires its exact current decision")
    return event


def execute_espionage(world, actor_ref, option_id, decision_event_id):
    """Recompose and execute one selected mission on an isolated candidate."""
    candidate = deepcopy(world)
    option = next((item for item in espionage_options(candidate, actor_ref) if item.id == option_id), None)
    if option is None:
        raise ValueError("espionage option is stale or unknown")
    decision = _decision(candidate, decision_event_id, option)
    if option.actor_ref != actor_ref:
        raise ValueError("espionage owner mismatch")
    require_authority(candidate, actor_ref, "diplomacy")
    agent = candidate.society.characters.get(option.agent_ref.id)
    target = candidate.society.settlements.get(option.target_ref.id)
    if (agent is None or agent.death_day is not None or agent.location_id != option.target_ref.id
            or agent.skills.investigation < MIN_INVESTIGATION_SKILL or target is None
            or target.administrator_id != option.target_owner_ref.id
            or not can_actor_act_for(candidate, option.agent_ref, actor_ref, "diplomacy")):
        raise ValueError("espionage agent, capability or target is no longer valid")
    evidence_event_id = _target_evidence(candidate, option.target_owner_ref, target.id)
    if evidence_event_id != option.evidence_event_id:
        raise ValueError("espionage target evidence is stale")
    detected = _target_detects(candidate, option.target_ref, option.target_owner_ref)
    result = "discovered" if detected else (
        "success" if agent.skills.investigation >= SUCCESS_INVESTIGATION_SKILL else "failure")
    finding_id = f"espionage_finding:{decision.id}"
    causes = _causes(decision.id, evidence_event_id)
    event = record_event(
        candidate, "espionage_resolved",
        "Uma missão de espionagem foi resolvida como fato institucional limitado.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("espionage_finding", finding_id, "result", None, result),
                _delta("espionage_finding", finding_id, "evidence_event_id", None,
                       evidence_event_id if result == "success" else None)),
        cause_ids=causes)
    finding = EspionageFinding(
        id=finding_id, mission_id=option.id, decision_event_id=decision.id,
        recipient_ref=actor_ref, agent_ref=option.agent_ref, target_ref=option.target_ref,
        target_owner_ref=option.target_owner_ref, result=result,
        evidence_event_id=evidence_event_id if result == "success" else None,
        learned_day=candidate.clock.absolute_day, event_id=event.id)
    candidate.knowledge.espionage_findings[finding.id] = finding
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return finding


def espionage_adapters():
    """Expose the same owner through the shared institutional affordance menu."""
    return (DiscretionaryAdapter(
        name="espionage", family="conflict", options_fn=espionage_options,
        label_fn=lambda _option: "Enviar agente para obter uma evidência canônica do alvo.",
        causes_fn=lambda _world, option: (option.evidence_event_id,),
        execute_fn=lambda world, actor, option_id, decision_event_id:
            execute_espionage(world, actor, option_id, decision_event_id),
    ),)


__all__ = ["ESPIONAGE_ACTION", "EspionageOption", "espionage_options", "execute_espionage",
           "espionage_adapters"]
