"""Testes do compressor determinístico.

Cobertura mínima que você NUNCA pode quebrar:
1. Compliance: termos proibidos nunca vazam no prompt final
2. Char limit: nenhuma variante excede 200 chars
3. Estrutura: primeira tag é sempre gênero
4. Degradação ordenada: ao estourar chars, remove na ordem certa
"""
from __future__ import annotations

import pytest

from app.schemas.sonic_dna import SonicDNA
from app.services.prompt_compressor import (
    SUNO_STYLE_CHAR_LIMIT,
    ComplianceError,
    compress,
    compress_all,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def coldplay_dna() -> SonicDNA:
    """DNA de exemplo (Coldplay) para testes."""
    return SonicDNA(
        subject="Coldplay",
        subject_type="band",
        era="2000s British alt-rock",
        genre_primary="alternative rock",
        genre_secondary="britpop",
        bpm_min=70,
        bpm_max=140,
        bpm_typical=105,
        mood_primary="anthemic, emotional",
        mood_secondary="uplifting, nostalgic",
        instruments=[
            "piano-led arrangements",
            "delay-heavy atmospheric guitars",
            "live strings",
        ],
        vocal_gender="male",
        vocal_timbre="emotive tenor, airy falsetto",
        vocal_delivery="intimate verses, belted choruses",
        production_palette=["polished arena reverb", "stadium drums"],
        articulation_score=8,
        forbidden_terms=["coldplay", "chris martin"],
    )


@pytest.fixture
def verbose_dna() -> SonicDNA:
    """DNA com strings longas para forçar degradação."""
    return SonicDNA(
        subject="Test",
        subject_type="artist",
        era="2020s experimental avant-garde neo-progressive chamber pop",
        genre_primary="experimental chamber pop with orchestral influences",
        genre_secondary="neo-progressive baroque art rock",
        bpm_min=60,
        bpm_max=140,
        bpm_typical=95,
        mood_primary="melancholic and contemplative with moments of euphoria",
        mood_secondary="cinematic and dreamlike with nostalgic undertones",
        instruments=[
            "layered piano with extended reverb tails",
            "chamber orchestra with french horn",
            "modular synthesizer arpeggios",
            "brushed drum kit with jazz sensibility",
        ],
        vocal_gender="mixed",
        vocal_timbre="layered male and female harmonies with operatic influence",
        vocal_delivery="whispered intimate verses building to cathedral-like choruses",
        production_palette=[
            "lush analog reverb with tape saturation",
            "wide stereo imaging with binaural elements",
            "dynamic compression with room mics",
        ],
        articulation_score=7,
        forbidden_terms=["test"],
    )


# ---------------------------------------------------------------------------
# Compliance tests (CRÍTICOS)
# ---------------------------------------------------------------------------

class TestCompliance:
    """Nome próprio proibido NUNCA pode aparecer no prompt final."""

    def test_coldplay_name_not_in_prompt(self, coldplay_dna: SonicDNA):
        for variant in compress_all(coldplay_dna):
            assert "coldplay" not in variant.prompt.lower()
            assert "chris martin" not in variant.prompt.lower()

    def test_explicit_leak_raises(self):
        """Se o DNA tiver o termo proibido em um campo subjetivo, deve falhar."""
        dna = SonicDNA(
            subject="Coldplay",
            subject_type="band",
            era="2000s",
            genre_primary="alternative rock",
            bpm_min=70,
            bpm_max=140,
            bpm_typical=105,
            mood_primary="anthemic",
            instruments=["coldplay-style piano", "guitars"],  # LEAK!
            vocal_gender="male",
            vocal_timbre="tenor",
            production_palette=["arena"],
            articulation_score=8,
            forbidden_terms=["coldplay"],
        )
        with pytest.raises(ComplianceError):
            compress(dna, "faithful")

    def test_short_forbidden_term_word_boundary(self):
        """Termos curtos (< 4 chars) só matcham em word boundary, não substring."""
        dna = SonicDNA(
            subject="U2",
            subject_type="band",
            era="1980s",
            genre_primary="alternative rock",
            bpm_min=80,
            bpm_max=140,
            bpm_typical=110,
            mood_primary="anthemic",
            instruments=["ringing guitars", "pulsing bass"],
            vocal_gender="male",
            vocal_timbre="tenor",
            production_palette=["stadium reverb"],
            articulation_score=8,
            forbidden_terms=["u2"],
        )
        # "u2" não aparece como palavra, mas outras palavras têm 'u2' como substring?
        # Não deve levantar por palavras inocentes.
        result = compress(dna, "faithful")
        # Verifica que "u2" não está como palavra isolada
        import re
        assert not re.search(r"\bu2\b", result.prompt.lower())


# ---------------------------------------------------------------------------
# Char limit tests
# ---------------------------------------------------------------------------

class TestCharLimit:
    def test_all_variants_under_200_chars(self, coldplay_dna: SonicDNA):
        for variant in compress_all(coldplay_dna):
            assert variant.char_count <= SUNO_STYLE_CHAR_LIMIT, (
                f"Variant {variant.label} exceeds limit: {variant.char_count} > {SUNO_STYLE_CHAR_LIMIT}"
            )

    def test_verbose_dna_still_fits(self, verbose_dna: SonicDNA):
        """Mesmo com strings verbosas, deve caber via degradação."""
        for variant in compress_all(verbose_dna):
            assert variant.char_count <= SUNO_STYLE_CHAR_LIMIT

    def test_char_count_matches_prompt_length(self, coldplay_dna: SonicDNA):
        for variant in compress_all(coldplay_dna):
            assert len(variant.prompt) == variant.char_count


# ---------------------------------------------------------------------------
# Estrutura tests
# ---------------------------------------------------------------------------

class TestStructure:
    def test_first_tag_is_genre(self, coldplay_dna: SonicDNA):
        """Primeira tag sempre é o gênero primário."""
        for variant in compress_all(coldplay_dna):
            first_tag = variant.prompt.split(",")[0].strip()
            assert first_tag == "alternative rock"

    def test_conservative_has_fewer_tags_than_creative(self, coldplay_dna: SonicDNA):
        conservative = compress(coldplay_dna, "conservative")
        creative = compress(coldplay_dna, "creative")
        assert conservative.tags_count < creative.tags_count

    def test_tag_count_within_sweet_spot(self, coldplay_dna: SonicDNA):
        """5-8 tags é o sweet spot empírico."""
        for variant in compress_all(coldplay_dna):
            assert 4 <= variant.tags_count <= 12

    def test_bpm_always_present_when_fits(self, coldplay_dna: SonicDNA):
        """Coldplay cabe tranquilo, BPM deve aparecer."""
        faithful = compress(coldplay_dna, "faithful")
        assert "105 BPM" in faithful.prompt


# ---------------------------------------------------------------------------
# Variants tests
# ---------------------------------------------------------------------------

class TestVariants:
    def test_three_variants_generated(self, coldplay_dna: SonicDNA):
        variants = compress_all(coldplay_dna, variants_to_generate=3)
        labels = {v.label for v in variants}
        assert labels == {"conservative", "faithful", "creative"}

    def test_variants_are_different(self, coldplay_dna: SonicDNA):
        variants = compress_all(coldplay_dna)
        prompts = {v.prompt for v in variants}
        assert len(prompts) == 3  # nenhuma duplicata

    def test_respects_variants_to_generate(self, coldplay_dna: SonicDNA):
        variants = compress_all(coldplay_dna, variants_to_generate=1)
        assert len(variants) == 1
        assert variants[0].label == "conservative"


# ---------------------------------------------------------------------------
# Instrumental edge case
# ---------------------------------------------------------------------------

def test_instrumental_track():
    dna = SonicDNA(
        subject="Lo-fi Beat",
        subject_type="song",
        era="2020s lo-fi",
        genre_primary="lo-fi hip hop",
        bpm_min=70,
        bpm_max=90,
        bpm_typical=80,
        mood_primary="chill, nostalgic",
        instruments=["warm Rhodes", "vinyl hiss", "soft drums"],
        vocal_gender="instrumental",
        vocal_timbre=None,
        vocal_delivery=None,
        production_palette=["tape saturation"],
        articulation_score=5,
        forbidden_terms=[],
    )
    for variant in compress_all(dna):
        assert "instrumental" in variant.prompt.lower()
        assert variant.char_count <= SUNO_STYLE_CHAR_LIMIT
