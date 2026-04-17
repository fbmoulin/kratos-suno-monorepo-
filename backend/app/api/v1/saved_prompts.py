"""Rotas CRUD para saved prompts.

Prompts são vinculados à session_id (cookie). Isso permite uso anônimo
(sem login Spotify) e também identifica prompts de usuários logados.

  POST   /api/v1/prompts           -> cria novo prompt salvo
  GET    /api/v1/prompts           -> lista prompts da sessão atual
  GET    /api/v1/prompts/{id}      -> detalha um prompt
  DELETE /api/v1/prompts/{id}      -> remove um prompt
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import SavedPrompt
from app.db.session import get_db
from app.schemas.auth import (
    SavedPromptCreate,
    SavedPromptListResponse,
    SavedPromptResponse,
)


router = APIRouter(prefix="/prompts", tags=["saved_prompts"])


def _ensure_session_id(
    response: Response,
    kratos_session: str | None,
) -> str:
    """Retorna session_id existente ou cria um novo (+ cookie).

    Permite uso anônimo — a cada request sem cookie, o backend cria um
    session_id descartável e retorna via cookie. Assim o usuário pode
    salvar prompts mesmo sem Spotify, e eles persistem nas próximas visitas.
    """
    if kratos_session:
        return kratos_session

    new_id = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=new_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
    )
    return new_id


@router.post("", response_model=SavedPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_prompt(
    payload: SavedPromptCreate,
    response: Response,
    kratos_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> SavedPromptResponse:
    """Cria um novo prompt salvo vinculado à sessão."""
    session_id = _ensure_session_id(response, kratos_session)

    row = SavedPrompt(
        session_id=session_id,
        subject=payload.subject,
        source=payload.source,
        sonic_dna=payload.sonic_dna.model_dump(),
        variants=[v.model_dump() for v in payload.variants],
        lyric_template=payload.lyric_template,
        user_note=payload.user_note,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    return SavedPromptResponse(
        id=row.id,
        subject=row.subject,
        source=row.source,
        sonic_dna=payload.sonic_dna,
        variants=payload.variants,
        lyric_template=row.lyric_template,
        user_note=row.user_note,
        created_at=row.created_at,
    )


@router.get("", response_model=SavedPromptListResponse)
async def list_saved_prompts(
    response: Response,
    kratos_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> SavedPromptListResponse:
    """Lista prompts salvos da sessão atual (ordenados por mais recentes)."""
    session_id = _ensure_session_id(response, kratos_session)

    stmt = (
        select(SavedPrompt)
        .where(SavedPrompt.session_id == session_id)
        .order_by(desc(SavedPrompt.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        SavedPromptResponse(
            id=row.id,
            subject=row.subject,
            source=row.source,
            sonic_dna=row.sonic_dna,  # Pydantic valida
            variants=row.variants,
            lyric_template=row.lyric_template,
            user_note=row.user_note,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return SavedPromptListResponse(items=items, total=len(items))


@router.get("/{prompt_id}", response_model=SavedPromptResponse)
async def get_saved_prompt(
    prompt_id: int,
    kratos_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> SavedPromptResponse:
    """Detalha um prompt salvo específico."""
    if not kratos_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sem sessão")

    stmt = select(SavedPrompt).where(
        SavedPrompt.id == prompt_id,
        SavedPrompt.session_id == kratos_session,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt não encontrado")

    return SavedPromptResponse(
        id=row.id,
        subject=row.subject,
        source=row.source,
        sonic_dna=row.sonic_dna,
        variants=row.variants,
        lyric_template=row.lyric_template,
        user_note=row.user_note,
        created_at=row.created_at,
    )


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_prompt(
    prompt_id: int,
    kratos_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove um prompt salvo (só da sessão atual)."""
    if not kratos_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sem sessão")

    stmt = select(SavedPrompt).where(
        SavedPrompt.id == prompt_id,
        SavedPrompt.session_id == kratos_session,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt não encontrado")

    await db.delete(row)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
