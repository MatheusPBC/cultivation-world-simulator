# Extensible Mechanical Language V1

## 1. Purpose and scope

Mechanical Language V1 gives each world a small mechanical grammar and an
extensible vocabulary for expressing derived metrics and conditions. It is a
domain model and persistence contract. It is not a replacement simulator, an
event-sourcing model, an LLM-owned rules engine, or a second canonical state
store.

The language separates:

- finite primitives understood by the language version;
- concepts and groundings owned by an individual world;
- readings computed from canonical state;
- reusable definitions that interpret readings; and
- observational proposals for mechanics that are not yet grounded or
  measurable.

## 2. V1 domain invariants

1. The primitive grammar is finite and explicitly versioned.
2. The nine dimensions listed in section 3 are the Mechanical Language V1
   set. They are not eternal or exhaustive for all future language versions.
3. A world's ontology may extend with new Concepts, Groundings, Derived Metric
   Definitions, and Condition Definitions, but may not silently add a new
   primitive dimension.
4. Readings are calculated from canonical state and include provenance.
5. Expressions are deterministic, validated ASTs with no arbitrary code or
   side effects.
6. Only validated domain actions mutate canonical state.
7. LLM discovery is observational and untrusted; it can suggest candidates but
   cannot establish truth or mutate the world.
8. Accepted definitions and the per-world ontology are persisted and reused.
9. No Mechanical Language record is a parallel owner of Avatar, region, sect,
   dynasty, or other canonical domain state.

## 3. Primitive Dimension V1

The primitive dimensions are the stable vocabulary of the V1 grammar:

| Dimension | Meaning |
| --- | --- |
| `stock` | Quantity held at a point in time. |
| `flow` | Quantity or rate changing through time. |
| `load` | Current use, pressure, demand, or occupancy. |
| `capacity` | Available ability or limit to sustain a load or activity. |
| `access` | Ability to reach, use, or participate. |
| `quality` | Degree of condition, fitness, or state. |
| `risk` | Exposure to an adverse outcome or loss. |
| `influence` | Ability to affect decisions, relationships, or outcomes. |
| `dependency` | Degree to which a subject relies on a named resource or capability. |

This is a versioned language boundary. A per-world concept such as
“settlement density pressure” is extensible ontology; it is not an additional
primitive dimension. Adding or changing primitive semantics requires a future
language version and an explicit architectural decision. The LLM cannot add a
primitive automatically.

## 4. Domain model

### 4.1 Concept

A Concept is a stable per-world meaning. It provides an identity, label, kind,
aliases, lifecycle, and the semantic intent that users or systems recognize.
It does not itself contain a reading, threshold, or mutation.

Concepts may begin as candidates, become active after validation, become
dormant, or be deprecated or merged as the world's vocabulary evolves. Those
lifecycle changes affect ontology reuse; they do not rewrite canonical state.

### 4.2 Grounding

A Grounding connects a Concept to the canonical state or observable evidence
that gives the concept meaning in a particular world and subject scope. A
grounding should make clear:

- what canonical subject or evidence it refers to;
- which primitive dimension or metric question it supports;
- the evidence supporting the association; and
- whether the association is proposed, claimed, or accepted as grounded.

Grounding is not the same as measurement. A concept can have a proposed
grounding while its current reading is unmeasurable, and a measurable reading
must still identify the state it came from.

Runtime `GroundedMetricBinding`s and the resolver registry are the bridge from
MetricKeys to canonical domain owners. A binding declares the supported
dimension/concept shape and unit, resolves a reading, and may enumerate keys
that are actually available. The callable binding itself is engine code and
is never written to a save. Missing grounding returns an explicit unknown
reading.

### 4.3 MetricKey

A MetricKey is the address of a metric question. It contains:

- a Primitive Dimension;
- the subject kind;
- the subject identity; and
- the per-world concept identity.

It contains no value. This makes a key reusable across calculation times and
keeps identity separate from observation.

### 4.4 MetricReading

A MetricReading is a time-scoped observation produced by resolving a MetricKey
against canonical state or accepted derived definitions. It contains, as
applicable:

- a numeric value or an explicit absence of value;
- a unit;
- calculation time;
- measurement availability;
- reading kind; and
- provenance, including state references and source evidence.

Measurement availability and reading kind must never be collapsed into one
field:

