# Causal World Kernel Spec

This document is the Task 1 deliverable of `docs/superpowers/plans/2026-08-20-causal-world-kernel.md`.
It records the ownership audit of the current repository and fixes the design of the
observable causal layer **before** any production code changes.

Every claim below names a concrete file, class, or function in the current tree
(base commit `eecade71`, branch `feat/causal-world-kernel`). Where a proposed
concept from the plan did not survive contact with the code, the deviation is
called out explicitly in section 11.

---

## 1. Scope and non-negotiables

The causal layer answers one player-facing question — *why did this happen?* — by
**linking facts that existing systems already produce**. It is not a second
simulation.

Restating the plan invariants in terms of this repository:

1. `Simulator.step()` (`src/sim/simulator_engine/simulator.py`) stays the only
   execution path. The 29 entries of `SIMULATION_PHASES`
   (`src/sim/simulator_engine/phase_registry.py`) stay the only orchestrator.
2. `Event` (`src/classes/event.py`) stays the only fact identity, and
   `EventStorage` (`src/classes/event_storage.py`) behind
   `EventManager` (`src/sim/managers/event_manager.py`) stays the only fact store.
3. Domain state stays authoritative: `Avatar` (`src/classes/core/avatar/core.py`),
   `CityRegion`/`CultivateRegion` (`src/classes/environment/region.py`),
   `Sect` (`src/classes/core/sect.py`), `SectDiplomacyState`
   (`src/classes/sect_diplomacy_state.py`), `POIManager`
   (`src/classes/poi/manager.py`), `CirculationManager`
   (`src/classes/circulation.py`), `Dynasty` (`src/classes/core/dynasty.py`).
   Causal records are **evidence about** those mutations, never the mutation.
4. Agents are one participant. `phase_update_city_population`
   (`src/sim/simulator_engine/phases/world.py:199`) mutates world state today and
   emits **zero** events; it is a first-class causal participant, not an
   afterthought.
5. No composed scenario classes. Subsystems keep owning local laws.
6. LLM chooses intent (`LLMAI._decide`, `src/classes/ai.py`); the engine validates
   (`ActionMixin.commit_next_plan`, `src/classes/core/avatar/action_mixin.py`) and
   applies reality.
7. New worlds only. `check_save_compatibility`
   (`src/sim/load/load_game.py`) already declines strict version blocking, and
   `.cursor/rules/development-phase.mdc` forbids paying for backward compatibility.
8. No push, no PR, no publication, no VPS mutation.

---

## 2. What the code already owns

### 2.1 Facts

`Event` is a `@dataclass` with `month_stamp`, `content`, `related_avatars`,
`related_sects`, `is_major`, `is_story`, `event_type`, `render_key`,
`render_params`, `subject_snapshots`, `id` (uuid4), `created_at`, and a runtime-only
`observations: list[EventObservation]`.

Serialization boundary is explicit and dual:

- `Event.to_dict` / `Event.from_dict` — used by the save file section
  `EventsSection` (`src/sim/save/sections/save_sections.py:137`), which dumps up to
  `CONFIG.save.max_events_to_save` (`static/config.yml:222`, currently `1000`)
  recent events into the JSON save, and by `EventsLoadSection`
  (`src/sim/save/sections/load_events.py`), which replays them **only when the
  SQLite database is empty**.
- `EventStorage._init_db` / `add_event` / `_row_to_event` — the SQLite schema.
  Tables today: `events`, `event_avatars`, `event_sects`, `event_observations`.
  `PRAGMA foreign_keys = ON` is set, and every side table declares
  `FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE`.

Two behaviours that constrain the design:

- `EventStorage.cleanup` (`event_storage.py:688`) issues a plain
  `DELETE FROM events WHERE ...` and relies on cascade to prune side tables.
  Any new causal table must therefore also declare cascade, and causal queries
  must tolerate a **pruned ancestor**.
- `_row_to_event` does **not** rehydrate `Event.observations`. Observations are
  write-only from the runtime's perspective and are joined back in SQL by
  `EventStorage.query_page` for `EventAudience.OBSERVED`. This is the exact
  precedent the causal edges should follow.

### 2.2 The single write funnel

`finalize_step` (`src/sim/simulator_engine/finalizer.py`) is the only place that:

- de-duplicates `ctx.events` by `Event.id`,
- decorates major non-story events with close-relation observations via
  `append_close_relation_major_observations`
  (`src/classes/close_relation_event_service.py`),
- calls `ctx.world.event_manager.add_event(event)` for each final event,
- advances `ctx.world.month_stamp = ctx.world.month_stamp + 1`.

This is the causal layer's persistence seam and its month boundary. Nothing else
in the tree advances the month.

### 2.3 Action lifecycle and results

- `ActualActionMixin` (`src/classes/action/action.py`) defines the lifecycle:
  `can_start(**params) -> tuple[bool, str]`, `start`, `step`, `async finish`.
- `ActionResult` (`src/classes/action_runtime.py`) is already the neutral return
  envelope: `status: ActionStatus`, `events: list`, `payload: dict | None`,
  `next_action`.
