"""Adapters and dated wake-ups over existing shared actor turns, not a planner."""

from src.systems.calendar_agenda import ScheduledSituation
from .institutional_decision_turn import DiscretionaryAdapter
from .religion import (invitation_options, adherence_options, religious_context,
                       invite_religious_adherence, accept_religious_adherence)

GROUP_REVIEW_KIND = "religious_group_response_review"
GROUP_REVIEW_PREFIX = "religious-group-response:"


def schedule_invitation_response(world, notice):
    if not world.config.ai_enabled:
        return
    actor = notice.recipient_ref
    if actor.kind == "character":
        from .character_rite_policy import OFFER_REVIEW_KIND, _offer_review_id
        identity, kind = _offer_review_id(actor.id, notice.event_id), OFFER_REVIEW_KIND
    else:
        identity, kind = f"{GROUP_REVIEW_PREFIX}{notice.id}", GROUP_REVIEW_KIND
    if world.agenda.get(identity) is None:
        world.agenda.schedule(ScheduledSituation(identity, kind, world.clock.absolute_day + 1))


def response_actors(world, situations):
    actors = set()
    for situation in situations:
        if situation.kind != GROUP_REVIEW_KIND or not situation.id.startswith(GROUP_REVIEW_PREFIX):
            continue
        notice = world.knowledge.religious_invitation_notices.get(situation.id[len(GROUP_REVIEW_PREFIX):])
        if (notice is not None and notice.recipient_ref.kind == "population_group"
                and adherence_options(world, notice.recipient_ref)):
            actors.add(notice.recipient_ref)
    return actors


def _situation(world, actor, options):
    return religious_context(world, actor)


def religion_adapters(*, invitations=True):
    response = DiscretionaryAdapter(
        "religious_adherence", adherence_options,
        lambda option: f"Escolher adesão ao convite {option.invitation_id}; não concede poder físico.",
        lambda world, option: (world.knowledge.religious_invitation_notices[option.invitation_id].event_id,),
        accept_religious_adherence, family="religion",
        situation_fn=_situation)
    if not invitations:
        return (response,)
    invitation = DiscretionaryAdapter(
        "religious_invitation", invitation_options,
        lambda option: f"Convidar {option.recipient_ref.kind}:{option.recipient_ref.id} em {option.settlement_id}; resposta independente.",
        lambda world, option: (option.report_event_id,), invite_religious_adherence,
        family="religion", situation_fn=_situation)
    return invitation, response
