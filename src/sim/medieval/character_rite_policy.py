"""One bounded individual initiative turn for existing local affordances.

This is deliberately not a character planner. A named resident gets one bounded
choice over current local rite and apprenticeship affordances. The host decides
separately whether to sponsor an instruction contract through its existing
monthly institutional menu. Provider absence, failure, invalid output, or
NO_ACTION creates no offer or contract.
"""

from src.classes.event import FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.mechanical_language import EntityRef
from src.systems.calendar_agenda import ScheduledSituation

from . import ai_decider
from .ai_decider import ProviderDecisionRequired
from .events import record_event, record_no_action_decision
from .actor_dossier import recent_creature_attacks_for_report
from .rites import record_rite_offer, rite_offer_options, rite_sponsor_options, sponsor_rite
from .apprenticeship import (record_apprenticeship_offer, specialist_offer_options)
from .research import (accept_research_work, lapse_stale_research_offers,
                       researcher_work_options)
from .religion import adherence_options, religious_context, accept_religious_adherence


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
    """Schedule one existing individual turn when a current option exists."""
    if not world.config.ai_enabled or not _actor_turn_available(world):
        return ()
    scheduled = []
    due_day = world.clock.absolute_day + 1
    for character_id in sorted(world.society.characters):
        rite_options = rite_offer_options(world, character_id)
        learning_options = _undecided_learning_offers(world, character_id)
        research_options = researcher_work_options(world, character_id)
        faith_options = adherence_options(world, EntityRef("character", character_id))
        if not rite_options and not learning_options and not research_options and not faith_options:
            continue
        # The agenda key is only a wake-up cause. At execution the menu is
        # always recomposed, so a stale report cannot preserve an old option.
        cause_id = (rite_options[0].report_event_id if rite_options
                    else learning_options[0].source_event_ids[0] if learning_options
                    else research_options[0].authorization_event_id if research_options
                    else world.knowledge.religious_invitation_notices[faith_options[0].invitation_id].event_id)
        situation_id = _offer_review_id(character_id, cause_id)
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
            "skills": character.skills.model_dump(mode="json"),
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
            "recent_creature_attacks": recent_creature_attacks_for_report(world, report),
        },
        "today": world.clock.absolute_day,
    }


def _character_self_situation(world, character, learning_options):
    return {
        "you_are": {
            "id": character.id,
            "name": character.name,
            "residence": character.location_id,
            "skills": character.skills.model_dump(mode="json"),
            "personality": character.personality.model_dump(mode="json"),
            "motivations": list(character.motivations),
            "activity": "busy" if any(item.character_id == character.id
                                       for item in world.activities.values()) else "available",
        },
        "learning_opportunities": [
            {"technology_id": option.technology_id, "host": option.host_ref.to_dict(),
             "settlement_id": option.settlement_id}
            for option in learning_options
        ],
        "today": world.clock.absolute_day,
    }


def _undecided_learning_offers(world, character_id):
    options = specialist_offer_options(world, character_id)
    if not options:
        return ()
    decided = set()
    for event in world.events:
        decision = event.decision or {}
        if decision.get("actor_ref") != EntityRef("character", character_id).to_dict():
            continue
        if decision.get("action") == "no_action":
            decided.update(decision.get("declined_option_ids", ()))
        elif decision.get("action") == "offer_apprenticeship":
            selected = decision.get("selected_affordance_id")
            if selected:
                decided.add(selected)
    return tuple(option for option in options if option.id not in decided)


