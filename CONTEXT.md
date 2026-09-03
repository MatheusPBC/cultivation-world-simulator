# Ubiquitous Language

## Celestial Dao

The player-visible authority that can remain silent, issue an observable sign,
or grant a limited favor. It never completes another domain's objective.

## Dao Tradition

A persistent regional interpretation of the one Celestial Dao. It is not an
Orthodoxy, sect, church, or temple system.

## Dao Petition

A World-owned request from an Avatar, Sect, or court. It names its initiator,
region, motivating facts, and response state.

## Imperial Crisis

One active political contest between a reigning Avatar and an eligible Avatar
claimant. It can change the dynasty's sovereign reference but does not create
territorial war or delete either Avatar.

## Mechanical Language V1

Mechanical Language is the world's vocabulary for describing measurable or
derivable conditions without becoming a second owner of world state. The
primitive grammar is finite and versioned; the ontology built from it is
extensible per world.

### Primitive Dimension V1

The V1 set contains exactly these nine primitive dimensions:

- `stock`: an amount held at a point in time.
- `flow`: an amount or rate changing through time.
- `load`: current use, pressure, demand, or occupancy against a system.
- `capacity`: available ability or limit to sustain a load or activity.
- `access`: ability to reach, use, or participate in something.
- `quality`: a degree of condition, fitness, or state.
- `risk`: exposure to an adverse outcome or loss.
- `influence`: ability to affect decisions, relationships, or outcomes.
- `dependency`: degree to which a subject relies on a named resource or
  capability.

These nine dimensions are the Mechanical Language V1 set, not an eternal
taxonomy. A later language version may add or revise primitives through an
explicit versioned decision; a world ontology must not silently invent a new
primitive dimension.

### Concept

A Concept is a per-world vocabulary entry: a stable identity, human-readable
label, kind, aliases, lifecycle, and the meaning the world assigns to it. A
concept is not automatically a fact, metric, condition, or action. It becomes
mechanically useful only when it has an accepted grounding or a validated
definition.

### Grounding

A Grounding is the evidence-backed association between a Concept and canonical
world state or observable domain evidence. It records what the concept refers
to, the subject scope, the supporting evidence, and the validity or confidence
of that association. Grounding can be proposed, claimed, or accepted as
grounded; a claim alone does not make the concept authoritative.

## Grounded Metric Binding

A Grounded Metric Binding is the engine-owned connection between a metric
question and canonical evidence. It makes a reading measurable only when the
world contains the required state; missing evidence remains unknown.

### MetricKey

A MetricKey identifies a metric without containing its value. It names the
primitive dimension, the subject kind and subject identity, and the per-world
concept being measured. Two readings with the same key refer to the same
question at different calculation times or from different evidence states.

### MetricReading

A MetricReading is the result of resolving a MetricKey against canonical state
at a calculation time. It may contain a value and unit, measurement metadata,
and provenance such as the canonical state references or source evidence used.
It is an observation, not a state mutation.

Measurement availability and reading kind are separate axes:

- Availability answers whether the world can measure the requested concept from
  the available canonical state: measurable, partially measurable, or
  unmeasurable.
- Reading kind answers how the returned result was obtained: exact, derived,
  estimated, or unknown.

An unavailable reading must not be turned into a guessed number. A derived
reading can be measurable because its inputs are measurable; an estimated
reading must expose its uncertainty; an unknown reading has no numeric value.

## Metric Lifecycle

A metric concept can be a candidate, active, dormant, deprecated, or merged.
Lifecycle changes control reuse of the world's vocabulary and do not rewrite
the historical facts that gave the concept meaning.

### Derived Metric Definition

A Derived Metric Definition is a named, reusable, per-world definition for
calculating a metric from primitive readings and, where explicitly allowed,
other derived definitions. It declares its concept, dimension, subject scope,
unit, and deterministic expression. The definition describes how to read the
world; it does not store or own the underlying state.

