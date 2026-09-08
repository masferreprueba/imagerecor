import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException

from .config import get_settings


def _unauthorized(message: str = "Usuario o contraseña incorrectos.") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.auth_username or not settings.auth_password or not settings.auth_secret:
        return False
    return hmac.compare_digest(username, settings.auth_username) and hmac.compare_digest(
        password, settings.auth_password
    )


def create_access_token(username: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = max(settings.auth_token_hours, 1) * 3600
    payload = json.dumps(
        {"sub": username, "exp": int(time.time()) + expires_in},
        separators=(",", ":"),
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(settings.auth_secret.encode(), encoded, hashlib.sha256).digest()
    token = b".".join((encoded, base64.urlsafe_b64encode(signature).rstrip(b"=")))
    return token.decode(), expires_in


def verify_access_token(token: str) -> str:
    settings = get_settings()
    if not settings.auth_secret:
        raise _unauthorized("Acceso no configurado.")
    try:
        encoded, supplied_signature = token.encode().split(b".", 1)
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(settings.auth_secret.encode(), encoded, hashlib.sha256).digest()
        ).rstrip(b"=")
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        username = str(payload["sub"])
        if not hmac.compare_digest(username, settings.auth_username):
            raise ValueError("invalid user")
        return username
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise _unauthorized("La sesión venció. Inicia sesión nuevamente.")


def require_auth(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("Debes iniciar sesión.")
    return verify_access_token(authorization.removeprefix("Bearer ").strip())
