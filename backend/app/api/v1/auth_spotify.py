"""Rotas de autenticação Spotify (PKCE flow).

Flow web:
  1. GET  /auth/spotify/login        -> cria sessão, gera PKCE, retorna URL
  2. Usuário visita URL no Spotify, autoriza
  3. Spotify redireciona para /auth/spotify/callback?code=...&state=...
  4. Backend troca code por tokens, salva na sessão, redireciona pro frontend
  5. GET  /auth/status                -> frontend consulta para saber se tá logado
  6. POST /auth/logout                -> invalida sessão

Flow mobile (W1-B):
  1. GET /auth/spotify/login?platform=mobile -> state marcado como mobile
  2. Spotify redireciona para /auth/spotify/mobile-callback
  3. Backend troca code por tokens, assina JWT, redireciona para
     kratossuno://spotify-connected?token=<jwt>
  4. Expo captura deep link e guarda JWT em expo-secure-store
  5. Requests subsequentes carregam Authorization: Bearer <jwt>
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.schemas.auth import AuthStatusResponse, SpotifyAuthURLResponse
from app.services.jwt_utils import sign_session_token, verify_session_token
from app.services.session_store import SessionData, SessionStore, get_session_store
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


async def _process_spotify_callback(
    code: str,
    state: str,
    session: SessionData,
    store: SessionStore,
    redirect_uri: str,
) -> SessionData:
    """Core callback logic — shared by web (``/callback``) and mobile (``/mobile-callback``).

    Validates OAuth state, exchanges the authorization ``code`` for tokens
    (using the same ``redirect_uri`` the authorize step used — Spotify
    enforces equality), fetches the profile, and writes everything back
    into the session. Returns the updated session.

    Raises:
        HTTPException: if ``state`` mismatches or PKCE verifier missing.
        SpotifyAuthError: on token exchange failure (caller translates to 502).
    """
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
        tokens = await client.exchange_code_for_tokens(
            code=code,
            code_verifier=session.pkce_verifier,
            redirect_uri=redirect_uri,
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
    return session


async def resolve_session_id(request: Request) -> str | None:
    """Resolve session_id from either cookie (web) or ``Authorization: Bearer`` (mobile).

    W1-B: central helper so routes don't care which client is calling.
    Web flow continues to read the HttpOnly cookie; mobile clients send a
    signed JWT whose ``sid`` claim carries the session_id.
    """
    # Web: existing cookie path
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        return session_id

    # Mobile: bearer JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if not settings.jwt_secret_key:
            return None
        try:
            payload = verify_session_token(token, settings.jwt_secret_key)
        except Exception:
            return None
        sid = payload.get("sid")
        return sid if isinstance(sid, str) else None
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/spotify/login", response_model=SpotifyAuthURLResponse)
async def spotify_login(
    response: Response,
    platform: str = Query(default="web", description="'web' | 'mobile' (W1-B)"),
    store: SessionStore = Depends(get_session_store),
) -> SpotifyAuthURLResponse:
    """Inicia fluxo PKCE. Cria sessão, gera verifier/challenge, retorna URL do Spotify.

    W1-B: ``platform=mobile`` redirects Spotify to the mobile-callback endpoint,
    which issues a JWT and bounces back into the Expo app via deep link.
    """
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
    # W1-B: remember which redirect_uri was used so the callback can match
    is_mobile = platform == "mobile"
    redirect_uri = (
        settings.spotify_mobile_redirect_uri if is_mobile else settings.spotify_redirect_uri
    )
    if is_mobile and not settings.spotify_mobile_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPOTIFY_MOBILE_REDIRECT_URI não configurado",
        )
    session.extra["redirect_uri"] = redirect_uri
    session.extra["platform"] = "mobile" if is_mobile else "web"
    await store.update(session)

    _set_session_cookie(response, session.session_id)

    authorize_url = SpotifyClient.build_authorize_url(
        oauth_state, challenge, redirect_uri=redirect_uri
    )
    return SpotifyAuthURLResponse(authorize_url=authorize_url, state=oauth_state)


@router.get("/spotify/callback")
async def spotify_callback(
    code: str,
    state: str,
    kratos_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(get_session_store),
) -> RedirectResponse:
    """Callback web do Spotify. Troca code por tokens e redireciona para o frontend."""
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

    redirect_uri = session.extra.get("redirect_uri") or settings.spotify_redirect_uri
    try:
        await _process_spotify_callback(code, state, session, store, redirect_uri)
    except SpotifyAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha na autenticação Spotify: {exc}",
        )

    # Redireciona para o frontend
    return RedirectResponse(
        url=f"{settings.frontend_origin}/?spotify=connected",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/spotify/mobile-callback")
async def spotify_mobile_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    kratos_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(get_session_store),
) -> RedirectResponse:
    """Mobile callback (W1-B): exchange code, issue JWT, bounce to deep link.

    Contract:
        - On success: ``302 -> kratossuno://spotify-connected?token=<jwt>``
        - On Spotify-side error (``?error=access_denied`` etc):
          ``302 -> kratossuno://spotify-connected?error=<error>``
        - On internal state failure: same scheme with an ``error`` param so the
          Expo app can render a readable message instead of a JSON blob.
    """
    scheme = settings.spotify_mobile_scheme

    if error:
        return RedirectResponse(
            url=f"{scheme}?error={error}", status_code=status.HTTP_302_FOUND
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{scheme}?error=missing_params", status_code=status.HTTP_302_FOUND
        )

    if not kratos_session:
        return RedirectResponse(
            url=f"{scheme}?error=missing_session", status_code=status.HTTP_302_FOUND
        )

    session = await store.get(kratos_session)
    if session is None:
        return RedirectResponse(
            url=f"{scheme}?error=invalid_session", status_code=status.HTTP_302_FOUND
        )

    redirect_uri = session.extra.get("redirect_uri") or settings.spotify_mobile_redirect_uri
    try:
        await _process_spotify_callback(code, state, session, store, redirect_uri)
    except HTTPException:
        return RedirectResponse(
            url=f"{scheme}?error=state_mismatch", status_code=status.HTTP_302_FOUND
        )
    except SpotifyAuthError:
        return RedirectResponse(
            url=f"{scheme}?error=spotify_exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )

    if not settings.jwt_secret_key:
        return RedirectResponse(
            url=f"{scheme}?error=jwt_not_configured",
            status_code=status.HTTP_302_FOUND,
        )

    token = sign_session_token(
        session_id=session.session_id,
        secret=settings.jwt_secret_key,
        ttl=settings.jwt_ttl_seconds,
    )
    return RedirectResponse(
        url=f"{scheme}?token={token}", status_code=status.HTTP_302_FOUND
    )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    request: Request,
    store: SessionStore = Depends(get_session_store),
) -> AuthStatusResponse:
    """Frontend consulta para saber se tem sessão Spotify ativa.

    W1-B: resolve session via cookie (web) or Bearer (mobile).
    """
    session_id = await resolve_session_id(request)
    if not session_id:
        return AuthStatusResponse(authenticated=False)

    session = await store.get(session_id)
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
    request: Request,
    response: Response,
    store: SessionStore = Depends(get_session_store),
) -> Response:
    """Invalida a sessão e limpa o cookie."""
    session_id = await resolve_session_id(request)
    if session_id:
        await store.delete(session_id)
    response.delete_cookie(settings.session_cookie_name)
    return response
