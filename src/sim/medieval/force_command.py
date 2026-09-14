"""Real commanders and bounded doctrines for existing detachments.

This is intentionally not a second force owner.  Society owns the small
appointment registry, AuthorityState is consulted live for the appointing
office, and FieldEngagement remains the only owner of combat outcomes.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.mechanical_language import EntityRef
from src.classes.society.force import DetachmentCommand
from src.classes.society.models import Identity

from .character_travel import is_traveling
from .economy import _causes, _delta
from .events import record_event


APPOINT_ACTION = "appoint_detachment_commander"
SET_DOCTRINE_ACTION = "set_detachment_doctrine"
RELEASE_ACTION = "release_detachment_commander"
COMMAND_SKILL_MINIMUM = 40


@dataclass(frozen=True)
class DetachmentCommandAppointmentOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    character_id: Identity
    office_id: Identity

    def decision(self):
        return {"action": APPOINT_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class DetachmentDoctrineOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity
    doctrine: Literal["hold", "press"]

    def decision(self):
        return {"action": SET_DOCTRINE_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class DetachmentCommandReleaseOption:
    id: Identity
    actor_ref: EntityRef
    detachment_id: Identity

    def decision(self):
        return {"action": RELEASE_ACTION, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def _current_military_offices(world, actor):
    day = world.clock.absolute_day
    return tuple(sorted((office for office in world.authority.offices.values()
                         if office.institution_ref == actor and "military" in office.scopes
                         and office.starts_day <= day
                         and (office.ends_day is None or day < office.ends_day)
                         and can_actor_act_for(world, actor, actor, "military")), key=lambda item: item.id))


def _engagement_open(world, detachment_id):
    return any((engagement.challenger_detachment_id == detachment_id
                or engagement.defender_detachment_id == detachment_id)
               and engagement.status == "offered"
               for engagement in world.society.field_engagements.values())


def _engagement_started_today(world, detachment_id):
    return any((engagement.challenger_detachment_id == detachment_id
                or engagement.defender_detachment_id == detachment_id)
               and engagement.offered_day == world.clock.absolute_day
               for engagement in world.society.field_engagements.values())


def command_is_current(world, command):
    """Pure read used by engagement; invalid commands are removed by resolver."""
    detachment = world.society.detachments.get(command.detachment_id)
    character = world.society.characters.get(command.character_id)
    office = world.authority.offices.get(command.office_id)
    day = world.clock.absolute_day
    return (detachment is not None and character is not None and office is not None
            and detachment.stage == "present" and character.death_day is None
            and character.location_id == detachment.location_id
            and office.institution_ref == command.institution_ref and "military" in office.scopes
            and office.starts_day <= day and (office.ends_day is None or day < office.ends_day)
            and can_actor_act_for(world, command.institution_ref, command.institution_ref, "military"))


def effective_doctrine(world, detachment_id):
    command = world.society.detachment_commands.get(detachment_id)
    if (command is None or not command_is_current(world, command)
            or command.doctrine_effective_day is None
            ):
        return None
    if world.clock.absolute_day < command.doctrine_effective_day:
        return command.previous_doctrine
    return command.doctrine


def detachment_command_options(world, actor, *, detachment_id=None):
    """Engine-enumerated appointment, doctrine and explicit release choices."""
    if actor.kind not in {"polity", "organization"} or not can_actor_act_for(world, actor, actor, "military"):
        return ()
    offices = _current_military_offices(world, actor)
    if not offices:
        return ()
    options = []
    for detachment in sorted(world.society.detachments.values(), key=lambda item: item.id):
        if detachment_id is not None and detachment.id != detachment_id:
            continue
        if detachment.owner_ref != actor or detachment.stage != "present":
            continue
        command = world.society.detachment_commands.get(detachment.id)
        if command is None and not _engagement_started_today(world, detachment.id):
            for character in sorted(world.society.characters.values(), key=lambda item: item.id):
                if (character.death_day is None and character.location_id == detachment.location_id
                        # Somebody already on the road is not present to be
                        # appointed, even though its residence has not changed.
                        and not is_traveling(world, character.id)
                        and character.skills.command >= COMMAND_SKILL_MINIMUM
                        and all(item.character_id != character.id
                                for item in world.society.detachment_commands.values())):
                    for office in offices:
                        options.append(DetachmentCommandAppointmentOption(
                            id=(f"detachment-command-appoint:{detachment.id}:{character.id}:{office.id}:"
                                f"{detachment.last_event_id}"), actor_ref=actor, detachment_id=detachment.id,
                            character_id=character.id, office_id=office.id))
        elif command is not None and command_is_current(world, command):
            options.append(DetachmentCommandReleaseOption(
                id=f"detachment-command-release:{detachment.id}:{command.last_event_id}:{detachment.last_event_id}",
                actor_ref=actor, detachment_id=detachment.id))
            if not _engagement_open(world, detachment.id):
                for doctrine in ("hold", "press"):
                    if doctrine != command.doctrine:
                        options.append(DetachmentDoctrineOption(
                            id=(f"detachment-doctrine:{detachment.id}:{doctrine}:{command.last_event_id}:"
                                f"{detachment.last_event_id}"), actor_ref=actor, detachment_id=detachment.id,
                            doctrine=doctrine))
    return tuple(sorted(options, key=lambda item: item.id))


def _decision(world, decision_event_id, action):
    event = next((item for item in world.events if item.id == decision_event_id), None)
    if event is None or event.fact_kind != FactKind.DECISION or event.decision is None:
        raise ValueError("detachment command requires an exact decision")
    if event.decision.get("action") != action:
        raise ValueError("detachment command has the wrong decision action")
    return event


def _actor_from_decision(event):
    raw = event.decision.get("actor_ref") if event.decision else None
    return EntityRef.from_dict(raw)


def appoint_detachment_commander(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in detachment_command_options(candidate, actor)
                   if isinstance(item, DetachmentCommandAppointmentOption) and item.id == option_id), None)
    if option is None:
        raise ValueError("detachment commander option is stale or unknown")
    decision = _decision(candidate, decision_event_id, APPOINT_ACTION)
    if _actor_from_decision(decision) != actor or decision.decision != option.decision():
        raise ValueError("detachment commander appointment has the wrong decision")
    require_authority(candidate, actor, "military")
    office = candidate.authority.offices.get(option.office_id)
    detachment = candidate.society.detachments[option.detachment_id]
    character = candidate.society.characters[option.character_id]
    if (office is None or office.institution_ref != actor or "military" not in office.scopes
            or not command_is_current(candidate, DetachmentCommand(
                id=detachment.id, detachment_id=detachment.id, character_id=character.id,
                institution_ref=actor, office_id=office.id, appointed_day=candidate.clock.absolute_day,
                last_event_id=decision.id))
            or character.skills.command < COMMAND_SKILL_MINIMUM
            or detachment.id in candidate.society.detachment_commands
            or any(item.character_id == character.id for item in candidate.society.detachment_commands.values())
            or _engagement_started_today(candidate, detachment.id)):
        raise ValueError("detachment commander is no longer eligible")
    command = DetachmentCommand(id=detachment.id, detachment_id=detachment.id, character_id=character.id,
                                institution_ref=actor, office_id=office.id,
                                appointed_day=candidate.clock.absolute_day, last_event_id="pending")
    event = record_event(
        candidate, "detachment_commander_appointed", "Uma pessoa real assumiu o comando da coluna no local.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment_command", command.id, "character_id", None, character.id),
                _delta("detachment_command", command.id, "office_id", None, office.id),
                _delta("detachment_command", command.id, "appointed_day", None, command.appointed_day)),
        cause_ids=_causes(decision.id, detachment.last_event_id))
    candidate.society.detachment_commands[command.id] = command.model_copy(update={"last_event_id": event.id})
    candidate.society.validate(set(candidate.map.regions), candidate)
    candidate.knowledge.validate(candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachment_commands[command.id]


def set_detachment_doctrine(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in detachment_command_options(candidate, actor)
                   if isinstance(item, DetachmentDoctrineOption) and item.id == option_id), None)
    if option is None:
        raise ValueError("detachment doctrine option is stale or unknown")
    decision = _decision(candidate, decision_event_id, SET_DOCTRINE_ACTION)
    if _actor_from_decision(decision) != actor or decision.decision != option.decision():
        raise ValueError("detachment doctrine has the wrong decision")
    require_authority(candidate, actor, "military")
    command = candidate.society.detachment_commands[option.detachment_id]
    if not command_is_current(candidate, command) or _engagement_open(candidate, command.detachment_id):
        raise ValueError("detachment doctrine is no longer possible")
    effective_day = candidate.clock.absolute_day + 1
    previous = effective_doctrine(candidate, command.detachment_id)
    event = record_event(
        candidate, "detachment_doctrine_set", "A coluna recebeu uma doutrina que só vale no próximo dia.",
        fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment_command", command.id, "doctrine", command.doctrine, option.doctrine),
                _delta("detachment_command", command.id, "doctrine_effective_day", command.doctrine_effective_day,
                       effective_day),
                _delta("detachment_command", command.id, "previous_doctrine", command.previous_doctrine, previous)),
        cause_ids=_causes(decision.id, command.last_event_id,
                          candidate.society.detachments[command.detachment_id].last_event_id))
    candidate.society.detachment_commands[command.id] = command.model_copy(
        update={"doctrine": option.doctrine, "doctrine_effective_day": effective_day,
                "previous_doctrine": previous, "last_event_id": event.id})
    candidate.society.validate(set(candidate.map.regions), candidate)
    world.__dict__.update(candidate.__dict__)
    return world.society.detachment_commands[command.id]


def _release_command(world, command, *, event_type, content, cause_ids=()):
    """Remove only the command registry; the living person remains in place."""
    event = record_event(
        world, event_type, content, fact_kind=FactKind.STATE_TRANSITION,
        deltas=(_delta("detachment_command", command.id, "character_id", command.character_id, None),),
        cause_ids=_causes(command.last_event_id, *cause_ids))
    del world.society.detachment_commands[command.id]
    return event


def release_detachment_commander(world, actor, option_id, decision_event_id):
    candidate = deepcopy(world)
    option = next((item for item in detachment_command_options(candidate, actor)
                   if isinstance(item, DetachmentCommandReleaseOption) and item.id == option_id), None)
    if option is None:
        raise ValueError("detachment commander release option is stale or unknown")
    decision = _decision(candidate, decision_event_id, RELEASE_ACTION)
    if _actor_from_decision(decision) != actor or decision.decision != option.decision():
        raise ValueError("detachment commander release has the wrong decision")
    require_authority(candidate, actor, "military")
    command = candidate.society.detachment_commands[option.detachment_id]
    if not command_is_current(candidate, command):
        raise ValueError("detachment commander is no longer current")
    _release_command(candidate, command, event_type="detachment_commander_released",
                     content="O comando da coluna foi encerrado; a pessoa permaneceu no local.",
                     cause_ids=(decision.id,))
    candidate.society.validate(set(candidate.map.regions), candidate)
    world.__dict__.update(candidate.__dict__)
    return None


def revoke_detachment_command_for(world, detachment, *, cause_ids=(), reason="presence_lost"):
    command = world.society.detachment_commands.get(detachment.id)
    if command is None:
        return None
    return _release_command(world, command, event_type="detachment_commander_released",
                            content="O comando da coluna cessou porque a presença material mudou.",
                            cause_ids=_causes(detachment.last_event_id, *cause_ids))


def revoke_invalid_detachment_commands(world):
    """Dated maintenance for death, divergence or loss of the appointing scope."""
    for command in tuple(sorted(world.society.detachment_commands.values(), key=lambda item: item.id)):
        if not command_is_current(world, command):
            _release_command(world, command, event_type="detachment_commander_released",
                             content="O comando cessou porque a pessoa, a coluna ou o office não permaneceu válido.",
                             cause_ids=())


def execute_detachment_command_option(world, actor, option_id, decision_event_id):
    option = next((item for item in detachment_command_options(world, actor) if item.id == option_id), None)
    if option is None:
        raise ValueError("detachment command option is stale or unknown")
    action = option.decision()["action"]
    if action == APPOINT_ACTION:
        return appoint_detachment_commander(world, actor, option_id, decision_event_id)
    if action == SET_DOCTRINE_ACTION:
        return set_detachment_doctrine(world, actor, option_id, decision_event_id)
    if action == RELEASE_ACTION:
        return release_detachment_commander(world, actor, option_id, decision_event_id)
    raise ValueError("unknown detachment command action")


__all__ = ["APPOINT_ACTION", "COMMAND_SKILL_MINIMUM", "RELEASE_ACTION", "SET_DOCTRINE_ACTION",
           "DetachmentCommandAppointmentOption", "DetachmentCommandReleaseOption", "DetachmentDoctrineOption",
           "command_is_current", "detachment_command_options", "effective_doctrine",
           "execute_detachment_command_option", "revoke_detachment_command_for", "revoke_invalid_detachment_commands"]
