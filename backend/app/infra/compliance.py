"""Compliance — heuristic extraction of forbidden_terms from free-text hints."""
from __future__ import annotations
import re

# Common adjectives/nationalities/generic words that accidentally capitalize
_COMMON_FALSE_POSITIVES = {
    "brazilian", "american", "british", "french", "german", "italian",
    "japanese", "portuguese", "spanish", "english", "chinese", "korean",
    "indie", "alternative", "electronic", "acoustic", "classical",
    "jazz", "rock", "pop", "folk", "metal", "rap", "hip", "hop",
    "old", "new", "young", "modern", "ancient",
}


def extract_forbidden_terms_from_hint(
    hint: str | None,
    artist_to_avoid: str | None,
) -> list[str]:
    """Return lowercase sorted list of likely proper-name tokens.

    Heuristic-only (no NER library). Covers:
    1. Explicit artist_to_avoid field
    2. Quoted phrases in hint: "Bohemian Rhapsody"
    3. Capitalized words in hint (filtering common false positives)
    """
    terms: set[str] = set()

    if artist_to_avoid:
        terms.add(artist_to_avoid.strip().lower())

    if hint:
        # 1. quoted phrases
        for match in re.findall(r'["\u201c]([^"\u201d]{2,40})["\u201d]', hint):
            terms.add(match.strip().lower())

        # 2. capitalized tokens (length >= 3 to avoid "A", "I")
        for token in re.findall(r"\b[A-Z][a-z]{2,}\b", hint):
            lower = token.lower()
            if lower not in _COMMON_FALSE_POSITIVES:
                terms.add(lower)

    # Drop empty strings and sort
    return sorted(t for t in terms if t)
