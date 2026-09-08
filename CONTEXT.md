# Ubiquitous Language

## Current implementation ledger (2026-09-04)

The current working tree contains the institutional backbone pieces through the
urban aid vertical: authority, relations, knowledge and memory remain separate
World-owned state; aid uses independent request/response decisions, multi-term
commitments, canonical delivery, bounded breach chaining, remediation, and
factual causal links. Memory decay/reinforcement is bounded and leader context
uses factual evidence only. SQLite schema 3 uses a required, versioned sidecar
with atomic publication; when overwriting an active save the old sidecar is
retained intentionally, with a known disk-growth limitation and no automated
sweep or live-data cleanup. Causal storage has lazy bulk links and a detailed
causal getter. Three institutional commitment locale templates (en-US, pt-BR,
zh-CN, neutral for aid and reciprocal exchange alike) match actual payload
interpolation. Wave 6 is not wholly complete: qualitative institutional
relationship impacts are implemented with enabled defaults (evaluation 8,
LLM budget 2), while aid `identity_anchor_impact` is currently zero. Each
observer independently makes a typed choice through the audited decision and
owner transition, with bounded friendliness changes of +/-2, +/-4, or +/-6;
`maintain`, `neutral`, and `ambivalent` produce no delta. The scalar is a
shared bilateral climate, not a private attitude, and no automatic formal
alliance/war kind changes occur.

Wave 7 local API/UI institutional-chain integration is implemented and verified
by focused tests; it is not browser/live-deployment acceptance. Region, Sect and
Dynasty surfaces have an actual path, with API/Why restoration complete.
Root-consolidated evidence is 218 backend tests passed in 52.56 seconds;
frontend build/typecheck succeeded and the final consolidated UI rerun passed
32/32 tests, including the 21 Why tests. Final audited 120-month artifacts
succeeded: natural has 3,200 events and causal depth 17; pressured has 3,661
events, causal depth 10, and 20 economic transfers.
Both report zero broken causes, out-of-window links, Story mutations, provider
calls/awaits, and Story material ancestors. Pressured proves the exact seven-event
witness chain and linked memory; absence of a required fulfillment witness is
valid in the natural scenario. Runtime tests also cover same-month refusal,
injected real-owner +6 and -2 choices yielding 4, roundtrip/replay/rollback,
and factual context/known-fact handling; current-authority and stale-counterpart
guards are implemented and reviewed.
At capture time, both artifacts still contained 147 untyped events and 27
conditions activated/0 resolved, so that evidence was not full production-world
quality proof. No whole-roadmap claim is valid.

### Validation evidence (2026-09-06)

Fresh artifacts under `/tmp/cws-validation-20260906/` record natural120 with
3,194 events and causal depth 16, and pressured120 with 3,666 events, causal
depth 10, and 20 economic transfers. Both audits are true and report zero
broken causes, out-of-window causes, story mutations, and provider calls or
awaits. The 27 activated conditions decompose into 8 positive conditions and
19 healing-access deficits (aggregate/group readings). That counter tracks
`semantic_condition` activations only; it says nothing about hydrology, and no
conclusion about flooding may be drawn from it. Floods are counted separately
in the artifacts' own `event_types`: the historical
`/tmp/cws-validation-20260906/natural.json` records 5
`regional_flood_started` and 5 `regional_flood_resolved`, and the newer
`/tmp/cws-wallet-natural120.json` records 4 and 4. Healing access is grounded
in the five classic CityRegions, with
declared demand and existing healing assets, but only roughly 9%-22% baseline
access; `CityState`/urban capacity projects remain the canonical capacity owner.

The historical 147-untyped-event observation above predates the current causal
correction checkpoint. `sect_annual_settlement` now emits a typed
`DETERMINISTIC` transition with `StateDelta` evidence owned by the canonical
Sect/Avatar domains, using `.value`-serialized before/after values for
treasury/upkeep/weariness. `celestial_phenomenon_update` now emits an
`EXTERNAL_EVENT` typed fact with explicit stochastic catalog-sampling evidence
and deltas for phenomenon ID/start-year changes. Existing calculations,
sampling cadence and same-ID reselection remain unchanged; neither path
fabricates an `AgentDecision`.

These two diagnosed gaps are now implemented, but this was not a claim that all
causal-coverage gaps were solved. At that checkpoint, gathering and story
events and hidden-domain mutations were still untyped, and the MagicStone
double-truth mutation was still an open risk; both are addressed further below
and this paragraph is kept as the state at that point, not as current state.
The smoke audits only validate the causal links and invariants they
inspect; they do not prove coverage of every canonical mutation. The definitive religious long smoke
now adds
`tests/test_sponsorship_long_smoke.py`: one pressured 120-month run passed in
154.14s with no provider calls, Story deltas, broken causes, or out-of-window
causes; Ruff also passed. Its existing world factory places the canonical
emperor in city 305 and synchronizes one titular patriarch into authority.
Injected policies choose only canonical `SponsorDaoRite`/Rest options and a
positive mild witness reaction; the popular rite is produced by the engine,
not a fake fixture event. It proves the exact decision -> sponsorship ->
`MEMBER_WITNESS` -> independent typed reaction/receipt chain. This is an
in-memory pressured-world witness: it does not prove SQLite roundtrip or
natural probability, does not cover every world's ancestry, and its global
story-mutation assertion is not equivalent to full mutation coverage.

An independent focused selection over 8 files passed 77 tests in 9.52s; Ruff
passed for the 4 changed Python files, and `git diff --check` is clean. The
natural120 owner-delta artifact at
`/tmp/cws-owner-deltas-natural120.json` recorded 3,198 events, causal depth 17,
and 5 untyped events (down from the historical 147), with `audit=true`, zero
broken causes, zero out-of-window causes, zero Story mutations, and zero
provider calls or awaits. This is focused evidence only: it is not a full-suite
claim, does not establish zero untyped events, and does not prove global
mutation coverage.

`MagicStone` no longer carries two numbers. It was an `int` subclass that also
stored the amount in a `.value` attribute, and its in-place `__iadd__` and
`__isub__` updated only that attribute while the immutable `int` base stayed
frozen -- so after `wallet += 50` a wallet created at 100 answered 150 to
`.value` and 100 to `int()`, and any owner building evidence from the stale
read produced a wrong `before`. It is now an immutable amount: `.value` is a
read-only property derived from the object itself, so the two reads cannot
disagree; `+` and `-` return a new `MagicStone`, so `+=` rebinds the holder's
attribute instead of mutating an object other holders alias; and operands go
through `operator.index`, which accepts `int` and `MagicStone` and rejects a
string or a float rather than parsing `"10"` or truncating `1.9`. The two
remaining `.value` writes in production, `fortune.py` 535 and 747, became
canonical wallet assignments. No gain or loss rule changed, no clamp was added,
no compatibility setter or migration exists, and the test fixtures that wrote
`.value` directly now assign a real `MagicStone`.

