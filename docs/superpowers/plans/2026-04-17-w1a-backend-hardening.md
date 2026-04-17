# W1-A Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the FastAPI backend against public exposure (rate limiting, budget cap, structured logging, async fix for audio pipeline, compliance fix for audio flow, improved health check, CI migration gate) with pluggable abstractions for stage 1→4.

**Architecture:** New `backend/app/infra/` package hosts cross-cutting concerns (`auth`, `rate_limit`, `budget`, `logging`, `compliance`) behind Protocol interfaces + in-memory implementations for stage 1. Routes gain Depends-based middleware. `setup_X(app)` pattern keeps merges safe for parallel work.

**Tech Stack:** Python 3.12, FastAPI 0.115, Pydantic 2.9, structlog 24.4, pytest 8.3 + pytest-asyncio. Existing 39 tests must remain green.

**Reference:** Parent spec at `docs/superpowers/specs/2026-04-17-kss-hardening-pluggable-design.md`.

---

## File Structure

New files:
- `backend/app/infra/__init__.py` — re-exports `get_auth_provider`, `get_rate_limiter`, `get_budget_tracker`
- `backend/app/infra/auth.py` — `AuthProvider` Protocol + `AuthContext` model + `SharedSecretAuthProvider`
- `backend/app/infra/rate_limit.py` — `RateLimiter` Protocol + `InMemoryRateLimiter` + `setup_rate_limit(app)` + `rate_limit` Depends
- `backend/app/infra/budget.py` — `BudgetTracker` Protocol + `InMemoryBudgetTracker` + `check_budget` Depends + `record_spend()` helper
- `backend/app/infra/logging.py` — `setup_logging(app)` (structlog + request-id middleware + global exception handler + access log)
- `backend/app/infra/compliance.py` — `extract_forbidden_terms_from_hint(hint, artist_to_avoid) -> list[str]`
- `backend/app/infra/factories.py` — `_build_auth_provider`, `_build_rate_limiter`, `_build_budget_tracker` factories
- `backend/tests/test_infra_auth.py`, `test_infra_rate_limit.py`, `test_infra_budget.py`, `test_infra_compliance.py`, `test_infra_logging.py`, `test_async_audio.py`, `test_endpoints_hardening.py`
- `.github/workflows/backend.yml` step: add `alembic upgrade head --sql` pre-build check

Modified files:
- `backend/app/config.py` — add settings for infra backends + limits + log format
- `backend/app/main.py` — wire `setup_logging(app)`, `setup_rate_limit(app)`, `setup_budget(app)`, plus DI for AuthProvider in routers
- `backend/app/api/v1/generate_text.py` — add `Depends(require_auth, rate_limit, check_budget)` + `record_spend` on success
- `backend/app/api/v1/generate_audio.py` — same + call `extract_forbidden_terms_from_hint` before `compress_all`
- `backend/app/api/v1/auth_spotify.py` — add rate limit to `/login` and `/callback`
- `backend/app/services/audio_analyzer.py` — refactor `extract` as `_extract_sync` + async wrapper using `asyncio.to_thread`
- `backend/app/services/dna_audio_extractor.py` — await the async wrapper; wrap `generate_spectrogram_png` in `asyncio.to_thread`
- `backend/app/config.py` — `SPOTIFY_REDIRECT_URI` comes purely from env; no hardcoded fallback
- `backend/requirements.txt` — add `structlog>=24.4.0,<25`

---

## Task 1: Add structlog dependency and create infra package skeleton

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/infra/__init__.py`
- Create: `backend/app/infra/factories.py` (stub)

- [ ] **Step 1: Add structlog to requirements**

Append to `backend/requirements.txt`:
```
# Observability (W1-A)
structlog>=24.4.0,<25
```

- [ ] **Step 2: Install**

Run: `cd backend && pip install structlog>=24.4.0,<25`
Expected: `Successfully installed structlog-24.4.x`

- [ ] **Step 3: Create infra package skeleton**

Create `backend/app/infra/__init__.py`:
```python
"""Cross-cutting infrastructure: auth, rate-limit, budget, logging, compliance."""
from app.infra.factories import (
    get_auth_provider,
    get_budget_tracker,
    get_rate_limiter,
)

__all__ = [
    "get_auth_provider",
    "get_budget_tracker",
    "get_rate_limiter",
]
```

Create `backend/app/infra/factories.py`:
```python
"""Factories — lru_cache singletons. Each _build_X lives here so parallel agents
can add their line without conflict on __init__.py."""
from __future__ import annotations
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.infra.auth import AuthProvider
    from app.infra.budget import BudgetTracker
    from app.infra.rate_limit import RateLimiter


@lru_cache
def get_auth_provider() -> "AuthProvider":
    from app.infra.auth import _build_auth_provider
    return _build_auth_provider()


@lru_cache
def get_rate_limiter() -> "RateLimiter":
    from app.infra.rate_limit import _build_rate_limiter
    return _build_rate_limiter()