### Condition Definition

A Condition Definition is a named, reusable rule that interprets one metric or
derived metric for a subject. It declares the condition concept, activation and
resolution boundaries, and any persistence or hysteresis requirements. It is a
definition, not an active occurrence. Thresholds and time windows are
configuration defaults and balancing inputs, not universal laws of every
world.

### Condition Instance

A Condition Instance is one occurrence of a Condition Definition attached to a
specific target. It records the condition's active or resolved lifecycle,
intensity when applicable, time boundaries, source readings, and causal
evidence. Instances are consequences of evaluating canonical state and
definitions; they do not become an alternative state authority. The single
owner is the world's `MechanicalLanguageState.condition_instances` registry,
keyed by instance ID; consumers query it by `EntityRef(target_kind, target_id)`.
Regions, routes, sects, Avatars, and dynasties do not carry duplicate condition
collections.

### Mechanic Proposal

A Mechanic Proposal is an observational suggestion for a concept, grounding,
metric, or condition that the current ontology cannot yet express or measure.
It records the proposed meaning and why the proposal was made. A proposal is
not an action, a fact, or permission to mutate the world. It requires explicit
validation and acceptance before it can produce a reusable definition.

### Action Intent

An Action Intent is a proposed change expressed from a meaningful transition
or situation. It states what could be pursued, but does not promise that the
world will perform it.

### Affordance

An Affordance is a change the current world makes available to an actor or
domain under the relevant conditions. Availability is not execution.

## Domain Reaction

A Domain Reaction is a typed interpretation of a causal transition by a
collective domain. It may maintain the current state or propose an action
intent; the owning domain decides whether the action is feasible and applies
any resulting change.

### Population Transfer

A Population Transfer is a domain change in which people move from one place
to another. Its meaning includes the origin, destination, and quantity moved.

### Domain Invalidation

Domain Invalidation is the loss of validity of a domain interpretation because
the conditions or evidence that supported it have changed. It requires the
affected interpretation to be reconsidered, not silently treated as current.

## Causal Budget

A Causal Budget is the bounded allowance for one simulation step's semantic
evaluations, interpreter decisions, propagation, and domain mutations. It is a
runtime guardrail, not a rule of the world.

### Regional Economy

Regional Economy is canonical quantitative state owned by a CityRegion. It may
declare stocks, capacities, local production and demand rates, access ratios,
and dependency strengths for named concepts. Missing declarations are unknown;
they are not inferred from a shop catalogue or from prose.

### Infrastructure State

Infrastructure State is canonical local capacity and quality owned by a
CityRegion. It describes declared assets such as storage, roads, or transport
capacity without creating a route graph. Routes and inter-city flow require an
authoritative map or logistics owner and cannot be invented from coordinates.

## CityState

CityState is the canonical local urban substrate owned by a CityRegion. It
describes districts, urban assets, their grounded capabilities and integrity,
and the city's administrative capacity.

### Urban Service Demand

Urban Service Demand is a CityState declaration of how much load one unit of
city population places on a dynamic capability such as housing, clean water,
sanitation, or security. It grounds a measurable need; it does not assert a
shortage or produce an adverse outcome by itself.

### Urban Population Group

An Urban Population Group is a weighted slice of a CityRegion's one canonical
population. It may declare relative priority for constrained urban services,
but it never owns a separate population count. Group population is always
derived from `CityRegion.population` and the group's weight.

### Urban Service Access

Urban Service Access is the measured share of declared demand that existing
urban assets can satisfy for the city or one Urban Population Group. The engine
derives it from population, service demand, asset capacity, quality, integrity,
and group priority. Access is an observation and never mutates population,
health, security, or any other domain directly.

### Settlement Capacity

Settlement Capacity is the aggregate population a CityRegion can sustainably
support. `CityRegion.population_capacity` is its single canonical owner; urban
assets may ground actions that change it but do not duplicate or replace it.

