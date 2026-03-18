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


def test_detect_language_fr_meilleur_yaourt():
    p = QueryPreprocessor()
    result = p.preprocess("meilleur yaourt")
    assert result.language == "fr"
    assert "best" in result.normalized_text
    assert "yogurt" in result.normalized_text


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


def test_normalize_full_french_snack_query_to_canonical_tokens():
    p = QueryPreprocessor()
    result = p.preprocess("Montrez-moi des en-cas sains, adaptes a un regime pauvre en sodium et vegetaliens")
    assert result.language == "fr"
    assert "show me" in result.normalized_text
    assert "snacks" in result.normalized_text
    assert "healthy" in result.normalized_text
    assert "low sodium diet" in result.normalized_text
    assert "vegan" in result.normalized_text


def test_normalize_french_proteines_to_protein_token():
    p = QueryPreprocessor(translator=lambda _text: None)
    result = p.preprocess("au moins 7g de proteines")
    assert "at least" in result.normalized_text
    assert "protein" in result.normalized_text


def test_normalize_french_moins_de_calories_phrase():
    p = QueryPreprocessor(translator=lambda _text: None)
    result = p.preprocess("moins de 390 calories et au moins 7g de proteines")
    assert "under 390 calories" in result.normalized_text
    assert "at least 7g" in result.normalized_text
    assert "protein" in result.normalized_text


def test_normalize_french_sous_calories_phrase():
    p = QueryPreprocessor(translator=lambda _text: None)
    normalized = p.normalize("sous 300 calories", "fr")
    assert "under 300 calories" in normalized


def test_preprocess_uses_translator_for_french_when_available():
    calls = []

    def fake_translator(text: str):
        calls.append(text)
        return "best yogurt"

    p = QueryPreprocessor(translator=fake_translator)
    result = p.preprocess("meilleur yaourt")

    assert result.language == "fr"
    assert result.normalized_text == "best yogurt"
    assert calls == ["meilleur yaourt"]


def test_preprocess_does_not_call_translator_for_english():
    calls = []

    def fake_translator(text: str):
        calls.append(text)
        return "ignored"

    p = QueryPreprocessor(translator=fake_translator)
    result = p.preprocess("best yogurt")

    assert result.language == "en"
    assert result.normalized_text == "best yogurt"
    assert calls == []


def test_preprocess_falls_back_to_rule_based_when_translator_returns_none():
    p = QueryPreprocessor(translator=lambda _text: None)
    result = p.preprocess("meilleur yaourt")

    assert result.language == "fr"
    assert result.normalized_text == "best yogurt"