Read the untyped-event snapshots in order. The 147 figure predates both the
typed annual sect settlement and the celestial phenomenon typing. The 5 figure
was captured *after* those two landed, and *before* the wallet correction
described here and before the `hidden_domain`, story and tournament typing
below. Neither reflects the current tree.

The current figure is 0. Root's final artifact
`/tmp/cws-wallet-typed-final120.json` records 3,191 events at causal depth 16
with 0 untyped events, `audit=true`, and zero broken causes, out-of-window
causes, Story mutations, and provider calls or awaits. Read that scope
literally: it is **one** natural 120-month world run without a provider. It is
not a multi-world result, not a pressured-scenario result, and not a full-suite
claim; a single world reaching zero untyped events does not establish that
every canonical mutation everywhere is typed.

The annual sect settlement emits a typed `sect_annual_settlement` carrying one
delta per field that really changed on its Sect and Avatar owners,
`STATE_TRANSITION` when anything moved and `OCCURRENCE` when nothing did, with
an engine-owned breakdown of the income, upkeep, net change and war inputs it
used. Alongside it, `hidden_domain_opened`, `hidden_domain_injury`,
`hidden_domain_empty_handed`, `action_story` and `gathering_story` are now
typed as well, with no new effect and no rule change. A tournament cancelled
for insufficient participants is likewise typed `tournament_cancelled` as a
delta-free `OCCURRENCE`: the cancellation moved no owner's state, and its
trigger condition is untouched.

Root's independent selection over 12 files passed 115 tests in 60.56 s, and the
final wallet/tournament/hidden-domain/story/month-rollback subset passed 45
tests in 5.52 s; those two overlap and must not be summed. `ruff check` passed
on all 18 changed files and `git diff --check` is clean.

Hidden-domain treasure is now factual as well. The loot rules are unchanged --
the same drops, the same prices, the same automatic equipping, the same RNG --
but the mutations that path already performed are recorded on a typed
`hidden_domain_treasure` fact. Its `causal_origin` is `EXTERNAL_EVENT`, because
loot is drawn by the world and nobody chose it, so no decision is cited or
fabricated. It carries one delta per canonical save field that really moved,
read back after the Avatar's own setters ran: `weapon_id`,
`weapon_proficiency`, `auxiliary_id`, `technique_id`, `magic_stone` and `hp`.
Re-equipping the same item ID therefore records no equipment change while
still recording the proficiency reset `change_weapon` performs, and a repeated
technique records nothing at all and stays an `OCCURRENCE`. The `hp` delta
exists because both equipment setters call `recalc_effects`, which clamps
`hp.cur` down when new gear lowers maximum HP; losing max HP is not an injury
and is deliberately not routed through the injury owner. Derived values such
as max HP and max lifespan are recomputed from effects and are not duplicated
as state. The structured `hidden_domain_loot` account holds JSON primitives
only -- domain, avatar, loot kind/ID/name, target realm, the effective
`drop_prob` that draw already used, the replaced item ID and the actual resale
amount -- and the fact links back to the real `hidden_domain_opened` of the
same step as `ENABLED_BY`, since entering the domain permitted the draw rather
than causing a reward. Stories remain non-causal and carry no delta.

Evidence for this slice is focused: `tests/test_hidden_domain_loot_causality.py`
passes 11 tests covering weapon, auxiliary with and without an old item to
resell, technique, the same-ID no-ops, the max-HP clamp, a SQLite round trip
that stores the opening too and reads the stored causal link back to it, and a
real failed month transaction through `SimulationPhaseRunner` that restores
equipment, proficiency, wallet, calendar, event count and RNG state together.
Root's independent verification passed 62 tests in 7.37 s over exactly
`tests/test_hidden_domain_loot_causality.py`, `tests/test_hidden_domain.py`,
`tests/test_story_event_service.py`, `tests/test_magic_stone_wallet.py`,
`tests/test_month_transaction.py`, `tests/systems/test_fortune.py` and
`tests/test_tournament.py`, with scoped `ruff check` and `git diff --check`
clean. Note that `tests/test_hidden_domain_loot_causality.py` is a new,
untracked file and has to be named explicitly to be collected.

The auction now closes its authorship instead of hiding it. Bidding really is
an actor choice, so it is recorded as one: `auction_bid_decision` is a
`DECISION` fact per participating actor, built from a validated selection
*before* any effect, whose `AgentDecision.source` is the existing
`ChoiceSource` value -- `llm` when a model really selected, `fallback` (with a
`test_mode` or `unusable_answer` reason) when it did not. Its `causal_origin`
follows that honestly, `LLM_INTERPRETATION` or `DETERMINISTIC`; a choice is
never relabelled deterministic to make it look engine-owned.

The choice itself is now bounded. Each actor is asked on its own, with its own
context and its own call, addressed by ID rather than display name, and it
selects one of the engine's enumerated levels 1-5. Strict integer validation
rejects a bool, a float, a numeric string, an unknown lot key and any
out-of-range number outright: an invalid or omitted answer is no bid, never a
coerced one. The prompt, updated in all seven locales, now also states what
each level materially commits and shows the per-lot ceilings computed by the
engine's own `_calculate_bid` at that actor's current balance, so a level 5 no
longer secretly authorizes spending the whole wallet unseen; if that balance
changes before resolution, the bid is refused rather than settled on terms the
actor never saw.

A catalog ID is not a lot identity. Circulation holds independent instances
that can share an ID and compare equal, so a transient `AuctionLot` keyed by
offered position now carries the auction end to end -- prompt, resolver,
settlement and evidence -- replacing the old `dict[Item]` contract, which is
removed rather than wrapped. `CirculationManager.remove_item` was corrected to
remove the exact instance by identity and to return whether it did, so a sale
can no longer retire a different equal copy; settlement refuses a lot whose
instance is gone, and lots that left circulation between offer and resolution
are filtered out beforehand so they cannot consume a hypothetical budget and
depress later lots.

Settlement records what it moved: `auction_settled` is `ACTOR_DECISION`,
motivated by the winner's decision and contributed to by the runner-up's,
since the second price is that actor's doing. It carries deltas for
`magic_stone`, `weapon_id`, `weapon_special_data`, `weapon_proficiency`,
`auxiliary_id`, `auxiliary_special_data`, `hp`, `consumed_elixirs` and the
circulation pool count owned by the playthrough, with gross price and refund
stated even when they cancel out. It is also the single deal fact: the old
untyped duplicate event is gone, and the existing localized wording and
runner-up relation pair moved onto it. An unsold lot leaves circulation
through its own deterministic `auction_lot_unsold` fact, and a lot nobody bid
on is untouched -- no bid never destroys stock. Pricing, second price, tie
ordering, auto-equipping, refunds and the destruction of replaced equipment are
unchanged. A failed `consume_elixir` keeps the existing payment and removal and
records `elixir_consumed: false` with no elixir delta, so the loss is visible
rather than a phantom benefit; correcting that economics was deliberately out
of scope. The unreachable `Material` branch was removed.

