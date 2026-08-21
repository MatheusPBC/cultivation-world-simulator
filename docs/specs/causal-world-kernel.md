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
- `get_action_infos` drops impossible actions **on purpose**, and the reason is in
  the code: `can_possibly_start`'s own docstring says it exists
  「用于在AI决策时过滤掉绝对不可能执行的动作，以减小prompt长度」
  (`src/classes/action/action.py:129-134`) — i.e. to shrink the prompt.
  `get_action_infos_str` feeds three prompt builders: `LLMAI._decide`
  (`src/classes/ai.py:56`), `src/classes/long_term_objective.py:94`, and
  `src/server/services/roleplay_service.py:329`. Re-adding impossible actions there
  would inflate every `action_decision` prompt and change the option set the model
  sees — a behavioural regression, not an improvement. The affordance work must
  therefore branch *beside* this path, not widen it. See §5.5 and §8.1.4.
- `Avatar.commit_next_plan` (`src/classes/core/avatar/action_mixin.py`) is where the
  `can_start(**params)` reason string actually exists, and it is discarded there by
  a `logger.warning(...)` + `continue`. That is the real information loss.

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
| `fact_kind` (occurrence / state transition / derived condition / decision) | n/a (new) — nearest existing owner `src/classes/event.py : Event`, whose `event_type` it must **not** overload | `Event.fact_kind`, `events.fact_kind` column | reusing/overloading `event_type`, which is already load-bearing for propagation (`finalizer.special_major_kinds`) and rendering (`render_key`) |
| `CausalLink` (typed edge between facts) | n/a (new) — nearest existing owner `src/classes/event_observation.py : EventObservation`, whose table shape it copies exactly | `src/classes/causal_link.py : CausalLink` + `event_causal_links` table with `ON DELETE CASCADE` | a graph store, a generic `relations` table, edges stored inside `render_params` |
| `StateDelta` (evidence of a domain state change) | n/a (new record); the **state** stays owned by `Avatar`, `CityRegion`, `CultivateRegion`, `Sect`, `SectDiplomacyState`, `POIManager`, `CirculationManager`, `Dynasty` | evidence-only dataclass persisted with the event; **never applied** | a patch/apply engine, a `set_state(path, value)` API, ECS-style component writes |
| Neutral change envelope | `src/classes/action_runtime.py : ActionResult` (already has `payload`) and `src/sim/simulator_engine/context.py : SimulationStepContext.add_events` | a recorder handle on `SimulationStepContext`; optional keys in `ActionResult.payload` | a new `SimulationChangeSet` type threaded through all 29 phases — see §11.2 |
| Decision audit (`AgentDecision`, carried on a `fact_kind=DECISION` `Event` — §5.4) | `src/classes/ai.py : LLMAI._decide`, `src/classes/core/avatar/action_mixin.py : ActionMixin.load_decide_result_chain` (`Avatar.thinking`, `Avatar.short_term_objective`), `src/classes/sect_decider.py : SectDecider` | emit a `fact_kind=DECISION` `Event` at the `phase_decide_actions` boundary carrying the `AgentDecision` in `causal_payload`, so `motivated_by` edges have a target (§5.4) | a second planner, a duplicate goal store, a duplicate memory store |
| Bounded decisions | `src/systems/single_choice/` : `SingleChoiceRequest`, `SingleChoiceDecision`, `resolve_single_choice` | reuse verbatim | a new choice resolver |
| Capability ("what can this entity do") | derived from `Sect`, `Avatar` inventory/technique mixins (`inventory_mixin.py`), `StoreMixin` on `CityRegion`, `src/classes/official_rank.py`, `src/systems/formation.py` | a read-only derivation function; no stored field | a `Capability` registry or persisted capability set |
| Affordance / constraint ("what is possible and why not"), **player/API-facing** | `src/classes/action/registry.py : ActionRegistry`, `Action.can_possibly_start`, `Action.get_requirements` / `REQUIREMENTS_ID`, `src/classes/action/param_options.py : build_param_options` | a **new** sibling builder in `src/classes/actions.py` (e.g. `build_action_affordances(avatar)`) that lists available *and* unavailable actions, reusing `can_possibly_start` for the verdict and `get_requirements()` for the categorical reason | a second validator, a rules DSL, duplicated eligibility checks, **and widening `get_action_infos_str` — see below** |
| Affordance, **prompt-facing** | `src/classes/actions.py : get_action_infos` / `get_action_infos_str`, consumed by `ai.py:56`, `long_term_objective.py:94`, `roleplay_service.py:329` | **none — leave unchanged** | adding unavailable actions here; it exists to shrink the prompt (`action.py:129-134`) and changing it changes what the LLM chooses |
| Concrete rejection reason | `ActualActionMixin.can_start(**params) -> tuple[bool, str]` (`action.py:242`), evaluated in `Avatar.commit_next_plan` | capture the discarded reason string into `AgentDecision.rejected` at that call site | re-evaluating `can_start` anywhere else, or trying to obtain a reason from `can_possibly_start` (bool-only, 18 overrides) |
| Avatar state over time (adjacent owner) | `src/classes/avatar_metrics.py : AvatarMetrics`, `MetricTag`; `Avatar.record_metrics` (`core.py:418`), invoked from `finalize_step` behind `Avatar.enable_metrics_tracking` | none — keep separate | merging `StateDelta` into `metrics_history`, or reusing `MetricTag` as the `StateDelta.aspect` vocabulary. Boundary: `AvatarMetrics` is an opt-in **periodic full snapshot** of one avatar, drained from the same funnel; `StateDelta` is a **per-event, per-aspect** delta on any owner. `MetricTag` is dormant in production (referenced only by `avatar_metrics.py` and `tests/test_avatar_metrics.py`) and its documented example tag is literally `"breakthrough"` (`docs/specs/avatar-metrics-tracking.md:39`), which overlaps the §8.1 agent flow — so the two must stay explicitly separate rather than drift into one |
| Memory scope | `src/classes/event_query.py : matches_memory_scope` + SQL in `EventStorage.query_page` | reuse | a memory table |
| Propagation / observation | `src/classes/event_observation.py : EventObservation`, `src/classes/event_renderer.py : render_observed_event`, `src/classes/close_relation_event_service.py` | reuse | causal edges doubling as propagation |
| Narrative text | `src/classes/story_event_service.py : StoryEventService` | story events link with `contributed_to`, never as a cause | LLM prose treated as a cause; a second story generator |
| Death cause | `src/classes/death_reason.py : DeathReason`, `src/classes/death.py : handle_death` | emit a `CausalLink` alongside the existing reason string | a parallel death-cause registry |
| Month boundary and persistence | `src/sim/simulator_engine/finalizer.py : finalize_step` | attach causal records to events before `add_event`; keep the month advance here | a causal commit phase separate from `finalize_step` |
| Read API | `src/server/services/game_queries.py`, `game_query_service.py`, `src/server/api/public_v1/query.py` | new query functions in `game_queries.py` + routes in `query.py` | logic in `src/server/main.py` (forbidden by AGENTS.md rule 28/29) |
| Chronicle UI | `WorldJournalPanel.vue`, `web/src/stores/worldJournal.ts`, `web/src/api/modules/event.ts`, `web/src/types/api.ts` | fill the already-declared `focus` / `stories` tabs; add a `why` drill-down | a second journal component, a second event store |
| Pause / failure | `src/server/runtime/session.py : GameSessionRuntime` (`set_paused`, `get_pause_reason`), `src/server/loop/runner.py : GameLoopRunner.run_once` | a new exception distinct from `SimulationStepAborted` propagating to `run_once`, plus a new `get_pause_reason` value — §6.2 | a custom transaction manager, a world-state deep copy per month, **and reusing `SimulationStepAborted`**, which `SimulationPhaseRunner.run` swallows and which already means "reset superseded this step" |
| Test-mode determinism | `src/utils/llm/test_mode_fallbacks.py : resolve_test_mode_task` | register any new task name | a bypass that reaches a real provider |

