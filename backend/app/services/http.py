import time
import httpx


def request_with_retry(client: httpx.Client, method: str, url: str, retries: int, **kwargs) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {429, 500, 502, 503, 504}
            if not retryable or attempt == retries - 1:
                raise
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError("Falló la solicitud al proveedor.") from last_error
