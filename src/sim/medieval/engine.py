"""Hybrid-calendar phase runner: prepare a candidate, commit it, then publish it."""

import asyncio
import copy
from pathlib import Path

from src.systems.calendar_scheduler import CalendarScheduler
from .activities import validate_activities
from .events import record_event, validate_history
from .persistence import save_world
from .phases import advance_monthly_practice
from .dated import resolve_dated
from .economy import produce_monthly, consume_monthly, monthly_workforce
from .expansion import progress_expansions, review_expansions
from .research import progress_research
from .research_policy import review_research
from .markets import update_markets
from .intelligence import refresh_reports, refresh_trade_reports
from .procurement import review_supply, progress_supply
from .diplomacy_policy import review_diplomacy
from .infrastructure import progress_repairs, review_maintenance
from .migration_policy import review_migration
from .household_provisioning import review_household_provisions
from .tariffs import review_export_tariffs
from .site_services import review_site_services
from .route_intelligence import refresh_route_reports, refresh_site_reports
from src.classes.core.infrastructure import validate_infrastructure


class MedievalSimulator:
    def __init__(self, world, *, save_path: Path | None = None):
        self.world = world
        self.save_path = save_path
        self._lock = asyncio.Lock()

    async def step(self):
        async with self._lock:
            # 1. Validate and prepare an isolated canonical candidate, including RNG.
            validate_activities(self.world)
            self.world.economy.validate(self.world)
            self.world.authority.validate(self.world)
            self.world.strategy.validate(self.world)
            self.world.knowledge.validate(self.world)
            self.world.research.validate(self.world)
            self.world.relations.validate(self.world)
            if any(day <= self.world.clock.absolute_day for day in self.world.agenda.due_days):
                raise ValueError("resolve pending dates before advancing")
            candidate = copy.deepcopy(self.world)
            jump = CalendarScheduler.next_jump(candidate.clock, candidate.agenda.due_days)
            candidate.clock = candidate.clock.advance(jump.elapsed_days)
            # 2. Resolve dated work before the monthly aggregation on a tie.
            if jump.agenda_due:
                resolve_dated(candidate, candidate.agenda.pop_due(jump.to_day))
                progress_supply(candidate)
                review_diplomacy(candidate)
                review_migration(candidate)
            # 3. Process monthly domains exactly once per month boundary.
            if jump.monthly_boundary:
                advance_monthly_practice(candidate)
                available = monthly_workforce(candidate)
                progress_research(candidate, available)
                progress_expansions(candidate, available)
                produce_monthly(candidate, available)
                consume_monthly(candidate)
                review_research(candidate)
                review_expansions(candidate)
                update_markets(candidate)
                refresh_reports(candidate)
                if review_export_tariffs(candidate):
                    # A changed policy republishes only affected market quotes;
                    # route/site/settlement observations remain single receipts.
                    refresh_trade_reports(candidate, replace_today=True)
                changed_service_sites = review_site_services(candidate)
                if changed_service_sites:
                    # Service changes are material state, so owners and connected
                    # recipients receive a new dated route/site observation today.
                    refresh_site_reports(candidate, site_ids=changed_service_sites)
                    refresh_route_reports(
                        candidate,
                        route_ids=tuple(sorted({route_id for site_id in changed_service_sites
                                                for route_id in candidate.map.infrastructure_sites[site_id].route_ids})),
                    )
                review_household_provisions(candidate)
                progress_repairs(candidate, available)
                review_maintenance(candidate)
                review_supply(candidate)
                review_diplomacy(candidate, allow_offers=True)
                review_migration(candidate)
                record_event(candidate, "month_closed", "O ciclo mensal foi concluído.")
            # 4. Validate and durably commit the candidate before publishing any change.
            candidate.society.validate(set(candidate.map.regions))
            candidate.economy.validate(candidate)
            candidate.authority.validate(candidate)
            candidate.strategy.validate(candidate)
            candidate.knowledge.validate(candidate)
            candidate.research.validate(candidate)
            candidate.relations.validate(candidate)
            validate_infrastructure(candidate)
            validate_activities(candidate)
            validate_history(candidate.events, candidate.clock.absolute_day)
            if self.save_path is not None:
                save_world(candidate, self.save_path)
            self.world.__dict__.update(candidate.__dict__)
            return jump
