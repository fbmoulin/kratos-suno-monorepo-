"""Tests for infra.auth — AuthProvider Protocol + SharedSecretAuthProvider."""
from __future__ import annotations
import pytest
from fastapi import HTTPException
from starlette.requests import Request

pytestmark = pytest.mark.asyncio


def _make_request(client_host: str = "1.2.3.4", headers: dict | None = None) -> Request:
    """Minimal ASGI scope for Request construction."""
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (client_host, 12345),
    }
    return Request(scope)


class TestSharedSecretAuthProvider:
    async def test_accepts_valid_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={"X-Kratos-Key": "secret123"})
        ctx = await provider.authenticate(request)
        assert ctx.subject_id.startswith("ip:")
        assert ctx.plan == "anon"

    async def test_rejects_missing_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={})
        with pytest.raises(HTTPException) as exc:
            await provider.authenticate(request)
        assert exc.value.status_code == 401

    async def test_rejects_wrong_key(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="secret123")
        request = _make_request(headers={"X-Kratos-Key": "wrong"})
        with pytest.raises(HTTPException) as exc:
            await provider.authenticate(request)
        assert exc.value.status_code == 401

    async def test_ip_hash_stable_for_same_ip(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="s")
        r1 = _make_request("9.9.9.9", headers={"X-Kratos-Key": "s"})
        r2 = _make_request("9.9.9.9", headers={"X-Kratos-Key": "s"})
        ctx1 = await provider.authenticate(r1)
        ctx2 = await provider.authenticate(r2)
        assert ctx1.subject_id == ctx2.subject_id

    async def test_different_ips_different_subject_id(self):
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="s")
        r1 = _make_request("1.1.1.1", headers={"X-Kratos-Key": "s"})
        r2 = _make_request("2.2.2.2", headers={"X-Kratos-Key": "s"})
        ctx1 = await provider.authenticate(r1)
        ctx2 = await provider.authenticate(r2)
        assert ctx1.subject_id != ctx2.subject_id

    async def test_empty_expected_key_bypasses_auth(self):
        """Dev mode: SHARED_SECRET_KEY='' disables auth."""
        from app.infra.auth import SharedSecretAuthProvider
        provider = SharedSecretAuthProvider(expected_key="")
        request = _make_request(headers={})
        ctx = await provider.authenticate(request)
        assert ctx.subject_id.startswith("ip:")
