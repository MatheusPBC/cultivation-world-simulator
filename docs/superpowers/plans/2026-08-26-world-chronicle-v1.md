# World Chronicle v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish immutable AI-narrated world chapters with validated inline sources and a clickable causal dossier.

**Architecture:** Persist structured chapters in a dedicated append-only table inside the event SQLite database. Generate one bounded chapter in an async pre-finalizer phase, then expose paginated chapter and dossier queries to a segmented Vue reader inside World Journal.

**Tech Stack:** Python 3.11, dataclasses, SQLite, FastAPI, Vue 3, Pinia, TypeScript, Vitest.

**Spec:** `docs/specs/world-chronicle-v1.md`

## Global Constraints

- Events and domain state remain authoritative; the LLM only narrates validated event IDs.
- Chapters are append-only and remain present when source events are pruned.
- Trigger once on a non-story major event or after three months; major wins when both apply.
- Provider/validation failure never advances the publication window and never fails the simulation.
- `test_mode` must never call a real LLM provider.
- Route `chronicle_chapter` as `fast`; the OAuth/Codex CLI profile supplies `fast_model_name=gpt-5.6-luna`. Do not hardcode credentials or call the CLI directly from Chronicle code.
- No mutation endpoint, no `v-html`, no text heuristics for references, and no foreign key from chapters to events.
- Preserve the existing uncommitted population edits in `src/sim/simulator_engine/phases/world.py` and `tests/test_city_population.py`; never stage them in Chronicle commits.
- New frontend translation keys are `zh-CN` only; generation templates are `zh-CN` and `pt-BR`.

---

### Task 1: Chronicle domain, storage, generation, and simulation phase

**Files:**
- Create: `src/classes/chronicle.py`
- Create: `src/systems/chronicle_service.py`
- Create: `tests/test_chronicle.py`
- Create: `tests/test_chronicle_generation.py`
- Create: `static/locales/zh-CN/templates/chronicle_chapter.txt`
- Create: `static/locales/pt-BR/templates/chronicle_chapter.txt`
- Modify: `src/classes/event_storage.py`
- Modify: `src/sim/managers/event_manager.py`
- Modify: `src/sim/simulator_engine/context.py`
- Modify: `src/sim/simulator_engine/phase_registry.py`
- Modify: `src/sim/simulator_engine/finalizer.py`
- Modify: `src/utils/llm/test_mode_fallbacks.py`
- Modify: `static/config.yml`
- Test: `tests/test_event_storage.py`
- Test: `tests/test_llm_test_mode.py`
- Test: `tests/test_simulator.py`

**Interfaces:**
- Produces the dataclasses and invariants exactly defined in `docs/specs/world-chronicle-v1.md`.
- Produces `EventStorage.append_chronicle_chapter(chapter) -> bool`, `get_latest_chronicle_chapter() -> ChronicleChapter | None`, `get_chronicle_chapters_page(cursor: str | None, limit: int) -> tuple[list[ChronicleChapter], str | None, bool]`, and `get_events_between_months(start: int, end: int) -> list[Event]`, delegated by `EventManager`.
- Produces `ChronicleService.maybe_generate_chapter(world, current_events) -> ChronicleChapter | None`.
- Produces `SimulationStepContext.pending_chronicle_chapter: ChronicleChapter | None`.

- [ ] **Step 1: Write domain/storage tests first**

Cover JSON round-trip, invalid empty chapter, append-only duplicate end month, latest chapter, descending cursor pagination, persistence after reopening SQLite, and survival after source cleanup. Use fixed IDs/timestamps and literal expectations.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `env CWS_DATA_DIR=/tmp/cws-chronicle-tests UV_CACHE_DIR=/tmp/cws-uv-cache uv run pytest -q tests/test_chronicle.py tests/test_event_storage.py`

Expected: failure because Chronicle types/table/methods do not exist.

- [ ] **Step 3: Implement the immutable domain and SQLite methods**

Use one `payload_json` column for the validated structured chapter. Use plain `INSERT`, catch only duplicate end-month integrity, and never update or delete a chapter.

- [ ] **Step 4: Write generation/trigger/test-mode tests first**

Cover months one/two/three, immediate major, story exclusion, major precedence, one chapter per month, existing-world three-month bootstrap, deterministic candidate ordering, unknown/duplicate source rejection, invalid entity target rejection, provider failure retry, and `llm_test_mode_scope(True)` with no provider call.

Also assert `get_task_mode("chronicle_chapter") == LLMMode.FAST` under default task routing and keep the existing Codex CLI provider contract (`--model <fast_model_name>`) unchanged.

- [ ] **Step 5: Run generation tests and confirm RED**

Run: `env CWS_DATA_DIR=/tmp/cws-chronicle-tests UV_CACHE_DIR=/tmp/cws-uv-cache uv run pytest -q tests/test_chronicle_generation.py tests/test_llm_test_mode.py tests/test_simulator.py`

- [ ] **Step 6: Implement generation and the async pre-finalizer phase**

Call task name `chronicle_chapter`. The fallback returns a title and paragraphs whose event IDs come only from `infos["events"]`. Catch expected LLM/parse/draft-validation errors, leave pending facts untouched, and append the accepted chapter only after final factual events are persisted.

- [ ] **Step 7: Run focused regression and commit**

Run the Task 1 tests plus `tests/test_save_load_events.py`, `tests/test_city_population.py`, and `git diff --check`. Commit only Task 1 files with `feat: generate persistent world chronicles`.

