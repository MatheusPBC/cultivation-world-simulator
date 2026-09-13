"""Serve only the medieval build; never fall back to the inherited bundle."""

from pathlib import Path

from fastapi.responses import FileResponse

from .errors import RuntimeProblem

PRODUCT_MARKER = '<meta name="mws-product" content="medieval-world-simulator"'


def mount_frontend(app, frontend_dir=None):
    root = Path(frontend_dir) if frontend_dir is not None else Path(__file__).resolve().parents[3] / "web" / "dist-medieval"

    @app.get("/", include_in_schema=False)
    async def index():
        path = root / "index.html"
        if not path.is_file() or PRODUCT_MARKER not in path.read_text(encoding="utf-8"):
            raise RuntimeProblem("FRONTEND_PENDING", "Gere a interface com npm run build na pasta web. API disponível em /docs.", 503)
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    @app.get("/web_static/{asset_path:path}", include_in_schema=False)
    async def asset(asset_path: str):
        assets = (root / "web_static").resolve()
        path = (assets / asset_path).resolve()
        if not path.is_relative_to(assets) or not path.is_file():
            raise RuntimeProblem("NOT_FOUND", "Arquivo não encontrado.", 404)
        return FileResponse(path)
