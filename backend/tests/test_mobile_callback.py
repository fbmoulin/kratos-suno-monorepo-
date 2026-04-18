"""Integration tests for W1-B /auth/spotify/mobile-callback + /auth/spotify/login?platform=mobile."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    """TestClient with JWT + mobile config pre-seeded and a fresh session store."""
    # debug=True lets the HttpOnly cookie be sent over plain http in tests
    monkeypatch.setattr("app.config.settings.debug", True)
    monkeypatch.setattr("app.config.settings.jwt_secret_key", "s" * 32)
    monkeypatch.setattr("app.config.settings.spotify_client_id", "c1")
    monkeypatch.setattr(
        "app.config.settings.spotify_redirect_uri",
        "http://127.0.0.1:8000/api/v1/auth/spotify/callback",
    )
    monkeypatch.setattr(
        "app.config.settings.spotify_mobile_redirect_uri",
        "http://127.0.0.1:8000/api/v1/auth/spotify/mobile-callback",
    )
    monkeypatch.setattr(
        "app.config.settings.spotify_mobile_scheme",
        "kratossuno://spotify-connected",
    )
    # Reset the session store singleton between tests
    import app.services.session_store as ss_mod

    monkeypatch.setattr(ss_mod, "_store", None)

    from app.main import app

    return TestClient(app)


class TestMobileCallbackErrors:
    def test_error_param_redirects_to_scheme(self, client):
        res = client.get(
            "/api/v1/auth/spotify/mobile-callback?error=access_denied",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["location"] == (
            "kratossuno://spotify-connected?error=access_denied"
        )

    def test_missing_params_redirects_with_error(self, client):
        res = client.get(
            "/api/v1/auth/spotify/mobile-callback",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["location"].startswith(
            "kratossuno://spotify-connected?error="
        )

    def test_missing_session_cookie_redirects_with_error(self, client):
        res = client.get(
            "/api/v1/auth/spotify/mobile-callback?code=abc&state=xyz",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "error=missing_session" in res.headers["location"]

    def test_invalid_session_cookie_redirects_with_error(self, client):
        res = client.get(
            "/api/v1/auth/spotify/mobile-callback?code=abc&state=xyz",
            cookies={"kratos_session": "does-not-exist"},
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "error=invalid_session" in res.headers["location"]


class TestMobileLoginPlatform:
    def test_login_with_platform_mobile_uses_mobile_redirect_uri(self, client):
        res = client.get(
            "/api/v1/auth/spotify/login?platform=mobile",
            follow_redirects=False,
        )
        assert res.status_code == 200
        body = res.json()
        assert "authorize_url" in body
        # Spotify redirect_uri is URL-encoded — assert the mobile callback path shows up
        assert "mobile-callback" in body["authorize_url"]

    def test_login_with_platform_web_uses_web_redirect_uri(self, client):
        res = client.get(
            "/api/v1/auth/spotify/login?platform=web",
            follow_redirects=False,
        )
        assert res.status_code == 200
        body = res.json()
        # Default web path, not mobile-callback
        assert "mobile-callback" not in body["authorize_url"]


class TestMobileCallbackSuccess:
    def test_successful_exchange_issues_jwt_and_redirects(self, client, monkeypatch):
        """End-to-end happy path: login (mobile) then callback returns JWT."""
        from app.services.jwt_utils import verify_session_token

        # Step 1: login with platform=mobile (TestClient persists cookies)
        login_res = client.get(
            "/api/v1/auth/spotify/login?platform=mobile",
            follow_redirects=False,
        )
        assert login_res.status_code == 200
        state = login_res.json()["state"]
        assert "kratos_session" in client.cookies

        # Step 2: mock the Spotify token exchange + profile fetch
        async def fake_exchange(self, code, code_verifier, redirect_uri=None):
            return {
                "access_token": "mock-at",
                "refresh_token": "mock-rt",
                "expires_in": 3600,
            }

        async def fake_profile(self, access_token):
            return {"id": "spotify-user-42", "display_name": "Felipe"}

        with patch(
            "app.services.spotify_client.SpotifyClient.exchange_code_for_tokens",
            new=fake_exchange,
        ), patch(
            "app.services.spotify_client.SpotifyClient.get_current_user",
            new=fake_profile,
        ):
            res = client.get(
                f"/api/v1/auth/spotify/mobile-callback?code=any-code&state={state}",
                follow_redirects=False,
            )

        assert res.status_code == 302
        location = res.headers["location"]
        assert location.startswith("kratossuno://spotify-connected?token="), (
            f"expected token redirect, got: {location}"
        )
        token = location.split("token=", 1)[1]
        payload = verify_session_token(token, "s" * 32)
        assert "sid" in payload
        assert payload["sid"]  # non-empty session_id
