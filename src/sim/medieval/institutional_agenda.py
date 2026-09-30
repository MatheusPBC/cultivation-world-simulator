"""The single monthly institutional turn, composed from every family.

Civil supply/aid/repair, diplomacy, technique copying, civic demands and
strategic adoption each already expose their own adapters over their own
unchanged executors. This module unions those adapters and their actor sets,
so one institution answers one composed consultation instead of one per
vertical. Newly-created same-day bilateral market requests have a separate
seller-response pass after buyer turns; it adds no material executor or
persisted planner.

Deliberately outside the monthly turn: anything already in course (an
accepted aid obligation being fulfilled or remediated, a promised teaching
being taught or accepted, an adopted defence plan being executed).

On the DAILY cadence recourse and received religious group invitations are composed here
(``review_daily_institutional_turn``): it is genuinely discretionary, keyed
by the acting polity itself, has no cross-actor dependency inside one day,
and keep their own family context fragments. A group invitation grants a dated
shared choice over adherence and current work/food/migration/civic alternatives,
not automatic conversion. The other daily verticals keep
their own owners and ordering, each for its own reason: force contact and
campaign supply answer material processes already in course; field aftermath
and strategy-response reviews are keyed per notice/plan, not per actor;
creatures run two dependent phases (institutions answer, then the drake
re-evaluates) inside one day; and the scheduled diplomacy day mixes
discretionary claims with in-course payment and the teacher-before-learner
ordering. Those keep their own owners and their own ordering.
"""

from .civic_protest_policy import civic_actors, civic_adapters
from .concurrent_civil_decision import CIVIL_ADAPTERS
from .diplomacy_policy import diplomacy_actors, diplomacy_adapters
from .institutional_decision_turn import (_rotated, review_institutional_decision_turn,
                                          review_institutional_decision_turn_with_provider)
from .recourse_policy import (REVIEW_KIND as RECOURSE_REVIEW_KIND, recourse_actors,
                              recourse_adapters, schedule_pending_recourse)
from .relief_policy import relief_actors, relief_adapters
from .strategy_response import (garrison_supply_adapters, garrison_supply_options,
                                strategy_adoption_actors, strategy_adoption_adapters)
from .technique_copy_policy import technique_copy_actors, technique_copy_adapters
from .sabotage import (accusation_options, accusation_response_options, investigation_options,
                       sabotage_adapters, sabotage_options)
from .espionage import espionage_adapters, espionage_options
from .infrastructure import repair_authorization_options, site_reactivation_options
from .bribery import (bribery_adapters, bribery_offer_options, bribery_payment_options,
                      bribery_response_options)
from .technology_sale_policy import technology_sale_actors, technology_sale_adapters
from .market_purchase_policy import (market_purchase_adapters,
                                     market_purchase_actors,
                                     market_purchase_response_actors)
from .technology_theft import technology_theft_adapters, technology_theft_options
from .permanent_employment import (employment_staffing_adapters, employment_staffing_options,
                                   permanent_employment_adapters, permanent_employment_options)
from .production_priority import production_priority_adapters, production_priority_options
from .workforce import (military_recruitment_adapters, military_recruitment_group_actors,
                        workforce_adapters, workforce_transition_options)
from .customs_policy import customs_adapters, customs_actors
from .embargo import embargo_options
from .garrison_policy import garrison_adapters, garrison_actors
from .research_policy import research_options
from .expansion import expansion_options
from .site_services import service_adapters, service_options
from .tariffs import tariff_adapters
from .migration_policy import migration_adapters, migration_actors
from .household_provisioning import (household_provision_adapters,
                                      household_provision_options,
                                      household_provision_sale_options)
from .assembly_denial import assembly_denial_adapters, assembly_denial_options
from .campaign_ceasefire import campaign_ceasefire_adapters
from .force_training import training_adapters, training_options
from .apprenticeship import apprenticeship_sponsor_adapters, apprenticeship_sponsor_options
from .family_loans import (family_loan_adapters, family_loan_options,
                           family_loan_repayment_options, family_loan_request_options)
from .productive_conveyance_policy import (
    conveyance_response_adapter,
    newly_offered_conveyance_buyers,
    productive_conveyance_adapters,
    productive_conveyance_actors,
)

from src.classes.mechanical_language import EntityRef
from .religion import invitation_options, adherence_options
from .religion_policy import GROUP_REVIEW_KIND, religion_adapters, response_actors


