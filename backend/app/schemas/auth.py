"""Schemas adicionais da Fase 3.

Não alteram os schemas existentes em sonic_dna.py — apenas adicionam novos
tipos para autenticação Spotify, perfil de gosto e saved prompts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.sonic_dna import SonicDNA, SunoPromptVariant


# ---------------------------------------------------------------------------
# Spotify OAuth
# ---------------------------------------------------------------------------

class SpotifyAuthURLResponse(BaseModel):
    """Resposta de GET /auth/spotify/login."""

    authorize_url: str = Field(..., description="URL para redirect do usuário")
    state: str = Field(..., description="State param para validação no callback")


class SpotifyCallbackRequest(BaseModel):
    """Body do POST /auth/spotify/callback quando usado por SPA com PKCE."""

    code: str
    state: str
    code_verifier: str = Field(..., description="Verifier PKCE do frontend")


class AuthStatusResponse(BaseModel):
    """GET /auth/status — o frontend consulta para saber se tem sessão."""

    authenticated: bool
    spotify_user_id: str | None = None
    display_name: str | None = None
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Spotify profile (taste)
# ---------------------------------------------------------------------------

class SpotifyArtist(BaseModel):
    """Artista do top-artists do usuário."""

    spotify_id: str
    name: str
    genres: list[str] = Field(default_factory=list)
    image_url: str | None = None


class TasteProfile(BaseModel):
    """Perfil de gosto agregado do usuário Spotify.

    Fonte: top-artists do usuário nos últimos N meses (scope: user-top-read).
    """

    top_artists: list[SpotifyArtist]
    dominant_genres: list[str] = Field(
        ..., description="Gêneros mais frequentes, ordenados por contagem"
    )
    time_range: Literal["short_term", "medium_term", "long_term"] = "medium_term"


# ---------------------------------------------------------------------------
# Saved prompts (CRUD)
# ---------------------------------------------------------------------------

class SavedPromptCreate(BaseModel):
    """POST /api/v1/prompts — criar novo prompt salvo."""

    subject: str = Field(..., max_length=200)
    source: Literal["text", "audio", "spotify_taste"]
    sonic_dna: SonicDNA
    variants: list[SunoPromptVariant]
    lyric_template: str
    user_note: str | None = Field(default=None, max_length=500)


class SavedPromptResponse(BaseModel):
    """Item retornado por GET /api/v1/prompts e derivados."""

    id: int
    subject: str
    source: str
    sonic_dna: SonicDNA
    variants: list[SunoPromptVariant]
    lyric_template: str
    user_note: str | None
    created_at: datetime


class SavedPromptListResponse(BaseModel):
    items: list[SavedPromptResponse]
    total: int
