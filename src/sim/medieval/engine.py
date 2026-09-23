"""Hybrid-calendar phase runner: prepare a candidate, commit it, then publish it."""

import asyncio
from pathlib import Path

from src.systems.calendar_scheduler import CalendarScheduler
from .activities import validate_activities
from .events import record_event, validate_history
from .persistence import save_world
from .phases import advance_monthly_practice
from .dated import resolve_dated
from .economy import produce_monthly, consume_monthly, monthly_workforce
from .permanent_employment import review_permanent_employment_fallback, settle_permanent_employment
from .expansion import progress_expansions, review_expansions
from .research import progress_research
from .research_policy import review_research
from .markets import update_markets
from .intelligence import refresh_reports, refresh_trade_reports
from .procurement import review_supply, progress_supply
from .diplomacy_policy import (review_diplomacy, review_diplomacy_with_provider,
                               review_promised_teaching_turns)
from .infrastructure import progress_repairs, review_maintenance
from .migration_policy import review_migration
from .household_provisioning import review_household_provisions
from .tariffs import review_export_tariffs
from .site_services import review_site_services
from .route_intelligence import refresh_route_reports, refresh_site_reports
from .customs import staff_customs_checkpoints
from .infrastructure_wear import apply_monthly_infrastructure_wear
from .demography import apply_monthly_births
from .mortality import apply_monthly_mortality
from .regional_overflow import apply_monthly_regional_overflow
from .workforce import refresh_workforce_notices, review_workforce_transition_fallback
from .institutional_aid_policy import review_institutional_aid_with_provider
from .relief_policy import review_relief_fallback
from .creature_policy import review_creatures
from .creatures import apply_monthly_creature_ecology
from .recourse_policy import review_recourse
from .character_rite_policy import review_character_rites, schedule_character_rite_offers
from .character_travel import review_character_travel, schedule_character_travel_reviews
from .force_contact_policy import review_force_contacts
from .field_aftermath_policy import review_field_aftermaths
from .campaign_supply import review_campaign_supplies
from .authority_claims import lapse_invalid_claims
from .force_command import revoke_invalid_detachment_commands
from .strategy_response import review_strategy_responses_with_provider
from .institutional_agenda import review_monthly_institutional_turn
from .institutional_decision_turn import STALE_AFFORDANCE_EVENT_TYPE
from .ai_decider import ProviderDecisionRequired
from src.classes.core.infrastructure import validate_infrastructure


def _raise_if_provider_stale(world, history_start):
    """Turn a provider-selected stale affordance into a transaction failure.

    The composed decision turn keeps a zero-delta blocked receipt when called
    directly, which is useful for read-only diagnostics.  At the simulator
    boundary, however, a stale provider choice is a technical decision wait:
    the isolated candidate must be discarded so no later monthly family can
    commit around the failed revalidation.
    """
    if not world.config.ai_enabled:
        return
    if any(event.event_type == STALE_AFFORDANCE_EVENT_TYPE
           for event in world.events[history_start - 1:]):
        raise ProviderDecisionRequired(
            "provider decision required: selected institutional affordance became stale"
        )


