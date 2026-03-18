"""Bilingual (EN/FR) query consistency tests.

Each test pair verifies that an English query and its French equivalent
produce the same FoodQuery structure after preprocessing and parsing.

The tests validate:
- identical category detection
- identical dietary tag extraction
- identical nutrient constraint nutrients and operators
- matching constraint values (where explicitly stated in both queries)
"""

from __future__ import annotations

import pytest

from off_ai.intent_parser import FoodQuery, IntentParser
from off_ai.query_preprocessor import QueryPreprocessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def parser() -> IntentParser:
    return IntentParser()


@pytest.fixture
def preprocessor() -> QueryPreprocessor:
    # Deterministic rules only — no LLM dependency in unit tests.
    return QueryPreprocessor(translator=None)


def _parse_en(parser: IntentParser, query: str) -> FoodQuery:
    """Parse a raw English query (no preprocessing needed for pure EN)."""
    return parser.parse(query)


def _parse_fr(preprocessor: QueryPreprocessor, parser: IntentParser, query: str) -> FoodQuery:
    """Preprocess a French query then parse the normalised text."""
    pre = preprocessor.preprocess(query)
    q = parser.parse(pre.normalized_text)
    q.detected_language = pre.language
    return q


def _nutrient_set(q: FoodQuery) -> set:
    return {c.nutrient for c in q.nutrient_constraints}


def _operators_for(q: FoodQuery, nutrient: str) -> set:
    return {c.operator for c in q.nutrient_constraints if c.nutrient == nutrient}


def _value_for(q: FoodQuery, nutrient: str, operator: str) -> float | None:
    for c in q.nutrient_constraints:
        if c.nutrient == nutrient and c.operator == operator:
            return c.value
    return None


# ===========================================================================
# Pair 1 — High-protein vegan snacks under 300 calories
# ===========================================================================

class TestHighProteinVeganSnacks:
    """Core bilingual parity test: most common search intent."""

    EN = "high protein vegan snacks under 300 calories"
    FR = "collations veganes riches en proteines sous 300 calories"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "snacks"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "snacks"

    def test_en_vegan_tag(self, parser):
        assert "vegan" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_vegan_tag(self, preprocessor, parser):
        assert "vegan" in _parse_fr(preprocessor, parser, self.FR).dietary_tags

    def test_en_protein_constraint_present(self, parser):
        q = _parse_en(parser, self.EN)
        assert "proteins_100g" in _nutrient_set(q)
        assert ">=" in _operators_for(q, "proteins_100g")

    def test_fr_protein_constraint_present(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "proteins_100g" in _nutrient_set(q)
        assert ">=" in _operators_for(q, "proteins_100g")

    def test_en_calorie_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert _value_for(q, "energy_kcal_100g", "<=") == 300.0

    def test_fr_calorie_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert _value_for(q, "energy_kcal_100g", "<=") == 300.0


# ===========================================================================
# Pair 2 — Low-sodium cereals
# ===========================================================================

class TestLowSodiumCereal:
    EN = "low sodium cereal"
    FR = "cereales faibles en sodium"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "cereals"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "cereals"

    def test_en_sodium_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert "sodium_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sodium_100g")

    def test_fr_sodium_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "sodium_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sodium_100g")


# ===========================================================================
# Pair 3 — Gluten-free cookies
# ===========================================================================

class TestGlutenFreeCookies:
    EN = "gluten free cookies"
    FR = "biscuits sans gluten"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "cookies"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "cookies"

    def test_en_gluten_free_tag(self, parser):
        assert "gluten-free" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_gluten_free_tag(self, preprocessor, parser):
        assert "gluten-free" in _parse_fr(preprocessor, parser, self.FR).dietary_tags


# ===========================================================================
# Pair 4 — Organic yogurt
# ===========================================================================

class TestOrganicYogurt:
    EN = "organic yogurt"
    FR = "yogourt biologique"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "dairy"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "dairy"

    def test_en_organic_tag(self, parser):
        assert "organic" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_organic_tag(self, preprocessor, parser):
        assert "organic" in _parse_fr(preprocessor, parser, self.FR).dietary_tags


