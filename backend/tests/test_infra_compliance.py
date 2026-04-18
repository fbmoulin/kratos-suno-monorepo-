"""Tests for infra.compliance.extract_forbidden_terms_from_hint."""
from __future__ import annotations
import pytest


class TestExtractForbiddenTerms:
    def test_empty_hint_returns_empty(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        assert extract_forbidden_terms_from_hint("", None) == []

    def test_respects_explicit_artist_to_avoid(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("", "Beatles")
        assert "beatles" in result

    def test_extracts_capitalized_words(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint(
            "this is a cover of Beatles by John Lennon", None
        )
        assert "beatles" in result
        assert "john" in result
        assert "lennon" in result
        # lowercase words not treated as proper names
        assert "cover" not in result

    def test_extracts_quoted_phrases(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint(
            'do "Let It Be" in jazz style', None
        )
        assert "let it be" in result

    def test_merges_hint_and_artist_to_avoid_dedup(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("cover of Beatles", "beatles")
        assert result.count("beatles") == 1

    def test_strips_short_common_words(self):
        """False-positive mitigation for 'Brazilian jazz'."""
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("Brazilian jazz", None)
        # 'brazilian' is a nationality, not an artist — skip common adjectives
        assert "brazilian" not in result

    def test_returns_sorted_unique_lowercase(self):
        from app.infra.compliance import extract_forbidden_terms_from_hint
        result = extract_forbidden_terms_from_hint("ZETA alpha Beta", None)
        assert result == sorted(set(r.lower() for r in result))
