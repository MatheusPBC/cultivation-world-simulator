# Causal World Kernel Implementation Plan

> Execute task by task. Each implementation task must be committed separately and reviewed before the next task starts.

## Goal

Add an observable causal layer to the existing simulation so the game can explain why state changed without creating a second simulation engine, a parallel planner, or scripted compound scenarios.

## Architectural invariants

1. Causality observes and links existing systems; it is never a new execution path.
2. Every concept has one owner. Extend or refactor the current owner instead of creating a parallel subsystem.
3. Existing domain state remains authoritative. Causal records are semantic evidence, not generic patches and not event sourcing.
4. Agents participate in causality but are not its center. Environment, economy, physiology, organizations, resources, and spiritual ecology are equal participants.
5. Subsystems implement local laws only. Never add a composed scenario such as `HauntedLakeCrisis`.
6. The LLM may choose intent and explain results; the engine validates and applies reality.
7. This branch targets newly created worlds. Do not build compatibility layers for old saves.
8. Preserve user data and never publish to the official repository.

## Proposed vocabulary, subject to Task 1 ownership audit

> Task 1 is complete. The audited design is `docs/specs/causal-world-kernel.md`.
> Three entries below were amended by direct code evidence; see section 11 of that spec.

- Existing `Event`: canonical identity and historical record. Extend it with causal metadata; do not add a second fact store.
- `fact_kind`: distinguishes occurrence, state transition, and derived condition. **Amended by Task 1:** it is a new field additive to and orthogonal to the existing `Event.event_type`, which is already load-bearing in `src/sim/simulator_engine/finalizer.py` (`special_major_kinds`), `src/classes/close_relation_event_service.py`, and `src/systems/background_npc/service.py`. Do not overload `event_type`.
- `CausalLink`: typed edge between existing events/facts. Initial relations: `triggered_by`, `enabled_by`, `motivated_by`, `response_to`, `resolves`, `prevented_by`, `contributed_to`.
- `StateDelta`: semantic evidence of a domain-owned state change. It must not mutate state itself.
- ~~`SimulationChangeSet`: neutral return envelope for semantic changes emitted by existing owners.~~ **Dropped by Task 1.** Every entry of `SIMULATION_PHASES` (`src/sim/simulator_engine/phase_registry.py`) already returns `list[Event] | None` into `SimulationStepContext.add_events`, and `ActionResult` (`src/classes/action_runtime.py`) already carries a free-form `payload`. A new envelope would mean editing all 29 phase handlers and every `Action.step` for zero behavioural gain. Replaced by a passive `CausalRecorder` on `SimulationStepContext`, drained by `finalize_step`, plus optional keys in `ActionResult.payload`.
- `AgentDecision`: audit record for an LLM/rule decision; it must not become another planner.
- Capability: a domain-owned answer to what an entity/settlement can do, derived from people, institutions, items, formations, or other current owners.
- Affordance/constraint: structured answer to what is currently possible or impossible and why, extending the existing action registry and `can_start` machinery.

## Delivery boundary

This plan implements the smallest end-to-end Phase 0 and Phase 1 slice. It does not yet implement physiology, ghosts, water scarcity, population migration, rumor propagation, or generational history. Those later systems should become possible by composing local laws over this foundation.

---

### Task 1: Ownership audit and final design spec

**Purpose:** Prove where each concept belongs in the current code before changing runtime behavior.

**Inspect:**

- `src/classes/event.py`
- `src/classes/event_storage.py`
- action and mutual-action result/lifecycle abstractions
- simulator step context, phases, finalizer, pause/error handling, save/load
- current AI deciders, goals, memories, story event service
- action registry, `can_start`/`can_possibly_start`, `PARAM_OPTION_SOURCES`
- stable query API and World Journal frontend path
- relevant tests and specs

**Create:**

- `docs/specs/causal-world-kernel.md`
- Update this plan only where direct code evidence invalidates a proposed owner or seam.

**The spec must include:**

- an ownership matrix: concept, existing owner, extension seam, forbidden parallel implementation;
- current execution flow and proposed observer flow;
- concrete schema drafts with serialization boundaries;
- exact first vertical slice and explicit non-goals;
- failure semantics, including required AI decision failure and month rollback/pause;
- query/UI contract for `why` and Chronicle views;
- migration stance for new worlds only;
- focused test map and performance risks;
- a short walkthrough showing how future local laws could produce the drunk worker -> drowning -> haunting -> water crisis chain without any composite scenario code.

**Verification:**

