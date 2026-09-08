from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import authenticate, create_access_token, require_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest):
    if not authenticate(credentials.username, credentials.password):
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    token, expires_in = create_access_token(credentials.username)
    return LoginResponse(access_token=token, expires_in=expires_in)


@router.get("/me")
def me(username: str = Depends(require_auth)):
    return {"username": username}
