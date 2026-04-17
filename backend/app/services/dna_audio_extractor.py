"""Extrator de Sonic DNA a partir de arquivo de áudio.

Arquitetura híbrida:
    1. librosa mede BPM, key, RMS, brightness (deterministico, preciso)
    2. matplotlib gera espectrograma como imagem PNG
    3. Claude Sonnet recebe os números + espectrograma + hint do usuário
       e preenche as dimensões subjetivas (mood, timbre vocal, produção)
    4. Resultado combinado vira SonicDNA validado

Vantagem sobre Gemini-only: BPM preciso (±1%), Key com confidence
mensurável, custo controlado.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import IO

import anthropic

from app.config import settings
from app.schemas.sonic_dna import SonicDNA
from app.services.audio_analyzer import (
    AudioFeatureExtractor,
    AudioFeatures,
    generate_spectrogram_png,
)
from app.services.dna_text_extractor import DNAExtractionError


# ---------------------------------------------------------------------------
# System prompt para análise de áudio
# ---------------------------------------------------------------------------

AUDIO_DNA_SYSTEM_PROMPT = """Você é um analista musicólogo especializado em extrair a identidade sonora técnica de faixas musicais a partir de dados objetivos medidos e análise visual de espectrograma.

Você receberá:
1. Métricas objetivas medidas com librosa (BPM, key, energia, brilho espectral)
2. Um espectrograma Mel da faixa (imagem) para análise visual complementar
3. Opcionalmente, uma dica do usuário sobre o tipo de música

Sua tarefa é retornar APENAS um JSON válido com o schema SonicDNA abaixo.

REGRAS CRÍTICAS:
- Use EXATAMENTE o BPM e key fornecidos (não invente nem arredonde)
- Derive mood, instrumentação, vocal e produção da sua análise do espectrograma + contexto
- NÃO tente adivinhar o nome do artista — você NÃO TEM essa informação
- NÃO inclua nomes próprios de artistas, bandas ou músicas no JSON
- forbidden_terms deve ser [] (não há nome próprio conhecido neste fluxo)

SCHEMA:
{
  "subject_type": "song",
  "era": "string curta descrevendo época/cena estimada",
  "genre_primary": "gênero dominante (lowercase)",
  "genre_secondary": "subgênero ou null",
  "bpm_min": int,
  "bpm_max": int,
  "bpm_typical": int (use o BPM medido exato),
  "mood_primary": "1-2 moods separados por vírgula",
  "mood_secondary": "1-2 moods complementares ou null",
  "instruments": ["2-4 instrumentos identificados no espectrograma"],
  "vocal_gender": "male|female|mixed|instrumental",
  "vocal_timbre": "timbre e registro vocal ou null se instrumental",
  "vocal_delivery": "entrega performática ou null",
  "production_palette": ["2-3 descritores de mix/produção"],
  "articulation_score": int (1-10),
  "forbidden_terms": []
}

Se a faixa é instrumental (vocal não audível no espectrograma), use:
  vocal_gender: "instrumental"
  vocal_timbre: null
  vocal_delivery: null

Retorne APENAS o JSON, sem markdown, sem comentários."""


# ---------------------------------------------------------------------------
# Serviço principal
# ---------------------------------------------------------------------------

class AudioDNAExtractor:
    """Extrai Sonic DNA de um arquivo de áudio combinando librosa + Claude."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        model: str | None = None,
    ):
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        # Áudio precisa de vision + interpretação nuançada -> Sonnet (não Haiku)
        self.model = model or settings.audio_dna_model
        self.audio_extractor = AudioFeatureExtractor()

    # -----------------------------------------------------------------------

    async def extract(
        self,
        audio_source: str | Path | IO[bytes],
        user_hint: str | None = None,
    ) -> tuple[SonicDNA, AudioFeatures]:
        """Extrai DNA e retorna também as features para exibição ao usuário."""

        # 1. Análise determinística (librosa)
        features = self.audio_extractor.extract(audio_source)

        # 2. Espectrograma (imagem)
        # Rewind se é file-like
        if hasattr(audio_source, "seek"):
            audio_source.seek(0)
        spectrogram_bytes = generate_spectrogram_png(audio_source)
        spectrogram_b64 = base64.b64encode(spectrogram_bytes).decode()

        # 3. Prompt user
        user_text = self._build_user_prompt(features, user_hint)

        # 4. Claude Sonnet (vision + text)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.3,
            system=AUDIO_DNA_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": spectrogram_b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        )

        # 5. Parse resposta
        raw = self._extract_text(response)
        data = self._parse_json(raw)

        # 6. Injeta dados objetivos medidos (override qualquer invenção do LLM)
        data["subject"] = f"audio:{features.duration_seconds:.1f}s"
        data["bpm_typical"] = int(round(features.bpm))
        # Mantém range do LLM mas força typical estar dentro
        bpm_min = data.get("bpm_min", int(features.bpm * 0.85))
        bpm_max = data.get("bpm_max", int(features.bpm * 1.15))
        data["bpm_min"] = min(bpm_min, data["bpm_typical"])
        data["bpm_max"] = max(bpm_max, data["bpm_typical"])

        # Sem forbidden_terms neste fluxo (não há nome próprio)
        data["forbidden_terms"] = []

        try:
            dna = SonicDNA(**data)
            return dna, features
        except Exception as exc:
            raise DNAExtractionError(
                f"JSON não valida contra SonicDNA: {exc}\nRaw: {data}"
            ) from exc

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(features: AudioFeatures, user_hint: str | None) -> str:
        hint_block = (
            f"\n\nHINT do usuário: {user_hint}" if user_hint else ""
        )
        return (
            f"Analise esta faixa musical.\n\n"
            f"Métricas medidas (librosa):\n{features.to_prompt_context()}"
            f"{hint_block}\n\n"
            f"Use o BPM e key exatos. Preencha os campos subjetivos (mood, instrumentos, "
            f"vocal, produção) com base no espectrograma e contexto."
        )

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
        raise DNAExtractionError("Resposta da API não contém texto")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            if len(lines) > 2:
                raw = "\n".join(lines[1:-1])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise DNAExtractionError(f"Nenhum JSON encontrado: {raw[:200]}")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise DNAExtractionError(f"JSON malformado: {exc}") from exc
