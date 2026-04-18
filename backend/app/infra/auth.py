"""AuthProvider Protocol + stage-1 implementations."""
from __future__ import annotations
import hashlib
from typing import Literal, Protocol

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import settings


class AuthContext(BaseModel):
    subject_id: str
    plan: Literal["anon", "free", "pro", "b2b"] = "anon"
    scope: set[str] = Field(default_factory=set)


class AuthProvider(Protocol):
    async def authenticate(self, request: Request) -> AuthContext: ...


class NoAuthProvider:
    """Stage-1 fallback: accepts everyone, derives subject_id from IP."""

    async def authenticate(self, request: Request) -> AuthContext:
        ip = request.client.host if request.client else "unknown"
        return AuthContext(subject_id=_ip_subject(ip))


class SharedSecretAuthProvider:
    """Stage-1: validates X-Kratos-Key header against expected_key.
    Empty expected_key disables validation (dev mode)."""

    def __init__(self, expected_key: str):
        self.expected_key = expected_key

    async def authenticate(self, request: Request) -> AuthContext:
        if self.expected_key:
            provided = request.headers.get("X-Kratos-Key", "")
            if provided != self.expected_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "auth_missing",
                        "code": "E_AUTH_MISSING",
                        "detail": "Invalid or missing X-Kratos-Key",
                    },
                )
        ip = request.client.host if request.client else "unknown"
        return AuthContext(subject_id=_ip_subject(ip))


def _ip_subject(ip: str) -> str:
    return f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"


def _build_auth_provider() -> AuthProvider:
    match settings.auth_provider:
        case "none":
            return NoAuthProvider()
        case "shared_secret":
            return SharedSecretAuthProvider(settings.shared_secret_key)
        case "clerk":
            raise NotImplementedError("Stage 3 — ClerkAuthProvider")
        case "api_key":
            raise NotImplementedError("Stage 4 — ApiKeyAuthProvider")


async def require_auth(request: Request) -> AuthContext:
    """FastAPI dependency."""
    from app.infra.factories import get_auth_provider
    return await get_auth_provider().authenticate(request)
