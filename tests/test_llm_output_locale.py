from unittest.mock import patch

import pytest

from src.classes.language import language_manager
from src.utils.llm.client import call_llm
from src.utils.llm.config import LLMConfig


@pytest.mark.asyncio
async def test_call_llm_requires_natural_brazilian_portuguese_for_ptbr_games():
    original_locale = str(language_manager)
    provider_prompts: list[str] = []
    config = LLMConfig(
        model_name="test-model",
        api_key="test-key",
        base_url="http://test.api/v1",
    )

    def fake_provider(_config: LLMConfig, prompt: str) -> str:
        provider_prompts.append(prompt)
        return "ok"

    try:
        language_manager.set_language("pt-BR")
        with (
            patch("src.utils.llm.client.LLMConfig.from_mode", return_value=config),
            patch("src.utils.llm.client._call_with_requests", side_effect=fake_provider),
        ):
            assert await call_llm("Retorne o objeto JSON solicitado.") == "ok"
    finally:
        language_manager.set_language(original_locale)

    assert len(provider_prompts) == 1
    provider_prompt = provider_prompts[0]
    assert provider_prompt.startswith("Retorne o objeto JSON solicitado.")
    assert "português brasileiro natural e claro" in provider_prompt
    assert "Adapte expressões e termos de cultivo" in provider_prompt
    assert "Preserve as chaves JSON" in provider_prompt
    assert "Não use chinês, japonês ou inglês" in provider_prompt