- Every architectural claim names current files/classes/functions.
- No proposed concept duplicates an existing owner.
- No production code changes in this task.
- Commit message: `docs: define causal world kernel ownership`

---

### Task 2: Extend canonical events with causal metadata

**Purpose:** Make existing history causally linkable while retaining `Event` and `EventStorage` as owners.

**Implement after Task 1 review:**

- Add the minimum typed causal metadata approved by the audit.
- Support multifactor links through multiple typed edges.
- Add semantic deltas as evidence only.
- Preserve centralized event storage and paginated queries.
- Add serialization and focused unit tests.

**Non-goals:** generic state patching, a parallel causal database, UI changes.

**Commit message:** `feat: add causal metadata to world events`

---

### Task 3: Record causal changes from existing domain owners

**Purpose:** Add a recorder/collector seam without routing execution through a causal engine.

**Implement after Task 2 review:**

- Define the smallest neutral change-set/result contract justified by the audit.
- Adapt existing action result and simulator phase boundaries rather than replacing them.
- Record cause links and semantic state deltas after domain owners execute normally.
- Instrument two representative existing flows: one agent/action flow and one non-agent/system flow.
- Add focused unit and integration tests proving behavior is unchanged when recording is absent.

**Commit message:** `feat: record causal changes from simulation owners`

---

### Task 4: Expose structured affordances and decision audit

**Purpose:** Let agents and users understand what is possible and why without creating another planner.

**Implement after Task 3 review:**

- Extend current action discovery/validation to expose available and unavailable actions with reasons.
- Record current decider inputs, selected intent/action, and resulting event identity where architecturally appropriate.
- Do not duplicate goals, memory, planner, or action validation.
- Register deterministic test-mode behavior for any new LLM task.
- Add focused tests.

**Commit message:** `feat: expose causal affordances and decisions`

---

### Task 5: Add causal queries and Chronicle UI slice

**Purpose:** Deliver an end-to-end observable feature to the player.

**Implement after Task 4 review:**

- Add stable read-only query endpoints for causal event detail and bounded ancestor traversal (`why`).
- Keep query building in the existing service/query layer, not `main.py`.
- Extend the existing World Journal with alternate views for timeline, highlights, people/objectives, and causal explanation using current design patterns.
- Preserve the existing full timeline; views filter/summarize it rather than replacing history.
- Ensure responsive mobile width, safe-area spacing, pagination, and typed DTO/mappers.
- Add backend and frontend tests.

**Commit message:** `feat: add causal chronicle views`

---

### Task 6: Failure semantics, regression, and documentation

**Purpose:** Make the vertical slice safe to run continuously.

**Implement after Task 5 review:**

- Apply the Task 1-approved semantics for required monthly AI decisions. **Amended by Task 1:** a per-month checkpoint/restore is not affordable — `Simulator.step()` has no transaction and no snapshot, and `save_game` (`src/sim/save/save_game.py`) is the only snapshot mechanism, copying the whole events SQLite file via `_copy_events_database_if_needed`. Use the atomic month boundary that already exists instead: `finalize_step` is the sole writer to `EventManager` and the sole place that advances `world.month_stamp`, and `SimulationPhaseRunner` already has the `SimulationStepAborted` path that skips it. So: **abort before mutating, then pause.** On a required-decision failure, `phase_decide_actions` aborts the step, no events are persisted, the month is not advanced, and `GameLoopRunner.run_once` must stop swallowing the error and instead call `runtime.set_paused(True)` with a new `get_pause_reason` value.
- Prerequisite for the gate above: split `phase_update_perception_and_knowledge` (`src/sim/simulator_engine/phases/world.py`) so that perception refresh stays at index 1 and region claiming (`avatar.occupy_region`) moves to its own phase after the decision gate. It is the only non-idempotent mutation before the gate, and moving it is also a single-owner fix. See section 6.2 of the spec.
- Do not make every agent a monthly LLM call. Named/high-detail tiers only; lower tiers remain rule/aggregate based.
- Run focused backend/frontend suites, serialization tests, and a bounded multi-month simulation smoke test.
- Measure event volume and bounded `why` query cost.
- Update customization and testing documentation.

**Commit message:** `feat: harden causal simulation cycle`

## Review protocol

For every task:

1. A fresh implementer receives only the task brief and current repository state.
2. The implementer writes a report under the task workspace and commits the change.
3. A fresh reviewer checks the exact task contract and diff.
4. Any required fixes are made and re-reviewed before moving on.
5. No push, PR, deployment, or VPS mutation is allowed without separate user authorization.
