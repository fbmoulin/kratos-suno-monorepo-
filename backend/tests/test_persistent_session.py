"""Tests for PersistentSessionStore against SQLite in-memory."""
from __future__ import annotations

import datetime as dt

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session_factory():
    from app.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


class TestPersistentSessionStore:
    async def test_persist_and_reload(self, session_factory):
        from app.services.persistent_session import PersistentSessionStore

        store = PersistentSessionStore(session_factory=session_factory)

        await store.save(
            session_id="sess-1",
            access_token="at",
            refresh_token="rt",
            expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
            spotify_user_id="spot-1",
            display_name="Felipe",
        )

        retrieved = await store.get("sess-1")
        assert retrieved is not None
        assert retrieved["access_token"] == "at"
        assert retrieved["refresh_token"] == "rt"
        assert retrieved["spotify_user_id"] == "spot-1"
        assert retrieved["display_name"] == "Felipe"

    async def test_get_missing_returns_none(self, session_factory):
        from app.services.persistent_session import PersistentSessionStore

        store = PersistentSessionStore(session_factory=session_factory)
        assert await store.get("nonexistent") is None

    async def test_update_overwrites(self, session_factory):
        from app.services.persistent_session import PersistentSessionStore

        store = PersistentSessionStore(session_factory=session_factory)
        now = dt.datetime.now(dt.timezone.utc)
        await store.save("sess-1", "at1", "rt", now, "s-1", "F")
        await store.save("sess-1", "at2", "rt", now, "s-1", "F")
        ret = await store.get("sess-1")
        assert ret is not None
        assert ret["access_token"] == "at2"

    async def test_delete(self, session_factory):
        from app.services.persistent_session import PersistentSessionStore

        store = PersistentSessionStore(session_factory=session_factory)
        now = dt.datetime.now(dt.timezone.utc)
        await store.save("sess-1", "at", "rt", now, "s", "F")
        await store.delete("sess-1")
        assert await store.get("sess-1") is None