# ===========================================================================
# Pair 5 — Low-sugar snacks
# ===========================================================================

class TestLowSugarSnacks:
    EN = "low sugar snacks"
    FR = "collations faibles en sucre"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "snacks"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "snacks"

    def test_en_sugar_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert "sugars_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sugars_100g")

    def test_fr_sugar_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "sugars_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sugars_100g")


# ===========================================================================
# Pair 6 — High-fibre cereals
# ===========================================================================

class TestHighFibreCereals:
    EN = "high fibre cereal"
    FR = "cereales riches en fibres"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "cereals"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "cereals"

    def test_en_fibre_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert "fiber_100g" in _nutrient_set(q)
        assert ">=" in _operators_for(q, "fiber_100g")

    def test_fr_fibre_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "fiber_100g" in _nutrient_set(q)
        assert ">=" in _operators_for(q, "fiber_100g")


# ===========================================================================
# Pair 7 — Vegan snacks (no numeric constraint)
# ===========================================================================

class TestVeganSnacksSimple:
    EN = "vegan snacks"
    FR = "collations vegetaliennes"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "snacks"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "snacks"

    def test_en_vegan_tag(self, parser):
        assert "vegan" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_vegan_tag(self, preprocessor, parser):
        assert "vegan" in _parse_fr(preprocessor, parser, self.FR).dietary_tags

    def test_no_numeric_constraints_en(self, parser):
        assert _parse_en(parser, self.EN).nutrient_constraints == []

    def test_no_numeric_constraints_fr(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).nutrient_constraints == []


# ===========================================================================
# Pair 8 — Low-fat snacks
# ===========================================================================

class TestLowFatSnacks:
    EN = "low fat snacks"
    FR = "collations faibles en gras"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "snacks"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "snacks"

    def test_en_fat_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert "fat_100g" in _nutrient_set(q)

    def test_fr_fat_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "fat_100g" in _nutrient_set(q)


# ===========================================================================
# Pair 9 — No palm oil cereals
# ===========================================================================

class TestNoPalmOilCereal:
    EN = "cereal without palm oil"
    FR = "cereales sans huile de palme"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "cereals"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "cereals"

    def test_en_palm_oil_excluded(self, parser):
        q = _parse_en(parser, self.EN)
        assert "palm oil" in q.excluded_ingredients

    def test_fr_palm_oil_excluded(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "palm oil" in q.excluded_ingredients


# ===========================================================================
# Pair 10 — Vegetarian pasta under 400 calories
# ===========================================================================

class TestVegetarianPasta:
    EN = "vegetarian pasta under 400 calories"
    FR = "pates vegetariennes sous 400 calories"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "pastas"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "pastas"

    def test_en_vegetarian_tag(self, parser):
        assert "vegetarian" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_vegetarian_tag(self, preprocessor, parser):
        assert "vegetarian" in _parse_fr(preprocessor, parser, self.FR).dietary_tags

    def test_en_calorie_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert _value_for(q, "energy_kcal_100g", "<=") == 400.0

    def test_fr_calorie_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert _value_for(q, "energy_kcal_100g", "<=") == 400.0


# ===========================================================================
# Pair 11 — Dairy-free chocolate
# ===========================================================================

class TestDairyFreeChocolate:
    EN = "dairy free chocolate"
    FR = "chocolat sans lait"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "chocolates"

    def test_fr_category(self, preprocessor, parser):
        assert _parse_fr(preprocessor, parser, self.FR).category == "chocolates"

    def test_en_dairy_free_tag(self, parser):
        assert "dairy-free" in _parse_en(parser, self.EN).dietary_tags

    def test_fr_dairy_free_tag(self, preprocessor, parser):
        assert "dairy-free" in _parse_fr(preprocessor, parser, self.FR).dietary_tags


# ===========================================================================
# Pair 12 — Low-sodium diet snack bars (compound qualifier)
# ===========================================================================

class TestLowSodiumDietSnackBars:
    EN = "snack bars suitable for a low sodium diet"
    FR = "barres de collation adaptes a un regime pauvre en sodium"

    def test_en_category(self, parser):
        assert _parse_en(parser, self.EN).category == "snack-bars"

    def test_fr_sodium_constraint(self, preprocessor, parser):
        q = _parse_fr(preprocessor, parser, self.FR)
        assert "sodium_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sodium_100g")

    def test_en_sodium_constraint(self, parser):
        q = _parse_en(parser, self.EN)
        assert "sodium_100g" in _nutrient_set(q)
        assert "<=" in _operators_for(q, "sodium_100g")


