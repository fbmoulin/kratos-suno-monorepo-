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
