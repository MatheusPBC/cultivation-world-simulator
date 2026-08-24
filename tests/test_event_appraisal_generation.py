"""Task 2: monthly personal appraisal generation.

See docs/specs/personal-appraisal-politics.md ("Monthly generation").

The appraisal phase only ATTACHES `EventAppraisal` objects to
`event.appraisals`; `finalize_step` -> `EventStorage.add_event` remains the
only write path, so appraisals are persisted atomically with their event.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.classes.age import Age
from src.classes.alignment import Alignment
from src.classes.core.avatar import Avatar, Gender
from src.classes.emotions import EmotionType
from src.classes.event import Event
from src.classes.event_appraisal import AppraisalSource
from src.classes.root import Root
from src.systems.cultivation import Realm
from src.systems.event_appraisal_service import (
    MAX_AI_APPRAISAL_CANDIDATES,
    build_appraisal_candidates,
    generate_appraisals_for_events,
)
from src.systems.time import Month, Year, create_month_stamp
from src.utils.id_generator import get_avatar_id
from src.utils.llm.exceptions import LLMError
from src.utils.llm.test_mode_fallbacks import registered_test_mode_tasks, resolve_test_mode_task


# --- helpers ---

def make_avatar(world, name: str) -> Avatar:
    avatar = Avatar(
        world=world,
        name=name,
        id=get_avatar_id(),
        birth_month_stamp=create_month_stamp(Year(2000), Month.JANUARY),
        age=Age(20, Realm.Qi_Refinement, innate_max_lifespan=80),
        gender=Gender.MALE,
        pos_x=0,
        pos_y=0,
        root=Root.GOLD,
        personas=[],
        alignment=Alignment.RIGHTEOUS,
    )
    avatar.personas = []
    avatar.technique = None
    avatar.recalc_effects()
    world.avatar_manager.register_avatar(avatar)
    return avatar


def make_battle_event(world, winner: Avatar, loser: Avatar, *, fatal: bool = False) -> Event:
    return Event(
        world.month_stamp,
        f"{winner.name} defeated {loser.name}",
        related_avatars=[winner.id, loser.id],
        is_major=True,
        event_type="battle_kill" if fatal else "battle_result",
        render_params={
            "killer_id": str(winner.id),
            "killer_name": winner.name,
            "victim_id": str(loser.id),
            "victim_name": loser.name,
        },
    )


def make_bond_event(world, a: Avatar, b: Avatar, event_type: str) -> Event:
    return Event(
        world.month_stamp,
        f"{a.name} and {b.name}: {event_type}",
        related_avatars=[a.id, b.id],
        is_major=True,
        event_type=event_type,
        render_params={
            "avatar_a_id": str(a.id),
            "avatar_a_name": a.name,
            "avatar_b_id": str(b.id),
            "avatar_b_name": b.name,
        },
    )


def llm_item(candidate_id: str, **overrides) -> dict:
    item = {
        "candidate_id": candidate_id,
        "personal_importance": 0.7,
        "valence": -0.4,
        "persistence": 0.5,
        "primary_emotion": "emotion_angry",
        "summary": "He humiliated me before the whole sect.",
    }
    item.update(overrides)
    return item


# --- eligibility ---

class TestAppraisalEligibility:

    def test_supported_interpersonal_event_yields_one_candidate_per_direction(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        candidates = build_appraisal_candidates(base_world, [event])

        pairs = {(c.appraiser.id, c.focus.id) for c in candidates}
        assert pairs == {(a.id, b.id), (b.id, a.id)}
        assert len({c.candidate_id for c in candidates}) == 2

    def test_unsupported_event_type_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_bond_event(base_world, a, b, "relationship_major")

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_story_event_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        event.is_story = True

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_non_major_event_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        event.is_major = False

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_event_without_structured_participant_ids_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        # Prose still names both avatars; IDs must never be inferred from it.
        event.render_params = {"killer_name": a.name, "victim_name": b.name}

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_event_with_only_one_structured_participant_id_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        event.render_params = dict(event.render_params or {})
        event.render_params.pop("victim_id")

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_dead_participant_never_appraises_but_may_still_be_appraised(self, base_world):
        """A dead avatar forms no new memory, yet the survivor still remembers them.

        Requiring the *focus* to be alive would make `battle_kill` -- where the
        victim is dead by definition -- permanently incapable of producing any
        appraisal, contradicting the spec's first allowlist entry.
        """
        killer = make_avatar(base_world, "Killer")
        victim = make_avatar(base_world, "Victim")
        event = make_battle_event(base_world, killer, victim, fatal=True)
        victim.is_dead = True

        candidates = build_appraisal_candidates(base_world, [event])

        assert [(c.appraiser.id, c.focus.id) for c in candidates] == [(killer.id, victim.id)]

    def test_both_participants_dead_produces_no_candidate(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        a.is_dead = True
        b.is_dead = True

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_unnamed_participant_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        b.name = ""
        event = make_battle_event(base_world, a, b)

        assert build_appraisal_candidates(base_world, [event]) == []

    def test_unknown_participant_id_is_ignored(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)
        event.render_params = dict(event.render_params or {})
        event.render_params["victim_id"] = "not-a-registered-avatar"

        assert build_appraisal_candidates(base_world, [event]) == []

    @pytest.mark.parametrize(
        "event_type",
        [
            "bond_lovers_formed",
            "bond_lovers_rejected",
            "bond_sworn_sibling_formed",
            "bond_sworn_sibling_rejected",
            "bond_master_disciple_formed",
        ],
    )
    def test_all_initially_supported_bond_types_are_eligible(self, base_world, event_type):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_bond_event(base_world, a, b, event_type)

        assert len(build_appraisal_candidates(base_world, [event])) == 2


# --- generation, batching and fallback ---

class TestAppraisalGeneration:

    @pytest.mark.asyncio
    async def test_valid_ai_output_is_attached_with_llm_source(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        async def fake_call(task_name, template_path, infos, **kwargs):
            assert task_name == "event_appraisal"
            ids = [c["candidate_id"] for c in infos["candidates"]]
            return {"appraisals": [llm_item(cid) for cid in ids]}

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [event])

        assert len(event.appraisals) == 2
        for appraisal in event.appraisals:
            assert appraisal.source is AppraisalSource.LLM
            assert appraisal.event_id == event.id
            assert appraisal.primary_emotion is EmotionType.ANGRY
            assert appraisal.summary == "He humiliated me before the whole sect."

    @pytest.mark.asyncio
    async def test_batch_caps_ai_candidates_and_overflow_uses_rule_fallback(self, base_world):
        events = []
        for _ in range(12):  # 24 candidates, 8 over the cap
            a = make_avatar(base_world, "Alpha")
            b = make_avatar(base_world, "Beta")
            events.append(make_battle_event(base_world, a, b))

        seen_batch_sizes: list[int] = []

        async def fake_call(task_name, template_path, infos, **kwargs):
            seen_batch_sizes.append(len(infos["candidates"]))
            ids = [c["candidate_id"] for c in infos["candidates"]]
            return {"appraisals": [llm_item(cid) for cid in ids]}

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ) as mock_call:
            await generate_appraisals_for_events(base_world, events)

        assert mock_call.await_count == 1
        assert seen_batch_sizes == [MAX_AI_APPRAISAL_CANDIDATES]

        attached = [appraisal for event in events for appraisal in event.appraisals]
        assert len(attached) == 24
        by_source = [a.source for a in attached]
        assert by_source.count(AppraisalSource.LLM) == MAX_AI_APPRAISAL_CANDIDATES
        assert by_source.count(AppraisalSource.RULE) == 24 - MAX_AI_APPRAISAL_CANDIDATES

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back_for_every_candidate(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=LLMError("provider down")),
        ):
            await generate_appraisals_for_events(base_world, [event])

        assert len(event.appraisals) == 2
        assert all(a.source is AppraisalSource.RULE for a in event.appraisals)

    @pytest.mark.asyncio
    async def test_partial_response_falls_back_only_for_missing_candidates(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        async def fake_call(task_name, template_path, infos, **kwargs):
            first = infos["candidates"][0]["candidate_id"]
            return {"appraisals": [llm_item(first)]}

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [event])

        sources = sorted(a.source.value for a in event.appraisals)
        assert sources == ["llm", "rule"]

    @pytest.mark.asyncio
    async def test_duplicate_known_candidate_id_is_invalidated_entirely(self, base_world):
        """A known candidate_id echoed more than once is not trustworthy -- neither
        occurrence is used, so the candidate falls back to RULE, while an unrelated
        valid candidate in the same response is unaffected."""
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        async def fake_call(task_name, template_path, infos, **kwargs):
            first, second = [c["candidate_id"] for c in infos["candidates"]]
            return {
                "appraisals": [
                    llm_item(first, summary="First answer."),
                    llm_item(first, summary="Duplicate echo of first."),
                    llm_item(second, summary="Valid unrelated answer."),
                    llm_item("fabricated-candidate-id", summary="Invented candidate."),
                ]
            }

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [event])

        assert len(event.appraisals) == 2
        by_summary = {a.summary: a for a in event.appraisals}
        assert by_summary["Valid unrelated answer."].source is AppraisalSource.LLM
        assert "First answer." not in by_summary
        assert "Duplicate echo of first." not in by_summary
        assert "Invented candidate." not in by_summary
        rule_appraisals = [a for a in event.appraisals if a.source is AppraisalSource.RULE]
        assert len(rule_appraisals) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_summary",
        [None, 123, True, False, ["a list"], {"k": "v"}],
        ids=["none", "int", "true", "false", "list", "dict"],
    )
    async def test_non_string_summary_is_malformed_and_falls_back_to_rule(self, base_world, bad_summary):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        async def fake_call(task_name, template_path, infos, **kwargs):
            ids = [item["candidate_id"] for item in infos["candidates"]]
            return {
                "appraisals": [
                    llm_item(ids[0], summary=bad_summary),
                    llm_item(ids[1]),
                ]
            }

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [event])

        sources = sorted(a.source.value for a in event.appraisals)
        assert sources == ["llm", "rule"]

    @pytest.mark.asyncio
    async def test_unexpected_build_error_for_one_candidate_does_not_block_others(self, base_world):
        import src.systems.event_appraisal_service as svc

        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        c = make_avatar(base_world, "Gamma")
        d = make_avatar(base_world, "Delta")
        broken_event = make_battle_event(base_world, a, b)
        healthy_event = make_battle_event(base_world, c, d)

        original_build_llm = svc._build_llm_appraisal

        def flaky_build_llm(candidate, item):
            if candidate.event is broken_event:
                raise RuntimeError("boom")
            return original_build_llm(candidate, item)

        async def fake_call(task_name, template_path, infos, **kwargs):
            ids = [item["candidate_id"] for item in infos["candidates"]]
            return {"appraisals": [llm_item(cid) for cid in ids]}

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ), patch(
            "src.systems.event_appraisal_service._build_llm_appraisal",
            side_effect=flaky_build_llm,
        ):
            await generate_appraisals_for_events(base_world, [broken_event, healthy_event])

        assert broken_event.appraisals == []
        assert len(healthy_event.appraisals) == 2
        assert all(a.source is AppraisalSource.LLM for a in healthy_event.appraisals)

    @pytest.mark.asyncio
    async def test_malformed_numeric_and_invalid_emotion_fall_back_per_candidate(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        c = make_avatar(base_world, "Gamma")
        d = make_avatar(base_world, "Delta")
        first_event = make_battle_event(base_world, a, b)
        second_event = make_battle_event(base_world, c, d)

        async def fake_call(task_name, template_path, infos, **kwargs):
            ids = [item["candidate_id"] for item in infos["candidates"]]
            return {
                "appraisals": [
                    llm_item(ids[0], personal_importance="not-a-number"),
                    llm_item(ids[1], primary_emotion="emotion_transcendent"),
                    llm_item(ids[2], summary="Valid answer."),
                    llm_item(ids[3], valence=None),
                ]
            }

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [first_event, second_event])

        attached = [*first_event.appraisals, *second_event.appraisals]
        assert len(attached) == 4
        llm_appraisals = [a for a in attached if a.source is AppraisalSource.LLM]
        assert [a.summary for a in llm_appraisals] == ["Valid answer."]

    @pytest.mark.asyncio
    async def test_numeric_values_are_clamped_and_summary_is_capped(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        async def fake_call(task_name, template_path, infos, **kwargs):
            ids = [item["candidate_id"] for item in infos["candidates"]]
            return {
                "appraisals": [
                    llm_item(
                        ids[0],
                        personal_importance=7.5,
                        valence=-9.0,
                        persistence=-2.0,
                        summary="x" * 400,
                    ),
                    llm_item(ids[1], personal_importance=-3.0, valence=4.0, persistence=9.0),
                ]
            }

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=fake_call),
        ):
            await generate_appraisals_for_events(base_world, [event])

        clamped = sorted(event.appraisals, key=lambda a: a.personal_importance)
        assert clamped[0].personal_importance == pytest.approx(0.0)
        assert clamped[0].valence == pytest.approx(1.0)
        assert clamped[0].persistence == pytest.approx(1.0)
        assert clamped[1].personal_importance == pytest.approx(1.0)
        assert clamped[1].valence == pytest.approx(-1.0)
        assert clamped[1].persistence == pytest.approx(0.0)
        assert len(clamped[1].summary) == 240

    @pytest.mark.asyncio
    async def test_rule_fallback_distinguishes_direction(self, base_world):
        winner = make_avatar(base_world, "Winner")
        loser = make_avatar(base_world, "Loser")
        event = make_battle_event(base_world, winner, loser)

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=LLMError("down")),
        ):
            await generate_appraisals_for_events(base_world, [event])

        by_appraiser = {a.appraiser_avatar_id: a for a in event.appraisals}
        loser_view = by_appraiser[str(loser.id)]
        winner_view = by_appraiser[str(winner.id)]
        assert loser_view.valence < 0
        assert loser_view.valence < winner_view.valence
        assert loser_view.personal_importance > 0

    @pytest.mark.asyncio
    async def test_generation_never_raises_when_everything_fails(self, base_world):
        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=RuntimeError("catastrophic")),
        ):
            await generate_appraisals_for_events(base_world, [event])

        assert len(event.appraisals) == 2


# --- test mode ---

class TestAppraisalTestMode:

    def test_event_appraisal_task_is_registered_for_test_mode(self):
        assert "event_appraisal" in registered_test_mode_tasks()
        assert resolve_test_mode_task("event_appraisal", {}) == {"appraisals": []}

    @pytest.mark.asyncio
    async def test_test_mode_never_contacts_a_provider_and_uses_rule_fallback(self, base_world):
        from src.utils.llm.runtime_mode import llm_test_mode_scope

        a = make_avatar(base_world, "Alpha")
        b = make_avatar(base_world, "Beta")
        event = make_battle_event(base_world, a, b)

        with patch("src.utils.llm.client.call_llm", new=AsyncMock()) as raw_call:
            with llm_test_mode_scope(True):
                await generate_appraisals_for_events(base_world, [event])

        raw_call.assert_not_awaited()
        assert len(event.appraisals) == 2
        assert all(a.source is AppraisalSource.RULE for a in event.appraisals)


# --- localization ---

class TestAppraisalRuleFallbackLocalization:

    @pytest.fixture(autouse=True)
    def restore_language(self):
        from src.classes.language import language_manager
        from src.i18n import reload_translations

        original_lang = str(language_manager)
        yield
        language_manager.set_language(original_lang)
        reload_translations()

    @pytest.mark.asyncio
    async def test_rule_fallback_summary_is_localized_to_pt_br_without_leakage(self, base_world):
        from src.classes.language import language_manager

        language_manager.set_language("pt-BR")

        winner = make_avatar(base_world, "Winner")
        loser = make_avatar(base_world, "Loser")
        event = make_battle_event(base_world, winner, loser)

        with patch(
            "src.systems.event_appraisal_service.call_llm_with_task_name",
            new=AsyncMock(side_effect=LLMError("down")),
        ):
            await generate_appraisals_for_events(base_world, [event])

        by_appraiser = {a.appraiser_avatar_id: a for a in event.appraisals}
        loser_view = by_appraiser[str(loser.id)]

        assert loser_view.summary == f"{winner.name} me derrotou naquela luta."
        # No English source text, no code identifiers, no untranslated leakage.
        assert "defeated me in that fight" not in loser_view.summary
        assert "emotion_" not in loser_view.summary
        assert "{focus_name}" not in loser_view.summary


# --- phase wiring ---

class TestAppraisalPhaseWiring:

    def test_appraisal_phase_runs_after_annual_maintenance_and_before_finalizer(self):
        from src.sim.simulator_engine.phase_registry import get_simulation_phases

        indexes = {phase.name: phase.index for phase in get_simulation_phases()}

        assert indexes["annual_maintenance"] == 29
        assert indexes["generate_event_appraisals"] == 30
        assert indexes["finalize_step"] == 31
        assert get_simulation_phases()[-1].name == "finalize_step"

    @pytest.mark.asyncio
    async def test_phase_only_attaches_and_finalizer_persists_event_with_appraisals(self, base_world, tmp_path):
        from src.sim.managers.event_manager import EventManager
        from src.sim.simulator_engine.context import SimulationStepContext
        from src.sim.simulator_engine.finalizer import finalize_step
        from src.sim.simulator_engine.phase_registry import generate_event_appraisals

        base_world.event_manager = EventManager.create_with_db(tmp_path / "events.db")
        try:
            a = make_avatar(base_world, "Alpha")
            b = make_avatar(base_world, "Beta")
            event = make_battle_event(base_world, a, b)

            ctx = SimulationStepContext.create(base_world)
            ctx.add_events([event])
            month_stamp = int(base_world.month_stamp)

            with patch(
                "src.systems.event_appraisal_service.call_llm_with_task_name",
                new=AsyncMock(side_effect=LLMError("down")),
            ):
                await generate_event_appraisals(None, ctx)

            # The phase attaches only; nothing is written yet.
            assert len(event.appraisals) == 2
            assert base_world.event_manager.count() == 0

            finalize_step(ctx)

            assert base_world.event_manager.count() == 1
            stored = base_world.event_manager.get_event_appraisals(
                appraiser_avatar_id=str(a.id),
                current_month_stamp=month_stamp,
            )
            assert [item.event_id for item in stored] == [event.id]
        finally:
            base_world.event_manager.close()