- `ActionMixin.tick_action` (`src/classes/core/avatar/action_mixin.py`) drives it,
  collecting events through `Avatar._pending_events` and `Avatar.add_event`.
- `MutualAction` (`src/classes/mutual_action/mutual_action.py`) adds the
  initiator/target response cycle (`_build_response_choice_request`,
  `_handle_response_result`) and reuses the same `ActionResult`.
- `EventHelper.push_pair` / `push_self` (`src/classes/action/event_helper.py`) is
  the shared "write once to the sidebar" convention.

### 2.4 Affordances

- `ActionRegistry` (`src/classes/action/registry.py`) with `@register_action`.
- `ALL_ACTUAL_ACTION_CLASSES` and `get_action_infos(avatar)`
  (`src/classes/actions.py`) already filter by
  `Action.can_possibly_start()` and attach `param_options` from
  `build_param_options` (`src/classes/action/param_options.py`), driven by
  `PARAM_OPTION_SOURCES` / `ParamOptionSource`.
- `get_action_infos` currently **drops** impossible actions silently and never
  surfaces the `can_start` reason string. Both are pure information loss and the
  natural extension point for structured affordances.

### 2.5 Decisions

- `LLMAI._decide` (`src/classes/ai.py`) issues one
  `call_llm_with_task_name("action_decision", ...)` per idle avatar, concurrently
  via `asyncio.gather`, and returns
  `(action_name_params_pairs, avatar_thinking, short_term_objective)`.
- `phase_decide_actions` (`src/sim/simulator_engine/phases/actions.py`) selects the
  avatars (`current_action is None and not has_plans()`, minus the roleplay-
  controlled avatar) and calls `Avatar.load_decide_result_chain`, which stores
  `thinking` and `short_term_objective` on the avatar and enqueues `ActionPlan`s.
- `phase_commit_next_plans` then calls `Avatar.commit_next_plan`, which is where
  `can_start` rejection is currently **logged and discarded**.
- `SectDecider` (`src/classes/sect_decider.py`) is the existing precedent for a
  persisted decision record: its `_build_summary` output lands in
  `Sect.yearly_thinking` and is exposed through the sect detail assembler.
- `single_choice` (`src/systems/single_choice/`) owns bounded decisions:
  `SingleChoiceRequest`, `SingleChoiceDecision`, `ChoiceSource`, `FallbackPolicy`,
  `resolve_single_choice`.
- Test-mode determinism is mandatory: `resolve_test_mode_task`
  (`src/utils/llm/test_mode_fallbacks.py`) fails closed with
  `TestModeUnsupportedLLMTask` for any unregistered task name.

### 2.6 Memory and story

- Memory scope is derived, not stored: `matches_memory_scope`
  (`src/classes/event_query.py`) plus the SQL in `EventStorage.query_page`.
  Long-term memory = `is_major AND NOT is_story`.
- `EventObservation` + `render_observed_event` (`src/classes/event_renderer.py`)
  own propagation and per-observer rendering.
- `StoryEventService` (`src/classes/story_event_service.py`) owns narrative text.
  It always produces `is_story=True` events and is probability-gated by
  `StoryEventKind` against `CONFIG.world.story.probabilities`
  (`static/config.yml:110`), except `GATHERING` which is fixed at `1.0`.

### 2.7 Query and UI

- Query builders live in `src/server/services/game_queries.py`
  (`get_events_page`, `get_world_journal`), are wrapped by
  `GameQueryService` (`src/server/services/game_query_service.py`) and routed by
  `create_public_query_router` (`src/server/api/public_v1/query.py`).
  Response envelope is `ok_response` / `raise_public_error`
  (`src/server/services/public_api_contract.py`).
- Event → DTO conversion is `serialize_events_for_client`
  (`src/server/serialization.py:162`).
- Frontend: `eventApi` (`web/src/api/modules/event.ts`),
  `useWorldJournalStore` (`web/src/stores/worldJournal.ts`),
  `WorldJournalPanel.vue` (`web/src/components/game/panels/WorldJournalPanel.vue`),
  plus `MobileDashboard.vue`. The panel already declares four tabs and ships
  `focus` and `stories` as `disabled: true` placeholders — a ready-made slot for
  the Chronicle views.

### 2.8 Runtime, pause, failure

- `GameSessionRuntime` (`src/server/runtime/session.py`) owns pause state:
  `set_paused`, `set_roleplay_auto_paused`, `is_effectively_paused`,
  `get_pause_reason`, and serializes all world mutation through
  `run_mutation` / `run_mutation_measured`.
- `GameLoopRunner.run_once` (`src/server/loop/runner.py`) wraps
  `sim.step()` in `runtime.run_mutation` and **catches every exception, logs it,
  and continues to the next tick**. There is no pause-on-error today.
- `SimulationPhaseRunner.run` (`src/sim/simulator_engine/phase_runner.py`) can
  abort mid-step via `SimulationStepAborted`, returning `[]`. When it aborts,
  `finalize_step` never runs, so `ctx.events` are never persisted and
  `world.month_stamp` is never advanced.

