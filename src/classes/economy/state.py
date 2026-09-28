"""Single owner of goods, money and the material conditions of subsistence."""

from dataclasses import dataclass, field

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef

from .models import (FamilyLoan, FamilyLoanRequest, FreightRecoveryCase, Market, MoneyAccount, Payroll, PermanentEmploymentContract,
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
    family_loan_requests: dict[str, FamilyLoanRequest] = field(default_factory=dict)
    family_loans: dict[str, FamilyLoan] = field(default_factory=dict)

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
        for request in self.family_loan_requests.values():
            account = self.accounts.get(request.account_id)
            if (account is None or account.owner_ref != request.borrower_ref
                    or request.settlement_id not in (world.society.settlements if world is not None else {request.settlement_id})
                    or request.principal <= 0):
                raise ValueError("family loan request requires the borrower's treasury")
            linked_loans = [self.family_loans.get(loan_id) for loan_id in request.family_loan_ids]
            if any(loan is None or loan.request_id != request.id for loan in linked_loans):
                raise ValueError("family loan request must name its funded loans")
            funded_principal = sum(loan.principal for loan in linked_loans if loan is not None)
            expected_status = (
                "open" if funded_principal == 0 else
                "partially_funded" if funded_principal < request.principal else
                "funded" if funded_principal == request.principal else "invalid"
            )
            if request.status != expected_status:
                raise ValueError("family loan request status must match contributed principal")
        for loan in self.family_loans.values():
            borrower = self.accounts.get(loan.borrower_account_id)
            lender = self.accounts.get(loan.lender_account_id)
            if (borrower is None or lender is None or borrower.owner_ref != loan.borrower_ref
                    or lender.owner_ref != loan.lender_ref or loan.request_id not in self.family_loan_requests):
                raise ValueError("family loan requires both canonical accounts and its request")
        for request_id in self.family_loan_requests:
            request_loans = [loan for loan in self.family_loans.values() if loan.request_id == request_id]
            lenders = [loan.lender_ref for loan in request_loans]
            if len(set(lenders)) != len(lenders):
                raise ValueError("a household may contribute only once to a family loan request")
            if {loan.id for loan in request_loans} != set(self.family_loan_requests[request_id].family_loan_ids):
                raise ValueError("family loan request and loan registry links disagree")
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
        for request in self.family_loan_requests.values():
            decision = events.get(request.decision_event_id)
            source = events.get(request.source_event_id)
            created = events.get(request.request_event_id)
            last = events.get(request.last_event_id)
            contract = (self.employment_contracts.get(request.employment_contract_id)
                        if request.employment_contract_id is not None else None)
            facility = (self.facilities.get(request.production_facility_id)
                        if request.production_facility_id is not None else None)
            production_stock = (self.stocks.get(facility.stock_id)
                                if facility is not None else None)
            production_recipe = (self.recipes.get(facility.recipe_id)
                                 if facility is not None else None)
            source_payload = source.causal_payload if source is not None else None
            production_payload = (source_payload.get("production")
                                  if isinstance(source_payload, dict) else None)
            production_limits = (production_payload.get("limits")
                                 if isinstance(production_payload, dict) else None)
            production_valid = (
                request.purpose == "food_production_payroll"
                and facility is not None and production_stock is not None
                and production_recipe is not None and "food" in production_recipe.outputs
                and facility.payroll_account_id == request.account_id
                and production_stock.location_id == request.settlement_id
                and production_stock.owner_ref == request.borrower_ref
                and production_payload is not None
                and source is not None and source.event_type == "production_limited"
                and production_payload.get("facility_id") == facility.id
                and production_payload.get("observed_day") == request.created_day
                and production_payload.get("batches") == 0
                and production_payload.get("limitations") == ["payroll_funds"]
                and isinstance(production_limits, dict)
                and production_limits.get("payroll_funds") == 0
                and all(value >= 1 for key, value in production_limits.items()
                        if key != "payroll_funds")
            )
            expected = {"action": "request_family_loan",
                        "actor_ref": request.borrower_ref.to_dict(),
                        "selected_affordance_id": request.selected_affordance_id}
            created_values = ({(delta.owner_kind, delta.owner_id, delta.aspect): delta.after
                               for delta in created.deltas} if created is not None else {})
            employment_valid = (
                request.purpose == "employment_payroll"
                and contract is not None
                and contract.employer_ref == request.borrower_ref
                and contract.settlement_id == request.settlement_id
                and contract.account_id == request.account_id
                and source is not None
                and source.event_type == "permanent_employment_unpaid"
            )
            if (decision is None or source is None or created is None or last is None
                    or not (employment_valid or production_valid)
                    or decision.fact_kind != FactKind.DECISION or decision.decision != expected
                    or decision.day != request.created_day
                    or created.event_type != "family_loan_requested"
                    or created_values.get(("family_loan_request", request.id, "purpose")) != request.purpose
                    or (request.production_facility_id is not None
                        and created_values.get(("family_loan_request", request.id, "production_facility_id"))
                        != request.production_facility_id)
                    or request.source_event_id not in {link.cause_event_id for link in created.causal_links}
                    or request.decision_event_id not in {link.cause_event_id for link in created.causal_links}
                    or source.day != request.created_day
                    or last.event_type not in {"family_loan_requested", "family_loan_funded"}
                    or (request.status == "open" and last.id != created.id)
                    or (request.status in {"partially_funded", "funded"}
                        and last.event_type != "family_loan_funded")
                    or request.created_day > world.clock.absolute_day
                    or request.expires_day <= request.created_day):
                raise ValueError("invalid family loan request provenance")
            request_loans = [loan for loan in self.family_loans.values() if loan.request_id == request.id]
            expected_loan_ids = {loan.id for loan in request_loans}
            funding_event_ids = {loan.funded_event_id for loan in request_loans}
            if expected_loan_ids != set(request.family_loan_ids):
                raise ValueError("family loan request links do not match funding history")
            if request.status != "open" and last.id not in funding_event_ids:
                raise ValueError("family loan request must point to its latest contribution")
            if request.status != "open" and not any(
                delta.owner_kind == "family_loan_request" and delta.owner_id == request.id
                and delta.aspect == "family_loan_ids" and delta.after == str(request.family_loan_ids)
                for delta in last.deltas
            ):
                raise ValueError("latest family loan request receipt lacks its contributions")
            total_funded = sum(loan.principal for loan in request_loans)
            expected_status = (
                "open" if total_funded == 0 else
                "partially_funded" if total_funded < request.principal else
                "funded" if total_funded == request.principal else "invalid"
            )
            if request.status != expected_status:
                raise ValueError("family loan request principal is inconsistent with its loans")
        for loan in self.family_loans.values():
            request = self.family_loan_requests.get(loan.request_id)
            decision = events.get(loan.decision_event_id)
            funded = events.get(loan.funded_event_id)
            last = events.get(loan.last_event_id)
            lender_notice = world.knowledge.family_loan_notices.get(loan.lender_notice_id)
            expected = {"action": "lend_to_polity", "actor_ref": loan.lender_ref.to_dict(),
                        "selected_affordance_id": loan.selected_affordance_id}
            if (request is None or decision is None or funded is None or last is None
                    or loan.id not in request.family_loan_ids
                    or request.status not in {"partially_funded", "funded"}
                    or decision.fact_kind != FactKind.DECISION or decision.decision != expected
                    or decision.day != loan.created_day or funded.event_type != "family_loan_funded"
                    or lender_notice is None or lender_notice.recipient_ref != loan.lender_ref
                    or loan.created_day > world.clock.absolute_day or loan.due_day <= loan.created_day):
                raise ValueError("invalid family loan funding provenance")
            if ((loan.status == "active" and last.id != funded.id)
                    or (loan.status == "repaid"
                        and loan.funded_event_id not in {link.cause_event_id for link in last.causal_links})):
                raise ValueError("family loan lifecycle receipt is not causally continuous")
            funding_delta = {delta.owner_id: int(delta.after) - int(delta.before)
                             for delta in funded.deltas
                             if delta.owner_kind == "account" and delta.aspect == "balance"}
            if funding_delta != {loan.borrower_account_id: loan.principal,
                                 loan.lender_account_id: -loan.principal}:
                raise ValueError("family loan must transfer existing money exactly")
            if not all(any(delta.owner_kind == "family_loan" and delta.owner_id == loan.id
                           and delta.aspect == aspect and delta.after == value
                           for delta in funded.deltas)
                       for aspect, value in (("principal", str(loan.principal)),
                                             ("due_day", str(loan.due_day)),
                                             ("request_id", loan.request_id),
                                             ("borrower_ref", str(loan.borrower_ref.to_dict())),
                                             ("lender_ref", str(loan.lender_ref.to_dict())))):
                raise ValueError("family loan terms lack a factual funding receipt")
            if loan.status == "repaid":
                repayment = events.get(loan.repayment_event_id)
                if (repayment is None or repayment.event_type != "family_loan_repaid"
                        or repayment.day < loan.due_day or repayment.day > world.clock.absolute_day
                        or last.id != repayment.id):
                    raise ValueError("invalid family loan repayment provenance")
                repayment_decision_id = (repayment.causal_payload.get("decision_event_id")
                                         if repayment.causal_payload else None)
                repayment_decision = events.get(repayment_decision_id)
                if (repayment_decision is None or repayment_decision.fact_kind != FactKind.DECISION
                        or repayment_decision.decision != {
                            "action": "repay_family_loan",
                            "actor_ref": loan.borrower_ref.to_dict(),
                            "selected_affordance_id": repayment.causal_payload.get("selected_affordance_id"),
                        }
                        or repayment_decision_id not in {link.cause_event_id for link in repayment.causal_links}):
                    raise ValueError("family loan repayment requires the borrower's decision")
                repayment_delta = {delta.owner_id: int(delta.after) - int(delta.before)
                                   for delta in repayment.deltas
                                   if delta.owner_kind == "account" and delta.aspect == "balance"}
                if repayment_delta != {loan.borrower_account_id: -loan.principal,
                                      loan.lender_account_id: loan.principal}:
                    raise ValueError("family loan repayment must return its exact principal")
            elif loan.repayment_event_id is not None:
                raise ValueError("active family loan cannot have a repayment receipt")
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
                                               "permanent_employment_unpaid", "permanent_employment_paused",
                                               "employment_staffing_changed"}):
                raise ValueError("invalid permanent employment contract provenance")
            staffing_change = events.get(contract.staffing_event_id) if contract.staffing_event_id else None
            if staffing_change is None:
                if contract.staffing_event_id is not None or contract.staffing_target != contract.workforce_limit:
                    raise ValueError("employment staffing target has no decision provenance")
            else:
                staffing_decision_id = staffing_change.causal_payload.get("decision_event_id")
                staffing_decision = events.get(staffing_decision_id)
                selected_id = staffing_change.causal_payload.get("selected_affordance_id")
                if (staffing_change.event_type != "employment_staffing_changed"
                        or staffing_change.fact_kind != FactKind.STATE_TRANSITION
                        or staffing_change.causal_origin != CausalOrigin.ACTOR_DECISION
                        or staffing_decision is None or staffing_decision.fact_kind != FactKind.DECISION
                        or staffing_decision.decision != {
                            "action": "set_permanent_employment_staffing",
                            "actor_ref": contract.employer_ref.to_dict(),
                            "selected_affordance_id": selected_id,
                        }
                        or staffing_decision_id not in {link.cause_event_id for link in staffing_change.causal_links}
                        or not any(delta.owner_kind == "employment_contract" and delta.owner_id == contract.id
                                   and delta.aspect == "staffing_target" and delta.after == str(contract.staffing_target)
                                   for delta in staffing_change.deltas)):
                    raise ValueError("invalid employment staffing decision provenance")
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