---

## 4. Execution flow, current and proposed

### 4.1 Current (unchanged by this plan)

The phase contract is **wrapper-based**, and getting this exactly right matters
because Task 3 edits one of the wrappers. `SIMULATION_PHASES` does not hold the
domain functions; it holds thin wrappers defined in the same
`phase_registry.py`. Each wrapper calls the domain function, calls
`ctx.add_events(...)` **itself**, and returns `None`. `finalize_step_phase` is the
only wrapper that returns a value.

```
GameLoopRunner.run_once
  └─ runtime.run_mutation(sim.step)
       └─ SimulationPhaseRunner.run
            ctx = SimulationStepContext.create(world)
            for phase in SIMULATION_PHASES (1..29):
                result = phase.handler(simulator, ctx)   # a wrapper in phase_registry.py
                if awaitable: result = await result      # the wrapper already called
                                                         # ctx.add_events() and returned None
                if phase.reset_check_after: raise_if_reset_requested()
                if phase.name == "finalize_step": return result or []
```

`SimulationPhaseRunner.run` never calls `ctx.add_events`. Concretely, in
`phase_registry.py`:

```python
def discover_pois(simulator, ctx):                    # adds events, returns None
    ctx.add_events(poi.phase_discover_pois(simulator.world, ctx.living_avatars))

def update_city_population(simulator, _ctx):          # adds nothing, DISCARDS ctx
    world_phases.phase_update_city_population(simulator.world)

def finalize_step_phase(_simulator, ctx):             # the only wrapper returning a value
    return finalize_step(ctx)
```

Three wrappers add no events at all: `handle_interactions`,
`update_city_population`, and `update_calculated_relations`. Of these,
`update_city_population` is the only one that names its parameter `_ctx` to mark
the discard — which is exactly why §8.1 has to call out an edit to it.

`finalize_step` (phase 29) then does:

```
dedupe ctx.events by Event.id
append close-relation observations to major non-story events
event_manager.add_event(e) for each final event
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
      result = phase.handler(simulator, ctx)     # same wrapper contract as §4.1
      # the wrapper still calls ctx.add_events() itself; an instrumented wrapper
      # also passes ctx (or ctx.causal) down so the owner can record
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
- `SimulationPhaseRunner.run` and `SIMULATION_PHASES` are untouched: no new phase,
  no re-indexing, no change to the runner's loop.
- `SimulationPhase.handler` keeps its `(simulator, ctx) -> Any` signature and every
  wrapper keeps returning what it returns today.
- **Instrumenting a flow does mean editing that flow's wrapper** when the wrapper
  currently discards `ctx` — see §8.1 for `update_city_population`. This is a
  per-flow, opt-in edit, not a contract change.
- The recorder never calls a domain method. It only accepts records.

---

## 5. Schema drafts and serialization boundaries

### 5.1 `FactKind`

```python
# src/classes/event.py
class FactKind(StrEnum):
    OCCURRENCE = "occurrence"                # something happened (default)
    STATE_TRANSITION = "state_transition"    # a domain-owned value changed
    DERIVED_CONDITION = "derived_condition"  # a condition became true/false
    DECISION = "decision"                    # an agent committed to an intent