@lru_cache
def get_budget_tracker() -> "BudgetTracker":
    from app.infra.budget import _build_budget_tracker
    return _build_budget_tracker()
```

- [ ] **Step 4: Verify imports don't break existing tests**

Run: `cd backend && pytest tests/ -v`
Expected: 39 passed (nothing uses infra yet)

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/infra/
git commit -m "feat(backend): scaffold infra package + structlog dep"
```

---

## Task 2: Config expansion for infra

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add infra settings to Settings class**

After existing settings in `backend/app/config.py`, add:
```python
    # --- Infra (W1-A): pluggable backends for stage 1→4 ---
    auth_provider: Literal["none", "shared_secret", "clerk", "api_key"] = "shared_secret"
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    budget_backend: Literal["memory", "redis", "postgres"] = "memory"

    # Stage-1 limits
    shared_secret_key: str = Field(
        default="",
        description="Stage 1: X-Kratos-Key header value. Empty = disabled (dev)."
    )
    rate_limit_per_hour: int = 20
    daily_budget_usd: float = 2.0
    cost_per_text_generation_usd: float = 0.002
    cost_per_audio_generation_usd: float = 0.01

    # Observability
    log_format: Literal["json", "console"] = "console"
```

Also remove the hardcoded Spotify redirect URI — find the line with `"http://127.0.0.1:8000"` and replace the default:
```python
    spotify_redirect_uri: str = Field(
        default="",
        description="Required in production. Localhost only acceptable in dev."
    )
```

- [ ] **Step 2: Update .env.example**

Append to `backend/.env.example`:
```
# --- Infra (W1-A) ---
AUTH_PROVIDER=shared_secret
RATE_LIMIT_BACKEND=memory
BUDGET_BACKEND=memory
SHARED_SECRET_KEY=change-me-to-random-48-hex
RATE_LIMIT_PER_HOUR=20
DAILY_BUDGET_USD=2.0
LOG_FORMAT=console
```

- [ ] **Step 3: Verify tests still green**

Run: `cd backend && pytest tests/ -v`
Expected: 39 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat(backend): add infra settings to config (auth/rate-limit/budget/log)"
```

---

## Task 3: Auth Provider — tests first

**Files:**
- Create: `backend/tests/test_infra_auth.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_infra_auth.py`:
```python
"""Tests for infra.auth — AuthProvider Protocol + SharedSecretAuthProvider."""
from __future__ import annotations
import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _make_request(client_host: str = "1.2.3.4", headers: dict | None = None) -> Request:
    """Minimal ASGI scope for Request construction."""
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (client_host, 12345),
    }
    return Request(scope)


class TestSharedSecretAuthProvider:
    async def test_accepts_valid_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={"X-Kratos-Key": "secret123"})
        ctx = await provider.authenticate(request)
        assert ctx.subject_id.startswith("ip:")
        assert ctx.plan == "anon"

    async def test_rejects_missing_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={})
        with pytest.raises(HTTPException) as exc:
            await provider.authenticate(request)
        assert exc.value.status_code == 401

    async def test_rejects_wrong_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={"X-Kratos-Key": "wrong"})
        with pytest.raises(HTTPException) as exc:
            await provider.authenticate(request)
        assert exc.value.status_code == 401

    async def test_ip_hash_stable_for_same_ip(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="s")
        r1 = _make_request("9.9.9.9", headers={"X-Kratos-Key": "s"})
        r2 = _make_request("9.9.9.9", headers={"X-Kratos-Key": "s"})
        ctx1 = await provider.authenticate(r1)
        ctx2 = await provider.authenticate(r2)
        assert ctx1.subject_id == ctx2.subject_id

    async def test_different_ips_different_subject_id(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="s")
        r1 = _make_request("1.1.1.1", headers={"X-Kratos-Key": "s"})
        r2 = _make_request("2.2.2.2", headers={"X-Kratos-Key": "s"})
        ctx1 = await provider.authenticate(r1)
        ctx2 = await provider.authenticate(r2)
        assert ctx1.subject_id != ctx2.subject_id

    async def test_empty_expected_key_bypasses_auth(self):
        """Dev mode: SHARED_SECRET_KEY='' disables auth."""
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="")
        request = _make_request(headers={})
        ctx = await provider.authenticate(request)
        assert ctx.subject_id.startswith("ip:")
```

Mark async tests: add to `backend/tests/conftest.py` (create if absent):
```python
import pytest

pytestmark = pytest.mark.asyncio
```

Actually, prefer per-file marker. At top of `test_infra_auth.py` add:
```python
pytestmark = pytest.mark.asyncio
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_infra_auth.py -v`
Expected: FAIL (module `app.infra.auth` doesn't exist yet)

- [ ] **Step 3: Implement auth provider**

Create `backend/app/infra/auth.py`:
```python
"""AuthProvider Protocol + stage-1 implementations."""
from __future__ import annotations
import hashlib
from typing import Literal, Protocol

