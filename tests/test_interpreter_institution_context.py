"""Institutional actors decide with their own history in front of them.

The government and organization interpreters project the existing
`institutional_memory.decision_context` into the prompt: only facts the
institution really knows, and only the office that could actually authorize
the choice at hand. Nothing here creates state, memory, or a leader.

These tests render the **real** template with `build_prompt`, because a
template without the `{actor}`/`{trigger}`/`{affordances}`/`{context}` slots
silently drops every info. A valid `act` is still *expressible* -- the
`output_schema` enumerates the offered ids independently of the prompt -- but
the choice would be made blind: what each option actually is, its parameters
and urgency, the trigger, and the institution's own known history would all be
absent from the text the model reads.
"""

from __future__ import annotations

import pytest

from src.classes.event import Event, FactKind
from src.classes.causal_origin import CausalOrigin
from src.classes.institution import AuthorityScope, KnowledgeChannel
from src.classes.mechanical_language import EntityRef
from src.i18n.locale_registry import get_project_root
from src.systems.domain_affordance_registry import DOMAIN_AFFORDANCES
from src.systems.government_interpreter import (
    GOVERNMENT_INTERPRETER_TEMPLATE,
    government_affordance_context,
    interpret_government_transition,
)
from src.systems.institution_bootstrap import bootstrap_institutional_authority
from src.systems.institutional_memory import record_known_fact
from src.systems.organization_interpreter import (
    ORGANIZATION_INTERPRETER_TEMPLATE,
    interpret_organization_transition,
    organization_affordance_context,
)
from src.utils.llm.prompt import build_prompt, load_template
from tests.test_civil_petition import aggrieved  # noqa: F401
from tests.test_organization_reactivity_integration import _setup as _setup_sect


TEMPLATE_LOCALES = ("pt-BR", "zh-CN")
TEMPLATE_SLOTS = ("{actor}", "{trigger}", "{affordances}", "{context}")


