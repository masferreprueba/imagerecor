from abc import ABC, abstractmethod
from pathlib import Path


class BackgroundRemovalProvider(ABC):
    name: str

    def __init__(self, api_key: str, timeout: int = 90, max_retries: int = 3):
        if not api_key:
            raise ValueError(f"Falta la llave API para el proveedor {self.name}.")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    @abstractmethod
    def remove_background(self, source: Path, destination: Path) -> None:
        raise NotImplementedError