**There is no month-granular snapshot or transaction anywhere.** The only
snapshot mechanism is `save_game` (`src/sim/save/save_game.py`), which writes a
full JSON payload and `shutil.copy2` copies the entire events SQLite file. This
single fact drives section 6.

---

## 3. Ownership matrix

| Concept | Existing owner (file : symbol) | Extension seam | Forbidden parallel implementation |
|---|---|---|---|
| Fact identity, content, time, participants | `src/classes/event.py : Event` | new optional typed fields + `to_dict`/`from_dict` | a `Fact`, `CausalNode`, or `WorldRecord` class |
| Fact persistence and pagination | `src/classes/event_storage.py : EventStorage`, `src/sim/managers/event_manager.py : EventManager` | new columns on `events` and one new side table created in `EventStorage._init_db`, written in `add_event` | a second DB, a JSON causal log, an event-sourcing replay log |
| `fact_kind` (occurrence / state transition / derived condition) | **new field on `Event`**, orthogonal to the existing `Event.event_type` | `Event.fact_kind`, `events.fact_kind` column | reusing/overloading `event_type`, which is already load-bearing for propagation (`finalizer.special_major_kinds`) and rendering (`render_key`) |
| `CausalLink` (typed edge between facts) | **new**, modelled exactly on `src/classes/event_observation.py : EventObservation` | `src/classes/causal_link.py : CausalLink` + `event_causal_links` table with `ON DELETE CASCADE` | a graph store, a generic `relations` table, edges stored inside `render_params` |
| `StateDelta` (evidence of a domain state change) | state owners: `Avatar`, `CityRegion`, `CultivateRegion`, `Sect`, `SectDiplomacyState`, `POIManager`, `CirculationManager`, `Dynasty` | evidence-only dataclass persisted with the event; **never applied** | a patch/apply engine, a `set_state(path, value)` API, ECS-style component writes |
| Neutral change envelope | `src/classes/action_runtime.py : ActionResult` (already has `payload`) and `src/sim/simulator_engine/context.py : SimulationStepContext.add_events` | a recorder handle on `SimulationStepContext`; optional keys in `ActionResult.payload` | a new `SimulationChangeSet` type threaded through all 29 phases — see §11.2 |
| Decision audit | `src/classes/ai.py : LLMAI._decide`, `src/classes/core/avatar/action_mixin.py : ActionMixin.load_decide_result_chain` (`Avatar.thinking`, `Avatar.short_term_objective`), `src/classes/sect_decider.py : SectDecider` | record the decision as an `AgentDecision` payload at the `phase_decide_actions` boundary | a second planner, a duplicate goal store, a duplicate memory store |
| Bounded decisions | `src/systems/single_choice/` : `SingleChoiceRequest`, `SingleChoiceDecision`, `resolve_single_choice` | reuse verbatim | a new choice resolver |
| Capability ("what can this entity do") | derived from `Sect`, `Avatar` inventory/technique mixins (`inventory_mixin.py`), `StoreMixin` on `CityRegion`, `src/classes/official_rank.py`, `src/systems/formation.py` | a read-only derivation function; no stored field | a `Capability` registry or persisted capability set |
| Affordance / constraint ("what is possible and why not") | `src/classes/action/registry.py : ActionRegistry`, `ActualActionMixin.can_start`, `Action.can_possibly_start`, `src/classes/actions.py : get_action_infos`, `src/classes/action/param_options.py : build_param_options` | extend `get_action_infos` to also return unavailable actions with their `can_start` reason | a second validator, a rules DSL, duplicated eligibility checks |
| Memory scope | `src/classes/event_query.py : matches_memory_scope` + SQL in `EventStorage.query_page` | reuse | a memory table |
| Propagation / observation | `src/classes/event_observation.py : EventObservation`, `src/classes/event_renderer.py : render_observed_event`, `src/classes/close_relation_event_service.py` | reuse | causal edges doubling as propagation |
| Narrative text | `src/classes/story_event_service.py : StoryEventService` | story events link with `contributed_to`, never as a cause | LLM prose treated as a cause; a second story generator |
| Death cause | `src/classes/death_reason.py : DeathReason`, `src/classes/death.py : handle_death` | emit a `CausalLink` alongside the existing reason string | a parallel death-cause registry |
| Month boundary and persistence | `src/sim/simulator_engine/finalizer.py : finalize_step` | attach causal records to events before `add_event`; keep the month advance here | a causal commit phase separate from `finalize_step` |
| Read API | `src/server/services/game_queries.py`, `game_query_service.py`, `src/server/api/public_v1/query.py` | new query functions in `game_queries.py` + routes in `query.py` | logic in `src/server/main.py` (forbidden by AGENTS.md rule 28/29) |
| Chronicle UI | `WorldJournalPanel.vue`, `web/src/stores/worldJournal.ts`, `web/src/api/modules/event.ts`, `web/src/types/api.ts` | fill the already-declared `focus` / `stories` tabs; add a `why` drill-down | a second journal component, a second event store |
| Pause / failure | `src/server/runtime/session.py : GameSessionRuntime`, `src/server/loop/runner.py : GameLoopRunner.run_once`, `src/sim/simulator_engine/phase_runner.py : SimulationStepAborted` | a new pause reason + abort before mutation | a custom transaction manager, a world-state deep copy per month |
| Test-mode determinism | `src/utils/llm/test_mode_fallbacks.py : resolve_test_mode_task` | register any new task name | a bypass that reaches a real provider |

