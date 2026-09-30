"""Local invitation and independent adherence; beliefs do not change physics."""

from dataclasses import dataclass
import json

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.authority import can_actor_act_for
from src.classes.governance.models import ReligiousInvitationNotice
from src.classes.mechanical_language import EntityRef
from src.classes.society.religion import ReligiousAdherence
from .economy import _delta
from .events import record_event
from .material_execution import execute_material

INVITE = "invite_religious_adherence"
JOIN = "accept_religious_adherence"
RELIGIOUS_KINDS = {"religious_order", "cult"}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def adherence_id(actor):
    return f"religious-adherence:{actor.kind}:{actor.id}"


def _residence(world, actor):
    if actor.kind == "population_group":
        group = world.society.population.get(actor.id)
        return group.settlement_id if group and world.society.available_count(group.id) > 0 else None
    character = world.society.characters.get(actor.id) if actor.kind == "character" else None
    if (character is None or character.death_day is not None
            or any(a.character_id == character.id for a in world.activities.values())
            or any(character.id in journey.character_ids for journey in world.society.migrations.values())):
        return None
    group = world.society.population.get(character.population_group_id)
    return character.location_id if group and group.settlement_id == character.location_id else None


@dataclass(frozen=True)
class ReligiousInvitationOption:
    id: str
    actor_ref: EntityRef
    recipient_ref: EntityRef
    settlement_id: str
    emissary_id: str
    report_event_id: str

    def decision(self):
        return {"action": INVITE, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


@dataclass(frozen=True)
class ReligiousAdherenceOption:
    id: str
    actor_ref: EntityRef
    invitation_id: str

    def decision(self):
        return {"action": JOIN, "actor_ref": self.actor_ref.to_dict(), "selected_affordance_id": self.id}


def invitation_options(world, actor):
    organization = world.society.organizations.get(actor.id) if actor.kind == "organization" else None
    if (organization is None or organization.kind not in RELIGIOUS_KINDS or not organization.doctrine
            or not can_actor_act_for(world, actor, actor, "diplomacy")):
        return ()
    options = []
    for report in world.knowledge.settlements_for_actor(actor):
        if (report.publisher_ref != actor or not 0 <= world.clock.absolute_day - report.observed_day < 7):
            continue
        emissary = next((member for member in sorted(organization.member_ids)
                         if _residence(world, EntityRef("character", member)) == report.settlement_id), None)
        if emissary is None:
            continue
        residents = [EntityRef("character", identity) for identity in sorted(world.society.characters)]
        residents += [EntityRef("population_group", identity) for identity in sorted(world.society.population)]
        for recipient in residents:
            if _residence(world, recipient) != report.settlement_id or recipient == EntityRef("character", emissary):
                continue
            adherence = world.society.religious_adherences.get(adherence_id(recipient))
            if adherence and adherence.organization_id == actor.id:
                continue
            if any(n.publisher_ref == actor and n.recipient_ref == recipient
                   and n.expires_day > world.clock.absolute_day
                   for n in world.knowledge.religious_invitation_notices.values()):
                continue
            options.append(ReligiousInvitationOption(
                f"religious-invite:{actor.id}:{recipient.kind}:{recipient.id}:{report.event_id}",
                actor, recipient, report.settlement_id, emissary, report.event_id))
    return tuple(options)


def adherence_options(world, actor):
    result = []
    current = world.society.religious_adherences.get(adherence_id(actor))
    for notice in world.knowledge.religious_invitation_notices.values():
        if (notice.recipient_ref != actor or not notice.offered_day <= world.clock.absolute_day < notice.expires_day
                or _residence(world, actor) != notice.settlement_id
                or (current and current.organization_id == notice.publisher_ref.id)):
            continue
        result.append(ReligiousAdherenceOption(f"religious-join:{notice.id}:{notice.event_id}", actor, notice.id))
    return tuple(sorted(result, key=lambda item: item.id))


def religious_context(world, actor):
    """Own declared affiliation and locally received public doctrine only.

    Doctrine is an authored, immutable declaration, not a physical reading.
    Neither institutional membership nor another resident's faith is exposed.
    """
    current = world.society.religious_adherences.get(adherence_id(actor))
    affiliation = None
    if current is not None:
        tradition = world.society.organizations[current.organization_id]
        affiliation = {"organization_id": tradition.id, "doctrine": list(tradition.doctrine),
                       "joined_day": current.joined_day, "event_id": current.last_event_id}
    invitations = []
    for option in adherence_options(world, actor):
        notice = world.knowledge.religious_invitation_notices[option.invitation_id]
        tradition = world.society.organizations[notice.publisher_ref.id]
        invitations.append({"affordance_id": option.id, "organization_id": tradition.id,
                            "doctrine": list(tradition.doctrine), "offered_day": notice.offered_day,
                            "expires_day": notice.expires_day, "event_id": notice.event_id})
    organization = world.society.organizations.get(actor.id) if actor.kind == "organization" else None
    return {"own_affiliation": affiliation, "received_invitations": invitations,
            "own_declared_doctrine": list(organization.doctrine) if organization else [],
            "interpretation": "Declarações religiosas são crenças, não leis ou efeitos físicos confirmados."}


def _decision(world, option, event_id):
    event = world.event_index().get(event_id)
    if (event is None or event.day != world.clock.absolute_day or event.fact_kind != FactKind.DECISION
            or event.causal_origin != CausalOrigin.ACTOR_DECISION or event.decision != option.decision()):
        raise ValueError("religious action requires its own current exact actor decision")
    return event


def _invite(world, actor, option_id, decision_event_id):
    option = next((o for o in invitation_options(world, actor) if o.id == option_id), None)
    if option is None:
        raise ValueError("religious invitation option is stale or unknown")
    decision = _decision(world, option, decision_event_id)
    identity = f"religious-invitation:{decision.id}"
    body = dict(id=identity, recipient_ref=option.recipient_ref.to_dict(), publisher_ref=actor.to_dict(),
                settlement_id=option.settlement_id, emissary_id=option.emissary_id,
                offered_day=world.clock.absolute_day, expires_day=world.clock.absolute_day + 7,
                report_event_id=option.report_event_id)
    event = record_event(world, "religious_invitation_delivered", "Convite religioso entregue localmente; nenhuma adesão foi presumida.",
                         fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
                         causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                                         "selected_affordance_id": option.id},
                         deltas=(_delta("religious_invitation", identity, "invitation", None, _json(body)),),
                         cause_ids=(decision.id, option.report_event_id))
    notice = ReligiousInvitationNotice(**body, event_id=event.id)
    world.knowledge.religious_invitation_notices[notice.id] = notice
    from .religion_policy import schedule_invitation_response
    schedule_invitation_response(world, notice)
    return notice


