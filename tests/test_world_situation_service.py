from types import SimpleNamespace

from src.classes.event import Event, FactKind
from src.classes.environment.regional_flood import RegionalFloodOccurrence
from src.classes.mechanical_language import ConditionInstance, DomainReactionReceipt
from src.systems.time import MonthStamp
from src.server.services.game_queries import get_world_journal
from src.systems.world_situation_service import build_world_situations


class _EventManager:
    def __init__(self, events):
        self.events = {event.id: event for event in events}
        self.requested_windows = []

    def get_event_by_id(self, event_id):
        return self.events.get(event_id)

    def get_events_between_months(self, start, end):
        self.requested_windows.append((start, end))
        return sorted(
            [event for event in self.events.values() if start <= int(event.month_stamp) <= end],
            key=lambda event: (int(event.month_stamp), event.created_at, event.id),
        )


class _AvatarManager:
    def __init__(self, avatars=None):
        self.avatars = avatars or {}

    def get_avatar(self, avatar_id):
        return self.avatars.get(str(avatar_id))


def _world(*, events, regions, floods=(), conditions=(), receipts=()):
    return SimpleNamespace(
        month_stamp=MonthStamp(30),
        event_manager=_EventManager(events),
        avatar_manager=_AvatarManager(),
        existed_sects=[],
        map=SimpleNamespace(
            regions={region.id: region for region in regions},
            infrastructure_sites={},
        ),
        regional_flood_state=SimpleNamespace(
            active_by_region={item.region_id: item for item in floods},
        ),
        mechanical_language=SimpleNamespace(
            condition_instances={item.id: item for item in conditions},
            reaction_receipts={item.id: item for item in receipts},
        ),
        dynasty=None,
        dao_petitions=[],
    )


def _region(region_id, name):
    return SimpleNamespace(
        id=region_id,
        name=name,
        city_state=SimpleNamespace(capacity_projects=()),
    )


def test_active_floods_form_one_persistent_world_situation():
    first = Event(MonthStamp(20), "A primeira enchente começou.", id="flood-1", created_at=1)
    second = Event(MonthStamp(25), "Outra região alagou.", id="flood-2", created_at=2)
    floods = (
        RegionalFloodOccurrence("1", 20, 0.72, ("climate-1",), first.id),
        RegionalFloodOccurrence("2", 25, 0.91, ("climate-2",), second.id),
    )
    world = _world(
        events=[first, second],
        regions=[_region(1, "Vale"), _region(2, "Pântano")],
        floods=floods,
    )

    situations = build_world_situations(world)

    assert [item["id"] for item in situations] == ["hazard:regional_flood"]
    flood = situations[0]
    assert flood["severity"] == "critical"
    assert flood["age_months"] == 11
    assert flood["primary_event_id"] == second.id
    assert flood["title_params"] == {"count": 2}
    assert [subject["name"] for subject in flood["subjects"]] == ["Vale", "Pântano"]


def test_condition_surfaces_the_latest_actor_response_without_persisting_a_new_record():
    cause = Event(MonthStamp(21), "A cidade ficou sobrecarregada.", id="cause", created_at=1)
    decision = Event(
        MonthStamp(28),
        "A cidade decidiu manter a situação.",
        id="decision",
        created_at=2,
        fact_kind=FactKind.DECISION,
        causal_payload={
            "deltas": [],
            "decision": {
                "subject_kind": "city",
                "subject_id": "1",
                "thinking": "Os recursos ainda são insuficientes.",
                "rejected": [
                    {"action_name": "expand", "reason": "Faltam pedras espirituais."}
                ],
            },
            "interpretation": {"decision": "maintain", "reason": "É prudente esperar."},
        },
    )
    condition = ConditionInstance(
        id="condition-1",
        definition_id="urban_service_strain",
        target_kind="region",
        target_id="1",
        label="Pressão urbana",
        intensity=0.8,
        started_month=21,
        cause_event_id=cause.id,
    )
    receipt = DomainReactionReceipt.create(
        condition.id,
        "city",
        "revision-1",
        decision="maintain",
        affordance_id=None,
        decision_event_ids=(decision.id,),
    )
    world = _world(
        events=[cause, decision],
        regions=[_region(1, "Capital")],
        conditions=[condition],
        receipts=[receipt],
    )
    receipt_count = len(world.mechanical_language.reaction_receipts)

    situations = build_world_situations(world)

    assert len(world.mechanical_language.reaction_receipts) == receipt_count
    projected = situations[0]
    assert projected["id"] == "condition:region:urban_service_strain"
    assert projected["latest_response"] == {
        "event_id": decision.id,
        "decision": "maintain",
        "reason": "É prudente esperar.",
        "actor": {"kind": "region", "id": "1", "name": "Capital"},
        "rejected": [
            {"action_name": "expand", "reason": "Faltam pedras espirituais."}
        ],
    }


def test_world_journal_reads_only_the_indexed_period_and_hides_decision_audits():
    occurrence = Event(
        MonthStamp(29), "A ponte cedeu.", id="occurrence", created_at=1, is_major=True
    )
    decision = Event(
        MonthStamp(30), "Uma decisão interna.", id="decision", created_at=2,
        fact_kind=FactKind.DECISION,
    )
    world = _world(events=[occurrence, decision], regions=[])

    def serialize(events, *, world=None):
        return [{"id": event.id, "content": event.content} for event in events]

    journal = get_world_journal(
        {"world": world},
        serialize_events_for_client=serialize,
        period_months=3,
    )

    assert world.event_manager.requested_windows == [(28, 30)]
    assert journal["activity"]["total_events"] == 1
    assert journal["highlights"] == [{"id": "occurrence", "content": "A ponte cedeu."}]
    assert journal["situations"] == []
