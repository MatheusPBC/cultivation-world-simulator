# ADR 0007: Institutional Knowledge Versus Institutional Memory

- Status: Accepted
- Date: 2026-09-04
- Scope: Institutional Knowledge, InstitutionalMemory, InstitutionalIdentityAnchor

## Context

"Who knows a fact" and "how much that fact matters" are different questions
answered by different owners. Collapsing them into one record would force the
knowledge system to carry salience/decay semantics it does not otherwise need,
and would force memory to duplicate fact propagation it does not own.

## Decision

- `InstitutionalKnowledgeState` is the sole owner of which Institution knows a
  canonical fact. It stores acquisition channel and evidence but no salience;
  institutional facts do not expire from knowledge in V1.
  Institutional Memory never determines or stores knowledge propagation.
- `InstitutionalMemory` records only how much a known canonical fact matters to
  an institution. Every memory references canonical event IDs; a memory with
  no traceable event is invalid.
- Active memory has salience, decay, and reinforcement. Engine-owned
  historical weight uses only relative scale, institutional change, commitment
  breach, and impact on an `InstitutionalIdentityAnchor` — no other ad hoc
  factor may be added without simulation evidence, matching the spec's frozen
  boundary against unbounded historical-weight factors.
- `InstitutionalIdentityAnchor` references canonical founders,
  headquarters/capitals, core relics, sacred sites, or founding commitments.
  It exists so historical weight has a stable reference point, not to become a
  second mutable identity record alongside `Institution`. Anchors are owned by
  `InstitutionalAuthorityState`; memory only references them when computing
  historical weight.

## Consequences

Positive consequences:

- Knowledge propagation logic can evolve (rumor, distance, secrecy) without
  touching memory salience or decay.
- Memory salience and decay can evolve independently of how facts spread,
  since both sides only share canonical event IDs as their contract.
- Historical weight stays auditable: every contributing factor traces to an
  event ID or an identity anchor.

Costs and boundaries:

- A memory record must never carry its own "who knows this" flag; that
  question is always answered by the knowledge system.
- Do not add new historical-weight factors casually; each new factor requires
  simulation evidence, per the spec's frozen boundaries.
- `InstitutionalIdentityAnchor` is a reference, not a place to store
  independently mutable institutional state.
