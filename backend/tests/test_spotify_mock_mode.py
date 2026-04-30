"""Wave 2b.5: verify SpotifyClient short-circuits when ``spotify_mock_mode`` is on.

These tests enable ``settings.spotify_mock_mode`` via monkeypatch and assert
that each of the three methods required by the OAuth happy path returns a
deterministic fixture WITHOUT touching the HTTP transport.

The Playwright E2E test (``packages/web/e2e/spotify-oauth.spec.ts``) relies
on this short-circuit so that a real SPOTIFY_CLIENT_ID is never required.
"""

from __future__ import annotations

import pytest

from app.services.spotify_client import SpotifyClient

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_mode(monkeypatch):
    """Enable spotify_mock_mode on the singleton settings for the test run."""
    from app.config import settings

    monkeypatch.setattr(settings, "spotify_mock_mode", True)
    yield


async def test_exchange_code_returns_fixed_tokens_in_mock_mode(mock_mode):
    """Token exchange must not hit httpx when mock mode is on."""
    # No http client set — if the real implementation tried to use it, the
    # assert self._http is not None would fire. Mock mode must short-circuit
    # BEFORE that line.
    client = SpotifyClient()
    tokens = await client.exchange_code_for_tokens(
        code="irrelevant",
        code_verifier="irrelevant",
    )
    assert tokens == {
        "access_token": "mock_access",
        "refresh_token": "mock_refresh",
        "expires_in": 3600,
        "scope": "user-top-read",
    }


async def test_get_current_user_returns_test_artist_in_mock_mode(mock_mode):
    """Profile fetch returns fixture with display_name == 'Test Artist'."""
    client = SpotifyClient()
    profile = await client.get_current_user("mock_access")
    assert profile["id"] == "test_user"
    assert profile["display_name"] == "Test Artist"
    assert profile["country"] == "BR"
    assert profile["images"] == []


async def test_get_top_artists_returns_three_fixture_artists_in_mock_mode(mock_mode):
    """Top artists returns exactly 3 artists (Beatles, Radiohead, Bjork) with genres."""
    client = SpotifyClient()
    artists = await client.get_top_artists("mock_access")

    assert len(artists) == 3
    names = [a.name for a in artists]
    assert names == ["The Beatles", "Radiohead", "Björk"]

    # Genre sanity check
    beatles = artists[0]
    assert "rock" in beatles.genres
    radiohead = artists[1]
    assert "alternative rock" in radiohead.genres
    bjork = artists[2]
    assert "art pop" in bjork.genres

    # Pydantic SpotifyArtist model shape
    for a in artists:
        assert a.spotify_id
        assert isinstance(a.genres, list)