```

`Event.fact_kind: FactKind = FactKind.OCCURRENCE`. Orthogonal to `event_type`,
`is_major`, and `is_story`; none of those change meaning. `DECISION` exists because
a `CausalLink` can only target an `Event`; see §5.4 for why that forces it.

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
    relation: CausalRelation = CausalRelation.TRIGGERED_BY
    weight: float = 1.0           # multifactor contribution, 0..1
    note_key: str | None = None   # i18n key, never a rendered sentence
    note_params: dict | None = None
    created_at: float = field(default_factory=time.time)
```

Multifactor causality is expressed as **several links on one effect event**, which
is why `weight` lives on the edge rather than on the event. Direction is always
effect → cause, matching how the `why` query walks ancestors.

An edge can only ever point at an `Event.id`. There is no node type other than
`Event`. That single constraint is what forces the decision design in §5.4.

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

### 5.4 `AgentDecision` — and why a decision must be its own `Event`

Two facts about the current code decide this schema.

1. **A `CausalLink` can only point at an `Event.id`** (§5.2). So if
   `motivated_by` is to have a target, the decision has to be an `Event`. Storing
   the decision as JSON inside some other event's payload makes it unaddressable.
2. **One decision produces N events across M months.** `LLMAI._decide`
   (`src/classes/ai.py`) returns `action_name_params_pairs` — a *list*.
   `Avatar.load_decide_result_chain` turns it into a list of `ActionPlan`s in
   `Avatar.planned_actions`, and `phase_commit_next_plans` →
   `Avatar.commit_next_plan` pops **one per month**. A chain of three plans is
   therefore still being consumed three months later, and each consumed plan can
   emit start, step, and finish events.

So: **a decision is a fact with `fact_kind=DECISION`, carrying its
`AgentDecision` payload, emitted by the recorder at the `phase_decide_actions`
boundary.** Every event later produced by any plan in that chain carries a
`motivated_by` edge to that one decision event.

```python
# src/classes/event.py
class FactKind(StrEnum):
    OCCURRENCE = "occurrence"
    STATE_TRANSITION = "state_transition"
    DERIVED_CONDITION = "derived_condition"
    DECISION = "decision"          # an agent committed to an intent
```

```python
# src/classes/agent_decision.py
@dataclass
class AgentDecision:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    month_stamp: int = 0
    subject_kind: str = "avatar"      # "avatar" | "sect"
    subject_id: str = ""
    source: str = "llm"               # mirrors single_choice.ChoiceSource
    considered_count: int = 0         # how many actions were offered; see §10.7
    chosen_chain: list[dict] = field(default_factory=list)
                                      # [{"action_name": ..., "params": {...}}, ...]
                                      # mirrors ActionPlan.to_dict(), one entry per plan
    thinking: str = ""                # copied from Avatar.thinking
    short_term_objective: str = ""    # copied from Avatar.short_term_objective
    rejected: list[dict] = field(default_factory=list)
                                      # [{"action_name", "params", "reason"}] captured
                                      # where can_start(**params) actually runs — see §5.5
```

Cardinality rules, stated so Task 3 and Task 4 cannot get them wrong:

- **No `result_event_id`.** The decision → results direction is not stored on the
  decision. It is read back by querying `event_causal_links` for
  `cause_event_id = <decision event id> AND relation = 'motivated_by'`, which is
  what `idx_event_causal_links_cause_event_id` exists for. That is naturally
  one-to-many and needs no schema change as the chain unfolds.
- **The decision event id must outlive the month.** `Avatar` gains a runtime-only
  `current_decision_event_id: str` set by `load_decide_result_chain` and read by
  the recorder when a plan from that chain produces an event in a later month. It
  is runtime state, cleared on load/reset like the roleplay session
  (AGENTS.md rule 34), so a decision chain that spans a save boundary simply loses
  its `motivated_by` edges rather than dangling.
- `rejected` is populated at the `commit_next_plan` boundary, not at
  `phase_decide_actions`, because that is the only place `can_start(**params)`
  runs — see §5.5.

`AgentDecision` is an **audit record**. Nothing in the simulator may read it back
to make a decision. `thinking` and `short_term_objective` stay owned by `Avatar`;
the record copies them.

**Consequence for the timeline, which must not be glossed over.** Decision events
are real rows in `events`, so without a filter they would appear in the existing
World Journal timeline and in `/api/v1/query/events`. That is a visible
behavioural change. Required mitigation, all in Task 4:

- `EventQuery` (`src/classes/event_query.py`) gains
  `include_decisions: bool = False`; `EventStorage._query_direct_page` and the
  observed branch of `query_page` add
  `(e.fact_kind IS NULL OR e.fact_kind != 'decision')` unless it is set.
  `EventManager.query_page`'s in-memory branch mirrors it.
- Decision events are written with `is_major=False` and `is_story=False`, so
  `EventStorage.cleanup(keep_major=True)` prunes them like any minor event.
