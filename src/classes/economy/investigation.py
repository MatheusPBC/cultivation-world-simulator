"""Paid, dated examination of a real infrastructure damage fact.

An investigation does not grant surveillance or reconstruct a hidden action.
It is only the Economy-owned work obligation that pays a local artisan to
examine one already observed Map damage event, including the narrow damage
fact produced by the River Lume drake.  Knowledge owns the eventual private
finding.
"""

from typing import Literal

from pydantic import Field, model_validator

from src.classes.mechanical_language import EntityRef
from src.classes.society.models import Count, Identity, SocietyValue
from src.classes.event import FactKind
from src.classes.governance.models import SiteReport


class Investigation(SocietyValue):
    id: Identity
    site_id: Identity
    investigator_ref: EntityRef
    damage_event_id: Identity
    report_event_id: Identity
    stock_id: Identity
    account_id: Identity
    opened_day: Count
    due_day: Count
    workers: int = Field(strict=True, gt=0)
    wage_per_worker: int = Field(strict=True, gt=0)
    stage: Literal["open", "attributed", "inconclusive", "blocked"] = "open"
    last_event_id: Identity

    @model_validator(mode="after")
    def valid_timing(self):
        if self.id != f"investigation:{self.damage_event_id}:{self.opened_day}":
            raise ValueError("investigation identity must name the damage and opening day")
        if self.due_day != self.opened_day + 30:
            raise ValueError("an investigation requires exactly thirty days of work")
        return self


def validate_investigations(economy, world=None):
    """The paid obligation is auditable even though its finding is private."""
    active_sites = set()
    events = {event.id: event for event in world.events} if world is not None else {}
    for investigation in economy.investigations.values():
        stock = economy.stocks.get(investigation.stock_id)
        account = economy.accounts.get(investigation.account_id)
        if stock is None or account is None:
            raise ValueError("investigation requires its stock and account")
        if stock.owner_ref != investigation.investigator_ref or account.owner_ref != investigation.investigator_ref:
            raise ValueError("investigation must use the investigator's own means")
        if investigation.stage == "open":
            if investigation.site_id in active_sites:
                raise ValueError("a site can have only one open investigation")
            active_sites.add(investigation.site_id)
        if world is None:
            continue
        site = world.map.infrastructure_sites.get(investigation.site_id)
        decision = events.get(investigation.damage_event_id)
        receipt = events.get(investigation.last_event_id)
        report_event = events.get(investigation.report_event_id)
        if (site is None or decision is None or receipt is None or investigation.opened_day > world.clock.absolute_day
                or decision.event_type not in {"site_sabotaged", "creature_damaged_site"}
                or decision.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "site" and delta.owner_id == investigation.site_id
                           and delta.aspect == "integrity" and float(delta.after) < float(delta.before)
                           for delta in decision.deltas)
                or report_event is None
                or investigation.report_event_id not in {link.cause_event_id for link in receipt.causal_links}
                or investigation.damage_event_id not in {link.cause_event_id for link in report_event.causal_links}):
            raise ValueError("investigation requires an observed factual site sabotage")
        if investigation.stage == "open":
            scheduled = world.agenda.get(investigation.id)
            if (receipt.event_type != "investigation_opened" or receipt.day != investigation.opened_day
                    or scheduled is None or scheduled.kind != "investigation" or scheduled.due_day != investigation.due_day
                    or investigation.due_day <= world.clock.absolute_day):
                raise ValueError("open investigation lacks its dated work")
        elif investigation.stage == "blocked":
            if receipt.event_type != "investigation_blocked" or world.agenda.get(investigation.id) is not None:
                raise ValueError("blocked investigation has invalid lifecycle")
        else:
            finding = world.knowledge.investigation_findings.get(
                f"investigation_finding:{investigation.id}")
            if (receipt.event_type != "investigation_completed" or receipt.day != investigation.due_day
                    or world.agenda.get(investigation.id) is not None or finding is None
                    or finding.event_id != receipt.id or finding.result != investigation.stage):
                raise ValueError("completed investigation lacks its private finding")
