# Ubiquitous Language

## Celestial Dao

The player-visible authority that can remain silent, issue an observable sign,
or grant a limited favor. It never completes another domain's objective.

## Dao Tradition

A persistent regional interpretation of the one Celestial Dao. It is not an
Orthodoxy, sect, church, or temple system.

## Dao Petition

A World-owned rare audience opened only after explicit institutional
sponsorship of grounded popular rites. It names its institution, region,
motivating facts, sponsored rite events, and response state.

## Royal House

The Dynasty-owned set of living or historical Avatar IDs recognized as members
of the ruling house. Marriage can add a spouse to the house. Royal blood is a
separate Dynasty-owned ID set inherited through birth; marriage alone never
creates royal blood. Personal kinship remains owned by Avatar relations.

## Imperial Crisis

A Dynasty-owned challenge or succession with an optional incumbent and several
independent Imperial Claims. It can change the dynasty's sovereign reference
but does not create territorial war or delete an Avatar.

### Imperial Claim

One candidate's pretension inside an Imperial Crisis. It owns that candidate's
status, official positions, evaluations, evidence, and winner flag. An official
may support at most one claim and may oppose several; neutrality is the absence
of a recorded position.

## Fact and Story

A Fact records an occurrence, decision, derived condition, or owner-applied
state transition. A Story is a non-mechanical interpretation of one or more
Facts. A Story carries no StateDelta and cannot be the cause of a mutation; it
points back to its factual source through a causal contribution link.

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

### Domain Affordance

A Domain Affordance is a transient, deterministic option that the current
canonical state makes available to one collective-domain actor. It names an
engine-owned action, current targets, engine-calculated parameters, urgency,
and motivating fact IDs. It is recomputed before execution and never persisted.
An interpreter may select its ID or maintain the current state; it may not
invent the action, target, quantity, or delta.

## Domain Reaction

A Domain Reaction is a typed interpretation of all current Domain Affordances
by a collective actor. It selects one offered ID or maintains the current
state. The owning domain recomputes the options, rejects stale IDs, and applies
any resulting change.

### Relationship Impact

A Relationship Impact is a qualitative interpretation of an interaction in
each direction: positive, negative, neutral, or ambivalent, with mild,
moderate, or strong intensity. The relationship owner maps intensity to the
fixed magnitudes 2, 4, or 6 and limits allowed valences for the action outcome.
Neutral and ambivalent interpretations change no friendliness. Generated prose
is never parsed as a numeric relationship delta.

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

### Operational Route Capacity

Operational Route Capacity is the usable transport capacity of an Explicit
Route after its own quality and every explicitly linked Infrastructure Site
are considered. The least available linked site is the bottleneck. It is a
derived observation: the Route retains its nominal capacity and each site
retains its own condition.

## Infrastructure Site

An Infrastructure Site is a stable, map-owned physical entity attached to
explicit cells and Regions. It records spatial identity, condition, declared
capabilities, and references to existing routes or water bodies. It does not
own route throughput, regional stocks, production, urban services, or the
effects that another domain may later derive from it.

### Site Condition

Site Condition is the canonical `integrity` and `enabled` state of one
Infrastructure Site. A validated change produces an Event, StateDelta, causal
source link, and domain invalidation. The site owner never directly alters a
route, city, population, organization, or economy; a dependent owner may
derive and record its own mechanically afforded consequence.

### Operational Site Capacity

Operational Site Capacity is a regional observation of how many fully intact
site-equivalents currently declare one capability. Each enabled Infrastructure
Site contributes its integrity; a disabled site contributes zero. This reading
measures grounded operational presence only. It is not production, throughput,
service capacity, stock, or permission to mutate another domain.

## Institutional Presence

**Urban Governance**:
The explicit institution administratively responsible for a CityRegion,
together with that city's ability to coordinate public action. It is not a
claim over surrounding territory and is not implied by nearby sect influence.
_Avoid_: Regional ownership, territorial sovereignty

**Sect Spatial Influence**:
The current reach of a Sect across physical space, derived from its grounded
headquarters, members, power, and competition with other Sects. Influence does
not by itself grant government, ownership, or permission to begin a war.
_Avoid_: Sect ownership, automatic occupation