- `tests/test_api_events.py` must assert the default event page is unchanged by
  the presence of decision events.

Volume: `phase_decide_actions` only decides for avatars with no current action and
no plans, so the rate is roughly *(living avatars) / (average chain length)* new
decision events per month — tens, not thousands, and prunable.

### 5.5 Rejections and the two affordance layers

`Action` exposes two different eligibility checks at two different layers, and the
causal design must not confuse them:

| Check | Signature | Where it runs | Reason available? |
|---|---|---|---|
| `Action.can_possibly_start` (`src/classes/action/action.py:129`) | `(self) -> bool` | `get_action_infos` (`src/classes/actions.py`), before params exist | **No** — bool only, and 18 subclasses override it |
| `ActualActionMixin.can_start` (`action.py:242`) | `(self, **params) -> tuple[bool, str]` | `Avatar.commit_next_plan` (`action_mixin.py`), with concrete params | **Yes** — the string is produced and currently only logged |

Therefore:

- `AgentDecision.rejected` is filled **only** from `commit_next_plan`, where the
  `can_start` reason string exists and is today discarded by a
  `logger.warning(...)` + `continue`.
- The categorical "this action is impossible for you at all" reason cannot come
  from `can_possibly_start`. It comes from the action's own declared requirement
  text, `Action.get_requirements()` / `REQUIREMENTS_ID`
  (`action.py:115-119`) — an existing, localized, action-owned string. It may be
  `""` for actions that never set `REQUIREMENTS_ID`; the affordance DTO must
  tolerate that rather than inventing a reason.
- Changing `can_possibly_start` to return a reason is explicitly **out of scope**:
  18 subclasses override it (`set_formation`, `educate`, `temper`,
  `devour_people`, `breakthrough`, `catch`, `take_treasure`, `eat_mortals`,
  `respire`, `plunder_people`, `dig_grave`, `sect_mission`, `govern`,
  `move_to_poi`, `meditate`, `help_people`, `inflict_gu`, and the base), and it
  would be a signature break for no causal gain.

### 5.6 Persistence

#### 5.6.1 New `Event` fields

`Event` (`src/classes/event.py`) gains exactly three fields. The two persisted ones
are ordinary compared fields; the runtime mirror copies the
`observations` treatment verbatim so `Event` equality, `repr`, and logging are
unaffected:

```python
    # persisted, in events.fact_kind
    fact_kind: FactKind = FactKind.OCCURRENCE
    # persisted, in events.causal_payload; deltas + at most one decision
    causal_payload: dict[str, Any] | None = None
    # runtime-only mirror, persisted into event_causal_links by EventStorage
    causal_links: list["CausalLink"] = field(default_factory=list, repr=False, compare=False)
```

`causal_payload` is the single home for `StateDelta` and `AgentDecision`:

```python
{
  "deltas":   [ <StateDelta as dict>, ... ],   # 0..n, from the recording owners
  "decision": <AgentDecision as dict> | None,  # only on a fact_kind=DECISION event
}
```

`StateDelta.event_id` / `AgentDecision.id` are kept inside those dicts, so the
payload is self-describing when read back out of a save file.

#### 5.6.2 `events` columns

The existing `subject_snapshots` column shows the real pattern, and it is
**two-sided**: the column is declared inside `CREATE TABLE IF NOT EXISTS events`
(`event_storage.py:100`) *and* backfilled by the `PRAGMA table_info(events)` guard
(`event_storage.py:151-156`). Both halves are required — the `CREATE TABLE` for a
fresh database, the guard for one created before this change. Implementing only the
`ALTER TABLE` produces a schema that works on upgraded databases and fails on new
ones.

Inside `CREATE TABLE IF NOT EXISTS events (...)`:

```sql
    fact_kind TEXT,          -- NULL == "occurrence"
    causal_payload TEXT,     -- JSON: {"deltas": [...], "decision": {...} | null}
```

And in the existing guard block, extending the same `columns` set check:

```sql
ALTER TABLE events ADD COLUMN fact_kind TEXT;
ALTER TABLE events ADD COLUMN causal_payload TEXT;
```

A `fact_kind` index is deliberately **not** added: the decision filter from §5.4 is
a low-selectivity predicate applied on top of the existing
`idx_events_month_stamp` ordering, and a second index on `events` would slow the
per-event insert in `add_event`.

#### 5.6.3 The `event_causal_links` table

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
  `causal_payload`; links go in as a nested `causal_links` list on the event dict.
  This keeps `EventsSection` / `EventsLoadSection` working without a new save
  section, and the 1000-event JSON cap still applies. The SQLite file remains the
  authority — the JSON copy is a fallback path only used when the DB is empty.
  `Event.from_dict` must default `fact_kind` to `OCCURRENCE` and
  `causal_payload` to `None` via `data.get(...)`, matching how every other field
  there already tolerates absence.

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
writer to `EventManager` and the sole place that advances `world.month_stamp`.

### 6.2 Abort-before-mutate already exists; only the pause is missing

The half of this that is already true today, and must not be reinvented:
`LLMAI._decide` calls `asyncio.gather(*tasks)` **without** `return_exceptions`, so
a provider or parse failure that survives the client's own retries
(`call_llm_json`, `CONFIG.ai.max_parse_retries = 3`, which raises `LLMError` after
exhausting them) propagates straight out of phase 4. `finalize_step` never runs,
`ctx.events` are discarded, and `world.month_stamp` is not advanced. The month
boundary is therefore *already* intact on a required-decision failure.

