"""Material damage and repair of installations the Map owns.

Damage is never invented here: it is applied from a prepared material fact
that already carries the exact site delta. Repair is an obligation financed
by the maintainer's own local stock, account and paid artisans, revalidated
on every monthly batch. Restoration is gradual and never lifts an
interdiction: turning ``enabled`` back on is an authority decision, not work.
"""

import math

from src.classes.economy.maintenance import RepairProject, batch_intent, repair_intent
from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.classes.governance.models import SiteReport
from src.classes.governance.authority import can_actor_act_for, require_authority
from src.classes.governance.models import Objective
from .economy import _apply_stock, _causes, _delta
from .events import record_event
from .labor import settle_work

OBSERVATION_DAYS = 30


def _event(world, event_id):
    if not isinstance(event_id, str) or not event_id.startswith("event:"):
        return None
    position = event_id.partition(":")[2]
    if not position.isdecimal() or not 1 <= int(position) <= len(world.events):
        return None
    event = world.events[int(position) - 1]
    return event if event.id == event_id else None


def missing_permille(integrity):
    """Work still needed, without quantizing the physical value for free."""
    return math.ceil(max(0.0, 1.0 - integrity) * 1000)


def local_holdings(world, actor_ref, site):
    """The maintainer's own stock and account at the place of the site."""
    stock = next((s for _, s in sorted(world.economy.stocks.items())
                  if s.owner_ref == actor_ref
                  and world.society.settlements[s.location_id].region_id in site.region_ids), None)
    account = next((a for _, a in sorted(world.economy.accounts.items()) if a.owner_ref == actor_ref), None)
    return stock, account


def site_blueprint(world, site):
    return next((b for _, b in sorted(world.economy.repair_blueprints.items()) if b.site_kind == site.kind), None)


def current_observation(world, actor_ref, site_id):
    report = world.knowledge.site_report(actor_ref, site_id)
    if not isinstance(report, SiteReport):
        return None
    try:
        # A registry entry is not evidence by itself.  Recheck the receipt here
        # because this executor can be called directly, outside the runner's
        # whole-world validation boundary.
        world.knowledge._validate_site_report(world, {event.id: event for event in world.events}, report)
    except ValueError:
        return None
    if not 0 <= world.clock.absolute_day - report.observed_day < OBSERVATION_DAYS:
        return None
    return report


def damage_site(world, site_id, *, event_id):
    """Apply a prepared material fact; prose and decisions never damage a site."""
    site = world.map.infrastructure_sites.get(site_id)
    event = _event(world, event_id)
    if (site is None or event is None or event.fact_kind != FactKind.STATE_TRANSITION
            or event.causal_origin != CausalOrigin.DETERMINISTIC
            or event.day != world.clock.absolute_day or site.last_event_id == event.id):
        raise ValueError("site damage requires an existing site and a material fact")
    deltas = [d for d in event.deltas if d.owner_kind == "site" and d.owner_id == site_id]
    if not deltas or len({d.aspect for d in deltas}) != len(deltas):
        raise ValueError("site damage requires its own exact site delta")
    updates = {}
    for delta in deltas:
        if delta.aspect not in {"integrity", "enabled"}:
            raise ValueError("a site fact can only change integrity or operability")
        if delta.before != {"integrity": str(site.integrity), "enabled": str(site.enabled)}[delta.aspect]:
            raise ValueError("site delta does not match the current site state")
        if delta.aspect == "integrity":
            value = float(delta.after)
            if not 0.0 <= value < site.integrity:
                raise ValueError("damage must lower integrity within the physical range")
            updates["integrity"] = value
        else:
            if delta.after != "False" or not site.enabled:
                raise ValueError("this fact can only interdict an operating site")
            updates["enabled"] = False
    site.update_runtime(**updates, last_event_id=event.id)
    return site