| Axis | Values | Question answered |
| --- | --- | --- |
| Measurement availability | measurable, partially measurable, unmeasurable | Can the requested concept be answered from available canonical state? |
| Reading kind | exact, derived, estimated, unknown | How was this result obtained? |

An exact reading may come directly from canonical state. A derived reading is
calculated from other readings. An estimated reading must carry uncertainty or
confidence. An unknown reading has no numeric value. When inputs are missing,
the result stays partially measurable or unmeasurable as appropriate; it is not
replaced with a guessed score.

### 4.5 Derived Metric Definition

A Derived Metric Definition is a named, persisted, reusable recipe for
producing a metric. It identifies its Concept, output Primitive Dimension,
subject scope, unit, and deterministic expression.

Its expression may reference allowed primitive MetricKeys, accepted derived
definitions, numeric constants, and the approved arithmetic or aggregation
operations. It may not execute arbitrary code, perform I/O, mutate state, or
follow a cyclic dependency.

The definition is knowledge about how to read the world. It is not a cache of
the world and cannot replace the canonical fields from which its readings are
computed.

### 4.6 Condition Definition

A Condition Definition is a named, persisted, reusable interpretation of a
metric for a target kind. It identifies:

- the condition Concept;
- the metric or Derived Metric Definition it evaluates;
- activation and resolution boundaries; and
- persistence, hysteresis, expiry, or other temporal requirements.

Activation and resolution are deliberately separate. A condition can remain
active while a value moves within the hysteresis band, and it resolves only
when its configured resolution rule is satisfied. Persistence counts
consecutive calendar months; a skipped evaluation resets the streak instead
of turning budget pressure into fictional continuity.

Thresholds, node/depth limits, persistence windows, and similar guardrail
numbers are configurable defaults, not laws of the world. The initial
validation profile may use an expression limit of 32 nodes and depth 8, and
condition persistence windows in the configured 1-to-12-month range; these are
tunable defaults and must not be presented as eternal domain truths.

### 4.7 Condition Instance

A Condition Instance is a concrete occurrence of a Condition Definition for a
specific target. It records the definition identity, target identity, active or
resolved status, relevant time boundaries, intensity when applicable, source
readings, and causal evidence.

The definition is reusable policy; the instance is one evaluated occurrence.
An instance can be active, resolved, or expired according to its definition.
Neither the instance nor its intensity is allowed to mutate canonical state by
itself. Any consequence that changes the world must be represented by a
validated domain action owned by the affected domain.

### 4.8 Mechanic Proposal

A Mechanic Proposal is a durable observational record that the current
ontology cannot yet express, ground, or measure a potentially useful mechanic.
It includes the candidate meaning, the reason for proposing it, and any
unmeasurable metric questions or evidence that motivated the proposal.

A proposal is not a Concept, accepted Grounding, definition, action, or fact.
It may be reviewed and rejected, refined into a candidate, or accepted only
after deterministic validation and domain approval.

## 5. Discovery and reuse lifecycle

The lifecycle is intentionally split between observation, validation, and
domain execution:

1. Canonical state produces observations and MetricReadings.
2. If the world has no reusable concept or definition for the observed need,
   an LLM may suggest candidates or a Mechanic Proposal.
3. The suggestion is treated as untrusted observational input. A deterministic
   validator checks concept references, primitive dimensions, AST grammar,
   dependency cycles, and configured complexity guardrails.
4. A validated and accepted concept/grounding/definition becomes per-world
   ontology and is persisted.
5. Future observations resolve the persisted definition directly. They do not
   invoke LLM discovery merely because the numeric value changed.
6. A Condition Definition evaluates readings into Condition Instances. Any
   resulting world change goes through a validated domain action.

The LLM may assist step 2 only. It does not perform steps 3, 4, or 6 and does
not own the result of any step. Current discovery is limited to grounded
region observations and is budgeted/cooldown-limited; the same accepted
definition is evaluated for other regions without rediscovery.

## 6. Reactive domain architecture

The first reactive vertical connects a semantic transition to a possible
world consequence without making semantic interpretation an action executor:

1. A semantic transition triggers an interpreter.
2. The resulting Action Intent is a proposal, not a guarantee that an action
   will occur.
3. The engine decides whether an Affordance exists and, when applicable, its
   destination and quantity. The interpreter does not decide those outcomes.
   A feasible partial transfer may reduce pressure without resolving the active
   condition.
4. `NO_ACTION` is a valid result when no supported or warranted consequence is
   available.
