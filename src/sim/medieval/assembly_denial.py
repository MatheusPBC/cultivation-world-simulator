"""A force may deny public rite assembly at one locally observed site.

This is deliberately narrower than a siege, capture or generic magic system.
The force changes no map/site/property state and never reads a rite contract.
It establishes a revocable Society fact.  On the following dated tick the
Research owner notices that factual denial and uses its normal reagent-loss
interruption path.
"""

from copy import deepcopy
from dataclasses import dataclass

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import AssemblyDenial
from src.classes.society.models import Identity
from src.systems.calendar_agenda import ScheduledSituation

from .economy import _causes, _delta
from .events import record_event


DENY_ACTION = "deny_rite_assembly"
LIFT_ACTION = "lift_rite_assembly_denial"
OBSERVATION_MAX_AGE_DAYS = 1


@dataclass(frozen=True)
class AssemblyDenialOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    site_id: Identity
    settlement_id: Identity
    kind: str
    observation_id: Identity | None = None

    def decision(self):
        return {"action": DENY_ACTION if self.kind == "deny" else LIFT_ACTION,
                "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _prepared_local_force(world, actor, detachment):
    if (detachment.owner_ref != actor or detachment.stage != "present" or detachment.provisions < detachment.count):
        return False
    position = world.society.force_positions.get(f"force-position:{detachment.id}")
    return position is not None and position.stage == "prepared" and position.settlement_id == detachment.location_id


def _active_rite_at_site(world, site_id, settlement_id):
    return any(rite.stage == "officiating" and rite.site_id == site_id and rite.settlement_id == settlement_id
               for rite in world.research.rites.values())


def assembly_denial_options(world, actor, *, detachment_id=None):
    """Current local choices; the private observation is the only rite input."""
    if not isinstance(actor, EntityRef) or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    options = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if detachment_id is not None and detachment.id != detachment_id:
            continue
        if not _prepared_local_force(world, actor, detachment):
            continue
        active = [denial for denial in world.society.assembly_denials.values()
                  if denial.detachment_id == detachment.id and denial.actor_ref == actor]
        for denial in sorted(active, key=lambda item: item.id):
            options.append(AssemblyDenialOption(
                id=f"rite-assembly-lift:{detachment.id}:{denial.id}:{denial.last_event_id}", actor_ref=actor,
                detachment_id=detachment.id, site_id=denial.id, settlement_id=denial.settlement_id, kind="lift"))
        if active:
            continue
        for observation in sorted(world.knowledge.rite_observations.values(), key=lambda item: item.id):
            if (observation.recipient_ref != actor or observation.settlement_id != detachment.location_id
                    or observation.stage != "underway"
                    or world.clock.absolute_day - observation.observed_day > OBSERVATION_MAX_AGE_DAYS
                    or observation.observed_day > world.clock.absolute_day
                    or observation.site_id in world.society.assembly_denials
                    or not _active_rite_at_site(world, observation.site_id, observation.settlement_id)):
                continue
            site = world.map.infrastructure_sites.get(observation.site_id)
            settlement = world.society.settlements.get(observation.settlement_id)
            if site is None or settlement is None or settlement.region_id not in site.region_ids:
                continue
            options.append(AssemblyDenialOption(
                id=(f"rite-assembly-deny:{detachment.id}:{observation.site_id}:{detachment.last_event_id}:"
                    f"{world.society.force_positions[f'force-position:{detachment.id}'].last_event_id}:{observation.event_id}"),
                actor_ref=actor, detachment_id=detachment.id, site_id=observation.site_id,
                settlement_id=observation.settlement_id, kind="deny", observation_id=observation.id))
    return tuple(options)


def _decision(world, decision_event_id, action):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if (event is None or event.fact_kind != FactKind.DECISION or event.day != world.clock.absolute_day
            or event.decision is None or event.decision.get("action") != action
            or set(event.decision) != {"action", "actor_ref", "selected_affordance_id"}):
        raise ValueError("assembly denial requires a current actor decision")
    try:
        return event, EntityRef.from_dict(event.decision["actor_ref"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("assembly denial has an invalid actor") from exc


def execute_assembly_denial_option(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in assembly_denial_options(candidate, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("assembly denial option is stale or unknown")
    decision, decided_by = _decision(candidate, decision_event_id,
                                     DENY_ACTION if option.kind == "deny" else LIFT_ACTION)
    if decided_by != actor or decision.decision != option.decision():
        raise ValueError("assembly denial has the wrong decision")
    require_authority(candidate, actor, "military")
    if option.kind == "lift":
        _lift(candidate, candidate.society.assembly_denials[option.site_id], cause_ids=(decision.id,))
    else:
        _deny(candidate, option, decision)
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    candidate.research.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.assembly_denials.get(option.site_id)


def _deny(world, option, decision):
    detachment = world.society.detachments.get(option.detachment_id)
    observation = world.knowledge.rite_observations.get(option.observation_id)
    if (detachment is None or observation is None or not _prepared_local_force(world, option.actor_ref, detachment)
            or observation.recipient_ref != option.actor_ref or observation.site_id != option.site_id
            or observation.settlement_id != option.settlement_id
            or world.clock.absolute_day - observation.observed_day > OBSERVATION_MAX_AGE_DAYS
            or option.site_id in world.society.assembly_denials
            or not _active_rite_at_site(world, option.site_id, option.settlement_id)):
        raise ValueError("assembly denial is no longer possible")
    denial = AssemblyDenial(id=option.site_id, actor_ref=option.actor_ref, detachment_id=detachment.id,
                            settlement_id=option.settlement_id, started_day=world.clock.absolute_day,
                            decision_event_id=decision.id, last_event_id="pending")
    position = world.society.force_positions[f"force-position:{detachment.id}"]
    event = record_event(
        world, "assembly_denied", "Uma coluna preparada negou a assembleia de um rito observado localmente.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("assembly_denial", denial.id, "detachment_id", None, detachment.id),
                _delta("assembly_denial", denial.id, "settlement_id", None, denial.settlement_id)),
        cause_ids=_causes(decision.id, observation.event_id, detachment.last_event_id, position.last_event_id))
    world.society.assembly_denials[denial.id] = denial.model_copy(update={"last_event_id": event.id})
    world.agenda.schedule(ScheduledSituation(denial.id, "rite_interruption", world.clock.absolute_day + 1))
    return world.society.assembly_denials[denial.id]


def _lift(world, denial, *, cause_ids=()):
    current = world.society.assembly_denials.get(denial.id)
    if current != denial:
        raise ValueError("assembly denial no longer holds")
    event = record_event(
        world, "assembly_denial_lifted", "A coluna deixou de negar a assembleia local.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("assembly_denial", denial.id, "detachment_id", denial.detachment_id, None),),
        cause_ids=_causes(denial.last_event_id, *cause_ids))
    del world.society.assembly_denials[denial.id]
    world.agenda.cancel(denial.id)
    return event


def revoke_assembly_denials_for(world, detachment, *, cause_ids=()):
    """A departing, unprepared or unsupplied column cannot retain this fact."""
    lifted = []
    for denial in tuple(world.society.assembly_denials.values()):
        if denial.detachment_id == detachment.id:
            lifted.append(_lift(world, denial, cause_ids=_causes(detachment.last_event_id, *cause_ids)))
    return tuple(lifted)


__all__ = ["DENY_ACTION", "LIFT_ACTION", "AssemblyDenialOption", "assembly_denial_options",
           "execute_assembly_denial_option", "revoke_assembly_denials_for"]
