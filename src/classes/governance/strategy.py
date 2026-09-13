"""Persistent institutional intentions, not cached affordances or inventories."""

from dataclasses import dataclass, field
from .models import Objective, StrategicPlan
from .serialization import RegistrySerialization, validate_actor


@dataclass
class StrategyState(RegistrySerialization):
    objectives: dict[str, Objective] = field(default_factory=dict)
    plans: dict[str, StrategicPlan] = field(default_factory=dict)
    registries = {"objectives": Objective, "plans": StrategicPlan}

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
        if len({(o.stock_id, o.resource_id) for o in self.objectives.values()}) != len(self.objectives):
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
