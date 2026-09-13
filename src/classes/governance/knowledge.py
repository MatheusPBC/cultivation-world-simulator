"""Single owner of actor-specific observations; canonical truth stays elsewhere."""

from dataclasses import dataclass, field
from .models import KnowledgeReport, DiplomaticNotice, RouteReport, SettlementReport, SiteReport, CustomsNotice
from .serialization import RegistrySerialization, validate_actor
from src.classes.event import FactKind
from src.classes.research.models import TechnicalKnowledge


def route_report_id(recipient_ref, route_id):
    return f"route_report:{recipient_ref.kind}:{recipient_ref.id}:{route_id}"


def site_report_id(recipient_ref, site_id):
    return f"site_report:{recipient_ref.kind}:{recipient_ref.id}:{site_id}"


def settlement_report_id(recipient_ref, settlement_id):
    return f"settlement_report:{recipient_ref.kind}:{recipient_ref.id}:{settlement_id}"


@dataclass
class KnowledgeState(RegistrySerialization):
    reports: dict[str, KnowledgeReport] = field(default_factory=dict)
    technologies: dict[str, TechnicalKnowledge] = field(default_factory=dict)
    notices: dict[str, DiplomaticNotice] = field(default_factory=dict)
    route_reports: dict[str, RouteReport] = field(default_factory=dict)
    settlement_reports: dict[str, SettlementReport] = field(default_factory=dict)
    site_reports: dict[str, SiteReport] = field(default_factory=dict)
    customs_notices: dict[str, CustomsNotice] = field(default_factory=dict)
    registries = {"reports": KnowledgeReport, "technologies": TechnicalKnowledge, "notices": DiplomaticNotice,
                  "route_reports": RouteReport, "settlement_reports": SettlementReport, "site_reports": SiteReport}
    registries["customs_notices"] = CustomsNotice

    def knows(self, actor_ref, technology_id):
        return any(k.owner_ref == actor_ref and k.technology_id == technology_id for k in self.technologies.values())

    def for_actor(self, actor_ref):
        return tuple(r for _, r in sorted(self.reports.items()) if r.recipient_ref == actor_ref)

    def routes_for_actor(self, actor_ref):
        """Latest dated observation per route this actor was told about."""
        return tuple(r for _, r in sorted(self.route_reports.items()) if r.recipient_ref == actor_ref)

    def route_report(self, actor_ref, route_id):
        return self.route_reports.get(route_report_id(actor_ref, route_id))

    def site_report(self, actor_ref, site_id):
        return self.site_reports.get(site_report_id(actor_ref, site_id))

    def customs_for_actor(self, actor_ref):
        return tuple(item for _, item in sorted(self.customs_notices.items()) if item.recipient_ref == actor_ref)

    def settlements_for_actor(self, actor_ref):
        return tuple(r for _, r in sorted(self.settlement_reports.items()) if r.recipient_ref == actor_ref)

    def settlement_report(self, actor_ref, settlement_id):
        return self.settlement_reports.get(settlement_report_id(actor_ref, settlement_id))

    def validate(self, world=None):
        super().validate(world)
        if world is None:
            return
        events = {e.id: e for e in world.events}
        for notice in self.notices.values():
            p = world.relations.proposals.get(notice.proposal_id)
            event = events.get(notice.event_id)
            if (p is None or notice.recipient_ref not in (p.proposer_ref, p.counterparty_ref) or event is None
                    or notice.id != f'notice:{notice.event_id}:{notice.recipient_ref.kind}:{notice.recipient_ref.id}'
                    or notice.learned_day != event.day or notice.learned_day > world.clock.absolute_day
                    or not any(d.owner_id == p.id or d.owner_id.startswith(p.id + ':term:') for d in event.deltas)):
                raise ValueError('invalid diplomatic notice provenance')
        if len({(k.owner_ref, k.technology_id) for k in self.technologies.values()}) != len(self.technologies):
            raise ValueError('duplicate technical knowledge')
        for item in self.technologies.values():
            validate_actor(world, item.owner_ref)
            event = events.get(item.event_id)
            if (item.id != f'technology:{item.owner_ref.kind}:{item.owner_ref.id}:{item.technology_id}'
                    or item.technology_id not in world.research.technologies or event is None
                    or item.learned_day > world.clock.absolute_day or event.day != item.learned_day
                    or event.event_type != {'research': 'technology_discovered', 'teaching': 'technology_taught'}[item.channel]
                    or not any(d.owner_kind == 'technical_knowledge' and d.owner_id == item.id
                               and d.aspect == 'technology_id' and d.before == 'None' and d.after == item.technology_id
                               for d in event.deltas)):
                raise ValueError('invalid technical knowledge provenance')
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
        for report in self.settlement_reports.values():
            self._validate_settlement_report(world, events, report)
        for report in self.site_reports.values():
            self._validate_site_report(world, events, report)
        for notice in self.customs_notices.values():
            self._validate_customs_notice(world, events, notice)

    @staticmethod
    def _validate_customs_notice(world, events, notice):
        checkpoint = world.economy.customs_checkpoints.get(notice.checkpoint_id)
        order = world.economy.freight_orders.get(notice.order_id)
        event = events.get(notice.event_id)
        transition = events.get(notice.state_event_id)
        manifest = world.economy.cargo_manifests.get(notice.manifest_id) if notice.manifest_id else None
        if (checkpoint is None or order is None or notice.id != f"customs_notice:{notice.parcel_id}"
                or notice.recipient_ref != order.owner_ref or notice.learned_day > world.clock.absolute_day
                or event is None or event.day != notice.learned_day
                or notice.resource_id != order.resource_id
                or event.event_type != "customs_presented" or event.fact_kind != FactKind.STATE_TRANSITION
                or not any(delta.owner_kind == "customs_notice" and delta.owner_id == notice.id
                           and delta.aspect == "state" and delta.before == "None" and delta.after == "presented"
                           for delta in event.deltas)
                or transition is None
                or (notice.state == "presented" and (notice.state_event_id != notice.event_id or notice.fee is not None or notice.manifest_id is not None))
                or (notice.state in {"fee_due", "cleared"} and (manifest is None or manifest.parcel_id != notice.parcel_id
                    or manifest.order_id != notice.order_id or manifest.resource_id != notice.resource_id
                    or manifest.quantity != notice.quantity or notice.fee is None))
                or (notice.state in {"detected", "evaded_undetected"} and (notice.manifest_id is not None or notice.fee is not None))
                or (notice.state != "presented" and notice.event_id not in {link.cause_event_id for link in transition.causal_links})
                or (notice.state == "fee_due" and transition.event_type != "cargo_manifest_declared")
                or (notice.state == "detected" and transition.event_type != "customs_fee_evasion_detected")
                or (notice.state == "evaded_undetected" and transition.event_type != "customs_fee_evaded")
                or (notice.state == "cleared" and transition.event_type != "customs_fee_paid")
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
                or report.channel != "administrative_site_report"
                or not isinstance(report.service_suspended, bool)
                or receipt.event_type != "site_observed" or receipt.fact_kind != FactKind.STATE_TRANSITION
                or not any(d.owner_kind == "site_report" and d.owner_id == report.id and d.aspect == "observation"
                           and d.after == report.observation() for d in receipt.deltas)):
            raise ValueError("site observation requires its own typed receipt")

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
