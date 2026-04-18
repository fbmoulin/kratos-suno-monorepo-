"""Configuração centralizada via pydantic-settings.

Padrão ModelRoleConfig (inspirado em pseuno-ai): cada papel do pipeline
tem seu modelo configurável. Assim você pode usar Haiku para extração
barata e Sonnet para interpretação de áudio, por exemplo.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings globais. Todas as variáveis podem ser sobrescritas via .env"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------------
    # App
    # -----------------------------------------------------------------------
    app_name: str = "kratos-suno-prompt"
    debug: bool = False
    frontend_origin: str = "http://localhost:5173"

    # -----------------------------------------------------------------------
    # LLM - Anthropic (role-based config)
    # -----------------------------------------------------------------------
    anthropic_api_key: str = Field(default="", description="Obrigatório em produção")

    # Role: extração de DNA a partir de texto (barato, estruturado)
    dna_extractor_model: str = "claude-haiku-4-5-20251001"

    # Role: análise de áudio com vision (precisa de Sonnet ou melhor)
    audio_dna_model: str = "claude-sonnet-4-6"

    # Role: validação / refinamento (opcional, só se quiser dupla-checagem)
    validator_model: str = "claude-haiku-4-5-20251001"

    # -----------------------------------------------------------------------
    # Prompt versioning (Prompt Lab)
    # -----------------------------------------------------------------------
    active_prompt_version: str = "v1_baseline"

    # -----------------------------------------------------------------------
    # Database (para cache de DNAs e saved prompts)
    # -----------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/kratos_suno",
        description="Connection string async (SQLAlchemy 2.0 style)",
    )

    # -----------------------------------------------------------------------
    # Uploads
    # -----------------------------------------------------------------------
    max_audio_upload_mb: int = 25
    allowed_audio_extensions: tuple[str, ...] = (".mp3", ".wav", ".flac", ".m4a", ".ogg")

    # -----------------------------------------------------------------------
    # Audio analysis
    # -----------------------------------------------------------------------
    audio_analysis_duration_seconds: float = 60.0
    spectrogram_duration_seconds: float = 30.0

    # -----------------------------------------------------------------------
    # Spotify OAuth (Fase 3)
    # -----------------------------------------------------------------------
    spotify_client_id: str = Field(default="", description="Opcional — app funciona sem Spotify")
    spotify_redirect_uri: str = Field(
        default="",
        description="Required in production. Localhost only acceptable in dev.",
    )
    spotify_mobile_redirect_uri: str = Field(
        default="",
        description=(
            "W1-B: mobile-specific Spotify redirect URI — e.g. "
            "https://api.example.com/api/v1/auth/spotify/mobile-callback. "
            "Empty = mobile flow disabled."
        ),
    )
    spotify_mobile_scheme: str = Field(
        default="kratossuno://spotify-connected",
        description="W1-B: deep-link URL used to bounce back into the Expo app.",
    )
    spotify_api_base: str = "https://api.spotify.com/v1"
    spotify_auth_base: str = "https://accounts.spotify.com"
    # Scopes mínimos — só leitura de top artists e profile
    spotify_scopes: tuple[str, ...] = ("user-top-read", "user-read-email")

    # -----------------------------------------------------------------------
    # Sessions (in-memory, TTL em segundos)
    # -----------------------------------------------------------------------
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 dias
    session_cookie_name: str = "kratos_session"

    # -----------------------------------------------------------------------
    # DNA cache
    # -----------------------------------------------------------------------
    dna_cache_enabled: bool = True
    dna_cache_ttl_days: int = 30

    # -----------------------------------------------------------------------
    # Infra (W1-A): pluggable backends for stage 1→4
    # -----------------------------------------------------------------------
    auth_provider: Literal["none", "shared_secret", "clerk", "api_key"] = "shared_secret"
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    budget_backend: Literal["memory", "redis", "postgres"] = "memory"

    # Stage-1 limits
    shared_secret_key: str = Field(
        default="",
        description="Stage 1: X-Kratos-Key header value. Empty = disabled (dev).",
    )
    rate_limit_per_hour: int = 20
    daily_budget_usd: float = 2.0
    cost_per_text_generation_usd: float = 0.002
    cost_per_audio_generation_usd: float = 0.01

    # Observability
    log_format: Literal["json", "console"] = "console"

    # -----------------------------------------------------------------------
    # JWT (W1-B) — bearer tokens for mobile clients
    # -----------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="",
        description="HS256 signing key — 32+ random hex chars. Empty = dev mode (insecure).",
    )
    jwt_ttl_seconds: int = 604800  # 7 days


@lru_cache
def get_settings() -> Settings:
    """Singleton via lru_cache para reuso em todo o app."""
    return Settings()


settings = get_settings()
