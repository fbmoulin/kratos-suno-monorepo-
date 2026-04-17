"""Testes das utilities de auth e cache — PKCE + cache key determinístico."""
from __future__ import annotations

import base64
import hashlib

from app.services.cache_utils import compute_cache_key, normalize_subject
from app.services.pkce_utils import generate_pkce_pair


class TestPKCE:
    def test_verifier_has_valid_length(self):
        verifier, _ = generate_pkce_pair()
        # RFC 7636: 43-128 chars
        assert 43 <= len(verifier) <= 128

    def test_challenge_is_sha256_of_verifier(self):
        verifier, challenge = generate_pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")
        assert challenge == expected

    def test_verifier_is_url_safe(self):
        verifier, _ = generate_pkce_pair()
        # Só caracteres URL-safe (letras, dígitos, -, _)
        allowed = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert set(verifier).issubset(allowed)

    def test_pairs_are_unique(self):
        """Duas chamadas consecutivas geram pairs diferentes."""
        v1, c1 = generate_pkce_pair()
        v2, c2 = generate_pkce_pair()
        assert v1 != v2
        assert c1 != c2

    def test_challenge_has_no_padding(self):
        """Base64url sem padding (sem '=' no final)."""
        _, challenge = generate_pkce_pair()
        assert "=" not in challenge


class TestCacheKey:
    def test_normalize_subject_lowercase(self):
        assert normalize_subject("Coldplay") == "coldplay"

    def test_normalize_subject_trims_whitespace(self):
        assert normalize_subject("  Coldplay  ") == "coldplay"

    def test_normalize_subject_collapses_spaces(self):
        assert normalize_subject("Pink   Floyd") == "pink floyd"

    def test_same_subject_produces_same_key(self):
        k1 = compute_cache_key("Coldplay", "v1_baseline")
        k2 = compute_cache_key("coldplay", "v1_baseline")
        k3 = compute_cache_key("  COLDPLAY  ", "v1_baseline")
        assert k1 == k2 == k3

    def test_different_prompt_version_different_key(self):
        k1 = compute_cache_key("Coldplay", "v1_baseline")
        k2 = compute_cache_key("Coldplay", "v2_stricter")
        assert k1 != k2

    def test_key_is_sha256_length(self):
        key = compute_cache_key("Coldplay", "v1_baseline")
        assert len(key) == 64  # SHA256 em hex
        # Só hex chars
        assert all(c in "0123456789abcdef" for c in key)
