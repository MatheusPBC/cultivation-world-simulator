# ADR 0008: Prose Is Never a Material Cause

- Status: Accepted
- Date: 2026-09-04
- Scope: LLM interpretation, Story, institutional decisions and affordances

## Context

ADR 0004 already established that Stories and LLM interpretations carry no
`StateDelta` and cannot be the material cause of a mutation for the general
causal architecture. Institutions, offices, claims, relations, commitments,
and memory introduce new surfaces — recognition, legitimacy readings,
`CasusBelliReading`, commitment fulfillment — where it would be easy to let
generated text quietly stand in for a missing fact. This ADR extends ADR
0004's rule explicitly into the institutional domain instead of leaving it
implicit.

## Decision

- Every institutional choice — opening or withdrawing an `AuthorityClaim`,
  recording or revoking `Formal Recognition`, proposing or actively fulfilling
  or remediating an `InstitutionalCommitment` Term, deliberately taking an
  incompatible action, or forming an `Institutional Relation` — is persisted
  as `FactKind.DECISION` carrying an `AgentDecision` with no `StateDelta`.
  Its `actor_ref` may be the Institution; the current office and holder only
  authorize it through deterministic `can_actor_act_for`.
- The canonical owner executes an accepted choice in a separate state
  transition event carrying the `StateDelta` and causally pointing to the
  decision. A missed deadline may produce a deterministic breach/expiry fact
  without a new choice, but prose never causes it and it never moves material
  resources automatically.
- An LLM or Story may select among engine-enumerated `DomainAffordance`
  options or interpret an outcome. It may not invent evidence, quantities,
  targets, terms, authority, or state changes for any institutional entity.
- `CasusBelliReading` fields — perceived cause, credibility, objective, reach,
  urgency, expected cost, expected gain, available alternatives — record an
  actor's interpretation. Missing evidence stays unknown; it is never
  replaced by a value invented from prose, and a `CasusBelliReading` never
  itself authorizes a war action or claim.
- Perceived legitimacy is read from an observer's knowledge and readings
  (ADR 0005); it is not asserted directly from narrative text describing how
  legitimate an institution "feels."
- This ADR references and extends ADR 0004: the finalizer's pre-commit
  invariant check (decision facts carry no delta, Story points to a real fact
  and is never a numeric input) applies to institutional facts on the same
  terms as any other domain.

## Consequences

Positive consequences:

- Institutional causal chains stay auditable back to an `AgentDecision` or
  engine-owned fact, never to unverifiable prose.
- Adding narrative flavor to institutional events cannot silently expand what
  the institution can materially do.

Costs and boundaries:

- Any new institutional feature that wants "the LLM decides X" must first
  express X as a `DomainAffordance` option or a typed decision field with
  engine-computed parameters; free-form text output is not an acceptable
  substitute.
- This ADR does not relax or duplicate ADR 0004; it is scoped to naming the
  institutional entities the general rule already covers.