from fastapi import Depends, HTTPException, Request, status
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
                    detail={"error": "auth_missing", "code": "E_AUTH_MISSING",
                            "detail": "Invalid or missing X-Kratos-Key"},
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
```

- [ ] **Step 4: Run tests — should pass**

Run: `cd backend && pytest tests/test_infra_auth.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/auth.py backend/tests/test_infra_auth.py
git commit -m "feat(infra): AuthProvider protocol + SharedSecretAuthProvider + tests"
```

---

## Task 4: Rate Limiter — tests first

**Files:**
- Create: `backend/tests/test_infra_rate_limit.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for infra.rate_limit.InMemoryRateLimiter (sliding window)."""
from __future__ import annotations
import asyncio
import pytest

pytestmark = pytest.mark.asyncio


class TestInMemoryRateLimiter:
    async def test_allows_up_to_limit(self):
        from app.infra.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(max_per_hour=3)
        for _ in range(3):
            res = await limiter.check("ip:abc")
            assert res.allowed is True

    async def test_blocks_over_limit(self):
        from app.infra.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(max_per_hour=3)
        for _ in range(3):
            await limiter.check("ip:abc")
        res = await limiter.check("ip:abc")
        assert res.allowed is False
        assert res.retry_after_seconds is not None
        assert res.retry_after_seconds > 0

    async def test_different_subjects_independent(self):
        from app.infra.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(max_per_hour=2)
        await limiter.check("ip:a")
        await limiter.check("ip:a")
        res_a = await limiter.check("ip:a")
        res_b = await limiter.check("ip:b")
        assert res_a.allowed is False
        assert res_b.allowed is True

    async def test_concurrent_safe(self):
        """50 concurrent checks against limit=10 → exactly 10 allowed."""
        from app.infra.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(max_per_hour=10)
        results = await asyncio.gather(
            *[limiter.check("ip:x") for _ in range(50)]
        )
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 10

    async def test_release_after_ttl(self, monkeypatch):
        """Simulate time advancement via mocked _now."""
        import time as _time
        from app.infra.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter(max_per_hour=1)

        t = [1000.0]
        monkeypatch.setattr(_time, "monotonic", lambda: t[0])

        await limiter.check("ip:z")  # uses bucket slot
        r2 = await limiter.check("ip:z")
        assert r2.allowed is False

        t[0] += 3601  # advance >1h
        r3 = await limiter.check("ip:z")
        assert r3.allowed is True
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_infra_rate_limit.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement**

Create `backend/app/infra/rate_limit.py`:
```python
"""Rate limiter — stage 1 in-memory sliding window."""
from __future__ import annotations
import asyncio
import time
from collections import defaultdict, deque
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from app.config import settings


class RateLimitResult(BaseModel):
    allowed: bool
    retry_after_seconds: int | None = None
    remaining: int = 0


class RateLimiter(Protocol):
    async def check(self, subject_id: str, cost: int = 1) -> RateLimitResult: ...


class InMemoryRateLimiter:
    def __init__(self, max_per_hour: int = 20, window_seconds: int = 3600):
        self.max = max_per_hour
        self.window = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, subject_id: str, cost: int = 1) -> RateLimitResult:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets[subject_id]
            # Evict old
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()

            if len(bucket) + cost > self.max:
                retry = int(bucket[0] + self.window - now) + 1 if bucket else 1
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(1, retry),
                    remaining=max(0, self.max - len(bucket)),
                )

            for _ in range(cost):
                bucket.append(now)
            return RateLimitResult(
                allowed=True,
                remaining=self.max - len(bucket),
            )


def _build_rate_limiter() -> RateLimiter:
    match settings.rate_limit_backend:
        case "memory":
            return InMemoryRateLimiter(settings.rate_limit_per_hour)
        case "redis":
            raise NotImplementedError("Stage 2 — RedisRateLimiter")


async def rate_limit(request: Request, auth_ctx=Depends(lambda: None)) -> None:
    """FastAPI dependency. Uses AuthContext.subject_id if provided via require_auth."""
    from app.infra.auth import require_auth
    from app.infra.factories import get_rate_limiter

    # Resolve subject_id from AuthContext if chained after require_auth,
    # else hash IP directly
    if auth_ctx is not None and hasattr(auth_ctx, "subject_id"):
        subject_id = auth_ctx.subject_id
    else:
        import hashlib
        ip = request.client.host if request.client else "unknown"
        subject_id = f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"

    result = await get_rate_limiter().check(subject_id)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "code": "E_RATE_LIMIT",
                "detail": f"Max {settings.rate_limit_per_hour} requests/hour",
            },
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


def setup_rate_limit(app: FastAPI) -> None:
    """Warm up the singleton. No-op middleware registration in stage 1."""
    _ = _build_rate_limiter()
```

- [ ] **Step 4: Run — should pass**

Run: `cd backend && pytest tests/test_infra_rate_limit.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/rate_limit.py backend/tests/test_infra_rate_limit.py
git commit -m "feat(infra): InMemoryRateLimiter sliding window + tests"
```

---

## Task 5: Budget Tracker — tests first

**Files:**
- Create: `backend/tests/test_infra_budget.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for infra.budget.InMemoryBudgetTracker."""
from __future__ import annotations
import asyncio
import pytest

