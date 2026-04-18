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
