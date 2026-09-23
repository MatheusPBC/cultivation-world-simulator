"""Derived resource requirements; neither plans nor reports own material stock."""


def productive_demand(world, stock_id, resource_id):
    return sum(world.economy.recipes[f.recipe_id].inputs.get(resource_id, 0) * f.max_batches
               for f in world.economy.facilities.values() if f.stock_id == stock_id)


def objective_target(world, objective):
    if objective.kind == "maintain_food_reserve":
        monthly = world.society.population_at(objective.settlement_id)
    else:
        monthly = productive_demand(world, objective.stock_id, objective.resource_id)
    if objective.kind == "maintain_garrison_supply":
        monthly = 0
    return (monthly * objective.reserve_months + construction_demand(world, objective.stock_id, objective.resource_id)
            + research_demand(world, objective.stock_id, objective.resource_id)
            + repair_demand(world, objective.stock_id, objective.resource_id)
            + garrison_demand(world, objective.stock_id, objective.resource_id))


def research_demand(world, stock_id, resource_id):
    return sum((world.research.technologies[p.technology_id].required_units - p.completed_units)
               * world.research.technologies[p.technology_id].inputs.get(resource_id, 0)
               for p in world.research.projects.values() if p.stock_id == stock_id and p.stage not in {'completed', 'superseded'})


def repair_demand(world, stock_id, resource_id):
    """Remaining materials of open repair obligations financed by this stock.

    The need is measured by the maintainer's own last observation, never by the
    canonical condition of a site it may not have seen. An expired observation
    does not dissolve the commitment: the reserve keeps the last known estimate,
    while executing a batch still demands a valid report. A missing report is an
    invalid active repair, never a fictional one-batch requirement. An objective
    only makes the purchase possible; it never acquires anything.
    """
    from .infrastructure import missing_permille

    total = 0
    for project in world.economy.repairs.values():
        blueprint = world.economy.repair_blueprints.get(project.blueprint_id)
        if project.stock_id != stock_id or project.stage == 'completed' or blueprint is None:
            continue
        report = world.knowledge.site_report(project.maintainer_ref, project.site_id)
        amount = blueprint.inputs.get(resource_id, 0)
        if not amount:
            continue
        if report is None:
            raise ValueError("active repair requires a typed site report")
        total += -(-amount * missing_permille(report.integrity) // blueprint.restored_permille)
    return total


def garrison_demand(world, stock_id, resource_id):
    """Rations an institution chose to hold for a standing duty of its own.

    This reserves nothing by itself: it only raises the quantity the owner of
    this stock treats as already spoken for, so the column's food is not the
    first thing other demands consume. It never buys, recruits, marches, or
    keeps the duty alive -- an unpaid garrison still lapses on its own owner.
    """
    from .campaign_supply import RATIONS_PER_SOLDIER_DAY

    if resource_id != "food":
        return 0
    total = 0
    for objective in world.strategy.objectives.values():
        if objective.kind != "maintain_garrison_supply" or objective.stock_id != stock_id:
            continue
        garrison = world.society.garrisons.get(objective.garrison_id) if objective.garrison_id else None
        detachment = world.society.detachments.get(garrison.detachment_id) if garrison is not None else None
        if (garrison is None or garrison.stage != "active" or detachment is None
                or detachment.stage != "present" or detachment.owner_ref != objective.actor_ref):
            continue
        total += detachment.count * RATIONS_PER_SOLDIER_DAY * 30 * objective.reserve_months
    return total


def construction_demand(world, stock_id, resource_id):
    return sum((world.economy.expansion_blueprints[p.blueprint_id].required_units - p.completed_units)
               * world.economy.expansion_blueprints[p.blueprint_id].inputs.get(resource_id, 0)
               for p in world.economy.expansions.values()
               # A foundation has no anchor facility yet and names its own
               # feeding stock; an ordinary expansion reads its anchor's.
               if p.stage != 'completed' and (
                   p.stock_id if p.facility_id is None else world.economy.facilities[p.facility_id].stock_id
               ) == stock_id)


def reserve_quantity(world, stock_id, resource_id="food"):
    stock = world.economy.stocks[stock_id]
    monthly = productive_demand(world, stock_id, resource_id)
    if resource_id == "food" and world.economy.needs[stock.location_id].stock_id == stock.id:
        monthly += world.society.population_at(stock.location_id)
    months = max((o.reserve_months for o in world.strategy.objectives.values()
                  if o.kind not in {"defend_occupied_settlement", "maintain_garrison_supply"}
                  and o.actor_ref == stock.owner_ref
                  and o.stock_id == stock_id and o.resource_id == resource_id), default=2)
    return (months * monthly + construction_demand(world, stock_id, resource_id)
            + research_demand(world, stock_id, resource_id) + repair_demand(world, stock_id, resource_id)
            + garrison_demand(world, stock_id, resource_id))
