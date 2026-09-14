"""Material coherence between the Map's sites and the repair obligations.

The Map stays the owner of integrity and operability; Economy stays the owner
of the projects that spend goods and wages. This validator only checks that a
site state which was changed by history carries the fact that changed it, and
that a repair obligation still refers to a real site, maintainer and blueprint.
"""

import json

from src.classes.event import FactKind


def site_aspect(site, aspect):
    return {"integrity": str(site.integrity), "enabled": str(site.enabled),
            "service_suspended": str(site.service_suspended),
            "owner_ref": json.dumps(site.owner_ref.to_dict(), sort_keys=True) if site.owner_ref else "None",
            "maintainer_ref": json.dumps(site.maintainer_ref.to_dict(), sort_keys=True) if site.maintainer_ref else "None"}.get(aspect)


def validate_infrastructure(world) -> None:
    events = {event.id: event for event in world.events}
    for site in world.map.infrastructure_sites.values():
        # Authored initial state has no receipt; anything changed since must.
        if site.last_event_id is None:
            continue
        event = events.get(site.last_event_id)
        if event is None or event.fact_kind != FactKind.STATE_TRANSITION or event.day > world.clock.absolute_day:
            raise ValueError("site state requires a dated material fact")
        deltas = [d for d in event.deltas if d.owner_kind == "site" and d.owner_id == site.id]
        if not deltas:
            raise ValueError("site provenance requires its own site delta")
        for delta in deltas:
            current = site_aspect(site, delta.aspect)
            if current is None or delta.after != current:
                raise ValueError("site state must match the value in its last receipt")
    for project in world.economy.repairs.values():
        site = world.map.infrastructure_sites.get(project.site_id)
        blueprint = world.economy.repair_blueprints.get(project.blueprint_id)
        if site is None or blueprint is None or blueprint.site_kind != site.kind:
            raise ValueError("repair requires its site and a blueprint for that kind of site")
        settlement = world.society.settlements.get(world.economy.stocks[project.stock_id].location_id)
        if settlement is None or settlement.region_id not in site.region_ids:
            raise ValueError("repair must be financed from a stock at the site")
        # A maintainer change or an intact site does not corrupt the history: the
        # executor revalidates authority and condition, and closes or blocks the
        # obligation without spending. An old project grants no authority by itself.
