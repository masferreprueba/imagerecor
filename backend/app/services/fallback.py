from pathlib import Path
from threading import Lock

from .base import BackgroundRemovalProvider


class FallbackProvider(BackgroundRemovalProvider):
    """Tries configured API keys in order and remembers the last working one."""

    name = "fallback"

    def __init__(self, providers: list[BackgroundRemovalProvider]):
        if not providers:
            raise ValueError("No hay llaves API configuradas para procesar imágenes.")
        self.providers = providers
        self._active_index = 0
        self._lock = Lock()

    def remove_background(self, source: Path, destination: Path) -> None:
        with self._lock:
            start = self._active_index

        last_error: Exception | None = None
        for offset in range(len(self.providers)):
            index = (start + offset) % len(self.providers)
            try:
                self.providers[index].remove_background(source, destination)
                with self._lock:
                    self._active_index = index
                return
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("Ningún proveedor de imágenes está disponible.")
