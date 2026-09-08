"""A 120-month provider-free run proving the witnessed-sponsorship chain.

This reuses the existing institutional smoke world factory, the real
``Simulator.step`` and the existing `CausalTortureRunner`; it adds no
production path and no new harness abstraction. The runner is what seeds and
restores the RNG, so the run is deterministic without this test managing
global random state itself.

Two fixture corrections make the vertical reachable at all, and nothing more:
the smoke emperor is born at (0, 0), which belongs to no region, so it could
never stand in a rite's region; and the classic map's sect institutions are
bootstrapped without an office holder, so no institution could ever witness.

The pressure is the scenario's own -- a real grain shortage in city 305 -- so
no rite is fabricated here. Only the emperor ever sponsors, and only when the
engine has already enumerated the action with a real parameter value; the
patriarch always takes the enumerated ``Rest`` so it stays in sight. The run
fails if a sponsorship was never validly offered.

Scope: the state read back is in-memory World state and this run's events.
This proves the causal chain and the reaction pipeline; it is deliberately not
a SQLite save/load round trip and makes no persistence claim.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.event import FactKind
from src.classes.institution import KnowledgeChannel
from src.systems.institution_bootstrap import synchronize_institutional_authority
from tools.institutional_smoke import _world_factory

MONTHS = 120
SEED = 7
RITE_CITY = 305
SPONSOR_ACTION = "SponsorDaoRite"
DYNASTY_INSTITUTION_ID = "inst:dynasty:1"


def _place_in_city(world, avatar, region_id: int, offset: int = 0) -> None:
    """Stand this avatar on a real tile of that city, not on a bare (0, 0)."""
    cors = list(world.map.regions[region_id].cors)
    x, y = cors[offset % len(cors)]
    avatar.pos_x, avatar.pos_y = int(x), int(y)
    avatar.tile = world.map.get_tile(int(x), int(y))


def _build_world(seed: int):
    """The pressured smoke world, with a present sponsor and a present witness."""
    from src.classes.age import Age
    from src.classes.core.avatar import Avatar, Gender
    from src.classes.sect_ranks import SectRank
    from src.systems.cultivation import Realm
    from src.systems.time import Month, Year, create_month_stamp

    world = _world_factory(pressured=True, commerce=False, seed=seed)(0, seed)
    emperor = world.avatar_manager.get_avatar(f"smoke-emperor-{seed}")
    _place_in_city(world, emperor, RITE_CITY, offset=0)

    sect = world.sect_context.get_active_sects()[0]
    patriarch = Avatar(
        world=world,
        name="Smoke Patriarch",
        id=f"smoke-patriarch-{seed}",
        birth_month_stamp=create_month_stamp(Year(70), Month.JANUARY),
        age=Age(30, Realm.Qi_Refinement),
        gender=Gender.MALE,
    )
    world.avatar_manager.register_avatar(patriarch)
    patriarch.sect = sect
    patriarch.sect_rank = SectRank.Patriarch
    sect.members = {str(patriarch.id): patriarch}
    # Adjacent to the emperor, comfortably inside the observation radius.
    _place_in_city(world, patriarch, RITE_CITY, offset=1)
    # The office exists but was bootstrapped holderless; this installs the
    # holder through the canonical owner rather than by hand.
    synchronize_institutional_authority(world)
    return world, emperor, patriarch, f"inst:sect:{sect.id}"


class _EmperorSponsorsWhenOffered:
    """Only the emperor sponsors, and only what the engine already enumerated.

    The patriarch always takes the enumerated ``Rest``: it is the witness, not
    a second sponsor, so the sponsorship under test can only have one author.
    """

    def __init__(self, sponsor_id: str, witness_id: str) -> None:
        self.sponsor_id = sponsor_id
        self.witness_id = witness_id
        self.sponsorship_offers = 0
        self.sponsorship_choices = 0

    def _chain(self, avatar):
        from src.systems.avatar_decision import offered_actions

        offered = offered_actions(avatar)
        if str(avatar.id) == self.sponsor_id:
            info = offered.get(SPONSOR_ACTION)
            options = (info or {}).get("param_options", {}).get("cause_event_id") or []
            if info is not None and options:
                self.sponsorship_offers += 1
                self.sponsorship_choices += 1
                return [(SPONSOR_ACTION, {"cause_event_id": str(options[0]["value"])})]
        return [("Rest", {})] if "Rest" in offered else None

    async def __call__(self, world, avatars):
        results = {}
        for avatar in avatars:
            if str(avatar.id) not in {self.sponsor_id, self.witness_id}:
                continue
            chain = self._chain(avatar)
            if chain is not None:
                results[avatar] = (chain, "Fixture policy.", "Stay and observe.", None)
        return results


def _witness_reader(module, witness_institution_id: str):
    """Read only the witnessed sponsorship, and only as the expected witness.

    Every other relationship reaction in the world -- aid, trade, commitment
    outcomes -- keeps its normal behaviour, so this fixture proves the
    sponsorship path without quietly steering the rest of the run.
    """
    original = module.interpret_domain_affordances
    state = {"acts": 0}

    def _is_target(kwargs) -> bool:
        trigger = kwargs.get("trigger_event")
        payload = getattr(trigger, "causal_payload", None) or {}
        rite = payload.get("dao_rite") or {}
        return (
            str(getattr(trigger, "event_type", "")) == "dao_rite"
            and bool(rite.get("is_sponsorship"))
            and str(kwargs.get("actor_label", "")) == witness_institution_id
        )

    async def controlled(*args, **kwargs):
        if not _is_target(kwargs):
            return await original(*args, **kwargs)
        chosen = next(
            (
                option
                for option in tuple(kwargs.get("affordances") or ())
                if option.parameters.get("valence") == "positive"
                and option.parameters.get("intensity") == "mild"
            ),
            None,
        )
        if chosen is None:
            return await original(*args, **kwargs)
        state["acts"] += 1
        return await original(
            *args,
            **{
                **kwargs,
                "injected_decision": DomainDecision(
                    DomainDecisionKind.ACT,
                    "Fixture reading of a witnessed rite.",
                    chosen.id,
                ),
            },
        )

    return controlled, state


def _story_free_ancestry(event, by_id) -> bool:
    """No Story is a material ancestor of this fact.

    The traversal is complete: `seen` bounds it because the event graph is
    finite, so there is no node cap that could report success merely because
    the walk stopped early.
    """
    seen: set[str] = set()
    frontier = [str(link.cause_event_id) for link in event.causal_links]
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        ancestor = by_id.get(current)
        if ancestor is None:
            continue
        if getattr(ancestor, "is_story", False):
            return False
        frontier.extend(str(link.cause_event_id) for link in ancestor.causal_links)
    return True


@pytest.mark.asyncio
async def test_witnessed_sponsorship_chain_over_120_months(mock_llm_managers):
    import src.systems.institutional_relationship_impact as impact
    from src.sim.simulator import Simulator
    from src.systems.causal_observatory import CausalTortureConfig, CausalTortureRunner

    built: dict = {}
    captured: list = []
    simulators: dict[int, object] = {}

    def world_factory(_index: int, world_seed: int):
        world, emperor, patriarch, sect_institution_id = _build_world(world_seed)
        built.update(
            world=world,
            emperor=emperor,
            patriarch=patriarch,
            sect_institution_id=sect_institution_id,
            policy=_EmperorSponsorsWhenOffered(str(emperor.id), str(patriarch.id)),
        )
        mock_llm_managers["ai"].decide = built["policy"]
        return world

    # `CausalTortureRunner` restores the world from its month checkpoint in a
    # `finally` before returning, so World state read after `run` would be the
    # pre-run snapshot.  Everything asserted about knowledge and receipts is
    # therefore copied out here, inside the step, while it is still live.
    live: dict = {"knowledge": {}, "receipts": set()}

    async def step(world):
        if id(world) not in simulators:
            simulators[id(world)] = Simulator(world)
        events = await simulators[id(world)].step()
        captured.extend(events)
        live["knowledge"] = {
            key: (fact.institution_id, fact.event_id, fact.channel)
            for key, fact in world.institutional_knowledge.known_facts.items()
        }
        live["receipts"] = set(world.mechanical_language.reaction_receipts)
        live["relation_kinds"] = [
            relation.kind.value
            for relation in world.institutional_relations.relations.values()
        ]
        return events

    provider = AsyncMock(side_effect=AssertionError("a provider call was attempted"))
    original_interpreter = impact.interpret_domain_affordances
    reader_state: dict = {}

    async def routed(*args, **kwargs):
        controlled = built.get("reader")
        return await (controlled or original_interpreter)(*args, **kwargs)

    with patch("src.utils.llm.client.call_llm_with_template", provider), patch.object(
        impact, "interpret_domain_affordances", routed
    ):
        # The reader needs the witness ID, which only exists once the world is
        # built, so it is installed by the factory's own call below.
        def _install_reader(world_seed: int):
            controlled, state = _witness_reader(
                SimpleNamespace(interpret_domain_affordances=original_interpreter),
                built["sect_institution_id"],
            )
            built["reader"] = controlled
            reader_state.update(state=state)

        def factory_with_reader(index: int, world_seed: int):
            world = world_factory(index, world_seed)
            _install_reader(world_seed)
            return world

        # The runner owns RNG seeding and restoration for this run.
        report = await CausalTortureRunner(
            CausalTortureConfig(
                worlds=1,
                months=MONTHS,
                seed=SEED,
                test_mode=True,
                provider="test",
                probe_profile="baseline",
            )
        ).run(world_factory=factory_with_reader, step=step)

    provider.assert_not_called()
    provider.assert_not_awaited()

    # Deliberately no post-run World read: the runner has already restored it.
    policy = built["policy"]
    sect_institution_id = built["sect_institution_id"]

    # 1. The engine really offered a sponsorship, and only that was ever taken.
    assert policy.sponsorship_offers >= 1
    assert policy.sponsorship_choices == policy.sponsorship_offers

    by_id = {str(event.id): event for event in captured}
    sponsorships = [
        event
        for event in captured
        if event.event_type == "dao_rite"
        and (event.causal_payload or {}).get("dao_rite", {}).get("is_sponsorship")
    ]
    assert sponsorships, "a validly offered sponsorship produced no fact"
    sponsorship = sponsorships[0]
    rite = sponsorship.causal_payload["dao_rite"]

    # 2. An authored occurrence citing the decision that really chose it.
    assert sponsorship.fact_kind is FactKind.OCCURRENCE
    # Only the emperor was allowed to sponsor, so every one of these is the
    # dynasty's; asserting it here keeps that guarantee explicit.
    assert {
        str((item.causal_payload or {})["dao_rite"]["sponsor_institution_id"])
        for item in sponsorships
    } == {DYNASTY_INSTITUTION_ID}
    decision = by_id.get(
        sponsorship.causal_payload["decision_source"]["decision_event_id"]
    )
    assert decision is not None and decision.fact_kind is FactKind.DECISION
    assert any(
        step_entry.get("action_name") == SPONSOR_ACTION
        for step_entry in decision.causal_payload["decision"]["chosen_chain"]
    )
    assert str(rite["cause_event_id"]) in by_id

    # 3. The present sect witnessed it and learned it as a witness.
    assert sect_institution_id in rite["witness_institution_ids"]
    learned = {
        (institution_id, event_id): channel
        for institution_id, event_id, channel in live["knowledge"].values()
    }
    assert learned.get((sect_institution_id, sponsorship.id)) is (
        KnowledgeChannel.MEMBER_WITNESS
    )
    assert learned.get((DYNASTY_INSTITUTION_ID, sponsorship.id)) is (
        KnowledgeChannel.OWN_ACTION
    )

    # 4. The witness reacted independently, through the real month pipeline.
    assert reader_state["state"]["acts"] >= 1
    assert impact._receipt_id(sect_institution_id, sponsorship.id) in live["receipts"]
    reactions = [
        event
        for event in captured
        if (event.causal_payload or {})
        .get("relationship_impact", {})
        .get("source_event_id")
        == sponsorship.id
    ]
    assert reactions, "the witnessed sponsorship produced no independent reaction"
    reaction = reactions[0]
    impact_payload = reaction.causal_payload["relationship_impact"]
    assert impact_payload["observer_institution_id"] == sect_institution_id
    assert impact_payload["counterparty_institution_id"] == DYNASTY_INSTITUTION_ID
    assert any(link.cause_event_id == sponsorship.id for link in reaction.causal_links)

    # 5. The run's own causal audit, and no Story behind either fact.
    totals = report.totals
    assert totals["broken_causes"] == 0
    assert totals["out_of_window_causes"] == 0
    assert totals["story_mutations"] == 0
    assert _story_free_ancestry(sponsorship, by_id)
    assert _story_free_ancestry(reaction, by_id)

    # 6. Nothing here creates a war.
    assert "at_war" not in live["relation_kinds"]
