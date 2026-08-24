# Personal Appraisal and Sect Politics

## Purpose

This slice proves causal flow across simulation scales without scripting a composed scenario:

```text
interpersonal event
  -> persistent personal interpretation
  -> leader decision context
  -> institutional action
  -> auditable causal chain
```

The causal kernel observes and links existing systems. It is never a second execution path. Every concept has one domain owner; existing owners are extended instead of duplicated.

## Domain boundaries

- `Event` remains historical world truth.
- `EventObservation` records who observed or knew the event.
- `EventAppraisal` records what a direct participant personally took from it.
- Existing relationship state remains the current social summary.
- `AgentDecision` remains the auditable choice made by an agent or institution.
- The sect remains the owner of diplomacy. Its current patriarch's memories are context, not a numeric modifier or compulsory outcome.

## EventAppraisal

```text
id: str
event_id: str
appraiser_avatar_id: int
focus_avatar_id: int
personal_importance: float [0, 1]
valence: float [-1, 1]
persistence: float [0, 1]
primary_emotion: EmotionType
summary: str, max 240 characters
source: llm | rule
```

An appraisal is immutable. A later reconciliation, betrayal, rescue, or loss creates another appraisal rather than rewriting history. Positive and negative appraisals may coexist.

Its current influence is calculated at query time:

```text
age_decay = 0.5 ** (age_months / 120)
effective_weight = personal_importance * (
    persistence + (1 - persistence) * age_decay
)
```

## Persistence

`EventStorage` owns a new `event_appraisals` table:

- foreign key to the source event with `ON DELETE CASCADE`;
- uniqueness per event, appraiser, and focus;
- indexes for appraiser and focus queries;
- queries support character, focus, minimum effective weight, and limit;
- appraisals are not duplicated inside avatar JSON;
- old databases receive an empty table and no synthetic backfill;
- normal save/load database copying preserves the table.

## Monthly generation

An asynchronous appraisal phase runs immediately before the finalizer. It only inspects important, non-story interpersonal events from the current month with exactly two structured participants.

The first allowlist covers battle results and kills, romantic bonds and rejections, sworn-sibling bonds and rejections, and master-disciple bonds. Producers must expose participant IDs through structured `render_params`; IDs are never inferred from prose.

Only living, named, direct participants receive appraisals. A single monthly `event_appraisal` batch uses the fast model and accepts at most 16 AI candidates. Test mode, overflow, malformed output, missing candidates, and provider failure use a deterministic per-candidate rule fallback. Appraisal failure never pauses or rolls back the month.

The model echoes engine-issued candidate IDs. Numeric values are clamped, emotion is validated against the existing enum, and summaries are capped at 240 characters. Locale templates follow the existing resolver and include the production pt-BR path.

## Sect decision context

For each diplomacy target, the sect decider receives the current living patriarchs and up to five appraisals from the local patriarch about the target patriarch. Only appraisals with effective weight at least `0.15` are eligible. Context includes appraisal ID, source event and date, emotion, summary, valence, and current weight.

If either sect has no living patriarch, personal influence is absent. Appraisals never directly alter sect relationship scores. Strategy, doctrine, military power, territory, finances, and war weariness remain independent inputs, and the model may ignore a negative memory.

The old diplomacy target arrays are removed. The plan uses:

```json
{
  "diplomacy_actions": [
    {
      "action": "declare_war",
      "other_sect_id": 2,
      "appraisal_ids": ["appraisal-id"]
    }
  ]
}
```

`action` is `declare_war` or `seek_peace`. A cited appraisal must belong to the local current patriarch, be present in that target's supplied context, and focus on the target current patriarch. Invented evidence invalidates only that diplomacy action.

## Causal audit

Every sect decision round records an `AgentDecision(subject_kind="sect")`. Its chosen chain contains institutional actions and cited appraisal IDs.

- The decision event links `MOTIVATED_BY` to source events of cited appraisals.
- A resulting war or peace event links `MOTIVATED_BY` to the decision event.
- Diplomacy changes are `FactKind.STATE_TRANSITION` facts with a `StateDelta` owned by `sect_diplomacy`, a normalized sect-pair owner ID, aspect `status`, and semantic before/after values.
- The existing summary event remains linked to the decision.
- Rule fallback is auditable and does not pause simulation.

## Query and UI

- Avatar detail exposes the top 10 `personal_appraisals`, sorted by effective weight.
- Causal event detail exposes `decision_appraisals` resolved from cited IDs.
- Decision DTO chosen steps accept `appraisal_ids`.
- The avatar profile adds a compact `Memórias marcantes` section showing focus, emotion, summary, date, and qualitative strength.
- Strength is strong at `>= 0.65`, moderate at `>= 0.35`, and weak at `>= 0.15`.
- Selecting a memory opens its source event in the existing causal-detail overlay.
- The Why view shows the subjective interpretation actually cited by the decision.
- Existing detail queries, journal store, overlay, and responsive layout are extended rather than duplicated.

## Acceptance criteria

1. Persistence round-trip, indexes, uniqueness, and event cascade are tested.
2. Weight decay is tested at 0, 10, 40, and 100 years.
3. Positive and negative appraisals can coexist.
4. Eligibility rejects story-only, unstructured, dead, unnamed, and unsupported cases.
5. Monthly batching caps AI work at 16 and never contacts a provider in test mode.
6. Existing saves open with no appraisal backfill; save/load preserves new rows.
7. Only current-patriarch appraisals enter the matching diplomacy context.
8. A negative appraisal may be ignored by a strategic decision.
9. Invented evidence invalidates only the corresponding diplomacy action.
10. One integration path proves conflict -> appraisal -> cited sect decision -> war -> Why chain.
11. An opposite integration path proves conflict plus military inferiority may still produce peace or inaction.
12. Backend tests, frontend tests/type-check, and `git diff --check` pass.
13. A new-world smoke test passes before any publication or deployment.

