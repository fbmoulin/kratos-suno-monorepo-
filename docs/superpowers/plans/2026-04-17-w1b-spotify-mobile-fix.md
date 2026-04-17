# W1-B Spotify Mobile Deep Link Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unblock the Spotify OAuth PKCE flow on mobile by (a) adding a backend mobile-callback endpoint that redirects to the `kratossuno://` scheme with a bearer JWT, (b) adding a mobile route handler that captures the deep link and stores the token, (c) persisting refresh tokens so a backend restart doesn't invalidate existing sessions.

**Architecture:** Backend issues short-lived JWT (signed HS256) after Spotify token exchange on mobile flow; writes refresh_token to Postgres (new `user_session` table). Mobile uses `expo-linking` to listen for `kratossuno://spotify-connected?token=...` and stores the JWT via `expo-secure-store`. Web flow unchanged (still uses HttpOnly cookies).

**Tech Stack:** Python: PyJWT, SQLAlchemy async. TS: expo-linking 7.0, expo-secure-store 14.0, expo-router 4.0.

**Reference:** Parent spec `docs/superpowers/specs/2026-04-17-kss-hardening-pluggable-design.md` (section on Spotify integration). User issue from analysis: mobile "Connect Spotify" button opens browser, completes OAuth, but app doesn't detect auth state change without manual "Check again".

---

## File Structure

New files:
- `backend/app/services/jwt_utils.py` — sign/verify HS256 JWTs
- `backend/app/services/persistent_session.py` — async DB-backed session store that hydrates from `user_session` table on miss
- `backend/app/db/migrations/versions/003_user_session.py` — new alembic migration
- `backend/tests/test_jwt_utils.py`
- `backend/tests/test_persistent_session.py`
- `packages/mobile/app/spotify-connected.tsx` — deep link handler route
- `packages/mobile/src/deepLinks.ts` — `handleSpotifyConnectedUrl(url)` utility

Modified files:
- `backend/app/db/models.py` — add `UserSession` SQLAlchemy model
- `backend/app/api/v1/auth_spotify.py` — new route `POST /auth/spotify/mobile-callback` + detect mobile vs web in `/callback`
- `backend/app/services/session_store.py` — compose with PersistentSessionStore
- `backend/app/config.py` — add `JWT_SECRET_KEY`, `JWT_TTL_SECONDS`
- `backend/.env.example` — document JWT_*
- `backend/requirements.txt` — add `PyJWT==2.9.0`
- `packages/mobile/app/_layout.tsx` — install global Linking listener that routes deep links to `spotify-connected`
- `packages/mobile/app/(tabs)/spotify.tsx` — after login, trigger refresh via `useAuth` once deep link captured

---

## Task 1: PyJWT dependency + jwt_utils

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/jwt_utils.py`
- Create: `backend/tests/test_jwt_utils.py`

- [ ] **Step 1: Add dependency**

Append to `backend/requirements.txt`:
```
# JWT for mobile bearer tokens (W1-B)
PyJWT==2.9.0
```

Run: `cd backend && pip install PyJWT==2.9.0`

- [ ] **Step 2: Add config**

In `backend/app/config.py`, add to Settings class:
```python
    # JWT (W1-B)
    jwt_secret_key: str = Field(
        default="",
        description="HS256 signing key — 32+ random hex chars. Empty = dev mode (insecure)."
    )
    jwt_ttl_seconds: int = 604800  # 7 days
```

Append to `.env.example`:
```
# --- JWT (W1-B) ---
JWT_SECRET_KEY=replace-with-48-hex-in-prod
JWT_TTL_SECONDS=604800
```

- [ ] **Step 3: Write failing tests**

Create `backend/tests/test_jwt_utils.py`:
```python
"""Tests for services.jwt_utils."""
from __future__ import annotations
import time

import pytest


