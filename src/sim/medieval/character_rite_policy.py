"""One individual turn: a resident healer may offer a restorative rite.

This is deliberately not a character planner. A qualified named resident gets
one bounded choice over the existing rite affordances after observing the
local condition. A different actor may sponsor on the following day from its
own report and own material means. Provider absence, failure, invalid output,
or NO_ACTION creates no offer and no rite.
"""

from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .events import record_event
from .rites import record_rite_offer, rite_offer_options, rite_sponsor_options, sponsor_rite


OFFER_REVIEW_KIND = "character_rite_offer_review"
SPONSOR_REVIEW_KIND = "character_rite_sponsor_review"
_OFFER_PREFIX = "character-rite-offer-review:"
_SPONSOR_PREFIX = "character-rite-sponsor-review:"


def _offer_review_id(character_id, report_event_id):
    return f"{_OFFER_PREFIX}{character_id}:{report_event_id}"


def _sponsor_review_id(offer_event_id):
    return f"{_SPONSOR_PREFIX}{offer_event_id}"


def _parse_offer_review(situation):
    if situation.kind != OFFER_REVIEW_KIND or not situation.id.startswith(_OFFER_PREFIX):
        return None
    character_id, marker, sequence = situation.id[len(_OFFER_PREFIX):].rpartition(":event:")
    if not character_id or marker != ":event:" or not sequence.isdecimal():
        return None
    return character_id, f"event:{sequence}"


def _parse_sponsor_review(situation):
    if situation.kind != SPONSOR_REVIEW_KIND or not situation.id.startswith(_SPONSOR_PREFIX):
        return None
    event_id = situation.id[len(_SPONSOR_PREFIX):]
    if not event_id.startswith("event:") or not event_id[6:].isdecimal():
        return None
    return event_id


def _actor_turn_available(world):
    """Whether a provider slot exists to schedule an individual turn."""
    return ai_decider.provider_available() and ai_decider.within_budget(world)


def schedule_character_rite_offers(world):
    """A fresh local report earns a future turn; it never chooses an action."""
    if not world.config.ai_enabled or not _actor_turn_available(world):
        return ()
    scheduled = []
    due_day = world.clock.absolute_day + 1
    for character_id in sorted(world.society.characters):
        options = rite_offer_options(world, character_id)
        if not options:
            continue
        situation_id = _offer_review_id(character_id, options[0].report_event_id)
        if world.agenda.get(situation_id) is None:
            world.agenda.schedule(ScheduledSituation(situation_id, OFFER_REVIEW_KIND, due_day))
            scheduled.append(situation_id)
    return tuple(scheduled)


def _character_situation(world, character, report):
    """Self-knowledge plus the character's own local aggregate observation."""
    return {
        "you_are": {
            "id": character.id,
            "name": character.name,
            "residence": character.location_id,
            "skills": {"restoration_magic": character.skills.restoration_magic},
            "personality": character.personality.model_dump(mode="json"),
            "motivations": list(character.motivations),
            "activity": "busy" if any(item.character_id == character.id for item in world.activities.values()) else "available",
        },
        "local_observation": {
            "settlement_id": report.settlement_id,
            "observed_day": report.observed_day,
            "health": report.health,
            "missing_food": report.missing_food,
            "unrest": report.unrest,
        },
        "today": world.clock.absolute_day,
    }


def _sponsor_situation(world, sponsor, option):
    """The sponsor sees its own report and a local offer, never foreign means."""
    report = world.knowledge.settlement_report(sponsor, option.settlement_id)
    return {
        "you_are": sponsor.to_dict(),
        "local_offer": {"settlement_id": option.settlement_id, "kind": "restorative_rite"},
        "local_observation": {
            "settlement_id": report.settlement_id,
            "observed_day": report.observed_day,
            "health": report.health,
            "missing_food": report.missing_food,
            "unrest": report.unrest,
        },
        "today": world.clock.absolute_day,
    }


async def _select(world, actor, situation, choices, *, causes):
    """Return a selection and only interpretation receipt IDs from this turn."""
    if not choices:
        return None, ()
    start = len(world.events)
    selected = await ai_decider.select_option(world, actor, situation, choices, causes=causes)
    receipts = tuple(event.id for event in world.events[start:]
                     if event.causal_origin.value == "llm_interpretation")
    return selected, receipts