**Regional Institutional Presence**:
A read-only view of Urban Governance and Sect Spatial Influence within one
Region. It exposes overlap between institutions without becoming another owner
of either state.
_Avoid_: Regional controller, political faction

### Regional Semantic Evaluation

Regional Semantic Evaluation is the deterministic application of an accepted
region-scoped definition to any Region whose canonical evidence can answer the
definition's metric questions. It is distinct from Semantic Discovery and from
Domain Reaction. An unknown reading creates neither a Condition Instance nor
evidence that the definition was reused in that Region.

### Regional Semantic Discovery

Regional Semantic Discovery is the controlled proposal of reusable vocabulary
from an uncovered metric surface that is measurable in a canonical Region.
The LLM receives metric schemas and provenance-backed target context, never
authority to write values or effects. Equivalent surfaces share retry and
deduplication state, and every proposal still passes deterministic validation
before it can enter the world's semantic registry.

## Physical Geography

Physical Geography is the map-owned, map-local description of terrain,
elevation, and water independent of which Region occupies the same space. It is
static geographic truth, not a condition or a visual overlay.

### Map Projection Layer

A Map Projection Layer is a removable visual reading of canonical map or
domain state. Terrain, elevation, water, regional boundaries, explicit routes,
sect territories, and names can be shown or hidden without changing the world.
An explicit route drawn between region anchors is topological evidence of a
connection, not a claim about its exact cell-by-cell path.

### Region Footprint

A Region Footprint is the set of map cells occupied by one Region. It expresses
semantic territory and may overlap many kinds of Physical Geography without
changing them.

### Terrain Cell

A Terrain Cell is one map location's physical land or water surface. Cities,
Sects, ruins, and other sites may occupy it, but they are not terrain kinds.

### Water Body

A Water Body is a map-owned river, lake, or sea attached to explicit cells. A
river additionally has a stable flow direction so upstream and downstream
relationships can be derived without relying on narrative text.

## Regional Weather

Regional Weather is the month-scoped physical precipitation and soil
saturation owned by `World.climate_state` for one Region. It is deterministically
grounded in the current month and physical geography; it does not own terrain,
water bodies, infrastructure, or consequences.

### Regional Hydrology Projection

A Regional Hydrology Projection is a read-only interpretation of Regional
Weather, map-owned geography, and real water-management Infrastructure Sites.
It exposes grounded mechanical readings and never becomes a parallel state
owner.

### Flood Risk

Flood Risk is a derived observation of hydrological exposure. It is not a flood
occurrence and cannot damage assets, close routes, move population, or change
another domain without a separately validated domain action.

### Regional Flood Occurrence

A Regional Flood Occurrence is active physical surface flooding in one Region,
owned by `World.regional_flood_state`. It begins only after grounded Flood Risk
remains high for the required persistence window and resolves only after a
separate low-risk persistence window. The occurrence is a real world state and
public causal fact, but it does not itself assert damage, disease, displacement,
route closure, or any other downstream consequence.

### Hazard Exposure

Hazard Exposure is a read-only measurement of how strongly one material hazard
reaches one canonical spatial target. It is derived from the hazard occurrence,
the target's real location, physical geography, and grounded protective
capabilities. Exposure is evidence, not damage.

### Hazard Impact Proposal

A Hazard Impact Proposal is a typed request for a target's canonical owner to
apply one bounded effect. The proposal never mutates the world directly. Before
acceptance, the engine recomputes the target's Hazard Exposure and the maximum
afforded magnitude; the owner then validates and records the actual transition.

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

### Regional Essence Profile

Regional Essence Profile is the five-element essence distribution owned by a
CultivateRegion. A region without that canonical substrate has an unknown
profile; absence of data is not zero essence.

### Grounded Spiritual Anchor

A Grounded Spiritual Anchor is an existing grave, treasure, or active formation
whose origin is linked to a real event. Its presence may be measured and used as
context, but does not by itself assert a ghost, curse, blessing, danger, or any
other manifestation.

### Spiritual Activity Condition

A Spiritual Activity Condition is an observational condition derived from
measurable regional essence and Grounded Spiritual Anchors. It describes a
persistent concentration of known spiritual evidence. It never creates an
entity, causes damage, changes essence, or grants an effect directly.

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

## Monthly Resource Balance

