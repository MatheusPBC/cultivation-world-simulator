"""Dispatch dated domains without dropping unknown scheduled situations."""

from .logistics import resolve_parcels
from .phases import resolve_dated_activities
from .commitments import resolve_diplomacy
from .migration import resolve_migrations
from .workforce import resolve_workforce_transitions
from .apprenticeship import resolve_apprenticeships
from .force import resolve_force_positions, resolve_forces
from .rites import resolve_rites
from .campaign_supply import load_campaign_baggage, observe_campaign_supply_needs
from .field_engagement import resolve_field_engagements
from .settlement_investment import revoke_invalid_settlement_investments
from .sabotage import resolve_investigations
from .force_command import revoke_invalid_detachment_commands
from .civic_protest import resolve_civic_protests
from .demography import resolve_generation_maturity
from .technique_copy import resolve_technique_copies


def resolve_dated(world, situations):
    if any(s.kind not in {"activity", "cargo", "migration", "workforce_transition", "apprenticeship",
                          "force", "force_preparation", "rite", "rite_interruption", "creature_review", "recourse_review",
                          "character_rite_offer_review", "character_rite_sponsor_review", "character_travel_review",
                          "force_contact_review",
                          "strategy_response_review",
                          "campaign_supply_review", "field_engagement", "field_aftermath_review", "diplomacy",
                          "diplomatic_review", "investigation", "civic_protest", "generation_maturity", "technique_copy"}
           for s in situations):
        raise ValueError("unknown dated situation")
    resolve_dated_activities(world, [s for s in situations if s.kind == "activity"])
    # Death, office expiry and an externally moved character do not leave a
    # tactical command silently attached to a column.
    revoke_invalid_detachment_commands(world)
    resolve_parcels(world, [s for s in situations if s.kind == "cargo"])
    resolve_civic_protests(world, [s for s in situations if s.kind == "civic_protest"])
    # A generation reaches working age before the day's other work reads the
    # cohorts, and moves only whoever actually remained.
    resolve_generation_maturity(world, [s for s in situations if s.kind == "generation_maturity"])
    # Freight unloads before a standing column consumes today's ration. The
    # bag is still Economy-owned; Society records only the actual loading.
    load_campaign_baggage(world)
    resolve_migrations(world, [s for s in situations if s.kind == "migration"])
    resolve_workforce_transitions(world, [s for s in situations if s.kind == "workforce_transition"])
    resolve_apprenticeships(world, [s for s in situations if s.kind == "apprenticeship"])
    resolve_investigations(world, [s for s in situations if s.kind == "investigation"])
    # Sustained access is judged on the day it ends, never sampled.
    resolve_technique_copies(world, [s for s in situations if s.kind == "technique_copy"])
    resolve_forces(world, [s for s in situations if s.kind == "force"])
    revoke_invalid_settlement_investments(world)
    resolve_force_positions(world, [s for s in situations if s.kind == "force_preparation"])
    resolve_field_engagements(world, [s for s in situations if s.kind == "field_engagement"])
    observe_campaign_supply_needs(world)
    resolve_rites(world, [s for s in situations if s.kind in {"rite", "rite_interruption"}])
    resolve_diplomacy(world, [s for s in situations if s.kind == "diplomacy"])
