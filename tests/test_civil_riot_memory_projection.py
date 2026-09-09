import pytest

from src.classes.mechanical_language import EntityRef
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.server.services.game_queries import get_event_causal_detail
from src.systems.institutional_memory import decision_context
from tests.test_civil_riot import _riot, rioting as _rioting  # noqa: F401
from tests.test_civil_petition import aggrieved  # noqa: F401


def _serialize(events, **_kwargs):
    return [event.to_dict() for event in events]


@pytest.mark.asyncio
async def test_real_riot_memory_keeps_damage_in_dynasty_chain_and_why(
    base_world, _rioting  # noqa: F811
):
    city, trigger, condition = _rioting
    _option, decision, riot = await _riot(base_world, city, trigger, condition)
    for event in (trigger, decision, riot):
        base_world.event_manager.add_event(event)

    institution_id = riot.causal_payload["civil_riot"]["addressed_institution_id"]
    chain = build_institutional_chain(
        base_world, owner_kind="dynasty", owner_id="1"
    )
    memories = [item for item in chain["memories"] if item["event_id"] == riot.id]
    assert len(memories) == 1
    factors = dict(memories[0]["factors"])
    assert factors["relative_scale"] == pytest.approx(
        riot.causal_payload["civil_riot"]["damage"]
    )
    assert factors["institutional_change"] == 0.0
    assert factors["commitment_breach"] == 0.0
    assert factors["identity_anchor_impact"] == 0.0

    why = get_event_causal_detail(
        {"world": base_world},
        serialize_events_for_client=_serialize,
        event_id=riot.id,
    )
    assert riot.id == why["event"]["id"]
    assert {item["event"]["id"] for item in why["causes"]} == {
        trigger.id,
        decision.id,
    }
    assert base_world.institutional_knowledge.contains(institution_id, riot.id)


@pytest.mark.asyncio
async def test_riot_memory_is_not_leaked_to_city_context(base_world, _rioting):  # noqa: F811
    city, trigger, condition = _rioting
    _option, decision, riot = await _riot(base_world, city, trigger, condition)
    for event in (trigger, decision, riot):
        base_world.event_manager.add_event(event)
    dynasty_id = riot.causal_payload["civil_riot"]["addressed_institution_id"]
    dynasty_context = decision_context(base_world, dynasty_id)
    assert riot.id in {fact["event_id"] for fact in dynasty_context["known_facts"]}
    city_institution = base_world.institutional_authority.get_institution_for_owner(
        EntityRef("region", str(city.id))
    )
    assert city_institution is not None
    context = decision_context(base_world, city_institution.id)
    assert riot.id not in {fact["event_id"] for fact in context["known_facts"]}
