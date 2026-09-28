from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import src.utils.llm.client as llm_client
from src.utils.llm.client import _call_with_requests
from src.utils.llm.config import LLMConfig
from src.utils.llm.exceptions import ProviderCallError
from tools.medieval_provider_civil_probe import _run_probe


def test_probe_runner_returns_after_worker_exception():
    def fail_in_worker():
        raise RuntimeError("synthetic provider failure")

    async def run_worker():
        try:
            await asyncio.to_thread(fail_in_worker)
        except RuntimeError as exc:
            return str(exc)

    assert _run_probe(run_worker()) == "synthetic provider failure"


def test_codex_cli_async_call_observes_completed_process_worker(tmp_path, monkeypatch):
    codex = tmp_path / "fake-codex"
    codex.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "args = sys.argv\n"
        "path = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
        "sys.stdin.read()\n"
        "path.write_text('ASYNC_CODEX_RESPONSE', encoding='utf-8')\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    config = LLMConfig(
        base_url="codex://local",
        api_key="",
        model_name="gpt-test",
        api_format="codex_cli",
    )
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: str(codex))
    monkeypatch.setattr(llm_client.LLMConfig, "from_mode", lambda _: config)
    monkeypatch.setattr(llm_client, "_get_semaphore", lambda: asyncio.Semaphore(1))
    monkeypatch.setattr(llm_client, "is_test_mode_enabled", lambda: False)
    monkeypatch.setattr(llm_client, "log_llm_call", lambda *args, **kwargs: None)

    assert _run_probe(llm_client.call_llm("prompt")) == "ASYNC_CODEX_RESPONSE"


def test_codex_cli_provider_reads_last_message_file():
    communicated = {}

    def fake_popen(command, **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text("CODEX_RESPONSE", encoding="utf-8")

        def communicate(*, input, timeout):
            communicated.update(input=input, timeout=timeout)
            return "", ""

        return SimpleNamespace(
            returncode=0,
            pid=123,
            communicate=communicate,
        )

    config = LLMConfig(
        base_url="codex://local",
        api_key="",
        model_name="gpt-test",
        api_format="codex_cli",
    )

    with patch("src.utils.llm.client.shutil.which", return_value="/test/codex"), \
         patch("src.utils.llm.client.subprocess.Popen", side_effect=fake_popen) as popen:
        assert _call_with_requests(config, "prompt") == "CODEX_RESPONSE"

    popen.assert_called_once()
    command = popen.call_args.args[0]
    assert command[:2] == ["/test/codex", "exec"]
    assert "--ephemeral" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert popen.call_args.kwargs["stdin"] is llm_client.subprocess.PIPE
    assert popen.call_args.kwargs["start_new_session"] is (os.name == "posix")
    assert "CODEX_HOME" not in popen.call_args.kwargs["env"]
    assert communicated["input"] == "prompt"
    assert communicated["timeout"] == llm_client._CODEX_CLI_TIMEOUT_SECONDS


def test_codex_cli_provider_applies_and_cleans_output_schema():
    captured_schema_path = None

    def fake_popen(command, **kwargs):
        nonlocal captured_schema_path
        captured_schema_path = Path(command[command.index("--output-schema") + 1])
        assert json.loads(captured_schema_path.read_text(encoding="utf-8")) == {
            "type": "object",
            "required": ["title"],
        }
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"title":"Chapter"}', encoding="utf-8")
        return SimpleNamespace(
            returncode=0,
            pid=123,
            communicate=lambda **_: ("", ""),
        )

    config = LLMConfig(
        base_url="codex://local",
        api_key="",
        model_name="gpt-test",
        api_format="codex_cli",
    )

    with patch("src.utils.llm.client.subprocess.Popen", side_effect=fake_popen):
        assert _call_with_requests(
            config,
            "prompt",
            output_schema={"type": "object", "required": ["title"]},
        ) == '{"title":"Chapter"}'

    assert captured_schema_path is not None
    assert not captured_schema_path.exists()


@pytest.mark.skipif(
    os.name != "posix" or not sys.platform.startswith("linux"),
    reason="Codex process-group cleanup check uses Linux process state",
)
def test_codex_cli_timeout_does_not_wait_on_detached_helper_pipes(tmp_path, monkeypatch):
    codex = tmp_path / "fake-codex"
    child_pid_path = tmp_path / "child.pid"
    codex.write_text(
        "#!/usr/bin/env python3\n"
        "import os, subprocess, sys, time\n"
        "child_code = 'import time; time.sleep(30)'\n"
        "group_child = subprocess.Popen([sys.executable, '-c', child_code])\n"
        "detached_child = subprocess.Popen([sys.executable, '-c', child_code], start_new_session=True)\n"
        "open(os.environ['CWS_TEST_CHILD_PID_FILE'], 'w').write(\n"
        "    str(group_child.pid) + ',' + str(detached_child.pid))\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    config = LLMConfig(
        base_url="codex://local",
        api_key="",
        model_name="gpt-test",
        api_format="codex_cli",
    )
    monkeypatch.setenv("CWS_TEST_CHILD_PID_FILE", str(child_pid_path))
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: str(codex))
    monkeypatch.setattr(llm_client, "_CODEX_CLI_TIMEOUT_SECONDS", 0.2)
    with pytest.raises(ProviderCallError, match="timed out"):
        _call_with_requests(config, "prompt")

    group_pid, detached_pid = map(int, child_pid_path.read_text(encoding="utf-8").split(","))
    group_stat = Path(f"/proc/{group_pid}/stat")
    detached_stat = Path(f"/proc/{detached_pid}/stat")
    try:
        group_state = (
            group_stat.read_text(encoding="utf-8").split(") ", 1)[1].split()[0]
            if group_stat.exists() else None
        )
        detached_state = (
            detached_stat.read_text(encoding="utf-8").split(") ", 1)[1].split()[0]
            if detached_stat.exists() else None
        )
        assert group_state in {None, "Z"}
        assert detached_state not in {None, "Z"}
    finally:
        # The detached helper is outside the CLI process group; clean up the
        # fixture after proving the caller returned despite its open pipes.
        try:
            os.kill(detached_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not detached_stat.exists() or detached_stat.read_text(encoding="utf-8").split(") ", 1)[1].split()[0] == "Z":
                break
            time.sleep(0.02)
        else:
            pytest.fail(f"test helper process {detached_pid} could not be cleaned up")
