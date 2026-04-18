"""W1-B: tests for Bearer-token auth path (mobile) via ``resolve_session_id``."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setattr("app.config.settings.jwt_secret_key", "s" * 32)
    return "s" * 32


@pytest.fixture
def mini_app(jwt_secret):
    """Minimal app that exposes resolve_session_id behind a /whoami endpoint."""
    from app.api.v1.auth_spotify import resolve_session_id

    app = FastAPI()

    @app.get("/whoami")
    async def whoami(request: Request):
        sid = await resolve_session_id(request)
        return {"sid": sid}

    return app


class TestBearerAuthResolver:
    def test_valid_bearer_resolves_sid(self, mini_app, jwt_secret):
        from app.services.jwt_utils import sign_session_token

        token = sign_session_token("my-mobile-session", jwt_secret, 3600)
        client = TestClient(mini_app)
        res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json() == {"sid": "my-mobile-session"}

    def test_cookie_still_works(self, mini_app):
        client = TestClient(mini_app)
        client.cookies.set("kratos_session", "web-session-abc")
        res = client.get("/whoami")
        assert res.status_code == 200
        assert res.json() == {"sid": "web-session-abc"}

    def test_cookie_takes_priority_over_bearer(self, mini_app, jwt_secret):
        """Current flow: cookie wins when both are present — matches web-first design."""
        from app.services.jwt_utils import sign_session_token

        token = sign_session_token("from-bearer", jwt_secret, 3600)
        client = TestClient(mini_app)
        client.cookies.set("kratos_session", "from-cookie")
        res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert res.json() == {"sid": "from-cookie"}

    def test_invalid_bearer_returns_none(self, mini_app):
        client = TestClient(mini_app)
        res = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-jwt"})
        assert res.status_code == 200
        assert res.json() == {"sid": None}

    def test_tampered_bearer_returns_none(self, mini_app, jwt_secret):
        from app.services.jwt_utils import sign_session_token

        token = sign_session_token("sid1", "other-secret" * 4, 3600)
        client = TestClient(mini_app)
        res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert res.json() == {"sid": None}

    def test_no_auth_returns_none(self, mini_app):
        client = TestClient(mini_app)
        res = client.get("/whoami")
        assert res.json() == {"sid": None}

    def test_empty_jwt_secret_rejects_bearer(self, mini_app, monkeypatch):
        """If JWT_SECRET_KEY is unconfigured, bearer path must refuse rather than accept anything."""
        from app.services.jwt_utils import sign_session_token

        token = sign_session_token("sid1", "s" * 32, 3600)
        monkeypatch.setattr("app.config.settings.jwt_secret_key", "")
        client = TestClient(mini_app)
        res = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        assert res.json() == {"sid": None}
