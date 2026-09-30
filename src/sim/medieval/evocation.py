"""Lifetime and single physical interception of the authored evoked bulwark.

The construct is non-sentient. Its finite energy comes from a completed paid
rite; a real creature impact spends it. It creates no people or material goods.
"""

from src.classes.event import FactKind
from .economy import _delta
from .events import record_event

MAX_ABSORPTION = 0.05
ABSORBED_FRACTION = 0.5


def active_manifestation(world, site_id):
    return next((item for _, item in sorted(world.research.manifestations.items())
                 if item.site_id == site_id and item.stage == "active"
                 and item.started_day <= world.clock.absolute_day < item.until_day), None)


def intercepted_damage(world, site_id, raw_magnitude):
    """Pure reading: option enumeration never spends a manifestation."""
    manifestation = active_manifestation(world, site_id)
    if raw_magnitude is None or manifestation is None:
        return raw_magnitude
    return raw_magnitude - min(MAX_ABSORPTION, raw_magnitude * ABSORBED_FRACTION)


def spend_manifestation(world, manifestation, event_id):
    """Called by the physical impact owner after emitting its exact delta."""
    current = active_manifestation(world, manifestation.site_id)
    event = world.event_index().get(event_id)
    if (current != manifestation or event is None or event.event_type != "creature_damaged_site"
            or event.day != world.clock.absolute_day
            or not any(d.owner_kind == "manifestation" and d.owner_id == current.id
                       and d.aspect == "stage" and d.before == "active" and d.after == "spent"
                       for d in event.deltas)):
        raise ValueError("manifestation spending requires its current material interception")
    world.research.manifestations[current.id] = current.model_copy(
        update={"stage": "spent", "last_event_id": event.id})
    world.agenda.cancel(current.id)


def resolve_manifestations(world, situations):
    """A finite construct dissipates on its actual expiry day, without refund."""
    for situation in situations:
        manifestation = world.research.manifestations.get(situation.id)
        if (manifestation is None or manifestation.stage != "active"
                or manifestation.until_day != world.clock.absolute_day
                or situation.kind != "manifestation"):
            raise ValueError("unknown or inconsistent manifestation expiry")
        event = record_event(world, "manifestation_expired", "O anteparo evocado se dissipou ao fim do prazo.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("manifestation", manifestation.id, "stage", "active", "expired"),),
                             cause_ids=(manifestation.last_event_id,))
        world.research.manifestations[manifestation.id] = manifestation.model_copy(
            update={"stage": "expired", "last_event_id": event.id})
        from .route_intelligence import refresh_site_reports
        refresh_site_reports(world, site_ids=(manifestation.site_id,), source_event_ids=(event.id,))