### Task 2: Paginated Chronicle and causal dossier query API

**Files:**
- Create: `tests/test_api_chronicle.py`
- Modify: `src/server/services/game_queries.py`
- Modify: `src/server/services/game_query_service.py`
- Modify: `src/server/api/public_v1/query.py`
- Modify: `src/server/main.py`
- Test: `tests/test_api_events.py`
- Test: `tests/test_event_causal_query_api.py`

**Interfaces:**
- Consumes Task 1 storage methods and Chronicle dataclasses.
- Produces `GET /api/v1/query/world/chronicle?cursor=&limit=` and `GET /api/v1/query/world/chronicle/{chapter_id}/anchors/{anchor_id}/dossier?depth=&limit=`.
- Produces list `{chapters, next_cursor, has_more}` and dossier `{chapter_id, anchor, focal_event, sequence, pruned_source_ids, truncated}`.

- [ ] **Step 1: Write failing API and query tests**

Cover newest-first cursor pagination, limit clamp 1–50, empty world, missing chapter/anchor 404, entity-anchor dossier rejection, fact and inference dossier, chronological dedupe, causal cycles, depth/limit truncation, and pruned explicit sources.

- [ ] **Step 2: Run tests and confirm RED**

Run: `env CWS_DATA_DIR=/tmp/cws-chronicle-tests UV_CACHE_DIR=/tmp/cws-uv-cache uv run pytest -q tests/test_api_chronicle.py tests/test_event_causal_query_api.py`

- [ ] **Step 3: Implement read-only builders, service wiring, and routes**

The dossier performs a bounded backwards traversal from all anchor source IDs, preserves missing IDs as `pruned_source_ids`, sorts surviving events by `(month_stamp, created_at, id)`, and leaves the existing event Why endpoint unchanged.

- [ ] **Step 4: Run focused regression and commit**

Run Task 2 tests plus `tests/test_api_events.py`, `tests/test_public_api_v1.py`, and `git diff --check`. Commit only Task 2 files with `feat: expose chronicle causal dossiers`.

### Task 3: Chronicle reader, structured links, and dossier drawer

**Files:**
- Create: `web/src/components/game/panels/world-journal/ChronicleView.vue`
- Create: `web/src/components/game/panels/world-journal/ChronicleDossierDrawer.vue`
- Create: `web/src/__tests__/components/game/panels/world-journal/ChronicleView.test.ts`
- Create: `web/src/__tests__/components/game/panels/world-journal/ChronicleDossierDrawer.test.ts`
- Create: `web/src/__tests__/stores/worldJournal.test.ts`
- Modify: `web/src/types/api.ts`
- Modify: `web/src/api/modules/event.ts`
- Modify: `web/src/stores/worldJournal.ts`
- Modify: `web/src/components/game/panels/WorldJournalPanel.vue`
- Modify: `web/src/locales/zh-CN/game.json`
- Test: `web/src/__tests__/components/game/panels/WorldJournalPanel.test.ts`
- Test: `web/src/__tests__/api/publicApiModules.test.ts`

**Interfaces:**
- Consumes the exact Task 2 DTOs.
- Adds `chronicle` to `WorldJournalTab` and store methods `refreshChronicle`, `loadMoreChronicle`, `openChronicleDossier`, and `closeChronicleDossier` with request-id race guards.
- Entity references use `uiStore.select`; event references open the Chronicle dossier; dossier sequence events open existing `openCausalDetail`.

- [ ] **Step 1: Define DTOs and write failing API/store/component tests**

Assert exact URLs, pagination append without duplicates, stale-response rejection, safe text rendering without `v-html`, fact/inference badges, source counts, entity selection, event dossier opening, pruned/truncated states, and Why delegation.

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd web && npm run test -- src/__tests__/api/publicApiModules.test.ts src/__tests__/stores/worldJournal.test.ts src/__tests__/components/game/panels/world-journal/ChronicleView.test.ts src/__tests__/components/game/panels/world-journal/ChronicleDossierDrawer.test.ts src/__tests__/components/game/panels/WorldJournalPanel.test.ts`

- [ ] **Step 3: Implement the typed reader and drawer**

Render segment text through Vue interpolation. Keep Chronicle/dossier state in the Journal store, keep the existing Why state independent, and use five responsive tab columns without removing existing views.

- [ ] **Step 4: Run frontend validation and commit**

Run the focused tests, `npm run type-check`, `npm run build`, and `git diff --check`. Commit only Task 3 files with `feat: add world chronicle reader`.

### Task 4: Integration verification and documentation alignment

**Files:**
- Modify: `docs/specs/world-chronicle-v1.md` only if implementation evidence requires correction.
- Modify: `docs/specs/causal-world-kernel.md` to link the Chronicle spec without claiming the LLM owns facts.
- Test: backend and frontend integration surfaces from Tasks 1–3.

- [ ] **Step 1: Add or complete one smoke test if cross-layer behavior is not already covered**

The smoke must prove factual event → chapter → list query → dossier → Why ID and prove real provider was not called in test mode.

- [ ] **Step 2: Run final backend and frontend suites**

Backend: Chronicle tests, event storage/causal/API/save-load/simulator/population regressions. Frontend: Chronicle/WorldJournal/API/store tests, type-check, and production build.

- [ ] **Step 3: Update causal-kernel documentation and commit**

Document the Chronicle as an append-only narrative projection over the causal event store. Commit with `docs: document world chronicle projection`.