def invite_religious_adherence(world, actor, option_id, decision_event_id):
    return execute_material(world, _invite, actor, option_id, decision_event_id)


def _join(world, actor, option_id, decision_event_id):
    option = next((o for o in adherence_options(world, actor) if o.id == option_id), None)
    if option is None:
        raise ValueError("religious adherence option is stale or unknown")
    decision = _decision(world, option, decision_event_id)
    notice = world.knowledge.religious_invitation_notices[option.invitation_id]
    identity = adherence_id(actor)
    previous = world.society.religious_adherences.get(identity)
    event = record_event(world, "religious_adherence_chosen", "O destinatário escolheu adesão religiosa; crença não comprova efeito físico.",
                         fact_kind=FactKind.STATE_TRANSITION, causal_origin=CausalOrigin.ACTOR_DECISION,
                         causal_payload={"decision_event_id": decision.id, "actor_ref": actor.to_dict(),
                                         "selected_affordance_id": option.id, "invitation_id": notice.id},
                         deltas=(_delta("religious_adherence", identity, "organization_id",
                                        previous.organization_id if previous else None, notice.publisher_ref.id),),
                         cause_ids=tuple(x for x in (decision.id, notice.event_id,
                                                   previous.last_event_id if previous else None) if x))
    adherence = ReligiousAdherence(id=identity, actor_ref=actor, organization_id=notice.publisher_ref.id,
                                  joined_day=world.clock.absolute_day, invitation_id=notice.id, last_event_id=event.id)
    world.society.religious_adherences[identity] = adherence
    return adherence


