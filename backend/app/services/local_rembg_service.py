from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image, ImageOps

from .base import BackgroundRemovalProvider


class LocalRembgProvider(BackgroundRemovalProvider):
    """Free, local background-removal fallback powered by rembg/ONNX."""

    name = "local-rembg"

    def __init__(self, model: str = "silueta", max_side: int = 1600):
        # This provider has no API key: inference runs inside our own process.
        self.model = model
        self.max_side = max(512, max_side)
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

    def _prepare_input(self, source: Path) -> bytes:
        """Bound inference resolution so large photos fit Render Free memory."""
        with Image.open(source) as original:
            # JPEG draft decoding avoids allocating the full 4000x4000 raster when possible.
            if (original.format or "").upper() in {"JPEG", "JPG"}:
                original.draft("RGB", (self.max_side, self.max_side))
            image = ImageOps.exif_transpose(original)
            image.thumbnail(
                (self.max_side, self.max_side),
                Image.Resampling.LANCZOS,
                reducing_gap=3.0,
            )
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=False)
            return buffer.getvalue()

    def remove_background(self, source: Path, destination: Path) -> None:
        try:
            # Serialize inference to keep memory usage within Render Free limits.
            with self._lock:
                prepared_input = self._prepare_input(source)
                remove, session = self._runtime()
                result = remove(prepared_input, session=session, decontaminate=True)
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
