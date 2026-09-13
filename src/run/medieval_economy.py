"""Initial economic holdings and standing production from authored content."""

import json
from pathlib import Path

from src.classes.economy import EconomyState
from src.classes.economy.models import Market, MoneyAccount, ProductionFacility, Recipe, Resource, SettlementNeeds, Stock
from src.classes.mechanical_language import EntityRef
from src.classes.economy.expansion import ExpansionBlueprint
from src.classes.economy.maintenance import RepairBlueprint

CATALOG_PATH = Path(__file__).resolve().parents[2] / "static/game_configs/medieval/economy.json"


def create_medieval_economy(society, *, catalog_path=CATALOG_PATH) -> EconomyState:
    data = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    if type(data["catalog_version"]) is not int or data["catalog_version"] != 1:
        raise ValueError("unsupported economy catalog")
    state = EconomyState()
    for name, model in (("resources", Resource), ("recipes", Recipe), ("facilities", ProductionFacility),
                        ("expansion_blueprints", ExpansionBlueprint), ("repair_blueprints", RepairBlueprint)):
        for raw in data[name]:
            value = model.model_validate(raw)
            if value.id in getattr(state, name):
                raise ValueError(f"duplicate catalog {name} ID")
            getattr(state, name)[value.id] = value
    for settlement in society.settlements.values():
        population = society.population_at(settlement.id)
        goods = dict(data["initial_public_goods"])
        for rid, amount in data["initial_public_goods_per_person"].items():
            goods[rid] = goods.get(rid, 0) + amount * population
        owner = (EntityRef("polity", settlement.administrator_id) if settlement.administrator_id
                 else EntityRef("settlement", settlement.id))
        stock = Stock(id=f"stock:{settlement.id}", owner_ref=owner, location_id=settlement.id,
                      capacity=population * data["public_storage_per_person"], goods=goods)
        state.stocks[stock.id] = stock
        state.needs[settlement.id] = SettlementNeeds(id=settlement.id, stock_id=stock.id)
        state.markets[settlement.id] = Market(id=settlement.id, prices={r.id: r.base_price for r in state.resources.values()})
    for polity in society.polities.values():
        account = MoneyAccount(id=f"treasury:{polity.id}", owner_ref=EntityRef("polity", polity.id), balance=data["polity_money"])
        state.accounts[account.id] = account
    for group in society.population.values():
        account = MoneyAccount(id=f"household:{group.id}", owner_ref=EntityRef("population_group", group.id), balance=0)
        state.accounts[account.id] = account
    for org in society.organizations.values():
        owner = EntityRef("organization", org.id)
        stock = Stock(id=f"stock:{org.id}", owner_ref=owner, location_id=org.seat_id,
                      capacity=data["organization_storage"], goods=data["initial_organization_goods"])
        account = MoneyAccount(id=f"treasury:{org.id}", owner_ref=owner, balance=data["organization_money"])
        state.stocks[stock.id], state.accounts[account.id] = stock, account
    state.validate()
    return state