Evidence: `tests/test_auction_causality.py` passes 27 tests, most of them
driving a full `execute` rather than a helper: strict level validation,
malformed answers leaving the whole auction untouched, test-mode abstention
through both the World RunConfig and the ContextVar with a provider proved
un-awaited, two actors sharing a display name asked once each by ID with the
runner-up's decision linked `CONTRIBUTED_TO` the second price, a runner-up
that goes stale after answering setting no price, duplicate catalog IDs as
separate lots, a stale first lot not depressing a later one, a changed balance
cancelling a bid, the failed elixir, the recorded owners and cited decision, a
SQLite round trip of the settlement and its decision link, and a failed month
that rolls back wallet, equipment, circulation, calendar and RNG.

Root's independent verification passed 100 tests in 12.10 s over exactly
`tests/test_auction.py`, `tests/test_auction_causality.py`,
`tests/test_circulation.py`, `tests/test_hidden_domain_loot_causality.py`,
`tests/test_magic_stone_wallet.py`, `tests/test_month_transaction.py`,
`tests/test_story_event_service.py`, `tests/test_llm_test_mode.py` and
`tests/test_causal_authorship.py`, with `ruff check` clean on the 4 changed
Python files and `git diff --check` clean. Note that
`tests/test_auction_causality.py` is a new, untracked file and has to be named
explicitly to be collected.

## Wave 10 civil disorder: a first partial slice (2026-09-06)

Wave 10 lists commerce, war, religion **and civil disorder**. The first three
have verticals; civil disorder had no code at all. This adds its smallest
end-to-end path, and **only** that path: `pressure -> population decision ->
public petition -> independent government answer -> existing material owners`.

`src/systems/civil_petition.py` owns the petition fact and nothing else.
A `file_public_petition` affordance is offered by `population_affordances`
**beside** the existing migration options, so the population may petition,
migrate, or do neither; `NO_ACTION` stays valid and no threshold forces a
protest. Availability is grounded in the mechanical grammar, not in an event
type or a disaster's name: only a condition whose metric dimension is `RISK`
or `LOAD` is a grievance, so a high `access` or `quality` reading offers
nothing. Filing additionally requires a real population, the condition to be
this region's registered live instance, a non-Story cause resolvable from the
step's own events or storage, and an institution that actually governs here.

This is protest, not rebellion: no organization, no named leader, no faction,
no prestige or hostility, no fabricated population, and no obligation. On
filing, only the addressed institution learns the fact, through
`KnowledgeChannel.FORMAL_NOTICE`, with **no** memory factors -- what a protest
is worth to a government has no engine-owned weight. The petition carries the
condition's cause as evidence and cites the population's own canonical
decision, which is validated by the shared `validate_actor_decision` and whose
id must match the cited one, before any knowledge or receipt is written.

The government phase runs before the population phase, so an answer arrives on
the next cycle. `enqueue_pending_petitions` finds unanswered petitions by a
bounded scan of the response window plus this step's events, and the
government answers the petition itself, with the condition still attached as
evidence. Authority is checked as an institution, never as a stand-in for its
current office holder: `can_actor_act_for` under `URBAN_ADMINISTRATION` with
material control, and the controller must be the one actually addressed, so a
region that changed hands answers nothing. That check is repeated during
recomposition after the interpreter's await, so losing authority mid-decision
empties the menu and blocks the reaction instead of mutating or raising.
Maintaining is a real answer and closes the petition; an act closes it only
once attempted, so exhausting the budget leaves the grievance pending rather
than burying it. Material responses remain the existing `_city_options`
maintenance and capacity-project owners; nothing auto-executes and no repair
is compelled.

The vertical is wired into the monthly step: `react_government` in the
canonical phase registry calls `enqueue_pending_petitions` with the step's own
events, so the government really answers in `Simulator.step` rather than only
under a direct helper call. Rebuilding the government's affordance context is
itself treated as a revalidation: authority, controller or condition changing
while the interpreter awaited blocks the reaction instead of raising and taking
the month down. The stale attempt is audited on the context captured *before*
the await, through the existing `stale_affordance_blocked_event`, and the
receipt keeps `act` with the selected affordance -- a blocked attempt does not
rewrite the actor's real choice into a maintain. That attempt happened, so it
closes the petition: it is not a retry. Retrying is the separate case of
budget exhaustion, where nothing is attempted at all and the grievance stays
pending for the next cycle.

Evidence: `tests/test_civil_petition.py` passes 17 tests -- detrimental-only
grounding, petition offered beside migration, uninhabited/ungoverned regions,
a free-standing condition object authorizing nothing, a step-local condition
still petitionable, the recorded fact with only the addressed institution
knowing and no memory, a mismatched decision id refused, the same grievance
not petitioned twice, a changed controller answering nothing, test-mode
reaching no provider, a SQLite round trip, and a month rollback reopening the
grievance. The end-to-end proof runs the real phases: `react_population`
produces the petition through the real interpreter with an injected choice,
the facts are persisted, the month advances, and `react_government` answers
with a specific `city_maintenance_completed` or `urban_capacity_project_started`
linked to that government decision and carrying a real owner transition -- not
merely any event that happens to hold a delta -- and a further month answers
nothing more. Budget exhaustion leaves the grievance pending and a fresh
budget then answers it. A state round trip of `MechanicalLanguageState` and
`InstitutionalKnowledgeState` keeps both the receipt and the knowledge, so a
reloaded world does not re-file the same grievance. Losing the controller
while the answer is being decided produces a blocked audit and moves no asset.

Root's independent verification passed 89 tests in 28.57 s over a group of 15
files -- civil petition, the institutional civil chain, trade, war, rite and
peace, and the population, government, domain, city, phase, month-transaction
and causal-authorship suites -- with `ruff check` clean on 9 Python files and
`git diff --check` clean. Two provider-free 120-month smokes were run *after*
the phase connection, so unlike the earlier baseline they actually exercise
this path: `/tmp/cws-main-plan-final-natural.json` recorded 3,199 events at
causal depth 19, and `/tmp/cws-main-plan-final-pressured.json` 3,665 events
with 20 transfers at depth 10, including the complete aid witness of request,
acceptance, fulfillment and memory. Both audits passed with zero broken
causes, out-of-window causes, Story mutations, untyped events and provider
calls. The read model surfaces the petition, the government's response and the
address history, so the chain is navigable through the existing Why path with
no new panel.

