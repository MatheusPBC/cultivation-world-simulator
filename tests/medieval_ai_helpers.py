"""Small test doubles that preserve the provider-receipt boundary."""

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind
from src.sim.medieval import ai_decider
from src.sim.medieval.events import record_event


def provider_selection_stub(chooser):
    """Wrap a selection stub so tests exercise the real receipt contract."""

    async def select_option(world, actor, situation, choices, **kwargs):
        selected = await chooser(world, actor, situation, choices, **kwargs)
        if selected is None:
            return None
        declined = selected == ai_decider.NO_ACTION
        record_event(
            world,
            ai_decider.DECLINED_EVENT if declined else ai_decider.INTERPRETED_EVENT,
            "Resposta simulada no limite do provider.",
            fact_kind=FactKind.OCCURRENCE,
            causal_origin=CausalOrigin.LLM_INTERPRETATION,
            causal_payload={"selection": {
                "actor_ref": actor.to_dict(), "selected_affordance_id": selected,
            }},
            cause_ids=kwargs.get("causes", ()),
        )
        return selected

    return select_option