### Urban Capacity Project

An Urban Capacity Project is a durable undertaking owned inside a CityState
that can increase Settlement Capacity after grounded work over time. An
interpreter may propose starting one, but the city domain determines its
feasibility, duration, progress, and capacity gain. No capacity changes before
the project completes.

### Construction Resource Reservation

A Construction Resource Reservation is a project-bound claim on part of a
Regional Economy stock. Reserved goods remain physically present until work
consumes them, but they are unavailable to ordinary demand, trade, or another
project. Releasing a reservation restores availability without creating goods.

### Construction Work Capacity

Construction Work Capacity is a grounded urban capability that limits how much
building work a city can carry out over time. It is not a currency or a stored
material, and administration can coordinate it without owning or consuming it.

## Explicit Route

An Explicit Route is a map-owned connection between two regions with declared
capacity, quality, enablement, mode, and resource permissions. Geographic
proximity does not create a route.

## Collective Health Projection

Collective Health Projection is a read-only view of living avatars, persistent
injuries, HP deficit, and explicitly grounded healing capacity in a
region. It does not assert disease or invent public-health risks.

### Healing Access

Healing Access is the measured share of a city's declared healing demand that
its existing healing assets can satisfy. It is not treatment, HP recovery, or
evidence that any particular Avatar received care.

### Recovery Strain

Recovery Strain is a persistent regional condition in which real Avatar injury
burden coincides with insufficient Healing Access. It describes pressure on
recovery without asserting disease among the wider population or causing harm
by itself.

## Spiritual Ecology Projection

Spiritual Ecology Projection is a read-only view of existing cultivation
essence, formations, graves, treasures, and celestial context associated with a
region. It does not invent manifestations or spiritual danger.

## Causal Origin

Causal Origin is the explicit, finite authorship category persisted alongside
`FactKind` on an event. It records whether the fact came from deterministic
engine work, an LLM interpretation, an actor decision, a derived condition, or
an external event. It is never inferred from prose.

## Causal Telemetry

Causal Telemetry is a read-only aggregation over persisted event IDs and causal
links. It reports origin and fact-kind counts, chain-depth distribution,
missing causes, and interpreter/actor shares without becoming a new state
owner.

## Causal Probe

A Causal Probe is an external test stimulus committed at a month boundary to
challenge the world's causal reactions. It selects targets from canonical
properties, uses the owning domain's validated mutation path, and records its
own evidence; it is not a world rule or a normal event generator.

## Simulation Month Transaction

A Simulation Month Transaction is the logical commit boundary for one complete
simulation step. Canonical objects are checkpointed before any phase runs; an
abort or exception restores their existing identities, values, semantic
registries, dirty state, calendar, and random generator state. Durable events
and an optional Chronicle chapter are committed together by EventStorage in one
SQLite transaction. The calendar advances only after both the in-memory work
and durable bundle succeed.

## Government Reaction

A Government Reaction is an institutional interpretation made by the current
Dynasty for a CityRegion whose `CityGovernance` explicitly names that Dynasty
as controller. It may authorize an existing urban affordance or take no action;
the CityState remains the sole owner of the resulting urban mutation. Government
Reaction does not imply a new government entity, treasury, policy ledger, or
territorial registry.

## Organization Reaction

An Organization Reaction is an institutional interpretation made by an
existing Sect. In the current model, Sect is the only organization owner: its
members and spirit-stone treasury are not copied into a generic organization
state. A Sect may react to a grounded regional condition affecting one of its
members, but a typed intent must pass the Sect owner's affordance checks before
any material support occurs.

### Sect Member Support

Sect Member Support is a bounded transfer from a Sect's canonical spirit-stone
treasury to one living member who is currently present in the causally relevant
region. The interpreter selects only among eligible member IDs; the deterministic
Sect owner validates membership, location, treasury, and amount, then records
both balance deltas and their causal sources.
