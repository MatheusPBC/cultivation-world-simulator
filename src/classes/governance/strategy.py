"""Persistent institutional intentions, not cached affordances or inventories.

``StrategicCapacity`` is deliberately a read model over those intentions.  It
does not reserve people or goods, cache an affordance, or become a second
planner: an institution's capacity is only the current posture of the plans it
already owns.
"""

from dataclasses import dataclass, field
from .models import Objective, StrategicPlan
from .serialization import RegistrySerialization, validate_actor


@dataclass(frozen=True)
class StrategicCapacityDimension:
    """One engine-derived posture, with only references to persistent intent."""

    status: str
    objective_ids: tuple[str, ...]
    plan_ids: tuple[str, ...]
    source_ids: tuple[str, ...] = ()

    def to_dict(self):
        return {"status": self.status, "objective_ids": self.objective_ids,
                "plan_ids": self.plan_ids, "source_ids": self.source_ids}


@dataclass(frozen=True)
class StrategicCapacity:
    """Engine-derived capacity across intentions already present in the world.

    ``unavailable`` means that this vertical has no persistent objective;
    ``unreviewed`` means it has an intention but no plan yet; ``committed``
    names a plan in progress; ``ready`` names a satisfied or completed plan;
    and ``blocked`` preserves the most restrictive currently recorded state.
    These labels deliberately say nothing about a hidden inventory, troop
    count, or future affordance.
    """

    food_reserves: StrategicCapacityDimension
    productive_inputs: StrategicCapacityDimension
    territorial_defense: StrategicCapacityDimension
    administrative_bandwidth: StrategicCapacityDimension
    diplomatic_bandwidth: StrategicCapacityDimension
    military_command: StrategicCapacityDimension
    project_capacity: StrategicCapacityDimension
    logistics_capacity: StrategicCapacityDimension

    def to_dict(self):
        return {
            "food_reserves": self.food_reserves.to_dict(),
            "productive_inputs": self.productive_inputs.to_dict(),
            "territorial_defense": self.territorial_defense.to_dict(),
            "administrative_bandwidth": self.administrative_bandwidth.to_dict(),
            "diplomatic_bandwidth": self.diplomatic_bandwidth.to_dict(),
            "military_command": self.military_command.to_dict(),
            "project_capacity": self.project_capacity.to_dict(),
            "logistics_capacity": self.logistics_capacity.to_dict(),
        }


