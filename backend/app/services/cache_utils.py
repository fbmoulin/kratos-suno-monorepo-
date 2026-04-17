"""Cache utilities — funções puras sem deps externas.

Separado de dna_cache.py (que depende de SQLAlchemy) para permitir testes
unitários rápidos das funções de normalização/hashing.
"""
from __future__ import annotations

import hashlib


def normalize_subject(subject: str) -> str:
    """Normaliza para chave de cache: lowercase, trim, espaço único."""
    return " ".join(subject.lower().strip().split())


def compute_cache_key(subject: str, prompt_version: str) -> str:
    """SHA256 de subject normalizado + prompt_version.

    Mudar a versão do prompt invalida o cache automaticamente — cada combinação
    (subject, prompt_version) tem chave única.
    """
    normalized = f"{normalize_subject(subject)}|{prompt_version}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
