"""Material coherence between the Map's sites and the repair obligations.

The Map stays the owner of integrity and operability; Economy stays the owner
of the projects that spend goods and wages. This validator only checks that a
site state which was changed by history carries the fact that changed it, and
that a repair obligation still refers to a real site, maintainer and blueprint.
"""

import json

from src.classes.event import FactKind


def site_capabilities(site):
    """Canonical text of a site's physical capabilities, for receipts."""
    return ",".join(site.capability_ids)


def site_aspect(site, aspect):
    return {"integrity": str(site.integrity), "enabled": str(site.enabled),
            "service_suspended": str(site.service_suspended),
            # Physical capability is what makes a place able to host a line at
            # all, so a capability that history changed must prove it like any
            # other aspect the Map owns.
            "capability_ids": site_capabilities(site),
            "owner_ref": json.dumps(site.owner_ref.to_dict(), sort_keys=True) if site.owner_ref else "None",
            "maintainer_ref": json.dumps(site.maintainer_ref.to_dict(), sort_keys=True) if site.maintainer_ref else "None"}.get(aspect)


def _commissioned_capabilities(events):
    """Index the last capability receipt for every site in one history pass."""
    latest = {}
    for event in events.values():
        for delta in event.deltas:
            if delta.owner_kind == "site" and delta.aspect == "capability_ids":
                previous = latest.get(delta.owner_id)
                if previous is None or event.sequence > previous[0].sequence:
                    latest[delta.owner_id] = (event, delta)
    return latest


def validate_infrastructure(world) -> None:
    events = world.event_index()
    commissioned_by_site = _commissioned_capabilities(events)
    granted = {blueprint.grants_capability_id
               for blueprint in world.economy.expansion_blueprints.values()
               if blueprint.grants_capability_id}
    for site in world.map.infrastructure_sites.values():
        # A capability is a physical fact about a place, so its shape is
        # checked whether or not history ever touched this site.
        if (len(set(site.capability_ids)) != len(site.capability_ids)
                or any(not capability or not capability.strip() for capability in site.capability_ids)):
            raise ValueError("site capabilities must be unique and named")
        commissioned = commissioned_by_site.get(site.id)
        if commissioned is not None:
            receipt, delta = commissioned
            # A capability history created must still read exactly as the
            # receipt that created it, and must be one an authored blueprint
            # actually grants -- never a capability invented after the fact.
            if delta.after != site_capabilities(site):
                raise ValueError("site capabilities must match the receipt that commissioned them")
            if receipt.fact_kind != FactKind.STATE_TRANSITION or receipt.day > world.clock.absolute_day:
                raise ValueError("commissioned capabilities require a dated material fact")
            if any(capability not in granted for capability in site.capability_ids):
                raise ValueError("a commissioned site may only hold an authored blueprint capability")
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
