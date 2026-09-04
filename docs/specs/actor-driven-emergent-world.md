# Actor-Driven Emergent World

## Status

Frozen architecture approved on 2026-09-04. Reopen the backbone only when
implementation or long simulations demonstrate a concrete limitation.

## Core causal loop

```text
canonical state
-> grounded readings and transient affordances
-> independent actor decision
-> commitment or action
-> canonical owner revalidates and executes
-> Event + StateDelta + causal links
-> memory, relations, and new conditions
-> future decisions
```

An actor deciding is not the same as an actor mutating the world. LLMs may
select among engine-enumerated affordances and interpret outcomes. They never
invent evidence, quantities, targets, terms, authority, physical laws, or
state changes.

## Domain contracts

### Institution, office, authority, and leadership

- `Institution` is the durable identity that owns institutional relations and
  commitments.
- `InstitutionalOffice` is a role inside an institution and declares authority
  scopes.
- `AuthorityClaim` is a concurrent claim over an office. Its lifecycle is only
  `active`, `withdrawn`, `defeated`, or `expired`.
- Formal recognition is relational, perceived legitimacy belongs to an
  observer's knowledge/readings, and material control is derived from canonical
  territory, administration, resources, and forces.
- `InstitutionalAuthorityState` owns institutions, offices, concurrent claims,
  and identity anchors. `InstitutionalRelationsState` and
  `InstitutionalKnowledgeState` remain separate World-owned states.
- Formal recognition lives in the relations state and references an
  `AuthorityClaim` ID, never a loose office holder. Authority loads before
  relations so that this reference can be validated.
- A claim never grants territory, troops, resources, treasury access, or
  authority merely by existing.
- The engine must deterministically answer
  `can_actor_act_for(actor, institution, scope)` from current state.
- Institutional decisions may use the institution itself as `actor_ref`; the
  office and current holder authorize that actor rather than replacing it.
- `CityGovernance` remains the V1 owner of material urban administrative
  control.
- Leaders remain Avatars. Institutions and their obligations survive a change
  of leader.
- In V1 a city institution is identified by its `CityRegion`. All cross-domain
  references use `EntityRef` so institution and location may be separated in a
  later schema without treating their current identity as a timeless domain
  truth.

### Institutional relations, commitments, and memory

- Replace `SectDiplomacyState` with a World-owned
  `InstitutionalRelationsState` containing only institutional relations,
  commitments, active institutional memories, and formal recognition.
- It must never own resources, population, territory, projects, strategy,
  capacity, or decisions.
- `InstitutionalCommitment` contains independent terms. Term states are
  `proposed`, `active`, `fulfilled`, `breached`, `remediation_proposed`,
  `remediated`, `cancelled`, or `expired`; aggregate status is derived.
- A term stores the immutable mechanical parameters enumerated by the engine
  and accepted by the parties, including engine-computed quantities. It does
  not own or reserve the stock needed for later fulfillment.
- Commitments are obligations, not scheduled commands. Fulfillment and
  remediation require a new decision, a current affordance, material
  feasibility, authority, and execution by the canonical owner.
- Remediation resolves the current obligation but never erases the historical
  breach.
- A missed due date may produce a deterministic breach or expiry fact, but
  never performs the promised material action automatically.
- `InstitutionalKnowledgeState` is the sole owner of which institution knows a
  fact.
  `InstitutionalMemory` records only how much a known canonical fact matters to
  an institution. Every memory references canonical event IDs.
- Active memory has salience, decay, and reinforcement. Engine-owned historical
  weight uses only relative scale, institutional change, commitment breach,
  and impact on an `InstitutionalIdentityAnchor`.
- Identity anchors reference canonical founders, headquarters/capitals, core
  relics, sacred sites, or founding commitments.

### Capacity, conflict, and perspectives

- Strategic capacity is multidimensional: administrative, diplomatic,
  military, logistics, and project capacity.
