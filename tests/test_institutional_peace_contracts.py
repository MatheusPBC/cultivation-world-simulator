"""Focused guards for the fact-derived bilateral peace contract."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.classes.event import Event, FactKind
from src.systems.domain_affordance_registry import AffordanceContext, StaleAffordanceError
from src.systems.institutional_diplomacy import (
    WAR_DECLARED_EVENT_TYPE,
    are_sects_at_war,
    conclude_formal_war,
    sect_institution_id,
    sect_institution_ref,
    set_formal_war,
)
from src.systems.institutional_memory import record_known_fact
from test_institutional_peace_runtime import (
    _advance_to_next_january,
    _enable_annual_peace,
    _peace_world,
)


def _control_actions(monkeypatch, mode: dict[str, str | None]) -> None:
    import src.systems.institutional_peace as peace

    original = peace.interpret_domain_affordances

    async def controlled(*args, **kwargs):
        selected = next(
            (
                option
                for option in kwargs["affordances"]
                if option.action_kind == peace.PROPOSE_ACTION
                or option.action_kind == mode["response"]
            ),
            None,
        )
        decision = (
            DomainDecision(DomainDecisionKind.ACT, "Controlled peace contract.", selected.id)
            if selected is not None
            else DomainDecision(DomainDecisionKind.MAINTAIN, "Keep the proposal open.")
        )
        return await original(*args, **{**kwargs, "injected_decision": decision})

    monkeypatch.setattr(peace, "interpret_domain_affordances", controlled)


async def _pending_proposal(base_world, monkeypatch, *, decision_interval_years: int | None = None):
    from src.sim.simulator import Simulator
    from src.utils.config import CONFIG

    _peace_world(base_world)
    if decision_interval_years is not None:
        monkeypatch.setattr(CONFIG.sect, "decision_interval_years", decision_interval_years)
    _enable_annual_peace(monkeypatch)
    mode = {"response": None}
    _control_actions(monkeypatch, mode)
    events = await Simulator(base_world).step()
    proposal = next(event for event in events if event.event_type == "institutional_peace_proposed")
    return proposal, mode


@pytest.mark.asyncio
async def test_maintain_leaves_the_canonical_proposal_answerable(base_world, monkeypatch):
    import src.systems.institutional_peace as peace
    from src.sim.simulator import Simulator

    proposal, _mode = await _pending_proposal(base_world, monkeypatch)
    _advance_to_next_january(base_world)
    events = await Simulator(base_world).step()

    assert not [event for event in events if event.event_type == peace.REJECTED_EVENT_TYPE]
    assert not [event for event in events if event.event_type == peace.ACCEPTED_EVENT_TYPE]
    assert [event.id for event, _payload in peace.open_peace_proposals(base_world)] == [proposal.id]
    wrong_actor = AffordanceContext(
        base_world, peace.RESPONSE_DOMAIN, sect_institution_ref(1), proposal
    )
    assert peace.response_affordances(wrong_actor) == ()
    assert are_sects_at_war(base_world, 1, 2)


@pytest.mark.asyncio
async def test_explicit_rejection_answers_once_without_ending_the_war(base_world, monkeypatch):
    import src.systems.institutional_peace as peace
    from src.sim.simulator import Simulator

    proposal, mode = await _pending_proposal(base_world, monkeypatch)
    _advance_to_next_january(base_world)
    mode["response"] = peace.REJECT_ACTION
    rejected_cycle = await Simulator(base_world).step()

    rejected_events = [event for event in rejected_cycle if event.event_type == peace.REJECTED_EVENT_TYPE]
    assert len(rejected_events) == 1
    rejected = rejected_events[0]
    assert rejected.causal_payload["proposal_event_id"] == proposal.id
    assert are_sects_at_war(base_world, 1, 2)
    assert proposal.id not in {event.id for event, _payload in peace.open_peace_proposals(base_world)}


@pytest.mark.asyncio
async def test_no_known_war_fact_skips_the_provider_and_interpreter(base_world, monkeypatch):
    import src.systems.institutional_peace as peace

    war = _peace_world(base_world)
    base_world.institutional_knowledge.known_facts.clear()
    provider = AsyncMock(side_effect=AssertionError("peace interpreter must not run"))

    events = await peace.process_institutional_peace_negotiation(
        base_world, llm_call=provider
    )

    context = AffordanceContext(
        base_world, peace.PROPOSAL_DOMAIN, sect_institution_ref(1), war
    )
    assert peace.proposal_affordances(context) == ()
    assert events == []
    assert provider.await_count == 0


@pytest.mark.asyncio
async def test_expiry_is_frozen_in_the_proposal_despite_later_cadence_change(base_world, monkeypatch):
    import src.systems.institutional_peace as peace
    from src.utils.config import CONFIG

    proposal, _mode = await _pending_proposal(
        base_world, monkeypatch, decision_interval_years=3
    )
    frozen_deadline = proposal.causal_payload["peace_proposal"]["expires_month"]
    opening_month = int(proposal.month_stamp)
    assert frozen_deadline == opening_month + 72
    monkeypatch.setattr(CONFIG.sect, "decision_interval_years", 1)
    base_world.month_stamp = opening_month + 25

    assert [event.id for event, _payload in peace.open_peace_proposals(base_world)] == [proposal.id]
    base_world.month_stamp = frozen_deadline + 1
    assert peace.open_peace_proposals(base_world) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_kind", ["malformed", "story", "forged"])
async def test_response_refuses_noncanonical_or_forged_proposal_fact(
    base_world, monkeypatch, invalid_kind
):
    import src.systems.institutional_peace as peace

    proposal, _mode = await _pending_proposal(base_world, monkeypatch)
    trigger = proposal
    if invalid_kind == "malformed":
        proposal.causal_payload = {"deltas": [], "peace_proposal": {}}
    elif invalid_kind == "story":
        proposal.is_story = True
    else:
        trigger = Event(
            proposal.month_stamp,
            "Forged proposal object.",
            id=proposal.id,
            causal_payload={"deltas": [], "peace_proposal": deepcopy(proposal.causal_payload["peace_proposal"])},
        )
        trigger.causal_payload["peace_proposal"]["war_event_id"] = "invented-war"

    context = AffordanceContext(
        base_world, peace.RESPONSE_DOMAIN, sect_institution_ref(2), trigger
    )
    assert peace.response_affordances(context) == ()


@pytest.mark.asyncio
async def test_new_war_episode_in_the_same_month_invalidates_old_proposal(base_world, monkeypatch):
    import src.systems.institutional_peace as peace

    proposal, _mode = await _pending_proposal(base_world, monkeypatch)
    response_context = AffordanceContext(
        base_world, peace.RESPONSE_DOMAIN, sect_institution_ref(2), proposal
    )
    acceptance = next(
        option
        for option in peace.response_affordances(response_context)
        if option.action_kind == peace.ACCEPT_ACTION
    )
    with pytest.raises(StaleAffordanceError, match="not canonical"):
        peace._execute_acceptance(response_context, acceptance, decision_event=Event(base_world.month_stamp, "forged"))
    base_world.month_stamp = proposal.month_stamp
    old_relation = conclude_formal_war(
        base_world, 1, 2, current_month=int(base_world.month_stamp), evidence_event_ids=(proposal.id,)
    )
    assert old_relation is not None
    new_war = Event(
        base_world.month_stamp,
        "A new war began in the same month.",
        event_type=WAR_DECLARED_EVENT_TYPE,
        fact_kind=FactKind.STATE_TRANSITION,
        related_sects=[1, 2],
        causal_payload={"deltas": []},
    )
    relation = set_formal_war(
        base_world, 1, 2, current_month=int(base_world.month_stamp), evidence_event_ids=(new_war.id,)
    )
    record_known_fact(base_world, new_war, (sect_institution_id(1), sect_institution_id(2)))
    assert base_world.event_manager.commit_step([new_war])
    assert relation.id == proposal.causal_payload["peace_proposal"]["relation_id"]
    assert relation.since_month == old_relation.since_month == int(proposal.month_stamp)
    assert new_war.id != proposal.causal_payload["peace_proposal"]["war_event_id"]

    context = AffordanceContext(
        base_world, peace.RESPONSE_DOMAIN, sect_institution_ref(2), proposal
    )
    assert peace.response_affordances(context) == ()
