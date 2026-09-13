"""Single owner of actor-specific observations; canonical truth stays elsewhere."""

from dataclasses import dataclass, field
from .models import KnowledgeReport, DiplomaticNotice
from .serialization import RegistrySerialization, validate_actor
from src.classes.research.models import TechnicalKnowledge


@dataclass
class KnowledgeState(RegistrySerialization):
    reports: dict[str, KnowledgeReport] = field(default_factory=dict)
    technologies: dict[str, TechnicalKnowledge] = field(default_factory=dict)
    notices: dict[str, DiplomaticNotice] = field(default_factory=dict)
    registries = {"reports": KnowledgeReport, "technologies": TechnicalKnowledge, "notices": DiplomaticNotice}

    def knows(self, actor_ref, technology_id):
        return any(k.owner_ref == actor_ref and k.technology_id == technology_id for k in self.technologies.values())

    def for_actor(self, actor_ref):
        return tuple(r for _, r in sorted(self.reports.items()) if r.recipient_ref == actor_ref)

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
