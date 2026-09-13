"""FastAPI assembly for the exclusively medieval observer contract."""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import queries
from .contracts import (CausalView, CreateRequest, EconomyView, EmptyRequest, Envelope, EventsView, GovernanceView, LoadRequest,
                        MapView, ObservatoryView, OptionsView, ResearchView, SaveRequest, SaveView, SocietyView, SpeedRequest, StatusView, WorldView)
from .errors import RuntimeProblem
from .runtime import MedievalRuntime
from .save_files import list_save_files


def create_app(*, save_dir=None, frontend_dir=None):
    runtime = MedievalRuntime(save_dir=save_dir)

    @asynccontextmanager
    async def lifespan(app):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="Medieval World Simulator", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?",
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False)

    def error(code, message, status):
        return JSONResponse(status_code=status, content={"ok": False, "error": {"code": code, "message": message},
                                                         "revision": runtime.revision})

    @app.middleware("http")
    async def command_guard(request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api/v2/command/"):
            origin = request.headers.get("origin")
            if origin:
                try:
                    parts = urlsplit(origin)
                    accepted = parts.scheme in {"http", "https"} and parts.hostname in {"localhost", "127.0.0.1", "::1", "testserver"}
                except ValueError:
                    accepted = False
                if not accepted:
                    return error("ORIGIN_FORBIDDEN", "Origem não autorizada para comandos locais.", 403)
            if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                return error("JSON_REQUIRED", "Envie o comando como JSON.", 415)
        return await call_next(request)

    @app.exception_handler(RuntimeProblem)
    async def runtime_error(request, exc):
        return error(exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error("INVALID_REQUEST", "Parâmetros inválidos para esta operação.", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error("NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR", "Operação não disponível.", exc.status_code)

    @app.get("/api/health")
    async def health():
        return {"ok": True, "product": "medieval-world-simulator", "status": "ready"}

    @app.get("/api/v2/query/status", response_model=Envelope[StatusView])
    async def status():
        return await runtime.read(lambda r: r.status())

    @app.get("/api/v2/query/observatory", response_model=Envelope[ObservatoryView])
    async def observatory():
        return await runtime.read(queries.observatory_view)

    @app.get("/api/v2/query/options", response_model=Envelope[OptionsView])
    async def options():
        return await runtime.read(lambda r: OptionsView())

    @app.get("/api/v2/query/world", response_model=Envelope[WorldView])
    async def world():
        return await runtime.read(lambda r: queries.world_view(r.require_world()))

    @app.get("/api/v2/query/society", response_model=Envelope[SocietyView])
    async def society():
        return await runtime.read(lambda r: queries.society_view(r.require_world()))

    @app.get("/api/v2/query/economy", response_model=Envelope[EconomyView])
    async def economy():
        return await runtime.read(lambda r: queries.economy_view(r.require_world()))

    @app.get("/api/v2/query/map", response_model=Envelope[MapView])
    async def game_map():
        return await runtime.read(lambda r: queries.map_view(r.require_world()))

    @app.get("/api/v2/query/governance", response_model=Envelope[GovernanceView])
    async def governance():
        return await runtime.read(lambda r: queries.governance_view(r.require_world()))

    @app.get("/api/v2/query/events", response_model=Envelope[EventsView])
    async def events(after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        return await runtime.read(lambda r: queries.events_view(r.require_world(), after, limit))

    @app.get("/api/v2/query/research", response_model=Envelope[ResearchView])
    async def research():
        return await runtime.read(lambda r: queries.research_view(r.require_world()))

    @app.get("/api/v2/query/causal/{event_id}", response_model=Envelope[CausalView])
    async def causal(event_id: str, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        return await runtime.read(lambda r: queries.causal_view(r.require_world(), event_id, after, limit))

    @app.get("/api/v2/query/saves", response_model=Envelope[list[SaveView]])
    async def saves():
        return await runtime.read(lambda r: list_save_files(r.save_path("probe").parent))

    @app.post("/api/v2/command/create", response_model=Envelope[StatusView])
    async def create(req: CreateRequest):
        return await runtime.create(req)

    @app.post("/api/v2/command/step", response_model=Envelope[StatusView])
    async def step(req: EmptyRequest):
        return await runtime.step()

    @app.post("/api/v2/command/pause", response_model=Envelope[StatusView])
    async def pause(req: EmptyRequest):
        return await runtime.pause()

    @app.post("/api/v2/command/resume", response_model=Envelope[StatusView])
    async def resume(req: EmptyRequest):
        return await runtime.resume()

    @app.post("/api/v2/command/speed", response_model=Envelope[StatusView])
    async def speed(req: SpeedRequest):
        return await runtime.speed(req)

    @app.post("/api/v2/command/save", response_model=Envelope[StatusView])
    async def save(req: SaveRequest):
        return await runtime.save(req)

    @app.post("/api/v2/command/load", response_model=Envelope[StatusView])
    async def load(req: LoadRequest):
        return await runtime.load(req)

    from .frontend import mount_frontend
    mount_frontend(app, frontend_dir)
    return app