def _sponsor_situation(world, sponsor, option):
    """The sponsor sees its own report and a local offer, never foreign means."""
    report = world.knowledge.settlement_report(sponsor, option.settlement_id)
    blueprint = world.research.rite_blueprints[option.blueprint_id]
    site_report = (world.knowledge.site_report(sponsor, option.site_id)
                   if blueprint.kind in {"earth_shaping", "evocation"} else None)
    return {
        "you_are": sponsor.to_dict(),
        "local_offer": {"settlement_id": option.settlement_id, "kind": blueprint.kind,
                        "technique": blueprint.name, "cost": blueprint.cost, "days": blueprint.days,
                        "paid_assistants": blueprint.assistants,
                        "wage_per_assistant": blueprint.wage_per_worker},
        "site_observation": ({"site_id": site_report.site_id, "observed_day": site_report.observed_day,
                              "integrity": site_report.integrity, "enabled": site_report.enabled,
                              "manifestation_id": site_report.manifestation_id}
                             if site_report else None),
        "local_observation": {
            "settlement_id": report.settlement_id,
            "observed_day": report.observed_day,
            "health": report.health,
            "missing_food": report.missing_food,
            "unrest": report.unrest,
            "recent_creature_attacks": recent_creature_attacks_for_report(world, report),
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
        f"provider decision required for {actor.kind}:{actor.id}: individual initiative affordance became stale"
    )


def _decision(world, option, event_type, content, *, causes):
    return record_event(world, event_type, content, fact_kind=FactKind.DECISION,
                        causal_origin=CausalOrigin.ACTOR_DECISION,
                        decision=option.decision(), cause_ids=tuple(causes))


async def _offer_turn(world, situation):
    parsed = _parse_offer_review(situation)
    if parsed is None:
        return False
    character_id, source_event_id = parsed
    character = world.society.characters.get(character_id)
    if character is None:
        return False
    lapse_stale_research_offers(world, character_id)
    rite_options = rite_offer_options(world, character_id)
    learning_options = _undecided_learning_offers(world, character_id)
    research_options = researcher_work_options(world, character_id)
    faith_options = adherence_options(world, EntityRef("character", character_id))
    if not rite_options and not learning_options and not research_options and not faith_options:
        return False
    report = (world.knowledge.settlement_report(EntityRef("character", character_id), rite_options[0].settlement_id)
              if rite_options else None)
    actor = EntityRef("character", character_id)
    situation_data = (_character_situation(world, character, report) if report is not None
                      else _character_self_situation(world, character, learning_options))
    situation_data["religious_identity"] = religious_context(world, actor)
    situation_data["learning_opportunities"] = [
        {"technology_id": option.technology_id, "host": option.host_ref.to_dict(),
         "settlement_id": option.settlement_id}
        for option in learning_options
    ]
    situation_data["site_observations"] = [
        {"site_id": observation.site_id, "observed_day": observation.observed_day,
         "integrity": observation.integrity, "enabled": observation.enabled,
         "manifestation_id": observation.manifestation_id}
        for option in rite_options
        if world.research.rite_blueprints[option.blueprint_id].kind in {"earth_shaping", "evocation"}
        and (observation := world.knowledge.site_report(actor, option.site_id)) is not None
    ]
    situation_data["research_offers"] = [
        {"technology": world.research.technologies[option.technology_id].name,
         "sponsor": option.owner_ref.to_dict(),
         "work_site": world.map.infrastructure_sites[option.site_id].name,
         "work_units": world.research.technologies[option.technology_id].required_units,
         "wage_per_worker_per_unit": world.research.technologies[option.technology_id].wage_per_worker}
        for option in research_options
    ]
    choices = ([{"id": option.id, "label": (
        f"Oferecer {world.research.rite_blueprints[option.blueprint_id].name} em {option.settlement_id}.")}
                for option in rite_options]
               + [{"id": option.id, "label": (
                   f"Oferecer instrução de {world.research.technologies[option.technology_id].name} "
                   f"em {option.settlement_id}.")}
                  for option in learning_options]
               + [{"id": option.id, "label": (
                   f"Aceitar trabalhar em {world.research.technologies[option.technology_id].name} "
                   f"em {world.map.infrastructure_sites[option.site_id].name}, por "
                   f"{world.research.technologies[option.technology_id].wage_per_worker} moedas por trabalhador/unidade, "
                   f"patrocinada por {option.owner_ref.id}.")}
                  for option in research_options]
               + [{"id": option.id, "label": f"Escolher adesão ao convite {option.invitation_id}; não concede poder físico."}
                  for option in faith_options])
    causes = tuple(sorted({cause for option in rite_options for cause in (option.report_event_id,)}
                          | {cause for option in learning_options for cause in option.source_event_ids}
                          | {cause for option in research_options
                             for cause in (option.authorization_event_id, option.sponsor_decision_id)}
                          | {world.knowledge.religious_invitation_notices[option.invitation_id].event_id
                             for option in faith_options}
                          | ({situation_data["religious_identity"]["own_affiliation"]["event_id"]}
                             if situation_data["religious_identity"]["own_affiliation"] else set())))
    selected, interpretation_ids = await _select(
        world, actor, situation_data, choices, causes=causes,
    )
    if selected == ai_decider.NO_ACTION:
        record_no_action_decision(
            world, "character_initiative_decided", "A pessoa decidiu não agir entre as iniciativas locais disponíveis.",
            actor, affordance_ids=(option["id"] for option in choices), cause_ids=causes,
        )
        return False
    if selected is None:
        return False
    fresh_faith = {item.id: item for item in adherence_options(world, actor)}
    option = fresh_faith.get(selected)
    if option is not None:
        notice = world.knowledge.religious_invitation_notices[option.invitation_id]
        decision = _decision(world, option, "religious_adherence_decided",
                             "A pessoa escolheu livremente uma adesão religiosa.",
                             causes=(*interpretation_ids, notice.event_id))
        try:
            accept_religious_adherence(world, actor, option.id, decision.id)
        except ValueError as exc:
            raise _stale(actor) from exc
        return True
    fresh_rites = {item.id: item for item in rite_offer_options(world, character_id)}
    fresh_learning = {item.id: item for item in _undecided_learning_offers(world, character_id)}
    option = fresh_rites.get(selected)
    if option is not None:
        offer = record_rite_offer(
            world, character_id, option.id,
            decision_source={"kind": "provider", "receipt_event_id": interpretation_ids[-1]},
            cause_ids=interpretation_ids)
        world.agenda.schedule(ScheduledSituation(_sponsor_review_id(offer.id), SPONSOR_REVIEW_KIND,
                                                 world.clock.absolute_day + 1))
        return True
    option = fresh_learning.get(selected)
    if option is not None:
        record_apprenticeship_offer(
            world, character_id, option.id,
            decision_source={"kind": "provider", "receipt_event_id": interpretation_ids[-1]},
            cause_ids=interpretation_ids,
        )
        return True
    fresh_research = {item.id: item for item in researcher_work_options(world, character_id)}
    option = fresh_research.get(selected)
    if option is not None:
        decision = record_event(
            world, "research_accepted", "O pesquisador aceitou uma proposta de trabalho remunerado.",
            fact_kind=FactKind.DECISION, causal_origin=CausalOrigin.ACTOR_DECISION,
            decision=option.decision(), cause_ids=(option.authorization_event_id, option.sponsor_decision_id),
        )
        try:
            accept_research_work(world, character_id, option.id, decision.id)
        except ValueError as exc:
            raise _stale(actor) from exc
        return True
    raise _stale(actor)


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
                [{"id": option.id, "label": (
                    f"Patrocinar {world.research.rite_blueprints[option.blueprint_id].name}.")}
                 for option in options],
                causes=(offer_event.id, report.event_id),
            )
            if selected == ai_decider.NO_ACTION:
                record_no_action_decision(
                    world, "rite_sponsorship_decided", "A instituição decidiu não patrocinar o rito neste turno.",
                    sponsor, affordance_ids=(option.id for option in options),
                    cause_ids=(offer_event.id, report.event_id),
                )
                continue
            if selected is None:
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
