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
