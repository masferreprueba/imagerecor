import json
from pathlib import Path
import httpx
from .base import BackgroundRemovalProvider
from .http import request_with_retry


class ClaidProvider(BackgroundRemovalProvider):
    name = "claid"
    endpoint = "https://api.claid.ai/v1/image/edit/upload"

    def remove_background(self, source: Path, destination: Path) -> None:
        payload = {
            "operations": {
                "background": {"remove": {"category": "products", "clipping": False}, "color": "transparent"}
            },
            "output": {"format": {"type": "png", "compression": "optimal"}},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client, source.open("rb") as image:
            response = request_with_retry(
                client, "POST", self.endpoint, self.max_retries, headers=headers,
                files={"file": (source.name, image, "application/octet-stream"), "data": (None, json.dumps(payload), "application/json")},
            )
            result_url = response.json()["data"]["output"]["tmp_url"]
            processed = request_with_retry(client, "GET", result_url, self.max_retries)
            destination.write_bytes(processed.content)
