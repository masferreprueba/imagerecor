from pathlib import Path
from threading import Lock

from PIL import Image

from .base import BackgroundRemovalProvider


class LocalRembgProvider(BackgroundRemovalProvider):
    """Free, local background-removal fallback powered by rembg/ONNX."""

    name = "local-rembg"

    def __init__(self, model: str = "silueta"):
        # This provider has no API key: inference runs inside our own process.
        self.model = model
        self._session = None
        self._lock = Lock()

    def _runtime(self):
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise RuntimeError("El eliminador local gratuito no está instalado.") from exc
        if self._session is None:
            self._session = new_session(self.model)
        return remove, self._session

    def remove_background(self, source: Path, destination: Path) -> None:
        try:
            # Serialize inference to keep memory usage within Render Free limits.
            with self._lock:
                remove, session = self._runtime()
                result = remove(source.read_bytes(), session=session, decontaminate=True)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(result)
            with Image.open(destination) as image:
                if image.mode not in {"RGBA", "LA"} or not image.getchannel("A").getbbox():
                    raise ValueError("El modelo local no detectó un objeto visible.")
        except Exception as exc:
            destination.unlink(missing_ok=True)
            if isinstance(exc, RuntimeError) and str(exc).startswith("El eliminador local"):
                raise
            raise RuntimeError(f"La eliminación local no pudo procesar {source.name}: {exc}") from exc
