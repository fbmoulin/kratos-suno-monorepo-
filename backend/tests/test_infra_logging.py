"""Tests for infra.logging — request-id middleware + structlog."""
from __future__ import annotations

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