class MedievalSimulator:
    def __init__(self, world, *, save_path: Path | None = None):
        self.world = world
        self.save_path = save_path
        self._lock = asyncio.Lock()

    async def step(self):
        async with self._lock:
            # 1. Validate and prepare an isolated canonical candidate, including RNG.
            # A command may have become invalid because its office ended or its
            # real person died since the preceding dated tick.  Release it in
            # the isolated candidate before strict cross-owner validation.
            candidate = self.world.transaction_copy()
            history_start = len(candidate.events) + 1
            revoke_invalid_detachment_commands(candidate)
            validate_activities(candidate)
            candidate.society.validate(set(candidate.map.regions), candidate)
            candidate.economy.validate(candidate)
            candidate.authority.validate(candidate)
            candidate.strategy.validate(candidate)
            # Knowledge is validated on every committed candidate below.  The
            # published world entering this transaction was already validated
            # by the previous commit, and no pre-step operation mutates its
            # knowledge registries.  Repeating the full historical-provenance
            # walk here made long horizons superlinear without adding a new
            # safety boundary; a tampered candidate still fails before save or
            # publication at the final validation below.
            candidate.research.validate(candidate)
            candidate.relations.validate(candidate)
            if any(day <= candidate.clock.absolute_day for day in candidate.agenda.due_days):
                raise ValueError("resolve pending dates before advancing")
            jump = CalendarScheduler.next_jump(candidate.clock, candidate.agenda.due_days)
            candidate.clock = candidate.clock.advance(jump.elapsed_days)
            # 2. Resolve dated work before the monthly aggregation on a tie.
            if jump.agenda_due:
                due = candidate.agenda.pop_due(jump.to_day)
                resolve_dated(candidate, due)
                progress_supply(candidate)
                if candidate.config.ai_enabled:
                    await review_diplomacy_with_provider(candidate)
                else:
                    review_diplomacy(candidate)
                # A dated step may answer, fulfil or repair an aid commitment,
                # but never opens a new request outside the monthly review.
                await review_institutional_aid_with_provider(candidate, allow_requests=False)
                # A scheduled creature review only offers turns; the deadline
                # itself never demands, restricts or reopens anything.
                await review_creatures(candidate, due)
                await review_character_rites(candidate, due)
                # An individual leg is chosen after the day's dated arrivals, so
                # a person decides from where it actually stands today.
                await review_character_travel(candidate, due)
                await review_force_contacts(candidate, due)
                await review_strategy_responses_with_provider(candidate, due)
                await review_field_aftermaths(candidate, due)
                await review_campaign_supplies(candidate, due)
                # Breaches have already been concluded by ``resolve_dated`` and
                # columns have already eaten and moved, so a wronged creditor
                # decides on today's real situation and never on a stale one.
                await review_recourse(candidate, due)
                _raise_if_provider_stale(candidate, history_start)
                # In provider mode migration is already part of the single
                # monthly population-group consultation.  The dated pass is
                # only the explicit offline/test policy; calling it here in
                # AI mode would let a deterministic chooser move households
                # outside the actor's affordance decision.
                if not candidate.config.ai_enabled:
                    review_migration(candidate)
            # 3. Process monthly domains exactly once per month boundary.
            if jump.monthly_boundary:
                advance_monthly_practice(candidate)
                available = monthly_workforce(candidate)
                # Standing employment is an Economy-owned obligation, not
                # created income. It must reserve/pay its named people before
                # other monthly work competes for the same local labour.
                settle_permanent_employment(candidate, available)
                staff_customs_checkpoints(candidate, available)
                progress_research(candidate, available)
                progress_expansions(candidate, available)
                produce_monthly(candidate, available)
                consume_monthly(candidate)
                # The subsistence receipt of this very cycle is the only source
                # of deprivation deaths, and a lifetime ends on the same closing.
                # Remaining monthly work sees the corrected availability.
                apply_monthly_mortality(candidate, available)
                # The same receipt, read from the other side: a fed cycle with
                # room to house people grows. Newborns are dependents, so the
                # workforce of this cycle is unchanged by construction.
                apply_monthly_births(candidate)
                # Material use has completed.  Wear belongs to the Map and is
                # applied before reports, so a maintainer sees this exact cycle.
                apply_monthly_infrastructure_wear(candidate)
                # A sustained, seed-derived water load can affect one declared
                # water-exposed Map site.  It runs after wear but before local
                # observations, never creates weather knowledge for actors.
                apply_monthly_regional_overflow(candidate)
                apply_monthly_creature_ecology(candidate)
                review_research(candidate)
                review_expansions(candidate)
                update_markets(candidate)
                refresh_reports(candidate)
                schedule_character_rite_offers(candidate)
                schedule_character_travel_reviews(candidate)
                if not candidate.config.ai_enabled:
                    # In the fully offline mode there is no composed provider
                    # turn to defer to, so retain the historical policy order.
                    if review_export_tariffs(candidate):
                        refresh_trade_reports(candidate, replace_today=True)
                    changed_service_sites = review_site_services(candidate)
                    if changed_service_sites:
                        refresh_site_reports(candidate, site_ids=changed_service_sites)
                        refresh_route_reports(
                            candidate,
                            route_ids=tuple(sorted({route_id for site_id in changed_service_sites
                                                    for route_id in candidate.map.infrastructure_sites[site_id].route_ids})),
                        )
                    review_household_provisions(candidate)
                progress_repairs(candidate, available)
                # Production and repair have now recorded their actual labour
                # limitations.  Only then may the affected sponsor receive a
                # dated demand receipt and a local group receive a direct offer.
                refresh_workforce_notices(candidate)
                # One consultation per institution across every discretionary
                # family at once -- supply, aid request, repair, diplomacy,
                # technique copying, civic demands and strategic adoption --
                # before any automatic pass runs. Claimed objectives/sites and
                # covered actors then skip their own pass below, so nothing
                # second-guesses the single menu the actor already saw.
                claims, covered = await review_monthly_institutional_turn(candidate)
                _raise_if_provider_stale(candidate, history_start)
                # These deterministic policies run only after the composed
                # consultation.  A provider may have been available while a
                # particular actor had no budget slot; ``covered`` tells the
                # owners exactly who must not be asked a second time.
                if not candidate.config.ai_enabled and review_export_tariffs(candidate):
                    # A changed policy republishes only affected market quotes;
                    # route/site/settlement observations remain single receipts.
                    refresh_trade_reports(candidate, replace_today=True)
                changed_service_sites = review_site_services(candidate) if not candidate.config.ai_enabled else ()
                if changed_service_sites:
                    # Service changes are material state, so owners and connected
                    # recipients receive a new dated route/site observation today.
                    refresh_site_reports(candidate, site_ids=changed_service_sites)
                    refresh_route_reports(
                        candidate,
                        route_ids=tuple(sorted({route_id for site_id in changed_service_sites
                                                for route_id in candidate.map.infrastructure_sites[site_id].route_ids})),
                    )
                if not candidate.config.ai_enabled:
                    review_household_provisions(candidate)
                # Offline/test mode still uses the actor-facing employment
                # affordance, but selects conservatively from public pressure
                # when no real provider turn occurred.  The owner then
                # revalidates the same option and creates the normal contract.
                if not candidate.config.ai_enabled:
                    review_permanent_employment_fallback(candidate)
                # Offline mode may accept one already-published transition when
                # observed pressure and a real labour shortfall make it useful.
                # The workforce owner still revalidates the selected terms.
                if not candidate.config.ai_enabled:
                    review_workforce_transition_fallback(candidate)
                # Offline/test mode has one declared, urgency-bounded relief
                # policy. It still records an actor decision and invokes the
                # same owner executors as the provider-selected affordance.
                if not candidate.config.ai_enabled:
                    review_relief_fallback(candidate)
                    review_maintenance(candidate)
                    review_supply(candidate)
                if not candidate.config.ai_enabled:
                    review_diplomacy(candidate, allow_offers=True)
                if candidate.config.ai_enabled:
                    # The learner's acceptance keeps its own ordered turn for
                    # whoever the composed menu left untouched.
                    await review_promised_teaching_turns(candidate, consulted=covered)
                # In provider mode, requests and the existing aid lifecycle
                # (response, fulfillment, remediation) are already part of
                # the single composed monthly menu.  Keeping this pass here
                # would ask the same polity again for the same boundary and
                # violate the one-consultation contract.  Dated reviews still
                # call the aid owner above when a real deadline is due.
                if not candidate.config.ai_enabled:
                    await review_institutional_aid_with_provider(candidate, allow_requests=True)
                    review_migration(candidate)
                lapse_invalid_claims(candidate)
                record_event(candidate, "month_closed", "O ciclo mensal foi concluído.")
            # 4. Validate and durably commit the candidate before publishing any change.
            candidate.society.validate(set(candidate.map.regions), candidate)
            candidate.economy.validate(candidate)
            candidate.authority.validate(candidate)
            candidate.strategy.validate(candidate)
            # Knowledge owners validate their own receipts immediately.  The
            # global provenance walk is still required at monthly boundaries
            # and dated turns (where knowledge can change), but repeating the
            # full historical registry scan on an ordinary ten-day jump made
            # long horizons superlinear without adding a new mutation guard.
            if jump.monthly_boundary or jump.agenda_due or self.save_path is not None:
                candidate.knowledge.validate(candidate)
            candidate.research.validate(candidate)
            candidate.relations.validate(candidate)
            candidate.regional_overflow.validate(candidate)
            validate_infrastructure(candidate)
            validate_activities(candidate)
            validate_history(candidate.events, candidate.clock.absolute_day,
                             from_sequence=history_start)
            if self.save_path is not None:
                save_world(candidate, self.save_path)
            self.world.__dict__.update(candidate.__dict__)
            return jump