def start_repair(world, site_id, blueprint_id, *, decision_event_id):
    economy = world.economy
    economy.validate(world)
    site = world.map.infrastructure_sites.get(site_id)
    blueprint = economy.repair_blueprints.get(blueprint_id)
    if site is None or blueprint is None or blueprint.site_kind != site.kind or site.maintainer_ref is None:
        raise ValueError("repair requires a known site with an explicit maintainer and its blueprint")
    maintainer = site.maintainer_ref
    stock, account = local_holdings(world, maintainer, site)
    decision = _event(world, decision_event_id)
    if (stock is None or account is None or decision is None or decision.fact_kind != FactKind.DECISION
            or decision.day != world.clock.absolute_day
            or decision.decision != repair_intent(maintainer, site_id, blueprint_id, stock.id, account.id)):
        raise ValueError("repair requires the maintainer's own exact current decision and local holdings")
    project_id = f"repair:{decision_event_id}"
    if project_id in economy.repairs or any(p.site_id == site_id and p.stage != "completed"
                                            for p in economy.repairs.values()):
        raise ValueError("repair decision already used or site already under repair")
    require_authority(world, maintainer, "supply")
    require_authority(world, maintainer, "trade")
    report = current_observation(world, maintainer, site_id)
    if report is None or report.integrity >= 1.0:
        raise ValueError("repair requires the maintainer's own valid observation of the damage")
    if site.integrity >= 1.0:
        # The observation was honest but the site is already intact: no obligation
        # is created, and a stale belief is not treated as a technical failure.
        return None
    event = record_event(world, "repair_started",
                         f"{site.name}: reparo autorizado; nenhuma recuperação ainda executada.",
                         fact_kind=FactKind.STATE_TRANSITION,
                         deltas=(_delta("repair", project_id, "stage", None, "waiting"),),
                         cause_ids=_causes(decision_event_id, report.event_id, site.last_event_id))
    project = RepairProject(id=project_id, site_id=site_id, blueprint_id=blueprint_id, maintainer_ref=maintainer,
                            stock_id=stock.id, account_id=account.id, decision_event_id=decision_event_id,
                            started_day=world.clock.absolute_day, last_event_id=event.id)
    economy.repairs[project.id] = project
    return project


