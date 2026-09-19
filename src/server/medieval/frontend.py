"""Serve only the medieval build; never fall back to the inherited bundle."""

import mimetypes
from pathlib import Path

from fastapi.responses import Response

from .errors import RuntimeProblem

PRODUCT_MARKER = '<meta name="mws-product" content="medieval-world-simulator"'


def mount_frontend(app, frontend_dir=None):
    root = Path(frontend_dir) if frontend_dir is not None else Path(__file__).resolve().parents[3] / "web" / "dist-medieval"

    @app.get("/", include_in_schema=False)
    async def index():
        path = root / "index.html"
        if not path.is_file() or PRODUCT_MARKER not in path.read_text(encoding="utf-8"):
            raise RuntimeProblem("FRONTEND_PENDING", "Gere a interface com npm run build na pasta web. API disponível em /docs.", 503)
        # Returning an in-memory response keeps the ASGI observer deterministic
        # under both uvicorn and the test transport.  FileResponse's streaming
        # path can leave an in-process ASGI client waiting after the body was
        # already resolved, which makes the valid bundle path unobservable.
        return Response(path.read_bytes(), media_type="text/html", headers={"Cache-Control": "no-store"})

    @app.get("/web_static/{asset_path:path}", include_in_schema=False)
    async def asset(asset_path: str):
        assets = (root / "web_static").resolve()
        path = (assets / asset_path).resolve()
        if not path.is_relative_to(assets) or not path.is_file():
            raise RuntimeProblem("NOT_FOUND", "Arquivo não encontrado.", 404)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return Response(path.read_bytes(), media_type=media_type)
