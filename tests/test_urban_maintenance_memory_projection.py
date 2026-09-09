import pytest

from src.classes.domain_affordance import DomainDecision, DomainDecisionKind
from src.server.assemblers.institutional_chain import build_institutional_chain
from src.server.services.game_queries import get_event_causal_detail
from src.systems.collective_affordances import DOMAIN_AFFORDANCES, government_affordances
from src.systems.government_interpreter import interpret_government_transition
from tests.test_civil_riot import (
    _government_context,
    _riot,
    rioting as _rioting,  # noqa: F401
)
from tests.test_civil_petition import aggrieved  # noqa: F401


def _serialize(events, **_kwargs):
    return [event.to_dict() for event in events]


@pytest.mark.asyncio
async def test_government_maintenance_adds_an_actual_repair_memory(
    base_world, _rioting  # noqa: F811
):
    city, trigger, condition = _rioting
    _option, population_decision, riot = await _riot(
        base_world, city, trigger, condition
    )
    for event in (trigger, population_decision, riot):
        base_world.event_manager.add_event(event)
    before = city.city_state.assets[0].integrity
    context = _government_context(base_world, riot, condition)
    maintenance = next(
        option for option in government_affordances(context)
        if option.action_kind == "urban_maintenance"
    )
    government_decision, government_decision_event = (
        await interpret_government_transition(
            base_world,
            riot,
            condition,
            force_rule=True,
            injected_decision=DomainDecision(
                DomainDecisionKind.ACT,
                "Repair the damaged urban asset.",
                maintenance.id,
            ),
        )
    )
    assert government_decision.selected_affordance_id == maintenance.id
    repair = DOMAIN_AFFORDANCES.execute(
        context,
        maintenance.id,
        decision_event_id=government_decision_event.id,
        decision_event=government_decision_event,
    )
    base_world.event_manager.add_event(government_decision_event)
    base_world.event_manager.add_event(repair)
    assert repair.event_type == "city_maintenance_completed"
    assert city.city_state.assets[0].integrity > before

    institution_id = riot.causal_payload["civil_riot"]["addressed_institution_id"]
    chain = build_institutional_chain(
        base_world, owner_kind="dynasty", owner_id="1"
    )
    memory_ids = {item["event_id"] for item in chain["memories"]}
    assert {riot.id, repair.id}.issubset(memory_ids)
    repair_delta = repair.causal_payload["deltas"][0]
    repair_memory = next(
        item for item in chain["memories"] if item["event_id"] == repair.id
    )
    assert dict(repair_memory["factors"])["relative_scale"] == pytest.approx(
        float(repair_delta["after"]) - float(repair_delta["before"])
    )
    assert base_world.institutional_knowledge.contains(institution_id, repair.id)
    why = get_event_causal_detail(
        {"world": base_world},
        serialize_events_for_client=_serialize,
        event_id=repair.id,
    )
    assert government_decision_event.id in {
        item["event"]["id"] for item in why["causes"] if item["event"]
    }
