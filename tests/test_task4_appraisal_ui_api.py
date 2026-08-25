"""Task 4: read-only API surface for personal appraisals.

Covers docs/specs/personal-appraisal-politics.md ("Query and UI"):
- AvatarDetail exposes the top 10 personal_appraisals by current effective weight.
- The causal "why" query resolves decision_appraisals from the appraisal_ids
  actually cited by the decision's chosen_chain.

No mutation endpoint is added or exercised here: both paths are pure reads
over data written by Task 1-3 (EventStorage / SectDecider).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.causal_link import CausalLink, CausalRelation
from src.classes.core.avatar import Avatar, Gender
from src.classes.core.world import World
from src.classes.emotions import EmotionType
from src.classes.environment.map import Map
from src.classes.environment.tile import TileType
from src.classes.event import Event, FactKind
from src.classes.event_appraisal import AppraisalSource, EventAppraisal
from src.classes.root import Root
from src.server.assemblers.avatar_detail import build_avatar_detail
from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.serialization import serialize_events_for_client
from src.server.services.game_queries import get_event_causal_detail
from src.systems.cultivation import Realm
from src.systems.time import Month, Year, create_month_stamp
from src.utils.id_generator import get_avatar_id


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_events.db"


@pytest.fixture
def world(temp_db_path):
    game_map = Map(width=10, height=10)
    for x in range(10):
        for y in range(10):
            game_map.create_tile(x, y, TileType.PLAIN)
    month_stamp = create_month_stamp(Year(100), Month.JANUARY)
    w = World.create_with_db(map=game_map, month_stamp=month_stamp, events_db_path=temp_db_path)
    yield w
    w.event_manager.close()


def _make_avatar(world: World, name: str) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=get_avatar_id(),
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.NEUTRAL,
    )
    avatar.personas = []
    avatar.weapon = MagicMock()
    avatar.weapon.get_detailed_info.return_value = "test weapon"
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def _write_appraisal(
    world: World,
    *,
    appraiser: Avatar,
    focus: Avatar,
    personal_importance: float,
    valence: float,
    persistence: float,
    summary: str,
) -> tuple[Event, EventAppraisal]:
    event = Event(
        world.month_stamp,
        f"{appraiser.name} and {focus.name} clashed",
        related_avatars=[appraiser.id, focus.id],
        is_major=True,
        event_type="battle_result",
    )
    world.event_manager.add_event(event)
    appraisal = EventAppraisal(
        event_id=event.id,
        appraiser_avatar_id=str(appraiser.id),
        focus_avatar_id=str(focus.id),
        personal_importance=personal_importance,
        valence=valence,
        persistence=persistence,
        primary_emotion=EmotionType.ANGRY,
        summary=summary,
        source=AppraisalSource.LLM,
    )
    assert world.event_manager._storage.add_event_appraisal(appraisal) is True
    return event, appraisal


def _resolve_avatar_pic_id(_avatar) -> int:
    return 0


class TestAvatarDetailPersonalAppraisals:
    def test_top_ten_sorted_by_effective_weight_with_display_fields(self, world):
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")

        _, weak = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.2, valence=-0.3, persistence=0.1, summary="A minor spat.",
        )
        strong_event, strong = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.8, persistence=0.9, summary="He betrayed me.",
        )

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        appraisals = detail["personal_appraisals"]
        assert [a["appraisal_id"] for a in appraisals] == [strong.id, weak.id]
        top = appraisals[0]
        assert top["focus_avatar_id"] == str(beta.id)
        assert top["focus_avatar_name"] == "Beta"
        assert top["summary"] == "He betrayed me."
        assert top["source_event_id"] == strong_event.id
        assert top["source_event_date"]
        assert top["valence"] == pytest.approx(-0.8)
        assert top["emotion"]["name"]
        assert top["emotion"]["emoji"]
        assert top["effective_weight"] > appraisals[1]["effective_weight"]

    def test_caps_at_ten_entries(self, world):
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        for i in range(12):
            _write_appraisal(
                world, appraiser=alpha, focus=beta,
                personal_importance=0.9, valence=-0.5, persistence=0.9, summary=f"Memory {i}.",
            )

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        assert len(detail["personal_appraisals"]) == 10

    def test_empty_when_avatar_has_no_appraisals(self, world):
        alpha = _make_avatar(world, "Alpha")

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        assert detail["personal_appraisals"] == []

    def test_weak_appraisals_below_the_floor_are_excluded(self, world):
        """`Memórias marcantes` has a defined floor: the spec only assigns a
        qualitative bucket down to 0.15, so anything weaker must not render."""
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        _, faint = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.1, valence=-0.2, persistence=1.0, summary="Barely registered.",
        )
        _, kept = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.2, valence=-0.2, persistence=1.0, summary="Just above the floor.",
        )

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        ids = [a["appraisal_id"] for a in detail["personal_appraisals"]]
        assert ids == [kept.id]
        assert faint.id not in ids

    def test_focus_name_falls_back_to_source_event_snapshot_when_avatar_is_gone(self, world):
        """A persistence=1.0 memory never decays, so the focus avatar can be
        garbage-collected long before the memory fades. The row must still
        name them, using the source event's subject snapshot."""
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        source_event, _ = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.9, persistence=1.0, summary="I never forgot.",
        )
        assert source_event.subject_snapshots.get(str(beta.id)) == "Beta"

        world.avatar_manager.remove_avatar(str(beta.id))
        assert world.avatar_manager.get_avatar(str(beta.id)) is None

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        assert [a["focus_avatar_name"] for a in detail["personal_appraisals"]] == ["Beta"]

    def test_only_own_appraisals_as_appraiser_are_shown(self, world):
        """An appraisal where this avatar is the focus, not the appraiser, must
        not appear -- these are the avatar's own memories, not opinions about them."""
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        _write_appraisal(
            world, appraiser=beta, focus=alpha,
            personal_importance=0.9, valence=0.9, persistence=0.9, summary="Beta's own memory of Alpha.",
        )

        detail = build_avatar_detail(alpha, resolve_avatar_pic_id=_resolve_avatar_pic_id)

        assert detail["personal_appraisals"] == []