Read that scope literally. Those are focused runs and a focused selection:
they are not a whole-suite result and not a whole-plan result. The civil slice
itself is the 17 isolated tests above.

A minimal, real **work stoppage** now extends the civil slice, owned by
`RegionalEconomyState` itself rather than by a parallel planner. Its premise is
declared, not inferred: `city_economy.csv` gained a `labor_dependence` column,
set to 1.0 for `grain`, `timber` and `stone` -- local agricultural and
extractive output that rests on collective labour -- and 0.0 for
`spirit_stone`, because this V1 does not model that concept's labour substrate
and therefore must not affect it. The runtime never guesses this from a
concept's name; a resource is immune unless config says otherwise.

`WorkStoppage` is one concrete record per region, never a list and never a
modifier DSL: a participation share bounded by `MAX_STOPPAGE_PARTICIPATION`
(0.20) scaled by the pressure's own severity, starting on the next productive
cycle and covering exactly that cycle -- `ends_month` is validated to be
`started_month + 1`, so a longer stoppage would have to be a new decision.
Base `production_rates` are never written. The owner answers
`effective_production_rate = base * (1 - participation * declared_dependence)`,
and both the monthly balance and every FLOW reading call that same method, so
metrics and stock can never disagree. Nothing is snapshotted or restored: a
base rate that really changes mid-stoppage keeps its new value afterwards.

Availability is grounded: a real population, an active canonical `RISK`/`LOAD`
condition of this region, a prior real local petition, and at least one
resource with declared labour, real output, a stock entry and actual headroom
-- so the option is never decorative. The petition it rests on is *resolved*,
not trusted: its authoring population decision must exist, be a `DECISION`
fact with no deltas, name subject `population`/`region:<id>`, share the
petition's month, select exactly this affordance, and answer the condition's
own cause. A forged payload with real evidence and no decision authorizes
nothing. Migration and `NO_ACTION` stay valid throughout. Each pressure
instance admits **one** petition and **one** stoppage, held by their own
receipts; a second of either requires a genuinely new pressure instance and
therefore a new decision, so nothing renews itself.

A legacy dispatcher bug in `population_reactivity` had to be corrected for this
to be reachable at all: every outcome other than `population_transfer_completed`
was treated as a failed migration and pushed the whole condition into a
twelve-month backoff, so a *successful* petition silently locked its own
grievance out of any further choice. A civil success is now scheduled like any
other success -- reconsidered next month -- and skips the transfer bookkeeping
that belongs only to migration. Failures and stale affordances keep the
existing backoff.

Attribution is honest at the warehouse: forgone output is
`min(base, headroom_before) - produced`, computed from one headroom read
before anything moved, so a full warehouse and a non-labour concept forgo
nothing and are never blamed on the stoppage. Where output really was lost,
the monthly balance and any shortage link `CONTRIBUTED_TO` the stoppage's
start fact; where stock did not move at all, a `regional_production_forgone`
OCCURRENCE states the flow with no invented before/after delta. The start fact
is a `STATE_TRANSITION` carrying the real record as its delta, and expiry --
run at the head of the economy phase, so production resumes regardless of any
other phase -- carries the reverse. Save schema rose to 5; older saves are
rejected outright, with no migration and no real data rewritten.

Evidence: `tests/test_civil_work_stoppage.py` passes 18 tests, including a
twelve-month `Simulator.step` run with no provider that reaches the whole chain
from the scenario's own pressure -- start, recorded cost linked back to it, and
end -- rather than driving phases by hand. Twelve months is a window chosen to
respect the engine's real activation timing, not a parameter the engine
imposes: the canonical condition definitions need about seven months to
activate, so a six-month window reaches no grievance at all, and only the
cities the smoke scenario actually governs can be petitioned. With the
petition, population, economy, government, city, economy-reactivity, save-schema
and domain-reactivity suites the focused selection passes 82 tests in 38.24 s
with `ruff check` clean.

Root's independent focused run after the scheduling correction passed 167 tests
in 51.19 s, including
`test_a_short_real_simulation_produces_the_whole_stoppage_chain`, with the
frontend at 2 tests in 1.72 s, `ruff check` clean across every file in this
vertical and `git diff --check` clean. Read that as a focused selection: it is
not a whole-suite result.

Both 120-month smokes were then re-run after the scheduling correction and
exited 0: natural recorded 3,205 events at max causal depth 18, and pressured
3,665 events at max depth 9 with 20 transfers. Both report zero broken causes,
out-of-window causes, Story mutations, untyped events and failed affordances.
Their JSON audits confirm it: `provider_call_count` and `provider_await_count`
are 0, `story_as_material_cause_ids` is empty, and `assertions_passed` is true
in both; the pressured run also carries `witness.fulfilled` with its complete
chain. Those are general world-health runs: they say the corrected scheduling
did not damage the world, and they are **not** the proof that a stoppage works.
That proof is the twelve-month `Simulator.step` test above.
Backend PT-BR and zh-CN strings were added and compiled with the existing
`tools/i18n/build_mo.py`.

### The government's answer to a work stoppage

The stoppage now has a counterpart: the institution that actually administers
the region may answer it, on its own decision. The start fact records
institutional knowledge for **that one institution only**, through
`KnowledgeChannel.PUBLIC_FACT`, and `enqueue_pending_stoppages` -- called from
the existing `react_government` hook, with no new phase -- offers only
stoppages that institution really knows and has not yet answered. One answer
per institution per start fact, keyed by its own receipt.

Three decouplings were needed and are deliberate. `_city_options` no longer
requires a `ConditionInstance`: without one it still derives the menu from
current material state, and its urgency from real damage headroom and the real
settlement ratio rather than from a condition's intensity or from the kind of
event that triggered the reaction. Maintenance is not offered at all when
administrative capacity is zero, so the menu states what the city can do rather
than what it would like to. The expansion target for the condition-free path
reuses `DEFAULT_TARGET_SETTLEMENT_RATIO`, the owner's own existing default,
named rather than newly invented.

A resolved grievance does not block the answer and does not get a substitute:
the government answers the fact that really happened, the interpreter's context
carries `condition: None`, and the stoppage's own dates plus the region
economy's live record say whether the interruption is still under way -- so an
expired stoppage is never presented as ongoing. When no condition is live there
is no condition receipt to write; the response receipt is the whole record.

`stoppage_payload` now requires the fact to be a `STATE_TRANSITION` of
`ACTOR_DECISION` origin carrying a coherent record, and
`canonical_stoppage_payload` re-reads it from the event store, so a forged or
unknown trigger authorizes nothing even when a perfectly valid condition is in
hand. `civil_response_is_open` is the single gate -- unanswered, known,
authorized under `URBAN_ADMINISTRATION` with material control, and about *this*
region -- and it is asked in `government_affordances` as well as on both sides
of the interpreter's await, so a direct registry call cannot bypass it. The
urban executors (`urban_maintenance`, `urban_capacity_project`) now validate
the acting body's real decision event through the shared
`validate_actor_decision`, not a bare ID; both callers pass the fact.

