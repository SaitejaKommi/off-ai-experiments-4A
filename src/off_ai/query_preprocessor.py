"""Lightweight language detection and EN/FR normalization."""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import requests


logger = logging.getLogger(__name__)


_FR_STRONG_HINTS = {
    # Common function/grammar words
    "sans", "avec", "moins", "sous",
    # Nutrients / food properties
    "sucre", "graisse", "gras", "proteine", "proteines", "fibres",
    "sodium", "sel",
    # Qualitative descriptors
    "faible", "faibles", "riche", "riches", "pauvre", "pauvres",
    # Dietary labels
    "vegetalien", "vegetarien", "vegetaliens", "vegetaliennes",
    "vegane", "veganes",
    # Categories
    "collation", "collations", "cereale", "cereales", "biscuits",
    "pates", "boisson", "boissons",
    # Other FR food words
    "huile", "palme", "chocolat", "biologique",
    "ajoute", "ajoutee", "ajoutes",
    "enfants", "montrez", "donnez", "donner", "encas",
    "sain", "sains", "saine", "saines",
    "regime", "adapte", "adaptes",
    "meilleur", "meilleure", "meilleurs", "meilleures",
    "yaourt", "yogourt",
    # Plural dietary forms
    "vegetarienne", "vegetariennes",
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
        # Common request framing
        "montrez-moi": "show me",
        "montrez moi": "show me",
        "montre-moi": "show me",
        "montre moi": "show me",
        "donnez-moi": "show me",
        "donnez moi": "show me",
        "donner": "show",

        # Common French superlatives
        "meilleur": "best",
        "meilleure": "best",
        "meilleurs": "best",
        "meilleures": "best",

        # Cereals/grains
        "cereales": "cereals",
        "cereale": "cereal",
        "muesli": "muesli",
        "chocolat": "chocolate",
        "collation": "snack",
        "collations": "snacks",
        "en-cas": "snacks",
        "encas": "snacks",
        "biscuit": "cookie",
        "biscuits": "cookies",
        "yaourt": "yogurt",
        "yogourt": "yogurt",
        "proteines": "protein",
        "proteine": "protein",
        "fibres": "fibre",
        "fibre": "fibre",
        "calorie": "calories",

        # Health preference
        "sain": "healthy",
        "saine": "healthy",
        "sains": "healthy",
        "saines": "healthy",
        "plus sain": "healthy",
        "plus saine": "healthy",
        "plus sains": "healthy",
        "plus saines": "healthy",
        
        # Palm oil
        "huile de palme": "palm oil",
        "sans huile de palme": "no palm oil",
        
        # Zero sugar variants
        "sans sucre": "zero sugar",
        "sans sucre ajoute": "zero added sugar",
        "sans sucre ajoutee": "zero added sugar",
        "sans sucres ajoutes": "zero added sugar",
        "sans sucre ajoutes": "zero added sugar",
        
        # Low fat variants (singular & plural)
        "faibles en gras": "low fat",
        "faible en gras": "low fat",
        "faibles en graisse": "low fat",
        "faible en graisse": "low fat",
        "moins de gras": "low fat",
        "moins gras": "low fat",
        "sous": "under",
        
        # Low sugar variants (singular & plural)
        "faibles en sucre": "low sugar",
        "faible en sucre": "low sugar",
        "pauvre en sucre": "low sugar",

        # Low sodium variants
        "faible en sodium": "low sodium",
        "faibles en sodium": "low sodium",
        "pauvre en sodium": "low sodium",
        "pauvres en sodium": "low sodium",
        "faible en sel": "low salt",
        "faibles en sel": "low salt",
        "regime pauvre en sodium": "low sodium diet",
        "adapte a un regime pauvre en sodium": "low sodium diet",
        "adaptes a un regime pauvre en sodium": "low sodium diet",
        "adaptes a une alimentation pauvre en sodium": "low sodium diet",
        "adapte a une alimentation pauvre en sodium": "low sodium diet",
        
        # High protein variants (singular & plural)
        "riches en proteines": "high protein",
        "riche en proteines": "high protein",
        "riches en proteine": "high protein",
        "riche en proteine": "high protein",
        
        # High fibre variants (singular & plural)
        "riches en fibres": "high fibre",
        "riche en fibres": "high fibre",
        "riches en fibre": "high fibre",
        "riche en fibre": "high fibre",
        
        # Dietary labels
        "vegetalien": "vegan",
        "vegetalienne": "vegan",
        "vegetaliens": "vegan",
        "vegetaliennes": "vegan",
        "vegane": "vegan",
        "veganes": "vegan",
        "vegetarien": "vegetarian",
        "vegetarienne": "vegetarian",
        "vegetariens": "vegetarian",
        "vegetariennes": "vegetarian",
        "biologique": "organic",
        "biologiques": "organic",
        "pour enfants": "for kids",
        "pour enfant": "for kids",
        "avec": "with",

        # Food categories (FR → EN canonical term for CATEGORY_KEYWORDS)
        "boisson": "drink",
        "boissons": "drinks",
        "pates": "pasta",
        "pate": "pasta",
        "riz": "rice",
        "legume": "vegetable",
        "legumes": "vegetables",
        "fruit": "fruit",
        "fruits": "fruits",
    }

    _TYPO_REPLACEMENTS: Dict[str, str] = {
        "choclates": "chocolates",
        "cerals": "cereals",
    }

    def __init__(self, translator: Optional[Callable[[str], Optional[str]]] = None) -> None:
        # Translator is optional. If not configured, deterministic rules remain the default behavior.
        self._translator = translator or self._build_default_translator()

    def preprocess(self, text: str) -> PreprocessResult:
        source_text = text.strip()
        lowered = source_text.lower()
        lang = self.detect_language(lowered)
        normalized = self.normalize(lowered, lang)

        # Optional FR -> EN translation path for better EN/FR parity on complex phrasing.
        if lang == "fr" and self._translator is not None:
            translated = self._translator(source_text)
            if translated:
                normalized = self.normalize(translated.lower().strip(), "en")

        return PreprocessResult(
            original_text=text,
            normalized_text=normalized,
            language=lang,
        )

    def _build_default_translator(self) -> Optional[Callable[[str], Optional[str]]]:
        provider = os.environ.get("OFF_TRANSLATION_PROVIDER", "").strip().lower()
        groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()

        if provider and provider != "groq":
            return None
        if not groq_api_key:
            return None

        model = os.environ.get("OFF_TRANSLATION_MODEL", "llama-3.1-8b-instant").strip()
        timeout_s = float(os.environ.get("OFF_TRANSLATION_TIMEOUT_S", "8"))
        return _GroqTranslator(api_key=groq_api_key, model=model, timeout_s=timeout_s)

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
            out = re.sub(r"\bplus de\b", "over", out)

        # Canonical punctuation spacing
        out = out.replace("-", " ")
        out = out.replace(" ,", ",")
        out = re.sub(r"\s+", " ", out).strip()
        return out


class _GroqTranslator:
    """Minimal translator wrapper over Groq OpenAI-compatible Chat Completions."""

    _API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout_s: float = 8.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s

    def __call__(self, text: str) -> Optional[str]:
        if not text:
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Translate user food-search queries from French to English. "
                        "Preserve meaning for nutrients, dietary labels, and categories. "
                        "Return only the translated query text."
                    ),
                },
                {"role": "user", "content": text},
            ],
        }

        try:
            response = requests.post(self._API_URL, headers=headers, json=payload, timeout=self._timeout_s)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"].strip()
            if not content:
                return None
            # Remove wrapping quotes some models occasionally add.
            return content.strip('"')
        except Exception as exc:  # pragma: no cover - network failures are environment-dependent
            logger.warning("FR translation via Groq failed; falling back to rule-based normalization: %s", exc)
            return None