---

## 4. Execution flow, current and proposed

### 4.1 Current (unchanged by this plan)

```
GameLoopRunner.run_once
  └─ runtime.run_mutation(sim.step)
       └─ SimulationPhaseRunner.run
            ctx = SimulationStepContext.create(world)
            for phase in SIMULATION_PHASES (1..29):
                events = phase.handler(simulator, ctx)   # mutates domain state
                ctx.add_events(events)
                raise_if_reset_requested()
            phase 29 = finalize_step(ctx):
                dedupe by Event.id
                append close-relation observations
                event_manager.add_event(e) for each
                world.month_stamp += 1
```

### 4.2 Proposed observer flow

The only structural addition is a **recorder** hanging off
`SimulationStepContext`. It is passive: it is written to by domain owners that
already ran, and it is drained by `finalize_step`.

```
SimulationPhaseRunner.run
  ctx = SimulationStepContext.create(world)      # ctx.causal: CausalRecorder
  for phase in SIMULATION_PHASES:
      events = phase.handler(simulator, ctx)     # domain executes normally
      ctx.add_events(events)                     # unchanged
      # owners that opted in have called ctx.causal.record_* while running
  finalize_step(ctx):
      dedupe                                     # unchanged
      close-relation observations                # unchanged
      ctx.causal.attach_to(final_events)         # NEW: links + deltas onto Events
      event_manager.add_event(e)                 # persists causal columns/table
      world.month_stamp += 1                     # unchanged
```

Properties this buys:

- Removing the recorder (or leaving it empty) reproduces today's behaviour byte
  for byte. That is the acceptance test for Task 3.
- No phase signature changes. Phases keep returning `list[Event] | None`.
- No new execution order, no new phase, no re-indexing of `SIMULATION_PHASES`.
- The recorder never calls a domain method. It only accepts records.

---

## 5. Schema drafts and serialization boundaries

### 5.1 `FactKind`

```python
# src/classes/event.py
class FactKind(StrEnum):
    OCCURRENCE = "occurrence"          # something happened (default)
    STATE_TRANSITION = "state_transition"  # a domain-owned value changed
    DERIVED_CONDITION = "derived_condition"  # a condition became true/false
```

`Event.fact_kind: FactKind = FactKind.OCCURRENCE`. Orthogonal to `event_type`,
`is_major`, and `is_story`; none of those change meaning.

### 5.2 `CausalRelation` and `CausalLink`

```python
# src/classes/causal_link.py
class CausalRelation(StrEnum):
    TRIGGERED_BY = "triggered_by"
    ENABLED_BY = "enabled_by"
    MOTIVATED_BY = "motivated_by"
    RESPONSE_TO = "response_to"
    RESOLVES = "resolves"
    PREVENTED_BY = "prevented_by"
    CONTRIBUTED_TO = "contributed_to"

@dataclass
class CausalLink:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""            # the effect; set by EventStorage.add_event
    cause_event_id: str = ""      # the cause; may point at a pruned event
    relation: str = CausalRelation.TRIGGERED_BY
    weight: float = 1.0           # multifactor contribution, 0..1
    note_key: str | None = None   # i18n key, never a rendered sentence
    note_params: dict | None = None
    created_at: float = field(default_factory=time.time)
```

Multifactor causality is expressed as **several links on one effect event**, which
is why `weight` lives on the edge rather than on the event. Direction is always
effect → cause, matching how the `why` query walks ancestors.

### 5.3 `StateDelta`

```python
# src/classes/state_delta.py
@dataclass
class StateDelta:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    owner_kind: str = ""     # "avatar" | "region" | "sect" | "poi" | "dynasty" | "world"
    owner_id: str = ""       # the domain owner's own id
    aspect: str = ""         # owner-declared semantic label, e.g. "population"
    before: str | None = None
    after: str | None = None
    magnitude: float | None = None
```

Hard rules:

- `before`/`after` are **strings for display and diffing only**. No code may parse
  them back into domain values, and nothing may write them into a domain object.
  This is what keeps `StateDelta` evidence rather than a patch.
- `aspect` is chosen by the owning subsystem. There is no central aspect registry
  and no schema validation across owners — a central registry would recreate the
  generic-patch design the plan forbids.
- `owner_kind` / `owner_id` are the same identifiers already exposed by
  `get_detail` (`game_queries.get_detail` accepts `avatar` / `region` / `sect`),
  so the UI can already link a delta to a detail panel.

