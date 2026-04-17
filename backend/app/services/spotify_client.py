"""SpotifyClient — autenticação PKCE + chamadas à Web API (versão 2026).

Mudanças importantes da Web API:
- audio-features foi DEPRECADO (nov/2024). Não usamos mais.
- preview_url (30s) foi removido. Não podemos baixar preview para librosa.
- HTTPS obrigatório em produção (localhost aceito só em dev).

Portanto, o Spotify aqui serve APENAS para:
1. Autenticar o usuário (PKCE)
2. Obter perfil (display_name, user_id)
3. Obter top artists + genres Spotify (user-top-read)

A partir dessa lista de artistas, o usuário pode escolher um e gerar
prompt via o fluxo /generate/text padrão.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.schemas.auth import SpotifyArtist, TasteProfile
from app.services.pkce_utils import generate_pkce_pair
from app.services.session_store import SessionData

# Re-export para código existente que importava daqui
__all__ = [
    "SpotifyAuthError",
    "SpotifyAPIError",
    "SpotifyClient",
    "generate_pkce_pair",
]


class SpotifyAuthError(Exception):
    """Falha no fluxo OAuth."""


class SpotifyAPIError(Exception):
    """Falha em chamada da Web API após autenticado."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SpotifyClient:
    """Wrapper stateless de chamadas à Spotify Web API.

    Não guarda sessão — recebe SessionData ou tokens em cada call.
    Session state é gerenciado externamente via SessionStore.
    """

    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http
        self._owns_http = http is None

    async def __aenter__(self) -> SpotifyClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    # -----------------------------------------------------------------------
    # Auth: build URL, exchange code, refresh token
    # -----------------------------------------------------------------------

    @staticmethod
    def build_authorize_url(
        state: str,
        code_challenge: str,
    ) -> str:
        """Monta a URL para redirecionar o usuário ao consent do Spotify."""
        if not settings.spotify_client_id:
            raise SpotifyAuthError(
                "SPOTIFY_CLIENT_ID não configurado. Adicione no .env para usar Spotify."
            )
        params = {
            "response_type": "code",
            "client_id": settings.spotify_client_id,
            "scope": " ".join(settings.spotify_scopes),
            "redirect_uri": settings.spotify_redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        return f"{settings.spotify_auth_base}/authorize?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        """Troca o authorization code por access_token + refresh_token."""
        assert self._http is not None
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.spotify_redirect_uri,
            "client_id": settings.spotify_client_id,
            "code_verifier": code_verifier,
        }
        resp = await self._http.post(
            f"{settings.spotify_auth_base}/api/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise SpotifyAuthError(
                f"Falha no exchange de token: HTTP {resp.status_code} — {resp.text}"
            )
        return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Renova access_token usando refresh_token."""
        assert self._http is not None
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.spotify_client_id,
        }
        resp = await self._http.post(
            f"{settings.spotify_auth_base}/api/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            raise SpotifyAuthError(
                f"Falha no refresh: HTTP {resp.status_code} — {resp.text}"
            )
        return resp.json()

    async def ensure_fresh_token(self, session: SessionData) -> str:
        """Retorna access_token válido, renovando se estiver perto de expirar."""
        if not session.spotify_refresh_token:
            raise SpotifyAuthError("Sessão sem refresh_token")

        if session.is_spotify_token_expired():
            tokens = await self.refresh_access_token(session.spotify_refresh_token)
            session.spotify_access_token = tokens["access_token"]
            # Spotify às vezes rotaciona refresh_token
            if new_refresh := tokens.get("refresh_token"):
                session.spotify_refresh_token = new_refresh
            expires_in = tokens.get("expires_in", 3600)
            session.spotify_token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )

        assert session.spotify_access_token is not None
        return session.spotify_access_token

    # -----------------------------------------------------------------------
    # API calls
    # -----------------------------------------------------------------------

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        """GET /me — perfil do usuário autenticado."""
        assert self._http is not None
        resp = await self._http.get(
            f"{settings.spotify_api_base}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise SpotifyAPIError(f"Falha em /me: HTTP {resp.status_code}")
        return resp.json()

    async def get_top_artists(
        self,
        access_token: str,
        time_range: str = "medium_term",
        limit: int = 20,
    ) -> list[SpotifyArtist]:
        """GET /me/top/artists — artistas mais escutados pelo usuário.

        time_range:
            short_term  = últimas 4 semanas
            medium_term = últimos 6 meses (default)
            long_term   = vários anos
        """
        assert self._http is not None
        resp = await self._http.get(
            f"{settings.spotify_api_base}/me/top/artists",
            params={"time_range": time_range, "limit": min(limit, 50)},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise SpotifyAPIError(
                f"Falha em /me/top/artists: HTTP {resp.status_code} — {resp.text}"
            )
        data = resp.json()
        items = data.get("items", [])
        return [
            SpotifyArtist(
                spotify_id=item["id"],
                name=item["name"],
                genres=item.get("genres", []),
                image_url=(item.get("images") or [{}])[0].get("url"),
            )
            for item in items
        ]

    async def build_taste_profile(
        self,
        access_token: str,
        time_range: str = "medium_term",
    ) -> TasteProfile:
        """Monta um TasteProfile agregando top artists + gêneros dominantes."""
        artists = await self.get_top_artists(access_token, time_range=time_range)

        # Conta gêneros (cada artista tem N gêneros Spotify)
        genre_count: dict[str, int] = {}
        for a in artists:
            for g in a.genres:
                genre_count[g] = genre_count.get(g, 0) + 1

        # Top 10 gêneros por frequência
        dominant_genres = sorted(
            genre_count.keys(),
            key=lambda g: genre_count[g],
            reverse=True,
        )[:10]

        return TasteProfile(
            top_artists=artists,
            dominant_genres=dominant_genres,
            time_range=time_range,  # type: ignore
        )