class _Capture:
    """A fake boundary: it records what the engine offered and picks an ID.

    Never a provider. It returns the shape the real schema demands, so an
    engine that cannot express a valid `act` fails the test loudly.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, task_name, template, infos, *, output_schema=None):
        self.calls.append({
            "task_name": task_name,
            "template": template,
            "infos": infos,
            "output_schema": output_schema,
        })
        ids = list(output_schema["properties"]["selected_affordance_id"]["enum"])
        return {
            "decision": "act",
            "reason": "The institution answers with its own history in view.",
            "selected_affordance_id": ids[0],
        }

    @property
    def only(self) -> dict:
        assert len(self.calls) == 1, f"expected one boundary call, got {len(self.calls)}"
        return self.calls[0]

    def rendered(self) -> str:
        call = self.only
        return build_prompt(load_template(call["template"]), call["infos"])


def _live_world(world) -> None:
    """A world that really reaches the boundary: no test-mode short circuit."""
    world.run_config_snapshot = {}


def _known_fact(world, institution_id: str, *, content: str) -> Event:
    """One canonical fact this institution genuinely learned, with memory."""
    event = Event(
        world.month_stamp,
        content,
        event_type="institutional_probe_fact",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        render_params={},
        causal_payload={"deltas": []},
    )
    world.event_manager.add_event(event)
    record_known_fact(
        world,
        event,
        (institution_id,),
        factors={"institutional_change": 1.0},
        channel=KnowledgeChannel.OWN_ACTION,
    )
    return event


def _unknown_fact(world, *, content: str) -> Event:
    """A real fact nobody was ever told about."""
    event = Event(
        world.month_stamp,
        content,
        event_type="institutional_probe_fact",
        fact_kind=FactKind.OCCURRENCE,
        causal_origin=CausalOrigin.DETERMINISTIC,
        render_params={},
        causal_payload={"deltas": []},
    )
    world.event_manager.add_event(event)
    return event


def _dynasty_institution_id(world) -> str:
    institution = world.institutional_authority.get_institution_for_owner(
        EntityRef("dynasty", str(world.dynasty.id))
    )
    assert institution is not None
    return institution.id


def _sect_institution_id(sect) -> str:
    from src.systems.institutional_diplomacy import sect_institution_id

    return sect_institution_id(str(sect.id))


# --------------------------------------------------------------------------
# The templates themselves
# --------------------------------------------------------------------------


@pytest.mark.parametrize("locale", TEMPLATE_LOCALES)
@pytest.mark.parametrize(
    "name", (GOVERNMENT_INTERPRETER_TEMPLATE, ORGANIZATION_INTERPRETER_TEMPLATE)
)
def test_the_templates_carry_the_real_slots_and_the_real_schema(locale, name):
    """A slot-less template drops every info, so the slots are the contract."""
    path = get_project_root() / "static" / "locales" / locale / "templates" / name
    text = load_template(path)

    for slot in TEMPLATE_SLOTS:
        assert slot in text, f"{locale}/{name} is missing {slot}"
    # The runtime accepts only `maintain`/`act` plus `selected_affordance_id`.
    assert "selected_affordance_id" in text
    assert "maintain" in text
    # No field the parser would reject as unsupported.
    for obsolete in (
        "capability_id", "project_kind", "action_intent",
        "member_id", "support_member",
    ):
        assert obsolete not in text, f"{locale}/{name} still asks for {obsolete}"


# --------------------------------------------------------------------------
# Government
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_government_prompt_carries_its_known_history_and_holder(
    base_world, aggrieved  # noqa: F811
):
    """Known fact, holder name and every offered ID reach the rendered text."""
    city, trigger, condition = aggrieved
    _live_world(base_world)
    institution_id = _dynasty_institution_id(base_world)
    known = _known_fact(base_world, institution_id, content="A remembered audience.")
    hidden = _unknown_fact(base_world, content="A fact nobody reported.")

    context = government_affordance_context(base_world, trigger, condition)[0]
    offered = DOMAIN_AFFORDANCES.compose(context)
    assert offered, "the fixture offered the government nothing to decide about"

    capture = _Capture()
    decision, event = await interpret_government_transition(
        base_world, trigger, condition, llm_call=capture
    )

    # The engine reached the boundary and accepted the ID it had offered.
    assert decision.selected_affordance_id in {item.id for item in offered}
    assert event.fact_kind is FactKind.DECISION

    prompt = capture.rendered()
    # Every offered option is really in the text the model would read.
    for option in offered:
        assert option.id in prompt
    # Its own known history is there; what it never learned is not.
    assert known.content in prompt
    assert hidden.content not in prompt
    assert hidden.id not in prompt
    # And the current authorized holder is named.
    holder = capture.only["infos"]["context"]["institution"]["authorized_holder"]
    assert holder is not None
    assert holder["holder"]["name"] in prompt

    # The scope projected is the one that could authorize this choice.
    assert holder["office_id"] in prompt
    verdict_scopes = base_world.institutional_authority.offices[
        holder["office_id"]
    ].scopes
    assert AuthorityScope.URBAN_ADMINISTRATION in verdict_scopes


@pytest.mark.asyncio
async def test_replacing_the_holder_changes_the_persona_but_not_the_memory(
    base_world, aggrieved  # noqa: F811
):
    """Offices outlive their holders: memory is the institution's, not theirs."""
    city, trigger, condition = aggrieved
    _live_world(base_world)
    institution_id = _dynasty_institution_id(base_world)
    known = _known_fact(base_world, institution_id, content="A remembered audience.")

    first = _Capture()
    await interpret_government_transition(
        base_world, trigger, condition, llm_call=first
    )
    before = first.only["infos"]["context"]["institution"]
    assert before["authorized_holder"]["holder"]["name"] in first.rendered()

    # The sovereign really changes, through the runtime reconciliation the
    # government phase itself runs -- not by re-bootstrapping the premise,
    # which is deliberately idempotent and moves no holder.
    from src.systems.institution_bootstrap import synchronize_institutional_authority
    from tests.test_civil_petition import _emperor

    old_id = str(base_world.dynasty.current_emperor_id)
    base_world.avatar_manager.get_avatar(old_id).is_dead = True
    successor = _emperor(base_world)
    successor.name = "Successor"
    base_world.dynasty.current_emperor_id = successor.id
    synchronize_institutional_authority(base_world)

    second = _Capture()
    await interpret_government_transition(
        base_world, trigger, condition, llm_call=second
    )
    after = second.only["infos"]["context"]["institution"]

    assert after["authorized_holder"]["holder"]["id"] == str(successor.id)
    assert "Successor" in second.rendered()
    # The same institution still remembers the same fact.
    assert [fact["event_id"] for fact in after["known_facts"]] == [
        fact["event_id"] for fact in before["known_facts"]
    ]
    assert known.content in second.rendered()


@pytest.mark.asyncio
async def test_an_unregistered_institution_can_neither_act_nor_name_a_leader(
    base_world, aggrieved  # noqa: F811
):
    """Fail closed on both questions, and in the right order.

    An institution the authority state does not hold cannot administer the
    city, so the government menu is empty and the boundary is never reached --
    the material refusal happens before any owner runs. Its projection is
    `None` too: a missing record never becomes an invented holder.
    """
    city, trigger, condition = aggrieved
    _live_world(base_world)
    # Authority state really loses this institution.
    base_world.institutional_authority.institutions.clear()
    base_world.institutional_authority.offices.clear()

    context = government_affordance_context(base_world, trigger, condition)[0]
    assert DOMAIN_AFFORDANCES.compose(context) == ()

    capture = _Capture()
    decision, event = await interpret_government_transition(
        base_world, trigger, condition, llm_call=capture
    )

    assert capture.calls == []
    assert decision.selected_affordance_id is None
    assert event.causal_payload["decision"]["source"] == "rule"
    # And no leader was invented for a record that does not exist.
    from src.systems.government_interpreter import _institution_context

    assert _institution_context(base_world, base_world.dynasty, trigger) is None