def monthly_adapters(*, allow_offers=True):
    return (*CIVIL_ADAPTERS, *diplomacy_adapters(allow_offers=allow_offers), *technique_copy_adapters(),
            *technology_sale_adapters(),
            *technology_theft_adapters(),
            *permanent_employment_adapters(),
            *employment_staffing_adapters(),
            *production_priority_adapters(),
            *workforce_adapters(),
            *military_recruitment_adapters(),
            # The embargo adapter arrives through CIVIL_ADAPTERS above; a second
            # registration here would let one budget answer the same affordance
            # twice in a single turn.
            *customs_adapters(), *service_adapters(), *tariff_adapters(),
            *migration_adapters(),
            *garrison_adapters(),
            *household_provision_adapters(),
            *family_loan_adapters(),
            *relief_adapters(), *civic_adapters(), *strategy_adoption_adapters(),
            *garrison_supply_adapters(), *sabotage_adapters(),
            *training_adapters(),
            *espionage_adapters(), *bribery_adapters(), *assembly_denial_adapters(),
            *campaign_ceasefire_adapters(), *apprenticeship_sponsor_adapters(),
            *productive_conveyance_adapters(), *religion_adapters())


def monthly_actors(world):
    """Every institution any family could offer something to this boundary."""
    actors = {EntityRef("polity", identity) for identity in world.society.polities}
    actors.update(diplomacy_actors(world))
    actors.update(technique_copy_actors(world))
    actors.update(technology_sale_actors(world))
    actors.update(productive_conveyance_actors(world))
    actors.update(market_purchase_actors(world))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if technology_theft_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if permanent_employment_options(world, actor))
    actors.update(EntityRef("polity", identity) for identity in world.society.polities
                  if family_loan_request_options(world, EntityRef("polity", identity))
                  or family_loan_repayment_options(world, EntityRef("polity", identity)))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if employment_staffing_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if production_priority_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if research_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if expansion_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if any(service_options(world, site.id, actor)
                         for site in world.map.infrastructure_sites.values()))
    actors.update(EntityRef("population_group", group.id)
                  for group in world.society.population.values()
                  if workforce_transition_options(world, group.id))
    actors.update(military_recruitment_group_actors(world))
    actors.update(customs_actors(world))
    actors.update(EntityRef("polity", identity) for identity in world.society.polities
                  if embargo_options(world, EntityRef("polity", identity)))
    actors.update(garrison_actors(world))
    # Campaign affordances are also valid for organizations with a current
    # military/diplomatic office.  Polities remain in the base set; this only
    # discovers non-polity owners that the same campaign adapters already
    # enumerate and revalidate.
    campaign_candidates = tuple(sorted(
        {office.institution_ref for office in world.authority.offices.values()
         if office.institution_ref.kind == "organization"},
        key=lambda ref: (ref.kind, ref.id)))
    for actor in campaign_candidates:
        if (any(adapter.options_fn(world, actor) for adapter in campaign_ceasefire_adapters())
                or training_options(world, actor)):
            actors.add(actor)
    actors.update(civic_actors(world))
    actors.update(relief_actors(world))
    actors.update(migration_actors(world))
    actors.update(EntityRef("population_group", group.id)
                  for group in world.society.population.values()
                  if household_provision_options(world, EntityRef("population_group", group.id)))
    actors.update(EntityRef("population_group", group.id)
                  for group in world.society.population.values()
                  if family_loan_options(world, EntityRef("population_group", group.id)))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if household_provision_sale_options(world, actor))
    actors.update(strategy_adoption_actors(world))
    actors.update(actor for actor in {garrison.detachment_id and detachment.owner_ref
                                      for garrison in world.society.garrisons.values()
                                      for detachment in (world.society.detachments.get(garrison.detachment_id),)
                                      if detachment is not None}
                  if actor is not None and garrison_supply_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if espionage_options(world, actor))
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if apprenticeship_sponsor_options(world, actor))
    # Organizations do not belong to the base polity set.  Include one when
    # it has a material bribery affordance of its own; otherwise an office
    # holder could publish a valid offer/payment/response that never reaches
    # the single monthly consultation simply because another family had no
    # option for that organization.
    actors.update(actor for actor in (office.institution_ref for office in world.authority.offices.values())
                  if any(options for options in (bribery_offer_options(world, actor),
                                                 bribery_response_options(world, actor),
                                                 bribery_payment_options(world, actor))))
    infrastructure_actors = {
        actor
        for site in world.map.infrastructure_sites.values()
        for actor in (site.owner_ref, site.maintainer_ref)
        if actor is not None
    }
    actors.update(actor for actor in infrastructure_actors
                  if repair_authorization_options(world, actor)
                  or site_reactivation_options(world, actor))
    # Organizations are not part of the base polity set.  Include one when a
    # current sabotage, investigation, or accusation affordance belongs to it;
    # otherwise the shared conflict adapters would be registered but never
    # consulted for that actor.
    actors.update(EntityRef("organization", identity)
                  for identity in world.society.organizations
                  if any(options for options in (sabotage_options(world, EntityRef("organization", identity)),
                                                 investigation_options(world, EntityRef("organization", identity)),
                                                 accusation_options(world, EntityRef("organization", identity)),
                                                 accusation_response_options(world, EntityRef("organization", identity)))))
    actors.update(actor for actor in (EntityRef("polity", identity) for identity in world.society.polities)
                  if assembly_denial_options(world, actor))
    # Keep the long-standing polity-first boundary deterministic.  The monthly
    # budget is intentionally finite; adding institutional families must not
    # silently make a population group with a current material offer lose its
    # turn behind unrelated offices. Rotate each class independently: polities
    # remain first, then population groups with workforce/civic affordances,
    # then other organizations; every class still rotates fairly.
    actors.update(EntityRef("organization", identity) for identity in world.society.organizations
                  if invitation_options(world, EntityRef("organization", identity)))
    actors.update(EntityRef("population_group", identity) for identity in world.society.population
                  if adherence_options(world, EntityRef("population_group", identity)))
    polities = tuple(sorted((actor for actor in actors if actor.kind == "polity"), key=lambda ref: ref.id))
    population_groups = tuple(sorted((actor for actor in actors if actor.kind == "population_group"),
                                     key=lambda ref: ref.id))
    organizations = tuple(sorted((actor for actor in actors
                                  if actor.kind not in {"polity", "population_group"}),
                                 key=lambda ref: (ref.kind, ref.id)))
    return _rotated(world, polities) + _rotated(world, population_groups) + _rotated(world, organizations)