Evidence: `tests/test_civil_stoppage_response.py` passes 11 tests -- the real
chain with two independent audited decisions (`population` vs `dynasty`), a
deterministic maintain with an empty menu, a resolved pressure answered on real
damage with real urgency, missing knowledge, lost authority, an unrecognised or
foreign stoppage, a stale post-await block that keeps the choice audited as an
act, budget exhaustion leaving the fact unanswered, and a month rollback that
releases the receipt while knowledge survives, checked through the current
`MechanicalLanguageState` / `InstitutionalKnowledgeState` serializers. The
integrated proof is the existing twelve-month `Simulator.step` run in
`tests/test_civil_work_stoppage.py`, now also requiring a
`RESPONSE_TO`-linked government decision on the persisted start fact, its
`AgentDecision` subject being the dynasty, and a completed response receipt
naming that decision; it passes in 11.36 s with no provider call.

Root's independent focused run for this slice passed **106 tests in 25.99 s**
across the new response suite plus the stoppage, civil, government, city,
domain-affordance, rollback, save/load and query suites, with `ruff check` and
`git diff --check` clean. The earlier 167-test, 49.84 s regression from the
stoppage slice still stands alongside it. Both are focused selections, not a
whole-suite result.

The 120-month smokes were re-run on this runtime and exited 0: natural recorded
3,206 events at max causal depth 18, and pressured 3,658 events at max depth 9
with 20 transfers. Both report zero broken causes, out-of-window causes, Story
mutations, untyped events and failed affordances, and their JSON audits carry
`provider_call_count` 0, `provider_await_count` 0, an empty
`story_as_material_cause_ids` and `assertions_passed` true, with the pressured
run's fulfilment witness present. These are world-health runs for *this*
runtime and are a separate measurement from the smokes recorded above for the
petition and stoppage slices; neither set is the proof that a government answer
works. That proof is the twelve-month `Simulator.step` test.

Two failures were observed **outside this slice's cut** and reproduced
independently:
`tests/test_city_state.py::test_urban_capability_quality_is_discovered_from_assets_not_a_fixed_catalog`
and
`tests/test_urban_service_metrics.py::test_available_service_surface_contains_aggregate_and_group_access_keys`.
Both reach `available_metric_keys(None, ...)` and die at
`src/systems/regional_hydrology.py:113` on `world.map`, entered from the
enumeration at `src/systems/semantic_world/resolvers.py:817`; neither test nor
either file was changed by this slice. That is what was observed, not a
baseline: no clean-checkout run was performed to confirm the failures predate
this work, and they are deliberately left unfixed here rather than repaired as
an unrelated feature.

Limitation: the answer reuses the existing urban menu only. There is no force,
no repression, no new resource, no concession, no negotiation and no bargaining
state; a maintain remains a legitimate answer and nothing compels a repair.

Limitation: this is a work stoppage, not a general strike. It reduces declared
labour output for one cycle in one region and touches nothing else -- no
demand, no transfers, no routes, no projects, no leadership, no organization,
no police, and no escalation ladder.

Status, honestly: this is a **partial** wave 10 -- the civil slice's protest
path, now with a bounded work stoppage. A *general* strike, riot, mob violence,
civic movement, rebellion and revolution are all still absent by design: what
exists is one petition and one single-cycle stoppage per pressure instance,
with no organization, no leadership and no escalation between them. Rebellion
in particular remains gated on the spec's own requirement of organization,
leadership and material capacity.
Wave 11 (intrigue, conspiracy, mythical threats) stays conditional on
long-run evidence and is not started. No whole-plan claim is valid.

That is coverage for these paths only. It is explicitly not global material
coverage: other effect and reward routes were outside this scope and remain
unexamined.

Wave 8 has a first, deliberately narrow slice, committed as fef7c882: a fixed
institutional prehistory of at most three months, clamped to the calendar that
exists before the playable January (a year-0 world legitimately gets zero
months). The world, dynasty, avatars and institutional authority are all
constructed at that genesis month before any event exists, so prehistory runs
forward and never backdates a fact; `world.start_year` still anchors the
playable year. Each prehistory month runs a filtered subset of the canonical
phase registry -- regional economy update, economy reactivity, late mechanical
invalidation carry-forward, and the shared finalizer -- with its own
`CausalBudget` and test-mode isolation. No avatar action, birth, death, war,
climate or narration phase runs, and nothing forces resources, pressure or a
positive decision: a silent prehistory is a valid world. This is institutional
history only, not a simulation of the world's past life, and it adds no run
config field, episode template or second owner. The new world is published to
the runtime (world, simulator and save path together) only after the prehistory
and the first playable month both succeed; a failed month restores that month
alone, earlier committed months stay in their own database, and the incomplete
candidate is never published. Save slots now carry a unique suffix so two
worlds created in the same minute cannot share an events database.
Initialization progress now reports 5 `generating_institutional_history`,
6 `preparing_character_profiles` and 7 `generating_initial_events`.
The frontend no longer preloads world data early: only static textures load
while initialization is in progress, world data loads once status is ready, and
the new phase label exists in all 7 locales.
Verified by focused runs only: 88 backend tests pass in 13.90 s (17 prehistory,
29 init integration, 7 init status, and the aid/relations/month-transaction/
phase/schema remainder), plus frontend 18 `useGameInit` and 47 world tests
(65 passed), `npm run build` in 10.27 s with typecheck and one pre-existing
large-chunk warning, and a clean git diff check. The end-to-end initialization
test needed host execution: under sandboxed execution it stalls to a 50 s
timeout with an idle thread pool and asyncio selector, while the same isolated
test passes on the host in 0.89 s. No whole-suite or long-smoke claim is made
for this block, and nothing was deployed or run against real data.

A bounded institutional commerce vertical now exists as local WIP on top of
fef7c882, not committed, pushed or deployed: a city facing a grounded
shortage sees, in one proposer decision, both the existing aid requests and
every enumerated reciprocal barter offer, and may select only an enumerated
affordance ID. Each offer pairs two `RESOURCE_TRANSFER` terms of different
resources inside one existing commitment, over canonical routes, with each leg
bounded independently by the actual deficit, the donor's surplus after
retaining its own demand stock, destination headroom and route capacity; no
price, currency, treasury, planner or unit parity exists, and the raw offered
terms are shown to both decision contexts. The counterparty accepts or
maintains on its own; acceptance reserves nothing and moves nothing, and each
obligor later decides its own shipment through the shared material commitment
lifecycle (`institutional_resource_commitment`), which owns fulfillment,
deadlines, breach and remediation for aid and trade alike and never executes a
reciprocal leg automatically. Limits: barter is shortage-driven between cities
only, the two legs are non-atomic and can be fulfilled, breached or remediated
separately, an unknown demand rate blocks export instead of reading as zero,
and a malformed or materially impossible response records no refusal.

