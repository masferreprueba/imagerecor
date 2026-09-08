from pathlib import Path
import httpx
from .base import BackgroundRemovalProvider
from .http import request_with_retry


class RemoveBgProvider(BackgroundRemovalProvider):
    name = "removebg"
    endpoint = "https://api.remove.bg/v1.0/removebg"

    def remove_background(self, source: Path, destination: Path) -> None:
        with httpx.Client(timeout=self.timeout) as client, source.open("rb") as image:
            response = request_with_retry(
                client, "POST", self.endpoint, self.max_retries,
                headers={"X-Api-Key": self.api_key},
                files={"image_file": (source.name, image, "application/octet-stream")},
                data={"size": "auto", "format": "png"},
            )
            destination.write_bytes(response.content)