class TestWhyViewDecisionAppraisals:
    def test_resolves_only_cited_appraisals_in_citation_order(self, world):
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        source_event, cited = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.8, persistence=0.9, summary="He humiliated me.",
        )
        # A second, uncited appraisal must never leak into the Why view.
        _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.2, valence=0.1, persistence=0.1, summary="An uncited memory.",
        )

        decision_payload = {
            "id": "decision-1",
            "subject_kind": "sect",
            "subject_id": "1",
            "source": "llm",
            "considered_count": 1,
            "chosen_chain": [
                {"action_name": "declare_war", "params": {"other_sect_id": 2}, "appraisal_ids": [cited.id]},
            ],
            "thinking": "Avenge the humiliation.",
            "short_term_objective": "",
            "rejected": [],
        }
        decision_event = Event(
            world.month_stamp, "decision round",
            is_major=False, fact_kind=FactKind.DECISION,
            causal_payload={"deltas": [], "decision": decision_payload},
        )
        world.event_manager.add_event(decision_event)

        war_event = Event(world.month_stamp, "war declared", is_major=True, fact_kind=FactKind.STATE_TRANSITION)
        war_event.causal_links.append(
            CausalLink(event_id=war_event.id, cause_event_id=decision_event.id, relation=CausalRelation.MOTIVATED_BY)
        )
        world.event_manager.add_event(war_event)

        runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
        runtime.set_world_and_sim(world, None)

        result = get_event_causal_detail(
            runtime,
            serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=world),
            event_id=war_event.id,
        )

        decision_appraisals = result["decision_appraisals"]
        assert [a["appraisal_id"] for a in decision_appraisals] == [cited.id]
        entry = decision_appraisals[0]
        assert entry["pruned"] is False
        assert entry["focus_avatar_id"] == str(beta.id)
        assert entry["focus_avatar_name"] == "Beta"
        assert entry["summary"] == "He humiliated me."
        assert entry["source_event_id"] == source_event.id
        assert entry["source_event_date"]
        assert entry["valence"] == pytest.approx(-0.8)
        assert entry["primary_emotion"] == EmotionType.ANGRY.value
        assert entry["emotion"]["name"]
        assert entry["emotion"]["emoji"]

    def test_missing_appraisal_id_yields_a_pruned_placeholder(self, world):
        """A citation whose appraisal row no longer exists must stay visible as
        a pruned placeholder -- the audit trail must never silently shrink."""
        war_event = self._build_decision_and_effect(world, cited_ids=["does-not-exist"])

        runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
        runtime.set_world_and_sim(world, None)

        result = get_event_causal_detail(
            runtime,
            serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=world),
            event_id=war_event.id,
        )

        assert len(result["decision_appraisals"]) == 1
        entry = result["decision_appraisals"][0]
        assert entry["appraisal_id"] == "does-not-exist"
        assert entry["pruned"] is True
        assert entry["summary"] is None
        assert entry["emotion"] is None
        assert entry["valence"] is None
        assert entry["source_event_id"] == ""

    def test_cascade_deleted_appraisal_becomes_a_pruned_placeholder_in_citation_order(self, world):
        """Deleting the source event cascades the appraisal row away
        (ON DELETE CASCADE). The surviving citation keeps its slot and order."""
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        doomed_event, doomed = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.8, persistence=0.9, summary="Will be pruned.",
        )
        _, survivor = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.7, persistence=0.9, summary="Still here.",
        )
        war_event = self._build_decision_and_effect(world, cited_ids=[doomed.id, survivor.id])

        storage = world.event_manager._storage
        with storage._transaction() as conn:
            conn.execute("DELETE FROM events WHERE id = ?", (doomed_event.id,))
        assert storage.get_event_appraisals_by_ids([doomed.id]) == []

        runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
        runtime.set_world_and_sim(world, None)

        result = get_event_causal_detail(
            runtime,
            serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=world),
            event_id=war_event.id,
        )

        entries = result["decision_appraisals"]
        # Citation order preserved, pruned entry still occupying its slot.
        assert [e["appraisal_id"] for e in entries] == [doomed.id, survivor.id]
        assert entries[0]["pruned"] is True
        assert entries[1]["pruned"] is False
        assert entries[1]["summary"] == "Still here."

    def test_cited_focus_name_falls_back_to_source_event_snapshot(self, world):
        alpha = _make_avatar(world, "Alpha")
        beta = _make_avatar(world, "Beta")
        _, cited = _write_appraisal(
            world, appraiser=alpha, focus=beta,
            personal_importance=0.9, valence=-0.8, persistence=1.0, summary="I never forgot.",
        )
        war_event = self._build_decision_and_effect(world, cited_ids=[cited.id])

        world.avatar_manager.remove_avatar(str(beta.id))
        assert world.avatar_manager.get_avatar(str(beta.id)) is None

        runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
        runtime.set_world_and_sim(world, None)

        result = get_event_causal_detail(
            runtime,
            serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=world),
            event_id=war_event.id,
        )

        assert [e["focus_avatar_name"] for e in result["decision_appraisals"]] == ["Beta"]

    @staticmethod
    def _build_decision_and_effect(world: World, *, cited_ids: list[str]) -> Event:
        """Persist a sect decision citing `cited_ids` plus the war event it caused."""
        decision_payload = {
            "id": "decision-1",
            "subject_kind": "sect",
            "subject_id": "1",
            "source": "llm",
            "considered_count": 1,
            "chosen_chain": [
                {"action_name": "declare_war", "params": {"other_sect_id": 2}, "appraisal_ids": list(cited_ids)},
            ],
            "thinking": "",
            "short_term_objective": "",
            "rejected": [],
        }
        decision_event = Event(
            world.month_stamp, "decision round",
            is_major=False, fact_kind=FactKind.DECISION,
            causal_payload={"deltas": [], "decision": decision_payload},
        )
        world.event_manager.add_event(decision_event)

        war_event = Event(world.month_stamp, "war declared", is_major=True, fact_kind=FactKind.STATE_TRANSITION)
        war_event.causal_links.append(
            CausalLink(event_id=war_event.id, cause_event_id=decision_event.id, relation=CausalRelation.MOTIVATED_BY)
        )
        world.event_manager.add_event(war_event)
        return war_event

    def test_no_decision_means_no_decision_appraisals(self, world):
        event = Event(world.month_stamp, "plain event", is_major=False)
        world.event_manager.add_event(event)

        runtime = GameSessionRuntime(dict(DEFAULT_GAME_STATE))
        runtime.set_world_and_sim(world, None)

        result = get_event_causal_detail(
            runtime,
            serialize_events_for_client=lambda evs, **kwargs: serialize_events_for_client(evs, world=world),
            event_id=event.id,
        )

        assert result["decision"] is None
        assert result["decision_appraisals"] == []