Evidence for this commerce slice, and for nothing wider: the consolidated
backend selection passed 86 tests with 1 deliberately deselected (the unchanged
`real_initialization_wires_genesis_prehistory_and_publication`) in 21.46 s, and
the commerce vertical plus commerce runtime files passed 14 tests in 11.22 s;
those two runs overlap and must not be summed. The prehistory/domain/resources/
settings group timed out at 90 s in the sandbox after 44 dots, while the exact
same command on the host passed 52 tests with 1 deselected in 6.67 s with the
pre-existing StarletteDeprecationWarning: that is a sandbox execution limit, not
a production defect, and nothing was changed for it. The frontend panel and
composable tests passed 3 tests in 1.42 s, `npm run build` (tsc plus vite)
passed in 10.31 s with the pre-existing >550 kB chunk warning, and
`git diff --check` is clean. Two audited 120-month long smokes both exited 0
with a true JSON audit: the natural run
(`/tmp/cws-commerce-natural120.json`) produced 3,193 events at causal depth 16
with 0 institutional transfers and no injected decision policy, and the
pressured commerce run (`/tmp/cws-commerce-pressured120.json`) produced 3,949
events at causal depth 9 with 20 institutional transfers, including exactly two
reciprocal accepted legs and both complete term witnesses. The pressured run
uses an injected fixture decision policy; the natural run uses none, so a
barter world is reachable but never guaranteed. Both runs recorded zero broken
links, zero out-of-window events, zero story mutations, zero provider calls or
awaits, and no story material ancestors. Both also still carry 147 untyped
events and 27 conditions activated with 0 resolved, so this is explicitly not a
general world-quality or whole-suite claim.

War/religion/civil-disorder composition remains
deferred and is not a completed wave 8+. The committed hydrology correction
now applies a nonlinear severe-weather and soil response, then a bounded
geography susceptibility multiplier, and finally drainage as subtractive
resistance; a known Region footprint composed only of open water (SEA/WATER)
has zero flood risk, while an unknown footprint remains unknown. Hydrology
provenance is now split between climate and drainage sources, with the
map-wide elevation dependency represented by an aggregate geography reference.
Each activation/resolution window persists one `DrainageObservation` per month,
validates the strict consecutive window, and saves that observation history;
the resulting mechanical measurements are available through the existing Why
path. This is a verified focused checkpoint, not a full hydrology acceptance
claim. The earlier focused hydrology checkpoint had 76 tests passed (previous
checkpoint). A preliminary three-seed,
12-month classic check changed the prior all-eight-regions-active result to zero
floods in two seeds and one wetland flood starting in month 5 and still active
at month 12 in the third. Final provider-free 120-month, one-world Simulator
smokes passed all audit assertions: natural produced 3,200 events at causal
depth 17 with zero transfers; pressured produced 3,661 events at causal depth
10 with 20 transfers.
Both report zero broken causes, out-of-window links, Story mutations, Story
material ancestors, and provider calls/awaits; pressured also proves the exact
seven-event fact chain and linked memory witness. Artifacts are
`/tmp/cws-provenance-verified-natural.json` and
`/tmp/cws-provenance-verified-pressured.json`. This remains focused evidence, not
full-suite or world-quality acceptance. It preserves floodable transitional
land, mixed/land regions, the existing
two-high-month activation and two-low-month resolution windows, and the
separate occurrence-to-site-damage owner chain; see
`.superpowers/sdd/actor-driven-emergent-world/hydrology-audit.md`.
Opus's earlier read-only review found no blocker, but its provenance precision
findings are now implemented and verified in the focused checkpoint: climate and
drainage source IDs are distinct, elevation normalization has an aggregate
map reference, and drainage observations are retained across the strict
two-month windows. Flood activation still labels site maintenance as context,
not `TRIGGERED_BY`; no full-hydrology claim is made. Calibration also shows
that some strongly drained regions cannot reach the 0.72 activation threshold
under the bounded maximum load, making a well-protected plain effectively
immune in this model, but not establishing universal immunity. The previously
flagged isolated-adjacency test was addressed and verified in the 76-test
rerun (previous checkpoint). Save schema is now version 4; loaders explicitly
reject version 3, with no destructive production data or DDL operation. This
schema/version evidence is current. The final hydrology subset rerun after
the tiny numeric fixture refinement passed 37 tests in 4.40 seconds. An
additional exact eight-file batch passed 65 tests in 77.15 seconds after an
earlier 64-pass/1-failure batch; that failure did not reproduce and its cause
is unconfirmed, so it is not labeled pre-existing-fixed and does not establish
full-suite green.
Relationship transitions learn both parties through `KnowledgeState` without
an added memory factor, and the API/UI
relation section is read-only with Why evidence. Future aid prompts may use
the current relation.
Orchestration is user-directed by the root agent: Claude Opus implemented this
provenance block, Terra reviewed it, and the root agent integrated it. This
ledger records current state, not a redesign of the frozen architecture.

The autonomous `sect_wars` simulation phase is removed (module, registry entry
and phase export), with the canonical phase registry renumbered to a contiguous
1-45. Nothing replaces it: there is no random wartime battle, no forced
teleport to a headquarters, and no automatic war contribution or war weariness
from an encounter. A formal war is an institutional relationship between sects,
and war status alone no longer initiates combat: two members of warring sects
standing on adjacent tiles fight only if one of them actually chooses to.
`Attack` remains an internal action (`actual=False`), used by existing combat
mechanics rather than exposed in the public action catalogue. `MutualAttack`
is now the natural public hostile entry: a precise accepted player/AI decision
and a valid execution boundary record one initiating aggression fact, including
the deciding actor, locked target, witnessed institutions and decision link.
It creates no battle; the target independently chooses Escape or internal
Attack. A defensive response is runtime-reactive, points back to the initiative
and cannot create/reverse a casus. Stale, renamed, dead, out-of-range, restored
or unaudited paths fail closed. Other avatar interactions that can end in a
fight, such as `Spar` and `Assassinate`, keep their own owners and are unchanged.
`Attack` now refuses a self target and a target outside the attacker's own
observation radius, and it revalidates the same predicate at the execution
boundary, failing the action instead of fighting a target that died, moved away
or stopped resolving between commit and execution. Observation stays directed,
so a weaker avatar cannot counterattack an initiator it cannot perceive.
Bilateral peace negotiation is now implemented in
`src/systems/institutional_peace.py` during January maintenance on the
configured sect decision cycle (currently every three years). Pending
proposals are canonical typed events and institutional-knowledge facts;
transient affordances are only the runtime choice surface. Proposing does not
end a war: on a later recipient cycle the counterparty may accept, reject, or
maintain, and acceptance rechecks both negotiating authority, the exact war
episode, and proposal expiry before preserving the relation's friendliness.
This slice adds no magic resources or non-aggression obligation, and the old
`seek_peace` path and sect-decider war output are removed. Unilateral formal
war declaration remains normal; it is no longer an administrative decision
field. The institutional war domain in `src/systems/institutional_war.py`
grounds a witnessed `MutualAttack` initiative in its chosen decision provenance.
The responsible office holder must be a participant or observe both avatars,
and the victim institution may decide through its own domain affordance; it may
also maintain, so aggression never forces war. There are no troops or automatic
military battles. Persisted aggression facts remain eligible after load;
restored in-flight plans without transient origin cannot create new aggression
evidence, and the same causal source is not spent twice.

