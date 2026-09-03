# ADR 0001: Extensible Mechanical Language V1

- Status: Accepted
- Date: 2026-09-01
- Scope: Mechanical Language V1 domain model

## Context

The world needs a vocabulary for discovering and reusing mechanics such as
pressure, capacity, access, risk, and influence. That vocabulary must support
world-specific concepts without allowing an open-ended text generator to
become a hidden simulation or a second owner of canonical state.

The design therefore has two different extension surfaces:

1. A small, finite primitive grammar that the engine understands and versions.
2. A per-world ontology of concepts, groundings, derived metrics, and
   conditions that can grow from those primitives.

The distinction is essential. New world concepts should not require changing
the primitive grammar, while new primitive semantics must be an explicit
language-version decision.

## Decision

Mechanical Language V1 adopts the following rules.

### 1. Primitive grammar is finite and versioned

The V1 primitive dimension set is:

`stock`, `flow`, `load`, `capacity`, `access`, `quality`, `risk`, and
`influence`.

This is the V1 set, not an eternal list. Future additions or changes require a
new explicit language version and must not be smuggled in as an arbitrary
concept or expression operator.

### 2. Ontology is extensible per world

Each world may define and retain its own Concepts and Groundings, including
aliases and lifecycle. A Concept names meaning; a Grounding connects that
meaning to canonical state or observable evidence. The ontology may also retain
reusable Derived Metric Definitions and Condition Definitions.

Definitions are durable domain knowledge. Once validated and accepted, they
are persisted with the world and reused when the same concept and context are
encountered again. Reuse does not require a new LLM discovery call.

### 3. Readings are computed from canonical state

MetricReadings are calculated at observation time from the canonical domain
state and the accepted definitions. They carry their availability, reading
kind, unit, calculation time, and provenance. They never become a parallel
copy of the state and cannot be used as an implicit write path.

Measurement availability is independent from reading kind. The system must be
able to say that a metric is measurable, partially measurable, or
unmeasurable, while separately saying whether a result is exact, derived,
estimated, or unknown. Unmeasurable or unknown input must not be replaced by a
fabricated numeric value.

### 4. Expressions are deterministic validated ASTs

Derived metric definitions use a deterministic, closed expression tree. The
tree may reference allowed primitive metrics, accepted derived definitions,
numeric constants, and the approved arithmetic/aggregation operations. It may
not contain arbitrary code, hidden I/O, side effects, or an unbounded recursive
reference graph.

Validation happens before a definition is accepted or persisted. Validation
checks the grammar, references, complexity, and dependency cycles. Complexity
limits and other guardrail numbers are configurable defaults for a world or
language profile, not world laws. The initial defaults may use a maximum of 32
nodes and depth 8 for an expression, with condition persistence constrained to
the configured operating range; these values may be tuned without changing the
meaning of the world.

### 5. Only validated domain actions mutate canonical state

Mechanical Language can observe, calculate, classify, and propose. It cannot
apply a state patch, invent a fact, or directly perform an action. Any world
mutation must pass through the existing validated domain-action path and remain
owned by the domain that owns the state.

Condition Instances therefore describe evaluated occurrences and their causal
evidence. They do not become a second state machine that can overwrite an
Avatar, region, sect, dynasty, or any other canonical owner.

### 6. LLM discovery is observational

An LLM may help discover a candidate Concept, Grounding, Derived Metric
Definition, Condition Definition, or Mechanic Proposal from observations. Its
output is untrusted input. The LLM does not define truth, validate its own
output, mutate canonical state, or become the owner of the ontology.

The deterministic validator decides whether a candidate is expressible and
safe. Only accepted definitions become reusable domain knowledge. A proposal
may remain observational when the concept is not measurable or cannot yet be
grounded.

### 7. There is no parallel state owner

Canonical domain state remains the only authority for reality. Mechanical
Language state is limited to the per-world ontology, accepted definitions,
groundings, proposals, and the persisted records needed to explain how
readings and conditions were obtained. It must not introduce a shadow world,
duplicate simulation state, or independent mutation queue.

## Consequences

Positive consequences:

- Worlds can acquire new mechanics through reusable concepts and definitions
  without expanding the primitive grammar for every new idea.
- Repeated observations become deterministic and cheap after the first
  accepted definition.
- Save/load preserves the learned per-world vocabulary and its definitions,
  so a reload does not silently require rediscovery.
- Causal provenance can explain a reading or condition without confusing the
  explanation with the state it describes.

Costs and boundaries:

- The ontology needs lifecycle and validation rules rather than accepting any
  text as a mechanic.
- Some concepts remain unmeasurable or partially measurable and must be
  represented honestly instead of receiving an invented score.
- Changes to primitive semantics require versioned architectural decisions.
- LLM output remains useful for discovery but cannot be treated as a domain
  command or a persistence authority.

## Acceptance scenario

Use one stable derived concept and its condition definition across the
following observations:

1. World A produces a canonical reading of `0.90`. The system discovers a
   candidate concept/definition, validates it, accepts it, and evaluates the
   condition. The accepted definition is persisted.
2. World B produces `0.91` for the same concept and context. The persisted
   definition is reused; no LLM discovery call is made.
3. World B later produces `0.70`. The same condition definition resolves the
   active Condition Instance according to its configured resolution rules.
4. Save and load the world. The accepted concept, grounding, metric
   definition, condition definition, and relevant condition record remain
   available after reload.
5. World C produces `0.92` for the same concept and context. The persisted
   definition is reused again, with no LLM discovery call.

This scenario proves discovery, validation, reuse, resolution, persistence,
and reuse after reload without granting the LLM or Mechanical Language a
parallel state owner.
