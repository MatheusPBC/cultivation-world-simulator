"""Civil customs posts owned by the material economy.

A post is a staffed service at an already-existing port or mountain passage.
It neither grants military control nor changes the Map's route topology.
"""

from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue


Positive = int


class CustomsCheckpoint(SocietyValue):
    id: Identity
    site_id: Identity
    operator_ref: EntityRef
    account_id: Identity
    staff_group_id: Identity
    staff_count: int = Field(strict=True, gt=0)
    fee_per_bulk: int = Field(strict=True, gt=0)
    started_day: Count
    last_staffed_day: Count
    # Inspection capacity is consumed only by an attempted evasion.  This is
    # deliberately separate from staffing: staff remain paid labour, while a
    # slot is a dated, auditable use of that labour.
    inspection_day: Count
    inspection_slots_used: Count = 0
    last_event_id: Identity | None = None

    @model_validator(mode="after")
    def matches_site_identity(self):
        if self.id != f"customs:{self.site_id}":
            raise ValueError("customs checkpoint ID must name its site")
        if self.last_staffed_day < self.started_day:
            raise ValueError("customs staffing predates its opening")
        if self.inspection_day < self.started_day:
            raise ValueError("customs inspection predates its opening")
        return self


class CargoManifest(SocietyValue):
    """Immutable declaration of one existing held parcel.

    A manifest describes cargo; it does not move it or grant an exemption.
    The payment executor remains the only owner that can release the parcel.
    """
    id: Identity
    checkpoint_id: Identity
    parcel_id: Identity
    order_id: Identity
    owner_ref: EntityRef
    resource_id: Identity
    quantity: int = Field(strict=True, gt=0)
    declared_day: Count
    event_id: Identity

    @model_validator(mode="after")
    def names_its_parcel(self):
        if self.id != f"cargo_manifest:{self.parcel_id}":
            raise ValueError("cargo manifest ID must name its parcel")
        return self


def validate_customs(economy, world=None) -> None:
    """Cross-owner checks; current authority is deliberately not historical state."""
    if len({checkpoint.site_id for checkpoint in economy.customs_checkpoints.values()}) != len(economy.customs_checkpoints):
        raise ValueError("only one customs checkpoint may serve a site")
    if world is None:
        return
    events = world.event_index()
    for checkpoint in economy.customs_checkpoints.values():
        site = world.map.infrastructure_sites.get(checkpoint.site_id)
        account = economy.accounts.get(checkpoint.account_id)
        staff = world.society.population.get(checkpoint.staff_group_id)
        opening = next((event for event in events.values()
                        if event.event_type == "customs_opened" and event.day == checkpoint.started_day
                        and any(delta.owner_kind == "customs_checkpoint" and delta.owner_id == checkpoint.id
                                and delta.aspect == "opened" and delta.before == "False" and delta.after == "True"
                                for delta in event.deltas)), None)
        decision = next((events.get(link.cause_event_id) for link in opening.causal_links
                         if events.get(link.cause_event_id) is not None
                         and events[link.cause_event_id].fact_kind.name == "DECISION"
                         and isinstance(events[link.cause_event_id].decision, dict)
                         and events[link.cause_event_id].decision.get("option_id") is not None), None) if opening else None
        expected = {"action": "open_customs_checkpoint", "actor_ref": checkpoint.operator_ref.to_dict(),
                    "site_id": checkpoint.site_id, "account_id": checkpoint.account_id,
                    "staff_count": checkpoint.staff_count, "fee_per_bulk": checkpoint.fee_per_bulk}
        opening_staff_id = (decision.decision or {}).get("staff_group_id") if decision is not None else None
        reassigned = any(
            event.event_type == "workforce_transition_completed" and event.fact_kind.name == "STATE_TRANSITION"
            and any(delta.owner_kind == "customs_checkpoint" and delta.owner_id == checkpoint.id
                    and delta.aspect == "staff_group_id" and delta.after == checkpoint.staff_group_id
                    for delta in event.deltas)
            for event in events.values()
        )
        if (site is None or site.kind not in {"port", "mountain_pass"}
                or account is None
                or staff is None
                or checkpoint.started_day > world.clock.absolute_day
                or checkpoint.last_staffed_day > world.clock.absolute_day
                or (checkpoint.last_event_id is not None and checkpoint.last_event_id not in events)
                or opening is None or decision is None
                or (decision.decision or {}).get("option_id") is None
                or (opening_staff_id != checkpoint.staff_group_id and not reassigned)
                or any((decision.decision or {}).get(key) != value for key, value in expected.items())):
            raise ValueError("invalid customs checkpoint")
    # V1 has no checkpoint position along a route.  Refusing ambiguous maps is
    # safer than silently choosing the lexically first post.
    by_route = {}
    for checkpoint in economy.customs_checkpoints.values():
        site = world.map.infrastructure_sites.get(checkpoint.site_id)
        if site is None:
            continue
        for route_id in site.route_ids:
            if route_id in by_route:
                raise ValueError("only one customs checkpoint may serve a route in V1")
            by_route[route_id] = checkpoint.id
    for manifest in economy.cargo_manifests.values():
        event = events.get(manifest.event_id)
        parcel = economy.parcels.get(manifest.parcel_id)
        order = economy.freight_orders.get(manifest.order_id)
        decisions = [events.get(link.cause_event_id) for link in event.causal_links] if event else []
        expected = {"action": "declare_customs_manifest", "actor_ref": manifest.owner_ref.to_dict(),
                    "notice_id": f"customs_notice:{manifest.parcel_id}", "checkpoint_id": manifest.checkpoint_id,
                    "parcel_id": manifest.parcel_id, "order_id": manifest.order_id,
                    "resource_id": manifest.resource_id, "quantity": manifest.quantity}
        if (manifest.checkpoint_id not in economy.customs_checkpoints or order is None
                or order.owner_ref != manifest.owner_ref or order.resource_id != manifest.resource_id
                or manifest.declared_day > world.clock.absolute_day or event is None
                or event.day != manifest.declared_day or event.event_type != "cargo_manifest_declared"
                or event.fact_kind.name != "STATE_TRANSITION"
                or not any(item is not None and item.fact_kind.name == "DECISION"
                           and all((item.decision or {}).get(key) == value for key, value in expected.items())
                           for item in decisions)
                or not any(delta.owner_kind == "cargo_manifest" and delta.owner_id == manifest.id
                           and delta.aspect == "declared" and delta.before == "False" and delta.after == "True"
                           for delta in event.deltas)):
            raise ValueError("invalid cargo manifest")
        # A historical manifest must remain valid after its parcel has moved or
        # been delivered.  If it still exists, only its immutable identity may
        # be checked against the live parcel.
        if parcel is not None and (parcel.order_id != manifest.order_id or parcel.quantity <= 0):
            raise ValueError("manifest parcel identity changed")
