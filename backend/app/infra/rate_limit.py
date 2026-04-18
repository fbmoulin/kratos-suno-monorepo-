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
