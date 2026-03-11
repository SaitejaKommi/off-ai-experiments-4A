"""Tests for language detection and query normalization."""

from off_ai.query_preprocessor import QueryPreprocessor


def test_detect_language_en():
    p = QueryPreprocessor()
    result = p.preprocess("low fat chocolates")
    assert result.language == "en"


def test_detect_language_fr():
    p = QueryPreprocessor()
    result = p.preprocess("chocolat sans sucre ajoute")
    assert result.language == "fr"


def test_normalize_fr_to_canonical_tokens():
    p = QueryPreprocessor()
    result = p.preprocess("chocolat sans sucre ajoute moins gras")
    assert "chocolate" in result.normalized_text
    assert "zero added sugar" in result.normalized_text
    assert "low fat" in result.normalized_text


def test_normalize_common_typos():
    p = QueryPreprocessor()
    result = p.preprocess("0 sugar choclates")
    assert "chocolates" in result.normalized_text


def test_normalize_french_low_sodium_phrase():
    p = QueryPreprocessor()
    result = p.preprocess("collation vegetalien faible en sodium")
    assert "snack" in result.normalized_text
    assert "vegan" in result.normalized_text
    assert "low sodium" in result.normalized_text
