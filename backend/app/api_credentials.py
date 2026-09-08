import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from .config import get_settings
from .database import ApiCredential, ApiUsageEvent, SessionLocal


SUPPORTED_PROVIDERS = {"claid", "photoroom", "removebg"}


@dataclass(frozen=True)
class ProviderKey:
    credential_id: int
    api_key: str


def _cipher() -> Fernet:
    secret = get_settings().api_key_encryption_secret
    if not secret:
        raise RuntimeError("Falta configurar API_KEY_ENCRYPTION_SECRET.")
    derived = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def _fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _mask(api_key: str) -> str:
    if len(api_key) <= 8:
        return "••••" + api_key[-2:]
    return f"{api_key[:4]}••••••••{api_key[-4:]}"


def add_api_credential(provider: str, label: str, api_key: str) -> ApiCredential:
    provider = provider.strip().lower()
    label = label.strip()
    api_key = api_key.strip()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Proveedor no compatible.")
    if not label or len(label) > 100:
        raise ValueError("Escribe un nombre de hasta 100 caracteres.")
    if len(api_key) < 12:
        raise ValueError("La llave API no parece válida.")
    fingerprint = _fingerprint(api_key)
    with SessionLocal.begin() as session:
        existing = session.scalar(select(ApiCredential).where(ApiCredential.fingerprint == fingerprint))
        if existing:
            raise ValueError("Esta llave API ya está registrada.")
        record = ApiCredential(
            provider=provider,
            label=label,
            encrypted_key=_cipher().encrypt(api_key.encode("utf-8")).decode("ascii"),
            fingerprint=fingerprint,
            masked_key=_mask(api_key),
        )
        session.add(record)
        session.flush()
        return record


def sync_environment_api_keys(provider: str, api_keys: list[str]) -> None:
    """Imports deployment keys once so their future use is tracked too."""
    if not api_keys:
        return
    cipher = _cipher()
    with SessionLocal.begin() as session:
        existing = set(session.scalars(select(ApiCredential.fingerprint)).all())
        for index, api_key in enumerate(api_keys, start=1):
            fingerprint = _fingerprint(api_key)
            if fingerprint in existing:
                continue
            session.add(ApiCredential(
                provider=provider.lower(),
                label=f"Llave configurada {index}",
                encrypted_key=cipher.encrypt(api_key.encode("utf-8")).decode("ascii"),
                fingerprint=fingerprint,
                masked_key=_mask(api_key),
            ))


def active_provider_keys(provider: str) -> list[ProviderKey]:
    cipher = _cipher()
    with SessionLocal() as session:
        records = session.scalars(
            select(ApiCredential)
            .where(ApiCredential.provider == provider.lower(), ApiCredential.active.is_(True))
            .order_by(ApiCredential.last_used_at.desc().nullslast(), ApiCredential.id)
        ).all()
        result: list[ProviderKey] = []
        for record in records:
            try:
                key = cipher.decrypt(record.encrypted_key.encode("ascii")).decode("utf-8")
            except InvalidToken as exc:
                raise RuntimeError("No fue posible descifrar una llave API registrada.") from exc
            result.append(ProviderKey(record.id, key))
        return result


def record_api_attempt(credential_id: int, success: bool, error: str | None, job_id: str | None) -> None:
    now = datetime.now(timezone.utc)
    safe_error = (error or "")[:500] or None
    with SessionLocal.begin() as session:
        record = session.get(ApiCredential, credential_id)
        if not record:
            return
        record.last_used_at = now
        record.updated_at = now
        record.last_error = None if success else safe_error
        if success:
            record.success_count += 1
        else:
            record.failure_count += 1
        session.add(ApiUsageEvent(
            credential_id=credential_id,
            job_id=job_id,
            success=success,
            error=safe_error,
            created_at=now,
        ))
