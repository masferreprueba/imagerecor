from pathlib import Path
import httpx
from .base import BackgroundRemovalProvider
from .http import request_with_retry


class PhotoroomProvider(BackgroundRemovalProvider):
    name = "photoroom"
    endpoint = "https://sdk.photoroom.com/v1/segment"

    def remove_background(self, source: Path, destination: Path) -> None:
        with httpx.Client(timeout=self.timeout) as client, source.open("rb") as image:
            response = request_with_retry(
                client, "POST", self.endpoint, self.max_retries,
                headers={"x-api-key": self.api_key},
                files={"image_file": (source.name, image, "application/octet-stream")},
                data={"format": "png", "channels": "rgba"},
            )
            destination.write_bytes(response.content)
