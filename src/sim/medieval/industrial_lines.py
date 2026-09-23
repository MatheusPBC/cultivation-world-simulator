"""Commissioned production lines share the site's canonical stock and workforce."""
from src.classes.economy.models import ProductionFacility


def line_id(facility, blueprint):
    return f'line:{facility.site_id}:{blueprint.additional_recipe_id}'


def line_exists_or_planned(economy, facility, blueprint, exclude_project=None):
    recipe_id = blueprint.additional_recipe_id
    if not recipe_id:
        return False
    if line_id(facility, blueprint) in economy.facilities or any(f.site_id == facility.site_id and f.recipe_id == recipe_id for f in economy.facilities.values()):
        return True
    return any(p.id != exclude_project and p.stage != 'completed'
               and p.facility_id is not None
               and economy.facilities[p.facility_id].site_id == facility.site_id
               and economy.expansion_blueprints[p.blueprint_id].additional_recipe_id == recipe_id
               for p in economy.expansions.values())


def commission_line(economy, facility, blueprint, event_id):
    value = ProductionFacility(id=line_id(facility, blueprint), site_id=facility.site_id,
        stock_id=facility.stock_id, recipe_id=blueprint.additional_recipe_id, max_batches=blueprint.new_capacity,
        payroll_account_id=facility.payroll_account_id, wage_per_worker=facility.wage_per_worker, last_event_id=event_id)
    economy.facilities[value.id] = value
