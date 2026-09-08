from pathlib import Path

import httpx

from .base import BackgroundRemovalProvider
from .http import request_with_retry


class PoofProvider(BackgroundRemovalProvider):
    name = "poof"
    endpoint = "https://api.poof.bg/v1/remove"

    def remove_background(self, source: Path, destination: Path) -> None:
        try:
            with httpx.Client(timeout=self.timeout) as client, source.open("rb") as image:
                response = request_with_retry(
                    client,
                    "POST",
                    self.endpoint,
                    self.max_retries,
                    headers={"x-api-key": self.api_key},
                    files={"image_file": (source.name, image, "application/octet-stream")},
                )
                destination.write_bytes(response.content)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 402, 403}:
                message = "Poof rechazó la llave API o no tiene créditos disponibles."
            elif status == 429:
                message = "Poof alcanzó el límite temporal de solicitudes."
            elif status in {400, 413, 415, 422}:
                message = "Poof rechazó el formato, tamaño o resolución de la imagen."
            else:
                message = f"Poof no está disponible temporalmente (HTTP {status})."
            raise RuntimeError(message) from exc
