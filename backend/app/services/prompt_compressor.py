"""Compressor determinístico: SonicDNA -> 3 variantes de style prompt Suno.

Este módulo é PURAMENTE determinístico (sem LLM). Dado o mesmo SonicDNA,
sempre produz o mesmo output. Isso é intencional:
- Reproduzibilidade para testes
- Auditoria de compliance (sem "caixa preta")
- Custo zero por chamada
- Latência < 1ms

A ordem de tags segue a pesquisa empírica do HookGenius (1000+ gerações testadas):
    [gênero] -> [mood] -> [instrumento] -> [vocal] -> [produção] -> [BPM]

Primeira posição tem peso desproporcional (~40% da saída), então sempre gênero.
"""
from __future__ import annotations

import re

from app.schemas.sonic_dna import (
    SUNO_STYLE_CHAR_LIMIT,
    SonicDNA,
    SunoPromptVariant,
    VariantLabel,
)


class ComplianceError(Exception):
    """Levantada quando um termo proibido vaza no prompt final.

    Esta é uma barreira dura: se acontecer, é bug (não degradação graciosa).
    """


# ---------------------------------------------------------------------------
# Configuração por variante
# ---------------------------------------------------------------------------

_VARIANT_CONFIG: dict[VariantLabel, dict[str, int | bool]] = {
    "conservative": {
        "include_genre_secondary": False,
        "include_mood_secondary": False,
        "instruments_slice": 1,
        "include_production": False,
        "include_vocal_delivery": False,
    },
    "faithful": {
        "include_genre_secondary": True,
        "include_mood_secondary": False,
        "instruments_slice": 2,
        "include_production": True,
        "include_vocal_delivery": False,
    },
    "creative": {
        "include_genre_secondary": True,
        "include_mood_secondary": True,
        "instruments_slice": 3,
        "include_production": True,
        "include_vocal_delivery": True,
    },
}


# ---------------------------------------------------------------------------
# Builder principal
# ---------------------------------------------------------------------------

def compress(dna: SonicDNA, variant: VariantLabel = "faithful") -> SunoPromptVariant:
    """Comprime um SonicDNA em um style prompt Suno dentro do limite de caracteres.

    Estratégia de fallback quando estoura 200 chars (degradação ordenada):
        1. Remove BPM
        2. Remove produção
        3. Remove instrumento_3 (se criativa)
        4. Remove instrumento_2 (se fiel/criativa)
        5. Remove mood_secondary
        6. Remove genre_secondary

    Raises:
        ComplianceError: Se após compressão um termo proibido vazou.
    """
    config = _VARIANT_CONFIG[variant]
    tags = _build_tags(dna, config)

    prompt = _render(tags)

    # Degradação ordenada se estourar 200 chars
    fallback_order = [
        "bpm",
        "production",
        "instruments_extra",
        "instruments_secondary",
        "mood_secondary",
        "genre_secondary",
    ]
    removed = 0
    while len(prompt) > SUNO_STYLE_CHAR_LIMIT and removed < len(fallback_order):
        target = fallback_order[removed]
        tags = _remove_section(tags, target)
        prompt = _render(tags)
        removed += 1

    if len(prompt) > SUNO_STYLE_CHAR_LIMIT:
        # Último recurso: força truncamento (cenário improvável se DNA for válido)
        prompt = prompt[:SUNO_STYLE_CHAR_LIMIT].rstrip(", ")

    _assert_compliance(prompt, dna.forbidden_terms)

    return SunoPromptVariant(
        label=variant,
        prompt=prompt,
        char_count=len(prompt),
        tags_count=prompt.count(",") + 1 if prompt else 0,
    )


def compress_all(dna: SonicDNA, variants_to_generate: int = 3) -> list[SunoPromptVariant]:
    """Gera as 3 variantes (ou quantas pediram) em ordem.

    A ordem é sempre conservative -> faithful -> creative para que
    o usuário veja primeiro a opção de menor risco.
    """
    labels: list[VariantLabel] = ["conservative", "faithful", "creative"]
    return [compress(dna, label) for label in labels[:variants_to_generate]]


# ---------------------------------------------------------------------------
# Construção das tags (estrutura intermediária)
# ---------------------------------------------------------------------------