The source-player decision acceptance audit is implemented through the shared
`avatar_decision.py`/`roleplay_service.py` path: one canonical `DecisionEvent`
is persisted through the serialized event API only after a roleplay command,
its offered public action chain and its immediate boundary are accepted. Raw
command text, chat messages and the runtime roleplay session remain transient
and never enter the save. Decision acceptance, plan adoption, action execution
and aggression attribution keep their separate canonical owners. A
rejected/failed acceptance creates no plan; a later-month rollback preserves
an already accepted decision event; and plan origin is transient, so load fails
closed while persisted event storage remains intact. The focused public `Rest`
runtime witness verifies its owner-authored HP causal link and final-month
rollback/retry proof. The public `MutualAttack` provenance/casus path is now
implemented with the limits above: it does not make internal `Attack` public,
does not invent a battle on Escape, and does not force an institutional war.

Focused MutualAttack evidence now covers accepted public initiative, successful
Escape, defensive internal Attack, player-selected response, victim `maintain`,
stale target rejection and response-time rollback without duplicate aggression.
The consolidated backend selection passed 171 tests with 3 deselected in
21.27 seconds (MutualAttack, war runtime/chain and roleplay-decision contracts);
lint and diff checks passed. The exclusions are the baseline
`test_spar_finish_generates_story` AttributeError and the timeout-prone baseline
`test_get_target_avatar_not_found` / `test_step_running_then_completed`, so this
does not claim universal-suite green. Two 120-month
provider-free smokes also completed within a 300-second allowance: natural
produced 3,198 events at causal depth 17 and pressured 3,669 at depth 10 with
20 transfers and the existing seven-event aid/memory witness. Both audit zero
broken/out-of-window causes, Story mutations/material ancestors and provider
calls/awaits. This is not war-stress or world-quality acceptance: the harness
does not force war, and both runs still report 147 untyped events and 27
activated, zero-resolved conditions.

Dao rite sponsorship authorship is corrected as local WIP on top of 31457838,
not committed, pushed or deployed. `SponsorDaoRite` no longer fabricates its
own `AgentDecision` with a defaulted `player` source, and no longer asserts a
sponsorship at `start`: the engine installs the plan origin only after `start`
returns, so `start` records nothing and the fact is written at the execution
boundary, as `MutualAttack` already does. The sponsorship is now a
`FactKind.OCCURRENCE` with no material effect -- it moves no resource and
changes no office, and the only deltas it carries are the institutional
knowledge and memory ones described below -- and is
authored only when the shared `avatar_decision` owner proves the actor's own
audited chain contains this exact `SponsorDaoRite` step with this exact cause
under `ActionOrigin.ACTOR_CHOICE`; an action rebuilt outside the commit path, a
reactive install and a chain that chose another rite all produce no
sponsorship at all. The blocker
now also rejects a Story cause and any cause outside the 12-month rite window,
including a future month stamp, and it is revalidated at the boundary, so a
rite that goes stale between commit and execution is refused. Duplicate
sponsorship per institution is preserved. `_sponsorable_dao_rite_options`
delegates to that blocker instead of restating the rule, so already-sponsored
and out-of-window rites are no longer offered. The audience path now resolves
the cited decision instead of trusting the payload, with the same rigor as
`_grounded_source`: exact `AgentDecision` field set, allowed source, decision
month not after the fact, matching subject, and an exact
`{cause_event_id}` parameter match; a dangling pointer, a pointer to another
action's decision and a hand-written `is_sponsorship` payload count towards no
Celestial Audience. Current office holding is deliberately not rechecked in
history, so a later leadership change does not unmake a past sponsorship.
Sponsorship is now grounded in institutional authority and memory, still as
local WIP. The loose emperor/patriarch gate is only a candidate check
(`_institution_candidate`); the actual permission is `can_actor_act_for` under
`AuthorityScope.RECOGNITION`, chosen because it is the one scope both the
dynasty's sovereign office and a sect's patriarch office hold and the one that
disposes of nothing material. Emperor and living patriarch remain the only
candidates, no office, claim or recognition is created, and there is no
permissive fallback: a world with no bootstrapped authority state has nobody
who can sponsor. Authority is revalidated at the execution boundary alongside
the rite window, so an office that loses its holder or its scope between commit
and execution refuses and mutates nothing. The fact carries
`dao_rite.sponsor_institution_id`, the canonical `Institution` ID; `"court"`
stays a legacy Dao label and never becomes an `EntityRef` kind. On success the
acting institution alone records the fact through `record_known_fact` with
`KnowledgeChannel.OWN_ACTION` -- no broadcast, no omniscience -- and one memory
built from the four frozen engine factors: `relative_scale` is this act's
single share of `RITES_REQUIRED_FOR_AUDIENCE`, deliberately not cumulative
because counting prior sponsorships would read the persisted window and the
runtime cache together, double-count an event present in both, and reweigh the
same fact after a reload; `identity_anchor_impact` is a real read of the
institution's anchors for that region; `institutional_change` and
`commitment_breach` are zero as a matter of fact. No LLM weighting and no
automatic hostility. The sponsorship stays a single Avatar action with no
duplicate `DomainAffordance`. `build_avatar_prompt_context` gains
`local_world.own_institution_memory`, the shared bounded
`institutional_memory.decision_context` under the same scope, visible only to
the avatar who may currently speak for the institution; an ordinary member
sees nothing. History survives a leadership change: current office holding is
not rechecked over past facts. Note that nothing in the engine ever creates an
`InstitutionalIdentityAnchor` today, so that factor reads 0.0 in a real world
and is exercised only by seeding an anchor in a test.