### 5.4 `AgentDecision`

```python
# src/classes/agent_decision.py
@dataclass
class AgentDecision:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    month_stamp: int = 0
    subject_kind: str = "avatar"      # "avatar" | "sect"
    subject_id: str = ""
    source: str = "llm"               # mirrors single_choice.ChoiceSource
    considered: list[str] = field(default_factory=list)  # action class names offered
    chosen_action: str = ""           # ActionPlan.action_name
    chosen_params: dict = field(default_factory=dict)
    thinking: str = ""                # already on Avatar.thinking
    short_term_objective: str = ""    # already on Avatar.short_term_objective
    rejected: list[dict] = field(default_factory=list)  # {"action", "reason"} from can_start
    result_event_id: str | None = None
```

`AgentDecision` is an **audit record**, not an input to anything. Nothing in the
simulator may read it back to make a decision. `thinking` and
`short_term_objective` remain owned by `Avatar`; the record copies them.

### 5.5 Persistence

`events` gains two nullable columns (created in `EventStorage._init_db` alongside
the existing `subject_snapshots` pattern, including the `PRAGMA table_info`
add-column guard already used there):

```sql
ALTER TABLE events ADD COLUMN fact_kind TEXT;      -- NULL == "occurrence"
ALTER TABLE events ADD COLUMN causal_payload TEXT; -- JSON: deltas + decision
```

One new side table, mirroring `event_observations`:

```sql
CREATE TABLE IF NOT EXISTS event_causal_links (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    cause_event_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    note_key TEXT,
    note_params TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, cause_event_id, relation),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_event_causal_links_event_id
    ON event_causal_links(event_id);
CREATE INDEX IF NOT EXISTS idx_event_causal_links_cause_event_id
    ON event_causal_links(cause_event_id);
```

Deliberate choices:

- **No FK on `cause_event_id`.** `EventStorage.cleanup` deletes minor events, so a
  surviving major event may legitimately reference a pruned cause. The `why` query
  renders that as a truncated chain rather than failing.
- **Links are a table; deltas and the decision are JSON.** Links need indexed
  traversal in both directions (`why` walks up, "what did this cause" walks down).
  Deltas and decisions are only ever read together with their own event, so a JSON
  column avoids two more tables and two more joins on the hot event page.
- **Write path**: `EventStorage.add_event` writes the new columns in the existing
  `INSERT OR IGNORE` and inserts links in the same `_transaction()`, exactly as it
  does for `event_observations`.
- **Read path**: `_row_to_event` restores `fact_kind` and the parsed
  `causal_payload`, and — unlike `observations` — does *not* eagerly load links.
  Links are loaded only by the dedicated `why` query, so the existing event page
  cost is unchanged.
- **Save file**: `Event.to_dict` / `from_dict` gain `fact_kind` and
  `causal_payload`; links go in as a nested list on the event dict. This keeps
  `EventsSection` / `EventsLoadSection` working without a new save section, and the
  1000-event JSON cap still applies. The SQLite file remains the authority — the
  JSON copy is a fallback path only used when the DB is empty.
- **Runtime-only mirror**: `Event.causal_links: list[CausalLink]` gets
  `repr=False, compare=False` like `Event.observations`, so nothing about `Event`
  equality or logging changes.

---

## 6. Failure semantics

### 6.1 What "rollback" can and cannot mean here

`Simulator.step()` mutates `Avatar`, `Region`, `Sect`, `POIManager`, and `World`
in place across 29 phases with no transaction and no snapshot. `save_game` is the
only snapshot and it `shutil.copy2`s the whole events database
(`_copy_events_database_if_needed`). Taking a real world snapshot every month is
therefore not affordable, and a deep-copy-per-month would be a new subsystem —
precisely what invariant 2 forbids.

What *is* already atomic is the **month boundary**: `finalize_step` is the sole
writer to `EventManager` and the sole place that advances `world.month_stamp`, and
`SimulationPhaseRunner` already has an abort path (`SimulationStepAborted`) that
skips it.

So the required semantics are restated as **fail before mutating, then pause**:

1. A *required* AI decision is one whose absence would leave the world silently
   inconsistent. In the Phase 1 slice the required set is exactly the
   `action_decision` calls in `LLMAI._decide` for avatars selected by
   `phase_decide_actions`. Everything else (`long_term_objective`, `nickname`,
   `story_teller`, `backstory`, `random_minor_event`, `sect_thinker`) is
   **optional**: its current behaviour on failure is to skip, and that stays.
2. On a required-decision failure, `phase_decide_actions` raises
   `SimulationStepAborted`. `SimulationPhaseRunner.run` returns `[]`,
   `finalize_step` never runs, `ctx.events` are discarded, and
   `world.month_stamp` is **not** advanced. The month boundary is intact.
3. `GameLoopRunner.run_once` must stop swallowing this: it calls
   `runtime.set_paused(True)` and records a visible reason, surfaced through
   `GameSessionRuntime.get_pause_reason` (new value
   `required_decision_failed`) and the existing
   `/api/v1/query/runtime/status` route.
