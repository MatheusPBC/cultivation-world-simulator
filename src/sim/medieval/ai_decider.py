"""Ask a real provider to pick among options the engine already enumerated.

The model never learns the world: it sees the institution it speaks for, the
dated facts that institution already holds, the direct notice it received, and
the labels of the choices the engine composed. It answers with one existing
option ID or NO_ACTION, and nothing else it says is kept or used.

    Its answer is an interpretation, recorded as a zero-delta receipt that can
    never be the material cause of anything. The decision, the revalidation and
    the execution stay with the actor and the canonical owner. Provider mode
    treats unavailable/error/invalid/NO_ACTION as no material action.
"""

import json

from src.classes.causal_origin import CausalOrigin
from src.classes.event import FactKind

from .events import record_event

NO_ACTION = "NO_ACTION"
INTERPRETED_EVENT = "ai_decision_interpreted"
FAILED_EVENT = "ai_decision_failed"
MAX_LABEL = 160


def provider_available() -> bool:
    """A real key and model must exist outside the save for this to be true."""
    from src.utils.llm.runtime_mode import is_test_mode_enabled
    if is_test_mode_enabled():
        return False
    try:
        from src.config.settings_service import get_settings_service
        profile = get_settings_service().get_settings().llm
    except Exception:
        return False
    return bool(getattr(profile, "has_api_key", False) and getattr(profile, "model_name", ""))


def spent_calls(world, *, since_day=None):
    """Budget is read from canonical receipts; there is no separate counter."""
    return sum(1 for event in world.events
               if event.event_type in {INTERPRETED_EVENT, FAILED_EVENT}
               and (since_day is None or event.day == since_day))


def within_budget(world):
    config = world.config
    if not config.ai_enabled or not config.ai_calls_per_step:
        return False
    if config.ai_max_calls and spent_calls(world) >= config.ai_max_calls:
        return False
    return spent_calls(world, since_day=world.clock.absolute_day) < config.ai_calls_per_step


def _receipt(world, event_type, content, *, causes=()):
    """Interpretations carry no delta and never authorize a mutation."""
    return record_event(world, event_type, content, fact_kind=FactKind.OCCURRENCE,
                        causal_origin=CausalOrigin.LLM_INTERPRETATION, cause_ids=tuple(causes))


def _prompt(actor, situation, choices):
    payload = {"you_are": actor.to_dict(), "situation": situation,
               "choices": [{"id": item["id"], "label": item["label"][:MAX_LABEL]} for item in choices],
               "answer_format": {"selected_id": f"one choice id or {NO_ACTION}"}}
    return ("Você decide por um ator do mundo medieval. Escolha exatamente uma opção da lista "
            "ou NO_ACTION. Responda somente JSON no formato indicado.\n"
            + json.dumps(payload, sort_keys=True, ensure_ascii=False))


async def select_option(world, actor, situation, choices, *, causes=()):
    """Return a chosen option ID, or None when provider mode must do nothing.

    ``situation`` and ``choices`` are built by the caller from the actor's own
    knowledge; this function adds nothing and mutates nothing.
    """
    if not choices:
        return None
    if not within_budget(world) or not provider_available():
        _receipt(world, FAILED_EVENT, "Consulta ao provedor indisponível; nenhuma ação material foi tomada.",
                 causes=causes)
        return None
    from src.utils.llm.client import call_llm_json
    try:
        answer = await call_llm_json(_prompt(actor, situation, choices))
    except Exception:
        # Provider errors, timeouts and parse failures are all the same to the
        # world: no interpretation happened and nothing material changed.
        _receipt(world, FAILED_EVENT, "O provedor falhou; nenhuma ação material foi tomada.", causes=causes)
        return None
    selected = answer.get("selected_id") if isinstance(answer, dict) else None
    known = {item["id"] for item in choices}
    if selected == NO_ACTION:
        _receipt(world, INTERPRETED_EVENT, "O provedor optou por não agir.", causes=causes)
        return NO_ACTION
    if not isinstance(selected, str) or selected not in known:
        _receipt(world, FAILED_EVENT, "O provedor devolveu uma escolha inexistente; nenhuma ação material foi tomada.",
                 causes=causes)
        return None
    # Only the ID survives: every other word of the answer is discarded.
    _receipt(world, INTERPRETED_EVENT, "O provedor indicou uma das opções enumeradas.", causes=causes)
    return selected