@dataclass
class StrategyState(RegistrySerialization):
    objectives: dict[str, Objective] = field(default_factory=dict)
    plans: dict[str, StrategicPlan] = field(default_factory=dict)
    registries = {"objectives": Objective, "plans": StrategicPlan}

    def capacity_for(self, actor_ref, world=None):
        """Derive a bounded strategy view for one actor from saved records.

        Capacity is intentionally not a registry: every field can be rebuilt
        after loading from ``objectives`` and ``plans``, so it cannot drift
        into a competing source of strategic truth.
        """
        def dimension(kinds):
            objectives = tuple(sorted(objective.id for objective in self.objectives.values()
                                      if objective.actor_ref == actor_ref and objective.kind in kinds))
            plans = tuple(sorted((plan for plan in self.plans.values() if plan.objective_id in objectives),
                                 key=lambda plan: plan.id))
            if not objectives:
                status = "unavailable"
            elif any(plan.stage == "blocked" for plan in plans):
                status = "blocked"
            elif any(plan.stage in {"acquire", "await_delivery", "adopted"} for plan in plans):
                status = "committed"
            elif plans and all(plan.stage in {"satisfied", "closed"} for plan in plans):
                status = "ready"
            else:
                status = "unreviewed"
            return StrategicCapacityDimension(
                status=status, objective_ids=objectives, plan_ids=tuple(plan.id for plan in plans))

        def owned(item):
            for field in ("owner_ref", "actor_ref", "employer_ref", "sponsor_ref", "debtor_ref",
                          "proposer_ref", "provider_ref"):
                if getattr(item, field, None) == actor_ref:
                    return True
            return False

        def derived(registries, active_stages, completed_stages=()):
            """Compose a read-only dimension from persisted records only.

            The records remain owned by their domains.  This helper merely
            projects their current lifecycle into a bounded posture; it never
            reserves a resource or creates a plan.
            """
            if world is None:
                return StrategicCapacityDimension("unavailable", (), ())
            records = []
            for registry_name in registries:
                registry = None
                for owner in (world, world.economy, world.research, world.society, world.relations):
                    registry = getattr(owner, registry_name, None)
                    if registry is not None:
                        break
                if isinstance(registry, dict):
                    records.extend(item for item in registry.values() if owned(item))
            if not records:
                return StrategicCapacityDimension("unavailable", (), ())
            ids = tuple(sorted(item.id for item in records if getattr(item, "id", None)))
            stages = tuple(getattr(item, "stage", getattr(item, "status", None)) for item in records)
            if any(stage in active_stages for stage in stages) or any(stage is None for stage in stages):
                status = "committed"
            elif completed_stages and all(stage in completed_stages for stage in stages if stage is not None):
                status = "ready"
            else:
                status = "unreviewed"
            return StrategicCapacityDimension(status, (), (), ids)

        return StrategicCapacity(
            food_reserves=dimension({"maintain_food_reserve"}),
            productive_inputs=dimension({"maintain_production_inputs"}),
            territorial_defense=dimension({"defend_occupied_settlement"}),
            administrative_bandwidth=derived(
                ("employment_contracts", "civic_movements", "civic_strikes"),
                {"active", "negotiating", "training"}, {"completed", "dissolved", "withdrawn"}),
            diplomatic_bandwidth=derived(
                ("proposals", "obligations"),
                {"offered", "accepted", "active"}, {"fulfilled", "expired", "breached", "remediated"}),
            military_command=derived(
                ("detachments", "force_standoffs", "siege_campaigns", "garrisons"),
                {"present", "active", "preparing", "underway"}, {"withdrawn", "completed", "collapsed"}),
            project_capacity=derived(
                ("projects", "expansions", "repairs", "investigations", "apprenticeships", "rites", "technique_copies"),
                {"waiting", "researching", "blocked", "underway", "training", "officiating", "copying"},
                {"completed", "closed", "failed", "superseded"}),
            logistics_capacity=derived(
                ("freight_orders", "parcels", "migration_provisions", "cargo_manifests"),
                {"waiting", "traveling", "unloading", "held", "active"},
                {"delivered", "resolved", "completed", "returned", "seized"}),
        )

    def validate(self, world=None):
        super().validate(world)
        if len({p.objective_id for p in self.plans.values()}) != len(self.plans):
            raise ValueError("objective cannot have concurrent supply plans")
        for plan in self.plans.values():
            if plan.objective_id not in self.objectives or len(set(plan.order_ids)) != len(plan.order_ids):
                raise ValueError("invalid plan objective or duplicate order")
        if world is None:
            return
        events = {e.id: e for e in world.events}
        for objective in self.objectives.values():
            validate_actor(world, objective.actor_ref)
            if objective.settlement_id not in world.society.settlements:
                raise ValueError("unknown strategic target")
            stock = world.economy.stocks.get(objective.stock_id)
            if (stock is None or stock.location_id != objective.settlement_id
                    or objective.resource_id not in world.economy.resources):
                raise ValueError("unknown strategic stock or resource")
            if objective.kind == "maintain_food_reserve" and (
                    objective.resource_id != "food" or world.economy.needs[objective.settlement_id].stock_id != stock.id):
                raise ValueError("food objective requires the public subsistence stock")
            if objective.kind == "defend_occupied_settlement" and (
                    objective.resource_id != "food" or world.economy.needs[objective.settlement_id].stock_id != stock.id):
                raise ValueError("defense objective requires the observed settlement stock")
        supply_objectives = [objective for objective in self.objectives.values()
                             if objective.kind != "defend_occupied_settlement"]
        if len({(o.stock_id, o.resource_id) for o in supply_objectives}) != len(supply_objectives):
            raise ValueError("duplicate stock-resource objective")
        for plan in self.plans.values():
            if plan.last_event_id not in events or plan.last_review_day > world.clock.absolute_day:
                raise ValueError("invalid strategic provenance")
            objective = self.objectives[plan.objective_id]
            for oid in plan.order_ids:
                order = world.economy.freight_orders.get(oid)
                if (order is None or order.owner_ref != objective.actor_ref or order.resource_id != objective.resource_id
                        or order.destination_id != objective.stock_id):
                    raise ValueError("plan references another objective's freight")
            if objective.kind == "defend_occupied_settlement":
                if plan.order_ids or plan.stage not in {"adopted", "closed", "blocked"}:
                    raise ValueError("invalid defense plan material state")
                adopted = [event for event in events.values() if event.event_type == "strategy_defense_adopted"
                           and any(delta.owner_kind == "strategy_objective" and delta.owner_id == objective.id
                                   for delta in event.deltas)]
                report_id = f"settlement_report:{objective.actor_ref.kind}:{objective.actor_ref.id}:{objective.settlement_id}"
                if not any(any(cause.event_type == "settlement_observed"
                               and any(delta.owner_kind == "settlement_report" and delta.owner_id == report_id
                                       and delta.aspect == "observation" for delta in cause.deltas)
                               for cause in (events.get(link.cause_event_id) for link in event.causal_links)
                               if cause is not None)
                           for event in adopted):
                    raise ValueError("defense objective lacks its settlement report source")
