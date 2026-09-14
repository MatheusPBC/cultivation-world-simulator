"""Bootstrap institutional bodies without inventing named AI characters."""

from src.classes.governance.authority import AuthorityState
from src.classes.governance.models import AuthorityOffice, TaxPolicy
from src.classes.mechanical_language import EntityRef
from src.classes.governance.strategy import StrategyState
from src.classes.governance.models import Objective


def create_authority(society):
    state = AuthorityState()
    for kind, registry in (("polity", society.polities), ("organization", society.organizations)):
        for identity in sorted(registry):
            ref = EntityRef(kind=kind, id=identity)
            office = AuthorityOffice(id=f"office:{kind}:{identity}", institution_ref=ref,
                                     holder_ref=ref, scopes=("trade", "supply", "taxation", "research", "diplomacy", "military") if kind == "polity" else ("trade", "supply", "research", "diplomacy"))
            state.offices[office.id] = office
    for polity_id in society.polities:
        state.tax_policies[polity_id] = TaxPolicy(id=polity_id, account_id=f"treasury:{polity_id}")
    return state


def create_strategy(society, economy):
    state = StrategyState()
    for settlement in sorted(society.settlements.values(), key=lambda s: s.id):
        if settlement.administrator_id:
            objective = Objective(id=f"supply:{settlement.id}", settlement_id=settlement.id,
                                  stock_id=economy.needs[settlement.id].stock_id,
                                  actor_ref=EntityRef(kind="polity", id=settlement.administrator_id))
            state.objectives[objective.id] = objective
    for facility in sorted(economy.facilities.values(), key=lambda f: f.id):
        stock = economy.stocks[facility.stock_id]
        for resource_id in sorted(economy.recipes[facility.recipe_id].inputs):
            objective = Objective(id=f"inputs:{stock.id}:{resource_id}", actor_ref=stock.owner_ref,
                                  settlement_id=stock.location_id, stock_id=stock.id,
                                  resource_id=resource_id, kind="maintain_production_inputs",
                                  motivation="Manter insumos para o trabalho produtivo.")
            state.objectives[objective.id] = objective
    return state
