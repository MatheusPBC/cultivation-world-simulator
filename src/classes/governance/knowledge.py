"""Single owner of actor-specific observations; canonical truth stays elsewhere."""

from dataclasses import dataclass, field
import json
from .models import (KnowledgeReport, DiplomaticNotice, AuthorityClaimNotice, FiscalRouteReport, RouteReport, SettlementReport, SiteReport,
                     CustomsNotice, WorkforceDemandReport, WorkforceOfferNotice, InstitutionalAidNotice,
                     CreatureTributeNotice, CreatureDamageNotice, ForceContactNotice, FieldEngagementOfferNotice,
                     FieldEngagementOutcomeNotice, CampaignSupplyNotice, SettlementPressureNotice,
                     RiteObservation, InvestigationFinding, InvestigationAccusationNotice, EspionageFinding, TechnologyTheftFinding,
                     CivicDemandNotice, TechnologySighting)
from .serialization import RegistrySerialization, validate_actor
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.research.models import TechnicalKnowledge


class _RegistryDict(dict):
    """Dict that invalidates transient KnowledgeState projections on writes."""

    def __init__(self, *args, owner=None, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = owner
        self._name = name

    def _touch(self):
        owner = self._owner
        # ``copy.deepcopy`` rebuilds a dict subclass before it has restored the
        # complete ``KnowledgeState`` instance it belongs to.  In that narrow
        # reconstruction window, assigning copied entries must not turn into a
        # registry mutation (nor require fields that have not been restored).
        # A live owner always has both epoch fields, so real registry writes
        # retain their normal invalidation semantics.
        if owner is None or not hasattr(owner, "_registry_epoch") or not hasattr(owner, "_registry_epochs"):
            return
        owner._registry_epoch += 1
        owner._registry_epochs[self._name] = owner._registry_epochs.get(self._name, 0) + 1

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._touch()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._touch()

    def clear(self):
        if self:
            super().clear()
            self._touch()

    def pop(self, key, *args):
        result = super().pop(key, *args)
        self._touch()
        return result

    def popitem(self):
        result = super().popitem()
        self._touch()
        return result

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        result = super().setdefault(key, default)
        self._touch()
        return result

    def update(self, *args, **kwargs):
        if args or kwargs:
            super().update(*args, **kwargs)
            self._touch()

    def __ior__(self, other):
        super().__ior__(other)
        self._touch()
        return self


def route_report_id(recipient_ref, route_id):
    return f"route_report:{recipient_ref.kind}:{recipient_ref.id}:{route_id}"


def fiscal_route_report_id(recipient_ref, route_id):
    return f"fiscal_route_report:{recipient_ref.kind}:{recipient_ref.id}:{route_id}"


def site_report_id(recipient_ref, site_id):
    return f"site_report:{recipient_ref.kind}:{recipient_ref.id}:{site_id}"


def settlement_report_id(recipient_ref, settlement_id):
    return f"settlement_report:{recipient_ref.kind}:{recipient_ref.id}:{settlement_id}"


def workforce_demand_report_id(sponsor_ref, work_kind, work_id):
    return f"workforce_demand:{sponsor_ref.kind}:{sponsor_ref.id}:{work_kind}:{work_id}"


def workforce_offer_notice_id(group_id, demand_id):
    return f"workforce_offer:{group_id}:{demand_id}"


def creature_tribute_notice_id(demand_id, recipient_ref):
    return f"creature_tribute_notice:{demand_id}:{recipient_ref.kind}:{recipient_ref.id}"


def creature_damage_notice_id(demand_id, site_id, recipient_ref):
    return f"creature_damage_notice:{demand_id}:{site_id}:{recipient_ref.kind}:{recipient_ref.id}"


def institutional_aid_notice_id(event_id, recipient_ref):
    return f"institutional_aid_notice:{event_id}:{recipient_ref.kind}:{recipient_ref.id}"


def force_contact_notice_id(standoff_id, recipient_ref):
    return f"force_contact_notice:{standoff_id}:{recipient_ref.kind}:{recipient_ref.id}"


def campaign_supply_notice_id(detachment_id, event_id):
    return f"campaign_supply_notice:{detachment_id}:{event_id}"


def field_engagement_offer_notice_id(engagement_id, recipient_ref):
    return f"field_engagement_offer_notice:{engagement_id}:{recipient_ref.kind}:{recipient_ref.id}"


def field_engagement_outcome_notice_id(engagement_id, recipient_ref):
    return f"field_engagement_outcome_notice:{engagement_id}:{recipient_ref.kind}:{recipient_ref.id}"


def settlement_pressure_notice_id(investment_id, recipient_ref):
    return f"settlement_pressure_notice:{investment_id}:{recipient_ref.kind}:{recipient_ref.id}"


def authority_claim_notice_id(claim_id, recipient_ref):
    return f"authority_claim_notice:{claim_id}:{recipient_ref.kind}:{recipient_ref.id}"


def rite_observation_id(recipient_ref, site_id):
    return f"rite_observation:{recipient_ref.kind}:{recipient_ref.id}:{site_id}"


def civic_demand_notice_id(protest_id, recipient_ref):
    return f"civic_demand_notice:{protest_id}:{recipient_ref.kind}:{recipient_ref.id}"


def investigation_accusation_notice_id(investigation_id, recipient_ref):
    return f"investigation_accusation:{investigation_id}:{recipient_ref.kind}:{recipient_ref.id}"


def technology_sighting_id(recipient_ref, holder_ref, technology_id):
    return (f"technology_sighting:{recipient_ref.kind}:{recipient_ref.id}:"
            f"{holder_ref.kind}:{holder_ref.id}:{technology_id}")


@dataclass
class KnowledgeState(RegistrySerialization):
    schema_version = 8
    _registry_epoch: int = field(default=0, init=False, repr=False, compare=False)
    _registry_epochs: dict[str, int] = field(default_factory=dict, init=False, repr=False, compare=False)
    _structural_validation_epoch: int | None = field(default=None, init=False, repr=False, compare=False)
    reports: dict[str, KnowledgeReport] = field(default_factory=dict)
    technologies: dict[str, TechnicalKnowledge] = field(default_factory=dict)
    notices: dict[str, DiplomaticNotice] = field(default_factory=dict)
    authority_claim_notices: dict[str, AuthorityClaimNotice] = field(default_factory=dict)
    route_reports: dict[str, RouteReport] = field(default_factory=dict)
    fiscal_route_reports: dict[str, FiscalRouteReport] = field(default_factory=dict)
    settlement_reports: dict[str, SettlementReport] = field(default_factory=dict)
    site_reports: dict[str, SiteReport] = field(default_factory=dict)
    customs_notices: dict[str, CustomsNotice] = field(default_factory=dict)
    workforce_demand_reports: dict[str, WorkforceDemandReport] = field(default_factory=dict)
    workforce_offer_notices: dict[str, WorkforceOfferNotice] = field(default_factory=dict)
    institutional_aid_notices: dict[str, InstitutionalAidNotice] = field(default_factory=dict)
    creature_tribute_notices: dict[str, CreatureTributeNotice] = field(default_factory=dict)
    creature_damage_notices: dict[str, CreatureDamageNotice] = field(default_factory=dict)
    force_contact_notices: dict[str, ForceContactNotice] = field(default_factory=dict)
    field_engagement_offer_notices: dict[str, FieldEngagementOfferNotice] = field(default_factory=dict)
    field_engagement_outcome_notices: dict[str, FieldEngagementOutcomeNotice] = field(default_factory=dict)
    campaign_supply_notices: dict[str, CampaignSupplyNotice] = field(default_factory=dict)
    settlement_pressure_notices: dict[str, SettlementPressureNotice] = field(default_factory=dict)
    rite_observations: dict[str, RiteObservation] = field(default_factory=dict)
    investigation_findings: dict[str, InvestigationFinding] = field(default_factory=dict)
    investigation_accusation_notices: dict[str, InvestigationAccusationNotice] = field(default_factory=dict)
    espionage_findings: dict[str, EspionageFinding] = field(default_factory=dict)
    technology_theft_findings: dict[str, TechnologyTheftFinding] = field(default_factory=dict)
    civic_demand_notices: dict[str, CivicDemandNotice] = field(default_factory=dict)
    technology_sightings: dict[str, TechnologySighting] = field(default_factory=dict)
    registries = {"reports": KnowledgeReport, "technologies": TechnicalKnowledge, "notices": DiplomaticNotice,
                  "authority_claim_notices": AuthorityClaimNotice,
                  "route_reports": RouteReport, "fiscal_route_reports": FiscalRouteReport,
                  "settlement_reports": SettlementReport, "site_reports": SiteReport}
    registries["customs_notices"] = CustomsNotice
    registries["workforce_demand_reports"] = WorkforceDemandReport
    registries["workforce_offer_notices"] = WorkforceOfferNotice
    registries["institutional_aid_notices"] = InstitutionalAidNotice
    registries["creature_tribute_notices"] = CreatureTributeNotice
    registries["creature_damage_notices"] = CreatureDamageNotice
    registries["force_contact_notices"] = ForceContactNotice
    registries["field_engagement_offer_notices"] = FieldEngagementOfferNotice
    registries["field_engagement_outcome_notices"] = FieldEngagementOutcomeNotice
    registries["campaign_supply_notices"] = CampaignSupplyNotice
    registries["settlement_pressure_notices"] = SettlementPressureNotice
    registries["rite_observations"] = RiteObservation
    registries["investigation_findings"] = InvestigationFinding
    registries["investigation_accusation_notices"] = InvestigationAccusationNotice
    registries["espionage_findings"] = EspionageFinding
    registries["technology_theft_findings"] = TechnologyTheftFinding
    registries["civic_demand_notices"] = CivicDemandNotice
    registries["technology_sightings"] = TechnologySighting

    def __post_init__(self):
        self._bind_registry_epoch()

    def _bind_registry_epoch(self, *, preserve_query=False):
        """Attach registries and isolate transient projections after a copy."""
        previous_query = getattr(self, "_query_cache", None) if preserve_query else None
        previous_epochs = (dict(getattr(self, "_registry_epochs", {}))
                           if preserve_query else {})
        previous_epoch = getattr(self, "_registry_epoch", 0) if preserve_query else 0
        previous_structural = (getattr(self, "_structural_validation_epoch", None)
                                if preserve_query else None)
        object.__setattr__(self, "_registry_epoch", previous_epoch)
        object.__setattr__(
            self,
            "_registry_epochs",
            {name: previous_epochs.get(name, 0) for name in self.registries},
        )
        for name in self.registries:
            registry = getattr(self, name)
            if not isinstance(registry, _RegistryDict) or registry._owner is not self:
                object.__setattr__(self, name, _RegistryDict(registry, owner=self, name=name))
        object.__setattr__(self, "_structural_validation_epoch", previous_structural)
        object.__setattr__(self, "_semantic_validation_key", None)
        if previous_query is None:
            object.__setattr__(self, "_query_cache", None)
        else:
            object.__setattr__(self, "_query_cache", {
                name: (signature, dict(projections))
                for name, (signature, projections) in previous_query.items()
            })

    def knows(self, actor_ref, technology_id):
        return any(k.owner_ref == actor_ref and k.technology_id == technology_id for k in self.technologies.values())

    def _actor_query(self, registry_name, actor_ref, predicate):
        """Cache a read-only actor projection until that registry changes."""
        registry = getattr(self, registry_name)
        signature = self._registry_epochs.get(registry_name, 0)
        cache = getattr(self, "_query_cache", None)
        if cache is None:
            cache = {}
            object.__setattr__(self, "_query_cache", cache)
        cached = cache.get(registry_name)
        if cached is None or cached[0] != signature:
            cached = (signature, {})
            cache[registry_name] = cached
        key = (actor_ref.kind, actor_ref.id)
        if key not in cached[1]:
            cached[1][key] = tuple(item for _, item in sorted(registry.items()) if predicate(item, actor_ref))
        return cached[1][key]

    def for_actor(self, actor_ref):
        return self._actor_query("reports", actor_ref, lambda item, actor: item.recipient_ref == actor)

    def routes_for_actor(self, actor_ref):
        """Latest dated observation per route this actor was told about."""
        return self._actor_query("route_reports", actor_ref, lambda item, actor: item.recipient_ref == actor)

    def route_report(self, actor_ref, route_id):
        return self.route_reports.get(route_report_id(actor_ref, route_id))

    def fiscal_routes_for_actor(self, actor_ref):
        return self._actor_query("fiscal_route_reports", actor_ref, lambda item, actor: item.recipient_ref == actor)

    def fiscal_route_report(self, actor_ref, route_id):
        return self.fiscal_route_reports.get(fiscal_route_report_id(actor_ref, route_id))

    def site_report(self, actor_ref, site_id):
        return self.site_reports.get(site_report_id(actor_ref, site_id))

    def customs_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.customs_notices.items()) if item.recipient_ref == actor_ref)

    def settlements_for_actor(self, actor_ref):
        return self._actor_query("settlement_reports", actor_ref, lambda item, actor: item.recipient_ref == actor)

    def settlement_report(self, actor_ref, settlement_id):
        return self.settlement_reports.get(settlement_report_id(actor_ref, settlement_id))

    def workforce_demand(self, sponsor_ref, work_kind, work_id):
        return self.workforce_demand_reports.get(workforce_demand_report_id(sponsor_ref, work_kind, work_id))

    def workforce_offers_for(self, group_id):
        recipient = group_id
        return tuple(item for _, item in sorted(self.workforce_offer_notices.items())
                     if item.recipient_ref.kind == "population_group" and item.recipient_ref.id == recipient)

    def creature_tributes_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.creature_tribute_notices.items())
                     if item.recipient_ref == actor_ref)

    def creature_damage_notices_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.creature_damage_notices.items())
                     if item.recipient_ref == actor_ref)

    def force_contacts_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.force_contact_notices.items())
                     if item.recipient_ref == actor_ref)

    def field_engagement_offers_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.field_engagement_offer_notices.items())
                     if item.recipient_ref == actor_ref)

    def campaign_supplies_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.campaign_supply_notices.items())
                     if item.recipient_ref == actor_ref)

    def settlement_pressures_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.settlement_pressure_notices.items())
                     if item.recipient_ref == actor_ref)

    def rite_observation(self, actor_ref, site_id):
        return self.rite_observations.get(rite_observation_id(actor_ref, site_id))

    def institutional_aid_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.institutional_aid_notices.items())
                     if item.recipient_ref == actor_ref)

    def authority_claims_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.authority_claim_notices.items())
                     if item.recipient_ref == actor_ref)

    def investigation_finding(self, actor_ref, investigation_id):
        item = self.investigation_findings.get(f"investigation_finding:{investigation_id}")
        return item if item is not None and item.recipient_ref == actor_ref else None

    def investigation_accusations_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.investigation_accusation_notices.items())
                     if item.recipient_ref == actor_ref)

    def espionage_findings_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.espionage_findings.items())
                     if item.recipient_ref == actor_ref)

    def technology_theft_findings_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.technology_theft_findings.items())
                     if item.recipient_ref == actor_ref)

    def civic_demands_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.civic_demand_notices.items())
                     if item.recipient_ref == actor_ref)

    def technology_sightings_for_actor(self, actor_ref, *, current_day=None):
        sightings = (item for _, item in sorted(self.technology_sightings.items())
                     if item.recipient_ref == actor_ref)
        if current_day is not None:
            sightings = (item for item in sightings if item.expires_day > current_day)
        return tuple(sightings)

    def has_current_technology_sighting(self, recipient_ref, holder_ref, technology_id, day):
        item = self.technology_sightings.get(technology_sighting_id(recipient_ref, holder_ref, technology_id))
        return item is not None and item.expires_day > day

    def validate(self, world=None):
        # During a live transaction, registry values are frozen SocietyValue
        # instances and owners replace entries instead of mutating them.  Keep
        # the structural and semantic provenance checks, but avoid serializing
        # every historical notice/report on each nested owner candidate.  Full
        # model revalidation still runs through ``validate()`` on load/save.
        if world is None:
            super().validate(world)
        else:
            if self._structural_validation_epoch != self._registry_epoch:
                self.validate_registry_structure()
                object.__setattr__(self, "_structural_validation_epoch", self._registry_epoch)
        if world is None:
            return
        events = world.event_index()
        # A single owner transaction may validate the same knowledge snapshot
        # more than once (for example after validating both economy and
        # relations).  Canonical knowledge changes are event-backed, so the
        # append-only ledger prefix plus current day is a sufficient transient
        # invalidation key.  This is only an in-memory optimization: load/save
        # still performs the complete model validation through ``world is
        # None`` and every new fact invalidates the key.
        validation_key = (
            len(world.events),
            id(world.events[-1]) if world.events else 0,
            world.clock.absolute_day,
            self._registry_epoch,
        )
        if getattr(self, "_semantic_validation_key", None) == validation_key:
            return
        for notice in self.notices.values():
            p = world.relations.proposals.get(notice.proposal_id)
            event = events.get(notice.event_id)
            if (p is None or notice.recipient_ref not in (p.proposer_ref, p.counterparty_ref) or event is None
                    or notice.id != f'notice:{notice.event_id}:{notice.recipient_ref.kind}:{notice.recipient_ref.id}'
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or not any(d.owner_id == p.id or d.owner_id.startswith(p.id + ':term:') for d in event.deltas)):
                raise ValueError('invalid diplomatic notice provenance')
        for notice in self.authority_claim_notices.values():
            validate_actor(world, notice.recipient_ref)
            claim = world.authority.claims.get(notice.claim_id)
            event = events.get(notice.event_id)
            if (claim is None or event is None
                    or notice.id != authority_claim_notice_id(notice.claim_id, notice.recipient_ref)
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or event.event_type != "authority_claim_declared"
                    or not any(delta.owner_kind == "authority_claim_notice" and delta.owner_id == notice.id
                               and delta.aspect == "claim_id" and delta.after == notice.claim_id
                               for delta in event.deltas)):
                raise ValueError("invalid authority claim notice provenance")
        if len({(k.owner_ref, k.technology_id) for k in self.technologies.values()}) != len(self.technologies):
            raise ValueError('duplicate technical knowledge')
        for item in self.technologies.values():
            validate_actor(world, item.owner_ref)
            event = events.get(item.event_id)
            if (item.id != f'technology:{item.owner_ref.kind}:{item.owner_ref.id}:{item.technology_id}'
                    or item.technology_id not in world.research.technologies or event is None
                    or item.learned_day > world.clock.absolute_day or event.day != item.learned_day
                    or event.event_type != {'research': 'technology_discovered', 'teaching': 'technology_taught',
                                            'apprenticeship': 'technology_apprenticed',
                                            'copied': 'technique_copy_completed',
                                            'sale': 'technology_sold',
                                            'stolen': 'technology_stolen'}[item.channel]
                    or not any(d.owner_kind == 'technical_knowledge' and d.owner_id == item.id
                               and d.aspect == 'technology_id' and d.before == 'None' and d.after == item.technology_id
                               for d in event.deltas)):
                raise ValueError('invalid technical knowledge provenance')
        for item in self.technology_sightings.values():
            validate_actor(world, item.recipient_ref)
            validate_actor(world, item.holder_ref)
            source = events.get(item.source_event_id)
            receipt = events.get(item.event_id)
            known = next((knowledge for knowledge in self.technologies.values()
                          if knowledge.owner_ref == item.holder_ref and knowledge.technology_id == item.technology_id), None)
            if (item.id != technology_sighting_id(item.recipient_ref, item.holder_ref, item.technology_id)
                    or known is None or known.event_id != item.source_event_id or source is None or receipt is None
                    or source.event_type not in {"technology_discovered", "technology_taught", "technology_apprenticed"}
                    or source.day > item.observed_day or receipt.event_type != "technology_sighting_received"
                    or receipt.fact_kind != FactKind.STATE_TRANSITION or receipt.day != item.observed_day
                    or item.observed_day > world.clock.absolute_day
                    or item.expires_day > item.observed_day + 180
                    or item.source_event_id not in {link.cause_event_id for link in receipt.causal_links}
                    or not any(delta.owner_kind == "technology_sighting" and delta.owner_id == item.id
                               and delta.aspect == "source_event_id" and delta.after == item.source_event_id
                               for delta in receipt.deltas)
                    or not any((decision := events.get(link.cause_event_id)) is not None
                               and decision.fact_kind == FactKind.DECISION
                               and decision.decision == {
                                   "action": "disclose_technology_sighting",
                                   "actor_ref": item.holder_ref.to_dict(),
                                   "selected_affordance_id": (
                                       f"technology-disclosure:{item.holder_ref.kind}:{item.holder_ref.id}:"
                                       f"{item.recipient_ref.kind}:{item.recipient_ref.id}:{item.technology_id}:"
                                       f"{item.source_event_id}"),
                               }
                               for link in receipt.causal_links)):
                raise ValueError("invalid technology sighting provenance")
        for report in self.reports.values():
            validate_actor(world, report.recipient_ref)
            validate_actor(world, report.publisher_ref)
            event = events.get(report.event_id)
            if (report.stock_id not in world.economy.stocks or report.resource_id not in world.economy.resources or event is None
                    or event.day != report.observed_day or report.observed_day > world.clock.absolute_day
                    or report.quote_day > report.observed_day):
                raise ValueError("invalid knowledge provenance")
            if ((report.kind == "inventory" and (report.channel != "administrative_report"
                                                 or report.recipient_ref != report.publisher_ref))
                    or (report.kind == "offer" and report.channel != "market_bulletin")):
                raise ValueError("knowledge requires a valid disclosure channel")
            self._validate_export_quote(events, report)
        for report in self.route_reports.values():
            self._validate_route_report(world, events, report)
        for report in self.fiscal_route_reports.values():
            self._validate_fiscal_route_report(world, events, report)
        for report in self.settlement_reports.values():
            self._validate_settlement_report(world, events, report)
        for report in self.site_reports.values():
            self._validate_site_report(world, events, report)
        for notice in self.customs_notices.values():
            self._validate_customs_notice(world, events, notice)
        for report in self.workforce_demand_reports.values():
            self._validate_workforce_demand(world, events, report)
        for notice in self.workforce_offer_notices.values():
            self._validate_workforce_offer(world, events, notice)
        for notice in self.institutional_aid_notices.values():
            self._validate_institutional_aid_notice(world, events, notice)
        for notice in self.creature_tribute_notices.values():
            validate_actor(world, notice.recipient_ref)
            demand = world.creatures.demands.get(notice.demand_id)
            event = events.get(notice.event_id)
            if (demand is None or event is None
                    or notice.id != creature_tribute_notice_id(notice.demand_id, notice.recipient_ref)
                    or notice.creature_id != demand.creature_id or notice.route_id != demand.route_id
                    or notice.food != demand.food or notice.due_day != demand.due_day
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or event.event_type != "creature_demanded_tribute"):
                raise ValueError("invalid creature tribute notice provenance")
        for notice in self.creature_damage_notices.values():
            validate_actor(world, notice.recipient_ref)
            demand = world.creatures.demands.get(notice.demand_id)
            site = world.map.infrastructure_sites.get(notice.site_id)
            event = events.get(notice.event_id)
            route = world.map.routes.get(notice.route_id)
            holders = {item.recipient_ref for item in self.creature_tribute_notices.values()
                       if item.demand_id == notice.demand_id}
            damage_causes = ([events.get(link.cause_event_id) for link in event.causal_links]
                             if event is not None else [])
            if (demand is None or site is None or route is None or event is None
                    or notice.id != creature_damage_notice_id(notice.demand_id, notice.site_id,
                                                              notice.recipient_ref)
                    or notice.recipient_ref not in holders or notice.route_id != demand.route_id
                    or notice.route_id not in site.route_ids
                    or not set(site.region_ids).intersection(route.endpoint_region_ids)
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or event.event_type != "creature_damage_noticed"
                    or event.fact_kind != FactKind.STATE_TRANSITION
                    or not any(candidate is not None and candidate.event_type == "creature_damaged_site"
                               and any(delta.owner_kind == "site" and delta.owner_id == notice.site_id
                                       and delta.aspect == "integrity"
                                       for delta in candidate.deltas)
                               for candidate in damage_causes)
                    or not any(delta.owner_kind == "creature_damage_notice"
                               and delta.owner_id == notice.id and delta.aspect == "observation"
                               for delta in event.deltas)):
                raise ValueError("invalid creature damage notice provenance")
        for notice in self.force_contact_notices.values():
            self._validate_force_contact_notice(world, events, notice)
        for notice in self.field_engagement_offer_notices.values():
            self._validate_field_engagement_offer_notice(world, events, notice)
        for notice in self.field_engagement_outcome_notices.values():
            self._validate_field_engagement_outcome_notice(world, events, notice)
        for notice in self.campaign_supply_notices.values():
            self._validate_campaign_supply_notice(world, events, notice)
        for notice in self.settlement_pressure_notices.values():
            self._validate_settlement_pressure_notice(world, events, notice)
        for observation in self.rite_observations.values():
            self._validate_rite_observation(world, events, observation)
        for finding in self.investigation_findings.values():
            self._validate_investigation_finding(world, events, finding)
        for notice in self.investigation_accusation_notices.values():
            self._validate_investigation_accusation(world, events, notice)
        for finding in self.espionage_findings.values():
            self._validate_espionage_finding(world, events, finding)
        for finding in self.technology_theft_findings.values():
            self._validate_technology_theft_finding(world, events, finding)
        for notice in self.civic_demand_notices.values():
            validate_actor(world, notice.recipient_ref)
            protest = world.society.civic_protests.get(notice.protest_id)
            event = events.get(notice.event_id)
            if (protest is None or event is None or notice.recipient_ref.kind != "polity"
                    or notice.id != civic_demand_notice_id(notice.protest_id, notice.recipient_ref)
                    or notice.group_id != protest.group_id or notice.settlement_id != protest.settlement_id
                    or notice.demand_kind != protest.demand_kind or notice.food_quantity != protest.food_quantity
                    or notice.site_id != protest.site_id or notice.due_day != protest.due_day
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or event.event_type != "civic_demand_received"
                    or not any(delta.owner_kind == "civic_demand_notice" and delta.owner_id == notice.id
                               and delta.aspect == "demand" for delta in event.deltas)):
                raise ValueError("invalid civic demand notice provenance")
        object.__setattr__(self, "_semantic_validation_key", validation_key)

    @staticmethod
    def _validate_investigation_finding(world, events, finding):
        validate_actor(world, finding.recipient_ref)
        investigation = world.economy.investigations.get(finding.investigation_id)
        event = events.get(finding.event_id)
        if (investigation is None or event is None or finding.damage_event_id != investigation.damage_event_id
                or finding.recipient_ref != investigation.investigator_ref
                or finding.learned_day != event.day or finding.learned_day > world.clock.absolute_day
                or event.event_type != "investigation_completed"
                or not any(delta.owner_kind == "investigation_finding" and delta.owner_id == finding.id
                           and delta.aspect == "result" and delta.after == finding.result for delta in event.deltas)):
            raise ValueError("invalid investigation finding provenance")
        if finding.result == "attributed":
            validate_actor(world, finding.subject_ref)

    @staticmethod
    def _validate_investigation_accusation(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.accuser_ref)
        validate_actor(world, notice.subject_ref)
        investigation = world.economy.investigations.get(notice.investigation_id)
        finding = world.knowledge.investigation_findings.get(
            f"investigation_finding:{notice.investigation_id}")
        event = events.get(notice.event_id)
        finding_event = events.get(notice.finding_event_id)
        if (notice.id != investigation_accusation_notice_id(notice.investigation_id, notice.recipient_ref)
                or investigation is None or investigation.stage != "attributed"
                or finding is None or finding.result != "attributed"
                or finding.recipient_ref != notice.accuser_ref
                or finding.subject_ref != notice.subject_ref
                or finding.event_id != notice.finding_event_id
                or investigation.site_id != notice.site_id
                or event is None or finding_event is None
                or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                or event.event_type != "investigation_accusation"
                or event.fact_kind != FactKind.STATE_TRANSITION
                or notice.finding_event_id not in {link.cause_event_id for link in event.causal_links}
                or not any(delta.owner_kind == "investigation_accusation_notice"
                           and delta.owner_id == notice.id and delta.aspect == "finding_event_id"
                           and delta.after == notice.finding_event_id for delta in event.deltas)):
            raise ValueError("invalid investigation accusation provenance")

    @staticmethod
    def _validate_espionage_finding(world, events, finding):
        validate_actor(world, finding.recipient_ref)
        validate_actor(world, finding.agent_ref)
        target = world.society.settlements.get(finding.target_ref.id)
        decision = events.get(finding.decision_event_id)
        event = events.get(finding.event_id)
        evidence = events.get(finding.evidence_event_id) if finding.evidence_event_id else None
        if (target is None or finding.target_owner_ref.kind != "polity"
                or finding.target_owner_ref.id != target.administrator_id
                or decision is None or decision.fact_kind != FactKind.DECISION
                or decision.decision != {"action": "espionage_mission",
                                         "actor_ref": finding.recipient_ref.to_dict(),
                                         "selected_affordance_id": finding.mission_id}
                or event is None or event.event_type != "espionage_resolved"
                or finding.learned_day != event.day or finding.learned_day > world.clock.absolute_day
                or finding.decision_event_id not in {link.cause_event_id for link in event.causal_links}
                or not any(delta.owner_kind == "espionage_finding" and delta.owner_id == finding.id
                           and delta.aspect == "result" and delta.after == finding.result for delta in event.deltas)):
            raise ValueError("invalid espionage finding provenance")
        if finding.result == "success":
            if (evidence is None or evidence.event_type != "settlement_observed"
                    or finding.evidence_event_id not in {link.cause_event_id for link in event.causal_links}
                    or not any(delta.owner_kind == "espionage_finding" and delta.owner_id == finding.id
                               and delta.aspect == "evidence_event_id" and delta.after == finding.evidence_event_id
                               for delta in event.deltas)):
                raise ValueError("successful espionage requires canonical evidence")

    @staticmethod
    def _validate_technology_theft_finding(world, events, finding):
        validate_actor(world, finding.recipient_ref)
        validate_actor(world, finding.agent_ref)
        validate_actor(world, finding.target_owner_ref)
        site = world.map.infrastructure_sites.get(finding.site_id)
        decision = events.get(finding.decision_event_id)
        receipt = events.get(finding.event_id)
        observation = events.get(finding.observation_event_id)
        held = next((item for item in world.knowledge.technologies.values()
                     if item.owner_ref == finding.target_owner_ref
                     and item.technology_id == finding.technology_id), None)
        operation = next((event for link in receipt.causal_links
                          if (event := events.get(link.cause_event_id)) is not None
                          and event.event_type == "production_completed"
                          and isinstance((event.causal_payload or {}).get("production"), dict)
                          and (event.causal_payload or {})["production"].get("site_id") == finding.site_id
                          and (event.causal_payload or {})["production"].get("batches", 0) > 0
                          and (recipe := world.economy.recipes.get(
                              (event.causal_payload or {})["production"].get("recipe_id"))) is not None
                          and recipe.required_technology_id == finding.technology_id
                          and held is not None
                          and held.event_id in {cause.cause_event_id for cause in event.causal_links}
                          and 0 <= finding.learned_day - event.day < 30), None) if receipt else None
        if (site is None or site.owner_ref != finding.target_owner_ref
                or finding.technology_id not in world.research.technologies
                or decision is None or decision.fact_kind != FactKind.DECISION
                or decision.decision != {"action": "steal_technology",
                                         "actor_ref": finding.recipient_ref.to_dict(),
                                         "selected_affordance_id": finding.mission_id}
                or receipt is None or receipt.event_type != "technology_theft_resolved"
                or operation is None
                or finding.learned_day != receipt.day or finding.learned_day > world.clock.absolute_day
                or finding.decision_event_id not in {link.cause_event_id for link in receipt.causal_links}
                or observation is None or observation.event_type != "site_observed"
                or observation.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "site_report"
                           and delta.owner_id == site_report_id(finding.recipient_ref, finding.site_id)
                           and delta.aspect == "observation" for delta in observation.deltas)
                or finding.observation_event_id not in {link.cause_event_id for link in receipt.causal_links}
                or not any(delta.owner_kind == "technology_theft_finding" and delta.owner_id == finding.id
                           and delta.aspect == "result" and delta.after == finding.result
                           for delta in receipt.deltas)):
            raise ValueError("invalid technology theft finding provenance")
        if finding.result != "success":
            return
        source = events.get(finding.source_knowledge_event_id)
        learned = events.get(finding.learned_knowledge_event_id)
        source_knowledge = next((item for item in world.knowledge.technologies.values()
                                 if item.owner_ref == finding.target_owner_ref
                                 and item.technology_id == finding.technology_id
                                 and item.event_id == finding.source_knowledge_event_id), None)
        learned_knowledge = next((item for item in world.knowledge.technologies.values()
                                  if item.owner_ref == finding.recipient_ref
                                  and item.technology_id == finding.technology_id
                                  and item.event_id == finding.learned_knowledge_event_id), None)
        if (source is None or learned is None or source_knowledge is None or learned_knowledge is None
                or source.id not in {link.cause_event_id for link in receipt.causal_links}
                or learned.id not in {link.cause_event_id for link in receipt.causal_links}
                or learned.event_type != "technology_stolen"
                or learned_knowledge.channel != "stolen"
                or not any(delta.owner_kind == "technology_theft_finding" and delta.owner_id == finding.id
                           and delta.aspect == "source_knowledge_event_id"
                           and delta.after == finding.source_knowledge_event_id for delta in receipt.deltas)
                or not any(delta.owner_kind == "technology_theft_finding" and delta.owner_id == finding.id
                           and delta.aspect == "learned_knowledge_event_id"
                           and delta.after == finding.learned_knowledge_event_id for delta in receipt.deltas)):
            raise ValueError("successful technology theft requires canonical knowledge provenance")

    @staticmethod
    def _validate_rite_observation(world, events, observation):
        validate_actor(world, observation.recipient_ref)
        event = events.get(observation.event_id)
        settlement = world.society.settlements.get(observation.settlement_id)
        site = world.map.infrastructure_sites.get(observation.site_id)
        if (event is None or settlement is None or site is None
                or observation.id != rite_observation_id(observation.recipient_ref, observation.site_id)
                or settlement.region_id not in site.region_ids
                or observation.observed_day != event.day or observation.observed_day > world.clock.absolute_day
                or event.event_type != "rite_observed" or event.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "rite_observation" and delta.owner_id == observation.id
                           and delta.aspect == "stage" and delta.after == observation.stage
                           for delta in event.deltas)
                or not any(delta.owner_kind == "rite_observation" and delta.owner_id == observation.id
                           and delta.aspect == "assistants_band" and delta.after == observation.assistants_band
                           for delta in event.deltas)):
            raise ValueError("invalid rite observation provenance")

    @staticmethod
    def _validate_settlement_pressure_notice(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        investment = world.society.settlement_investments.get(notice.investment_id)
        event = events.get(notice.event_id)
        settlement = world.society.settlements.get(notice.settlement_id)
        # This is a historical notice to the administration that received it.
        # A later, factual administration transfer must not rewrite or
        # invalidate that prior knowledge receipt.
        if (investment is None or event is None or settlement is None
                or notice.id != settlement_pressure_notice_id(investment.id, notice.recipient_ref)
                or notice.settlement_id != investment.settlement_id
                or notice.route_count != len(investment.route_ids)
                or notice.recipient_ref.kind != "polity"
                or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                or event.event_type != "settlement_invested"
                or not any(delta.owner_kind == "settlement_pressure_notice" and delta.owner_id == notice.id
                           and delta.aspect == "route_count" and delta.after == str(notice.route_count)
                           for delta in event.deltas)):
            raise ValueError("invalid settlement pressure notice provenance")

    @staticmethod
    def _validate_force_contact_notice(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.counterparty_ref)
        standoff = world.society.force_standoffs.get(notice.standoff_id)
        own = world.society.detachments.get(notice.own_detachment_id)
        receipt = events.get(notice.event_id)
        latest = events.get(notice.last_event_id)
        if (standoff is None or own is None or receipt is None or latest is None
                or notice.id != force_contact_notice_id(notice.standoff_id, notice.recipient_ref)
                or notice.recipient_ref != own.owner_ref or notice.own_detachment_id not in standoff.detachment_ids
                or notice.settlement_id != standoff.settlement_id or notice.learned_day != latest.day
                or notice.learned_day > world.clock.absolute_day
                or receipt.event_type != "armed_standoff_observed" or receipt.fact_kind != FactKind.STATE_TRANSITION
                or standoff.started_event_id not in {link.cause_event_id for link in receipt.causal_links}
                or not any(delta.owner_kind == "force_contact_notice" and delta.owner_id == notice.id
                           and delta.aspect == "observation" and delta.after == notice.standoff_id
                           for delta in receipt.deltas)
                or not any(delta.owner_kind == "force_contact_notice" and delta.owner_id == notice.id
                           and delta.aspect == "counterparty_strength_band"
                           for delta in receipt.deltas)
                or not any(delta.owner_kind == "force_contact_notice" and delta.owner_id == notice.id
                           and delta.aspect == "counterparty_posture" for delta in receipt.deltas)):
            raise ValueError("invalid private force contact notice")
        if notice.last_event_id != notice.event_id and (
                latest.event_type != "force_contact_sighting_observed" or latest.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "force_contact_notice" and delta.owner_id == notice.id
                           and delta.aspect == "learned_day" and delta.after == str(notice.learned_day)
                           for delta in latest.deltas)
                or not any(delta.owner_kind == "force_contact_notice" and delta.owner_id == notice.id
                           and delta.aspect in {"counterparty_strength_band", "counterparty_posture"}
                           for delta in latest.deltas)):
            raise ValueError("force contact sighting lacks its factual receipt")
        other_id = next(identity for identity in standoff.detachment_ids if identity != notice.own_detachment_id)
        other = world.society.detachments.get(other_id)
        if other is None or notice.counterparty_ref != other.owner_ref:
            raise ValueError("force contact notice has the wrong observed rival")

    @staticmethod
    def _validate_field_engagement_offer_notice(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.challenger_ref)
        engagement = world.society.field_engagements.get(notice.engagement_id)
        event = events.get(notice.event_id)
        if (engagement is None or event is None or notice.recipient_ref != engagement.defender_ref
                or notice.challenger_ref != engagement.challenger_ref or notice.standoff_id != engagement.standoff_id
                or notice.settlement_id != engagement.settlement_id
                or notice.id != field_engagement_offer_notice_id(engagement.id, notice.recipient_ref)
                or notice.event_id != engagement.offer_event_id or notice.learned_day != event.day
                or event.event_type != "field_engagement_offered"
                or not any(delta.owner_kind == "field_engagement_offer_notice" and delta.owner_id == notice.id
                           and delta.aspect == "engagement_id" and delta.after == engagement.id
                           for delta in event.deltas)):
            raise ValueError("invalid field engagement offer notice")

    @staticmethod
    def _validate_field_engagement_outcome_notice(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.counterparty_ref)
        engagement = world.society.field_engagements.get(notice.engagement_id)
        event = events.get(notice.event_id)
        if engagement is None or event is None or engagement.status != "resolved":
            raise ValueError("invalid field engagement outcome notice")
        if notice.recipient_ref == engagement.challenger_ref:
            casualties, counterparty, own_detachment_id = (engagement.challenger_casualties,
                                                            engagement.defender_ref,
                                                            engagement.challenger_detachment_id)
            expected_outcome = ("won" if engagement.winner_ref == engagement.challenger_ref else
                                "lost" if engagement.winner_ref == engagement.defender_ref else "indecisive")
        elif notice.recipient_ref == engagement.defender_ref:
            casualties, counterparty, own_detachment_id = (engagement.defender_casualties,
                                                            engagement.challenger_ref,
                                                            engagement.defender_detachment_id)
            expected_outcome = ("won" if engagement.winner_ref == engagement.defender_ref else
                                "lost" if engagement.winner_ref == engagement.challenger_ref else "indecisive")
        else:
            raise ValueError("field engagement outcome recipient is not a participant")
        if (notice.counterparty_ref != counterparty or notice.own_detachment_id != own_detachment_id
                or notice.own_casualties != casualties
                or notice.outcome != expected_outcome
                or notice.id != field_engagement_outcome_notice_id(engagement.id, notice.recipient_ref)
                or notice.settlement_id != engagement.settlement_id or notice.learned_day != event.day
                or notice.event_id != event.id or event.id != engagement.last_event_id
                or not any(delta.owner_kind == "field_engagement_outcome_notice" and delta.owner_id == notice.id
                           and delta.aspect == "outcome" and delta.after == notice.outcome for delta in event.deltas)):
            raise ValueError("invalid field engagement outcome notice")
    @staticmethod
    def _validate_campaign_supply_notice(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        detachment = world.society.detachments.get(notice.detachment_id)
        opened = events.get(notice.event_id)
        final = events.get(notice.last_event_id)
        if (detachment is None or opened is None or final is None
                or notice.id != campaign_supply_notice_id(notice.detachment_id, notice.event_id)
                or notice.recipient_ref != detachment.owner_ref or notice.settlement_id not in world.society.settlements
                or notice.learned_day != opened.day or notice.learned_day > world.clock.absolute_day
                or opened.event_type != "campaign_supply_observed" or opened.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "campaign_supply_notice" and delta.owner_id == notice.id
                           and delta.aspect == "state" and delta.before == "None" and delta.after == "open"
                           for delta in opened.deltas)):
            raise ValueError("invalid campaign supply notice")
        if notice.state == "open" and (notice.freight_id is not None or notice.last_event_id != notice.event_id):
            raise ValueError("open campaign supply notice has an invalid lifecycle")
        if notice.state in {"dispatched", "fulfilled"}:
            order = world.economy.freight_orders.get(notice.freight_id)
            if (order is None or order.destination_id != f"stock:camp:{notice.detachment_id}"
                    or order.owner_ref != notice.recipient_ref):
                raise ValueError("campaign supply notice lacks its own freight")
        if notice.state != "open" and not any(
                delta.owner_kind == "campaign_supply_notice" and delta.owner_id == notice.id
                and delta.aspect == "state" and delta.after == notice.state for delta in final.deltas):
            raise ValueError("campaign supply notice lacks its final receipt")

    @staticmethod
    def _validate_institutional_aid_notice(world, events, notice):
        """Only the named participant can learn an aid request/response.

        The receipt is deliberately verified from recorded decisions, deltas and
        causal links.  A snapshot edit cannot introduce a discoverable request
        because it would need to reproduce this complete factual chain.
        """
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.requester_ref)
        request = events.get(notice.request_event_id)
        event = events.get(notice.event_id)
        if (notice.id != institutional_aid_notice_id(notice.event_id, notice.recipient_ref)
                or request is None or event is None or notice.learned_day != event.day
                or notice.learned_day > world.clock.absolute_day
                or notice.channel != "direct_institutional_aid"):
            raise ValueError("invalid institutional aid notice provenance")

        request_decisions = [events[link.cause_event_id] for link in request.causal_links
                             if link.cause_event_id in events]
        request_decision = next((item for item in request_decisions
                                 if item.fact_kind == FactKind.DECISION
                                 and (item.decision or {}).get("action") == "request_institutional_aid"), None)
        def request_delta_value(aspect):
            values = [delta.after for delta in request.deltas
                      if delta.owner_kind == "aid_request" and request_decision is not None
                      and delta.owner_id == f"aid-request:{request_decision.id}" and delta.aspect == aspect]
            return values[0] if len(values) == 1 else None
        if (request.event_type != "institutional_aid_requested" or request.fact_kind != FactKind.STATE_TRANSITION
                or request_decision is None or (request_decision.decision or {}).get("actor_ref") != notice.requester_ref.to_dict()
                or request_delta_value("status") != "requested"
                or request_delta_value("requester_settlement_id") != notice.requester_settlement_id
                or request_delta_value("report_id") != notice.report_id):
            raise ValueError("invalid institutional aid request notice provenance")
        report_events = [events[link.cause_event_id] for link in request.causal_links if link.cause_event_id in events]
        observations = [delta.after for candidate in report_events if candidate.fact_kind == FactKind.STATE_TRANSITION
                        for delta in candidate.deltas
                        if delta.owner_kind == "settlement_report" and delta.owner_id == notice.report_id]
        if not observations:
            raise ValueError("institutional aid notice lacks its settlement report cause")
        # The asked-for need is copied once, at request time, and must still
        # match the causal observation. Nothing else of the requester travels.
        try:
            observed_need = [json.loads(payload).get("missing_food") for payload in observations]
        except (TypeError, ValueError) as exc:
            raise ValueError("institutional aid notice lacks its settlement report cause") from exc
        if (request_delta_value("requested_food") != str(notice.requested_food)
                or notice.requested_food not in observed_need):
            raise ValueError("institutional aid notice must carry the requested need of its report")

        if notice.kind == "request":
            if (notice.event_id != request.id or notice.response_status is not None
                    or request_delta_value("provider_ref") != json.dumps(
                        notice.recipient_ref.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)):
                raise ValueError("invalid institutional aid request recipient")
            return

        response_decisions = [events[link.cause_event_id] for link in event.causal_links
                              if link.cause_event_id in events]
        response_decision = next((item for item in response_decisions
                                  if item.fact_kind == FactKind.DECISION
                                  and (item.decision or {}).get("action") == "respond_institutional_aid"), None)
        expected_type = f"institutional_aid_{notice.response_status}" if notice.response_status else None
        if (notice.recipient_ref != notice.requester_ref or notice.response_status not in {"accepted", "rejected"}
                or event.event_type != expected_type or event.fact_kind != FactKind.STATE_TRANSITION
                or request.id not in {link.cause_event_id for link in event.causal_links}
                or response_decision is None
                or request_delta_value("provider_ref") != json.dumps(
                    (response_decision.decision or {}).get("actor_ref"), sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False)
                or not any(delta.owner_kind == "aid_request" and delta.owner_id == f"aid-request:{request.id}"
                           and delta.aspect == "status" and delta.before == "requested"
                           and delta.after == notice.response_status for delta in event.deltas)):
            raise ValueError("invalid institutional aid response notice provenance")

    @staticmethod
    def _validate_workforce_demand(world, events, report):
        """The report must cite one current-cycle material labour limitation."""
        validate_actor(world, report.recipient_ref)
        validate_actor(world, report.publisher_ref)
        receipt = events.get(report.event_id)
        source = events.get(report.source_event_id)
        observation = report.observation()
        if (report.recipient_ref != report.sponsor_ref or report.publisher_ref != report.sponsor_ref
                or report.id != workforce_demand_report_id(report.sponsor_ref, report.work_kind, report.work_id)
                or receipt is None or source is None or report.observed_day > world.clock.absolute_day
                or receipt.day != report.observed_day or source.day != report.observed_day
                or receipt.event_type != "workforce_demand_observed" or receipt.fact_kind != FactKind.STATE_TRANSITION
                or report.source_event_id not in {link.cause_event_id for link in receipt.causal_links}
                or not any(delta.owner_kind == "workforce_demand" and delta.owner_id == report.id
                           and delta.aspect == "observation" and delta.after == observation for delta in receipt.deltas)):
            raise ValueError("invalid workforce demand provenance")
        def shortfall(owner_kind):
            """Typed, quantified labour signal from the source work receipt."""
            values = [int(delta.after) for delta in source.deltas
                      if delta.owner_kind == owner_kind and delta.owner_id == report.work_id
                      and delta.aspect == "labor_shortfall" and delta.after.isdecimal()]
            return max(values) if values else 0

        def expanded_demand():
            """Engine-owned scaling receipt for a pressure-sized farmer demand."""
            values = [int(delta.after) for delta in receipt.deltas
                      if delta.owner_kind == "workforce_demand" and delta.owner_id == report.id
                      and delta.aspect == "count" and delta.after.isdecimal()]
            return max(values) if values else 0

        if report.work_kind == "facility":
            if (source.event_type not in {"production_completed", "production_limited"}
                    or report.target_occupation not in {"farmer", "artisan"}
                    or not 0 < report.count <= shortfall("production")
                    and report.count != expanded_demand()):
                raise ValueError("workforce facility demand lacks a material labour receipt")
            return
        if report.work_kind == "repair":
            if (source.event_type != "repair_progressed" or report.target_occupation != "artisan"
                    or not 0 < report.count <= shortfall("repair")):
                raise ValueError("workforce repair demand lacks a material labour receipt")
            return
        if report.work_kind == "research":
            project = world.research.projects.get(report.work_id)
            technology = (world.research.technologies.get(project.technology_id)
                          if project is not None else None)
            if (source.event_type != "research_progressed" or project is None or technology is None
                    or report.sponsor_ref != project.owner_ref
                    or report.target_occupation != technology.assistant_occupation
                    or report.account_id != project.account_id
                    or not 0 < report.count <= shortfall("research")):
                raise ValueError("workforce research demand lacks a material labour receipt")
            return
        if report.work_kind == "military_recruitment":
            plans = (world.strategy.plans.get(delta.after) for delta in source.deltas
                     if delta.owner_kind == "military_recruitment" and delta.owner_id == report.work_id
                     and delta.aspect == "plan_id")
            plan = next((item for item in plans if item is not None), None)
            objective = world.strategy.objectives.get(plan.objective_id) if plan is not None else None
            settlement = world.society.settlements.get(report.work_id)
            account = world.economy.accounts.get(report.account_id)
            if (source.event_type != "strategy_defense_plan_updated" or plan is None or objective is None
                    or objective.kind != "defend_occupied_settlement"
                    or objective.actor_ref != report.sponsor_ref
                    or settlement is None or settlement.administrator_id != report.sponsor_ref.id
                    or account is None or account.owner_ref != report.sponsor_ref
                    or report.target_occupation != "soldier"
                    or not 0 < report.count <= shortfall("military_recruitment")
                    or not any(delta.owner_kind == "strategy_plan" and delta.owner_id == plan.id
                               and delta.aspect == "stage" and delta.after == "blocked"
                               for delta in source.deltas)):
                raise ValueError("workforce military demand lacks a material plan receipt")
            return
        if (report.target_occupation != "merchant" or report.work_id not in world.economy.customs_checkpoints
                or not 0 < report.count <= shortfall("customs_checkpoint")):
            raise ValueError("workforce customs demand lacks a material labour receipt")

    @staticmethod
    def _validate_workforce_offer(world, events, notice):
        validate_actor(world, notice.recipient_ref)
        validate_actor(world, notice.publisher_ref)
        demand = world.knowledge.workforce_demand_reports.get(notice.demand_id)
        receipt = events.get(notice.event_id)
        if (notice.recipient_ref != EntityRef("population_group", notice.source_group_id)
                or notice.publisher_ref != notice.sponsor_ref or demand is None
                or notice.id != workforce_offer_notice_id(notice.source_group_id, notice.demand_id)
                or demand.sponsor_ref != notice.sponsor_ref or demand.observed_day != notice.observed_day
                or demand.target_occupation != notice.target_occupation
                or notice.count > demand.count or notice.stipend_per_person != demand.stipend_per_person
                or receipt is None or receipt.day != notice.observed_day
                or receipt.event_type != "workforce_offer_received" or receipt.fact_kind != FactKind.STATE_TRANSITION
                or demand.event_id not in {link.cause_event_id for link in receipt.causal_links}
                or not any(delta.owner_kind == "workforce_offer" and delta.owner_id == notice.id
                           and delta.aspect == "observation" and delta.after == notice.observation()
                           for delta in receipt.deltas)):
            raise ValueError("invalid workforce offer provenance")
        if demand.work_kind == "military_recruitment":
            group = world.society.population.get(notice.source_group_id)
            decision_id = receipt.causal_payload.get("decision_event_id") if receipt.causal_payload else None
            decision = events.get(decision_id)
            expected_id = f"military-recruitment:{demand.id}:{demand.event_id}"
            if (group is None or group.settlement_id != demand.work_id
                    or receipt.causal_origin.value != "actor_decision" or decision is None
                    or decision.fact_kind != FactKind.DECISION
                    or decision_id not in {link.cause_event_id for link in receipt.causal_links}
                    or decision.decision != {"action": "authorize_military_recruitment",
                                             "actor_ref": demand.sponsor_ref.to_dict(),
                                             "selected_affordance_id": expected_id}):
                raise ValueError("military recruitment offer lacks sponsor decision")

    @staticmethod
    def _validate_customs_notice(world, events, notice):
        checkpoint = world.economy.customs_checkpoints.get(notice.checkpoint_id)
        order = world.economy.freight_orders.get(notice.order_id)
        event = events.get(notice.event_id)
        transition = events.get(notice.state_event_id)
        manifest = world.economy.cargo_manifests.get(notice.manifest_id) if notice.manifest_id else None
        resource = world.economy.resources.get(notice.resource_id)
        if (checkpoint is None or order is None or notice.id != f"customs_notice:{notice.parcel_id}"
                or notice.recipient_ref != order.owner_ref or notice.learned_day > world.clock.absolute_day
                or event is None or event.day != notice.learned_day
                or notice.resource_id != order.resource_id
                or resource is None or notice.classification != resource.trade_class
                or event.event_type != "customs_presented" or event.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "customs_notice" and delta.owner_id == notice.id
                           and delta.aspect == "state" and delta.before == "None" and delta.after == "presented"
                           for delta in event.deltas)
                or not any(delta.owner_kind == "customs_notice" and delta.owner_id == notice.id
                           and delta.aspect == "classification" and delta.before == "None"
                           and delta.after == notice.classification for delta in event.deltas)
                or transition is None
                or (notice.state == "presented" and (notice.state_event_id != notice.event_id or notice.fee is not None or notice.manifest_id is not None))
                or (notice.state in {"fee_due", "cleared"} and (manifest is None or manifest.parcel_id != notice.parcel_id
                    or manifest.order_id != notice.order_id or manifest.resource_id != notice.resource_id
                    or manifest.quantity != notice.quantity or notice.fee is None))
                or (notice.state in {"detected", "evaded_undetected", "returned", "seized", "refused"}
                    and (notice.manifest_id is not None or notice.fee is not None))
                or (notice.state != "presented" and notice.event_id not in {link.cause_event_id for link in transition.causal_links})
                or (notice.state == "fee_due" and transition.event_type != "cargo_manifest_declared")
                or (notice.state == "detected" and transition.event_type != "customs_fee_evasion_detected")
                or (notice.state == "evaded_undetected" and transition.event_type != "customs_fee_evaded")
                or (notice.state == "cleared" and transition.event_type != "customs_fee_paid")
                or (notice.state == "returned" and transition.event_type != "contraband_returned")
                or (notice.state == "seized" and transition.event_type != "contraband_seized")
                or (notice.state == "refused" and transition.event_type != "customs_refused")
                or (notice.state != "presented" and not any(delta.owner_kind == "customs_notice"
                    and delta.owner_id == notice.id and delta.aspect == "state" and delta.after == notice.state
                    for delta in transition.deltas))
                or (notice.state == "detected" and not {
                    (delta.aspect, delta.after) for delta in transition.deltas
                    if delta.owner_kind == "customs_inspection"
                } >= {("threshold_permille", "350")})):
            raise ValueError("invalid private customs notice")

    @staticmethod
    def _validate_export_quote(events, report):
        """A tariff quote is historical policy knowledge, never a live tax lookup."""
        collector = report.export_collector_ref
        policy_event_id = report.export_policy_event_id
        report_event = events.get(report.event_id)

        def published_quote_matches():
            if report.kind != "offer":
                return True
            quote = (report_event.decision or {}) if report_event is not None else {}
            return (quote.get("action") == "publish_offer"
                    and quote.get("export_rate_permille") == report.export_rate_permille
                    and quote.get("export_policy_event_id") == report.export_policy_event_id
                    and quote.get("export_collector_ref") == (collector.to_dict() if collector is not None else None))

        if collector is None:
            if (report.export_rate_permille != 0 or policy_event_id is not None
                    or not published_quote_matches()):
                raise ValueError("unadministered origin cannot quote an export tariff")
            return
        if collector.kind != "polity":
            raise ValueError("export collector must be the source polity")
        if policy_event_id is None:
            if report.export_rate_permille != 0 or not published_quote_matches():
                raise ValueError("only a zero bootstrap tariff lacks a policy receipt")
            return
        policy_event = events.get(policy_event_id)
        if (policy_event is None or report_event is None
                or policy_event_id not in {link.cause_event_id for link in report_event.causal_links}
                or not any(delta.owner_kind == "tax_policy" and delta.owner_id == collector.id
                           and delta.aspect == "export_rate_permille"
                           and delta.after == str(report.export_rate_permille)
                           for delta in policy_event.deltas)):
            raise ValueError("export quote requires its source policy receipt")
        if not published_quote_matches():
                raise ValueError("export offer requires its published tariff quote")

    @staticmethod
    def _validate_settlement_report(world, events, report):
        """Validate historical receipt chains without consulting today's settlement."""
        validate_actor(world, report.recipient_ref)
        validate_actor(world, report.publisher_ref)
        receipt = events.get(report.event_id)
        observation = report.observation()
        if (report.settlement_id not in world.society.settlements or receipt is None
                or report.id != settlement_report_id(report.recipient_ref, report.settlement_id)
                or report.observed_day > world.clock.absolute_day or receipt.day != report.observed_day):
            raise ValueError("invalid settlement knowledge provenance")

        def records(candidate, event_type, owner_id):
            return (candidate.event_type == event_type and candidate.fact_kind == FactKind.STATE_TRANSITION
                    and candidate.day == report.observed_day
                    and any(d.owner_kind == "settlement_report" and d.owner_id == owner_id
                            and d.aspect == "observation" and d.after == observation for d in candidate.deltas))

        def causes(event):
            return (events[link.cause_event_id] for link in event.causal_links if link.cause_event_id in events)

        if report.channel == "local_settlement_report":
            if report.recipient_ref != report.publisher_ref or not records(receipt, "settlement_observed", report.id):
                raise ValueError("settlement observation requires its own typed receipt")
            return
        own = settlement_report_id(report.publisher_ref, report.settlement_id)
        if report.recipient_ref == report.publisher_ref or not records(receipt, "settlement_report_received", report.id):
            raise ValueError("settlement bulletin requires its typed delivery receipt")
        published = [event for event in causes(receipt)
                     if event.fact_kind == FactKind.DECISION and event.day == report.observed_day
                     and (event.decision or {}).get("action") == "publish_settlement_report"
                     and event.decision.get("actor_ref") == report.publisher_ref.to_dict()
                     and event.decision.get("settlement_id") == report.settlement_id
                     and event.decision.get("observation") == observation
                     and report.recipient_ref.to_dict() in event.decision.get("recipients", [])]
        if not published:
            raise ValueError("settlement bulletin requires its publication decision")
        if not any(records(event, "settlement_observed", own) for decision in published for event in causes(decision)):
            raise ValueError("settlement bulletin requires the publisher's own observation receipt")

    @staticmethod
    def _validate_site_report(world, events, report):
        """Own dated physical/service observation, checked against its receipt.

        Do not compare against the current Map: a prior service reading remains
        truthful historical knowledge after a later suspension or resumption.
        """
        validate_actor(world, report.recipient_ref)
        validate_actor(world, report.publisher_ref)
        receipt = events.get(report.event_id)
        if (report.site_id not in world.map.infrastructure_sites or receipt is None
                or report.recipient_ref != report.publisher_ref
                or report.id != site_report_id(report.recipient_ref, report.site_id)
                or report.observed_day > world.clock.absolute_day or receipt.day != report.observed_day
                or report.channel not in {"administrative_site_report", "local_site_report"}
                or not isinstance(report.service_suspended, bool)
                or receipt.event_type != "site_observed" or receipt.fact_kind != FactKind.STATE_TRANSITION
                or not any(d.owner_kind == "site_report" and d.owner_id == report.id and d.aspect == "observation"
                           and d.after == report.observation() for d in receipt.deltas)):
            raise ValueError("site observation requires its own typed receipt")
        if report.channel == "local_site_report":
            group = world.society.population.get(report.recipient_ref.id)
            settlement = world.society.settlements.get(group.settlement_id) if group is not None else None
            site = world.map.infrastructure_sites[report.site_id]
            if (report.recipient_ref.kind != "population_group" or group is None or settlement is None
                    or settlement.region_id not in site.region_ids):
                raise ValueError("local site report requires a present local group")

    @staticmethod
    def _validate_route_report(world, events, report):
        """Check the historical receipts named by the report, never today's route.

        An observation stays valid after the physical route changes: it is a
        dated fact about what was seen, not a copy of canonical state. A
        bulletin needs the whole chain: the publisher's original observation,
        its publication intent and the delivery that actually reached this
        recipient. Intent alone never becomes knowledge.
        """
        validate_actor(world, report.recipient_ref)
        validate_actor(world, report.publisher_ref)
        receipt = events.get(report.event_id)
        observation = report.observation()
        if (report.route_id not in world.map.routes or receipt is None
                or report.id != route_report_id(report.recipient_ref, report.route_id)
                or report.observed_day > world.clock.absolute_day or receipt.day != report.observed_day):
            raise ValueError("invalid route knowledge provenance")

        def records(candidate, event_type, owner_id):
            return (candidate.event_type == event_type and candidate.fact_kind == FactKind.STATE_TRANSITION
                    and candidate.day == report.observed_day
                    and any(d.owner_kind == "route_report" and d.owner_id == owner_id
                            and d.aspect == "observation" and d.after == observation for d in candidate.deltas))

        def causes(event):
            return (events[link.cause_event_id] for link in event.causal_links if link.cause_event_id in events)

        if report.channel == "administrative_route_report":
            if report.recipient_ref != report.publisher_ref or not records(receipt, "route_observed", report.id):
                raise ValueError("route observation requires its own typed receipt")
            return
        own = route_report_id(report.publisher_ref, report.route_id)
        if report.recipient_ref == report.publisher_ref or not records(receipt, "route_report_received", report.id):
            raise ValueError("route bulletin requires its typed delivery receipt")
        published = [event for event in causes(receipt)
                     if event.fact_kind == FactKind.DECISION and event.day == report.observed_day
                     and (event.decision or {}).get("action") == "publish_route_report"
                     and event.decision.get("actor_ref") == report.publisher_ref.to_dict()
                     and event.decision.get("route_id") == report.route_id
                     and event.decision.get("observation") == observation
                     and report.recipient_ref.to_dict() in event.decision.get("recipients", [])]
        if not published:
            raise ValueError("route bulletin requires its publication decision")
        if not any(records(event, "route_observed", own) for decision in published for event in causes(decision)):
            raise ValueError("route bulletin requires the publisher's own observation receipt")

    @staticmethod
    def _validate_fiscal_route_report(world, events, report):
        """Validate dated checkpoint knowledge without consulting today's post."""
        validate_actor(world, report.recipient_ref)
        validate_actor(world, report.publisher_ref)
        receipt = events.get(report.event_id)
        checkpoint = world.economy.customs_checkpoints.get(report.checkpoint_id)
        observation = report.observation()
        if (report.route_id not in world.map.routes or checkpoint is None or receipt is None
                or report.id != fiscal_route_report_id(report.recipient_ref, report.route_id)
                or report.publisher_ref != checkpoint.operator_ref or report.fee_per_bulk != checkpoint.fee_per_bulk
                or report.observed_day > world.clock.absolute_day or receipt.day != report.observed_day):
            raise ValueError("invalid fiscal route knowledge provenance")

        def records(candidate, event_type, owner_id):
            return (candidate.event_type == event_type and candidate.fact_kind == FactKind.STATE_TRANSITION
                    and candidate.day == report.observed_day
                    and any(d.owner_kind == "fiscal_route_report" and d.owner_id == owner_id
                            and d.aspect == "observation" and d.after == observation for d in candidate.deltas))

        def causes(event):
            return (events[link.cause_event_id] for link in event.causal_links if link.cause_event_id in events)

        def sourced_by_checkpoint(event):
            return any(candidate.event_type in {"customs_opened", "customs_staff_paid"}
                       and any(delta.owner_kind == "customs_checkpoint" and delta.owner_id == checkpoint.id
                               for delta in candidate.deltas)
                       for candidate in causes(event))

        if report.channel == "administrative_fiscal_route_report":
            if (report.recipient_ref != report.publisher_ref
                    or not records(receipt, "fiscal_route_observed", report.id)
                    or not sourced_by_checkpoint(receipt)):
                raise ValueError("fiscal route observation requires its own typed receipt")
            return
        own = fiscal_route_report_id(report.publisher_ref, report.route_id)
        if report.recipient_ref == report.publisher_ref or not records(receipt, "fiscal_route_report_received", report.id):
            raise ValueError("fiscal route bulletin requires its typed delivery receipt")
        published = [event for event in causes(receipt)
                     if event.fact_kind == FactKind.DECISION and event.day == report.observed_day
                     and (event.decision or {}).get("action") == "publish_fiscal_route_report"
                     and event.decision.get("actor_ref") == report.publisher_ref.to_dict()
                     and event.decision.get("route_id") == report.route_id
                     and event.decision.get("observation") == observation
                     and report.recipient_ref.to_dict() in event.decision.get("recipients", [])]
        if not published:
            raise ValueError("fiscal route bulletin requires its publication decision")
        if not any(records(event, "fiscal_route_observed", own) and sourced_by_checkpoint(event)
                   for decision in published for event in causes(decision)):
            raise ValueError("fiscal route bulletin requires the publisher's own observation receipt")