What is missing is only the pause: `GameLoopRunner.run_once` catches bare
`Exception`, logs `"Game loop error: ..."`, and proceeds to the next tick, so the
world retries the same month forever without telling anyone.

**`SimulationStepAborted` must not be reused for this.** It means exactly one
thing today — "a lifecycle command (reset) superseded this step" — which is a
*normal* outcome that must not pause. And `SimulationPhaseRunner.run` catches it
itself:

```python
except SimulationStepAborted:
    return []
```

A required-decision failure routed through it would surface to `run_once` as a
*successful* step with zero events: no pause, no reason, not even a log line.
That is strictly worse than today.

So the mechanism is a distinct exception that is deliberately **not** caught by
`phase_runner`:

1. **New exception**, e.g. `RequiredDecisionFailed`, defined next to
   `phase_decide_actions` in `src/sim/simulator_engine/phases/actions.py` and
   **not** a subclass of `SimulationStepAborted`. Because
   `SimulationPhaseRunner.run` only has `except SimulationStepAborted`, it
   propagates untouched through `run()`, `Simulator.step()`, and
   `GameSessionRuntime.run_mutation` into `GameLoopRunner.run_once`. No change to
   `phase_runner.py` is needed.
2. **`GameLoopRunner.run_once` gains an `except RequiredDecisionFailed` clause
   before its existing `except Exception`**, which calls
   `runtime.set_paused(True)` and records the reason.
3. **`GameSessionRuntime`** gains `set_failure_pause(reason: str)` writing a new
   `pause_reason_override` state key, and `get_pause_reason` returns that key
   first, before the existing `roleplay_*` and `paused` branches. New value:
   `required_decision_failed`. It is cleared by `set_paused(False)`,
   `reset_to_idle`, and `mark_pending_initialization`, alongside the keys those
   already reset. The value reaches the client through the unchanged
   `/api/v1/query/runtime/status` route.
4. **Resuming re-runs the same month** from phase 1.

### 6.3 What counts as a failure, and what does not

This distinction is the whole safety of the gate, because `LLMAI._decide`
currently collapses three different situations into one `continue`
(`src/classes/ai.py`):

```python
if not res or avatar.name not in res:
    continue
...
if not pairs:
    continue          # Skip if no valid actions found
```

Definitions Task 6 must implement:

| Situation | Detected how | Classification |
|---|---|---|
| Provider/transport failure, or parse failure after `max_parse_retries` | `LLMError` / `ParseError` / `ProviderCallError` (`src/utils/llm/exceptions.py`) escapes `call_llm_with_task_name` | **Required failure → pause** |
| Response parsed, but the avatar's key is absent or `pairs` is empty | the two `continue` branches above, with no exception | **Valid empty decision → skip, do not pause** (today's behaviour, unchanged) |
| Test mode | `resolve_test_mode_task("action_decision", ...)` returns empty pairs and never raises | **Valid empty decision** — rule-based runs must never pause |

Consequences:

- Task 6 must **not** add `return_exceptions=True` to the `asyncio.gather` in
  `_decide` without then re-raising: swallowing exceptions there would convert a
  required failure into an indistinguishable empty decision and defeat the gate.
  If per-avatar isolation is wanted, collect the exceptions and raise
  `RequiredDecisionFailed` once with the failing avatar ids attached.
- One escaped exception is enough to pause. Retries already happened inside the
  LLM client, so by the time an exception escapes, retrying the month
  automatically would just loop.
- `long_term_objective`, `nickname`, `story_teller`, `backstory`,
  `random_minor_event`, `sect_thinker`, and the `single_choice` tasks stay
  **optional**: their current skip-on-failure behaviour is unchanged, and none of
  them may pause the world.

### 6.4 The residue, stated honestly

Failing at phase 4 means phases 1–3 already ran, and their in-memory mutations
survive in the live `World` even though no event was persisted. Their side effects:

| Phase | Handler | Side effect | Safe to re-run? |
|---|---|---|---|
| 1 | `phase_update_perception_and_knowledge` | `avatar.known_regions.add(...)` | Yes — set union, idempotent |
| 1 | same handler | `avatar.occupy_region(region)` | **No** — a real state change whose describing `Event` would be discarded |
| 2 | `phase_long_term_objective_thinking` | sets the avatar's long-term objective | Yes — overwritten on re-run |
| 3 | `phase_process_gatherings` | gathering state in `GatheringManager` | Not verified for idempotency |
| 4 | `phase_decide_actions` → `gateway.before_ai_decision` | may set `roleplay_auto_paused=True` and a `pending_request` before any LLM call | Needs confirmation — see below |

The failure point is fixed at phase 4, where the `action_decision` calls actually
happen; it is not relocated. So three follow-ups belong to Task 6:

1. **`occupy_region` (row 2).** Split
   `phase_update_perception_and_knowledge` so perception refresh (pure, idempotent)
   stays at index 1 and region claiming moves to its own phase **after** phase 4.
   Otherwise a failed month can leave a real, permanent occupation whose describing
   `Event` was discarded — an unexplained state change, which is precisely what
   this whole plan exists to eliminate. This also fixes a genuine single-owner
   violation (a perception phase owning territory acquisition), and it is the
   reason §11.3 amends the plan. If a reviewer judges the split out of scope, the
   alternative is to document the unrecorded occupation as a known gap; silently
   tolerating it is not acceptable.
