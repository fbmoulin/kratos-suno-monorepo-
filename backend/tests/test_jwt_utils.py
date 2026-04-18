"""Tests for services.jwt_utils."""
from __future__ import annotations

import pytest
import jwt


class TestJwtUtils:
    def test_sign_and_verify_roundtrip(self):
        from app.services.jwt_utils import sign_session_token, verify_session_token

        token = sign_session_token(session_id="abc123", secret="s" * 32, ttl=3600)
        payload = verify_session_token(token, secret="s" * 32)
        assert payload["sid"] == "abc123"
        assert "exp" in payload

    def test_reject_wrong_secret(self):
        from app.services.jwt_utils import sign_session_token, verify_session_token

        token = sign_session_token("abc", "s" * 32, 3600)
        with pytest.raises(jwt.InvalidSignatureError):
            verify_session_token(token, "other" * 8)

    def test_reject_expired(self):
        from app.services.jwt_utils import sign_session_token, verify_session_token

        token = sign_session_token("abc", "s" * 32, ttl=-1)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_session_token(token, "s" * 32)

    def test_empty_secret_refused(self):
        from app.services.jwt_utils import sign_session_token

        with pytest.raises(ValueError):
            sign_session_token("abc", "", 3600)
