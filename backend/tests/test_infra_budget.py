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