def accept_religious_adherence(world, actor, option_id, decision_event_id):
    return execute_material(world, _join, actor, option_id, decision_event_id)


def validate_invitation(world, notice):
    events = world.event_index()
    event = events.get(notice.event_id)
    organization = world.society.organizations.get(notice.publisher_ref.id)
    body = notice.model_dump(mode="json", exclude={"event_id"})
    sources = {link.cause_event_id for link in event.causal_links} if event else set()
    decision = events.get((event.causal_payload or {}).get("decision_event_id")) if event else None
    report = events.get(notice.report_event_id)
    readings = [json.loads(d.after) for d in report.deltas
                if d.owner_kind == "settlement_report" and d.aspect == "observation"] if report else []
    expected_option_id = (f"religious-invite:{notice.publisher_ref.id}:{notice.recipient_ref.kind}:"
                          f"{notice.recipient_ref.id}:{notice.report_event_id}")
    actors = world.society.characters if notice.recipient_ref.kind == "character" else world.society.population
    if (organization is None or organization.kind not in RELIGIOUS_KINDS or not organization.doctrine
            or notice.recipient_ref.id not in actors or notice.emissary_id not in world.society.characters
            or event is None or event.event_type != "religious_invitation_delivered"
            or event.causal_origin != CausalOrigin.ACTOR_DECISION
            or event.day != notice.offered_day or event.day > world.clock.absolute_day
            or notice.id != f"religious-invitation:{decision.id if decision else ''}"
            or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.causal_origin != CausalOrigin.ACTOR_DECISION or decision.day != event.day
            or decision.decision != {"action": INVITE, "actor_ref": notice.publisher_ref.to_dict(),
                                      "selected_affordance_id": (event.causal_payload or {}).get("selected_affordance_id")}
            or decision.id not in sources or notice.report_event_id not in sources
            or report is None or report.event_type != "settlement_observed"
            or (event.causal_payload or {}).get("actor_ref") != notice.publisher_ref.to_dict()
            or (event.causal_payload or {}).get("selected_affordance_id") != expected_option_id
            or not any(r["publisher"] == notice.publisher_ref.to_dict()
                       and r["settlement_id"] == notice.settlement_id
                       and 0 <= notice.offered_day - r["observed_day"] < 7 for r in readings)
            or not any(d.owner_kind == "religious_invitation" and d.owner_id == notice.id
                       and d.aspect == "invitation" and d.before == "None" and d.after == _json(body) for d in event.deltas)):
        raise ValueError("religious invitation lacks its exact authored local receipt")


def validate_adherence(world, adherence):
    events = world.event_index()
    event = events.get(adherence.last_event_id)
    notice = world.knowledge.religious_invitation_notices.get(adherence.invitation_id)
    decision = events.get((event.causal_payload or {}).get("decision_event_id")) if event else None
    if (event is None or event.event_type != "religious_adherence_chosen" or event.day != adherence.joined_day
            or event.causal_origin != CausalOrigin.ACTOR_DECISION
            or notice is None or notice.recipient_ref != adherence.actor_ref
            or notice.publisher_ref.id != adherence.organization_id
            or not notice.offered_day <= event.day < notice.expires_day or event.day > world.clock.absolute_day
            or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.causal_origin != CausalOrigin.ACTOR_DECISION or decision.day != event.day
            or decision.decision != ReligiousAdherenceOption(
                f"religious-join:{notice.id}:{notice.event_id}", adherence.actor_ref, notice.id).decision()
            or not {notice.event_id, decision.id} <= {link.cause_event_id for link in event.causal_links}
            or not any(d.owner_kind == "religious_adherence" and d.owner_id == adherence.id
                       and d.aspect == "organization_id" and d.after == adherence.organization_id for d in event.deltas)):
        raise ValueError("religious adherence lacks independent consent and invitation")
