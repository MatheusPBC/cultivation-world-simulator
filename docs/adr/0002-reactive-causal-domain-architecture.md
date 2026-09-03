# Reactive Causal Domain Architecture V1

- Status: Accepted
- Date: 2026-09-01
- Scope: Causal world architecture delivered in V1

This delivery establishes a reactive domain layer in which canonical state
remains authoritative, the Mechanical Language supplies a finite grammar, and
the world ontology can grow through grounded concepts and deterministic
derived observations. The decision records the boundaries that keep LLM
interpretation useful without turning it into a hidden simulator.

## Decision

- Mechanical Language V1 has a finite, versioned grammar of nine primitive
  dimensions: `stock`, `flow`, `load`, `capacity`, `access`, `quality`, `risk`,
  `influence`, and `dependency`. An LLM may not add a primitive or write a
  canonical state value.
- `MetricKey` identifies a question; `GroundedMetricBinding` and the resolver
  registry connect that question to canonical state at runtime. Bindings are
  not persisted. `MetricReading` is calculated, can be unknown, and carries
  unit, availability/reading kind, state references, and causal source IDs.
- Concepts and groundings form a per-world extensible vocabulary. Concepts,
  derived metric definitions, and conditions have explicit lifecycle states;
  mechanic proposals remain observational until accepted. Derived metrics are
  validated ASTs, deterministic, bounded, acyclic, and observational only.
- Condition definitions and condition instances are separate. Instances are
  attached to a target and retain readings and causal evidence. Activation and
  resolution use distinct thresholds and persistence windows, so hysteresis is
  explicit and a condition does not mutate the world by itself.
- Domain interpreters return typed decisions and action-intent proposals for
  population transfer, resource transfer, or urban maintenance. `maintain` or
  `NO_ACTION` is valid. A proposal is not execution: the owning domain checks
  affordances, chooses quantities/destinations where applicable, applies the
  mutation, and emits `Event`, `StateDelta`, and causal links.
- Reactivity is dirty-driven. Mechanical and semantic invalidations carry
  target, reason, revision, and source-event IDs. Persisted domain reaction
  receipts deduplicate reactions per condition/domain/revision. One shared
  per-step causal budget limits semantic evaluations, interpreter calls,
  propagation, and domain mutations.
- `Region` owns city-local canonical state. All `ConditionInstance` records are
  owned by the world's `MechanicalLanguageState.condition_instances` registry
  and are queried by their `EntityRef` target; no domain keeps a duplicate
  condition collection.
  `CityState` provides districts, urban assets, and governance capacity;
  `RegionalEconomyState` provides declared stocks, capacities, production,
  demand, access, and dependencies; health and spiritual ecology are
  read-only projections of existing avatars, injuries, assets, essence,
  formations, graves, treasures, and celestial context.
- Inter-city logistics uses explicit map-owned `Route` entities with stable
  endpoints, capacity, quality, enablement, and resource permissions. Geometry
  or nearby coordinates never imply a route, access, or war capability.
- The current interpreters are population, economy, and city maintenance.
  Sect decisions receive the regional semantic context; they are not forced to
  alter relations or start wars. Test mode uses deterministic task fallbacks
  and never calls an LLM provider.
- Imperial crises remain active through inconclusive annual readings. Explicit
  support and opposition are the only stored political positions; neutrality
  is derived. Celestial evidence affects legitimacy only when its source fact
  identifies exactly one contender. Imperial actions return events to the
  normal step pipeline instead of persisting outside it.
- Step events are finalized as one atomic storage batch. A failed event rolls
  the batch back and the month does not advance, preserving the causal boundary
  between canonical mutation, evidence, and time progression.
- Every persisted event also carries an explicit `CausalOrigin`, orthogonal to
  `FactKind`: deterministic engine work, LLM interpretation, actor decision,
  derived condition, or external event. Read-only causal telemetry aggregates
  these origins, fact kinds, chain depths, and missing causes from event IDs;
  it never infers authorship from prose or mutates the world.

## Consequences and explicit boundaries

This architecture lets a world retain and reuse a newly accepted observation
without paying for an LLM call whenever its value changes. It also makes each
causal chain inspectable through event evidence and save/load, while leaving
the state owner responsible for every real consequence.

This delivery does not implement LLM-created primitives or arbitrary state,
disease or epidemiology, climate/hydrology or flood simulation, crime and
public-security simulation, territorial war/control/supply, or autonomous
government, culture, religion, or war interpreters. It also does not infer
poverty, class access, transport routes, or spiritual danger from prose or
coordinates. Those features require additional canonical substrate and a
separate decision; the existing war, sect, imperial, Dao, and individual
systems continue under their current contracts.

The architecture is documented in detail in
[`extensible-mechanical-language-v1.md`](../specs/extensible-mechanical-language-v1.md).
