"""Endpoint: POST /api/v1/generate/audio — gera style prompts a partir de MP3.

Aceita multipart/form-data com campo `file` (MP3/WAV/FLAC/M4A/OGG)
e campo opcional `user_hint` (texto).
"""
from __future__ import annotations

import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.schemas.sonic_dna import GenerateResponse
from app.services.dna_audio_extractor import AudioDNAExtractor
from app.services.dna_text_extractor import DNAExtractionError
from app.services.prompt_compressor import (
    ComplianceError,
    build_lyric_template,
    compress_all,
)

router = APIRouter(prefix="/generate", tags=["generation"])


def get_audio_extractor() -> AudioDNAExtractor:
    return AudioDNAExtractor()


@router.post("/audio", response_model=GenerateResponse)
async def generate_from_audio(
    file: UploadFile = File(..., description="Arquivo de áudio (MP3/WAV/FLAC/M4A/OGG)"),
    user_hint: str | None = Form(default=None, max_length=200),
    variants_to_generate: int = Form(default=3, ge=1, le=3),
    extractor: AudioDNAExtractor = Depends(get_audio_extractor),
) -> GenerateResponse:
    """Análise híbrida: librosa extrai BPM/key precisos, Claude interpreta o resto.

    Pipeline:
        1. Valida formato e tamanho do arquivo
        2. librosa mede BPM, key, energia, brilho
        3. Gera espectrograma Mel como PNG
        4. Claude Sonnet recebe números + imagem + hint
        5. Compressor gera 3 variantes e valida compliance
    """
    # Validação de formato
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo sem nome",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_audio_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato '{ext}' não suportado. "
                f"Permitidos: {', '.join(settings.allowed_audio_extensions)}"
            ),
        )

    # Ler em memória (limite de tamanho)
    max_bytes = settings.max_audio_upload_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo excede limite de {settings.max_audio_upload_mb}MB",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio",
        )

    # Extrai DNA (híbrido librosa + Claude)
    try:
        audio_io = io.BytesIO(content)
        dna, features = await extractor.extract(audio_io, user_hint=user_hint)
    except DNAExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao extrair Sonic DNA: {exc}",
        )
    except ValueError as exc:
        # librosa não conseguiu ler o áudio
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo de áudio inválido: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro inesperado: {type(exc).__name__}",
        )

    # Comprime em variantes
    try:
        variants = compress_all(dna, variants_to_generate)
    except ComplianceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha de compliance: {exc}",
        )

    return GenerateResponse(
        subject=f"[audio] {file.filename}",
        sonic_dna=dna,
        variants=variants,
        lyric_template=build_lyric_template(dna),
    )