pytestmark = pytest.mark.asyncio


class TestInMemoryBudgetTracker:
    async def test_accepts_under_cap(self):
        from app.infra.budget import InMemoryBudgetTracker
        tracker = InMemoryBudgetTracker(daily_cap_usd=1.0)
        assert await tracker.can_spend(0.5) is True
        await tracker.record(0.5, "ip:a")
        assert await tracker.can_spend(0.4) is True

    async def test_rejects_over_cap(self):
        from app.infra.budget import InMemoryBudgetTracker
        tracker = InMemoryBudgetTracker(daily_cap_usd=1.0)
        await tracker.record(0.8, "ip:a")
        assert await tracker.can_spend(0.5) is False

    async def test_concurrent_safe(self):
        """100 concurrent records of $0.01 → total $1.00, no race."""
        from app.infra.budget import InMemoryBudgetTracker
        tracker = InMemoryBudgetTracker(daily_cap_usd=10.0)
        await asyncio.gather(
            *[tracker.record(0.01, f"ip:{i}") for i in range(100)]
        )
        remaining = await tracker.remaining()
        assert abs(remaining - 9.0) < 1e-6

    async def test_daily_reset(self, monkeypatch):
        """After UTC midnight crossing, spend resets."""
        import datetime as _dt
        from app.infra.budget import InMemoryBudgetTracker

        t = [_dt.datetime(2026, 4, 17, 23, 0, 0, tzinfo=_dt.timezone.utc)]
        monkeypatch.setattr(
            "app.infra.budget.datetime", _MockDT(t)
        )
        tracker = InMemoryBudgetTracker(daily_cap_usd=1.0)
        await tracker.record(0.9, "ip:a")
        assert await tracker.can_spend(0.2) is False

        # advance 2 hours → new day UTC
        t[0] = _dt.datetime(2026, 4, 18, 1, 0, 0, tzinfo=_dt.timezone.utc)
        assert await tracker.can_spend(0.5) is True


class _MockDT:
    def __init__(self, t):
        self._t = t
    def now(self, tz=None):
        return self._t[0]
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_infra_budget.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Create `backend/app/infra/budget.py`:
```python
"""Budget tracker — stage 1 in-memory with daily UTC reset."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Protocol

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings


class BudgetTracker(Protocol):
    async def can_spend(self, amount_usd: float) -> bool: ...
    async def record(self, amount_usd: float, subject_id: str) -> None: ...
    async def remaining(self) -> float: ...


class InMemoryBudgetTracker:
    def __init__(self, daily_cap_usd: float = 2.0):
        self.cap = daily_cap_usd
        self._spent_usd = 0.0
        self._day_key = self._today()
        self._lock = asyncio.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def _reset_if_new_day(self) -> None:
        today = self._today()
        if today != self._day_key:
            self._day_key = today
            self._spent_usd = 0.0

    async def can_spend(self, amount_usd: float) -> bool:
        async with self._lock:
            await self._reset_if_new_day()
            return (self._spent_usd + amount_usd) <= self.cap

    async def record(self, amount_usd: float, subject_id: str) -> None:
        async with self._lock:
            await self._reset_if_new_day()
            self._spent_usd += amount_usd

    async def remaining(self) -> float:
        async with self._lock:
            await self._reset_if_new_day()
            return max(0.0, self.cap - self._spent_usd)


def _build_budget_tracker() -> BudgetTracker:
    match settings.budget_backend:
        case "memory":
            return InMemoryBudgetTracker(settings.daily_budget_usd)
        case "redis":
            raise NotImplementedError("Stage 2 — RedisBudgetTracker")
        case "postgres":
            raise NotImplementedError("Stage 3 — PostgresBudgetTracker")


async def check_budget_text() -> None:
    from app.infra.factories import get_budget_tracker
    if not await get_budget_tracker().can_spend(settings.cost_per_text_generation_usd):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "budget_exceeded", "code": "E_BUDGET_EXCEEDED",
                    "detail": "Daily budget cap reached. Retry after UTC midnight."},
        )


async def check_budget_audio() -> None:
    from app.infra.factories import get_budget_tracker
    if not await get_budget_tracker().can_spend(settings.cost_per_audio_generation_usd):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "budget_exceeded", "code": "E_BUDGET_EXCEEDED",
                    "detail": "Daily budget cap reached. Retry after UTC midnight."},
        )


async def record_text_spend(subject_id: str) -> None:
    from app.infra.factories import get_budget_tracker
    await get_budget_tracker().record(settings.cost_per_text_generation_usd, subject_id)


async def record_audio_spend(subject_id: str) -> None:
    from app.infra.factories import get_budget_tracker
    await get_budget_tracker().record(settings.cost_per_audio_generation_usd, subject_id)
```

