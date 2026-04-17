"""Schemas Pydantic v2 para Sonic DNA e endpoints da API.

Estes schemas são o contrato entre o compressor determinístico (prompt_compressor.py)
e os geradores de DNA (via texto ou áudio). Qualquer mudança aqui requer atualização
coordenada em services/prompt_compressor.py.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Constantes (espelhadas em constants.py mas inline para evitar import circular)
# ---------------------------------------------------------------------------

SUNO_STYLE_CHAR_LIMIT = 200
VARIANT_LABELS = ("conservative", "faithful", "creative")
VariantLabel = Literal["conservative", "faithful", "creative"]


# ---------------------------------------------------------------------------
# Core: Sonic DNA (8 dimensões)
# ---------------------------------------------------------------------------

class SonicDNA(BaseModel):
    """Representação técnica da identidade sonora de um artista, banda ou música.

    Este é o IR (intermediate representation) da aplicação. O campo `subject` é
    apenas para logging/cache — NUNCA deve aparecer nos prompts Suno gerados.
    Todos os `forbidden_terms` são validados no compressor antes do output final.
    """

    # Identificação (interno)
    subject: str = Field(..., description="Input original (Coldplay, Bohemian Rhapsody, etc.)")
    subject_type: Literal["artist", "band", "song"]
    era: str = Field(..., description="Ex: '2000s British alt-rock'")

    # Gênero
    genre_primary: str = Field(..., description="Gênero dominante em lowercase")
    genre_secondary: str | None = None

    # Tempo
    bpm_min: int = Field(..., ge=40, le=240)
    bpm_max: int = Field(..., ge=40, le=240)
    bpm_typical: int = Field(..., ge=40, le=240)

    # Mood
    mood_primary: str = Field(..., description="1-2 moods separados por vírgula")
    mood_secondary: str | None = None

    # Instrumentação
    instruments: list[str] = Field(..., min_length=2, max_length=5)

    # Vocal
    vocal_gender: Literal["male", "female", "mixed", "instrumental"]
    vocal_timbre: str | None = None
    vocal_delivery: str | None = None

    # Produção
    production_palette: list[str] = Field(..., min_length=1, max_length=4)

    # Articulation
    articulation_score: int = Field(..., ge=1, le=10)

    # Compliance
    forbidden_terms: list[str] = Field(
        default_factory=list,
        description="Nomes próprios que nunca podem aparecer no prompt final",
    )

    # --- Validadores ---

    @model_validator(mode="after")
    def validate_bpm_range(self) -> SonicDNA:
        if self.bpm_min > self.bpm_max:
            raise ValueError(f"bpm_min ({self.bpm_min}) > bpm_max ({self.bpm_max})")
        if not (self.bpm_min <= self.bpm_typical <= self.bpm_max):
            raise ValueError(
                f"bpm_typical ({self.bpm_typical}) deve estar entre bpm_min ({self.bpm_min}) "
                f"e bpm_max ({self.bpm_max})"
            )
        return self

    @field_validator("forbidden_terms")
    @classmethod
    def normalize_forbidden(cls, v: list[str]) -> list[str]:
        """Lowercase e dedup para comparação case-insensitive."""
        return sorted({t.lower().strip() for t in v if t.strip()})

    @field_validator("instruments", "production_palette")
    @classmethod
    def strip_items(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v if item.strip()]

    # --- Derivados ---

    @property
    def recommended_lyric_density(self) -> Literal["sparse", "moderate", "dense"]:
        """Derivado do articulation_score: letras atmosféricas < 4, densas >= 8."""
        if self.articulation_score <= 4:
            return "sparse"
        if self.articulation_score <= 7:
            return "moderate"
        return "dense"


# ---------------------------------------------------------------------------
# Variantes de prompt (saída do compressor)
# ---------------------------------------------------------------------------

class SunoPromptVariant(BaseModel):
    """Uma das 3 variantes comprimidas (≤200 chars) do style prompt."""

    label: VariantLabel
    prompt: str = Field(..., max_length=SUNO_STYLE_CHAR_LIMIT)
    char_count: int = Field(..., le=SUNO_STYLE_CHAR_LIMIT)
    tags_count: int = Field(..., ge=1, le=15)

    @model_validator(mode="after")
    def validate_counts(self) -> SunoPromptVariant:
        if len(self.prompt) != self.char_count:
            raise ValueError(
                f"char_count inconsistente: declarado {self.char_count}, real {len(self.prompt)}"
            )
        return self


# ---------------------------------------------------------------------------
# API: Request/Response
# ---------------------------------------------------------------------------

class GenerateFromTextRequest(BaseModel):
    """POST /api/v1/generate/text — input textual (nome de artista/banda/música)."""

    subject: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nome do artista, banda ou música. Ex: 'Coldplay', 'Bohemian Rhapsody'",
    )
    variants_to_generate: int = Field(default=3, ge=1, le=3)
    language_hint: str | None = Field(
        default=None,
        description="Dica para letra, ex: 'portuguese', 'english'. Não afeta o style prompt.",
    )


class GenerateFromAudioRequest(BaseModel):
    """Metadata para POST /api/v1/generate/audio (arquivo vem em multipart)."""

    variants_to_generate: int = Field(default=3, ge=1, le=3)
    user_hint: str | None = Field(
        default=None,
        max_length=200,
        description="Opcional: usuário pode dar uma pista do que é (ex: 'sertanejo universitário')",
    )


class GenerateResponse(BaseModel):
    """Resposta unificada de /generate/text e /generate/audio."""

    subject: str
    sonic_dna: SonicDNA
    variants: list[SunoPromptVariant]
    lyric_template: str = Field(..., description="Template de letras com metatags do Suno")
    disclaimer: str = Field(
        default=(
            "Esta ferramenta produz descritores técnicos de estilo musical para uso com Suno AI. "
            "Os prompts gerados são originais e não reproduzem obras protegidas por direitos autorais."
        )
    )


# ---------------------------------------------------------------------------
# Erros estruturados
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None
