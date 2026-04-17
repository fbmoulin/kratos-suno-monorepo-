"""Rota GET /api/v1/spotify/profile — perfil de gosto do usuário."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status

from app.schemas.auth import TasteProfile
from app.services.session_store import SessionStore, get_session_store
from app.services.spotify_client import SpotifyAPIError, SpotifyClient


router = APIRouter(prefix="/spotify", tags=["spotify"])


@router.get("/profile", response_model=TasteProfile)
async def get_taste_profile(
    time_range: Literal["short_term", "medium_term", "long_term"] = Query(
        default="medium_term",
        description="short_term=4 semanas, medium_term=6 meses, long_term=anos",
    ),
    kratos_session: str | None = Cookie(default=None),
    store: SessionStore = Depends(get_session_store),
) -> TasteProfile:
    """Retorna top artists do usuário + gêneros dominantes."""
    if not kratos_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado — faça login com Spotify primeiro",
        )

    session = await store.get(kratos_session)
    if session is None or not session.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

    async with SpotifyClient() as client:
        try:
            # Renova token se estiver perto de expirar
            access_token = await client.ensure_fresh_token(session)
            await store.update(session)

            return await client.build_taste_profile(
                access_token,
                time_range=time_range,
            )
        except SpotifyAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao consultar Spotify: {exc}",
            )
