from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.utils.llm.client import _call_with_requests
from src.utils.llm.config import LLMConfig


def test_codex_cli_provider_reads_last_message_file():
    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("CODEX_RESPONSE", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    config = LLMConfig(
        base_url="codex://local",
        api_key="",
        model_name="gpt-test",
        api_format="codex_cli",
    )

    with patch("src.utils.llm.client.subprocess.run", side_effect=fake_run) as run:
        assert _call_with_requests(config, "prompt") == "CODEX_RESPONSE"

    run.assert_called_once()
    command = run.call_args.args[0]
    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--ephemeral" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert run.call_args.kwargs["input"] == "prompt"
