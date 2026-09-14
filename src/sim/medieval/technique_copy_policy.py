"""One bounded provider turn over material technique-copy affordances.

The policy owns neither knowledge nor access.  It only lets an eligible actor
select one current ID and delegates the revalidation to ``technique_copy``.
No provider, invalid answer, or NO_ACTION opens no dated work.
"""

from src.classes.event import FactKind

from . import ai_decider
from .events import record_event
from .technique_copy import open_technique_copy, technique_copy_options


def _turn_available(world):
    return ai_decider.provider_available() and ai_decider.within_budget(world)


def _situation(world, actor, options):
    """Only the actor's owned/received evidence appears in its prompt."""
    sightings = {item.event_id: item for item in world.knowledge.technology_sightings_for_actor(
        actor, current_day=world.clock.absolute_day)}
    reports = {item.event_id: item for item in world.knowledge.site_reports.values()
               if item.recipient_ref == actor}
    return {
        "you_are": actor.to_dict(),
        "copy_opportunities": [
            {
                "technology_id": item.technology_id,
                "holder_ref": item.holder_ref.to_dict(),
                "site_id": item.site_id,
                "sighting_day": sightings[item.sighting_event_id].observed_day,
                "site_observed_day": reports[item.report_event_id].observed_day,
            }
            for item in options
            if item.sighting_event_id in sightings and item.report_event_id in reports
        ],
        "today": world.clock.absolute_day,
    }


async def review_technique_copies_with_provider(world):
    """At most one real-AI decision per eligible institution per boundary."""
    if not world.config.ai_enabled or not _turn_available(world):
        return False
    actors = sorted({item.recipient_ref for item in world.knowledge.technology_sightings.values()},
                    key=lambda item: (item.kind, item.id))
    changed = False
    for actor in actors:
        options = technique_copy_options(world, actor)
        if not options:
            continue
        choices = [{"id": item.id, "label": "Copiar a técnica observada por trabalho local já em curso."}
                   for item in options]
        causes = tuple(sorted({item.sighting_event_id for item in options}
                              | {item.report_event_id for item in options}
                              | {item.access_event_id for item in options}))
        selected = await ai_decider.select_option(
            world, actor, _situation(world, actor, options), choices, causes=causes)
        if selected in (None, ai_decider.NO_ACTION):
            continue
        option = next((item for item in options if item.id == selected), None)
        if option is None:
            continue
        decision = record_event(
            world, "technique_copy_decided", "Uma instituição selecionou uma cópia técnica permitida.",
            fact_kind=FactKind.DECISION, decision=option.decision(),
            # Never cite the LLM receipt: it interpreted a fact but did not
            # cause the material decision.
            cause_ids=causes,
        )
        try:
            open_technique_copy(world, actor, option.id, decision.id)
        except ValueError:
            # Recomposition in the owner keeps a stale selected ID harmless.
            continue
        changed = True
    return changed


__all__ = ["review_technique_copies_with_provider"]