async def review_monthly_institutional_turn(world, *, allow_offers=True):
    """Compose monthly choices, then resolve newly-created market responses.

    Returns the same ``(claims, covered)`` every turn returns: ``claims`` for
    the deterministic passes that must skip a target already offered, and
    ``covered`` for the policies that must not ask the same institution again
    this boundary.
    """
    previous_conveyance_proposals = {
        event.id for event in world.events
        if (event.decision or {}).get("action") == "propose_productive_site_conveyance"
    }
    claims, covered_actors = await review_institutional_decision_turn_with_provider(
        world, monthly_adapters(allow_offers=allow_offers), actors=monthly_actors(world))
    if not world.config.ai_enabled:
        return claims, covered_actors

    # A polity's normal turn precedes organizational buyers. Their same-day
    # purchase requests therefore cannot appear in a seller's already-used
    # menu. Give only the affected sellers a separate response turn after all
    # buyer choices; no material transfer occurs without that seller choice.
    response_adapter = next(adapter for adapter in market_purchase_adapters()
                            if adapter.name == "market_purchase_acceptance")
    for seller in market_purchase_response_actors(world):
        response_claims, response_covered = await review_institutional_decision_turn(
            world, seller, (response_adapter,))
        for kind, identities in response_claims.items():
            claims.setdefault(kind, set()).update(identities)
        if response_covered:
            covered_actors.add(seller)

    # Institutional ordering keeps polities before organizations, but a
    # productive-site seller may be an organization. Give only the polity or
    # organization named by a fresh same-day offer its independent acceptance
    # consultation after the seller turn, without repeating old offers.
    response_buyers = newly_offered_conveyance_buyers(world, previous_conveyance_proposals)
    new_proposal_ids = {
        event.id for event in world.events
        if event.day == world.clock.absolute_day
        and event.id not in previous_conveyance_proposals
        and (event.decision or {}).get("action") == "propose_productive_site_conveyance"
    }
    if response_buyers:
        response_adapter = conveyance_response_adapter(new_proposal_ids)
        for buyer in response_buyers:
            response_claims, response_covered = await review_institutional_decision_turn(
                world, buyer, (response_adapter,))
            for kind, identities in response_claims.items():
                claims.setdefault(kind, set()).update(identities)
            if response_covered:
                covered_actors.add(buyer)
    return claims, covered_actors


def daily_adapters(situations):
    adapters = recourse_adapters() if any(item.kind == RECOURSE_REVIEW_KIND for item in situations) else ()
    if any(item.kind == GROUP_REVIEW_KIND for item in situations):
        # A received invitation grants a shared turn, not an exclusive religious
        # consultation. The group can instead work, buy food, migrate or protest.
        adapters = (*adapters, *religion_adapters(invitations=False), *workforce_adapters(),
                    *household_provision_adapters(), *family_loan_adapters(),
                    *migration_adapters(), *civic_adapters())
    return adapters


def daily_actors(world, situations):
    actors = set(recourse_actors(world)) if any(item.kind == RECOURSE_REVIEW_KIND for item in situations) else set()
    actors.update(response_actors(world, situations))
    actors = tuple(sorted(actors, key=lambda actor: (actor.kind, actor.id)))
    if not actors:
        return actors
    offset = world.clock.absolute_day % len(actors)
    return actors[offset:] + actors[:offset]


async def review_daily_institutional_turn(world, situations):
    situations = tuple(situations)
    adapters = daily_adapters(situations)
    if not adapters:
        return {}, set()
    claims, covered = {}, set()
    for actor in daily_actors(world, situations):
        actor_claims, consulted = await review_institutional_decision_turn(world, actor, adapters)
        for kind, identities in actor_claims.items():
            claims.setdefault(kind, set()).update(identities)
        if consulted:
            covered.add(actor)
    schedule_pending_recourse(world)
    return claims, covered


__all__ = ["monthly_actors", "monthly_adapters", "review_monthly_institutional_turn",
           "daily_actors", "daily_adapters", "review_daily_institutional_turn"]