4. Resuming re-runs the same month from phase 1.

### 6.2 The residue, stated honestly

Aborting at phase 4 means phases 1–3 already ran. Their surviving side effects:

| Phase | Handler | Side effect | Safe to re-run? |
|---|---|---|---|
| 1 | `phase_update_perception_and_knowledge` | `avatar.known_regions.add(...)` | Yes — set union, idempotent |
| 1 | same handler | `avatar.occupy_region(region)` | **No** — a real state change whose describing `Event` would be discarded |
| 2 | `phase_long_term_objective_thinking` | sets the avatar's long-term objective | Yes — overwritten on re-run |
| 3 | `phase_process_gatherings` | gathering state in `GatheringManager` | Not verified for idempotency |

Because of rows 2 and 4, Task 6 must make one small structural change before the
gate is trustworthy: **split `phase_update_perception_and_knowledge` so that
perception refresh (pure, idempotent) stays at index 1 and region claiming moves
to its own phase after the decision gate.** This also fixes a genuine
single-owner violation — a perception phase should not own territory
acquisition — and is the reason section 11.3 amends the plan.

Explicitly out of scope for the slice: rolling back gathering state. Task 6 places
the decision gate before `phase_process_gatherings` rather than trying to undo it.

### 6.3 Test mode

Any LLM task added by Task 4 must be registered in `resolve_test_mode_task` and
in `registered_test_mode_tasks()`. `TestModeUnsupportedLLMTask` already fails
closed, so an unregistered task cannot silently reach a provider. The Phase 1
slice is designed to add **no new LLM task**: the decision audit records what
`action_decision` already returned.

---

## 7. Query and UI contract

### 7.1 `why`

New builder in `src/server/services/game_queries.py`, new route in
`src/server/api/public_v1/query.py`, wrapped by `GameQueryService`. Nothing in
`src/server/main.py`.

```
GET /api/v1/query/events/{event_id}/causal?depth=3&limit=40
-> ok_response({
     "event": <serialize_events_for_client single item, plus fact_kind>,
     "causes": [
       {"relation": "triggered_by", "weight": 1.0,
        "note_key": null, "note_params": null,
        "depth": 1, "event": <event DTO | null>, "pruned": false}
     ],
     "effects": [ ... same shape, edges where cause_event_id == event_id ... ],
     "deltas": [
       {"owner_kind": "region", "owner_id": "12", "aspect": "population",
        "before": "80.0", "after": "78.4", "magnitude": -1.6}
     ],
     "decision": <AgentDecision DTO | null>,
     "truncated": false
   })
```

Contract rules:

- `depth` is clamped server-side (max 5) and `limit` bounds the total node count;
  `truncated: true` says the walk was cut. Traversal is breadth-first with a
  visited set so a cycle cannot loop.
- `pruned: true` with `event: null` is the normal representation of a cause that
  `EventStorage.cleanup` removed. It is not an error.
- Read-only. It is a `query`, never a `command`, per AGENTS.md rule 28.
- All human-readable text is either the event's existing localized content or an
  i18n key. `note_key` never carries a rendered sentence — AGENTS.md rule 14.

### 7.2 Chronicle views

`get_world_journal` (`game_queries.py:530`) already returns `period`, `activity`,
`highlights`, `ongoing` for `period_months ∈ {1, 3, 12}`, and
`WorldJournalPanel.vue` already declares `now`, `focus`, `stories`, `timeline`
with the middle two disabled. The slice fills them:

- `now` — unchanged.
- `focus` — people and objectives, from the existing `ongoing` aggregation plus
  `Avatar.short_term_objective` / long-term objective.
- `stories` — `is_story` events for the period, which the current response only
  counts.
- `timeline` — unchanged; it stays the full paginated `EventPanel` history.
  **Views filter and summarize; they never replace the timeline.**
- Every event row in every view gets a "why" affordance that opens the §7.1
  drill-down.

Frontend obligations (from `.cursor/rules/frontend*.mdc`):

- DTOs first in `web/src/types/api.ts`, mapping in `web/src/api/mappers/`, no
  `any`; errors via `appError`.
- Panel logic in `web/src/stores/worldJournal.ts` or a composable, not in the
  `.vue`; large objects via `shallowRef` (the store already does this for
  `journal`).
- Mobile: `MobileDashboard.vue` must keep responsive width and safe-area spacing;
  causal chains scroll inside their own container.
- Pagination is mandatory for anything list-shaped.

---

## 8. First vertical slice, and non-goals

### 8.1 In scope

1. `FactKind` on `Event`; `CausalLink`, `StateDelta`, `AgentDecision` dataclasses;
   `EventStorage` schema, write path, and read path; `to_dict`/`from_dict`.
2. A passive `CausalRecorder` on `SimulationStepContext`, drained by
   `finalize_step`.
