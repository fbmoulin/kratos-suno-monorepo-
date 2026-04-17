"""DNACache — cache de Sonic DNAs em Postgres.

Chave: hash SHA256 de (subject_normalizado + prompt_version).
Isso garante que mudar a versão do prompt invalida o cache automaticamente.

Não cacheamos DNAs extraídos de áudio (cada arquivo é único por natureza —
hashear os bytes do MP3 seria caro e teria hit-rate baixo).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CachedDNA
from app.schemas.sonic_dna import SonicDNA
from app.services.cache_utils import compute_cache_key, normalize_subject

# Re-export para manter retrocompatibilidade
__all__ = ["DNACache", "compute_cache_key", "normalize_subject"]


class DNACache:
    """Cache Postgres-backed de SonicDNA."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.ttl_days = settings.dna_cache_ttl_days

    async def get(
        self,
        subject: str,
        prompt_version: str,
    ) -> SonicDNA | None:
        """Retorna DNA cacheado se existir e não estiver expirado."""
        if not settings.dna_cache_enabled:
            return None

        cache_key = compute_cache_key(subject, prompt_version)
        stmt = select(CachedDNA).where(CachedDNA.cache_key == cache_key)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        # Verifica TTL
        age_limit = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
        # created_at é timezone-aware (server_default=func.now() com TIMESTAMPTZ)
        if row.created_at < age_limit:
            # Expirado — remove e retorna None
            await self.session.delete(row)
            await self.session.flush()
            return None

        return SonicDNA(**row.dna_json)

    async def put(
        self,
        subject: str,
        prompt_version: str,
        model_used: str,
        dna: SonicDNA,
    ) -> None:
        """Armazena DNA no cache. Overwrite se já existir."""
        if not settings.dna_cache_enabled:
            return

        cache_key = compute_cache_key(subject, prompt_version)

        # Overwrite: remove o antigo se houver
        stmt = select(CachedDNA).where(CachedDNA.cache_key == cache_key)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        cached = CachedDNA(
            cache_key=cache_key,
            subject=subject,
            prompt_version=prompt_version,
            model_used=model_used,
            dna_json=dna.model_dump(),
        )
        self.session.add(cached)
        await self.session.flush()
