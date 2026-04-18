"""Rotas de autenticação Spotify (PKCE flow).

Flow:
  1. GET  /auth/spotify/login        -> cria sessão, gera PKCE, retorna URL
  2. Usuário visita URL no Spotify, autoriza
  3. Spotify redireciona para /auth/spotify/callback?code=...&state=...
  4. Backend troca code por tokens, salva na sessão, redireciona pro frontend
  5. GET  /auth/status                -> frontend consulta para saber se tá logado
  6. POST /auth/logout                -> invalida sessão
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.infra.rate_limit import rate_limit
from app.schemas.auth import AuthStatusResponse, SpotifyAuthURLResponse
from app.services.session_store import SessionStore, get_session_store
from app.services.spotify_client import (
    SpotifyAuthError,
    SpotifyClient,
    generate_pkce_pair,
)


router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_session_cookie(response: Response, session_id: str) -> None:
    """Seta cookie HTTP-only com session_id."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # HTTPS obrigatório em prod
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/spotify/login", response_model=SpotifyAuthURLResponse)
async def spotify_login(
    response: Response,
    _rl: None = Depends(rate_limit),
    store: SessionStore = Depends(get_session_store),
) -> SpotifyAuthURLResponse:
    """Inicia fluxo PKCE. Cria sessão, gera verifier/challenge, retorna URL do Spotify."""
    if not settings.spotify_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integração Spotify não configurada no servidor (SPOTIFY_CLIENT_ID ausente)",
        )

    session = await store.create()
    verifier, challenge = generate_pkce_pair()
    oauth_state = secrets.token_urlsafe(16)

    session.pkce_verifier = verifier
    session.oauth_state = oauth_state
    await store.update(session)

    _set_session_cookie(response, session.session_id)

    authorize_url = SpotifyClient.build_authorize_url(oauth_state, challenge)
    return SpotifyAuthURLResponse(authorize_url=authorize_url, state=oauth_state)


@router.get("/spotify/callback")
async def spotify_callback(
    code: str,
    state: str,
    kratos_session: str | None = Cookie(default=None),
    _rl: None = Depends(rate_limit),
    store: SessionStore = Depends(get_session_store),
) -> RedirectResponse:
    """Callback do Spotify. Troca code por tokens e redireciona para o frontend."""
    if not kratos_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão ausente — inicie o login novamente",
        )

    session = await store.get(kratos_session)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

    # Valida state (anti-CSRF)
    if session.oauth_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State inválido — possível tentativa de CSRF",
        )

    if not session.pkce_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão sem PKCE verifier",
        )

    # Troca code por tokens
    async with SpotifyClient() as client:
        try:
            tokens = await client.exchange_code_for_tokens(
                code=code,
                code_verifier=session.pkce_verifier,
            )
        except SpotifyAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha na autenticação Spotify: {exc}",
            )

        # Busca perfil básico pra exibir nome
        try:
            profile = await client.get_current_user(tokens["access_token"])
        except Exception:
            profile = {}

    # Atualiza sessão
    session.spotify_access_token = tokens["access_token"]
    session.spotify_refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    session.spotify_token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in
    )
    session.spotify_user_id = profile.get("id")
    session.display_name = profile.get("display_name")
    # Limpa PKCE (não precisa mais)
    session.pkce_verifier = None
    session.oauth_state = None
    await store.update(session)

    # Redireciona para o frontend
    return RedirectResponse(
        url=f"{settings.frontend_origin}/?spotify=connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    kratos_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(get_session_store),
) -> AuthStatusResponse:
    """Frontend consulta para saber se tem sessão Spotify ativa."""
    if not kratos_session:
        return AuthStatusResponse(authenticated=False)

    session = await store.get(kratos_session)
    if session is None or not session.is_authenticated:
        return AuthStatusResponse(authenticated=False)

    return AuthStatusResponse(
        authenticated=True,
        spotify_user_id=session.spotify_user_id,
        display_name=session.display_name,
        expires_at=session.spotify_token_expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    kratos_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(get_session_store),
) -> Response:
    """Invalida a sessão e limpa o cookie."""
    if kratos_session:
        await store.delete(kratos_session)
    response.delete_cookie(settings.session_cookie_name)
    return response
