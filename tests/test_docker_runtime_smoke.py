import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def request(port, path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if data is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.docker
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not found in PATH")
def test_medieval_docker_v2_lifecycle():
    with tempfile.TemporaryDirectory() as work_dir:
        codex_dir = Path(work_dir) / "empty-codex-home"
        codex_dir.mkdir()
        node_file = Path(work_dir) / "empty-node"
        node_file.touch()
        codex_module_dir = Path(work_dir) / "empty-codex-module"
        codex_module_dir.mkdir()
        override = Path(work_dir) / "compose.override.yml"
        override.write_text(f'''services:\n  backend:\n    volumes:\n      - cws_smoke_data:/data\n      - "{codex_dir}:/codex-home:ro"\n      - "{node_file}:/usr/bin/node:ro"\n      - "{codex_module_dir}:/usr/lib/node_modules/@openai/codex:ro"\n  frontend: {{}}\nvolumes:\n  cws_smoke_data: {{}}\n''')
        project = f"cws-smoke-{uuid.uuid4().hex[:10]}"
        compose = ["docker", "compose", "-p", project, "-f", "docker-compose.yml", "-f", str(override)]
        env = {**os.environ, "CWS_BIND_IP": "127.0.0.1", "CWS_BACKEND_PORT": "0", "CWS_FRONTEND_PORT": "0"}
        try:
            subprocess.run(compose + ["up", "-d", "--build"], cwd=ROOT, env=env, check=True, timeout=900)
            backend_port = int(subprocess.check_output(compose + ["port", "backend", "8002"], cwd=ROOT, env=env, text=True).rsplit(":", 1)[1])
            frontend_port = int(subprocess.check_output(compose + ["port", "frontend", "80"], cwd=ROOT, env=env, text=True).rsplit(":", 1)[1])
            deadline = time.time() + 180
            while time.time() < deadline:
                try:
                    if request(backend_port, "/api/health").get("ok"):
                        break
                except Exception:
                    time.sleep(2)
            else:
                raise AssertionError("/api/health did not become ready")
            status = request(backend_port, "/api/v2/query/status")
            assert status["ok"] is True and status["data"]["ready"] is False
            deadline = time.time() + 180
            while time.time() < deadline:
                try:
                    frontend_health = request(frontend_port, "/api/health")
                    if frontend_health.get("ok") is True:
                        break
                except Exception:
                    time.sleep(2)
            else:
                raise AssertionError("frontend /api/health did not become ready")
            assert frontend_health["product"] == "medieval-world-simulator"
            with urllib.request.urlopen(f"http://127.0.0.1:{frontend_port}/", timeout=10) as response:
                html = response.read().decode()
            assert response.status == 200 and 'name="mws-product" content="medieval-world-simulator"' in html
            created = request(backend_port, "/api/v2/command/create", "POST", {"seed": 73, "character_count": 2, "replace": False})
            assert created["ok"] is True and created["data"]["ready"] is True and created["data"]["paused"] is True
            initial = request(backend_port, "/api/v2/query/observatory")
            assert initial["ok"] is True and initial["data"]["world"]["day"] == 0
            assert initial["data"]["world"]["config"]["seed"] == 73
            assert request(backend_port, "/api/v2/command/step", "POST", {})["ok"] is True
            stepped = request(backend_port, "/api/v2/query/observatory")
            assert stepped["data"]["world"]["day"] > initial["data"]["world"]["day"]
            assert request(backend_port, "/api/v2/command/pause", "POST", {})["ok"] is True
            assert request(backend_port, "/api/v2/command/resume", "POST", {})["ok"] is True
            assert request(backend_port, "/api/v2/command/pause", "POST", {})["ok"] is True
            saved_state = request(backend_port, "/api/v2/query/observatory")
            saved_day = saved_state["data"]["world"]["day"]
            assert request(backend_port, "/api/v2/command/save", "POST", {"save_id": "docker-smoke-v2", "overwrite": False})["ok"] is True
            assert any(item["save_id"] == "docker-smoke-v2" for item in request(backend_port, "/api/v2/query/saves")["data"])
            subprocess.run(compose + ["restart", "backend"], cwd=ROOT, env=env, check=True, timeout=180)
            previous_backend_port = backend_port
            backend_port = int(
                subprocess.check_output(
                    compose + ["port", "backend", "8002"], cwd=ROOT, env=env, text=True
                ).rsplit(":", 1)[1]
            )
            print(f"backend published port before restart={previous_backend_port}, after restart={backend_port}")
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    if request(backend_port, "/api/health").get("ok"):
                        break
                except Exception:
                    time.sleep(2)
            else:
                raise AssertionError("backend did not recover after restart")
            assert any(item["save_id"] == "docker-smoke-v2" for item in request(backend_port, "/api/v2/query/saves")["data"])
            loaded = request(backend_port, "/api/v2/command/load", "POST", {"save_id": "docker-smoke-v2"})
            assert loaded["ok"] is True and loaded["data"]["paused"] is True
            restored = request(backend_port, "/api/v2/query/observatory")
            assert restored["data"]["world"]["day"] == saved_day
            assert restored["data"]["world"]["config"]["seed"] == 73
        except Exception:
            logs = subprocess.run(
                compose + ["logs", "--tail", "80"],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            print(logs.stdout)
            print(logs.stderr)
            raise
        finally:
            subprocess.run(compose + ["down", "-v", "--remove-orphans"], cwd=ROOT, env=env, check=False, timeout=180)
