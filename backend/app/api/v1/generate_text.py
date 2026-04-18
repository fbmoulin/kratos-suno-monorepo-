"""Endpoint: POST /api/v1/generate/text — gera style prompts a partir de nome.

Fase 3: agora com cache Postgres. Se o mesmo subject já foi extraído com a
versão ativa de prompt, retorna do cache (0 custo, ~1ms).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.infra.auth import AuthContext, require_auth
from app.infra.budget import check_budget_text, record_text_spend
from app.infra.rate_limit import rate_limit
from app.schemas.sonic_dna import GenerateFromTextRequest, GenerateResponse
from app.services.dna_cache import DNACache
from app.services.dna_text_extractor import DNAExtractionError, TextDNAExtractor
from app.services.prompt_compressor import (
    ComplianceError,
    build_lyric_template,
    compress_all,
)


router = APIRouter(prefix="/generate", tags=["generation"])


def get_text_extractor() -> TextDNAExtractor:
    """DI factory — permite mock em testes."""
    return TextDNAExtractor()


@router.post("/text", response_model=GenerateResponse)
async def generate_from_text(
    request: GenerateFromTextRequest,
    auth_ctx: AuthContext = Depends(require_auth),
    _rl: None = Depends(rate_limit),
    _bg: None = Depends(check_budget_text),
    extractor: TextDNAExtractor = Depends(get_text_extractor),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Gera 3 variantes de style prompt Suno a partir do nome informado.

    Fluxo (Fase 3):
      1. Tenta servir do cache Postgres (hit comum para artistas populares)
      2. Se miss, chama Claude para extrair DNA
      3. Persiste no cache
      4. Comprime em 3 variantes
      5. Retorna resposta
    """
    cache = DNACache(db)

    # 1. Cache lookup
    dna = await cache.get(request.subject, settings.active_prompt_version)

    # 2. Miss -> chama LLM
    if dna is None:
        try:
            dna = await extractor.extract(request.subject)
        except DNAExtractionError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao extrair Sonic DNA: {exc}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro inesperado na extração: {type(exc).__name__}",
            )

        # 3. Persiste no cache (best-effort — falha não bloqueia resposta)
        try:
            await cache.put(
                subject=request.subject,
                prompt_version=settings.active_prompt_version,
                model_used=settings.dna_extractor_model,
                dna=dna,
            )
        except Exception:
            pass  # TODO: log estruturado em produção

    # 4. Comprime
    try:
        variants = compress_all(dna, request.variants_to_generate)
    except ComplianceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha de compliance na geração: {exc}",
        )

    response = GenerateResponse(
        subject=request.subject,
        sonic_dna=dna,
        variants=variants,
        lyric_template=build_lyric_template(dna),
    )
    # Record spend after success (best-effort, do not block response)
    await record_text_spend(auth_ctx.subject_id)
    return response
