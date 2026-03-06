"""
query_preprocessor.py – Lightweight AI-style query preprocessing

Stages:
1) language detection (EN/FR)
2) normalization to canonical tokens used by IntentParser
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict


_FR_STRONG_HINTS = {
    "sans", "avec", "moins", "sucre", "graisse", "gras", "proteine",
    "proteines", "vegetalien", "vegetarien", "huile", "palme", "chocolat",
    "faible", "riche", "biologique", "ajoute", "ajoutee", "ajoutes",
    "cereale", "cereales",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@dataclass
class PreprocessResult:
    original_text: str
    normalized_text: str
    language: str


class QueryPreprocessor:
    """Detect query language and normalize EN/FR phrases to canonical tokens."""

    _FR_REPLACEMENTS: Dict[str, str] = {
        "cereales": "cereals",
        "cereale": "cereal",
        "muesli": "muesli",
        "chocolat": "chocolate",
        "huile de palme": "palm oil",
        "sans huile de palme": "no palm oil",
        "sans sucre": "zero sugar",
        "sans sucre ajoute": "zero added sugar",
        "sans sucre ajoutee": "zero added sugar",
        "sans sucres ajoutes": "zero added sugar",
        "sans sucre ajoutes": "zero added sugar",
        "faible en gras": "low fat",
        "moins de gras": "low fat",
        "moins gras": "low fat",
        "faible en sucre": "low sugar",
        "riche en proteines": "high protein",
        "riche en fibres": "high fibre",
        "vegetalien": "vegan",
        "vegetarien": "vegetarian",
        "biologique": "organic",
    }

    _TYPO_REPLACEMENTS: Dict[str, str] = {
        "choclates": "chocolates",
        "cerals": "cereals",
    }

    def preprocess(self, text: str) -> PreprocessResult:
        lowered = text.lower().strip()
        lang = self.detect_language(lowered)
        normalized = self.normalize(lowered, lang)
        return PreprocessResult(
            original_text=text,
            normalized_text=normalized,
            language=lang,
        )

    def detect_language(self, text: str) -> str:
        ascii_text = _strip_accents(text.lower())
        tokens = set(re.findall(r"[a-zA-Z]+", ascii_text))
        fr_score = len(tokens.intersection(_FR_STRONG_HINTS))
        has_french_accent = ascii_text != text.lower()
        if fr_score >= 2 or has_french_accent:
            return "fr"
        return "en"

    def normalize(self, text: str, language: str) -> str:
        out = _strip_accents(text.lower())
        out = re.sub(r"\s+", " ", out).strip()

        # Common typo cleanup first
        for source, target in self._TYPO_REPLACEMENTS.items():
            out = re.sub(rf"\b{re.escape(source)}\b", target, out)

        # French → canonical English tokens
        if language == "fr":
            # Longer phrases first to avoid partial overwrite
            for source in sorted(self._FR_REPLACEMENTS.keys(), key=len, reverse=True):
                target = self._FR_REPLACEMENTS[source]
                out = re.sub(rf"\b{re.escape(source)}\b", target, out)

            # Numeric French patterns
            out = re.sub(r"\bmoins de\b", "under", out)
            out = re.sub(r"\bau moins\b", "at least", out)

        # Canonical punctuation spacing
        out = out.replace(" ,", ",")
        out = re.sub(r"\s+", " ", out).strip()
        return out
