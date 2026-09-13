"""One owner and mutation lock for the public medieval session."""

import asyncio
import logging
from pathlib import Path
import uuid

from src.config.data_paths import get_data_paths
from src.run.medieval_world import create_medieval_world
from src.sim.medieval.engine import MedievalSimulator
from src.sim.medieval import persistence
from .contracts import ErrorView, StatusView
from .errors import RuntimeProblem
from .save_files import resolve_save


class MedievalRuntime:
    def __init__(self, *, save_dir=None):
        self._save_dir = save_dir or (lambda: get_data_paths().saves_dir / "medieval")
        self.world = None
        self.simulator = None
        self.paused = True
        self.jumps_per_second = 1
        self.last_error = None
        self.run_id = None
        self.revision = 0
        self._auto_id = None
        self._lock = asyncio.Lock()
        self._changed = asyncio.Event()
        self._runner = None
        self._closing = False

    def save_path(self, save_id):
        return resolve_save(Path(self._save_dir()), save_id)

    def require_world(self):
        if self.world is None:
            raise RuntimeProblem("WORLD_NOT_READY", "Crie ou carregue um mundo primeiro.")
        return self.world

    def status(self):
        return StatusView(ready=self.world is not None, paused=self.paused,
                          jumps_per_second=self.jumps_per_second, run_id=self.run_id,
                          day=self.world.clock.absolute_day if self.world is not None else None, last_error=self.last_error)

    def _response(self, value):
        data = [item.model_dump(mode="json") for item in value] if isinstance(value, list) else value.model_dump(mode="json")
        return {"ok": True, "data": data, "revision": self.revision}

    async def read(self, builder):
        async with self._lock:
            return self._response(builder(self))

    def _require_paused(self):
        if not self.paused:
            raise RuntimeProblem("PAUSE_REQUIRED", "Pause a simulação antes desta operação.")

    def _fail(self, code, message, exc):
        logging.getLogger(__name__).error("%s (%s)", code, type(exc).__name__)
        self.paused = True
        self.last_error = ErrorView(code=code, message=message)
        self.revision += 1
        self._changed.set()
        return RuntimeProblem(code, message, 500)

    def _activate(self, candidate):
        session_id = uuid.uuid4().hex
        auto_id = f"auto-{session_id}"
        path = self.save_path(auto_id)
        if path.exists():
            raise OSError("autosave identity collision")
        persistence.save_world(candidate, path)
        self.world = candidate
        self.simulator = MedievalSimulator(candidate, save_path=path)
        self.run_id, self._auto_id = session_id, auto_id
        self.paused, self.last_error = True, None
        self.revision += 1
        self._changed.set()

    async def create(self, request):
        async with self._lock:
            self._require_paused()
            if self.world is not None and not request.replace:
                raise RuntimeProblem("WORLD_EXISTS", "Já existe um mundo. Confirme a substituição para criar outro.")
            try:
                candidate = create_medieval_world(request.seed, character_count=request.character_count)
                self._activate(candidate)
            except Exception as exc:
                raise self._fail("CREATE_FAILED", "Não foi possível criar e salvar o mundo.", exc) from exc
            return self._response(self.status())

    async def _step_unlocked(self):
        self.require_world()
        try:
            # Resolve the current configured directory at call time, not from a stale absolute path.
            self.simulator.save_path = self.save_path(self._auto_id)
            await self.simulator.step()
        except Exception as exc:
            raise self._fail("STEP_FAILED", "O avanço falhou. O mundo anterior foi preservado e a simulação foi pausada.", exc) from exc
        self.last_error = None
        self.revision += 1

    async def step(self):
        async with self._lock:
            self._require_paused()
            await self._step_unlocked()
            return self._response(self.status())

    async def pause(self):
        async with self._lock:
            self.paused = True
            self.revision += 1
            self._changed.set()
            return self._response(self.status())

    async def resume(self):
        async with self._lock:
            self.require_world()
            self.paused, self.last_error = False, None
            self.revision += 1
            self._changed.set()
            return self._response(self.status())

    async def speed(self, request):
        async with self._lock:
            self.jumps_per_second = request.jumps_per_second
            self.revision += 1
            self._changed.set()
            return self._response(self.status())

    async def save(self, request):
        async with self._lock:
            self.require_world()
            path = self.save_path(request.save_id)
            if path.exists() and not request.overwrite:
                raise RuntimeProblem("SAVE_EXISTS", "Este save já existe. Confirme a sobrescrita.")
            # The autosave slot remains separately owned by the session.
            if request.save_id == self._auto_id:
                raise RuntimeProblem("AUTOSAVE_RESERVED", "Escolha outro nome para o save manual.")
            try:
                persistence.save_world(self.world, path)
            except Exception as exc:
                raise self._fail("SAVE_FAILED", "Não foi possível salvar o mundo.", exc) from exc
            self.revision += 1
            return self._response(self.status())

    async def load(self, request):
        async with self._lock:
            self._require_paused()
            path = self.save_path(request.save_id)
            if not path.is_file():
                raise RuntimeProblem("SAVE_NOT_FOUND", "Save não encontrado.", 404)
            try:
                candidate = persistence.load_world(path)
            except Exception as exc:
                raise RuntimeProblem("SAVE_INVALID", "O arquivo não é um save medieval válido desta versão.", 422) from exc
            try:
                self._activate(candidate)
            except Exception as exc:
                raise self._fail("LOAD_FAILED", "Não foi possível preparar o mundo carregado.", exc) from exc
            return self._response(self.status())

    async def tick(self):
        async with self._lock:
            if not self.paused and not self._closing and self.world is not None:
                await self._step_unlocked()

    async def start(self):
        if self._runner is None or self._runner.done():
            self._closing = False
            self._runner = asyncio.create_task(self._loop(), name="medieval-world-loop")

    async def close(self):
        async with self._lock:
            self._closing, self.paused = True, True
            self._changed.set()
        if self._runner is not None:
            await self._runner

    async def _loop(self):
        while not self._closing:
            if self.paused or self.world is None:
                await self._changed.wait()
                self._changed.clear()
                continue
            try:
                await self.tick()
            except RuntimeProblem:
                continue  # tick already paused with a typed failure; no automatic retry.
            try:
                await asyncio.wait_for(self._changed.wait(), timeout=1 / self.jumps_per_second)
            except asyncio.TimeoutError:
                pass
            self._changed.clear()