2. **Gathering state (row 4).** Not rolled back, and its idempotency under a
   re-run is unverified. Task 6 must either confirm `GatheringManager` tolerates a
   re-run or move `phase_process_gatherings` after phase 4 as well.
3. **Roleplay state (row 5).** `phase_decide_actions` calls
   `gateway.before_ai_decision(world)` *before* any LLM work, and that call can
   already set `session["status"] = "awaiting_decision"` plus
   `runtime.set_roleplay_auto_paused(True)`
   (`src/sim/runtime_capabilities.py : RuntimeDecisionBoundaryGateway`). If the
   required-decision failure for *other* avatars then fires,
   `is_paused` and `roleplay_auto_paused` are both set, and
   `get_pause_reason` must resolve them in a defined order — §6.2 puts
   `pause_reason_override` first, so `required_decision_failed` wins. Task 6 must
   confirm that resuming clears the failure pause without stranding a legitimate
   `pending_request`, per AGENTS.md rules 34–35 (roleplay state is runtime-only and
   pauses only at decision boundaries).

### 6.5 Test mode

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
- `"decision"` is populated by following the `motivated_by` edge to its
  `fact_kind=DECISION` event and reading that event's
  `causal_payload["decision"]` (§5.4). The queried event does not carry the
  decision itself. Because a decision event is a normal `Event`, this route must
  resolve it even though the default event page hides it — the traversal reads by
  id and is not subject to the §5.4 timeline filter.

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
     `motivated_by` the `fact_kind=DECISION` event emitted at the
     `phase_decide_actions` boundary (§5.4), `enabled_by` the cultivation state,
     plus a `StateDelta` on the avatar's realm. Because
     `Avatar.load_decide_result_chain` can enqueue a chain, the `motivated_by`
     target is resolved through `Avatar.current_decision_event_id`, which may have
     been set in an earlier month.
   - **non-agent flow**: `phase_update_city_population`
     (`phases/world.py:199`) — today it changes `CityRegion.population` and emits
     nothing. It gains a `fact_kind=STATE_TRANSITION` event with a `StateDelta`
     for `aspect="population"`. This is the clearest proof that causality is not
     agent-centric. **Concrete edit required:** the wrapper
     `update_city_population(simulator, _ctx)` in
     `src/sim/simulator_engine/phase_registry.py` currently discards its context
     and the domain function returns `None`. Task 3 must make the wrapper accept
     and forward `ctx`, and have `phase_update_city_population` return its events —
     per §4.2 this is a per-flow opt-in edit, not a change to the phase contract.
4. Affordance exposure, in **two separate places** (§5.5):
   - a new player/API-facing `build_action_affordances(avatar)` in
     `src/classes/actions.py`, listing available and unavailable actions with
     `get_requirements()` as the categorical reason;
   - `commit_next_plan` rejections captured into `AgentDecision.rejected` with the
     real `can_start(**params)` reason instead of being logged and dropped.
   `get_action_infos` / `get_action_infos_str` and their three prompt callers stay
   **untouched**, so no prompt grows and no LLM option set changes.
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
| Affordances (player/API) | `tests/test_action_can_possibly_start.py`, `tests/test_action_param_options.py` | the new affordance builder lists unavailable actions with `get_requirements()` reasons; `param_options.value` stays executable (AGENTS.md rule 3) |
| Affordances (prompt path unchanged) | `tests/test_ai.py`, `tests/test_action_can_possibly_start.py` | `get_action_infos_str` output is byte-identical before and after Task 4 — guards the M2 regression risk for all three prompt callers |
| Decision events | `tests/test_api_events.py`, `tests/test_event_storage.py` | `fact_kind='decision'` events are excluded from the default event page and from `get_world_journal` activity counters unless `include_decisions` is set; `cleanup(keep_major=True)` prunes them |
| Decision cardinality | `tests/test_ai.py`, `tests/test_simulator.py` | a multi-plan chain produces `motivated_by` edges from events in later months back to the one decision event; `Avatar.current_decision_event_id` is cleared on load/reset |
| Decision audit | `tests/test_ai.py` | the audit reflects what `LLMAI._decide` returned; `can_start` rejections land in `rejected` |
| Failure | `tests/test_loop_runtime.py`, `tests/test_game_session_runtime.py`, `tests/test_llm_failures.py` | an `LLMError` escaping `_decide` leaves `month_stamp` unadvanced, persists no events, and pauses with `required_decision_failed`; a `SimulationStepAborted` (reset) still does **not** pause; an empty-but-valid decision does **not** pause |
| API | `tests/test_api_events.py`, `tests/test_public_api_v1.py` | `why` response shape, depth clamp, `truncated`, `pruned`, and `ok_response` envelope |
| Test mode | `tests/test_llm_test_mode.py` | no new unregistered LLM task, and a rule-based run never triggers the failure pause (`resolve_test_mode_task` returns empty pairs without raising) |
| Frontend | `web/src/__tests__/components/game/panels/WorldJournalPanel.test.ts`, `web/src/__tests__/components/mobile/MobileDashboard.test.ts` | the two new tabs render, paginate, and the `why` drill-down opens; lazy-loaded modals use `{ immediate: true }` watchers (AGENTS.md rule 38) |
| i18n | `tests/test_frontend_locales.py`, `tests/test_backend_locales.py` | new keys exist for `zh-CN`; no Chinese `msgid` |