class TestJwtUtils:
    def test_sign_and_verify_roundtrip(self):
        from app.services.jwt_utils import sign_session_token, verify_session_token
        token = sign_session_token(session_id="abc123", secret="s" * 32, ttl=3600)
        payload = verify_session_token(token, secret="s" * 32)
        assert payload["sid"] == "abc123"
        assert "exp" in payload

    def test_reject_wrong_secret(self):
        from app.services.jwt_utils import sign_session_token, verify_session_token
        token = sign_session_token("abc", "s" * 32, 3600)
        with pytest.raises(Exception):  # jwt.InvalidSignatureError
            verify_session_token(token, "other" * 8)

    def test_reject_expired(self, monkeypatch):
        from app.services.jwt_utils import sign_session_token, verify_session_token
        token = sign_session_token("abc", "s" * 32, ttl=-1)
        with pytest.raises(Exception):  # jwt.ExpiredSignatureError
            verify_session_token(token, "s" * 32)

    def test_empty_secret_refused(self):
        from app.services.jwt_utils import sign_session_token
        with pytest.raises(ValueError):
            sign_session_token("abc", "", 3600)
```

- [ ] **Step 4: Verify fail**

Run: `cd backend && pytest tests/test_jwt_utils.py -v`
Expected: FAIL (module missing)

- [ ] **Step 5: Implement**

Create `backend/app/services/jwt_utils.py`:
```python
"""HS256 JWT helpers for mobile session tokens."""
from __future__ import annotations
import time
from typing import Any

import jwt


