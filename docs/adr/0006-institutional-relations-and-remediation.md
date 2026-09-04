# ADR 0006: Institutional Relations, Multi-Term Commitments, and Remediation

- Status: Accepted
- Date: 2026-09-04
- Scope: InstitutionalRelationsState, InstitutionalCommitment, Term, remediation

## Context

`SectDiplomacyState` couples relations to one organization type and treats a
commitment as a single flag rather than an obligation with independent parts
that can each succeed, fail, or be repaired. This blocks reuse across other
institutions and hides the difference between "we agreed to something" and
"the agreed thing actually happened."

## Decision

- Replace `SectDiplomacyState` with a World-owned `InstitutionalRelationsState`
  containing only institutional relations, commitments, active institutional
  memories, and formal recognition. It never owns resources, population,
  territory, projects, strategy, capacity, or decisions; those remain with
  their existing canonical owners.
- `InstitutionalRelationsState` is separate from
  `InstitutionalAuthorityState` (ADR 0005).
  Relations and commitments are not a channel for granting or contesting
  authority.
- `InstitutionalCommitment` contains independent Terms. A Term's state is
  exactly `proposed`, `active`, `fulfilled`, `breached`,
  `remediation_proposed`, `remediated`, `cancelled`, or `expired`. The
  Commitment's aggregate status is derived from its Terms and is never stored
  as an independent field that could disagree with them.
- A Term stores the immutable mechanical parameters enumerated by the engine
  and accepted by the parties, including an engine-computed quantity when the
  obligation is quantitative. Those parameters make the promise auditable;
  the Term does not own or reserve canonical stock.
- Commitments are obligations, not scheduled commands. Fulfillment and
  remediation each require: a new decision, a current affordance, material
  feasibility, authority, and execution by the canonical owner. A missed due
  date may deterministically produce a breach or expiry fact, but it never
  executes a material transfer or project.
- Remediation resolves the current obligation but never erases the historical
  breach. The breach fact remains navigable after accepted remediation; a
  remediated Term reads as "breached, then remediated," not as if the breach
  never happened.
- This ADR removes the obsolete `SectDiplomacyState` path rather than keeping
  it as a compatibility layer; sect diplomacy consumers migrate to
  `InstitutionalRelationsState`.

## Consequences

Positive consequences:

- Any two institutions, not only sects, can hold relations and commitments
  through the same state and the same rules.
- A commitment with several independent terms can partially succeed, partially
  breach, and be partially remediated without losing precision.
- Historical accountability survives remediation, so an institution cannot
  launder a breach out of the record by fulfilling a later term.

Costs and boundaries:

- Every fulfillment or remediation path must go through decision, affordance,
  feasibility, and authority checks; none may write a Term transition directly.
- Authority state loads before relations state. A formal recognition record
  stores a claim ID and is invalid if that claim is absent.
- `InstitutionalRelationsState` must not accumulate resource, territory, or
  capacity fields as a convenience; those additions belong to their owning
  domains.
- Removing `SectDiplomacyState` is a breaking change to that code path by
  design; no fallback or dual-write period is introduced.
