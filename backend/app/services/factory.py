from .base import BackgroundRemovalProvider
from .claid_service import ClaidProvider
from .photoroom_service import PhotoroomProvider
from .removebg_service import RemoveBgProvider
from .fallback import FallbackProvider

PROVIDERS = {"claid": ClaidProvider, "photoroom": PhotoroomProvider, "removebg": RemoveBgProvider}


def create_provider(name: str, api_key: str, timeout: int, max_retries: int) -> BackgroundRemovalProvider:
    provider = PROVIDERS.get(name.lower())
    if not provider:
        raise ValueError(f"Proveedor no compatible: {name}.")
    return provider(api_key=api_key, timeout=timeout, max_retries=max_retries)


def create_provider_chain(name: str, api_keys: list[str], timeout: int, max_retries: int) -> BackgroundRemovalProvider:
    providers = [create_provider(name, key, timeout, max_retries) for key in api_keys]
    return FallbackProvider(providers)