Monthly Resource Balance is the net change to a region's canonical resource
stock after its declared production and demand for one month are reconciled.
Production and demand remain measurable flows, but when they cancel each other
there is no stock transition fact to report.

## Institution

An Institution is the durable identity that owns institutional relations and
commitments across a change of leader. In V1 a city institution is identified
by its `CityRegion`; this is the current V1 identity, not a timeless domain
truth, and all cross-domain references use `EntityRef` so institution and
location may separate in a later schema.

### InstitutionalOffice

An InstitutionalOffice is a named role inside an Institution that declares one
or more authority scopes. An office exists independently of who currently
holds it.

### AuthorityClaim

An AuthorityClaim is a concurrent claim over an InstitutionalOffice. Its
lifecycle is exactly `active`, `withdrawn`, `defeated`, or `expired`. A claim
never grants territory, troops, resources, treasury access, or authority by
merely existing; the engine deterministically answers
`can_actor_act_for(actor, institution, scope)` from current canonical state.

### Authority Scope

An Authority Scope is the declared boundary of what an InstitutionalOffice may
authorize. It is distinct from Formal Recognition and from material control:
an actor may hold a scope without the territory, forces, or resources needed
to exercise it.

### Formal Recognition

Formal Recognition is a relational fact about who or what acknowledges an
AuthorityClaim. It always stores the claim ID, never a loose office holder. It
is independent from perceived legitimacy,
which belongs to an observer's knowledge and readings, and from material
control, which is derived from canonical territory, administration, resources,
and forces. Concurrent claimants may diverge in recognition, perceived
legitimacy, and material control at the same time.

## Institutional Relation

An Institutional Relation is a World-owned fact between two Institutions,
held in `InstitutionalRelationsState`. `InstitutionalRelationsState` never
owns resources, population, territory, projects, strategy, capacity, or
decisions; it is separate from `InstitutionalAuthorityState`, which owns
institutions, offices, claims, and identity anchors. Recognition records live
in the relations state and reference a claim ID loaded from the authority
state; a missing claim is invalid.

### Institutional Commitment and Term

An Institutional Commitment is an obligation between Institutions composed of
independent Terms. Each Term preserves the immutable mechanical parameters
enumerated by the engine and accepted by the parties, including an
engine-computed quantity where relevant. It neither owns nor reserves the
canonical stock needed later. A Term's state is exactly `proposed`, `active`,
`fulfilled`, `breached`, `remediation_proposed`, `remediated`, `cancelled`, or
`expired`; the Commitment's aggregate status is derived from its Terms, never
stored independently. A Commitment is an obligation, not a scheduled command:
fulfillment and remediation each require a new decision, a current
affordance, material feasibility, authority, and execution by the canonical
owner. A missed due date may deterministically produce a breach or expiry fact,
but never a material transfer. Remediation resolves the current obligation but
never erases the historical breach.

## Institutional Knowledge

An Institutional Knowledge record belongs to `InstitutionalKnowledgeState` and
answers only whether an Institution knows a canonical event. It identifies the
institution, event, acquisition channel, and acquisition event/month. It does
not store salience and does not forget facts in V1.

## Institutional Memory

An Institutional Memory records only how much a known canonical fact matters
to an Institution; it never decides who knows that fact. Every memory
references canonical event IDs. Active memory has salience, decay, and
reinforcement; engine-owned historical weight uses only relative scale,
institutional change, commitment breach, and impact on an
InstitutionalIdentityAnchor.

### Institutional Identity Anchor

An InstitutionalIdentityAnchor is owned by `InstitutionalAuthorityState` and
references a canonical founder, headquarters or capital, core relic, sacred
site, or founding commitment. It exists to give Institutional Memory a stable
reference for historical weight, not to add a new mutable domain state.

## Strategic Capacity

Strategic Capacity is a derived, non-persisted reading of what an Institution
can currently sustain: administrative, diplomatic, military, logistics, and
project capacity. Each dimension is read from canonical state and is never a
single aggregate score.

## Casus Belli Reading

A CasusBelliReading is one actor's interpretation of a potential conflict. It
contains perceived cause, credibility, objective, reach, urgency, expected
cost, expected gain, and available alternatives. Missing evidence remains
unknown; it is never replaced by a fabricated value. An ImperialCrisis
produces AuthorityClaims, not CasusBelliReadings by itself.
