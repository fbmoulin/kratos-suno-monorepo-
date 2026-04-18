"""FastAPI application entry point.

Padrão KCP: lifespan context manager para startup/shutdown assíncrono,
CORS restrito ao frontend_origin configurado, routers versionados em /api/v1.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    auth_spotify,
    generate_audio,
    generate_text,
    saved_prompts,
    spotify_profile,
)
from app.config import settings
from app.infra.logging import setup_logging
from app.infra.rate_limit import setup_rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown assíncrono.

    W1-B: attach a persistent session store so sessions survive restarts.
    If the DB is unreachable, log and fall back to in-memory only (current
    behaviour) — this must never break the app at startup.
    """
    from app.db.session import AsyncSessionLocal
    from app.services.persistent_session import PersistentSessionStore
    from app.services.session_store import get_session_store

    try:
        persistent = PersistentSessionStore(session_factory=AsyncSessionLocal)
        get_session_store().attach_persistent(persistent)
    except Exception:
        # Non-fatal — in-memory sessions still work, just not durable
        pass

    # TODO(fase-4): inicializar background task de cleanup de sessões expiradas
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Gera style prompts para Suno AI a partir de nome de artista/banda/música "
        "(texto), arquivo de áudio (MP3) ou perfil de gosto Spotify. "
        "Arquitetura híbrida Claude + librosa + Spotify."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# Infra wiring (W1-A): structured logging + rate limiter singleton
setup_logging(app)
setup_rate_limit(app)

# CORS — precisa allow_credentials=True para cookies Spotify
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers v1
app.include_router(generate_text.router, prefix="/api/v1")
app.include_router(generate_audio.router, prefix="/api/v1")
app.include_router(auth_spotify.router, prefix="/api/v1")
app.include_router(spotify_profile.router, prefix="/api/v1")
app.include_router(saved_prompts.router, prefix="/api/v1")


# Health check
@app.get("/health", tags=["meta"])
async def health() -> dict[str, object]:
    from pathlib import Path

    from app.infra.factories import get_budget_tracker

    checks: dict[str, str] = {}

    # Anthropic key configured
    checks["anthropic_key"] = "configured" if settings.anthropic_api_key else "missing"

    # Budget state
    remaining = await get_budget_tracker().remaining()
    checks["budget_remaining_usd"] = f"{remaining:.2f}"

    # Prompt version file exists
    prompt_path = (
        Path(__file__).parent
        / "prompts"
        / "versions"
        / f"{settings.active_prompt_version}.md"
    )
    checks["prompt_version_file"] = "present" if prompt_path.exists() else "missing"

    status_overall = (
        "ok"
        if checks["anthropic_key"] == "configured"
        and checks["prompt_version_file"] == "present"
        else "degraded"
    )
    return {"status": status_overall, "app": settings.app_name, "checks": checks}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "message": "Kratos Suno Prompt API",
        "docs": "/docs",
        "health": "/health",
    }
