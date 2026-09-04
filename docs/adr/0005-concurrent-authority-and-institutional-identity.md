# ADR 0005: Concurrent Authority and Institutional Identity

- Status: Accepted
- Date: 2026-09-04
- Scope: Institution, InstitutionalOffice, AuthorityClaim, InstitutionalAuthorityState

## Context

Leadership, formal recognition, perceived legitimacy, and material control are
four different facts that earlier designs were at risk of collapsing into one
boolean "who is in charge." A single owner cannot answer contested succession,
partial recognition, or a claimant who holds an office on paper but no troops
or treasury to exercise it. Leaders are Avatars and can die, retire, or be
replaced; institutional obligations must outlive that change.

## Decision

- `Institution` is the durable identity that owns institutional relations and
  commitments. It survives a change of leader.
- `InstitutionalOffice` is a role inside an institution and declares one or
  more authority scopes. An office is not the person who holds it.
- `AuthorityClaim` is a concurrent claim over an office. Its lifecycle is
  exactly `active`, `withdrawn`, `defeated`, or `expired`. Nothing else moves
  a claim between states.
- A claim never grants territory, troops, resources, treasury access, or
  authority merely by existing. `can_actor_act_for(actor, institution, scope)`
  is answered deterministically from current canonical state, never cached or
  inferred from prose.
- Formal recognition, perceived legitimacy, and material control are three
  separate facts. Formal recognition is relational and always references an
  `AuthorityClaim` ID, never a loose office holder. Perceived legitimacy
  belongs to an observer's knowledge and readings. Material control is
  derived from canonical territory, administration, resources, and forces.
  Concurrent claimants may diverge on all three at once.
- `InstitutionalAuthorityState` owns institutions, offices, claims, and
  identity anchors. It is a separate state object from
  `InstitutionalRelationsState` (ADR 0006); neither may absorb the other's
  responsibility.
- In V1, a city institution is identified by its `CityRegion`. This is the
  current V1 identity, not an eternal domain truth: all cross-domain
  references use `EntityRef` so institution and location can separate in a
  later schema without a breaking migration of every reference.
- `ImperialCrisis` produces `AuthorityClaim`s for the contested office; it does
  not itself grant territory, recognition, or material control, and it does
  not replace `InstitutionalAuthorityState` as the owner of claim lifecycle.
- `ImperialClaim.status=active|withdrawn|failed|ascended` projects to the
  general lifecycle as `active|withdrawn|defeated|expired`. Ascension is
  represented by the office holder changing plus the winning claim closing;
  there is no fifth global claim status.
- `CityGovernance` remains the V1 owner of material urban administrative
  control. An authority claim or formal recognition never duplicates it.

## Consequences

Positive consequences:

- Contested succession, partial recognition, and powerless titleholders are
  all representable without special-casing.
- Institutional obligations do not need to be rewritten or re-authorized every
  time a leader changes.
- A later schema can separate institution identity from `CityRegion` without
  invalidating existing `EntityRef`-based references.

Costs and boundaries:

- Callers must not shortcut `can_actor_act_for` with a cached or remembered
  answer; it is recomputed from current state.
- `CityRegion`-as-institution-identity remains a V1 simplification and must
  not be documented or coded as a permanent architectural truth.
- Do not add a separate `CityInstitution` type in V1; the frozen boundary in
  the spec still applies.
