"""Derived resource requirements; neither plans nor reports own material stock."""


def productive_demand(world, stock_id, resource_id):
    return sum(world.economy.recipes[f.recipe_id].inputs.get(resource_id, 0) * f.max_batches
               for f in world.economy.facilities.values() if f.stock_id == stock_id)


def objective_target(world, objective):
    if objective.kind == "maintain_food_reserve":
        monthly = world.society.population_at(objective.settlement_id)
    else:
        monthly = productive_demand(world, objective.stock_id, objective.resource_id)
    return (monthly * objective.reserve_months + construction_demand(world, objective.stock_id, objective.resource_id)
            + research_demand(world, objective.stock_id, objective.resource_id))


def research_demand(world, stock_id, resource_id):
    return sum((world.research.technologies[p.technology_id].required_units - p.completed_units)
               * world.research.technologies[p.technology_id].inputs.get(resource_id, 0)
               for p in world.research.projects.values() if p.stock_id == stock_id and p.stage not in {'completed', 'superseded'})


def construction_demand(world, stock_id, resource_id):
    return sum((world.economy.expansion_blueprints[p.blueprint_id].required_units - p.completed_units)
               * world.economy.expansion_blueprints[p.blueprint_id].inputs.get(resource_id, 0)
               for p in world.economy.expansions.values()
               if p.stage != 'completed' and world.economy.facilities[p.facility_id].stock_id == stock_id)


def reserve_quantity(world, stock_id, resource_id="food"):
    stock = world.economy.stocks[stock_id]
    monthly = productive_demand(world, stock_id, resource_id)
    if resource_id == "food" and world.economy.needs[stock.location_id].stock_id == stock.id:
        monthly += world.society.population_at(stock.location_id)
    months = max((o.reserve_months for o in world.strategy.objectives.values()
                  if o.actor_ref == stock.owner_ref and o.stock_id == stock_id and o.resource_id == resource_id), default=2)
    return months * monthly + construction_demand(world, stock_id, resource_id) + research_demand(world, stock_id, resource_id)