Commands: `pytest` (or `pytest -n 8`), `cd web && npm run test && npm run type-check`.

## 10. Performance risks

1. **Event volume from state transitions.** Instrumenting
   `phase_update_city_population` adds one event per city per month where there
   were none. With `CONFIG.save.max_events_to_save` at `1000`, these can crowd the
   JSON save tail. Mitigation: emit the transition event only when the delta
   crosses a configured threshold, and keep it `is_major=False` so
   `cleanup(keep_major=True)` prunes it.
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
6. **Event volume from decision events (§5.4).** One new event per deciding
   avatar per decision — roughly *(living avatars) / (average chain length)* per
   month. Bounded the same way: `is_major=False`, prunable by `cleanup`, and hidden
   from the default event page by the `include_decisions` filter. The filter is a
   correctness requirement, not just cosmetics: without it the World Journal
   activity counters in `get_world_journal` would silently inflate.
7. **`AgentDecision` payload size.** The original draft had
   `considered: list[str]` — the full offered action catalogue, per avatar, per
   month, JSON-serialized into `causal_payload` and dumped into the save. With 52
   registered actual actions (`register_action(actual=True)`: 39 in
   `src/classes/action/__init__.py`, 13 in
   `src/classes/mutual_action/__init__.py`) that is on the order of 700 bytes of
   pure redundancy per decision. §5.4 therefore stores `considered_count: int`
   instead: the audit value is "how many options existed", and the interesting part
   — what was rejected and why — is already in `rejected`, which is bounded by the
   length of the plan chain. `chosen_chain` is bounded the same way.
8. **No new LLM calls.** `phase_decide_actions` already issues one
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

Four. Everything else in the plan survived the audit.

### 11.1 `fact_kind` is a new field, not a reinterpretation of `event_type`

The plan lists `fact_kind` under "extend `Event`" without saying how it relates to
what is there. `Event.event_type` is already load-bearing: `finalizer.py` keys
`special_major_kinds` off it, `close_relation_event_service` maps it to bond
labels, and `background_npc/service.py` sets it. Overloading it would break those.
`fact_kind` is therefore additive and orthogonal.

### 11.2 `SimulationChangeSet` is not justified; use the recorder + `ActionResult.payload`

Direct evidence: `SIMULATION_PHASES` holds thin wrappers defined in
`phase_registry.py`; each wrapper calls `ctx.add_events(...)` **itself** and
returns `None`, `finalize_step_phase` is the only one that returns a value, and
`SimulationPhaseRunner.run` never calls `ctx.add_events` at all. `ActionResult`
already carries a free-form `payload`. Introducing a new envelope type would
require rewriting all 29 wrappers and every `Action.step` implementation for zero
behavioural gain, and would make "recording absent ⇒ behaviour identical" much
harder to prove. Replaced by: a passive `CausalRecorder` on
`SimulationStepContext`, drained by `finalize_step`, plus optional keys in the
existing `ActionResult.payload`. Instrumenting a specific flow does still mean
editing that flow's wrapper when it discards `ctx` — see §4.1 and §8.1 for
`update_city_population`.

### 11.3 "Checkpoint and restore the month boundary" becomes "the month boundary already holds; add the pause"

Direct evidence: `Simulator.step()` has no transaction and no snapshot;
`save_game` is the only snapshot and it copies the entire events SQLite file. A
literal per-month checkpoint/restore is not affordable and would be a new
subsystem.

It is also not needed. `LLMAI._decide` calls `asyncio.gather` without
`return_exceptions`, so a required-decision failure already propagates out of
phase 4, `finalize_step` never runs, and `world.month_stamp` is never advanced.
The abort-before-mutate property exists today; the *pause* is what is missing,
because `GameLoopRunner.run_once` catches bare `Exception` and continues.

Task 6 is therefore: raise a dedicated exception (**not** `SimulationStepAborted`,
which `SimulationPhaseRunner.run` catches itself and which legitimately means
"reset superseded this step"), let it propagate to `GameLoopRunner.run_once`, and
pause there with a `required_decision_failed` reason. Plus the residue follow-ups
in §6.4: split `phase_update_perception_and_knowledge` so region claiming moves out
of the perception phase, settle `phase_process_gatherings` idempotency, and confirm
the roleplay gateway interaction.

### 11.4 A decision must be an `Event`, and its cardinality is one-to-many

Direct evidence: a `CausalLink` addresses an `Event.id` and nothing else, so an
`AgentDecision` stored only as JSON on some other event cannot be the target of the
`motivated_by` edge the first vertical slice is defined by. And `LLMAI._decide`
returns a *list* of action/param pairs, which `load_decide_result_chain` enqueues
as multiple `ActionPlan`s that `commit_next_plan` consumes one per month — so one
decision legitimately produces many events across many months. The plan's
`AgentDecision` bullet is therefore refined: a decision is emitted as its own
`fact_kind=DECISION` `Event`, and the decision → results direction is read from
`event_causal_links` rather than stored on the record. See §5.4.

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

---

## 13. Task 6: what was actually delivered

Section 6 above is the design; this records the as-built shape and the one
finding that went beyond "confirm idempotency."

