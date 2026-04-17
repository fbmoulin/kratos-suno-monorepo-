"""SessionStore — armazenamento in-memory de sessões de usuário.

Motivação: o MVP não precisa de Redis/Postgres para sessions. TTL simples
e thread-safe via asyncio.Lock resolve. Para escalar horizontalmente
(Fase 5+), trocar por Redis mantendo a interface.

O que guarda por session_id:
- access_token e refresh_token do Spotify
- spotify_user_id, display_name
- pkce_verifier (durante o flow de login)
- state do OAuth (para validação anti-CSRF no callback)
"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class SessionData:
    """Dados de uma sessão ativa."""

    session_id: str
    created_at: datetime
    expires_at: datetime
    # OAuth state (durante o flow)
    pkce_verifier: str | None = None
    oauth_state: str | None = None
    # Credenciais Spotify (depois do callback)
    spotify_access_token: str | None = None
    spotify_refresh_token: str | None = None
    spotify_token_expires_at: datetime | None = None
    # Dados do usuário (cache simples)
    spotify_user_id: str | None = None
    display_name: str | None = None
    # Extensibilidade futura
    extra: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    def is_spotify_token_expired(self) -> bool:
        if not self.spotify_token_expires_at:
            return True
        # 30s de margem
        return datetime.now(timezone.utc) >= (
            self.spotify_token_expires_at - timedelta(seconds=30)
        )

    @property
    def is_authenticated(self) -> bool:
        return (
            self.spotify_access_token is not None
            and self.spotify_user_id is not None
        )


class SessionStore:
    """Store in-memory de sessões. Thread-safe para uso async.

    Uso típico:
        store = SessionStore()
        session = await store.create()
        session.oauth_state = "abc"
        await store.update(session)
        # ...
        session = await store.get(session_id)
    """

    def __init__(self, ttl_seconds: int = 60 * 60 * 24 * 7):
        self._sessions: dict[str, SessionData] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds

    async def create(self) -> SessionData:
        """Cria uma nova sessão com ID aleatório de 128 bits."""
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        session = SessionData(
            session_id=session_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )
        async with self._lock:
            self._sessions[session_id] = session
        return session

    async def get(self, session_id: str) -> SessionData | None:
        """Retorna sessão se existir e não estiver expirada. Limpa se expirada."""
        if not session_id:
            return None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired():
                self._sessions.pop(session_id, None)
                return None
            return session

    async def update(self, session: SessionData) -> None:
        """Persiste mudanças na sessão (overrwrite)."""
        async with self._lock:
            self._sessions[session.session_id] = session

    async def delete(self, session_id: str) -> None:
        """Remove sessão (logout)."""
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def cleanup_expired(self) -> int:
        """Remove sessões expiradas. Retorna quantas foram removidas.

        Chame periodicamente via task de background em produção.
        """
        async with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items() if s.is_expired()
            ]
            for sid in expired_ids:
                self._sessions.pop(sid, None)
            return len(expired_ids)


# Singleton global — um store por processo
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """DI factory — retorna a instância singleton."""
    global _store
    if _store is None:
        from app.config import settings
        _store = SessionStore(ttl_seconds=settings.session_ttl_seconds)
    return _store
