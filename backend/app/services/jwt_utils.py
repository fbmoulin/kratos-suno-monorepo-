"""HS256 JWT helpers for mobile session tokens.

W1-B: mobile clients receive a bearer JWT after the Spotify OAuth flow
completes via the mobile-callback endpoint. The JWT carries the session_id
in its ``sid`` claim so the backend can resolve the in-memory / persistent
session on subsequent authenticated requests.

Web clients continue to use the HttpOnly cookie path — nothing here replaces
that flow.
"""
from __future__ import annotations

import time
from typing import Any

import jwt


def sign_session_token(session_id: str, secret: str, ttl: int) -> str:
    """Sign an HS256 JWT carrying ``sid`` (session_id) with expiration ``ttl`` seconds from now.

    Raises:
        ValueError: if ``secret`` is empty (prevents accidental dev-mode insecure signing
            being used as if secure).
    """
    if not secret:
        raise ValueError("jwt secret is empty — configure JWT_SECRET_KEY")
    now = int(time.time())
    payload: dict[str, Any] = {
        "sid": session_id,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_session_token(token: str, secret: str) -> dict[str, Any]:
    """Verify HS256 JWT and return decoded payload. Raises on tamper/expiration."""
    return jwt.decode(token, secret, algorithms=["HS256"])
