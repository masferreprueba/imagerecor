from .base import BackgroundRemovalProvider
from .claid_service import ClaidProvider
from .photoroom_service import PhotoroomProvider
from .removebg_service import RemoveBgProvider
from .poof_service import PoofProvider
from .fallback import FallbackProvider
from .local_rembg_service import LocalRembgProvider

PROVIDERS = {"claid": ClaidProvider, "photoroom": PhotoroomProvider, "removebg": RemoveBgProvider, "poof": PoofProvider}


def create_provider(name: str, api_key: str, timeout: int, max_retries: int) -> BackgroundRemovalProvider:
    provider = PROVIDERS.get(name.lower())
    if not provider:
        raise ValueError(f"Proveedor no compatible: {name}.")
    return provider(api_key=api_key, timeout=timeout, max_retries=max_retries)


def create_provider_chain(name: str, api_keys: list[str], timeout: int, max_retries: int, credential_ids: list[int] | None = None, on_attempt=None) -> BackgroundRemovalProvider:
    providers = [create_provider(name, key, timeout, max_retries) for key in api_keys]
    return FallbackProvider(providers, credential_ids=credential_ids, on_attempt=on_attempt)


def create_mixed_provider_chain(
    credentials,
    timeout: int,
    max_retries: int,
    on_attempt=None,
    local_enabled: bool = True,
    local_model: str = "u2netp",
    local_max_side: int = 1024,
) -> BackgroundRemovalProvider:
    providers = [create_provider(item.provider, item.api_key, timeout, max_retries) for item in credentials]
    credential_ids: list[int | None] = [item.credential_id for item in credentials]
    if local_enabled:
        providers.append(LocalRembgProvider(model=local_model, max_side=local_max_side))
        credential_ids.append(None)
    return FallbackProvider(
        providers,
        credential_ids=credential_ids,
        on_attempt=on_attempt,
    )
