"""SessionStore — armazenamento in-memory de sessões de usuário.

Motivação: o MVP não precisa de Redis/Postgres para sessions. TTL simples
e thread-safe via asyncio.Lock resolve. Para escalar horizontalmente
(Fase 5+), trocar por Redis mantendo a interface.

O que guarda por session_id:
- access_token e refresh_token do Spotify
- spotify_user_id, display_name
- pkce_verifier (durante o flow de login)
- state do OAuth (para validação anti-CSRF no callback)

W1-B: when a :class:`PersistentSessionStore` is attached via
:meth:`attach_persistent`, the in-memory cache is hydrated from the DB on
miss (read-through) and Spotify token writes are propagated to the DB
(write-through). This lets sessions survive a backend restart.
"""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.persistent_session import PersistentSessionStore


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

    def __init__(
        self,
        ttl_seconds: int = 60 * 60 * 24 * 7,
        persistent: "PersistentSessionStore | None" = None,
    ):
        self._sessions: dict[str, SessionData] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._persistent: "PersistentSessionStore | None" = persistent

    def attach_persistent(self, persistent: "PersistentSessionStore | None") -> None:
        """Wire a durable backend (W1-B). Called from the FastAPI lifespan."""
        self._persistent = persistent

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
        """Retorna sessão se existir e não estiver expirada.

        Ordem de consulta:
          1. cache in-memory — hot path
          2. se ausente e persistente configurado, rehidrata do DB
        """
        if not session_id:
            return None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                if session.is_expired():
                    self._sessions.pop(session_id, None)
                else:
                    return session

        # Cache miss → tenta rehidratar do persistente
        if self._persistent is not None:
            record = await self._persistent.get(session_id)
            if record is not None:
                now = datetime.now(timezone.utc)
                hydrated = SessionData(
                    session_id=record["session_id"],
                    created_at=now,
                    expires_at=now + timedelta(seconds=self._ttl_seconds),
                    spotify_access_token=record["access_token"],
                    spotify_refresh_token=record["refresh_token"],
                    spotify_token_expires_at=record["expires_at"],
                    spotify_user_id=record["spotify_user_id"],
                    display_name=record["display_name"],
                )
                async with self._lock:
                    self._sessions[session_id] = hydrated
                return hydrated

        return None

    async def update(self, session: SessionData) -> None:
        """Persiste mudanças na sessão (overrwrite).

        Se houver store persistente e a sessão tiver tokens Spotify,
        propaga via write-through.
        """
        async with self._lock:
            self._sessions[session.session_id] = session

        if (
            self._persistent is not None
            and session.spotify_access_token
            and session.spotify_refresh_token
            and session.spotify_token_expires_at
        ):
            await self._persistent.save(
                session_id=session.session_id,
                access_token=session.spotify_access_token,
                refresh_token=session.spotify_refresh_token,
                expires_at=session.spotify_token_expires_at,
                spotify_user_id=session.spotify_user_id,
                display_name=session.display_name,
            )

    async def delete(self, session_id: str) -> None:
        """Remove sessão (logout). Propaga delete ao persistente se configurado."""
        async with self._lock:
            self._sessions.pop(session_id, None)
        if self._persistent is not None:
            await self._persistent.delete(session_id)

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