- [ ] **Step 4: Run — should pass**

Run: `cd backend && pytest tests/test_infra_budget.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/budget.py backend/tests/test_infra_budget.py
git commit -m "feat(infra): InMemoryBudgetTracker + daily UTC reset + tests"
```

---

## Task 6: Compliance — forbidden_terms heuristic

**Files:**
- Create: `backend/tests/test_infra_compliance.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for infra.compliance.extract_forbidden_terms_from_hint."""
from __future__ import annotations
import pytest


class TestExtractForbiddenTerms:
    def test_empty_hint_returns_empty(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        assert extract_forbidden_terms_from_hint("", None) == []

    def test_respects_explicit_artist_to_avoid(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("", "Beatles")
        assert "beatles" in result

    def test_extracts_capitalized_words(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint(
            "this is a cover of Beatles by John Lennon", None
        )
        assert "beatles" in result
        assert "john" in result
        assert "lennon" in result
        # lowercase words not treated as proper names
        assert "cover" not in result

    def test_extracts_quoted_phrases(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint(
            'do "Let It Be" in jazz style', None
        )
        assert "let it be" in result

    def test_merges_hint_and_artist_to_avoid_dedup(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("cover of Beatles", "beatles")
        assert result.count("beatles") == 1

    def test_strips_short_common_words(self):
        """False-positive mitigation for 'Brazilian jazz'."""
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("Brazilian jazz", None)
        # 'brazilian' is a nationality, not an artist — skip common adjectives
        assert "brazilian" not in result

    def test_returns_sorted_unique_lowercase(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("ZETA alpha Beta", None)
        assert result == sorted(set(r.lower() for r in result))
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_infra_compliance.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Create `backend/app/infra/compliance.py`:
```python
"""Compliance — heuristic extraction of forbidden_terms from free-text hints."""
from __future__ import annotations
import re

# Common adjectives/nationalities/generic words that accidentally capitalize
_COMMON_FALSE_POSITIVES = {
    "brazilian", "american", "british", "french", "german", "italian",
    "japanese", "portuguese", "spanish", "english", "chinese", "korean",
    "indie", "alternative", "electronic", "acoustic", "classical",
    "jazz", "rock", "pop", "folk", "metal", "rap", "hip", "hop",
    "old", "new", "young", "modern", "ancient",
}


def extract_forbidden_terms_from_hint(
    hint: str | None,
    artist_to_avoid: str | None,
) -> list[str]:
    """Return lowercase sorted list of likely proper-name tokens.

    Heuristic-only (no NER library). Covers:
    1. Explicit artist_to_avoid field
    2. Quoted phrases in hint: "Bohemian Rhapsody"
    3. Capitalized words in hint (filtering common false positives)
    """
    terms: set[str] = set()

    if artist_to_avoid:
        terms.add(artist_to_avoid.strip().lower())

    if hint:
        # 1. quoted phrases
        for match in re.findall(r'["\u201c]([^"\u201d]{2,40})["\u201d]', hint):
            terms.add(match.strip().lower())

        # 2. capitalized tokens (length >= 3 to avoid "A", "I")
        for token in re.findall(r"\b[A-Z][a-z]{2,}\b", hint):
            lower = token.lower()
            if lower not in _COMMON_FALSE_POSITIVES:
                terms.add(lower)

    # Drop empty strings and sort
    return sorted(t for t in terms if t)