Other institutions may now interpret a sponsorship they actually witnessed,
reusing the existing relationship-impact engine with no new planner, church,
war path or schema. `record_dao_rite_sponsorship` captures
`dao_rite.witness_institution_ids` at the exact moment of the act: a dynasty or
sect (never the sponsor, never a city) whose current `COMMITMENT_NEGOTIATION`
holder is alive, passes `can_actor_act_for`, and has the sponsoring avatar
inside its own observation radius. Nothing is inferred from shared region,
membership or prose, and the snapshot is never recomputed from where anyone
stands later. Witnesses learn the same still-uncommitted fact through
`KnowledgeChannel.MEMBER_WITNESS` while the sponsor keeps `OWN_ACTION`; no
memory is fabricated for a witness, because what a sponsorship is worth to an
onlooker has no engine-owned weight. There is no broadcast to the world.

In `institutional_relationship_impact`, observer enumeration and pair
resolution are now separate: `_observer_candidates` lists who may react, and
`_reaction_pair` returns the commitment's own two parties for the existing
facts and always `(witness, sponsor)` for a sponsorship, so witnesses never
pair with each other and the sponsor never reacts to itself. A valid source is
only what the Dao owner's `_is_institutional_rite` accepts -- the cited
decision resolved and proved -- never a loose `is_sponsorship` flag, so a
popular rite sharing the `dao_rite` event type is not reactable. IDs are
resolved against the authority state rather than coerced: a non-string, a
dangling witness or an unresolvable sponsor fails closed, and an unresolvable
sponsor offers no options and makes no interpreter call. `maintain` remains the
test-mode default and neither valence forces a relation kind or war. The
interpreter templates in en-US, pt-BR and zh-CN now say institutional fact
rather than aid, and pass the rite's canonical tradition as context for how the
act reads, explicitly not as a rule about who must resent whom. One adjacent
correction: `record_maintained_reaction` now rechecks authority, and the phase
skips instead of crashing when a reaction goes stale mid-interpretation, so a
receipt is never spent without permission.

Limits: no new religion, engine, owner, institution, church schema, event type
or persisted affordance was added, and no shared authority, model or LLM
interface was changed. Witnessing grants nothing by itself and creates no
relation on its own. The transient `_dao_sponsorship_events_this_step` cache is
now pruned to the rite window instead of growing for the world's lifetime, but
it remains runtime-only; a `SimulationMonthCheckpoint` rollback releases it
with the rest of the World, so a rolled-back sponsorship is decidable again.
Knowledge and memory append their deltas onto the still-uncommitted
sponsorship event, so no persisted fact is mutated, and
`validate_causal_integrity` accepts the decision and the fact collected
together.

Evidence is focused only. The dedicated authorship file now passes 19 tests,
adding to the 10 below: own-institution knowledge with `OWN_ACTION` and nobody
else learning, the exact four factors and their salience, an anchored region
raising the remembered weight, the holder reading its own memory through the
real `build_avatar_prompt_context(...)["local_world"]["own_institution_memory"]`
while an ordinary avatar reads `None` on that same path, a dead holder and a
removed `RECOGNITION` scope between commit and finish each mutating nothing,
survival of a leadership change, idempotent re-recording, causal-integrity
acceptance, and rollback releasing knowledge and memory. The earlier 10 are
the
authored occurrence fact, month 0, a SQLite re-read of the stored fact and its
decision with no step overlay and no dedup cache, an already-sponsored rite
dropping out of
`param_options`, checkpoint rollback and retry, a decision naming another rite,
a rite that goes stale between commit and execution, future/Story causes, and
three forged sponsorships. The forged cases carry the actor-decision origin on
purpose, so they reach the pointer lookup rather than dying on the structural
guard; that was verified by mutation (neutralising the lookup fails the test).
The witness slice adds `tests/test_sponsorship_witness_reaction.py`, 11 focused
tests on a fixture of a sponsoring emperor, two patriarchs inside observation
radius and one deliberately out of range: witness capture excluding the
outsider and the sponsor, witness knowledge without memory, each witness
pairing only with the sponsor, a popular rite and a forged flag being
unreactable, dangling and malformed IDs failing closed, test-mode maintain
creating no relation, injected positive and negative readings moving only the
shared scalar and never the relation kind, the real `process_economy_reactivity`
gateway carrying the sponsorship to both witnesses, a receipt closing the fact
with a rollback reopening it while the earlier sponsorship knowledge survives,
and the two risk cases: moving a holder out of range afterwards does not unmake
the historical snapshot, and losing the scope mid-interpretation spends no
receipt for that observer while the other one still closes its own. That
receipt case was mutation-checked -- removing the new authority recheck fails
it. The fixture declares `test_mode` on the World itself and an autouse stub
makes any provider call fail, so nothing depends on ambient shell state.
`ruff check` on the changed files passed.

The current focused evidence for this slice is root's independent integrated
regression across 16 test files: 110 tests passed in 15.32 s. The
`tests/test_institutional_relationship_runtime.py` failure root saw at an
earlier baseline was a test-side defect, resolved by Luna with an explicit
`institutional_aid` import in that test; no production path was involved and
nothing here fixed it. The earlier authorship-only slice passed 94 tests in
11.66 s: sponsor
authorship and rites/material, Luna's institutional rite chain and the
institutional chain assembler projection built on
`dao_rite.sponsor_institution_id`, authority, persistence, avatar prompt, the
Dao phase and public services, param options, roleplay decision, causal
authorship and month transaction. `ruff check` passed on eight Python files
and `git diff --check` is clean. Nothing was committed, pushed or deployed.
Sponsorship tests now have to bootstrap institutional authority, which is the
intended consequence of removing the permissive fallback rather than a fixture
convenience. The
baseline `test_spar_finish_generates_story` AttributeError still fails and is
unrelated and untouched. No save/load round trip specific to this path was
written: the SQLite witness re-reads the two facts out of the event store, the
checkpoint witness rolls back a month, and the fail-closed witness rebuilds the
action object directly, which is the shape a loader produces rather than a
reloaded world. Persistence coverage for this slice is the generic persistence
suite in the integrated run, not a sponsorship-specific one. No whole-suite,
long-smoke or world-quality claim is made.

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
Flooding responds nonlinearly to severe weather and soil saturation, applies a
bounded geography susceptibility multiplier, and then subtracts drainage as
resistance. A known pure SEA/WATER footprint yields zero flood risk; an unknown
footprint yields unknown rather than silently suppressing or inventing a
hazard. It exposes grounded mechanical readings and never becomes a parallel
state owner.

### Flood Risk

Flood Risk is a derived observation of hydrological exposure. It is not a flood
occurrence and cannot damage assets, close routes, move population, or change
another domain without a separately validated domain action. Pure open-water
Regions have zero Flood Risk when their footprint is known; land and mixed
footprints remain eligible. The two-high-month activation and two-low-month
resolution windows are unchanged.

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