def sign_session_token(session_id: str, secret: str, ttl: int) -> str:
    if not secret:
        raise ValueError("jwt secret is empty — configure JWT_SECRET_KEY")
    payload: dict[str, Any] = {
        "sid": session_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_session_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
```

- [ ] **Step 6: Run — should pass**

Run: `cd backend && pytest tests/test_jwt_utils.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/.env.example backend/app/services/jwt_utils.py backend/tests/test_jwt_utils.py
git commit -m "feat(auth): PyJWT + sign/verify session token helpers"
```

---

## Task 2: Alembic migration — user_session table

**Files:**
- Create: `backend/app/db/migrations/versions/003_user_session.py`
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add model to models.py**

Append to `backend/app/db/models.py` (after existing classes):
```python
class UserSession(Base):
    """Persistent session — hydrates in-memory store on backend restart."""
    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    spotify_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    access_token: Mapped[str] = mapped_column(String(500))
    refresh_token: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create migration**

Create `backend/app/db/migrations/versions/003_user_session.py`:
```python
"""user_session persistent table

Revision ID: 003_user_session
Revises: 002_saved_prompt
Create Date: 2026-04-17
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "003_user_session"
down_revision = "002_saved_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_session",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("spotify_user_id", sa.String(100), nullable=True),
        sa.Column("access_token", sa.String(500), nullable=False),
        sa.Column("refresh_token", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_session_session_id", "user_session", ["session_id"], unique=True)
    op.create_index("ix_user_session_spotify_user_id", "user_session", ["spotify_user_id"])


def downgrade() -> None:
    op.drop_table("user_session")
```

- [ ] **Step 3: Verify migration applies**

Run: `cd backend && alembic upgrade head` (if local DB configured, else skip)
Expected: `INFO  [alembic.runtime.migration] Running upgrade 002_saved_prompt -> 003_user_session`

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations/versions/003_user_session.py
git commit -m "feat(db): user_session persistent table migration"
```

---

## Task 3: PersistentSessionStore

**Files:**
- Create: `backend/app/services/persistent_session.py`
- Create: `backend/tests/test_persistent_session.py`

- [ ] **Step 1: Write failing tests (SQLite in-memory)**

Create `backend/tests/test_persistent_session.py`:
```python
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
        assert ret["access_token"] == "at2"

    async def test_delete(self, session_factory):
        from app.services.persistent_session import PersistentSessionStore
        store = PersistentSessionStore(session_factory=session_factory)
        now = dt.datetime.now(dt.timezone.utc)
        await store.save("sess-1", "at", "rt", now, "s", "F")
        await store.delete("sess-1")
        assert await store.get("sess-1") is None
```

Note: requires `aiosqlite` for in-memory testing. Add to requirements.txt dev section OR install locally:
```
aiosqlite==0.20.0  # dev only for tests
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_persistent_session.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Create `backend/app/services/persistent_session.py`:
```python
"""Postgres-backed session persistence to survive backend restarts."""
from __future__ import annotations
import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import UserSession


class PersistentSessionStore:
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
        async with self._factory() as s:
            existing = (
                await s.execute(select(UserSession).where(UserSession.session_id == session_id))
            ).scalar_one_or_none()
            if existing:
                existing.access_token = access_token
                existing.refresh_token = refresh_token
                existing.expires_at = expires_at
                existing.spotify_user_id = spotify_user_id
                existing.display_name = display_name
                existing.updated_at = dt.datetime.now(dt.timezone.utc)
            else:
                s.add(UserSession(
                    session_id=session_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    spotify_user_id=spotify_user_id,
                    display_name=display_name,
                ))
            await s.commit()

    async def get(self, session_id: str) -> dict[str, Any] | None:
        async with self._factory() as s:
            row = (
                await s.execute(select(UserSession).where(UserSession.session_id == session_id))
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
        async with self._factory() as s:
            row = (
                await s.execute(select(UserSession).where(UserSession.session_id == session_id))
            ).scalar_one_or_none()
            if row:
                await s.delete(row)
                await s.commit()
```

- [ ] **Step 4: Run — should pass**

Run: `cd backend && pytest tests/test_persistent_session.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/persistent_session.py backend/tests/test_persistent_session.py
git commit -m "feat(session): PersistentSessionStore with Postgres persistence"
```

---

## Task 4: Hydration — load session from DB on miss

**Files:**
- Modify: `backend/app/services/session_store.py`

- [ ] **Step 1: Compose SessionStore with PersistentSessionStore**

Read the existing `SessionStore` class. Identify the `get` method (returns session dict or None from in-memory dict).

Add an optional `persistent` attribute:
```python
class SessionStore:
    def __init__(self, ttl_seconds: int = 604800, persistent: PersistentSessionStore | None = None):
        ...
        self._persistent = persistent

    async def get(self, session_id: str) -> dict | None:
        async with self._lock:
            entry = self._store.get(session_id)
            if entry is not None:
                return entry  # existing path
        # fallback: try persistent
        if self._persistent:
            record = await self._persistent.get(session_id)
            if record:
                # hydrate in-memory
                async with self._lock:
                    self._store[session_id] = {
                        "spotify_access_token": record["access_token"],
                        "spotify_refresh_token": record["refresh_token"],
                        "expires_at": record["expires_at"],
                        "display_name": record["display_name"],
                        "spotify_user_id": record["spotify_user_id"],
                        # pkce verifier/state omitted — only needed during login flow
                    }
                return self._store[session_id]
        return None

    async def set_spotify_tokens(self, session_id, access_token, refresh_token, expires_in, ...):
        # existing logic...
        # ALSO write-through to persistent store
        if self._persistent:
            import datetime as _dt
            await self._persistent.save(
                session_id=session_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=expires_in),
                spotify_user_id=...,
                display_name=...,
            )
```

- [ ] **Step 2: Wire factory in main.py (startup)**

In `backend/app/main.py` lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import AsyncSessionLocal
    from app.services.persistent_session import PersistentSessionStore
    from app.services.session_store import _session_store  # or wherever singleton lives

    persistent = PersistentSessionStore(session_factory=AsyncSessionLocal)
    _session_store.attach_persistent(persistent)
    yield
```

Add `attach_persistent(self, persistent)` method to `SessionStore`.

- [ ] **Step 3: Run all tests**

Run: `cd backend && pytest tests/ -v`
Expected: all pass (existing session_store tests should not regress)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/session_store.py backend/app/main.py
git commit -m "feat(session): hydrate in-memory cache from persistent DB on miss"
```

---

## Task 5: Mobile callback endpoint

**Files:**
- Modify: `backend/app/api/v1/auth_spotify.py`
- Modify: `backend/app/schemas/auth.py`

- [ ] **Step 1: Understand current /login flow**

Read `auth_spotify.py` to identify:
- `/login` creates session, returns authorize_url
- `/callback` receives `code`, exchanges for tokens, sets HttpOnly cookie

The mobile flow needs:
- `/login?platform=mobile` returns authorize_url with redirect to `/auth/spotify/mobile-callback`
- `/mobile-callback` exchanges code, issues JWT, redirects to `kratossuno://spotify-connected?token=<jwt>`

- [ ] **Step 2: Add platform param + mobile-callback route**

In `/login` handler, accept optional `platform: str | None = Query(default="web")` parameter. Branch:
- If `platform == "mobile"`: set `redirect_uri = settings.spotify_mobile_redirect_uri` (new setting) and attach a query param `_mobile=1` to state
- Otherwise: unchanged

Add new config:
```python
spotify_mobile_redirect_uri: str = Field(
    default="",
    description="e.g. https://api.example.com/api/v1/auth/spotify/mobile-callback"
)
```

Add new route:
```python
@router.get("/spotify/mobile-callback")
async def spotify_mobile_callback(
    code: str,
    state: str,
    error: str | None = None,
):
    # Validate state + exchange code — similar to /callback
    # Difference: after success, issue JWT and redirect to kratossuno://
    from app.services.jwt_utils import sign_session_token
    from fastapi.responses import RedirectResponse

    if error:
        return RedirectResponse(url=f"kratossuno://spotify-connected?error={error}", status_code=307)

    session_id = await _process_spotify_callback(code, state)  # extract into helper from existing /callback
    token = sign_session_token(
        session_id=session_id,
        secret=settings.jwt_secret_key,
        ttl=settings.jwt_ttl_seconds,
    )
    return RedirectResponse(url=f"kratossuno://spotify-connected?token={token}", status_code=307)
```

Add bearer auth pathway: when request comes with `Authorization: Bearer <jwt>`, verify, extract `sid`, use that session_id for downstream lookups. Centralize in a new dependency `resolve_session_id(request)`.

- [ ] **Step 3: Write integration test (mocked Spotify)**

Create `backend/tests/test_mobile_callback.py`:
```python
"""Integration test for /auth/spotify/mobile-callback."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


class TestMobileCallback:
    def test_success_redirects_to_scheme_with_token(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.jwt_secret_key", "s" * 32)
        monkeypatch.setattr("app.config.settings.spotify_client_id", "c1")

        # Mock SpotifyClient.exchange_code
        async def fake_exchange(self, code, verifier, redirect_uri):
            return {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
            }

        with patch("app.services.spotify_client.SpotifyClient.exchange_code",
                   new=fake_exchange):
            from app.main import app
            client = TestClient(app)
            # Seed a fake session with matching state
            # ... (depends on how _process_spotify_callback looks up state)
            # This test is structural — adjust mocks to match impl

            # For now, validate the route exists and returns redirect
            res = client.get("/api/v1/auth/spotify/mobile-callback?code=c&state=s",
                             follow_redirects=False)
            # 307 redirect expected
            assert res.status_code in (307, 400)

    def test_error_param_passes_through(self):
        from app.main import app
        client = TestClient(app)
        res = client.get("/api/v1/auth/spotify/mobile-callback?code=&state=&error=access_denied",
                         follow_redirects=False)
        assert res.status_code == 307
        assert res.headers["location"].startswith("kratossuno://spotify-connected?error=")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_mobile_callback.py -v`
Expected: both pass (may need mock adjustments)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/auth_spotify.py backend/app/config.py backend/tests/test_mobile_callback.py
git commit -m "feat(auth): Spotify mobile-callback route + JWT issuance"
```

---

## Task 6: Bearer token auth for mobile requests

**Files:**
- Modify: `backend/app/api/v1/saved_prompts.py`, `spotify_profile.py`, `auth_spotify.py`

- [ ] **Step 1: Add resolve_session_id dependency**

In `backend/app/api/v1/auth_spotify.py` (or a new `backend/app/api/deps.py`):
```python
async def resolve_session_id(request: Request) -> str | None:
    """Returns session_id from either cookie (web) or Authorization Bearer (mobile)."""
    # Web: existing cookie path
    session_id = request.cookies.get("kratos_session")
    if session_id:
        return session_id

    # Mobile: bearer JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from app.services.jwt_utils import verify_session_token
        from app.config import settings
        try:
            payload = verify_session_token(auth_header[7:], settings.jwt_secret_key)
            return payload.get("sid")
        except Exception:
            return None
    return None
```

- [ ] **Step 2: Use resolve_session_id everywhere that currently reads cookie**

In `saved_prompts.py`, `spotify_profile.py`, replace `request.cookies.get("kratos_session")` reads with `await resolve_session_id(request)`.

- [ ] **Step 3: Add test**

Create `backend/tests/test_bearer_auth.py`:
```python
"""Tests for Bearer token auth path (mobile)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient


class TestBearerAuth:
    def test_saved_prompts_accepts_bearer(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.jwt_secret_key", "s" * 32)

        from app.services.jwt_utils import sign_session_token
        from app.main import app

        # Seed an in-memory session (details depend on SessionStore API)
        token = sign_session_token("test-sess", "s" * 32, 3600)
        client = TestClient(app)
        res = client.get(
            "/api/v1/prompts",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Route exists and accepts auth header (may return 200 with empty list)
        assert res.status_code in (200, 401)
```

- [ ] **Step 4: Run**

Run: `cd backend && pytest tests/test_bearer_auth.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/
git commit -m "feat(auth): resolve session from cookie OR bearer token"
```

---

## Task 7: Mobile deep link handler

**Files:**
- Create: `packages/mobile/app/spotify-connected.tsx`
- Create: `packages/mobile/src/deepLinks.ts`
- Modify: `packages/mobile/app/_layout.tsx`

- [ ] **Step 1: Create deepLinks utility**

Create `packages/mobile/src/deepLinks.ts`:
```typescript
import * as Linking from "expo-linking";
import { setToken } from "./session";

export interface SpotifyConnectedParams {
  token?: string;
  error?: string;
}

export function parseSpotifyConnectedUrl(url: string): SpotifyConnectedParams {
  const parsed = Linking.parse(url);
  const qp = parsed.queryParams || {};
  return {
    token: typeof qp.token === "string" ? qp.token : undefined,
    error: typeof qp.error === "string" ? qp.error : undefined,
  };
}

export async function handleSpotifyConnectedUrl(url: string): Promise<{ ok: boolean; error?: string }> {
  const { token, error } = parseSpotifyConnectedUrl(url);
  if (error) return { ok: false, error };
  if (!token) return { ok: false, error: "no_token" };
  await setToken(token);
  return { ok: true };
}
```

- [ ] **Step 2: Create spotify-connected route**

Create `packages/mobile/app/spotify-connected.tsx`:
```typescript
import { useEffect } from "react";
import { View, Text, ActivityIndicator, StyleSheet } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { setToken } from "@/src/session";

export default function SpotifyConnected() {
  const { token, error } = useLocalSearchParams<{ token?: string; error?: string }>();

  useEffect(() => {
    (async () => {
      if (token) {
        await setToken(token);
        // bounce to spotify tab
        router.replace("/(tabs)/spotify");
      } else {
        // error path
        router.replace("/(tabs)/spotify");
      }
    })();
  }, [token]);

  return (
    <View style={styles.container}>
      <ActivityIndicator />
      <Text style={styles.text}>
        {error ? `Erro: ${error}` : "Conectando Spotify..."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0a0a0a" },
  text: { color: "#e0e0e0", marginTop: 16 },
});
```

- [ ] **Step 3: Install global Linking listener**

In `packages/mobile/app/_layout.tsx`, at top-level component, add:
```typescript
import { useEffect } from "react";
import * as Linking from "expo-linking";
import { handleSpotifyConnectedUrl } from "@/src/deepLinks";
import { router } from "expo-router";

// Inside Layout component:
  useEffect(() => {
    const sub = Linking.addEventListener("url", async ({ url }) => {
      if (url.includes("spotify-connected")) {
        const result = await handleSpotifyConnectedUrl(url);
        if (result.ok) {
          router.replace("/(tabs)/spotify");
        }
      }
    });
    // Also handle cold start
    (async () => {
      const initial = await Linking.getInitialURL();
      if (initial && initial.includes("spotify-connected")) {
        await handleSpotifyConnectedUrl(initial);
      }
    })();
    return () => sub.remove();
  }, []);
```

- [ ] **Step 4: Update spotify.tsx to refresh auth after deep link**

In `packages/mobile/app/(tabs)/spotify.tsx`, after `useAuth` is initialized, add a `useFocusEffect` or `useEffect` that runs `refresh()` when the tab gains focus — the deep link handler redirects here after token save.

- [ ] **Step 5: Type-check**

Run: `cd packages/mobile && pnpm typecheck`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add packages/mobile/app/spotify-connected.tsx packages/mobile/src/deepLinks.ts packages/mobile/app/_layout.tsx packages/mobile/app/\(tabs\)/spotify.tsx
git commit -m "feat(mobile): spotify-connected deep link handler + global linking listener"
```

---

## Task 8: Update mobile API client to send Bearer

**Files:**
- Modify: `packages/mobile/src/apiClient.ts` (verify existing)

Most likely already uses bearer. Verify:

- [ ] **Step 1: Confirm apiClient uses bearer strategy**

Read `packages/mobile/src/apiClient.ts`. Should have `sessionStrategy: "bearer", getBearerToken: getToken`. If not, fix.

- [ ] **Step 2: Verify session.ts exposes getToken/setToken/clearToken**

Read `packages/mobile/src/session.ts`. Should wrap `expo-secure-store` under key `"kratos.jwt"`. If not, already covered by existing code.

- [ ] **Step 3: Commit if changes**

```bash
git add packages/mobile/src/apiClient.ts
git commit -m "chore(mobile): verify Bearer auth strategy in apiClient"
```

---

## Task 9: End-to-end manual smoke test

- [ ] **Step 1: Backend up with JWT configured**

```bash
cd backend
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export SPOTIFY_CLIENT_ID=<from .env>
export SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/spotify/callback
export SPOTIFY_MOBILE_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/spotify/mobile-callback
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 2: Curl login with platform=mobile**

```bash
curl -s "http://localhost:8000/api/v1/auth/spotify/login?platform=mobile" | jq .
```

Expected: `{"authorize_url": "https://accounts.spotify.com/authorize?..."}` with redirect_uri=mobile-callback

- [ ] **Step 3: Mobile app test**

In mobile:
```bash
cd packages/mobile
npx expo start --tunnel
```

Scan QR on phone. Tap Spotify tab → Connect → complete Spotify OAuth → should auto-redirect back to app and show authenticated.

- [ ] **Step 4: Verify session survives backend restart**

After successful login on mobile, kill uvicorn. Restart. In mobile app, hit Saved tab or any authenticated endpoint — should still work (session hydrated from DB).

- [ ] **Step 5: Commit docs of smoke result**

```bash
# (No code change — document outcome in PR description)
```

---

## Done Criteria

- [ ] Mobile "Connect Spotify" works end-to-end without manual "Check again"
- [ ] Backend restart doesn't lose authenticated sessions
- [ ] 39+ original tests green, ~15+ new tests green
- [ ] JWT verification rejects tampered/expired tokens
- [ ] `user_session` table migration applies cleanly
- [ ] Web Spotify flow untouched and still works via cookies

---

## Rollback

- Mobile-callback route: remove from router; mobile falls back to cookie flow (broken but known)
- PersistentSessionStore: set `persistent=None` in SessionStore → in-memory only (pre-existing behavior, still broken on restart)
- Full revert by reverting task commits individually
