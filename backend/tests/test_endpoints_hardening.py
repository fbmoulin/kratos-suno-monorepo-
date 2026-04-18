"""Integration tests covering hardened routes (rate limit, budget, auth)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_infra(monkeypatch):
    """Force re-create singletons with tighter limits for test isolation."""
    # Empty shared secret = dev mode (no auth required)
    monkeypatch.setattr("app.config.settings.shared_secret_key", "")
    monkeypatch.setattr("app.config.settings.rate_limit_per_hour", 3)
    monkeypatch.setattr("app.config.settings.daily_budget_usd", 0.005)
    monkeypatch.setattr("app.config.settings.cost_per_text_generation_usd", 0.002)

    # Clear cached singletons so they pick up the new settings
    from app.infra import factories
    factories.get_auth_provider.cache_clear()
    factories.get_rate_limiter.cache_clear()
    factories.get_budget_tracker.cache_clear()
    yield
    factories.get_auth_provider.cache_clear()
    factories.get_rate_limiter.cache_clear()
    factories.get_budget_tracker.cache_clear()


def _mock_dna_dict() -> dict:
    return {
        "subject": "Test",
        "subject_type": "band",
        "era": "2020s",
        "genre_primary": "pop",
        "bpm_min": 100,
        "bpm_max": 120,
        "bpm_typical": 110,
        "mood_primary": "happy",
        "instruments": ["guitar", "drums"],
        "vocal_gender": "male",
        "vocal_timbre": "tenor",
        "production_palette": ["clean"],
        "articulation_score": 7,
        "forbidden_terms": [],
    }


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient with DB + LLM fully mocked."""
    from app.schemas.sonic_dna import SonicDNA

    # Mock TextDNAExtractor.extract to return a fixed DNA
    async def fake_extract(self, subject):
        return SonicDNA(**_mock_dna_dict())

    monkeypatch.setattr(
        "app.services.dna_text_extractor.TextDNAExtractor.extract",
        fake_extract,
    )

    # Mock DNACache.get -> always miss; DNACache.put -> no-op
    async def fake_cache_get(self, subject, prompt_version):
        return None

    async def fake_cache_put(self, **kwargs):
        return None

    monkeypatch.setattr("app.services.dna_cache.DNACache.get", fake_cache_get)
    monkeypatch.setattr("app.services.dna_cache.DNACache.put", fake_cache_put)

    # Override get_db dependency to yield None (DNACache is mocked, won't touch DB)
    from app.db.session import get_db
    from app.main import app

    async def fake_get_db():
        yield None

    app.dependency_overrides[get_db] = fake_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_rate_limit_returns_429_after_limit(client, monkeypatch):
    """With rate_limit_per_hour=3, the 4th request should be 429.

    Override the budget cap high enough so it doesn't fire first.
    """
    monkeypatch.setattr("app.config.settings.daily_budget_usd", 100.0)
    from app.infra import factories
    factories.get_budget_tracker.cache_clear()

    for i in range(3):
        res = client.post("/api/v1/generate/text", json={"subject": "Test"})
        assert res.status_code == 200, f"Request {i + 1} failed: {res.status_code} {res.text}"
    res = client.post("/api/v1/generate/text", json={"subject": "Test"})
    assert res.status_code == 429
    assert "retry-after" in {k.lower() for k in res.headers}


def test_budget_returns_402_when_exhausted(client):
    """cost_per_text = 0.002, cap = 0.005 -> 2 allowed before 402."""
    # Two calls fit under 0.005 (2 * 0.002 = 0.004)
    for _ in range(2):
        res = client.post("/api/v1/generate/text", json={"subject": "Test"})
        assert res.status_code == 200
    # Third would push to 0.006, exceeds cap
    res = client.post("/api/v1/generate/text", json={"subject": "Test"})
    assert res.status_code == 402