3. Exactly two instrumented flows:
   - **agent flow**: `Breakthrough` (`src/classes/action/breakthrough.py`) —
     `motivated_by` the `AgentDecision`, `enabled_by` the cultivation state, plus a
     `StateDelta` on the avatar's realm.
   - **non-agent flow**: `phase_update_city_population`
     (`phases/world.py:199`) — today it changes `CityRegion.population` and emits
     nothing. It gains a `fact_kind=STATE_TRANSITION` event with a `StateDelta`
     for `aspect="population"`. This is the clearest proof that causality is not
     agent-centric.
4. Affordance exposure: `get_action_infos` also reports unavailable actions with
   their `can_start` reason; `commit_next_plan` rejections become
   `AgentDecision.rejected` instead of log-only.
5. The `why` query, the two Chronicle views, and the drill-down.
6. Failure semantics and the phase split from §6.

### 8.2 Explicit non-goals

Not in this plan, and no placeholder code for them: physiology or intoxication,
ghosts or hauntings, water scarcity, population migration, rumor propagation,
generational history, economy simulation beyond `CirculationManager`, causal
inference or scoring, LLM-authored causal edges, retroactive causality for
existing saves, and any composed scenario class.

---

## 9. Test map

| Area | File | What it must prove |
|---|---|---|
| Event schema | `tests/test_event.py` | `fact_kind` round-trips through `to_dict`/`from_dict`; default is `occurrence`; existing assertions unchanged |
| Storage | `tests/test_event_storage.py` | links write and read back; `UNIQUE` de-duplicates; `cleanup` cascades links and leaves a dangling `cause_event_id` readable; a DB created before the change gains the new columns via the `PRAGMA table_info` guard |
| Save/load | `tests/test_save_load_events.py` | causal payload survives save → load; SQLite remains authoritative; the JSON fallback path still works |
| Recorder neutrality | `tests/test_simulator.py` | with an empty recorder, `step()` produces the identical event set — the Task 3 acceptance test |
| Agent flow | `tests/test_breakthrough_logic.py` | breakthrough emits the expected links and delta |
| Non-agent flow | `tests/test_city_population.py` | population change emits a `STATE_TRANSITION` event with a `population` delta and does not perturb the logistic result |
| Affordances | `tests/test_action_can_possibly_start.py`, `tests/test_action_param_options.py` | unavailable actions appear with reasons; `param_options.value` stays executable (AGENTS.md rule 3) |
| Decision audit | `tests/test_ai.py` | the audit reflects what `LLMAI._decide` returned; `can_start` rejections land in `rejected` |
| Failure | `tests/test_loop_runtime.py`, `tests/test_game_session_runtime.py` | required-decision failure leaves `month_stamp` unadvanced, persists no events, and pauses with `required_decision_failed` |
| API | `tests/test_api_events.py`, `tests/test_public_api_v1.py` | `why` response shape, depth clamp, `truncated`, `pruned`, and `ok_response` envelope |
| Test mode | `tests/test_llm_test_mode.py` | no new unregistered LLM task |
| Frontend | `web/src/__tests__/components/game/panels/WorldJournalPanel.test.ts`, `.../mobile/MobileDashboard.test.ts` | the two new tabs render, paginate, and the `why` drill-down opens; lazy-loaded modals use `{ immediate: true }` watchers (AGENTS.md rule 38) |
| i18n | `tests/test_frontend_locales.py`, `tests/test_backend_locales.py` | new keys exist for `zh-CN`; no Chinese `msgid` |

Commands: `pytest` (or `pytest -n 8`), `cd web && npm run test && npm run type-check`.

## 10. Performance risks

1. **Event volume.** Instrumenting `phase_update_city_population` adds one event
   per city per month where there were none. With `CONFIG.save.max_events_to_save`
   at `1000`, these can crowd the JSON save tail. Mitigation: emit the transition
   event only when the delta crosses a configured threshold, and keep it
   `is_major=False` so `cleanup(keep_major=True)` prunes it.
2. **`why` traversal.** Unbounded ancestor walking on a long-running world is
   the main cost. Mitigated by the depth clamp, the node limit, the visited set,
   and `idx_event_causal_links_event_id`.
3. **Event page regression.** Avoided by not loading links in `_row_to_event`.
   `tests/test_api_events.py::test_full_pagination_cycle` is the guard.
4. **Write amplification.** Links are inserted inside the existing
   `add_event` transaction, so no extra commit. `EventStorage` is single-connection
   under `threading.RLock`, so a large per-event link fan-out would serialize
   against reads — the recorder must cap links per event (a small constant, 8).
5. **Save size.** `causal_payload` is JSON per event, capped by the existing
   1000-event ceiling. `_copy_events_database_if_needed` cost grows with the DB,
   which is already true today.
6. **No new LLM calls.** `phase_decide_actions` already issues one
   `action_decision` per idle avatar per month via `asyncio.gather`. The slice adds
   zero calls; Task 6 must not turn the audit record into a reason for a second
   per-avatar call. There is no "named tier" concept in the code today — the
   existing detail tiers are `Avatar` (full LLM agent), `Mortal`
   (`src/sim/managers/mortal_manager.py`, aggregate, no LLM), and background NPCs
   (`src/systems/background_npc/service.py`, template text, no LLM), plus the
   per-avatar opt-in `Avatar.enable_metrics_tracking`. Any tiering work must build
   on those, not invent a parallel tier field.

