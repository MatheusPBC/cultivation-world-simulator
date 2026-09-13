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
from .intelligence import refresh_reports
from .procurement import review_supply, progress_supply
from .diplomacy_policy import review_diplomacy


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
                review_supply(candidate)
                review_diplomacy(candidate, allow_offers=True)
                record_event(candidate, "month_closed", "O ciclo mensal foi concluído.")
            # 4. Validate and durably commit the candidate before publishing any change.
            candidate.society.validate(set(candidate.map.regions))
            candidate.economy.validate(candidate)
            candidate.authority.validate(candidate)
            candidate.strategy.validate(candidate)
            candidate.knowledge.validate(candidate)
            candidate.research.validate(candidate)
            candidate.relations.validate(candidate)
            validate_activities(candidate)
            validate_history(candidate.events, candidate.clock.absolute_day)
            if self.save_path is not None:
                save_world(candidate, self.save_path)
            self.world.__dict__.update(candidate.__dict__)
            return jump