```

- [ ] **Step 4: Run — should pass**

Run: `cd backend && pytest tests/test_infra_compliance.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/compliance.py backend/tests/test_infra_compliance.py
git commit -m "feat(infra): heuristic forbidden_terms extraction + tests"
```

---

## Task 7: Structured logging (structlog) + global exception handler

**Files:**
- Create: `backend/tests/test_infra_logging.py`
- Create: `backend/app/infra/logging.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for infra.logging — request-id middleware + structlog."""
from __future__ import annotations
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_logging():
    from app.infra.logging import setup_logging
    app = FastAPI()
    setup_logging(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


class TestRequestIdMiddleware:
    def test_generates_request_id_if_absent(self, app_with_logging):
        client = TestClient(app_with_logging)
        res = client.get("/ping")
        assert res.status_code == 200
        assert "x-request-id" in {k.lower() for k in res.headers}
        assert len(res.headers["x-request-id"]) > 8

    def test_preserves_request_id_from_header(self, app_with_logging):
        client = TestClient(app_with_logging)
        res = client.get("/ping", headers={"X-Request-Id": "custom-123"})
        assert res.headers["x-request-id"] == "custom-123"


class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_structured_error(self):
        from app.infra.logging import setup_logging
        app = FastAPI()
        setup_logging(app)

        @app.get("/boom")
        async def boom():
            raise RuntimeError("kaboom")

        client = TestClient(app, raise_server_exceptions=False)
        res = client.get("/boom")
        assert res.status_code == 500
        body = res.json()
        assert body["error"] == "internal_error"
        assert body["code"] == "E_INTERNAL"
        assert "request_id" in body
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_infra_logging.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Create `backend/app/infra/logging.py`:
```python
"""Structured logging + request-id middleware + global exception handler."""
from __future__ import annotations
import contextvars
import logging
import sys
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# Context var accessible anywhere via structlog.contextvars
_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def _configure_structlog() -> None:
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        token = _REQUEST_ID.set(req_id)
        structlog.contextvars.bind_contextvars(request_id=req_id)
        log = structlog.get_logger("http")
        log.info("request.start", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
            _REQUEST_ID.reset(token)
        response.headers["X-Request-Id"] = req_id
        log.info("request.end", status=response.status_code)
        return response


def setup_logging(app: FastAPI) -> None:
    _configure_structlog()
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(Exception)
    async def _global_handler(request: Request, exc: Exception):
        req_id = _REQUEST_ID.get()
        log = structlog.get_logger("error")
        log.error("unhandled_exception",
                  exc_type=type(exc).__name__,
                  exc_msg=str(exc),
                  path=request.url.path)
        detail = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "code": "E_INTERNAL",
                "detail": detail,
                "request_id": req_id,
            },
            headers={"X-Request-Id": req_id},
        )
```

- [ ] **Step 4: Run — should pass**

Run: `cd backend && pytest tests/test_infra_logging.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infra/logging.py backend/tests/test_infra_logging.py
git commit -m "feat(infra): structlog + RequestIdMiddleware + global exception handler"
```

---

## Task 8: Async fix — audio pipeline

**Files:**
- Modify: `backend/app/services/audio_analyzer.py`
- Modify: `backend/app/services/dna_audio_extractor.py`
- Create: `backend/tests/test_async_audio.py`

- [ ] **Step 1: Write failing test**

```python
"""Verify audio pipeline doesn't block event loop."""
from __future__ import annotations
import asyncio
import time

import numpy as np
import pytest
import soundfile as sf
from pathlib import Path

pytestmark = pytest.mark.asyncio


@pytest.fixture
def synthetic_wav(tmp_path: Path) -> Path:
    """60s sine wave at 440Hz, 22050Hz sample rate, mono."""
    sr = 22050
    duration = 5.0  # keep test fast
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    path = tmp_path / "sine.wav"
    sf.write(str(path), y, sr)
    return path


class TestAsyncAudioExtractor:
    async def test_extract_async_runs_sync_in_thread(self, synthetic_wav: Path):
        """Two parallel calls should finish in ~time of 1 (concurrency proven)."""
        from app.services.audio_analyzer import AudioFeatureExtractor
        extractor = AudioFeatureExtractor()

        start = time.monotonic()
        await extractor.extract_async(synthetic_wav)
        single_dur = time.monotonic() - start

        start = time.monotonic()
        await asyncio.gather(
            extractor.extract_async(synthetic_wav),
            extractor.extract_async(synthetic_wav),
        )
        parallel_dur = time.monotonic() - start

        # Parallel must be <1.7x single (would be 2x if blocking)
        assert parallel_dur < single_dur * 1.7, (
            f"Audio extract is blocking: parallel {parallel_dur:.2f}s vs "
            f"single {single_dur:.2f}s"
        )

    async def test_extract_async_returns_same_features_as_sync(self, synthetic_wav: Path):
        from app.services.audio_analyzer import AudioFeatureExtractor
        extractor = AudioFeatureExtractor()
        sync_features = extractor.extract(synthetic_wav)
        async_features = await extractor.extract_async(synthetic_wav)
        assert sync_features == async_features
```

- [ ] **Step 2: Verify fail**

Run: `cd backend && pytest tests/test_async_audio.py -v`
Expected: FAIL (`extract_async` doesn't exist)

- [ ] **Step 3: Add async method to AudioFeatureExtractor**

In `backend/app/services/audio_analyzer.py`, at end of class `AudioFeatureExtractor`:
```python
    async def extract_async(self, source):
        """Non-blocking wrapper — runs librosa in threadpool."""
        import asyncio
        return await asyncio.to_thread(self.extract, source)
```

Also add module-level async spectrogram:
```python
async def generate_spectrogram_png_async(source, duration_seconds=30.0, sample_rate=22050):
    import asyncio
    return await asyncio.to_thread(generate_spectrogram_png, source, duration_seconds, sample_rate)
