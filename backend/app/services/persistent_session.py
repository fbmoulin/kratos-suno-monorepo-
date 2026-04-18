"""Postgres-backed session persistence to survive backend restarts.

W1-B: The in-memory :class:`SessionStore` is the hot path for request
serving. This module adds a durable cold store (``user_session`` table)
that is consulted on cache miss so that restarting the FastAPI process
does not invalidate existing authenticated sessions.

Write-through: every Spotify token update in ``SessionStore`` also writes
to this store; on cache miss, read-through rehydrates the in-memory entry.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import UserSession


class PersistentSessionStore:
    """Durable async store backed by the ``user_session`` SQLAlchemy model."""

    def __init__(self, session_factory: async_sessionmaker):
        self._factory = session_factory

    async def save(
        self,
        session_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: dt.datetime,
        spotify_user_id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Upsert session by ``session_id``.

        Creates a new ``UserSession`` row if missing; otherwise overwrites
        token and profile fields on the existing row.
        """
        async with self._factory() as s:
            existing = (
                await s.execute(
                    select(UserSession).where(UserSession.session_id == session_id)
                )
            ).scalar_one_or_none()
            if existing:
                existing.access_token = access_token
                existing.refresh_token = refresh_token
                existing.expires_at = expires_at
                existing.spotify_user_id = spotify_user_id
                existing.display_name = display_name
                existing.updated_at = dt.datetime.now(dt.timezone.utc)
            else:
                s.add(
                    UserSession(
                        session_id=session_id,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        spotify_user_id=spotify_user_id,
                        display_name=display_name,
                    )
                )
            await s.commit()

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Return a dict snapshot of the persisted session, or ``None`` if absent."""
        async with self._factory() as s:
            row = (
                await s.execute(
                    select(UserSession).where(UserSession.session_id == session_id)
                )
            ).scalar_one_or_none()
            if not row:
                return None
            return {
                "session_id": row.session_id,
                "access_token": row.access_token,
                "refresh_token": row.refresh_token,
                "expires_at": row.expires_at,
                "spotify_user_id": row.spotify_user_id,
                "display_name": row.display_name,
            }

    async def delete(self, session_id: str) -> None:
        """Remove the persisted session row (logout / cleanup)."""
        async with self._factory() as s:
            row = (
                await s.execute(
                    select(UserSession).where(UserSession.session_id == session_id)
                )
            ).scalar_one_or_none()
            if row:
                await s.delete(row)
                await s.commit()
