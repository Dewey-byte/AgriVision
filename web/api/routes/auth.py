"""Single-admin authentication with HMAC-signed bearer tokens."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from web.api import config

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


def _sign(payload: str) -> str:
    return hmac.new(
        config.get_secret_key().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_token(username: str) -> str:
    expires = int(time.time()) + config.TOKEN_TTL_SECONDS
    payload = f"{username}:{expires}"
    return f"{payload}:{_sign(payload)}"


def verify_token(token: str) -> str | None:
    parts = token.rsplit(":", 1)
    if len(parts) != 2:
        return None
    payload, sig = parts
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    try:
        username, expires = payload.rsplit(":", 1)
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return username


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    username = verify_token(credentials.credentials)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


@router.post("/login")
def login(body: LoginRequest) -> dict:
    if not (
        hmac.compare_digest(body.username, config.ADMIN_USERNAME)
        and hmac.compare_digest(body.password, config.ADMIN_PASSWORD)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "token": create_token(body.username),
        "username": body.username,
        "expires_in": config.TOKEN_TTL_SECONDS,
    }


@router.get("/me")
def me(username: str = Depends(require_admin)) -> dict:
    return {"username": username, "role": "admin"}