```

- [ ] **Step 4: Update dna_audio_extractor to use async versions**

In `backend/app/services/dna_audio_extractor.py`, find the `extract` method. Replace:
```python
features = self.audio_extractor.extract(audio_source)
```
with:
```python
features = await self.audio_extractor.extract_async(audio_source)
```

And:
```python
spectrogram_bytes = generate_spectrogram_png(audio_source)
```
with:
```python
from app.services.audio_analyzer import generate_spectrogram_png_async
spectrogram_bytes = await generate_spectrogram_png_async(audio_source)
```

(Keep existing seek() call in between.)

- [ ] **Step 5: Run — should pass**

Run: `cd backend && pytest tests/test_async_audio.py tests/test_prompt_compressor.py -v`
Expected: all pass (39 existing + 2 new)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/audio_analyzer.py backend/app/services/dna_audio_extractor.py backend/tests/test_async_audio.py
git commit -m "fix(audio): wrap librosa+matplotlib in asyncio.to_thread"
```

---

## Task 9: Wire infra into main.py + routes

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v1/generate_text.py`
- Modify: `backend/app/api/v1/generate_audio.py`
- Modify: `backend/app/api/v1/auth_spotify.py`

- [ ] **Step 1: Wire setup_logging in main.py**

Near top of `backend/app/main.py` add import:
```python
from app.infra.logging import setup_logging
from app.infra.rate_limit import setup_rate_limit
```

After `app = FastAPI(...)` block, before routers:
```python
setup_logging(app)
setup_rate_limit(app)
```

- [ ] **Step 2: Update generate_text route**

In `backend/app/api/v1/generate_text.py`, add imports:
```python
from app.infra.auth import require_auth, AuthContext
from app.infra.rate_limit import rate_limit
from app.infra.budget import check_budget_text, record_text_spend
```

Modify the route signature to add deps:
```python
@router.post("/text", response_model=GenerateResponse)
async def generate_from_text(
    request: GenerateFromTextRequest,
    auth_ctx: AuthContext = Depends(require_auth),
    _rl: None = Depends(rate_limit),
    _bg: None = Depends(check_budget_text),
    extractor: TextDNAExtractor = Depends(get_text_extractor),
) -> GenerateResponse:
```

At end of the handler, after successful `return` path, record spend. Restructure:
```python
    response = GenerateResponse(...)
    await record_text_spend(auth_ctx.subject_id)
    return response
```

- [ ] **Step 3: Update generate_audio route**

Same pattern + compliance extraction. In `generate_audio.py`:

Add imports:
```python
from app.infra.auth import require_auth, AuthContext
from app.infra.rate_limit import rate_limit
from app.infra.budget import check_budget_audio, record_audio_spend
from app.infra.compliance import extract_forbidden_terms_from_hint
```

Modify signature to include `artist_to_avoid: str | None = Form(default=None)` and deps:
```python
@router.post("/audio", response_model=GenerateResponse)
async def generate_from_audio(
    file: UploadFile = File(...),
    user_hint: str | None = Form(default=None, max_length=200),
    artist_to_avoid: str | None = Form(default=None, max_length=200),
    variants_to_generate: int = Form(default=3, ge=1, le=3),
    auth_ctx: AuthContext = Depends(require_auth),
    _rl: None = Depends(rate_limit),
    _bg: None = Depends(check_budget_audio),
    extractor: AudioDNAExtractor = Depends(get_audio_extractor),
) -> GenerateResponse:
```

Before `compress_all(dna, ...)`, inject forbidden terms:
```python
    extra_forbidden = extract_forbidden_terms_from_hint(user_hint, artist_to_avoid)
    dna.forbidden_terms = sorted(set(dna.forbidden_terms + extra_forbidden))
```

At end, record spend:
```python
    await record_audio_spend(auth_ctx.subject_id)
    return response
```

- [ ] **Step 4: Add rate limit to Spotify login/callback**

In `backend/app/api/v1/auth_spotify.py`, add `Depends(rate_limit)` to `/login` and `/callback` route definitions.

- [ ] **Step 5: Run full suite**

Run: `cd backend && pytest tests/ -v`
Expected: all 39 existing tests pass + new tests from tasks 3-8 pass. Total ~65.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/v1/
git commit -m "feat(api): wire auth/rate-limit/budget/compliance into routes"
```

---

## Task 10: Health check improvement

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Extend /health to validate DB + Anthropic key presence**

Replace the existing `/health` endpoint body:
```python
@app.get("/health", tags=["meta"])
async def health() -> dict[str, object]:
    from app.infra.factories import get_budget_tracker
    checks: dict[str, str] = {}

    # Anthropic key configured
    checks["anthropic_key"] = "configured" if settings.anthropic_api_key else "missing"

    # Budget state
    remaining = await get_budget_tracker().remaining()
    checks["budget_remaining_usd"] = f"{remaining:.2f}"

    # Prompt version file exists
    from pathlib import Path
    prompt_path = Path(__file__).parent / "prompts" / "versions" / f"{settings.active_prompt_version}.md"
    checks["prompt_version_file"] = "present" if prompt_path.exists() else "missing"

    status_overall = "ok" if checks["anthropic_key"] == "configured" and checks["prompt_version_file"] == "present" else "degraded"
    return {"status": status_overall, "app": settings.app_name, "checks": checks}
```

