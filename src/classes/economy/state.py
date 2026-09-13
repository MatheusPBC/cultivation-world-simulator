"""Single owner of goods, money and the material conditions of subsistence."""

from dataclasses import dataclass, field

from .models import Market, MoneyAccount, Payroll, ProductionFacility, Recipe, Resource, SettlementNeeds, Stock
from .serialization import EconomySerialization, REGISTRIES
from .logistics import CargoParcel, FreightOrder, RouteFlow, validate_logistics
from .expansion import ExpansionBlueprint, ExpansionProject, validate_expansions


@dataclass
class EconomyState(EconomySerialization):
    resources: dict[str, Resource] = field(default_factory=dict)
    recipes: dict[str, Recipe] = field(default_factory=dict)
    stocks: dict[str, Stock] = field(default_factory=dict)
    accounts: dict[str, MoneyAccount] = field(default_factory=dict)
    facilities: dict[str, ProductionFacility] = field(default_factory=dict)
    payrolls: dict[str, Payroll] = field(default_factory=dict)
    needs: dict[str, SettlementNeeds] = field(default_factory=dict)
    payments: dict[str, str] = field(default_factory=dict)
    freight_orders: dict[str, FreightOrder] = field(default_factory=dict)
    parcels: dict[str, CargoParcel] = field(default_factory=dict)
    route_flows: dict[str, RouteFlow] = field(default_factory=dict)
    markets: dict[str, Market] = field(default_factory=dict)
    expansion_blueprints: dict[str, ExpansionBlueprint] = field(default_factory=dict)
    expansions: dict[str, ExpansionProject] = field(default_factory=dict)

    def used_capacity(self, stock: Stock) -> int:
        return sum(self.resources[rid].bulk * amount for rid, amount in stock.goods.items())

    def validate(self, world=None) -> None:
        for name, model in REGISTRIES.items():
            registry = getattr(self, name)
            if not isinstance(registry, dict):
                raise ValueError(f"invalid {name} registry")
            for key, value in registry.items():
                if not isinstance(value, model) or key != value.id:
                    raise ValueError(f"invalid {name} key or value")
                # Frozen values contain mutable dictionaries; revalidate at boundaries.
                model.model_validate(value.model_dump(mode="json"))
        if "food" not in self.resources:
            raise ValueError("subsistence requires food")
        for recipe in self.recipes.values():
            if (set(recipe.inputs) | set(recipe.outputs)) - set(self.resources):
                raise ValueError("unknown recipe resource")
            if world is not None and recipe.required_technology_id and recipe.required_technology_id not in world.research.technologies:
                raise ValueError('unknown recipe technology')
        for market in self.markets.values():
            if set(market.prices) != set(self.resources):
                raise ValueError("market must quote the resource catalog")
            if any(not (self.resources[r].base_price + 3) // 4 <= price <= self.resources[r].base_price * 4
                   for r, price in market.prices.items()):
                raise ValueError("market price outside allowed bounds")
        for stock in self.stocks.values():
            if (set(stock.goods) | set(stock.last_event_ids)) - set(self.resources):
                raise ValueError("unknown stock resource")
            if self.used_capacity(stock) > stock.capacity:
                raise ValueError("storage capacity exceeded")
        for facility in self.facilities.values():
            if facility.stock_id not in self.stocks or facility.recipe_id not in self.recipes:
                raise ValueError("unknown facility stock or recipe")
            account = self.accounts.get(facility.payroll_account_id)
            if account is None or account.owner_ref != self.stocks[facility.stock_id].owner_ref:
                raise ValueError("payroll requires the employer's account")
        if len({need.stock_id for need in self.needs.values()}) != len(self.needs):
            raise ValueError("settlements cannot share a subsistence stock")
        for need in self.needs.values():
            if need.stock_id not in self.stocks or self.stocks[need.stock_id].location_id != need.id:
                raise ValueError("subsistence stock must be local")
        if not isinstance(self.payments, dict) or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in self.payments.items()):
            raise ValueError("invalid payment receipts")
        validate_logistics(self, world)
        validate_expansions(self, world)
        if world is None:
            return
        owners = {"polity": world.society.polities, "organization": world.society.organizations,
                  "character": world.society.characters, "settlement": world.society.settlements,
                  "population_group": world.society.population}
        events = {e.id: e for e in world.events}
        for item in (*self.stocks.values(), *self.accounts.values()):
            if item.owner_ref.id not in owners.get(item.owner_ref.kind, {}):
                raise ValueError("unknown economic owner")
        for payroll in self.payrolls.values():
            if (payroll.id not in {*self.facilities, *self.expansions, *world.research.projects} or payroll.day > world.clock.absolute_day
                    or payroll.last_event_id not in events
                    or set(payroll.workers_by_group) - set(world.society.population)):
                raise ValueError("invalid payroll provenance")
            event = events[payroll.last_event_id]
            expected_types = ({"income_tax_collected"} if payroll.tax else
                              {"wages_paid"} if payroll.gross else {"production_completed", "production_limited", "expansion_progressed"})
            if event.day != payroll.day or event.event_type not in expected_types:
                raise ValueError("invalid payroll event type or date")
        for stock in self.stocks.values():
            if stock.location_id not in world.society.settlements:
                raise ValueError("unknown stock location")
        if set(self.needs) != set(world.society.settlements):
            raise ValueError("each settlement requires subsistence state")
        if set(self.markets) != set(world.society.settlements) or any(
                m.updated_day > world.clock.absolute_day for m in self.markets.values()):
            raise ValueError("invalid local market state")
        for facility in self.facilities.values():
            site = world.map.infrastructure_sites.get(facility.site_id)
            stock = self.stocks[facility.stock_id]
            region_id = world.society.settlements[stock.location_id].region_id
            recipe = self.recipes[facility.recipe_id]
            if (site is None or region_id not in site.region_ids or site.owner_ref != stock.owner_ref
                    or recipe.capability_id not in site.capability_ids):
                raise ValueError("facility requires a local capable site and its owner's stock")
        provenance = [eid for s in self.stocks.values() for eid in s.last_event_ids.values()]
        provenance += [v.last_event_id for v in (*self.accounts.values(), *self.needs.values(), *self.facilities.values(), *self.markets.values()) if v.last_event_id]
        if any(eid not in events for eid in provenance):
            raise ValueError("unknown economy event provenance")
        for decision_id, event_id in self.payments.items():
            if (decision_id not in events or event_id not in events
                    or events[event_id].event_type not in {"payment_completed", "household_purchase_completed"}
                    or decision_id not in {link.cause_event_id for link in events[event_id].causal_links}):
                raise ValueError("invalid payment history")
        for event in world.events:
            if event.event_type != "household_purchase_completed":
                continue
            parties = [events[link.cause_event_id] for link in event.causal_links
                       if link.cause_event_id in events and events[link.cause_event_id].decision is not None]
            if (len(parties) != 2 or {p.decision.get("action") for p in parties} != {"buy_rations", "sell_rations"}
                    or any(self.payments.get(p.id) != event.id for p in parties)):
                raise ValueError("household purchase requires both decision receipts")
