"""Tests for the intent parser."""

import pytest

from off_ai.intent_parser import FoodQuery, IntentParser, NutrientConstraint


@pytest.fixture
def parser():
    return IntentParser()


# ---------------------------------------------------------------------------
# Category extraction
# ---------------------------------------------------------------------------

class TestCategoryExtraction:
    def test_snack_category(self, parser):
        q = parser.parse("high protein vegan snack under 200 calories")
        assert q.category == "snacks"

    def test_cereal_category(self, parser):
        q = parser.parse("low sodium cereal for diabetics")
        assert q.category == "cereals"

    def test_chocolate_category(self, parser):
        q = parser.parse("healthier alternative to Nutella chocolate spread")
        assert q.category == "chocolates"

    def test_no_category(self, parser):
        q = parser.parse("low fat food")
        assert q.category is None

    def test_beverage_category(self, parser):
        q = parser.parse("sugar-free drink")
        assert q.category == "beverages"


# ---------------------------------------------------------------------------
# Dietary tag extraction
# ---------------------------------------------------------------------------

class TestDietaryTags:
    def test_vegan_tag(self, parser):
        q = parser.parse("high protein vegan snack")
        assert "vegan" in q.dietary_tags

    def test_gluten_free_tag(self, parser):
        q = parser.parse("gluten free pasta")
        assert "gluten-free" in q.dietary_tags

    def test_organic_tag(self, parser):
        q = parser.parse("organic breakfast cereal")
        assert "organic" in q.dietary_tags

    def test_multiple_tags(self, parser):
        q = parser.parse("organic vegan gluten-free snack")
        assert "vegan" in q.dietary_tags
        assert "organic" in q.dietary_tags
        assert "gluten-free" in q.dietary_tags

    def test_no_tags(self, parser):
        q = parser.parse("peanut butter")
        assert q.dietary_tags == []


# ---------------------------------------------------------------------------
# Numeric constraint extraction
# ---------------------------------------------------------------------------

class TestNumericConstraints:
    def test_under_calories(self, parser):
        q = parser.parse("snack under 200 calories")
        calorie_constraints = [
            c for c in q.nutrient_constraints if "kcal" in c.nutrient
        ]
        assert len(calorie_constraints) == 1
        c = calorie_constraints[0]
        assert c.operator == "<="
        assert c.value == 200.0

    def test_over_protein(self, parser):
        q = parser.parse("cereal with over 10g protein")
        protein_constraints = [
            c for c in q.nutrient_constraints if "protein" in c.nutrient
        ]
        assert len(protein_constraints) == 1
        c = protein_constraints[0]
        assert c.operator == ">="
        assert c.value == 10.0

    def test_max_sodium(self, parser):
        q = parser.parse("maximum 0.5g sodium per 100g")
        sodium_constraints = [
            c for c in q.nutrient_constraints if "sodium" in c.nutrient
        ]
        assert len(sodium_constraints) == 1
        c = sodium_constraints[0]
        assert c.operator == "<="
        assert c.value == 0.5

    def test_at_least_fat(self, parser):
        q = parser.parse("at least 5g fat")
        fat_constraints = [
            c for c in q.nutrient_constraints if c.nutrient == "fat_100g"
        ]
        assert len(fat_constraints) == 1
        assert fat_constraints[0].operator == ">="


# ---------------------------------------------------------------------------
# Qualitative constraint extraction
# ---------------------------------------------------------------------------

class TestQualitativeConstraints:
    def test_high_protein(self, parser):
        q = parser.parse("high protein vegan snack")
        protein_c = [c for c in q.nutrient_constraints if "protein" in c.nutrient]
        assert len(protein_c) >= 1
        assert protein_c[0].operator == ">="

    def test_low_sodium(self, parser):
        q = parser.parse("low sodium cereal")
        sodium_c = [c for c in q.nutrient_constraints if "sodium" in c.nutrient]
        assert len(sodium_c) >= 1
        assert sodium_c[0].operator == "<="

    def test_qualitative_does_not_duplicate_numeric(self, parser):
        """Qualitative 'high protein' should not add a second constraint when
        an explicit numeric protein constraint is already present."""
        q = parser.parse("over 15g protein high protein bar")
        protein_c = [c for c in q.nutrient_constraints if "protein" in c.nutrient]
        # Should have exactly one protein constraint (the numeric one)
        assert len(protein_c) == 1
        assert protein_c[0].value == 15.0


# ---------------------------------------------------------------------------
# Comparison / alternative mode
# ---------------------------------------------------------------------------

class TestComparisonMode:
    def test_alternative_to(self, parser):
        q = parser.parse("healthier alternative to Nutella")
        assert q.comparison_product is not None
        assert "nutella" in q.comparison_product.lower()

    def test_instead_of(self, parser):
        q = parser.parse("instead of peanut butter")
        assert q.comparison_product is not None
        assert "peanut butter" in q.comparison_product.lower()

    def test_no_comparison(self, parser):
        q = parser.parse("organic vegan snack")
        assert q.comparison_product is None


# ---------------------------------------------------------------------------
# FoodQuery serialisation
# ---------------------------------------------------------------------------

class TestFoodQuerySerialization:
    def test_to_dict_has_required_keys(self, parser):
        q = parser.parse("high protein vegan snack under 200 calories")
        d = q.to_dict()
        for key in ("raw_text", "category", "nutrient_constraints", "dietary_tags"):
            assert key in d

    def test_to_dict_nutrient_constraints_structure(self, parser):
        q = parser.parse("under 200 calories")
        d = q.to_dict()
        assert isinstance(d["nutrient_constraints"], list)
        if d["nutrient_constraints"]:
            c = d["nutrient_constraints"][0]
            assert "nutrient" in c
            assert "operator" in c
            assert "value" in c

    def test_str_representation(self, parser):
        q = parser.parse("high protein vegan snack under 200 calories")
        text = str(q)
        assert "snack" in text or "protein" in text or "vegan" in text


# ---------------------------------------------------------------------------
# NutrientConstraint
# ---------------------------------------------------------------------------

class TestNutrientConstraint:
    def test_str(self):
        c = NutrientConstraint("proteins_100g", ">=", 10.0, "g")
        assert "proteins_100g" in str(c)
        assert ">=" in str(c)
        assert "10.0" in str(c)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_query(self, parser):
        q = parser.parse("")
        assert isinstance(q, FoodQuery)
        assert q.category is None
        assert q.dietary_tags == []
        assert q.nutrient_constraints == []

    def test_raw_text_preserved(self, parser):
        text = "high protein vegan snack under 200 calories"
        q = parser.parse(text)
        assert q.raw_text == text

    def test_case_insensitive(self, parser):
        q = parser.parse("HIGH PROTEIN VEGAN SNACK")
        assert "vegan" in q.dietary_tags
        assert q.category == "snacks"
