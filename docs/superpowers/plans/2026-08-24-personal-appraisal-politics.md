# Personal Appraisal and Sect Politics Implementation Plan

**Spec:** `docs/specs/personal-appraisal-politics.md`

## Constraints

- Extend existing domain owners; do not create a parallel simulation path.
- Build and verify one vertical layer at a time.
- Write failing focused tests before each behavioral change.
- Test mode must never contact an LLM provider.
- Preserve saves and production data. This plan does not authorize deployment.

## Task 1: Domain and persistence

- Add the `EventAppraisal` domain model, source enum, validation, and effective-weight calculation.
- Extend `Event` runtime loading consistently with observations and decisions.
- Add `event_appraisals` persistence, indexes, cascade, and focused query methods to `EventStorage`.
- Add round-trip, uniqueness, cascade, old-database, coexistence, and decay tests.

## Task 2: Appraisal generation

- Normalize structured participant IDs in eligible event producers.
- Add candidate eligibility and deterministic rule fallback.
- Add one monthly batched `event_appraisal` LLM task, capped at 16 candidates.
- Add locale templates and test-mode fallback registration.
- Add the pre-finalizer async phase and focused tests for eligibility, cap, invalid output, provider failure, and test mode.

## Task 3: Sect politics and audit trail

- Add current-patriarch appraisal context to diplomacy targets.
- Replace legacy war/peace arrays with validated `diplomacy_actions` and optional `appraisal_ids`.
- Reject fabricated or mismatched evidence per action.
- Record every sect decision round as an `AgentDecision` event.
- Link cited source events to decisions and decisions to resulting diplomacy transitions.
- Record semantic sect-diplomacy `StateDelta` values.
- Add strategic-ignore, fabricated-evidence, and both integration-path tests.

## Task 4: API and UI

- Extend backend DTOs and avatar/event detail query services.
- Extend frontend types and mappers before components.
- Add `Memórias marcantes` to the existing avatar detail.
- Resolve cited appraisals in the existing Why overlay.
- Add component/store tests and verify mobile/desktop overflow behavior.

## Task 5: Verification and documentation

- Run focused suites after each task.
- Run the complete backend suite, frontend tests, frontend type-check, and `git diff --check`.
- Run a clean new-world smoke test without touching production saves.
- Update relevant README/customization documentation.
- Perform a final architecture and code-quality review before requesting publication or deployment authorization.
