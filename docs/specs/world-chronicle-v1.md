# World Chronicle v1

## Objective

Add an append-only **Chronicle** tab to the World Journal. An LLM narrates closed batches of factual world events, while structured references keep every paragraph and important claim traceable to persisted events. Clicking an important claim opens a causal dossier; clicking an avatar, sect, or region opens its existing detail view.

## Product behavior

- Chapters are immutable publications. Opening the panel never regenerates old text.
- A chapter is published once for the pending event window when either:
  - the current month contains at least one `is_major=True` and `is_story=False` event; or
  - three world months have elapsed since the last published chapter.
- At most one chapter is published per simulated month. A major event and the three-month deadline in the same month produce one chapter with trigger `major_event`.
- For worlds without chapters, the first generation considers at most the current month and the two preceding months. This bootstraps an existing production world without rewriting its full history.
- Story events are excluded as evidence because they are already LLM prose. Factual events, including decision events, may be evidence.
- If no factual source event exists, no empty chapter is published.
- Provider failure or invalid structured output does not fail the simulation and does not advance the publication window. The pending facts are retried on a later month.
- In `test_mode`, the registered deterministic `chronicle_chapter` fallback returns valid structured output and never reaches a real provider.
- `chronicle_chapter` is routed through `LLMMode.FAST`. With the production OAuth/Codex CLI profile, this selects `fast_model_name=gpt-5.6-luna` and invokes the already authenticated CLI; the Chronicle service does not hardcode provider credentials or bypass task routing.

## Authority boundary

- `Event`, domain state, and causal records remain the source of truth.
- The LLM receives a bounded, structured candidate set and may only cite IDs from that set.
- The LLM narrates and labels a claim as `fact` or `inference`; it never creates an `Event`, causal link, state delta, war, relationship, or other domain state.
- Every paragraph has validated `source_event_ids`.
- Every clickable event claim has validated `source_event_ids`. A factual event anchor also has a validated `target_id`; an inference has no factual target.
- Invalid, duplicate, empty, or out-of-scope references reject the whole draft. We do not silently publish partially auditable prose.

## Domain model

`src/classes/chronicle.py` owns JSON-pure immutable values:

```python
ChronicleTrigger = Literal["major_event", "max_interval"]
ChronicleClaimKind = Literal["fact", "inference"]
ChronicleReferenceKind = Literal["avatar", "sect", "region", "event"]

@dataclass(frozen=True, slots=True)
class ChronicleReference:
    id: str
    kind: ChronicleReferenceKind
    label: str
    target_id: str | None
    claim_kind: ChronicleClaimKind | None
    source_event_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ChronicleSegment:
    text: str
    reference: ChronicleReference | None = None

@dataclass(frozen=True, slots=True)
class ChronicleParagraph:
    segments: tuple[ChronicleSegment, ...]
    source_event_ids: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ChronicleChapter:
    id: str
    start_month_stamp: int
    end_month_stamp: int
    trigger: ChronicleTrigger
    title: str
    paragraphs: tuple[ChronicleParagraph, ...]
    source_event_ids: tuple[str, ...]
    created_at: float
```

All classes provide `to_dict()` and `from_dict()` and reject malformed enum values or structurally empty chapters.

## Persistence

Chapters live in the same SQLite file as `EventStorage`, in their own table:

```sql
CREATE TABLE IF NOT EXISTS chronicle_chapters (
    id TEXT PRIMARY KEY,
    start_month_stamp INTEGER NOT NULL,
    end_month_stamp INTEGER NOT NULL UNIQUE,
    trigger TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chronicle_chapters_end
ON chronicle_chapters(end_month_stamp DESC, id DESC);
```

There is no foreign key to events. Event cleanup may prune evidence, but it must never delete or rewrite a chapter. Storage exposes append, latest, and descending cursor pagination. Duplicate `end_month_stamp` returns `False` without overwriting the existing payload.

Because save/load already copies the complete event SQLite database, the Chronicle follows the established backup and restore path without a parallel JSON copy.

## Generation pipeline

An async simulation phase `generate_chronicle` runs after event appraisals and before `finalize_step`:

1. Read the latest chapter.
2. Build the pending month window.
3. Combine persisted events in that window with `ctx.events`, deduplicated by event ID.
4. Exclude `is_story=True`; order deterministically by `(month_stamp, created_at, id)`.
5. Decide the trigger. `major_event` takes precedence over `max_interval`.
6. Bound the prompt candidates while always retaining current-window major events and their causal evidence.
7. Call task `chronicle_chapter` using the current content locale template.
8. Validate paragraph sources, references, entity targets, factual targets, and claim kinds against the supplied candidates/world.
9. Put the accepted chapter in `SimulationStepContext.pending_chronicle_chapter`.
10. `finalize_step` persists factual events first, then appends the chapter, and then advances the month.

The generation phase catches only expected LLM/parse/validation failures, logs a warning, and returns without a chapter. Unexpected programming errors continue to fail fast.

`static/config.yml` declares `chronicle_chapter: "fast"`. The normal model remains available to decisions and other higher-judgment tasks; Chronicle narration intentionally uses the cheaper Luna fast model configured by the active OAuth profile.

## Query API

Only read operations are added:

```text
GET /api/v1/query/world/chronicle?cursor=<end_month_stamp>&limit=20
GET /api/v1/query/world/chronicle/{chapter_id}/anchors/{anchor_id}/dossier?depth=3&limit=40
```

The list response is `{chapters, next_cursor, has_more}` with a server limit clamp of 1–50.

The dossier endpoint only accepts `event` references. It returns the anchor, the focal event when factual, a chronological deduplicated sequence made from explicit evidence and their causal ancestors, pruned source IDs, and `truncated`. Each surviving sequence event keeps its event ID so the existing Why query can be opened.

The dossier is an explanation of persisted evidence, not a mutation and not another LLM call.

## Frontend

- Add `chronicle` to `WorldJournalTab` without removing Now, Focus, Stories, or Timeline.
- `ChronicleView.vue` renders paginated chapters and safe Vue text segments; never use `v-html` or name-matching heuristics.
- Avatar, sect, and region references call the existing `uiStore.select()` path.
- Event fact/inference references open `ChronicleDossierDrawer.vue` in the World Journal.
- Facts and inferences have distinct subtle badges. Inferences explicitly say that they are the chronicler's interpretation.
- Every paragraph exposes a compact source count. The dossier shows its causal sequence and a Why action for every surviving event.
- Loading, empty, error, truncated, and pruned states remain visible.
- Only new `zh-CN` UI keys are required in this phase. The generation template must exist for `zh-CN` and `pt-BR`, because production content is narrated in pt-BR.

## Verification

- Unit: immutable serialization, append-only SQLite behavior, cursor pagination, three-month boundary, major precedence, source/entity validation, invalid draft rejection.
- Integration: simulator facts to chapter to API to dossier; cleanup leaves pruned sources; database save/load retains chapters.
- Test mode: `chronicle_chapter` returns parseable content without a provider call.
- Frontend: tab, pagination, safe segments, entity navigation, dossier, Why, races, and error/empty/pruned states.
- Regression: existing World Journal, causal queries, event storage, simulator, population threshold WIP, frontend type-check, and production build.
