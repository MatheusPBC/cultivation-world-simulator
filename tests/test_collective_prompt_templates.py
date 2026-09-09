import pytest

from src.i18n.locale_registry import get_project_root
from src.utils.llm.prompt import build_prompt, load_template


@pytest.mark.parametrize(
    "locale,template_name",
    [
        (locale, f"{domain}_interpreter.txt")
        for locale in ("pt-BR", "zh-CN")
        for domain in ("population", "city", "economy", "government", "organization")
    ],
)
def test_collective_interpreter_templates_use_shared_domain_contract(
    locale: str, template_name: str
) -> None:
    path = get_project_root() / "static" / "locales" / locale / "templates" / template_name
    template = load_template(path)
    infos = {
        "actor": '{"kind":"population","id":"region:301"}',
        "trigger": '{"event_id":"event-1","event_type":"semantic_condition_activated"}',
        "affordances": '[{"id":"affordance-1","action_kind":"maintain"}]',
        "context": '{"condition":"grounded","region_id":"301"}',
    }

    prompt = build_prompt(template, infos)

    for value in infos.values():
        assert value in prompt
    assert "decision" in prompt
    assert "maintain" in prompt
    assert "act" in prompt
    assert "selected_affordance_id" in prompt
    assert "{actor}" not in prompt
    assert "{trigger}" not in prompt
    assert "{affordances}" not in prompt
    assert "{context}" not in prompt
    for obsolete in ("action_intent", "preferences"):
        assert obsolete not in prompt
    for obsolete_slot in ("origin", "candidates", "shortage", "destination"):
        assert "{" + obsolete_slot + "}" not in prompt