def _limits(world, project, site, blueprint, stock, account, available, report):
    units = blueprint.restored_permille
    limits = {"condition": missing_permille(site.integrity), "schedule": units}
    for resource_id, amount in blueprint.inputs.items():
        limits[f"input:{resource_id}"] = stock.goods.get(resource_id, 0) * units // amount
    artisans = sum(available.get(g.id, 0) for g in world.society.population.values()
                   if g.settlement_id == stock.location_id and g.occupation == "artisan")
    limits["labor"] = artisans * units // blueprint.workers
    limits["payroll_funds"] = (account.balance // blueprint.wage_per_worker) * units // blueprint.workers
    if (site.maintainer_ref != project.maintainer_ref or stock.owner_ref != project.maintainer_ref
            or account.owner_ref != project.maintainer_ref
            or any(not can_actor_act_for(world, project.maintainer_ref, project.maintainer_ref, scope)
                   for scope in ("supply", "trade"))):
        limits["authority"] = 0
    if world.society.settlements[stock.location_id].region_id not in site.region_ids:
        limits["locality"] = 0
    if report is None:
        limits["observation"] = 0
    return limits


def _reason(world, blocker):
    if blocker.startswith("input:"):
        return f"faltam materiais: {world.economy.resources[blocker[6:]].name}"
    return {"condition": "instalação já recuperada", "schedule": "lote mensal esgotado",
            "labor": "sem artesãos disponíveis", "payroll_funds": "sem saldo para salários",
            "authority": "sem autoridade ou posse vigente", "locality": "sem base local no sítio",
            "observation": "sem observação própria válida"}[blocker]


def _progress_repair(world, project, available, day):
    economy = world.economy
    site = world.map.infrastructure_sites[project.site_id]
    blueprint = economy.repair_blueprints[project.blueprint_id]
    stock, account = economy.stocks[project.stock_id], economy.accounts[project.account_id]
    report = current_observation(world, project.maintainer_ref, project.site_id)
    limits = _limits(world, project, site, blueprint, stock, account, available, report)
    units = min(limits.values())
    blocker = next((name for name in sorted(limits) if limits[name] == 0), None)
    restored = project.restored_permille + units
    integrity = min(1.0, site.integrity + units / 1000)
    stage = "completed" if integrity >= 1.0 else "repairing" if units else "blocked"
    if not units:
        event = record_event(world, "repair_progressed",
                             f"{site.name}: reparo impedido; {_reason(world, blocker)}.",
                             fact_kind=FactKind.STATE_TRANSITION,
                             deltas=(_delta("repair", project.id, "restored_permille", restored, restored),
                                     _delta("repair", project.id, "stage", project.stage, stage)),
                             cause_ids=_causes(project.last_event_id, site.last_event_id,
                                               report.event_id if report else None))
        economy.repairs[project.id] = project.model_copy(update={
            "stage": stage, "blocker": blocker, "last_work_day": day, "last_event_id": event.id})
        return
    # Executing a batch is its own current decision, revalidated above.
    decision = record_event(world, "repair_batch_decided",
                            f"{site.name}: executar lote de reparo de {units / 10:g}% da instalação.",
                            fact_kind=FactKind.DECISION,
                            decision=batch_intent(project.maintainer_ref, project.id, units),
                            # The decider cites what it knows: its obligation, its own
                            # observation and its own account, never an unobserved fact.
                            cause_ids=_causes(project.last_event_id, report.event_id, account.last_event_id))
    goods = dict(stock.goods)
    for resource_id, amount in blueprint.inputs.items():
        goods[resource_id] = goods.get(resource_id, 0) - math.ceil(amount * units / blueprint.restored_permille)
    workers = math.ceil(blueprint.workers * units / blueprint.restored_permille)
    event = _apply_stock(world, stock, goods, "repair_progressed",
                         f"{site.name}: integridade restaurada para {round(integrity * 100)}%.",
                         extra_deltas=(_delta("repair", project.id, "restored_permille",
                                              project.restored_permille, restored),
                                       _delta("repair", project.id, "stage", project.stage, stage),
                                       _delta("site", site.id, "integrity", site.integrity, integrity)),
                         cause_ids=_causes(decision.id, project.last_event_id, site.last_event_id,
                                           report.event_id, account.last_event_id))
    settle_work(world, work_id=project.id, account_id=project.account_id, stock_id=project.stock_id,
                occupation="artisan", worker_count=workers, wage=blueprint.wage_per_worker,
                available=available, production_event_id=event.id)
    site.update_runtime(integrity=integrity, last_event_id=event.id)
    economy.repairs[project.id] = project.model_copy(update={
        "restored_permille": restored, "stage": stage, "blocker": None,
        "last_work_day": day, "last_event_id": event.id})


def progress_repairs(world, available):
    """Monthly work on open obligations; a deadline alone never restores anything."""
    world.economy.validate(world)
    day = world.clock.absolute_day
    if day % 30:
        return
    for project in sorted(world.economy.repairs.values(), key=lambda p: p.id):
        if project.stage == "completed" or project.started_day >= day or project.last_work_day == day:
            continue
        _progress_repair(world, project, available, day)


def review_maintenance(world):
    """Deterministic policy: a maintainer that saw its own damage may authorize work."""
    for site_id in sorted(world.map.infrastructure_sites):
        site = world.map.infrastructure_sites[site_id]
        maintainer = site.maintainer_ref
        # The intention comes from the maintainer's own observation, not from the
        # canonical condition; the owner revalidates before any obligation exists.
        if (maintainer is None
                or any(p.site_id == site_id and p.stage != "completed" for p in world.economy.repairs.values())):
            continue
        blueprint = site_blueprint(world, site)
        report = current_observation(world, maintainer, site_id)
        stock, account = local_holdings(world, maintainer, site)
        if (blueprint is None or report is None or report.integrity >= 1.0 or stock is None or account is None
                or any(not can_actor_act_for(world, maintainer, maintainer, scope) for scope in ("supply", "trade"))):
            continue
        decision = record_event(world, "repair_decided", f"{site.name}: autorizar o reparo da instalação.",
                                fact_kind=FactKind.DECISION,
                                decision=repair_intent(maintainer, site_id, blueprint.id, stock.id, account.id),
                                cause_ids=_causes(report.event_id))
        project = start_repair(world, site_id, blueprint.id, decision_event_id=decision.id)
        if project is not None:
            _hold_material_objectives(world, project, blueprint, stock)


def _hold_material_objectives(world, project, blueprint, stock):
    """Reuse the standing supply mechanism so missing materials can be bought.

    The objective only makes procurement possible: no material is acquired here,
    and an unmet objective stays visibly unmet instead of silently stalling.
    """
    for resource_id in sorted(blueprint.inputs):
        identity = f"inputs:{stock.id}:{resource_id}"
        if identity in world.strategy.objectives:
            continue
        world.strategy.objectives[identity] = Objective(
            id=identity, actor_ref=project.maintainer_ref, settlement_id=stock.location_id,
            stock_id=stock.id, resource_id=resource_id, kind="maintain_production_inputs",
            motivation="Manter materiais para o reparo da instalação.")
