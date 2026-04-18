"""Budget tracker — stage 1 in-memory with daily UTC reset."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Protocol

from fastapi import HTTPException, status

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
            detail={
                "error": "budget_exceeded",
                "code": "E_BUDGET_EXCEEDED",
                "detail": "Daily budget cap reached. Retry after UTC midnight.",
            },
        )


async def check_budget_audio() -> None:
    from app.infra.factories import get_budget_tracker
    if not await get_budget_tracker().can_spend(settings.cost_per_audio_generation_usd):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "budget_exceeded",
                "code": "E_BUDGET_EXCEEDED",
                "detail": "Daily budget cap reached. Retry after UTC midnight.",
            },
        )


async def record_text_spend(subject_id: str) -> None:
    from app.infra.factories import get_budget_tracker
    await get_budget_tracker().record(settings.cost_per_text_generation_usd, subject_id)


async def record_audio_spend(subject_id: str) -> None:
    from app.infra.factories import get_budget_tracker
    await get_budget_tracker().record(settings.cost_per_audio_generation_usd, subject_id)
