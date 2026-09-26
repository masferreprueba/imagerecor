from types import SimpleNamespace

import pytest

from app.services.factory import create_mixed_provider_chain


def test_mixed_chain_contains_only_configured_external_providers():
    credentials = [
        SimpleNamespace(
            provider="photoroom",
            api_key="test-key",
            credential_id=7,
        )
    ]

    chain = create_mixed_provider_chain(credentials, timeout=30, max_retries=1)

    assert [provider.name for provider in chain.providers] == ["photoroom"]
    assert chain.credential_ids == [7]


def test_mixed_chain_requires_an_external_api_key():
    with pytest.raises(ValueError, match="No hay llaves API configuradas"):
        create_mixed_provider_chain([], timeout=30, max_retries=1)
