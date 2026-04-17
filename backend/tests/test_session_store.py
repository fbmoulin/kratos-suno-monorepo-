"""Testes do SessionStore — criação, expiração, TTL, thread-safety."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.services.session_store import SessionStore


@pytest.mark.asyncio
async def test_create_session_returns_unique_id():
    store = SessionStore(ttl_seconds=3600)
    s1 = await store.create()
    s2 = await store.create()
    assert s1.session_id != s2.session_id
    assert len(s1.session_id) >= 32  # token_urlsafe(32) gera ~43 chars


@pytest.mark.asyncio
async def test_get_retrieves_existing_session():
    store = SessionStore(ttl_seconds=3600)
    created = await store.create()
    retrieved = await store.get(created.session_id)
    assert retrieved is not None
    assert retrieved.session_id == created.session_id


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none():
    store = SessionStore(ttl_seconds=3600)
    assert await store.get("does-not-exist") is None
    assert await store.get("") is None


@pytest.mark.asyncio
async def test_expired_session_removed_on_get():
    store = SessionStore(ttl_seconds=3600)
    session = await store.create()
    # Força expiração manualmente
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await store.update(session)

    # get deve retornar None E limpar o registro
    assert await store.get(session.session_id) is None


@pytest.mark.asyncio
async def test_update_persists_changes():
    store = SessionStore(ttl_seconds=3600)
    session = await store.create()
    session.oauth_state = "abc123"
    session.pkce_verifier = "verifier-xyz"
    await store.update(session)

    retrieved = await store.get(session.session_id)
    assert retrieved is not None
    assert retrieved.oauth_state == "abc123"
    assert retrieved.pkce_verifier == "verifier-xyz"


@pytest.mark.asyncio
async def test_delete_removes_session():
    store = SessionStore(ttl_seconds=3600)
    session = await store.create()
    await store.delete(session.session_id)
    assert await store.get(session.session_id) is None


@pytest.mark.asyncio
async def test_cleanup_expired_removes_only_expired():
    store = SessionStore(ttl_seconds=3600)
    fresh = await store.create()
    expired = await store.create()
    expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await store.update(expired)

    removed = await store.cleanup_expired()
    assert removed == 1
    assert await store.get(fresh.session_id) is not None
    assert await store.get(expired.session_id) is None


@pytest.mark.asyncio
async def test_is_authenticated_requires_token_and_user_id():
    store = SessionStore(ttl_seconds=3600)
    session = await store.create()
    assert not session.is_authenticated

    session.spotify_access_token = "tok"
    assert not session.is_authenticated  # sem user_id ainda

    session.spotify_user_id = "spotify_user_1"
    assert session.is_authenticated


@pytest.mark.asyncio
async def test_concurrent_creates_are_thread_safe():
    """Múltiplas criações concorrentes não corrompem o store."""
    store = SessionStore(ttl_seconds=3600)
    # 50 sessões em paralelo
    sessions = await asyncio.gather(*(store.create() for _ in range(50)))
    ids = {s.session_id for s in sessions}
    assert len(ids) == 50  # todos únicos