---

## 11. Plan amendments required by code evidence

Only these three. Everything else in the plan survived the audit.

### 11.1 `fact_kind` is a new field, not a reinterpretation of `event_type`

The plan lists `fact_kind` under "extend `Event`" without saying how it relates to
what is there. `Event.event_type` is already load-bearing: `finalizer.py` keys
`special_major_kinds` off it, `close_relation_event_service` maps it to bond
labels, and `background_npc/service.py` sets it. Overloading it would break those.
`fact_kind` is therefore additive and orthogonal.

### 11.2 `SimulationChangeSet` is not justified; use the recorder + `ActionResult.payload`

Direct evidence: every entry in `SIMULATION_PHASES` returns `list[Event] | None`,
consumed by `SimulationStepContext.add_events`, and `ActionResult` already carries
a free-form `payload`. Introducing a new envelope type would require editing all
29 phase handlers and every `Action.step` implementation for zero behavioural
gain, and would make "recording absent ⇒ behaviour identical" much harder to
prove. Replaced by: a passive `CausalRecorder` on `SimulationStepContext`, drained
by `finalize_step`, plus optional keys in the existing `ActionResult.payload`.

### 11.3 "Restore the month boundary" must be "abort before mutating", and it needs a phase split

Direct evidence: `Simulator.step()` has no transaction and no snapshot;
`save_game` is the only snapshot and it copies the entire events SQLite file. A
literal per-month checkpoint/restore is not affordable and would be a new
subsystem. What exists instead is a genuinely atomic month boundary in
`finalize_step` plus the `SimulationStepAborted` path in
`SimulationPhaseRunner`. Task 6 is therefore: place the required-decision gate so
that failure aborts before any non-idempotent mutation, and additionally split
`phase_update_perception_and_knowledge` so region claiming moves out of the
perception phase (which is also a single-owner fix). See §6.2 for the residue
table this is based on.

---

## 12. Walkthrough: drunk worker → drowning → haunting → water crisis

The point of this section is that the chain below contains **no scenario class**.
Every step is a local law owned by an existing subsystem, and the chain exists only
as `CausalLink` rows a reader can walk.

Nothing here is implemented by this plan; §8.2 lists it all as a non-goal. It is a
feasibility argument for the schema.

1. **Intoxication (a future local law owned by the item/effect layer,
   `src/classes/effect/`, `src/classes/items/`).** A mortal consumes wine at a
   `CityRegion` store (`StoreMixin`). The effect layer emits
   `fact_kind=STATE_TRANSITION` with a `StateDelta(owner_kind="avatar",
   aspect="intoxication", before="0", after="2")`. No other system knows about
   drunkenness.

2. **Drowning (a future local law owned by movement / region hazards,
   `src/classes/action/move*.py`, `src/classes/environment/region.py`).** The
   movement law asks the region whether crossing water is hazardous and consults
   whatever modifiers apply — one of which happens to be intoxication. On failure
   it calls the existing `handle_death` (`src/classes/death.py`) with a
   `DeathReason`. The recorder attaches to the death event:
   `triggered_by` → the water-crossing event, `enabled_by` → the intoxication
   transition (weight `0.6`). The movement law never mentions wine; it only asks
   for modifiers.

3. **Haunting (a future local law owned by `POIManager` and the POI layer,
   `src/classes/poi/`).** `handle_death` already calls
   `poi_manager.create_grave_from_avatar`. A future spiritual-ecology law reads
   grave POIs near a water region and, on its own thresholds, emits a
   `fact_kind=DERIVED_CONDITION` event with a `StateDelta(owner_kind="region",
   aspect="spiritual_taint")` and `CausalLink(relation=CONTRIBUTED_TO)` to each
   contributing death. Multifactor is native: three drownings produce three
   weighted edges into one condition, not a `HauntedLake` object.

4. **Water crisis (a future local law owned by `CityRegion`).**
   `phase_update_city_population` already computes logistic growth from
   `population` and `population_capacity`. A future law lets a region's
   `spiritual_taint` reduce effective `population_capacity`. Population then falls
   through the **existing** `change_population`, and the instrumented phase from
   §8.1 emits a `STATE_TRANSITION` with `aspect="population"` and
   `enabled_by` → the taint condition.

5. **Reading it back.** The player opens the population-decline entry in the
   Chronicle and follows §7.1: population decline `enabled_by` taint,
   taint `contributed_to`-by three deaths, each death `triggered_by` a crossing and
   `enabled_by` an intoxication transition. Four subsystems that never referenced
   each other produced one legible chain, and nothing composed it.

What made this possible: typed edges instead of a scenario graph, `StateDelta` as
evidence so each owner keeps writing its own state, `weight` for multifactor
contribution, and `DERIVED_CONDITION` so "the lake is haunted" is a fact with
causes rather than a class.