- `CasusBelliReading` contains perceived cause, credibility, objective, reach,
  urgency, expected cost, expected gain, and available alternatives. Missing
  evidence remains unknown.
- Deliberate betrayal requires a known active commitment, understood
  incompatibility, and a deliberate incompatible action. Motivation explains
  the choice but is not a mechanical prerequisite.
- Civil disorder may develop through protest, strike, riot, mob violence,
  civic movement, rebellion, and revolution. A riot needs no leader; rebellion
  requires organization, leadership, and material capacity.
- The Heavenly Dao is omniscient. Actor perspectives are optional filters and
  never remove the Dao's access to canonical truth.

## First vertical

```text
urban pressure
-> city decides whether to request aid
-> recipient institution decides independently
-> multi-term commitment
-> material transfer or project
-> fulfillment, refusal, breach, or remediation
-> institutional memory and relationship change
-> future decisions
```

The vertical must reuse existing city pressure, economy, stocks, reservations,
routes, projects, `DomainAffordance`, owners, causal recorder, and Why query.
It must not create a parallel planner, logistics state, treasury, resource, or
story-driven execution path.

## Delivery waves

1. Record vocabulary and ADRs for concurrent authority, institutional
   relations, knowledge versus memory, and prose never being a material cause.
2. Add institutions, offices, claims, relations, memories, identity anchors,
   multi-term commitments, persistence, and rollback.
3. Replace sect diplomacy with the shared institutional state and remove the
   obsolete path.
4. Deliver the urban-pressure aid vertical end to end.
5. Route decisions through transient `DomainAffordance` options or `NO_ACTION`,
   with owner-side recomposition and stale-option rejection.
6. Add fulfillment, breach, remediation, memory decay/reinforcement, and their
   effect on future decisions.
7. Expose the full chain through API and Dao UI.
8. Generate factual prehistory from engine-enumerated valid episodes; LLMs may
   select and interpret, while owners execute canonical effects.
9. Make nearby water a flood vulnerability rather than a permanent flood load;
   grounded hydrology feeds the same institutional response loop.
10. Compose commerce, war, religion, and civil disorder from these primitives.
11. Consider intrigue, conspiracy, and mythical threats only after long-run
    evidence.

Each wave must work end to end before expanding the next one. Preserve and
integrate the existing Avatar activity UI WIP.

## Acceptance

- Invented or stale affordances, targets, and terms cause no mutation.
- Requests, responses, fulfillment, and remediation are independent decisions.
- Decision facts carry `AgentDecision` without `StateDelta`; the canonical
  owner's separate transition event carries deltas and links back to the
  decision.
- Owners revalidate stocks, routes, capacity, authority, and scopes.
- A leadership change preserves institutional commitments, relations, and
  memory.
- Concurrent claimants may diverge in recognition, perceived legitimacy, and
  material control.
- A claim without material control cannot perform actions it cannot actually
  authorize or supply.
- A breach remains a navigable fact after accepted remediation.
- Knowledge and memory have one owner each; every memory links to canonical
  facts.
- Stories and LLM prose never emit `StateDelta` or become material causes.
- Save/load preserves institutional state and causal evidence but never
  transient affordances.
- Monthly rollback restores institutional state, events, relationships,
  commitments, calendar, and RNG together.
- A 120-month natural smoke accepts stability while requiring zero broken
  causes and zero Story-originated mutations.
- A deliberately pressured 120-month smoke requires at least one complete,
  navigable, materially valid institutional chain.

## Frozen boundaries

- Do not add a separate `CityInstitution` in V1.
- Do not add more historical-weight factors without simulation evidence.
- Do not add a church owner, political faction layer, imperial treasury,
  parallel territorial-war engine, or second planner.
- Religions emerge from existing Sects, orthodoxies, claims, presence, and
  material actions.
- Population remains aggregate until real organization and named leadership
  emerge.
- Physically grounded stochastic events remain allowed.
- New schemas may explicitly reject old saves, but existing save data must not
  be deleted or destructively migrated.
