from pathlib import Path
from threading import Lock

from .base import BackgroundRemovalProvider


class FallbackProvider(BackgroundRemovalProvider):
    """Tries configured API keys in order and remembers the last working one."""

    name = "fallback"

    def __init__(self, providers: list[BackgroundRemovalProvider], credential_ids: list[int | None] | None = None, on_attempt=None):
        if not providers:
            raise ValueError("No hay llaves API configuradas para procesar imágenes.")
        self.providers = providers
        self.credential_ids = credential_ids or list(range(len(providers)))
        self.on_attempt = on_attempt
        self._active_index = 0
        self._lock = Lock()

    def _record(self, credential_id: int | None, success: bool, error: str | None) -> None:
        if credential_id is None or not self.on_attempt:
            return
        try:
            self.on_attempt(credential_id, success, error)
        except Exception:
            # Usage statistics must never interrupt image processing.
            pass

    def remove_background(self, source: Path, destination: Path) -> None:
        with self._lock:
            start = self._active_index

        last_error: Exception | None = None
        for offset in range(len(self.providers)):
            index = (start + offset) % len(self.providers)
            try:
                self.providers[index].remove_background(source, destination)
                self._record(self.credential_ids[index], True, None)
                with self._lock:
                    self._active_index = index
                return
            except Exception as exc:
                self._record(self.credential_ids[index], False, str(exc))
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("Ningún proveedor de imágenes está disponible.")