1. **`RequiredDecisionFailed`** lives next to `phase_decide_actions`
   (`src/sim/simulator_engine/phases/actions.py`), is not a
   `SimulationStepAborted` subclass, and is raised by wrapping the single
   `await llm_ai.decide(world, avatars_to_decide)` call in a `try`/`except
   Exception`. Nothing else in that function path can legitimately raise:
   a parsed-but-empty response and rule-based test mode both return
   normally with an empty result (§6.3). No `return_exceptions=True` was
   added to `LLMAI._decide`'s `asyncio.gather` — it still fails fast on the
   first escaping exception, so `avatar.load_decide_result_chain` is never
   called for a failed batch (abort-before-mutate holds unchanged).
2. **`GameSessionRuntime.set_failure_pause(reason)`** sets `is_paused=True`
   and a new `pause_reason_override` state key, read first by
   `get_pause_reason()` ahead of the roleplay and plain-`paused` branches.
   It is cleared by `set_paused(False)`, `reset_to_idle`, and
   `mark_pending_initialization` — the same three call sites that already
   clear roleplay runtime state. Clearing it does **not** touch
   `roleplay_auto_paused` or the roleplay session: if roleplay was also
   waiting on a decision boundary, resuming from a
   `required_decision_failed` pause correctly falls back to
   `roleplay_waiting_decision` instead of fully unpausing.
   `GameLoopRunner.run_once` gets an `except RequiredDecisionFailed` clause
   ahead of its existing `except Exception`, calling
   `runtime.set_failure_pause("required_decision_failed")`.
3. **Residue (a), region claiming.** `phase_update_perception_and_knowledge`
   now only refreshes `known_regions` (a pure set union — idempotent).
   Occupation moved to a new phase, `phase_claim_ownerless_regions`
   (`src/sim/simulator_engine/phases/world.py`), registered as
   `SIMULATION_PHASES` index 4, immediately after `decide_actions` (index
   3) and before `commit_next_plans`. Both phases independently recompute
   "regions observed this tick" from the avatar's current position and
   observation radius (factored into `_observed_regions_this_tick`) rather
   than reusing accumulated `known_regions` — avatar position cannot change
   between phase 1 and phase 4 within one step (movement happens later, in
   `execute_actions`), so this reproduces the original "passed by and
   occupied" semantics exactly, while making a same-month retry safe: a
   second call over an unchanged world state claims nothing new.
4. **Residue (b), gatherings — upgraded from "confirm" to "move."** Reading
   the three registered `Gathering` subclasses showed re-run is **not**
   safe for two of them: `Tournament.is_start` re-fires unconditionally on
   every January of a matching year with no state marking it as already
   run, and `SectTeachingConference.is_start` re-picks a (possibly
   different) sect each call with no such guard either — both would
   literally re-run a full gathering (battles, teaching, relation deltas)
   a second time on a same-month retry. `Auction` happens to self-limit
   because `sold_item_count` is a derived property that `execute` drains,
   but that is incidental, not a documented invariant. `HiddenDomain`
   updates its own cooldown state inside `is_start` itself specifically to
   guard repeated calls, which is the closest thing to a real precedent for
   "idempotent by design" — and even that guard only prevents a *second*
   opening, not the fact that the first opening's loot/events already ran
   in-memory during the failed attempt. Given this, `process_gatherings`
   was moved (not left in place with a "confirmed safe" note) to
   `SIMULATION_PHASES` index 5, after `claim_ownerless_regions` and before
   `commit_next_plans` — the same reasoning as region claiming.
5. **Behavioral consequence of both moves, stated explicitly.** Avatars now
   decide their month's actions *before* any gathering or region-claim
   outcome from that same month is known to them, whereas previously
   gatherings (and the region-claim side effect) ran first. This is a
   deliberate trade-off: the alternative is an irreversible mutation sitting
   before the point where a required-decision failure can abort the step,
   which is exactly the hazard this task exists to remove. `is_in_major_action`
   / `can_join_gathering` eligibility is unaffected either way, since it
   reads `Avatar.current_action`, which `commit_next_plans` (still after
   both moved phases) is what actually sets.
6. **Residue (c), roleplay interaction — confirmed, not changed.**
   `RuntimeDecisionBoundaryGateway.before_ai_decision` can set
   `roleplay_auto_paused=True` and a `pending_request` before any LLM call
   in the same `phase_decide_actions` invocation that later fails for a
   *different* avatar. Because `set_failure_pause` never mutates
   `roleplay_auto_paused` or the roleplay session, that pending request
   survives a `required_decision_failed` pause untouched, and precedence
   in `get_pause_reason()` resolves deterministically
   (`pause_reason_override` first). See
   `tests/test_game_session_runtime.py::test_resuming_from_failure_pause_falls_back_to_a_still_pending_roleplay_wait`.
7. **No new phase-index churn beyond this.** `SIMULATION_PHASES` grew from
   29 to 30 entries (one new phase, `claim_ownerless_regions`); every other
   phase kept its relative order and shifted index by exactly the same
   amount. `tests/test_backend_phase4_architecture.py`'s sequential-index
   and first/last-name assertions are index-count-agnostic and still hold.
8. **Measurements.** A 3-avatar, 6-month smoke run under the default
   "valid empty decision" mock produced 3 events total (background world
   phases only — no decisions, no gatherings, no region claims in that
   fixture); a 60-hop linear causal chain (past the depth=5 clamp) resolved
   through `get_event_causal_detail` in well under a millisecond. See
   `tests/test_causal_kernel_smoke.py`.