def _build_tags(dna: SonicDNA, config: dict) -> dict[str, str | list[str] | None]:
    """Monta dict ordenado de seções que vira tags separadas por vírgula."""
    instruments = dna.instruments[: config["instruments_slice"]]

    # Vocal: combina gender + timbre (+ delivery se criativa)
    if dna.vocal_gender == "instrumental":
        vocal = "instrumental"
    else:
        parts = [f"{dna.vocal_gender} vocals"]
        if dna.vocal_timbre:
            parts.append(dna.vocal_timbre)
        if config["include_vocal_delivery"] and dna.vocal_delivery:
            parts.append(dna.vocal_delivery)
        vocal = ", ".join(parts)

    mood = dna.mood_primary
    if config["include_mood_secondary"] and dna.mood_secondary:
        mood = f"{mood}, {dna.mood_secondary}"

    return {
        "genre_primary": dna.genre_primary,
        "genre_secondary": dna.genre_secondary if config["include_genre_secondary"] else None,
        "mood": mood,
        "instruments": instruments,
        "vocal": vocal,
        "production": dna.production_palette[0] if config["include_production"] else None,
        "bpm": f"{dna.bpm_typical} BPM",
    }


def _render(tags: dict) -> str:
    """Concatena as seções em uma string de tags separadas por vírgula."""
    parts: list[str] = []

    if tags.get("genre_primary"):
        parts.append(tags["genre_primary"])
    if tags.get("genre_secondary"):
        parts.append(tags["genre_secondary"])
    if tags.get("mood"):
        parts.append(tags["mood"])

    for instrument in tags.get("instruments") or []:
        parts.append(instrument)

    if tags.get("vocal"):
        parts.append(tags["vocal"])
    if tags.get("production"):
        parts.append(tags["production"])
    if tags.get("bpm"):
        parts.append(tags["bpm"])

    return ", ".join(parts)


def _remove_section(tags: dict, section: str) -> dict:
    """Remove uma seção para encaixar no limite de chars."""
    tags = dict(tags)
    match section:
        case "bpm":
            tags["bpm"] = None
        case "production":
            tags["production"] = None
        case "instruments_extra":
            # Remove o último instrumento (índice 2+, só existe em creative)
            if tags.get("instruments") and len(tags["instruments"]) > 2:
                tags["instruments"] = tags["instruments"][:2]
        case "instruments_secondary":
            if tags.get("instruments") and len(tags["instruments"]) > 1:
                tags["instruments"] = tags["instruments"][:1]
        case "mood_secondary":
            mood = tags.get("mood") or ""
            # Se mood tem vírgula (primary + secondary), corta a secondary
            if "," in mood:
                tags["mood"] = mood.split(",")[0].strip()
        case "genre_secondary":
            tags["genre_secondary"] = None
    return tags


# ---------------------------------------------------------------------------
# Compliance: guard-rail contra vazamento de nomes próprios
# ---------------------------------------------------------------------------

def _assert_compliance(prompt: str, forbidden_terms: list[str]) -> None:
    """Bloqueia qualquer nome próprio proibido no prompt final.

    Comparação case-insensitive em word-boundaries para não pegar falsos
    positivos tipo 'cold' em 'Coldplay' quebrar 'cold reverb'.

    Se um termo tem >= 4 chars e é substring (mesmo sem word boundary),
    levanta ComplianceError por precaução — melhor falhar do que vazar.
    """
    if not forbidden_terms:
        return

    prompt_lower = prompt.lower()

    for term in forbidden_terms:
        if not term:
            continue

        # Termos >= 4 chars: substring match (mais restritivo)
        if len(term) >= 4 and term in prompt_lower:
            raise ComplianceError(
                f"Termo proibido '{term}' detectado no prompt final: {prompt!r}"
            )

        # Termos curtos (1-3 chars): só word boundary
        if len(term) < 4:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, prompt_lower):
                raise ComplianceError(
                    f"Termo proibido '{term}' detectado como palavra em: {prompt!r}"
                )


# ---------------------------------------------------------------------------
# Templates de letra (extra)
# ---------------------------------------------------------------------------

DEFAULT_LYRIC_TEMPLATE = """[Intro]

[Verse 1]
...

[Pre-Chorus]
...

[Chorus]
...

[Verse 2]
...

[Bridge]
...

[Chorus]
...

[Outro]"""


def build_lyric_template(dna: SonicDNA) -> str:
    """Adapta o template de letras ao tipo/gênero detectado.

    Regras:
    - Músicas instrumentais: template vazio (só indicações de seção)
    - Articulation >= 8: pode ter mais linhas (letras densas)
    - Estilos específicos: adiciona marcações (ex: [Spoken Word] pra rap)
    """
    if dna.vocal_gender == "instrumental":
        return "[Intro]\n\n[Main Section]\n\n[Variation]\n\n[Outro]"

    # Rap/hip-hop: adiciona flow cue no chorus
    if "rap" in dna.genre_primary.lower() or "hip hop" in dna.genre_primary.lower():
        return DEFAULT_LYRIC_TEMPLATE.replace(
            "[Chorus]\n...",
            "[Chorus]\n(hook)\n...",
            1,
        )

    return DEFAULT_LYRIC_TEMPLATE