# ===========================================================================
# Preprocessing language-detection smoke tests
# ===========================================================================

class TestLanguageDetection:
    def test_en_query_detected_as_english(self, preprocessor):
        pre = preprocessor.preprocess("high protein vegan snacks under 300 calories")
        assert pre.language == "en"

    def test_fr_query_detected_as_french_via_hints(self, preprocessor):
        pre = preprocessor.preprocess("collations veganes riches en proteines sous 300 calories")
        assert pre.language == "fr"

    def test_fr_accented_query_detected_as_french(self, preprocessor):
        pre = preprocessor.preprocess("collations véganes riches en protéines")
        assert pre.language == "fr"

    def test_fr_avec_hint_triggers_french(self, preprocessor):
        pre = preprocessor.preprocess("snacks avec proteines")
        assert pre.language == "fr"


# ===========================================================================
# Normalisation accuracy tests
# ===========================================================================

class TestFRNormalisation:
    def test_veganes_normalised_to_vegan(self, preprocessor):
        pre = preprocessor.preprocess("collations veganes")
        assert "vegan" in pre.normalized_text

    def test_riches_en_proteines_normalised(self, preprocessor):
        pre = preprocessor.preprocess("riches en proteines")
        assert "high protein" in pre.normalized_text

    def test_sous_normalised_to_under(self, preprocessor):
        # Two FR hints needed for detection: cereales + sous
        pre = preprocessor.preprocess("cereales sous 300 calories")
        assert "under" in pre.normalized_text

    def test_sans_gluten_normalised(self, preprocessor):
        pre = preprocessor.preprocess("biscuits sans gluten")
        assert "gluten" in pre.normalized_text

    def test_faibles_en_gras_normalised(self, preprocessor):
        pre = preprocessor.preprocess("collation faibles en gras")
        assert "low fat" in pre.normalized_text

    def test_pates_normalised_to_pasta(self, preprocessor):
        pre = preprocessor.preprocess("pates vegetariennes")
        assert "pasta" in pre.normalized_text


class TestCanonicalFoodQueryParity:
    def test_en_fr_queries_produce_identical_canonical_intent(self, preprocessor, parser):
        en = "high protein vegan snacks under 300 calories"
        fr = "collations veganes riches en proteines avec moins de 300 calories"

        en_q = parser.parse(preprocessor.preprocess(en).normalized_text)
        fr_q = parser.parse(preprocessor.preprocess(fr).normalized_text)

        def canonical(q: FoodQuery) -> dict:
            nutrients = sorted(
                [(c.nutrient, c.operator, round(c.value, 3)) for c in q.nutrient_constraints],
                key=lambda item: (item[0], item[1], item[2]),
            )
            return {
                "category": q.category,
                "dietary_tags": sorted(q.dietary_tags),
                "nutrient_constraints": nutrients,
            }

        assert canonical(en_q) == canonical(fr_q)


class TestFrenchImperativeParity:
    def test_donner_query_maps_to_vegan_high_protein_snacks(self, preprocessor, parser):
        fr = "donner des collations végétaliennes riches en protéines"
        q = _parse_fr(preprocessor, parser, fr)

        assert q.category == "snacks"
        assert "vegan" in q.dietary_tags
        assert "vegetarian" not in q.dietary_tags
        assert "donner" not in q.search_terms
        assert any(c.nutrient == "proteins_100g" and c.operator == ">=" and c.value == 10.0 for c in q.nutrient_constraints)
