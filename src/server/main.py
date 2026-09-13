"""Application entrypoint for the medieval fork (no alternate xianxia runtime)."""

import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.server.encoding_runtime import configure_process_encoding

configure_process_encoding()

from src.server.medieval.app import create_app

app = create_app()


def start():
    import uvicorn
    from src.server.bootstrap import resolve_server_binding

    host, port = resolve_server_binding()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("O runtime local não possui autenticação; use uma interface de loopback.")
    print(f"Medieval World Simulator — API local: http://{host}:{port}/docs")
    print(f"Observatório: http://{host}:{port}/ (gere web/dist-medieval com npm run build)")
    uvicorn.run(app, host=host, port=port, log_level=os.environ.get("MWS_LOG_LEVEL", "info"))


if __name__ == "__main__":
    start()
