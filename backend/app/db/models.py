"""Modelos SQLAlchemy 2.0 para persistência.

Uso principal (Fase 3): cachear DNAs já extraídos para evitar re-chamar a
API Anthropic quando o mesmo subject for consultado de novo.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa SQLAlchemy 2.0."""


class CachedDNA(Base):
    """Cache de Sonic DNAs extraídos.

    Chave: hash do subject normalizado (lowercase + trim) + prompt_version.
    Assim, mudar a versão do prompt invalida o cache automaticamente.
    """

    __tablename__ = "cached_dna"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(200), index=True)
    prompt_version: Mapped[str] = mapped_column(String(50))
    model_used: Mapped[str] = mapped_column(String(100))
    dna_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GenerationLog(Base):
    """Log de gerações para observabilidade e análise de uso."""

    __tablename__ = "generation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)  # "text" | "audio" | "spotify_taste"
    subject: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(50))
    success: Mapped[bool] = mapped_column()
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SavedPrompt(Base):
    """Prompts que o usuário salvou para reuso.

    Fase 3 MVP: sem autenticação obrigatória — usa session_id (cookie) para
    vincular a sessão do usuário. Fase futura: trocar por user_id real.
    """

    __tablename__ = "saved_prompt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20))  # "text" | "audio" | "spotify_taste"
    sonic_dna: Mapped[dict] = mapped_column(JSON)
    variants: Mapped[list] = mapped_column(JSON)
    lyric_template: Mapped[str] = mapped_column(String(4000))
    user_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