def _stale(actor):
    return ProviderDecisionRequired(
        f"provider decision required for {actor.kind}:{actor.id}: character rite affordance became stale"
    )


def _decision(world, option, event_type, content, *, causes):
    return record_event(world, event_type, content, fact_kind=FactKind.DECISION,
                        decision=option.decision(), cause_ids=tuple(causes))


async def _offer_turn(world, situation):
    parsed = _parse_offer_review(situation)
    if parsed is None:
        return False
    character_id, source_event_id = parsed
    character = world.society.characters.get(character_id)
    if character is None:
        return False
    options = tuple(option for option in rite_offer_options(world, character_id)
                    if option.report_event_id == source_event_id)
    if not options:
        return False
    report = world.knowledge.settlement_report(EntityRef("character", character_id), options[0].settlement_id)
    if report is None:
        return False
    selected, interpretation_ids = await _select(
        world, EntityRef("character", character_id), _character_situation(world, character, report),
        [{"id": option.id, "label": "Oferecer conduzir um rito restaurador local."} for option in options],
        causes=(report.event_id,),
    )
    if selected in (None, ai_decider.NO_ACTION):
        return False
    option = next((item for item in rite_offer_options(world, character_id) if item.id == selected), None)
    if option is None or option.report_event_id != source_event_id:
        raise _stale(EntityRef("character", character_id))
    offer = record_rite_offer(world, character_id, option.id, cause_ids=interpretation_ids)
    world.agenda.schedule(ScheduledSituation(_sponsor_review_id(offer.id), SPONSOR_REVIEW_KIND,
                                             world.clock.absolute_day + 1))
    return True


async def _sponsor_turn(world, situation):
    offer_event_id = _parse_sponsor_review(situation)
    if offer_event_id is None:
        return False
    offer_event = next((event for event in world.events if event.id == offer_event_id), None)
    if offer_event is None:
        return False
    acted = False
    for sponsor_kind, registry in (("organization", world.society.organizations), ("polity", world.society.polities)):
        for sponsor_id in sorted(registry):
            sponsor = EntityRef(sponsor_kind, sponsor_id)
            options = tuple(option for option in rite_sponsor_options(world, sponsor)
                            if option.offer_event_id == offer_event_id)
            if not options:
                continue
            report = world.knowledge.settlement_report(sponsor, options[0].settlement_id)
            if report is None:
                continue
            selected, interpretation_ids = await _select(
                world, sponsor, _sponsor_situation(world, sponsor, options[0]),
                [{"id": option.id, "label": "Patrocinar o rito restaurador local."} for option in options],
                causes=(offer_event.id, report.event_id),
            )
            if selected in (None, ai_decider.NO_ACTION):
                continue
            option = next((item for item in rite_sponsor_options(world, sponsor) if item.id == selected), None)
            if option is None or option.offer_event_id != offer_event_id:
                raise _stale(sponsor)
            decision = _decision(world, option, "rite_sponsorship_decided",
                                 "A instituição escolheu uma resposta para o rito local.",
                                 causes=(*interpretation_ids, offer_event.id))
            try:
                sponsor_rite(world, sponsor, option.id, decision.id)
            except ValueError as exc:
                raise _stale(sponsor) from exc
            acted = True
    return acted


async def review_character_rites(world, situations):
    """Resolve only scheduled individual and sponsor turns, within provider budget."""
    reviewed_characters = set()
    for situation in sorted(situations, key=lambda item: item.id):
        parsed = _parse_offer_review(situation)
        if parsed is not None:
            character_id, _ = parsed
            if character_id in reviewed_characters:
                continue
            reviewed_characters.add(character_id)
            await _offer_turn(world, situation)
        elif _parse_sponsor_review(situation) is not None:
            await _sponsor_turn(world, situation)


__all__ = ["OFFER_REVIEW_KIND", "SPONSOR_REVIEW_KIND", "review_character_rites", "schedule_character_rite_offers"]
