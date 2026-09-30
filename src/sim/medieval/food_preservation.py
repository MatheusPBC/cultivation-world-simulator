"""Deterministic deterioration of exposed public food stores.

Only the public stock above the current settlement's monthly subsistence
reserve is exposed. A commissioned and operating smokehouse protects a bounded
amount derived from its physical integrity; this module neither owns the site
nor changes private pantries or cargo.
"""

from .economy import _apply_stock, _causes


MONTHLY_LOSS_PERMILLE = 5
SMOKEHOUSE_CAPACITY = 2_000
PRESERVATION_CAPABILITY = "food_preservation"


def protected_food_capacity(world, stock):
    """Return physical capacity belonging to this stock's local maintainer."""
    settlement = world.society.settlements.get(stock.location_id)
    if settlement is None:
        return 0, ()
    sites = []
    for site in world.map.infrastructure_sites.values():
        if (settlement.region_id not in site.region_ids
                or PRESERVATION_CAPABILITY not in site.capability_ids
                or not site.enabled or site.integrity <= 0
                or site.owner_ref != stock.owner_ref
                or site.maintainer_ref != stock.owner_ref):
            continue
        sites.append(site)
    capacity = sum(int(SMOKEHOUSE_CAPACITY * site.integrity) for site in sites)
    return capacity, tuple(sorted(sites, key=lambda item: item.id))


def deteriorate_public_food(world, need, public_required):
    """Apply the storage law to exposed surplus and return its receipt if any."""
    stock = world.economy.stocks[need.stock_id]
    before = stock.goods.get("food", 0)
    protected_capacity, sites = protected_food_capacity(world, stock)
    reserve = min(before, max(0, int(public_required)))
    protected = min(max(0, before - reserve), protected_capacity)
    exposed = max(0, before - reserve - protected)
    lost = exposed * MONTHLY_LOSS_PERMILLE // 1000
    if lost <= 0:
        return None

    causes = _causes(
        need.last_event_id,
        stock.last_event_ids.get("food"),
        *(site.last_event_id for site in sites),
    )
    payload = {
        "food_storage_loss": {
            "settlement_id": need.id,
            "stock_id": stock.id,
            "reserve_quantity": reserve,
            "protected_quantity": protected,
            "exposed_quantity": exposed,
            "loss_quantity": lost,
            "monthly_loss_permille": MONTHLY_LOSS_PERMILLE,
            "protection_site_ids": [site.id for site in sites],
            "observed_day": world.clock.absolute_day,
        }
    }
    if not causes:
        payload["root_premise"] = {
            "kind": "world_generation",
            "domain": "initial_public_food_storage",
            "source_refs": [
                {"kind": "stock", "id": stock.id},
                {"kind": "settlement_needs", "id": need.id},
                *({"kind": "infrastructure_site", "id": site.id} for site in sites),
            ],
            "observed_day": world.clock.absolute_day,
        }
    goods = dict(stock.goods)
    goods["food"] = before - lost
    settlement = world.society.settlements[need.id]
    return _apply_stock(
        world,
        stock,
        goods,
        "public_food_storage_loss",
        f"{settlement.name}: {lost} rações excedentes deterioraram no armazenamento público.",
        cause_ids=causes,
        causal_payload=payload,
    )
