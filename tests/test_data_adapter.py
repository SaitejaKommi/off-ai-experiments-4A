"""Tests for the data adapter (unit tests, no network calls)."""

import pytest

from off_ai.data_adapter import Product, _parse_product
from off_ai.intent_parser import NutrientConstraint


# ---------------------------------------------------------------------------
# _parse_product helper
# ---------------------------------------------------------------------------

class TestParseProduct:
    def test_basic_fields(self):
        raw = {
            "code": "3017620422003",
            "product_name": "Nutella",
            "brands": "Ferrero",
            "nutriscore_grade": "e",
            "nova_group": 4,
            "nutriments": {
                "energy-kcal_100g": 530.0,
                "sugars_100g": 56.3,
                "fat_100g": 30.9,
                "proteins_100g": 6.3,
            },
            "additives_tags": ["en:e322", "en:e471"],
            "additives_n": 2,
            "labels_tags": [],
            "categories_tags": ["en:spreads", "en:chocolate-spreads"],
        }
        product = _parse_product(raw)
        assert product.barcode == "3017620422003"
        assert product.name == "Nutella"
        assert product.brands == "Ferrero"
        assert product.nutriscore == "e"
        assert product.nova_group == 4
        assert product.nutrients["energy-kcal_100g"] == 530.0
        assert product.additives_count == 2

    def test_missing_fields_default(self):
        product = _parse_product({})
        assert product.name == "Unknown"
        assert product.nutrients == {}
        assert product.additives == []
        assert product.nova_group is None
        assert product.nutriscore is None

    def test_categories_stripped_of_prefix(self):
        raw = {"categories_tags": ["en:snacks", "fr:snacks"]}
        product = _parse_product(raw)
        assert "snacks" in product.categories

    def test_nova_group_as_string(self):
        raw = {"nova_group": "3"}
        product = _parse_product(raw)
        assert product.nova_group == 3


# ---------------------------------------------------------------------------
# Product.passes_constraints
# ---------------------------------------------------------------------------

class TestPassesConstraints:
    def _make_product(self, nutrients: dict) -> Product:
        return Product(
            barcode="0000000000001",
            name="Test",
            nutrients=nutrients,
        )

    def test_passes_upper_bound(self):
        p = self._make_product({"energy-kcal_100g": 150.0})
        c = NutrientConstraint("energy-kcal_100g", "<=", 200.0, "kcal")
        assert p.passes_constraints([c]) is True

    def test_fails_upper_bound(self):
        p = self._make_product({"energy-kcal_100g": 250.0})
        c = NutrientConstraint("energy-kcal_100g", "<=", 200.0, "kcal")
        assert p.passes_constraints([c]) is False

    def test_passes_lower_bound(self):
        p = self._make_product({"proteins_100g": 15.0})
        c = NutrientConstraint("proteins_100g", ">=", 10.0, "g")
        assert p.passes_constraints([c]) is True

    def test_fails_lower_bound(self):
        p = self._make_product({"proteins_100g": 5.0})
        c = NutrientConstraint("proteins_100g", ">=", 10.0, "g")
        assert p.passes_constraints([c]) is False

    def test_missing_nutrient_passes(self):
        """Missing nutrient data should not filter out the product."""
        p = self._make_product({})
        c = NutrientConstraint("proteins_100g", ">=", 10.0, "g")
        assert p.passes_constraints([c]) is True

    def test_multiple_constraints_all_pass(self):
        p = self._make_product({
            "proteins_100g": 12.0,
            "energy-kcal_100g": 150.0,
        })
        constraints = [
            NutrientConstraint("proteins_100g", ">=", 10.0, "g"),
            NutrientConstraint("energy-kcal_100g", "<=", 200.0, "kcal"),
        ]
        assert p.passes_constraints(constraints) is True

    def test_multiple_constraints_one_fails(self):
        p = self._make_product({
            "proteins_100g": 5.0,
            "energy-kcal_100g": 150.0,
        })
        constraints = [
            NutrientConstraint("proteins_100g", ">=", 10.0, "g"),
            NutrientConstraint("energy-kcal_100g", "<=", 200.0, "kcal"),
        ]
        assert p.passes_constraints(constraints) is False

    def test_empty_constraints_always_pass(self):
        p = self._make_product({})
        assert p.passes_constraints([]) is True


# ---------------------------------------------------------------------------
# Product serialisation
# ---------------------------------------------------------------------------

class TestProductSerialization:
    def test_to_dict_keys(self):
        p = Product(
            barcode="123",
            name="Test",
            nutrients={"energy-kcal_100g": 100.0},
            nutriscore="b",
        )
        d = p.to_dict()
        for key in (
            "barcode", "name", "brands", "categories", "nutrients",
            "nutriscore", "nova_group", "additives", "labels",
        ):
            assert key in d

    def test_nutrient_method(self):
        p = Product(barcode="1", name="X", nutrients={"fat_100g": 5.0})
        assert p.nutrient("fat_100g") == 5.0
        assert p.nutrient("missing_key") is None