- [ ] **Step 2: Smoke test**

Run: `cd backend && uvicorn app.main:app --port 8001 &` (background)
Then: `curl -s http://localhost:8001/health | jq .`
Kill the background process.

Expected shape:
```json
{"status": "ok", "app": "kratos-suno-prompt", "checks": {...}}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(health): validate Anthropic key + budget + prompt file"
```

---

## Task 11: CI — migration gate

**Files:**
- Modify: `.github/workflows/backend.yml`

- [ ] **Step 1: Add alembic dry-run step before Docker build**

In `.github/workflows/backend.yml`, in the test job (before or after pytest), add:
```yaml
      - name: Verify alembic migrations apply
        run: |
          cd backend
          # Spin up ephemeral Postgres
          docker run -d --name pg-test -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16-alpine
          for i in 1 2 3 4 5; do
            pg_isready -h localhost -p 5433 && break
            sleep 2
          done
          DATABASE_URL=postgresql+asyncpg://postgres:test@localhost:5433/postgres \
            alembic upgrade head
          docker rm -f pg-test
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/backend.yml
git commit -m "ci(backend): add alembic migration dry-run gate"
```

---

## Task 12: Final integration test + docs

**Files:**
- Create: `backend/tests/test_endpoints_hardening.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Write integration tests**

```python
"""Integration tests covering hardened routes (rate limit, budget, auth)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.fixture(autouse=True)
def reset_infra(monkeypatch):
    # Force re-create singletons
    from app.infra import factories
    factories.get_auth_provider.cache_clear()
    factories.get_rate_limiter.cache_clear()
    factories.get_budget_tracker.cache_clear()
    # Empty shared secret = dev mode (no auth required)
    monkeypatch.setattr("app.config.settings.shared_secret_key", "")
    monkeypatch.setattr("app.config.settings.rate_limit_per_hour", 3)
    monkeypatch.setattr("app.config.settings.daily_budget_usd", 0.005)


def _mock_dna():
    return {
        "subject": "Test", "subject_type": "band", "era": "2020s",
        "genre_primary": "pop", "bpm_min": 100, "bpm_max": 120, "bpm_typical": 110,
        "mood_primary": "happy", "instruments": ["guitar", "drums"],
        "vocal_gender": "male", "vocal_timbre": "tenor",
        "production_palette": ["clean"], "articulation_score": 7,
        "forbidden_terms": [],
    }


def test_rate_limit_returns_429_after_limit(monkeypatch):
    async def fake_extract(self, subject):
        from app.schemas.sonic_dna import SonicDNA
        return SonicDNA(**_mock_dna())

    monkeypatch.setattr("app.services.dna_text_extractor.TextDNAExtractor.extract", fake_extract)
    client = TestClient(app)
    for _ in range(3):
        res = client.post("/api/v1/generate/text", json={"subject": "Test"})
        assert res.status_code == 200
    res = client.post("/api/v1/generate/text", json={"subject": "Test"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_budget_returns_402_when_exhausted(monkeypatch):
    async def fake_extract(self, subject):
        from app.schemas.sonic_dna import SonicDNA
        return SonicDNA(**_mock_dna())

    monkeypatch.setattr("app.services.dna_text_extractor.TextDNAExtractor.extract", fake_extract)
    # cost_per_text = 0.002, cap = 0.005 → ~2 allowed before 402
    client = TestClient(app)
    for _ in range(2):
        client.post("/api/v1/generate/text", json={"subject": "Test"})
    res = client.post("/api/v1/generate/text", json={"subject": "Test"})
    assert res.status_code == 402
```

- [ ] **Step 2: Run full suite**

Run: `cd backend && pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_endpoints_hardening.py
git commit -m "test(integration): rate limit 429 + budget 402 + auth wiring"
```

---

## Done Criteria

- [ ] All 39 original tests still green
- [ ] ~30+ new tests added, all green
- [ ] `grep -r "TODO" backend/app/infra/` returns empty
- [ ] `pytest --cov=app.infra` shows >90% coverage on infra/
- [ ] `/health` returns structured checks
- [ ] CI migration gate runs in <30s
- [ ] Manual smoke: `pnpm dev:backend` + `curl -H "X-Kratos-Key: test" http://localhost:8000/api/v1/generate/text ...` works
- [ ] Manual smoke: 21st curl gets 429
- [ ] Manual smoke: audio upload with `artist_to_avoid=Beatles` blocks vazamento via compliance

---

## Rollback

All changes are additive. If issues found in production:
1. Set `AUTH_PROVIDER=none` in env → disables shared-secret check
2. Set `RATE_LIMIT_PER_HOUR=99999` → effectively disabled
3. Set `DAILY_BUDGET_USD=9999` → effectively disabled
4. Revert individual commits — each task is atomic
