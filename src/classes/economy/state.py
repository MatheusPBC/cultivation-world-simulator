"""Single owner of goods, money and the material conditions of subsistence."""

from dataclasses import dataclass, field

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from .models import (FreightRecoveryCase, Market, MoneyAccount, Payroll, PermanentEmploymentContract,
                     ProductionFacility, ProductionPriority, Recipe, Resource, SettlementNeeds, Stock)
from .serialization import EconomySerialization, REGISTRIES
from .logistics import CargoParcel, FreightOrder, RouteFlow, validate_logistics
from .expansion import ExpansionBlueprint, ExpansionProject, validate_expansions
from .maintenance import RepairBlueprint, RepairProject, validate_repairs
from .investigation import Investigation, validate_investigations
from .migration import MigrationProvision
from .customs import CargoManifest, CustomsCheckpoint, validate_customs


@dataclass
class EconomyState(EconomySerialization):
    resources: dict[str, Resource] = field(default_factory=dict)
    recipes: dict[str, Recipe] = field(default_factory=dict)
    stocks: dict[str, Stock] = field(default_factory=dict)
    accounts: dict[str, MoneyAccount] = field(default_factory=dict)
    facilities: dict[str, ProductionFacility] = field(default_factory=dict)
    production_priorities: dict[str, ProductionPriority] = field(default_factory=dict)
    payrolls: dict[str, Payroll] = field(default_factory=dict)
    needs: dict[str, SettlementNeeds] = field(default_factory=dict)
    payments: dict[str, str] = field(default_factory=dict)
    freight_orders: dict[str, FreightOrder] = field(default_factory=dict)
    parcels: dict[str, CargoParcel] = field(default_factory=dict)
    route_flows: dict[str, RouteFlow] = field(default_factory=dict)
    markets: dict[str, Market] = field(default_factory=dict)
    expansion_blueprints: dict[str, ExpansionBlueprint] = field(default_factory=dict)
    expansions: dict[str, ExpansionProject] = field(default_factory=dict)
    repair_blueprints: dict[str, RepairBlueprint] = field(default_factory=dict)
    repairs: dict[str, RepairProject] = field(default_factory=dict)
    migration_provisions: dict[str, MigrationProvision] = field(default_factory=dict)
    customs_checkpoints: dict[str, CustomsCheckpoint] = field(default_factory=dict)
    cargo_manifests: dict[str, CargoManifest] = field(default_factory=dict)
    freight_recovery_cases: dict[str, FreightRecoveryCase] = field(default_factory=dict)
    investigations: dict[str, Investigation] = field(default_factory=dict)
    employment_contracts: dict[str, PermanentEmploymentContract] = field(default_factory=dict)

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
            for reading in (market.observed_supply, market.observed_demand):
                if (set(reading) - set(self.resources)
                        or any(type(amount) is not int or amount < 0 for amount in reading.values())):
                    raise ValueError("market readings must use non-negative catalog resources")
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
        for priority in self.production_priorities.values():
            facility = self.facilities.get(priority.facility_id)
            account = self.accounts.get(priority.payroll_account_id)
            stock = self.stocks.get(facility.stock_id) if facility is not None else None
            recipe = self.recipes.get(facility.recipe_id) if facility is not None else None
            if (facility is None or account is None or stock is None or recipe is None
                    or priority.owner_ref != account.owner_ref
                    or priority.owner_ref != stock.owner_ref
                    or facility.payroll_account_id != priority.payroll_account_id
                    or stock.location_id != priority.settlement_id
                    or recipe.occupation != priority.occupation):
                raise ValueError("production priority does not match its economic records")
        if len({contract.cohort_id for contract in self.employment_contracts.values()}) != len(self.employment_contracts):
            raise ValueError("a cohort cannot hold multiple permanent employment contracts")
        for contract in self.employment_contracts.values():
            account = self.accounts.get(contract.account_id)
            stock = self.stocks.get(contract.stock_id)
            site = world.map.infrastructure_sites.get(contract.work_site_id) if world is not None else None
            local_site = (site is not None and world is not None
                          and contract.settlement_id in {
                              settlement.id for settlement in world.society.settlements.values()
                              if settlement.region_id in site.region_ids
                          })
            if (account is None or stock is None or account.owner_ref != contract.employer_ref
                    or stock.owner_ref != contract.employer_ref or stock.location_id != contract.settlement_id
                    or (world is not None and (site is None or site.owner_ref != contract.employer_ref or not local_site))):
                raise ValueError("employment contract requires local employer site, stock and account")
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
        validate_repairs(self, world)
        validate_investigations(self, world)
        validate_customs(self, world)
        for provision in self.migration_provisions.values():
            if provision.account_id not in self.accounts:
                raise ValueError("migration provision requires its travel account")
        if world is None:
            return
        owners = {"polity": world.society.polities, "organization": world.society.organizations,
                  "character": world.society.characters, "settlement": world.society.settlements,
                  "population_group": world.society.population}
        events = world.event_index()
        for priority in self.production_priorities.values():
            owner = owners.get(priority.owner_ref.kind, {}).get(priority.owner_ref.id)
            facility = self.facilities[priority.facility_id]
            stock = self.stocks[facility.stock_id]
            recipe = self.recipes[facility.recipe_id]
            decision = events.get(priority.decision_event_id)
            last = events.get(priority.last_event_id)
            expected_owner = priority.owner_ref.to_dict()
            if (owner is None
                    or facility.payroll_account_id != priority.payroll_account_id
                    or stock.location_id != priority.settlement_id
                    or recipe.occupation != priority.occupation
                    or decision is None or last is None
                    or decision.fact_kind != FactKind.DECISION
                    or decision.day >= priority.effective_day
                    or decision.day > world.clock.absolute_day
                    or last.day > world.clock.absolute_day
                    or decision.decision is None
                    or decision.decision.get("action") != "set_production_priority"
                    or decision.decision.get("actor_ref") != expected_owner
                    or decision.decision.get("selected_affordance_id") != priority.selected_affordance_id
                    or last.event_type != "production_priority_selected"
                    or priority.decision_event_id not in {link.cause_event_id for link in last.causal_links}
                    or not any(delta.owner_kind == "production_priority" and delta.owner_id == priority.id
                               and delta.aspect == "selected_affordance_id"
                               and delta.after == priority.selected_affordance_id
                               for delta in last.deltas)):
                raise ValueError("invalid production priority provenance")
        if any(group.last_event_id is not None and group.last_event_id not in events
               for group in world.society.population.values()):
            raise ValueError("unknown population provenance")
        journeys = world.society.migrations
        if {item.journey_id for item in self.migration_provisions.values()} != set(journeys):
            raise ValueError("every active migration needs exactly one provision")
        for provision in self.migration_provisions.values():
            journey = journeys.get(provision.journey_id)
            account = self.accounts[provision.account_id]
            decision = events.get(journey.decision_event_id) if journey is not None else None
            expected = ({"action": "migrate", "actor_ref": EntityRef("population_group", journey.source_group_id).to_dict(),
                         "group_id": journey.source_group_id, "destination_id": journey.initial_destination_id,
                         "count": journey.count, "route_ids": list(journey.initial_route_ids)} if journey is not None else {})
            if (journey is None or journey.provision_id != provision.id or account.owner_ref != EntityRef("population_group", journey.source_group_id)
                    or provision.last_event_id not in events or journey.last_event_id not in events):
                raise ValueError("invalid migration material provenance")
            consumed = events.get(provision.consumed_event_id) if provision.consumed_event_id else None
            invalid_consumption = (provision.consumed_day is None) != (provision.consumed_event_id is None)
            if consumed is not None:
                invalid_consumption = invalid_consumption or (
                    consumed.event_type != "migration_rations_consumed"
                    or consumed.day != provision.consumed_day
                    or provision.consumed_day > world.clock.absolute_day
                    or not any(delta.owner_kind == "migration_provision" and delta.owner_id == provision.id
                               and delta.aspect == "consumed_day" and delta.after == str(provision.consumed_day)
                               for delta in consumed.deltas))
            if provision.consumed_event_id is not None and consumed is None:
                invalid_consumption = True
            if invalid_consumption:
                raise ValueError("invalid migration ration consumption provenance")
            if (decision is None or decision.fact_kind.name != "DECISION"
                    or any(decision.decision.get(key) != value for key, value in expected.items())):
                raise ValueError("invalid migration decision provenance")
            scheduled = world.agenda.get(journey.id)
            if journey.stage == "stranded":
                if scheduled is not None:
                    raise ValueError("stranded migration must await an explicit later action")
            elif (scheduled is None or scheduled.kind != "migration" or scheduled.due_day != journey.due_day
                  or journey.due_day <= world.clock.absolute_day):
                raise ValueError("migration agenda mismatch")
        if any(item["kind"] == "migration" and item["id"] not in journeys for item in world.agenda.to_dict()):
            raise ValueError("migration agenda references missing journey")
        for item in (*self.stocks.values(), *self.accounts.values()):
            if item.owner_ref.id not in owners.get(item.owner_ref.kind, {}):
                raise ValueError("unknown economic owner")
        for payroll in self.payrolls.values():
            if (payroll.id not in {*self.facilities, *self.expansions, *self.repairs, *self.investigations, *world.research.projects,
                                   *world.research.apprenticeships, *world.research.rites,
                                   *world.research.technique_copies,
                                   *world.society.detachments, *self.customs_checkpoints,
                                   *self.employment_contracts}
                    or payroll.day > world.clock.absolute_day
                    or payroll.last_event_id not in events
                    or set(payroll.workers_by_group) - set(world.society.population)):
                raise ValueError("invalid payroll provenance")
            event = events[payroll.last_event_id]
            expected_types = ({"income_tax_collected"} if payroll.tax else
                              {"customs_staff_paid"} if payroll.id in self.customs_checkpoints else
                              {"wages_paid"} if payroll.gross else
                              {"production_completed", "production_limited", "expansion_progressed",
                               "repair_progressed", "investigation_completed", "rite_completed"})
            if event.day != payroll.day or event.event_type not in expected_types:
                raise ValueError("invalid payroll event type or date")
        for contract in self.employment_contracts.values():
            group = world.society.population.get(contract.cohort_id)
            created = events.get(contract.created_event_id)
            decision = events.get(contract.decision_event_id)
            last = events.get(contract.last_event_id)
            expected_decision = {"action": "create_permanent_employment",
                                 "actor_ref": contract.employer_ref.to_dict(),
                                 "selected_affordance_id": contract.selected_affordance_id}
            if (group is None or contract.settlement_id not in world.society.settlements
                    or contract.created_day > world.clock.absolute_day
                    or contract.last_reviewed_day > world.clock.absolute_day
                    or created is None or decision is None or last is None
                    or decision.fact_kind != FactKind.DECISION or decision.decision != expected_decision
                    or created.event_type != "permanent_employment_created"
                    or created.day != contract.created_day
                    or contract.decision_event_id not in {link.cause_event_id for link in created.causal_links}
                    or not any(delta.owner_kind == "employment_contract" and delta.owner_id == contract.id
                               and delta.aspect == "created" and delta.before == "False" and delta.after == "True"
                               for delta in created.deltas)
                    or last.event_type not in {"permanent_employment_created", "permanent_employment_settled",
                                               "permanent_employment_unpaid"}):
                raise ValueError("invalid permanent employment contract provenance")
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
                    or events[event_id].event_type not in {"payment_completed", "export_tariff_collected", "household_purchase_completed", "household_provisions_purchased", "customs_fee_paid"}
                    or decision_id not in {link.cause_event_id for link in events[event_id].causal_links}):
                raise ValueError("invalid payment history")
        for event_type, actions in (("household_purchase_completed", {"buy_rations", "sell_rations"}),
                                    ("household_provisions_purchased", {"buy_household_provisions", "sell_household_provisions"})):
          for event in world.events_of_type(event_type):
            parties = [events[link.cause_event_id] for link in event.causal_links
                       if link.cause_event_id in events and events[link.cause_event_id].decision is not None
                       and events[link.cause_event_id].decision.get("action") in actions]
            terms = ("group_id", "stock_id", "quantity", "unit_price", "seller_account_id")
            if event.event_type == "household_provisions_purchased":
                terms += ("offer_id",)
            if (len(parties) != 2 or {p.decision.get("action") for p in parties} != actions
                    or any(self.payments.get(p.id) != event.id for p in parties)
                    or any(p.day != event.day for p in parties)
                    or len({tuple(p.decision.get(key) for key in terms) for p in parties}) != 1):
                raise ValueError("household purchase requires both decision receipts")
        for event in world.events_of_type("export_tariff_collected"):
            parties = [events[link.cause_event_id] for link in event.causal_links
                       if link.cause_event_id in events and events[link.cause_event_id].decision is not None
                       and events[link.cause_event_id].decision.get("action") in {"buy", "sell"}]
            terms = ("source_id", "destination_id", "resource_id", "quantity", "unit_price", "quote_day", "route_ids",
                     "seller_account_id", "buyer_account_id", "export_rate_permille", "export_policy_event_id",
                     "export_collector_ref", "total_price")
            if (len(parties) != 2 or {party.decision.get("action") for party in parties} != {"buy", "sell"}
                    or any(party.day != event.day for party in parties)
                    or any(parties[0].decision.get(key) != parties[1].decision.get(key) for key in terms)
                    or self.payments.get(next(party.id for party in parties if party.decision["action"] == "buy")) != event.id):
                raise ValueError("export tariff requires matching bilateral decisions")
            values = parties[0].decision
            rate, quantity, price = values["export_rate_permille"], values["quantity"], values["unit_price"]
            collector = values["export_collector_ref"]
            if (not isinstance(rate, int) or not isinstance(quantity, int) or not isinstance(price, int)
                    or not isinstance(collector, dict) or set(collector) != {"kind", "id"}):
                raise ValueError("invalid export tariff receipt terms")
            policy = world.authority.tax_policies.get(collector["id"])
            fee = (quantity * price * rate + 999) // 1000
            if (policy is None or values["total_price"] != quantity * price + fee
                    or values["export_policy_event_id"] not in {link.cause_event_id for link in event.causal_links}):
                raise ValueError("export tariff receipt lacks its policy quote")
            expected = {values["buyer_account_id"]: -values["total_price"], values["seller_account_id"]: quantity * price}
            expected[policy.account_id] = expected.get(policy.account_id, 0) + fee
            actual = {delta.owner_id: int(delta.after) - int(delta.before) for delta in event.deltas
                      if delta.owner_kind == "account" and delta.aspect == "balance"}
            if actual != {account_id: change for account_id, change in expected.items() if change}:
                raise ValueError("export tariff receipt account deltas are not conserved")
        self._validate_freight_recovery_cases(world, events)

    def _validate_freight_recovery_cases(self, world, events):
        """Validate persisted purchase-recovery records without rebuilding options."""
        for case in self.freight_recovery_cases.values():
            order = self.freight_orders.get(case.order_id)
            source, destination = self.stocks.get(case.source_id), self.stocks.get(case.destination_id)
            if (order is None or source is None or destination is None
                    or order.source_id != case.source_id or order.destination_id != case.destination_id
                    or order.resource_id != case.resource_id or order.quantity != case.quantity
                    or order.owner_ref != case.buyer_ref or source.owner_ref != case.seller_ref
                    or destination.owner_ref != case.buyer_ref):
                raise ValueError("freight recovery case does not match its purchase")
            if (case.payment_event_id not in events or self.payments.get(case.buy_decision_id) != case.payment_event_id
                    or case.original_freight_event_id not in events
                    or any(item not in events for item in case.blocked_event_ids)):
                raise ValueError("freight recovery case lacks payment or blockage provenance")
            buy = events.get(case.buy_decision_id)
            sell = events.get(case.sell_decision_id)
            payment = events.get(case.payment_event_id)
            opened = events.get(case.original_freight_event_id)
            expected_request = {"action": "request_paid_purchase_recovery",
                                "actor_ref": case.buyer_ref.to_dict(),
                                "selected_affordance_id": case.requested_option_id}
            if (buy is None or sell is None or payment is None or opened is None
                    or buy.fact_kind != FactKind.DECISION or sell.fact_kind != FactKind.DECISION
                    or (buy.decision or {}).get("action") != "buy"
                    or (sell.decision or {}).get("action") != "sell"
                    or payment.event_type not in {"payment_completed", "export_tariff_collected"}
                    or case.buy_decision_id not in {link.cause_event_id for link in payment.causal_links}
                    or case.sell_decision_id not in {link.cause_event_id for link in payment.causal_links}
                    or opened.event_type != "freight_opened"
                    or not any(delta.owner_kind == "cargo" and delta.owner_id == case.original_parcel_id
                               and delta.aspect == "quantity" and delta.after == str(case.quantity)
                               for delta in opened.deltas)
                    or case.request_decision_id not in events
                    or events[case.request_decision_id].decision != expected_request):
                raise ValueError("freight recovery case has invalid decision provenance")
            request = events[case.request_decision_id]
            if (request.fact_kind != FactKind.DECISION or request.day > world.clock.absolute_day
                    or request.causal_origin == CausalOrigin.LLM_INTERPRETATION
                    or case.last_event_id not in events):
                raise ValueError("freight recovery case request is invalid")
            response = events.get(case.response_decision_id) if case.response_decision_id else None
            last = events.get(case.last_event_id)
            if case.status == "requested":
                if response is not None or last.event_type != "purchase_recovery_requested":
                    raise ValueError("open freight recovery case has invalid receipt")
            elif case.status == "rejected":
                if (response is None or response.decision is None
                        or response.decision.get("action") != "respond_paid_purchase_recovery"
                        or last.event_type != "purchase_recovery_rejected"):
                    raise ValueError("rejected freight recovery case has invalid receipt")
            else:
                successor = self.freight_orders.get(case.successor_order_id)
                resolution = events.get(case.resolution_event_id)
                parcel = [item for item in self.parcels.values() if item.order_id == case.order_id]
                if (response is None or successor is None or resolution is None
                        or response.decision is None
                        or response.decision.get("action") != "respond_paid_purchase_recovery"
                        or successor.id == order.id or successor.quantity != case.quantity
                        or order.resolved_quantity != case.quantity or order.resolution_event_id != resolution.id
                        or parcel or resolution.event_type not in {"purchase_recovery_completed", "contraband_returned"}
                        or last.event_type != "purchase_recovery_completed"):
                    raise ValueError("completed freight recovery case has invalid resolution")
