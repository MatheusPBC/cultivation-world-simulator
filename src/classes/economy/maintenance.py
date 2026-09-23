"""Repair obligations financed by real materials and paid local work.

The Map owns a site's integrity. This registry owns only the commitment to
restore it: which blueprint, whose stock and account, how much was already
restored and under which decision. Nothing here changes a site by itself.
"""

from typing import Annotated, Literal

from pydantic import Field
from src.classes.event import FactKind
from src.classes.governance.models import SiteReport
from src.classes.mechanical_language import EntityRef
from src.classes.society.models import SocietyValue, Identity, Count
from .models import Positive


class RepairBlueprint(SocietyValue):
    id: Identity
    name: Identity
    site_kind: Identity
    inputs: dict[Identity, Positive]
    workers: Positive
    wage_per_worker: Positive
    restored_permille: Annotated[int, Field(strict=True, ge=1, le=100)]


class RepairProject(SocietyValue):
    """``restored_permille`` is accumulated work, not the site's integrity.

    Later damage during an open project does not erase the work already paid
    for, so this total is uncapped; the physical ceiling of 1.0 integrity and
    the per-batch limit are enforced where the Map is actually changed.
    """
    id: Identity
    site_id: Identity
    blueprint_id: Identity
    maintainer_ref: EntityRef
    stock_id: Identity
    account_id: Identity
    decision_event_id: Identity
    started_day: Count
    restored_permille: Count = 0
    last_work_day: Count | None = None
    stage: Literal['waiting', 'repairing', 'blocked', 'completed'] = 'waiting'
    blocker: Identity | None = None
    last_event_id: Identity


def repair_intent(maintainer_ref, site_id, blueprint_id, stock_id, account_id):
    return {'action': 'repair_site', 'actor_ref': maintainer_ref.to_dict(), 'site_id': site_id,
            'blueprint_id': blueprint_id, 'stock_id': stock_id, 'account_id': account_id}


def batch_intent(maintainer_ref, project_id, units):
    return {'action': 'repair_batch', 'actor_ref': maintainer_ref.to_dict(),
            'project_id': project_id, 'units': units}


def validate_repairs(economy, world=None):
    events = world.event_index() if world is not None else {}
    for blueprint in economy.repair_blueprints.values():
        if not blueprint.inputs or set(blueprint.inputs) - set(economy.resources):
            raise ValueError('repair requires known materials')
    active = set()
    for project in economy.repairs.values():
        blueprint = economy.repair_blueprints.get(project.blueprint_id)
        stock = economy.stocks.get(project.stock_id)
        account = economy.accounts.get(project.account_id)
        if blueprint is None or stock is None or account is None:
            raise ValueError('unknown repair blueprint, stock or account')
        if stock.owner_ref != project.maintainer_ref or account.owner_ref != project.maintainer_ref:
            raise ValueError('repair must spend the maintainer\'s own stock and account')
        if project.id != f'repair:{project.decision_event_id}':
            raise ValueError('repair identity must name its own decision')
        if project.last_work_day is not None and (project.last_work_day <= project.started_day
                                                  or project.last_work_day % 30):
            raise ValueError('repair work must take time')
        if project.stage != 'completed':
            if project.site_id in active:
                raise ValueError('concurrent repair of a site')
            active.add(project.site_id)
        if world is None:
            continue
        decision = events.get(project.decision_event_id)
        if (project.started_day > world.clock.absolute_day or project.last_event_id not in events
                or (project.last_work_day is not None and project.last_work_day > world.clock.absolute_day)
                or decision is None or decision.fact_kind != FactKind.DECISION
                or decision.day != project.started_day
                or decision.decision != repair_intent(project.maintainer_ref, project.site_id,
                                                      project.blueprint_id, project.stock_id, project.account_id)):
            raise ValueError('invalid repair provenance')
        event = events[project.last_event_id]
        if project.stage != 'completed':
            report = world.knowledge.site_report(project.maintainer_ref, project.site_id)
            if not isinstance(report, SiteReport):
                raise ValueError('active repair requires a typed site report')
            try:
                world.knowledge._validate_site_report(world, events, report)
            except ValueError as exc:
                raise ValueError('active repair requires a valid site report receipt') from exc
        if project.last_work_day is None:
            if (project.restored_permille or project.stage != 'waiting'
                    or event.event_type != 'repair_started' or event.day != project.started_day
                    or project.decision_event_id not in {link.cause_event_id for link in event.causal_links}):
                raise ValueError('invalid repair start receipt')
        elif (event.event_type != 'repair_progressed' or event.day != project.last_work_day
              or not any(d.owner_kind == 'repair' and d.owner_id == project.id
                         and d.aspect == 'restored_permille' and d.after == str(project.restored_permille)
                         for d in event.deltas)
              or not any(d.owner_kind == 'repair' and d.owner_id == project.id
                         and d.aspect == 'stage' and d.after == project.stage for d in event.deltas)):
            raise ValueError('repair progress requires its material receipt')