5. The current typed interpreters cover population transfer, resource transfer,
   and city urban maintenance. Population and economy reactions can be
   grounded in conditions; city maintenance requires a risk definition whose
   expression actually references a quality capability present in a city's
   urban asset. No city is selected by a hardcoded script.
6. Mechanical invalidations only trigger deterministic recomputation. Semantic
   transitions trigger interpretation. A shared causal budget limits
   evaluations, interpreter calls, propagation, and mutations. A domain may
   return `maintain`/`NO_ACTION` when no justified action exists.
7. A proposal never chooses an ungrounded result. The population and economy
   engines calculate affordances, destinations, quantities, route capacity,
   and partial outcomes. The city executor calculates maintenance amount from
   the asset and governance capacity.
8. Accepted domain changes emit factual events and StateDeltas. The delta is
   causal evidence, not a patch language. Source event IDs remain attached to
   invalidations, readings, decisions, and resulting events.

The canonical regional substrates implemented by this vertical are:

- `CityState`, owned by `Region`, with footprint-covering districts, dynamic
  capability IDs on urban assets, asset quality/integrity, and governance
  administrative capacity;
- regional economy and local infrastructure state, owned by the same region,
  with declared stocks, capacities, production, demand, access, dependency,
  and quality/capacity facts; and
- map-owned explicit routes with stable IDs, endpoint regions, mode, capacity,
  quality, enabled state, and allowed resources.

Read-only collective health exposes living avatars in the region, active V1
injuries, HP deficit, and explicitly grounded healing capacity. It
does not infer disease, mortality, or class-based access. Read-only spiritual
ecology exposes cultivation essence, active formations, graves, treasures, and
celestial context already present in the world. It does not invent a spiritual
risk or a manifestation.

The vertical is accepted only when its semantic transition, intent, affordance,
destination, quantity, and `NO_ACTION` outcomes survive save/load and remain
explainable through the world's Why evidence. Save/load must preserve the
meaning needed to reproduce or inspect the result; Why must distinguish the
transition, the proposed intent, the engine's decision, and any resulting
domain change.

## 7. Deterministic expression contract

Every derived expression is an AST whose nodes belong to the versioned grammar.
V1 supports metric references, references to accepted derived definitions,
numeric constants, and approved arithmetic, aggregation, and bounding
operations. The validator must reject unknown operators, malformed nodes,
invalid references, excessive complexity, and dependency cycles.

Evaluation is deterministic for the same canonical state, accepted definitions,
target, and calculation time. Missing inputs propagate as an explicit unknown
or partially measurable result with provenance; evaluation does not infer a
number to make a condition look complete.

Guardrail values such as maximum AST size, maximum depth, threshold defaults,
and persistence windows are configuration. They limit unsafe or noisy
definitions but do not define universal world physics.

## 8. Reactivity, receipts, and causal budgets

The simulator runs the domain layer through a dirty queue rather than calling
every interpreter for every entity every month:

```text
canonical mutation
  -> mechanical invalidation
  -> metric recomputation
  -> condition transition
  -> semantic invalidation
  -> typed interpreter decision
  -> domain-owned affordance and mutation
  -> events/deltas/source IDs
  -> further invalidations
```

Invalidations are layered as mechanical or semantic and carry the target,
reason, revision, condition instance when relevant, and source-event IDs.
Reaction receipts are durable records keyed by condition instance, domain, and
trigger revision. They record decision events, next eligibility, and completion
so population, economy, and city reactions can be retried or deduplicated
independently after save/load. A shared `CausalBudget` bounds the whole chain
within one simulation step; its numbers are configurable guardrails, not world
laws.

## 9. Persistence and save/load

The per-world ontology is part of the world's durable knowledge. Save/load must
preserve, at minimum:

- accepted Concepts and their Groundings;
- accepted Derived Metric Definitions;
- accepted Condition Definitions;
- Mechanic Proposals that are intentionally retained; and
- Condition Instances or resolution records needed to preserve the world's
  current interpretation after reload.
- Reaction receipts and pending source-event provenance needed to continue a
  dirty evaluation without losing its causal explanation.
- Region-owned CityState and economy/infrastructure state, map-owned routes,
  and world-owned condition instances keyed by target EntityRef
  runtime values, using stable IDs and JSON data.

Events emitted by one simulation step are persisted as a single atomic batch.
If any event or association fails, no event in that batch is committed and the
world month remains unchanged.

