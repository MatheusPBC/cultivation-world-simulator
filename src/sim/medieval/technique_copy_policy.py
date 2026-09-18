"""One bounded provider turn over material technique-copy affordances.

The policy owns neither knowledge nor access.  It only lets an eligible actor
select one current ID and delegates the revalidation to ``technique_copy``.
No provider, invalid answer, or NO_ACTION opens no dated work.
"""

from .institutional_decision_turn import (DiscretionaryAdapter, _rotated,
                                          review_institutional_decision_turn_with_provider)
from .technique_copy import open_technique_copy, technique_copy_options


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


def _causes(world, option):
    return (option.sighting_event_id, option.report_event_id, option.access_event_id)


def technique_copy_actors(world):
    return sorted({item.recipient_ref for item in world.knowledge.technology_sightings.values()},
                  key=lambda item: (item.kind, item.id))


def technique_copy_adapters(on_executed=None):
    """The family's adapters; ``on_executed`` only reports that a material
    copy actually opened, for the standalone caller's boolean contract."""
    def _execute(world, actor, option_id, decision_event_id):
        option = next((item for item in technique_copy_options(world, actor) if item.id == option_id), None)
        if option is None:
            raise ValueError("stale or unknown technique copy option")
        open_technique_copy(world, actor, option.id, decision_event_id)
        if on_executed is not None:
            on_executed()

    return (DiscretionaryAdapter(
        name="technique_copy", family="technique_copy", options_fn=technique_copy_options,
        label_fn=lambda option: "Copiar a técnica observada por trabalho local já em curso.",
        causes_fn=_causes, execute_fn=_execute, situation_fn=_situation),)


async def review_technique_copies_with_provider(world):
    """At most one real-AI decision per eligible institution per boundary."""
    changed = {"value": False}
    adapters = technique_copy_adapters(on_executed=lambda: changed.__setitem__("value", True))
    await review_institutional_decision_turn_with_provider(
        world, adapters, actors=_rotated(world, technique_copy_actors(world)), situation_fn=_situation)
    return changed["value"]


__all__ = ["review_technique_copies_with_provider", "technique_copy_actors", "technique_copy_adapters"]