@pytest.mark.asyncio
async def test_no_options_never_reaches_the_boundary(base_world, aggrieved):  # noqa: F811
    """Nothing to choose is a deterministic maintain, not a prompt."""
    from dataclasses import replace

    city, trigger, condition = aggrieved
    _live_world(base_world)
    # An intact city with room to spare can materially do nothing.
    city.city_state = replace(
        city.city_state,
        assets=tuple(
            replace(asset, integrity=1.0) for asset in city.city_state.assets
        ),
    )
    context = government_affordance_context(base_world, trigger, condition)[0]
    assert DOMAIN_AFFORDANCES.compose(context) == ()

    capture = _Capture()
    decision, event = await interpret_government_transition(
        base_world, trigger, condition, llm_call=capture
    )

    assert capture.calls == []
    assert decision.selected_affordance_id is None
    assert event.causal_payload["decision"]["source"] == "rule"


# --------------------------------------------------------------------------
# Organization
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_sect_prompt_carries_its_treasury_office_and_known_history(
    base_world,
):
    """The sect decides on its own memory, under the office that pays."""
    sect, avatar, city, trigger, condition = _setup_sect(base_world)
    _live_world(base_world)
    # A sect office needs the single *living* patriarch the owner requires: a
    # rank-and-file member authorizes nothing, and an office whose holder the
    # avatar manager cannot find is correctly refused as dead.
    from src.classes.sect_ranks import SectRank

    avatar.sect_rank = SectRank.Patriarch
    base_world.avatar_manager.register_avatar(avatar)
    bootstrap_institutional_authority(base_world)
    institution_id = _sect_institution_id(sect)
    assert base_world.institutional_authority.get_institution(institution_id)
    known = _known_fact(base_world, institution_id, content="A remembered tribute.")
    hidden = _unknown_fact(base_world, content="A rival's secret loss.")

    context = organization_affordance_context(
        base_world, sect, city, condition, trigger
    )
    offered = DOMAIN_AFFORDANCES.compose(context)
    assert offered, "the fixture offered the sect nothing to decide about"

    capture = _Capture()
    decision, _event = await interpret_organization_transition(
        base_world, sect, city, condition, trigger, llm_call=capture
    )

    assert decision.selected_affordance_id in {item.id for item in offered}
    prompt = capture.rendered()
    for option in offered:
        assert option.id in prompt
    assert known.content in prompt
    assert hidden.content not in prompt

    holder = capture.only["infos"]["context"]["institution"]["authorized_holder"]
    assert holder is not None
    assert holder["holder"]["name"] in prompt
    # Supporting a member spends the sect's treasury, so that is the scope.
    scopes = base_world.institutional_authority.offices[holder["office_id"]].scopes
    assert AuthorityScope.TREASURY_DISPOSITION in scopes


@pytest.mark.asyncio
async def test_the_engine_alone_owns_the_amounts_and_the_member(base_world):
    """Context is perspective: quantities and identities come from the engine."""
    sect, avatar, city, trigger, condition = _setup_sect(base_world)
    _live_world(base_world)
    # A sect office needs the single *living* patriarch the owner requires: a
    # rank-and-file member authorizes nothing, and an office whose holder the
    # avatar manager cannot find is correctly refused as dead.
    from src.classes.sect_ranks import SectRank

    avatar.sect_rank = SectRank.Patriarch
    base_world.avatar_manager.register_avatar(avatar)
    bootstrap_institutional_authority(base_world)
    before_sect = int(sect.magic_stone)

    capture = _Capture()
    decision, _event = await interpret_organization_transition(
        base_world, sect, city, condition, trigger, llm_call=capture
    )

    # The boundary was given IDs only; it never chose a member or an amount.
    schema = capture.only["output_schema"]
    assert set(schema["properties"]) == {
        "decision", "reason", "selected_affordance_id"
    }
    assert schema["additionalProperties"] is False
    option = next(
        item
        for item in DOMAIN_AFFORDANCES.compose(
            organization_affordance_context(
                base_world, sect, city, condition, trigger
            )
        )
        if item.id == decision.selected_affordance_id
    )
    assert str(option.parameters["member_id"]) == str(avatar.id)
    # Interpreting alone moved no money: execution is a separate step.
    assert int(sect.magic_stone) == before_sect
