"""PKCE utilities — RFC 7636, zero dependências externas.

Isolado do SpotifyClient (que depende de httpx) para testes unitários rápidos.
"""
from __future__ import annotations

import base64
import hashlib
import secrets


def generate_pkce_pair() -> tuple[str, str]:
    """Gera (verifier, challenge) para PKCE (RFC 7636).

    - verifier: 43-128 chars cryptographically random URL-safe
    - challenge: SHA256(verifier) em base64url sem padding

    Uso:
        verifier, challenge = generate_pkce_pair()
        # challenge vai na URL de authorize
        # verifier é guardado server-side para trocar code por token
    """
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge
