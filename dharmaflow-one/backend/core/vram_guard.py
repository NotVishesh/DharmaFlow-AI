import gc
import asyncio
from contextlib import asynccontextmanager

class VRAMGuard:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active_model_name: str | None = None
        self._active_model_instance = None
        self.unload_history: list[str] = []  # Used by unit tests to verify unload calls

    @asynccontextmanager
    async def acquire_model(self, model_name: str, loader_fn, unloader_fn=None):
        async with self._lock:
            if self._active_model_instance is not None:
                self._force_unload(unloader_fn)
            self._active_model_name = model_name
            try:
                if asyncio.iscoroutinefunction(loader_fn):
                    self._active_model_instance = await loader_fn()
                else:
                    self._active_model_instance = await asyncio.to_thread(loader_fn)
                yield self._active_model_instance
            finally:
                self._force_unload(unloader_fn)

    def _force_unload(self, unloader_fn=None):
        if self._active_model_name:
            self.unload_history.append(self._active_model_name)
        if unloader_fn and self._active_model_instance is not None:
            try:
                unloader_fn(self._active_model_instance)
            except Exception:
                pass
        self._active_model_instance = None
        self._active_model_name = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

vram_guard = VRAMGuard()
