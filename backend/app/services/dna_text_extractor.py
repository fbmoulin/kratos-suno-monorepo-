"""Extrator de Sonic DNA a partir de texto (nome de artista/banda/música).

Usa Claude (Haiku para custo, Sonnet para qualidade) com system prompt
versionado em prompts/versions/. O modelo é escolhido via ModelRoleConfig
no config.py.

Fluxo:
    1. Carrega system prompt da versão ativa
    2. Envia subject como user message
    3. Parse JSON response com validação Pydantic
    4. Injeta subject original (para cache/audit)
    5. Retorna SonicDNA validado
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from app.config import settings
from app.schemas.sonic_dna import SonicDNA


class DNAExtractionError(Exception):
    """Falha ao extrair DNA — JSON inválido, resposta vazia, etc."""


class TextDNAExtractor:
    """Extrai Sonic DNA de um subject textual via Claude API."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ):
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.dna_extractor_model
        self.prompt_version = prompt_version or settings.active_prompt_version
        self._system_prompt = self._load_system_prompt(self.prompt_version)

    # -----------------------------------------------------------------------
    # API pública
    # -----------------------------------------------------------------------

    async def extract(self, subject: str) -> SonicDNA:
        """Extrai o Sonic DNA do subject informado."""
        user_message = f"Subject: {subject}"

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.3,  # baixo: queremos extração factual, não criatividade
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = self._extract_text(response)
        data = self._parse_json(raw)

        # Injeta subject original (o prompt instrui o LLM a NÃO incluir no JSON)
        data["subject"] = subject

        # Normaliza bpm_range -> bpm_min/max
        if "bpm_range" in data and isinstance(data["bpm_range"], list) and len(data["bpm_range"]) == 2:
            data["bpm_min"] = data["bpm_range"][0]
            data["bpm_max"] = data["bpm_range"][1]
            data["bpm_typical"] = data.get("bpm_typical", (data["bpm_min"] + data["bpm_max"]) // 2)
            del data["bpm_range"]

        try:
            return SonicDNA(**data)
        except Exception as exc:
            raise DNAExtractionError(
                f"JSON retornado não valida contra schema SonicDNA: {exc}\nRaw: {data}"
            ) from exc

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _load_system_prompt(version: str) -> str:
        """Carrega o system prompt da versão ativa.

        Versões ficam em app/prompts/versions/{version}.md e são versionadas
        no git. O prompt_lab permite rodar A/B entre versões.
        """
        base = Path(__file__).parent.parent / "prompts" / "versions"
        path = base / f"{version}.md"
        if not path.exists():
            raise FileNotFoundError(
                f"System prompt '{version}' não encontrado em {path}. "
                f"Verifique settings.active_prompt_version."
            )
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        """Extrai texto de resposta da API Anthropic."""
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        raise DNAExtractionError("Resposta da API não contém bloco de texto")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Parse JSON com fallbacks para markdown fences e texto extra."""
        # Remove markdown code fences se presentes
        raw = raw.strip()
        if raw.startswith("```"):
            # Remove primeira e última linha de fence
            lines = raw.split("\n")
            if len(lines) > 2:
                raw = "\n".join(lines[1:-1])

        # Tenta parse direto
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fallback: extrai primeiro objeto JSON da string
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise DNAExtractionError(f"Nenhum JSON encontrado na resposta: {raw[:200]}")

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise DNAExtractionError(
                f"JSON malformado na resposta: {exc}\nRaw: {raw[:500]}"
            ) from exc