Reload must restore definitions as reusable definitions, not as new discovery
requests. Persisted definitions remain subject to the current language-version
compatibility policy; no hidden migration or parallel legacy path is part of
V1.

### Regional evaluation scope

Semantic discovery in V1 may select any canonical Region that exposes at least
one uncovered metric which the engine resolves as measurable for that concrete
target. The LLM receives only these grounded metric schemas. It cannot turn an
unknown reading into a numeric proposal, mutate canonical state, or bypass the
same deterministic proposal validator used for urban discovery.

Discovery candidates are deduplicated by metric-surface structure rather than
Region identity. Retry cooldown is also attached to that surface, so equivalent
Regions do not generate redundant calls and a failed surface does not starve a
different measurable surface. CityRegion keeps its established scheduling
priority; non-city discovery adds reach without changing the existing urban
calendar semantics. Configured discovery and causal budgets remain operational
guardrails, not laws of the world.

Deterministic reuse remains broader than discovery: every accepted definition
whose `target_kind` is `region` is evaluated against every canonical Region.
Resolvers decide whether the required evidence is measurable for each concrete
target. An unknown reading cannot activate or resolve a condition and does not
add a reuse context.

Regional condition events remain observations. City, Population, and
Government reactions require a CityRegion target; Organization may react in a
non-city Region only through its existing grounded regional-adversity and
member-presence rules.

## 10. Acceptance scenario

The following scenario is normative for V1 and uses the same concept,
grounding, derived metric definition, and condition definition for several
regions in one world:

1. **A = 0.90 discovers.** Region A has canonical state from which the needed
   derived reading is `0.90`. No reusable definition exists, so discovery may
   use the LLM to propose the concept/grounding/definition. The deterministic
   validator accepts it, and the definition is persisted.
2. **B = 0.91 reuses without LLM.** Region B reaches the same metric context at
   `0.91`. The persisted definition is found and evaluated directly; no LLM
   discovery call occurs.
3. **B = 0.70 resolves.** Region B later reads `0.70`. The existing Condition
   Definition applies its configured resolution rule and resolves the active
   Condition Instance when the required temporal guardrail is satisfied.
4. **Save/load.** Save and reload the world. The accepted ontology,
   definitions, grounding, and relevant condition record remain available.
5. **C = 0.92 reuses without LLM.** Region C reaches the same context at `0.92`.
   It reuses the persisted definition without another LLM discovery call.

The scenario is successful only if numeric values are derived from canonical
state, definition reuse survives save/load, resolution follows the condition
definition, and no LLM or Mechanical Language component becomes a parallel
state owner.

## 11. Causal torture probes

The headless torture harness may apply a typed `CausalProbe` at a month
boundary. A probe is an external test stimulus, not a normal world rule and
not a scripted event for a named city. Its target is selected deterministically
from canonical properties and usable affordances in the generated world.

The owning domain validates and applies the canonical mutation, while the
probe commits a public event, state deltas, target references, and pending
source-event provenance atomically. From that point onward, the normal runtime
must produce every consequence: metric recomputation, condition transitions,
interpreter decisions, validated actions or `NO_ACTION`, further mutations,
and causal links.

V1 includes generic profiles for population pressure, resource shortage, and
resource shortage with an interrupted route. These are verification tools for
causal propagation. They do not grant interpreters permission to invent city
state, resource stock, routes, or outcomes.

## 12. Test-mode and explicit non-goals

Rule-based test mode registers deterministic fallbacks for semantic discovery,
population, economy, and city interpreter tasks. It never performs provider
connectivity checks or calls a real LLM. Unknown tasks fail closed rather than
falling back to a provider.

The following are intentionally not implemented by this delivery:

- Adding primitive dimensions without a new language version.
- Treating free-form LLM text as executable mechanics.
- Letting an LLM invent canonical state, a primitive, a route, a disease, a
  flood, a crime event, or a war capability.
- Letting a MetricReading, ConditionInstance, or proposal write canonical
  state directly.
- Maintaining a shadow simulation or duplicate state store.
- Treating guardrail defaults as immutable world laws.
- Disease/epidemiology, detailed water propagation, flood effects on population
  or economy, crime/public security, territorial war/control/supply, and autonomous government,
  culture, religion, or war interpreters.
- Inferring poverty, class access, spiritual danger, or route connectivity
  from prose, proximity, or coordinates.
