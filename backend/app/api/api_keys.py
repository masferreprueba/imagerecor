from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..api_credentials import add_api_credential
from ..auth import require_auth
from ..database import ApiCredential, ApiUsageEvent, SessionLocal


router = APIRouter(prefix="/api/api-keys", tags=["api-keys"], dependencies=[Depends(require_auth)])


class ApiKeyCreate(BaseModel):
    provider: str = "photoroom"
    label: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=12, max_length=500)


class ApiKeyState(BaseModel):
    active: bool


def serialize(record: ApiCredential) -> dict:
    return {
        "id": record.id,
        "provider": record.provider,
        "label": record.label,
        "masked_key": record.masked_key,
        "active": record.active,
        "success_count": record.success_count,
        "failure_count": record.failure_count,
        "last_used_at": record.last_used_at,
        "last_error": record.last_error,
        "created_at": record.created_at,
    }


@router.get("")
def list_api_keys():
    with SessionLocal() as session:
        records = session.scalars(select(ApiCredential).order_by(ApiCredential.created_at.desc())).all()
        return {"keys": [serialize(record) for record in records]}


@router.post("", status_code=201)
def create_api_key(payload: ApiKeyCreate):
    try:
        record = add_api_credential(payload.provider, payload.label, payload.api_key)
        return serialize(record)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{credential_id}")
def update_api_key(credential_id: int, payload: ApiKeyState):
    with SessionLocal.begin() as session:
        record = session.get(ApiCredential, credential_id)
        if not record:
            raise HTTPException(404, "Llave API no encontrada.")
        record.active = payload.active
        record.updated_at = datetime.now(timezone.utc)
        session.flush()
        return serialize(record)


@router.get("/{credential_id}/usage")
def api_key_usage(credential_id: int, limit: int = 50):
    limit = min(max(limit, 1), 100)
    with SessionLocal() as session:
        if not session.get(ApiCredential, credential_id):
            raise HTTPException(404, "Llave API no encontrada.")
        events = session.scalars(
            select(ApiUsageEvent)
            .where(ApiUsageEvent.credential_id == credential_id)
            .order_by(ApiUsageEvent.created_at.desc())
            .limit(limit)
        ).all()
        return {"events": [{
            "success": event.success,
            "error": event.error,
            "job_id": event.job_id,
            "created_at": event.created_at,
        } for event in events]}
